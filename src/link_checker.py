"""
投稿直前チェック。

これまでの検討で洗い出した「投稿は成功しているが実質的に意味がない」パターンを
機械的に検出し、いずれかに該当する商品は投稿対象から自動除外する。

チェック項目:
1. リンクの疎通確認(ステータスコードが200番台か)
2. 販売終了・品切れワードの検出
3. 投稿文中の商品名・価格が、APIから取得した実データと文字列レベルで一致するか
4. アフィリエイトIDがURL内に正しい形式で含まれているか
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import requests

SOLD_OUT_KEYWORDS = ["販売終了", "品切れ", "売り切れ", "ページが見つかりません", "在庫なし"]


@dataclass
class CheckResult:
    passed: bool
    reason: str = ""


def check_link_reachable(url: str, timeout: int = 10) -> CheckResult:
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        return CheckResult(passed=False, reason=f"接続エラー: {exc}")

    if not (200 <= resp.status_code < 300):
        return CheckResult(passed=False, reason=f"ステータスコード異常: {resp.status_code}")

    body = resp.text
    for kw in SOLD_OUT_KEYWORDS:
        if kw in body:
            return CheckResult(passed=False, reason=f"販売終了/品切れの疑い(検出語: {kw})")

    return CheckResult(passed=True)


def check_fact_consistency(post_text: str, item_name: str, item_price: int) -> CheckResult:
    """投稿文中の商品名・価格が、実データと一致するか確認する(表現部分は対象外)。"""
    # 商品名は完全一致ではなく、実データの主要な部分文字列が含まれているかで判定
    # (AIが多少言い回しを変えても、固有名詞部分は保持される前提)
    name_core = _extract_core_name(item_name)
    if name_core not in post_text:
        return CheckResult(passed=False, reason=f"商品名の不一致: 期待='{name_core}'")

    price_str = f"{item_price:,}"
    if price_str not in post_text and str(item_price) not in post_text:
        return CheckResult(passed=False, reason=f"価格の不一致: 期待='{price_str}円'")

    return CheckResult(passed=True)


def check_affiliate_id_present(url: str, affiliate_id: str) -> CheckResult:
    """アフィリエイトIDがURLに正しい形式で含まれているかを文字列検証する。"""
    if not affiliate_id:
        return CheckResult(passed=False, reason="affiliate_idが設定されていません")
    if affiliate_id not in url:
        return CheckResult(passed=False, reason="URLにアフィリエイトIDが含まれていません(無報酬リンクの疑い)")
    return CheckResult(passed=True)


def _extract_core_name(item_name: str, max_len: int = 20) -> str:
    """商品名の先頭部分(固有名詞が集中しやすい)を抽出する簡易ロジック。"""
    cleaned = re.sub(r"[\[\]【】].*?[\]\]】]", "", item_name)  # 記号で囲まれた装飾部分を除去
    return cleaned.strip()[:max_len]


def run_all_checks(post_text: str, item_url: str, item_name: str, item_price: int) -> CheckResult:
    """全チェックを実行し、いずれかが失敗したら理由付きで失敗を返す。"""
    affiliate_id = os.environ.get("RAKUTEN_AFFILIATE_ID", "")

    checks = [
        check_link_reachable(item_url),
        check_fact_consistency(post_text, item_name, item_price),
        check_affiliate_id_present(item_url, affiliate_id),
    ]
    for result in checks:
        if not result.passed:
            return result
    return CheckResult(passed=True)
