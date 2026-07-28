"""
投稿直前チェック。

これまでの検討で洗い出した「投稿は成功しているが実質的に意味がない」パターンを
機械的に検出し、いずれかに該当する商品は投稿対象から自動除外する。

チェック項目:
1. リンクの疎通確認(ステータスコードが200番台か)
2. 販売終了・品切れワードの検出
3. 返信文中の価格が、APIから取得した実データと文字列レベルで一致するか
4. アフィリエイトIDがURL内に正しい形式で含まれているか

【2026-07 修正】item.rakuten.co.jpへの疎通確認リクエストにUser-Agentがないと
Bot判定され応答が極端に遅くなり(timeout=10で全滅)、投稿対象が0件になっていた。
ブラウザ相当のUser-Agentを付与し、timeoutも15秒に緩和する。

【2026-07 修正】生のaffiliate_id文字列がURLにそのまま含まれるかを見ていたが、
実際の楽天アフィリエイトURLはハッシュ化されたトラッキングコードに変換されるため
(例: https://hb.afl.rakuten.co.jp/hgc/xxxxx.../?pc=...)、affiliate_id自体の
文字列はURLに一切現れない。そのため常に不一致になり、正当な報酬付きリンクまで
ほぼ全件「無報酬リンク」と誤判定していたバグを修正し、hb.afl.rakuten.co.jp
ドメインを使っているかどうかで判定するように変更した。

【2026-07 大幅変更】投稿フォーマットを「本文(煽り)+返信(フック+リンク)」の
2段構成に変更したことに伴い、事実確認の対象を変更した。
- 商品名は本文・返信文どちらにも書かない設計(リンクプレビューに任せる)ため、
  商品名の一致チェック(旧 check_fact_consistency / _extract_core_name)は廃止。
- 価格チェックの対象を本文(post_text)から返信文(reply_text)に変更。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests

SOLD_OUT_KEYWORDS = ["販売終了", "品切れ", "売り切れ", "ページが見つかりません", "在庫なし"]

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


@dataclass
class CheckResult:
    passed: bool
    reason: str = ""


def check_link_reachable(url: str, timeout: int = 15) -> CheckResult:
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True, headers=_BROWSER_HEADERS)
    except requests.RequestException as exc:
        return CheckResult(passed=False, reason=f"接続エラー: {exc}")

    if not (200 <= resp.status_code < 300):
        return CheckResult(passed=False, reason=f"ステータスコード異常: {resp.status_code}")

    body = resp.text
    for kw in SOLD_OUT_KEYWORDS:
        if kw in body:
            return CheckResult(passed=False, reason=f"販売終了/品切れの疑い(検出語: {kw})")

    return CheckResult(passed=True)


def check_price_consistency(reply_text: str, item_price: int) -> CheckResult:
    """返信文中に実際の価格が正しく含まれているか確認する(表現部分中の事実齟齬を防ぐ)。"""
    price_str = f"{item_price:,}"
    if price_str not in reply_text and str(item_price) not in reply_text:
        return CheckResult(passed=False, reason=f"返信文に価格が含まれていません: 期待='{price_str}円'")
    return CheckResult(passed=True)


def check_affiliate_id_present(url: str, affiliate_id: str) -> CheckResult:
    """URLが楽天アフィリエイトの正規トラッキングリンク(hb.afl.rakuten.co.jp)かどうかを確認する。"""
    if not affiliate_id:
        return CheckResult(passed=False, reason="affiliate_idが設定されていません")
    if "hb.afl.rakuten.co.jp" not in url:
        return CheckResult(passed=False, reason="楽天アフィリエイトのトラッキングリンク形式ではありません(無報酬リンクの疑い)")
    return CheckResult(passed=True)


def run_all_checks(main_text: str, reply_text: str, item_url: str, item_price: int) -> CheckResult:
    """全チェックを実行し、いずれかが失敗したら理由付きで失敗を返す。

    main_text は現状チェック対象にしていない(事実を含まない煽り文のため)が、
    将来的にNGワード検出等を行う場合に備えて引数として受け取っておく。
    """
    affiliate_id = os.environ.get("RAKUTEN_AFFILIATE_ID", "")

    checks = [
        check_link_reachable(item_url),
        check_price_consistency(reply_text, item_price),
        check_affiliate_id_present(item_url, affiliate_id),
    ]
    for result in checks:
        if not result.passed:
            return result
    return CheckResult(passed=True)