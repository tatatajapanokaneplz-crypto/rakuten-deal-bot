"""
投稿文生成モジュール。

これまでの検討の核心:「テンプレートに事実を機械的に差し込むだけ」では
- bot的なワンパターンさが目立ち、SNS側にもGoogleにも量産パターンとして見抜かれやすい
- 「独自の付加価値」が失われる

一方で「AIに商品説明を自由に書かせる」と
- 型番違い・旧モデル混同などのハルシネーションが混入するリスクがある

そのため、投稿文を以下の2つに明確に分離する:
- 事実部分: 商品名・価格・リンク。AIには生成させず、Rakutenのデータをそのまま使う。
            投稿後、link_checker.py で機械的に一致確認する対象。
- 表現部分: キャッチコピー、ランキング内での立ち位置の解説など。AIが自由に生成してよい。
            ここは機械チェックの対象外(=多様な自然な文章になる)。

【2026-07 修正】非推奨の google.generativeai パッケージは、Google AI Studioが
新規発行する "AQ." 形式のAuthキーに対応していないため、現行の google-genai
パッケージ(Interactions API)に移行済み。

【2026-07 追記】単純な一言キャッチコピー生成にthinkingは不要かつコスト増の原因になるため、
thinking_level="low"を指定してコストを抑える。

【2026-07 追記】アカウントのペルソナ(system_instruction)を追加。
見た目はおじいちゃん(グランパ)だが、中身は心が20代でトレンドやガジェットを
自分ごととして楽しんでいる、というギャップキャラクター設定。
「若い子の間で」のように若者を外側から語る表現は禁止し、当事者目線で書かせる。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from google import genai
import yaml

from src.rakuten_client import RakutenItem

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "filters.yaml")

_PERSONA_SYSTEM_INSTRUCTION = (
    "あなたは陽気で親しみやすい「グランパ」というおじいちゃんキャラクターです。"
    "話し言葉にはおじいちゃんらしい柔らかい語尾(例:「〜じゃ」「わし」「〜のう」など)を"
    "軽く交えますが、中身は心が20代で、トレンドの商品やガジェットを本当に自分の趣味として"
    "楽しんでいます。"
    "「若い子の間で」「今どきの若者は」のように、若者を外側から評論するような言い回しは"
    "絶対に使わないでください。あくまで自分自身が当事者としてその商品を気に入っている、"
    "という自然なテンションで書いてください。"
    "誇大な効果効能の断定表現や、過度に煽る表現は避けてください。"
)


@dataclass
class ComposedPost:
    text: str
    item: RakutenItem


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _generate_catch_copy(item: RakutenItem, track: str) -> str:
    """Gemini APIで、事実を歪めない範囲のキャッチコピー(表現部分)だけを生成させる。"""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    if track == "timesale":
        instruction = "今だけのお得情報として、短く勢いのあるキャッチコピーを1文で。"
    else:
        instruction = "人気ランキング入りしている理由が伝わるような、短い一言コメントを1文で。"

    prompt = (
        f"{instruction}\n"
        f"商品名や価格などの具体的な事実は、この文には含めないでください(別途固定で付記されます)。\n"
        f"絵文字は控えめに、誇大な効能・効果の表現は避けてください。\n"
        f"商品ジャンル: {item.genre_id or '不明'}\n"
        f"参考情報(店舗名): {item.shop_name}"
    )
    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        system_instruction=_PERSONA_SYSTEM_INSTRUCTION,
        input=prompt,
        generation_config={"thinking_level": "low"},
    )
    return interaction.output_text.strip()


def compose(item: RakutenItem, track: str) -> ComposedPost:
    """
    track: "timesale" または "ranking"

    投稿文の構造:
    【PR】<キャッチコピー(AI生成・表現部分)>

    <商品名(事実・固定)>
    <価格(事実・固定)>円
    <URL(事実・固定、アフィリエイトID込み)>

    ※このアカウントは自動投稿botです
    """
    config = _load_config()
    pr_label = config["post_composer"]["fixed_pr_label"]
    bot_disclosure = config["post_composer"]["bot_disclosure"]

    catch_copy = _generate_catch_copy(item, track)

    text = (
        f"{pr_label} {catch_copy}\n\n"
        f"{item.item_name}\n"
        f"{item.item_price:,}円\n"
        f"{item.item_url}\n\n"
        f"{bot_disclosure}"
    )
    return ComposedPost(text=text, item=item)