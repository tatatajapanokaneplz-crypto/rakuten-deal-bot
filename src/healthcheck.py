"""
デッドマンズスイッチ連携。

設計思想: 「異常を検知して知らせる」のではなく「正常のサインが途絶えたら鳴る」。
これにより、監視ロジック自身がバグって動かなくなった場合でも(自分のコードとは
完全に独立した外部サービス側が「pingが来ない」ことを検知するため)気づける。

healthchecks.io、Cronitor、UptimeRobot等、無料枠のある外部サービスを利用する想定。
ジョブの「開始」と「成功」でそれぞれ別のシグナルを送ることで、
「実行され始めたが完了しなかった(=途中で落ちた)」ケースも判別できるようにする。
"""

from __future__ import annotations

import requests


def ping_start(healthcheck_url: str) -> None:
    if not healthcheck_url:
        return
    try:
        requests.get(f"{healthcheck_url}/start", timeout=10)
    except requests.RequestException:
        # ping送信自体の失敗で本処理を止めない。ping途絶はサービス側のタイムアウトで検知される。
        pass


def ping_success(healthcheck_url: str) -> None:
    if not healthcheck_url:
        return
    try:
        requests.get(healthcheck_url, timeout=10)
    except requests.RequestException:
        pass


def ping_failure(healthcheck_url: str, message: str = "") -> None:
    if not healthcheck_url:
        return
    try:
        requests.post(f"{healthcheck_url}/fail", data=message.encode("utf-8"), timeout=10)
    except requests.RequestException:
        pass
