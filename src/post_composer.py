"""
投稿文生成モジュール。

これまでの検討の核心:「テンプレートに事実を機械的に差し込むだけ」では
- bot的なワンパターンさが目立ち、SNS側にもGoogleにも量産パターンとして見抜かれやすい
- 「独自の付加価値」が失われる

一方で「AIに商品説明を自由に書かせる」と
- 型番違い・旧モデル混同などのハルシネーションが混入するリスクがある

そのため、投稿文を以下の2つに明確に分離する:
- 事実部分: 価格。AIには自由生成させず、実データをプロンプトに明示して「そのまま使う」
            よう指示し、投稿後 link_checker.py で機械的に一致確認する対象とする。
- 表現部分: 煽り文・リアクション文。AIが自由に生成してよい。

【2026-07 修正】非推奨の google.generativeai パッケージは、Google AI Studioが
新規発行する "AQ." 形式のAuthキーに対応していないため、現行の google-genai
パッケージ(Interactions API)に移行済み。

【2026-07 追記】単純な短文生成にthinkingは不要かつコスト増の原因になるため、
thinking_level="low"を指定してコストを抑える。

【2026-07 追記】アカウントのペルソナ(system_instruction)を追加。
見た目はおじいちゃん(グランパ)だが、中身は心が20代でトレンドやガジェットを
自分ごととして楽しんでいる、というギャップキャラクター設定。
「若い子の間で」のように若者を外側から語る表現は禁止し、当事者目線で書かせる。

【2026-07 大幅変更】投稿フォーマットを「本文(煽り)+返信(フック+リンク)」の
2段構成(スレッド)に変更した。理由:
- Xのアルゴリズムは本文に外部リンクを含む投稿の表示を抑制する傾向があるため、
  リンクは返信側に置き、本文には含めない
- リンクを踏めばOGP(リンクカード)で商品名・画像が自動表示されるため、
  本文・返信文中に商品名を重複して書く必要がない(むしろ冗長)
- 「※このアカウントは自動投稿botです」は本文から削除し、プロフィール欄側で
  明記する運用に変更(エンゲージメント低下を避けるため)
- 【PR】は本文冒頭ではなく、返信文末尾の#PRハッシュタグとして表示する

【2026-07 バグ修正】healthchecks.io の "ranking" チェックが
"Cannot send a request, as the client has been closed." で失敗する障害が発生。
genai.Clientを一時オブジェクトとしてチェーン呼び出ししていたのが原因だったため、
プロセス内シングルトンとしてキャッシュするよう修正済み。

【2026-07 修正(本文の単調さ)】本文の切り方の例を15パターンに拡充。

【2026-07 修正(返信の語尾の単調さ + 読点の重複)】返信の語尾が「ｗｗｗ」に
偏っていた問題を修正し、語尾の例を30パターンに拡充。読点の重複も整形するよう
にした。

【2026-07 修正(締めの句読点の単調さ)】語尾の"単語"は散らばるようになったが、
実際の出力を確認したところ、今度は締めの句読点が3件とも「！」で統一されて
いた(「テンション高めで」という指示に引っ張られ、モデルが感嘆符を選びがちに
なっていたと推測される)。これも「ｗｗｗ」偏重と同根の問題。そのため、
締めの句読点についても「！」「。」「…」「句読点なしで言い切り」を毎回変える
よう明示的に指示を追加した。
"""

from __future__ import annotations

import os
import re
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

# genai.Clientをプロセス内でシングルトンとして使い回す(temporary objectとして
# 使うと google-genai 1.39.0以降で内部httpxクライアントが早期closeされる不具合があるため)。
_genai_client: genai.Client | None = None

# 本文の切り口ヒント(15パターン)。あくまで語感の例であり、AIはこれ以外の
# 表現も自由に使ってよい。カテゴリを分散させることで特定パターンへの偏りを防ぐ。
_TEASER_HOOK_EXAMPLES = [
    "まさかの、",
    "今だけ、",
    "これだけで、",
    "ところが、",
    "でもな、",
    "聞いてくれ、",
    "実はな、",
    "なんとまあ、",
    "ここからが本題での、",
    "しかもじゃ、",
    "それがどうも、",
    "わけがあってな、",
    "驚くことに、",
    "ここだけの話、",
    "実際のところ、",
]

# 返信リアクションの語尾ヒント(30パターン)。「ｗｗｗ」だけに偏らないための例。
_REACTION_ENDING_EXAMPLES = [
    "ｗｗｗ",
    "…",
    "じゃろ!",
    "たまらんのう",
    "にやけが止まらんわ",
    "まいったのう",
    "しびれたわい",
    "ゾクゾクしたぞ",
    "これは反則じゃろ",
    "惚れてもうたわ",
    "たまげたのう",
    "これはやられたわ",
    "にんまりしてもうた",
    "最高すぎるじゃろ",
    "わしの負けじゃ",
    "こりゃたまらんて",
    "くせになりそうじゃ",
    "なんじゃこりゃ",
    "一目惚れしたわい",
    "こんなのアリかよ",
    "トキメキが止まらん",
    "これは反則級じゃ",
    "わしゃ興奮しっぱなしじゃ",
    "たまらん気持ちになったわい",
    "これは事件じゃろ",
    "わしの心つかまれたわ",
    "しばらく興奮冷めやらんかったわ",
    "こりゃ参ったのう",
    "一気にテンション上がったわい",
    "こんなん惚れてまうやろ",
]


def _collapse_repeated_punctuation(text: str) -> str:
    """連続する読点・句点を1つに整形する(「見つけてな、、」→「見つけてな、」)。

    「ｗｗｗ」「…」のような意図的な繰り返し表現は対象外(崩さない)。
    """
    text = re.sub(r"、{2,}", "、", text)
    text = re.sub(r"。{2,}", "。", text)
    return text


@dataclass
class ComposedPost:
    """投稿するスレッドの各パート。texts[0]が本文、texts[1]が返信。"""

    texts: list[str]
    item: RakutenItem

    @property
    def main_text(self) -> str:
        return self.texts[0]

    @property
    def reply_text(self) -> str:
        return self.texts[1]


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _client() -> genai.Client:
    """genai.Clientをプロセス内で1つだけ生成し、以降は使い回す。"""
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _genai_client


def _generate_teaser(item: RakutenItem, track: str) -> str:
    """本文用: 事実にもオチにも触れず、"できるだけ早く"切り上げる煽り文を生成する。"""
    if track == "timesale":
        situation = "ランキングやセールを眺めていたら気になる商品を見つけて、つい買ってしまった"
    else:
        situation = "人気ランキングを眺めていたら気になる商品を見つけた"

    hook_list = "、".join(_TEASER_HOOK_EXAMPLES)

    prompt = (
        f"{situation}、という体で、続きが気になる書き出し文を書いてください。\n\n"
        f"絶対に守ること:\n"
        f"・全体で30〜40字程度、1文以内に収めること。長く書かない\n"
        f"・具体的な商品名・価格・数量などの事実は一切書かない\n"
        f"・「デザインが良い」「機能が優れている」のような、良かった理由の説明も"
        f"一切書かない。理由や結論は全て返信側で明かすので、本文では触れない\n"
        f"・文を完成させる必要はない。読点(、)で止めて構わないので、思い切って"
        f"早く文を切ること。長く続けるほど本文だけで話が伝わってしまい失敗になる\n"
        f"・切り方を「これが、」「それが、」のような決まった形に固定しないこと。"
        f"以下は語感の例であり、これに限らず自由に考えてよい"
        f"(同じパターンの繰り返しは避けること):\n"
        f"{hook_list}\n\n"
        f"・絵文字は使わない\n\n"
        f"悪い例(これはNG。理由の説明まで書いてしまい、長すぎる):\n"
        f"「気になるアイテムがあってな。デザインも機能もドンピシャで、心が"
        f"くすぐられまくったんじゃが…」\n\n"
        f"商品ジャンル: {item.genre_id or '不明'}"
    )
    client = _client()
    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        system_instruction=_PERSONA_SYSTEM_INSTRUCTION,
        input=prompt,
        generation_config={"thinking_level": "low"},
    )
    return _collapse_repeated_punctuation(interaction.output_text.strip())


def _generate_reply_hook(item: RakutenItem) -> str:
    """返信用: 実際の価格に軽く触れつつ、テンション高めの一言リアクションを生成する。

    価格は実データをそのまま使うようプロンプトで明示指示し、link_checker.py側で
    生成結果に実際の価格文字列が含まれているかを機械チェックする。
    語尾の単語だけでなく、締めの句読点(！/。/…/句読点なし)も毎回変わるよう指示する。
    """
    price_str = f"{item.item_price:,}円"
    ending_list = "、".join(_REACTION_ENDING_EXAMPLES)

    prompt = (
        f"さっき話題に出した商品の値段にテンション高めでリアクションする、短い一言(1文)を"
        f"書いてください。\n"
        f"実際の価格は「{price_str}」です。この価格を必ずそのまま(数字も含めて)文中に"
        f"入れてください。\n"
        f"文末を「ｗｗｗ」に固定しないこと。以下は語尾の例であり、これに限らず"
        f"自由に考えてよい(同じ語尾の繰り返しは避けること):\n"
        f"{ending_list}\n\n"
        f"さらに、文の締めの句読点も「！」に固定しないこと。「！」「。」「…」"
        f"「句読点なしで言い切り」をランダムに使い分けること"
        f"(「！」ばかりが続くのは不自然なので避ける)。\n"
        f"誇張しすぎた煽り表現は避けてください。\n"
        f"商品名やURLはこの文には含めないでください(別途付記します)。"
    )
    client = _client()
    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        system_instruction=_PERSONA_SYSTEM_INSTRUCTION,
        input=prompt,
        generation_config={"thinking_level": "low"},
    )
    return _collapse_repeated_punctuation(interaction.output_text.strip())


def compose(item: RakutenItem, track: str) -> ComposedPost:
    """
    track: "timesale" または "ranking"

    投稿はスレッド形式(本文+返信)で構成する:
    本文: 事実もオチも伏せ、できるだけ早く切り上げる煽り文(AI生成)。
    返信: 価格に軽く触れるリアクション文(AI生成、価格は実データ埋め込み)
          + URL(アフィリエイトID込み) + #PR

    ※bot表記(「このアカウントは自動投稿botです」)は本文には含めない。
      アカウントのプロフィール欄側で明記する運用とする(config/filters.yaml参照)。
    """
    config = _load_config()
    pr_label = config["post_composer"]["fixed_pr_label"]

    main_text = _generate_teaser(item, track)
    reaction = _generate_reply_hook(item)

    reply_text = f"{reaction}\n\n{item.item_url}\n\n{pr_label}"

    return ComposedPost(texts=[main_text, reply_text], item=item)