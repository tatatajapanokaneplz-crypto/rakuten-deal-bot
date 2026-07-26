"""
楽天ウェブサービスAPI(https://webservice.rakuten.co.jp/)のラッパー。

【2026-07 確認済み・重要】2026年5月14日に旧エンドポイント(app.rakuten.co.jp)は
完全停止し、新エンドポイント(openapi.rakuten.co.jp)に移行済み。
新APIでは以下がすべて必須:
- applicationId(クエリパラメータ、従来通り)
- accessKey(ヘッダーまたはクエリパラメータ。新APIからの追加要件)
- Origin / Referer ヘッダー(値は「許可Webサイト(Allowed websites)」に登録した
  文字列と完全一致させること。実在するサイトである必要はなく、登録時と送信時で
  一致してさえいればよい。本プロジェクトでは RAKUTEN_ALLOWED_SITE で管理する)

【重要】RankingとSearchでベースパスが異なる。
- Ranking: https://openapi.rakuten.co.jp/ichibaranking/api/...
- Search : https://openapi.rakuten.co.jp/ichibams/api/...
同一のRAKUTEN_API_BASEでまとめると404になるため、別々の定数として持つ。

【2026-07 修正】楽天APIはitemPriceを文字列で返すケースがあるため、
post_composer側でのフォーマット(カンマ区切り)エラーを防ぐためint変換を明示する。

主に以下の2つのAPIを利用する:
- IchibaItem/Ranking: ジャンル別の売れ筋ランキング取得
- IchibaItem/Search: キーワード・ジャンル指定での商品検索(タイムセール・クーポン対象商品の取得)

いずれも楽天アフィリエイトIDをパラメータに含めることで、取得した商品URLに
自動的にアフィリエイトリンクを埋め込める(公式の仕組みであり、スクレイピングではない)。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

RAKUTEN_RANKING_ENDPOINT = "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
RAKUTEN_SEARCH_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"


@dataclass
class RakutenItem:
    """楽天商品の構造化データ。post_composer側で「事実部分」として使う。"""

    item_name: str
    item_code: str          # 型番相当。同一商品かどうかの照合に使う
    item_price: int
    item_url: str           # アフィリエイトID込みのURL
    shop_name: str
    review_average: float
    review_count: int
    genre_id: Optional[str] = None


class RakutenClient:
    def __init__(
        self,
        app_id: Optional[str] = None,
        access_key: Optional[str] = None,
        affiliate_id: Optional[str] = None,
        allowed_site: Optional[str] = None,
    ):
        self.app_id = app_id or os.environ["RAKUTEN_APP_ID"]
        self.access_key = access_key or os.environ["RAKUTEN_ACCESS_KEY"]
        self.affiliate_id = affiliate_id or os.environ.get("RAKUTEN_AFFILIATE_ID", "")
        # Rakuten Developersの「許可Webサイト(Allowed websites)」に登録した値と
        # 完全一致させる必要がある。実在URLでなくてよい(識別子として使うだけ)。
        self.allowed_site = allowed_site or os.environ.get(
            "RAKUTEN_ALLOWED_SITE", "https://rakuten-granpa.example"
        )
        self._session = requests.Session()
        self._session.headers.update(
            {
                "accessKey": self.access_key,
                "Origin": self.allowed_site,
                "Referer": self.allowed_site,
                "User-Agent": "rakuten-deal-bot/1.0",
            }
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get(self, endpoint: str, params: dict) -> dict:
        params = {
            **params,
            "applicationId": self.app_id,
            "affiliateId": self.affiliate_id,
            "format": "json",
        }
        resp = self._session.get(endpoint, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_ranking(self, genre_id: str = "0", page: int = 1) -> list[RakutenItem]:
        """指定ジャンルの売れ筋ランキングを取得する。genre_id='0'は総合ランキング。"""
        data = self._get(RAKUTEN_RANKING_ENDPOINT, {"genreId": genre_id, "page": page})
        return [self._parse_item(entry["Item"]) for entry in data.get("Items", [])]

    def search_items(self, keyword: str, genre_id: Optional[str] = None, hits: int = 30) -> list[RakutenItem]:
        """キーワード・ジャンル指定で商品検索。タイムセール・クーポン対象商品の取得に使う。"""
        params = {"keyword": keyword, "hits": hits}
        if genre_id:
            params["genreId"] = genre_id
        data = self._get(RAKUTEN_SEARCH_ENDPOINT, params)
        return [self._parse_item(entry["Item"]) for entry in data.get("Items", [])]

    @staticmethod
    def _parse_item(item: dict) -> RakutenItem:
        return RakutenItem(
            item_name=item["itemName"],
            item_code=item["itemCode"],
            item_price=int(item["itemPrice"]),
            item_url=item["affiliateUrl"] or item["itemUrl"],
            shop_name=item["shopName"],
            review_average=float(item.get("reviewAverage", 0) or 0),
            review_count=int(item.get("reviewCount", 0) or 0),
            genre_id=str(item.get("genreId", "")) or None,
        )