"""
ランキングトラック: 人気商品紹介。

config/filters.yaml のフィルタ条件(レビュー数・評価スコア・除外ジャンル)を適用する。
速報トラックと違い、鮮度より品質担保を優先する。

【2026-07 変更】投稿はスレッド形式(本文+返信)。BUFFER_CHANNEL_ID_X は
twitter、BUFFER_CHANNEL_ID_THREADS は threads として Buffer に渡す
(createPostのmetadataキーがサービスごとに異なるため)。

【2026-07 変更(投稿頻度の調整)】1回の実行で最大3件まとめて投稿していたが、
「一気に投稿するのはアルゴリズム的にもフォロワー的にも良くない」との判断から、
1回の実行につき1件のみ投稿する形に変更した。その代わり、ワークフロー側の
実行回数を1日1回→3回(11:00/16:00/23:00 JST)に増やし、timesaleの実行時刻
(9:00/13:00/20:00 JST)とずらすことで、1日6件程度の投稿を間隔を空けて
配信するようにした(.github/workflows/ranking.yml参照)。
"""

from __future__ import annotations

import argparse
import os
import sys

import yaml
from dotenv import load_dotenv

from src import healthcheck, link_checker, post_composer
from src.buffer_client import BufferClient
from src.rakuten_client import RakutenClient

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "filters.yaml")

# env変数名 -> BufferのcreatePost.metadataキー(サービス名)の対応
CHANNEL_SERVICE_MAP = {
    "BUFFER_CHANNEL_ID_X": "twitter",
    "BUFFER_CHANNEL_ID_THREADS": "threads",
}

# 1回の実行で投稿する件数の上限。バースト投稿を避けるため1に固定している。
MAX_POSTS_PER_RUN = 1


def _load_filters() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["ranking"]


def _passes_filter(item, filters: dict) -> bool:
    if item.review_count < filters["min_review_count"]:
        return False
    if item.review_average < filters["min_review_score"]:
        return False
    if item.genre_id in filters.get("excluded_genre_ids", []):
        return False
    return True


def main(dry_run: bool = False) -> int:
    load_dotenv()
    healthcheck_url = os.environ.get("HEALTHCHECK_URL_RANKING", "")
    healthcheck.ping_start(healthcheck_url)

    try:
        filters = _load_filters()
        rakuten = RakutenClient()
        buffer = BufferClient()

        candidates = rakuten.get_ranking(genre_id="0", page=1)
        posted = 0

        for item in candidates:
            if not _passes_filter(item, filters):
                continue

            composed = post_composer.compose(item, track="ranking")
            check = link_checker.run_all_checks(
                main_text=composed.main_text,
                reply_text=composed.reply_text,
                item_url=item.item_url,
                item_price=item.item_price,
            )
            if not check.passed:
                print(f"[SKIP] {item.item_name}: {check.reason}")
                continue

            for channel_env, service in CHANNEL_SERVICE_MAP.items():
                channel_id = os.environ.get(channel_env, "")
                if not channel_id:
                    continue
                result = buffer.create_post(
                    channel_id, service, composed.texts, dry_run=dry_run
                )
                if not result.success:
                    print(f"[ERROR] 投稿失敗 channel={channel_id}: {result.error}")

            posted += 1
            if posted >= MAX_POSTS_PER_RUN:
                break

        healthcheck.ping_success(healthcheck_url)
        print(f"完了: {posted}件投稿")
        return 0

    except Exception as exc:  # noqa: BLE001
        healthcheck.ping_failure(healthcheck_url, message=str(exc))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run))