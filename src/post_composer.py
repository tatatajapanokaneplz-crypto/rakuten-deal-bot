"""
謚慕ｨｿ譁・函謌舌Δ繧ｸ繝･繝ｼ繝ｫ縲・

縺薙ｌ縺ｾ縺ｧ縺ｮ讀懆ｨ弱・譬ｸ蠢・縲後ユ繝ｳ繝励Ξ繝ｼ繝医↓莠句ｮ溘ｒ讖滓｢ｰ逧・↓蟾ｮ縺苓ｾｼ繧縺縺代阪〒縺ｯ
- bot逧・↑繝ｯ繝ｳ繝代ち繝ｼ繝ｳ縺輔′逶ｮ遶九■縲ヾNS蛛ｴ縺ｫ繧・oogle縺ｫ繧る㍼逕｣繝代ち繝ｼ繝ｳ縺ｨ縺励※隕区栢縺九ｌ繧・☆縺・
- 縲檎峡閾ｪ縺ｮ莉伜刈萓｡蛟､縲阪′螟ｱ繧上ｌ繧・

荳譁ｹ縺ｧ縲窟I縺ｫ蝠・刀隱ｬ譏弱ｒ閾ｪ逕ｱ縺ｫ譖ｸ縺九○繧九阪→
- 蝙狗分驕輔＞繝ｻ譌ｧ繝｢繝・Ν豺ｷ蜷後↑縺ｩ縺ｮ繝上Ν繧ｷ繝阪・繧ｷ繝ｧ繝ｳ縺梧ｷｷ蜈･縺吶ｋ繝ｪ繧ｹ繧ｯ縺後≠繧・

縺昴・縺溘ａ縲∵兜遞ｿ譁・ｒ莉･荳九・2縺､縺ｫ譏守｢ｺ縺ｫ蛻・屬縺吶ｋ:
- 莠句ｮ滄Κ蛻・ 蝠・刀蜷阪・萓｡譬ｼ繝ｻ繝ｪ繝ｳ繧ｯ縲・I縺ｫ縺ｯ逕滓・縺輔○縺壹ヽakuten縺ｮ繝・・繧ｿ繧偵◎縺ｮ縺ｾ縺ｾ菴ｿ縺・・
            謚慕ｨｿ蠕後〕ink_checker.py 縺ｧ讖滓｢ｰ逧・↓荳閾ｴ遒ｺ隱阪☆繧句ｯｾ雎｡縲・
- 陦ｨ迴ｾ驛ｨ蛻・ 繧ｭ繝｣繝・メ繧ｳ繝斐・縲√Λ繝ｳ繧ｭ繝ｳ繧ｰ蜀・〒縺ｮ遶九■菴咲ｽｮ縺ｮ隗｣隱ｬ縺ｪ縺ｩ縲・I縺瑚・逕ｱ縺ｫ逕滓・縺励※繧医＞縲・
            縺薙％縺ｯ讖滓｢ｰ繝√ぉ繝・け縺ｮ蟇ｾ雎｡螟・=螟壽ｧ倥↑閾ｪ辟ｶ縺ｪ譁・ｫ縺ｫ縺ｪ繧・縲・
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import google.generativeai as genai
import yaml

from src.rakuten_client import RakutenItem

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "filters.yaml")


@dataclass
class ComposedPost:
    text: str
    item: RakutenItem


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _generate_catch_copy(item: RakutenItem, track: str) -> str:
    """Gemini API縺ｧ縲∽ｺ句ｮ溘ｒ豁ｪ繧√↑縺・ｯ・峇縺ｮ繧ｭ繝｣繝・メ繧ｳ繝斐・(陦ｨ迴ｾ驛ｨ蛻・縺縺代ｒ逕滓・縺輔○繧九・""
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash")

    if track == "timesale":
        instruction = "莉翫□縺代・縺雁ｾ玲ュ蝣ｱ縺ｨ縺励※縲∫洒縺丞兇縺・・縺ゅｋ繧ｭ繝｣繝・メ繧ｳ繝斐・繧・譁・〒縲・
    else:
        instruction = "莠ｺ豌励Λ繝ｳ繧ｭ繝ｳ繧ｰ蜈･繧翫＠縺ｦ縺・ｋ逅・罰縺御ｼ昴ｏ繧九ｈ縺・↑縲∫洒縺・ｸ險繧ｳ繝｡繝ｳ繝医ｒ1譁・〒縲・

    prompt = (
        f"{instruction}\n"
        f"蝠・刀蜷阪ｄ萓｡譬ｼ縺ｪ縺ｩ縺ｮ蜈ｷ菴鍋噪縺ｪ莠句ｮ溘・縲√％縺ｮ譁・↓縺ｯ蜷ｫ繧√↑縺・〒縺上□縺輔＞(蛻･騾泌崋螳壹〒莉倩ｨ倥＆繧後∪縺・縲・n"
        f"邨ｵ譁・ｭ励・謗ｧ縺医ａ縺ｫ縲∬ｪ・､ｧ縺ｪ蜉ｹ閭ｽ繝ｻ蜉ｹ譫懊・陦ｨ迴ｾ縺ｯ驕ｿ縺代※縺上□縺輔＞縲・n"
        f"蝠・刀繧ｸ繝｣繝ｳ繝ｫ: {item.genre_id or '荳肴・'}\n"
        f"蜿り・ュ蝣ｱ(蠎苓・蜷・: {item.shop_name}"
    )
    response = model.generate_content(prompt)
    return response.text.strip()


def compose(item: RakutenItem, track: str) -> ComposedPost:
    """
    track: "timesale" 縺ｾ縺溘・ "ranking"

    謚慕ｨｿ譁・・讒矩:
    縲娠R縲・繧ｭ繝｣繝・メ繧ｳ繝斐・(AI逕滓・繝ｻ陦ｨ迴ｾ驛ｨ蛻・>

    <蝠・刀蜷・莠句ｮ溘・蝗ｺ螳・>
    <萓｡譬ｼ(莠句ｮ溘・蝗ｺ螳・>蜀・
    <URL(莠句ｮ溘・蝗ｺ螳壹√い繝輔ぅ繝ｪ繧ｨ繧､繝・D霎ｼ縺ｿ)>

    窶ｻ縺薙・繧｢繧ｫ繧ｦ繝ｳ繝医・閾ｪ蜍墓兜遞ｿbot縺ｧ縺・
    """
    config = _load_config()
    pr_label = config["post_composer"]["fixed_pr_label"]
    bot_disclosure = config["post_composer"]["bot_disclosure"]

    catch_copy = _generate_catch_copy(item, track)

    text = (
        f"{pr_label} {catch_copy}\n\n"
        f"{item.item_name}\n"
        f"{item.item_price:,}蜀・n"
        f"{item.item_url}\n\n"
        f"{bot_disclosure}"
    )
    return ComposedPost(text=text, item=item)
