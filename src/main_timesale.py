"""
速報トラック: タイムセール・クーポン速報。

フィルタは適用しない(鮮度優先という前提。README/config/filters.yaml 参照)。
ただし投稿直前チェック(リンク疎通・価格一致・アフィリエイトID確認)は必須。

【2026-07 変更】投稿はスレッド形式(本文+返信)。BUFFER_CHANNEL_ID_X は
twitter、BUFFER_CHANNEL_ID_THREADS は threads として Buffer に渡す
(createPostのmetadataキーがサービスごとに異なるため)。

【2026-07 変更(投稿頻度の調整)】以前はキーワードごとに1件、最大3件を
1回の実行でまとめて投稿していたが、「一気に投稿するのはアルゴリズム的にも
フォロワー的にも良くない」との判断から、1回の実行につき1件のみ投稿する
形に変更した(複数キーワードを順に試すのは、1件目のキーワードで良い候補が
見つからなかった場合のフォールバックとして維持している)。
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from src import healthcheck, link_checker, post_composer
from src.buffer_client import BufferClient
from src.rakuten_client import RakutenClient

# 速報対象として検索するキーワード。1件目のキーワードで投稿できなかった場合の
# フォールバックとして複数用意している(実際に投稿するのは1回の実行につき1件のみ)。
SEARCH_KEYWORDS = ["タイムセール", "クーポン", "お買い物マラソン"]

# env変数名 -> BufferのcreatePost.metadataキー(サービス名)の対応
CHANNEL_SERVICE_MAP = {
    "BUFFER_CHANNEL_ID_X": "twitter",
    "BUFFER_CHANNEL_ID_THREADS": "threads",
}

# 1回の実行で投稿する件数の上限。バースト投稿を避けるため1に固定している。
MAX_POSTS_PER_RUN = 1


def main(dry_run: bool = False) -> int:
    load_dotenv()
    healthcheck_url = os.environ.get("HEALTHCHECK_URL_TIMESALE", "")
    healthcheck.ping_start(healthcheck_url)

    try:
        rakuten = RakutenClient()
        buffer = BufferClient()

        posted = 0
        for keyword in SEARCH_KEYWORDS:
            if posted >= MAX_POSTS_PER_RUN:
                break

            items = rakuten.search_items(keyword=keyword, hits=10)
            for item in items:
                composed = post_composer.compose(item, track="timesale")
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
                break  # このキーワードでの投稿は完了。次のキーワードには進まない

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