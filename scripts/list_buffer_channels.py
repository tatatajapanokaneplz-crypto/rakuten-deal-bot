#!/usr/bin/env python3
"""
Buffer organization配下の全チャンネル(接続済みSNSアカウント)を一覧表示するスクリプト。
"""

import json
import os
import sys
import urllib.request
import urllib.error

BUFFER_API_ENDPOINT = "https://api.buffer.com"

QUERY = """
query GetChannels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) {
    id
    name
    displayName
    service
    isQueuePaused
  }
}
"""


def fetch_channels(access_token: str, organization_id: str) -> list:
    payload = json.dumps(
        {
            "query": QUERY,
            "variables": {"organizationId": organization_id},
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        BUFFER_API_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTPエラー: {e.code} {e.reason}", file=sys.stderr)
        print(e.read().decode("utf-8"), file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"接続エラー: {e.reason}", file=sys.stderr)
        sys.exit(1)

    if "errors" in body:
        print("GraphQLエラー:", json.dumps(body["errors"], ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    return body.get("data", {}).get("channels", [])


def main() -> None:
    access_token = os.environ.get("BUFFER_ACCESS_TOKEN")
    organization_id = os.environ.get("BUFFER_ORGANIZATION_ID")

    if not access_token:
        print("環境変数 BUFFER_ACCESS_TOKEN が設定されていません。", file=sys.stderr)
        sys.exit(1)
    if not organization_id:
        print("環境変数 BUFFER_ORGANIZATION_ID が設定されていません。", file=sys.stderr)
        sys.exit(1)

    channels = fetch_channels(access_token, organization_id)

    if not channels:
        print("チャンネルが見つかりませんでした。組織IDやAPIキーの権限を確認してください。")
        return

    print(f"取得したチャンネル数: {len(channels)}")
    print("-" * 60)
    for ch in channels:
        service = ch.get("service", "unknown")
        name = ch.get("name", "")
        display_name = ch.get("displayName", "")
        channel_id = ch.get("id", "")
        paused = ch.get("isQueuePaused", False)
        print(f"service      : {service}")
        print(f"displayName  : {display_name}")
        print(f"name         : {name}")
        print(f"id           : {channel_id}")
        print(f"queue paused : {paused}")
        print("-" * 60)

    print(
        "\n上記の一覧から、serviceがX/twitter系のものと threads のものを探し、"
        "それぞれの id を BUFFER_CHANNEL_ID_X / BUFFER_CHANNEL_ID_THREADS として"
        "GitHub Secretsに登録してください。"
    )


if __name__ == "__main__":
    main()