"""
速報トラック: タイムセール・クーポン速報。

フィルタは適用しない(鮮度優先という前提。README/config/filters.yaml 参照)。
ただし投稿直前チェック(リンク疎通・事実一致・アフィリエイトID確認)は必須。
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from src import healthcheck, link_checker, post_composer
from src.buffer_client import BufferClient
from src.rakuten_client import RakutenClient

# 速報対象として検索するキーワード。実運用では複数キーワードをローテーションする想定。
SEARCH_KEYWORDS = ["タイムセール", "クーポン", "お買い物マラソン"]


def main(dry_run: bool = False) -> int:
    load_dotenv()
    healthcheck_url = os.environ.get("HEALTHCHECK_URL_TIMESALE", "")
    healthcheck.ping_start(healthcheck_url)

    try:
        rakuten = RakutenClient()
        buffer = BufferClient()

        posted = 0
        for keyword in SEARCH_KEYWORDS:
            items = rakuten.search_items(keyword=keyword, hits=10)
            for item in items:
                composed = post_composer.compose(item, track="timesale")
                check = link_checker.run_all_checks(
                    post_text=composed.text,
                    item_url=item.item_url,
                    item_name=item.item_name,
                    item_price=item.item_price,
                )
                if not check.passed:
                    print(f"[SKIP] {item.item_name}: {check.reason}")
                    continue

                for channel_env in ("BUFFER_CHANNEL_ID_X", "BUFFER_CHANNEL_ID_THREADS"):
                    channel_id = os.environ.get(channel_env, "")
                    if not channel_id:
                        continue
                    result = buffer.create_post(channel_id, composed.text, dry_run=dry_run)
                    if not result.success:
                        print(f"[ERROR] 投稿失敗 channel={channel_id}: {result.error}")

                posted += 1
                break  # 1キーワードにつき1商品のみ投稿(投稿頻度の抑制)

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
