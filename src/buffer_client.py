"""
Buffer API(https://developers.buffer.com/)のラッパー。

【2026-07 確認済み】Buffer の公開APIはGraphQLベースの単一エンドポイント
(https://api.buffer.com への POST)。旧REST(/2/posts 等)は新規開発者登録を
停止しており、個人APIキー(Personal API Key)方式でのGraphQL利用が現実的な唯一の経路。
本ファイルは developers.buffer.com の公式ガイド・サンプルに基づく実装。

認証: Authorization: Bearer <個人APIキー>(publish.buffer.com/settings/api で発行)
投稿作成: createPost ミューテーション。channelId + schedulingType: automatic +
          mode で即時/キュー追加/予約を指定する。
          - mode: shareNow        → 即時投稿(このプロジェクトで使用)
          - mode: addToQueue      → 次の空き時間枠に追加
          - mode: shareNext       → キューの次の枠に追加
          - mode: customScheduled → dueAt で指定した日時に投稿
レスポンス: createPost の戻り値はユニオン型(PostActionSuccess | MutationError)。
          GraphQL特有の top-level "errors" 配列と、この MutationError の両方を
          確認する必要がある(片方だけだとエラーを見逃す)。

チャンネル一覧取得(channels query)には organizationId が必須。
組織IDは account { organizations { id } } で事前に取得しておくこと
(初回セットアップ時に1回確認すれば、以降は .env に固定値として保存してよい)。

レート制限(Freeプラン, 2026-07時点): 15分100件 / 24時間100件 / 30日3,000件。
本プロジェクトの想定投稿量(1日10件程度)なら十分に余裕がある。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

BUFFER_API_ENDPOINT = "https://api.buffer.com"


@dataclass
class PostResult:
    success: bool
    channel_id: str
    post_id: Optional[str] = None
    error: Optional[str] = None


class BufferClient:
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.environ["BUFFER_ACCESS_TOKEN"]
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _graphql(self, query: str) -> dict:
        resp = self._session.post(BUFFER_API_ENDPOINT, json={"query": query}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def create_post(self, channel_id: str, text: str, dry_run: bool = False) -> PostResult:
        """
        指定チャンネルに即時投稿(mode: shareNow)を作成する。

        dry_run=True の場合、実際のAPI呼び出しは行わず、内容を検証するだけに留める。
        まず --dry-run で投稿内容を目視確認してから実運用に移すこと。
        """
        if dry_run:
            print(f"[DRY RUN] channel={channel_id}\n--- 投稿内容 ---\n{text}\n----------------")
            return PostResult(success=True, channel_id=channel_id, post_id="dry-run")

        escaped_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        query = f"""
        mutation CreatePost {{
          createPost(input: {{
            text: "{escaped_text}",
            channelId: "{channel_id}",
            schedulingType: automatic,
            mode: shareNow
          }}) {{
            ... on PostActionSuccess {{
              post {{
                id
                text
              }}
            }}
            ... on MutationError {{
              message
            }}
          }}
        }}
        """

        try:
            data = self._graphql(query)
        except requests.RequestException as exc:
            return PostResult(success=False, channel_id=channel_id, error=str(exc))

        # GraphQL特有のトップレベルエラー(認証エラー・レート制限等)
        if data.get("errors"):
            return PostResult(success=False, channel_id=channel_id, error=str(data["errors"]))

        result = data.get("data", {}).get("createPost", {})

        # MutationError(投稿自体は受け付けたがビジネスロジック上のエラー)
        if "message" in result:
            return PostResult(success=False, channel_id=channel_id, error=result["message"])

        post = result.get("post", {})
        return PostResult(success=True, channel_id=channel_id, post_id=post.get("id"))

    def get_organization_id(self) -> Optional[str]:
        """
        最初の組織IDを取得する。個人利用(単一組織)を想定した簡易実装。
        初回セットアップ時にこれを一度呼び出し、結果を .env に
        BUFFER_ORGANIZATION_ID として固定保存しておくことを推奨
        (毎回問い合わせる必要はない)。
        """
        query = """
        query GetOrganizations {
          account {
            organizations {
              id
            }
          }
        }
        """
        data = self._graphql(query)
        orgs = data.get("data", {}).get("account", {}).get("organizations", [])
        return orgs[0]["id"] if orgs else None

    def list_channels(self, organization_id: Optional[str] = None) -> list[dict]:
        """
        接続済みチャンネル一覧を取得。BUFFER_CHANNEL_ID_X等を確認する際に使う。
        organization_id を省略した場合、get_organization_id() で自動取得する。
        """
        org_id = organization_id or self.get_organization_id()
        if not org_id:
            return []

        query = f"""
        query GetChannels {{
          channels(input: {{
            organizationId: "{org_id}"
          }}) {{
            id
            name
            displayName
            service
            isQueuePaused
          }}
        }}
        """
        data = self._graphql(query)
        return data.get("data", {}).get("channels", [])
