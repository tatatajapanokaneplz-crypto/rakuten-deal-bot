# rakuten-deal-bot

楽天ウェブサービスAPI × Buffer API による、複合型(タイムセール/クーポン速報 + 人気ランキング紹介)の
X/Threads自動投稿ボット。完全自動化を前提に設計しており、日常運用における手動ステップはない。

## 設計思想

- **完全自動化**: 日次実行後、通常運用では一切の手動操作を必要としない
- **例外ベースの監視**: 「異常を検知して知らせる」のではなく「正常のサインが途絶えたら鳴る」
  デッドマンズスイッチ方式(外部サービス healthchecks.io 等を利用)
- **2トラック分離**: 速報性が命の「タイムセール/クーポン速報」と、品質担保が要る「人気ランキング紹介」を
  別ロジックとして分離し、フィルタが鮮度を殺す矛盾を回避する
- **投稿直前チェック必須**: リンク疎通・型番/価格の事実一致・アフィリエイトIDの検証を、
  投稿前に必ず自動で行う
- **Xの本文にはリンクを直接書かない設計を選択可能**: X APIへの直接連携ではなく、Buffer API経由で
  投稿することで、Xのリンク付き投稿の割増課金(pay-per-use時の$0.20/件)を回避する
- **いいね・返信の自動化はしない**: bot判定リスクを避けるため、エンゲージメントの自動化は行わない

## ディレクトリ構成

```
config/
  filters.yaml        ランキングトラックのフィルタ条件(レビュー数・評価スコア閾値、除外カテゴリ)
src/
  rakuten_client.py    楽天ウェブサービスAPI(商品検索・ランキング取得)のラッパー
  buffer_client.py     Buffer API(投稿作成)のラッパー。X/Threadsそれぞれのチャンネルに対応
  link_checker.py      投稿直前チェック(疎通確認・型番/価格一致・アフィリエイトID検証)
  post_composer.py     投稿文生成。事実部分(固定・機械チェック対象)と表現部分(AI自由生成)を分離
  healthcheck.py       デッドマンズスイッチ(healthchecks.io等)へのping送信
  main_timesale.py     速報トラックのエントリーポイント(GitHub Actionsから高頻度実行)
  main_ranking.py      ランキングトラックのエントリーポイント(低頻度実行)
.github/workflows/
  timesale.yml         速報トラック用ワークフロー
  ranking.yml          ランキングトラック用ワークフロー
```

## セットアップ

### 1. 環境変数の設定

`.env.example` を `.env` にコピーし、各値を埋める。GitHub Actionsで実行する場合は
リポジトリの Settings > Secrets and variables > Actions に同名で登録する。

```bash
cp .env.example .env
```

必要な値:

| 変数名 | 取得元 |
|---|---|
| `RAKUTEN_APP_ID` | 楽天ウェブサービス(https://webservice.rakuten.co.jp/)で開発者登録し発行 |
| `RAKUTEN_AFFILIATE_ID` | 楽天アフィリエイト管理画面 |
| `BUFFER_ACCESS_TOKEN` | Buffer開発者ポータル(developers.buffer.com)でAPIキー発行 |
| `BUFFER_CHANNEL_ID_X` | Bufferで接続したXチャンネルのID |
| `BUFFER_CHANNEL_ID_THREADS` | Bufferで接続したThreadsチャンネルのID |
| `HEALTHCHECK_URL_TIMESALE` | healthchecks.io等で発行する速報トラック用のping URL |
| `HEALTHCHECK_URL_RANKING` | 同上、ランキングトラック用 |

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. ローカルでの動作確認

```bash
python -m src.main_timesale --dry-run
python -m src.main_ranking --dry-run
```

`--dry-run` を付けると、実際の投稿・API課金を行わず、生成される投稿文とチェック結果のみを
標準出力に表示する。初回はまずここで確認すること。

### 4. GitHub Actionsでの自動実行

`.github/workflows/timesale.yml` と `ranking.yml` を確認し、実行頻度(cron)を調整する。
Secretsの登録が完了していれば、あとは push するだけで自動的にスケジュール実行が始まる。

## Buffer APIについて(2026-07 確認済み)

Buffer の公開APIはGraphQLベース(単一エンドポイント `https://api.buffer.com` へのPOST)。
旧REST API(`/2/posts` 等)は新規開発者登録を停止済みのため、Bufferダッシュボードの
Settings > API から発行する**個人APIキー**を使う(Freeプランでも1つ発行可能)。

投稿は `createPost` ミューテーションで、`mode: shareNow` を指定すると即時投稿される
(`addToQueue` は次の空き枠、`customScheduled` は日時指定)。詳細は `src/buffer_client.py`
のdocstringと [Buffer API公式ドキュメント](https://developers.buffer.com/) を参照。

初回セットアップの手順:
1. `BufferClient().get_organization_id()` で組織IDを取得 → `.env` の `BUFFER_ORGANIZATION_ID` に保存
2. `BufferClient().list_channels()` で接続済みチャンネルのIDを確認 → `BUFFER_CHANNEL_ID_X` 等に保存

レート制限(Freeプラン): 24時間100件・30日3,000件。本プロジェクトの投稿量(1日10件程度)なら
十分に余裕がある。

## 未確定・要確認事項

- 楽天アフィリエイトの成果レポートAPI連携は未実装(後付け予定)
- 決済・課金の途絶監視(サーバー代・各種サブスクのカード期限切れ等)は未実装
- ステマ規制上、固定PR表記は常時挿入する設計(post_composer.py 参照)。将来的にプレミアムパートナー
  案件等を扱う場合は、楽天アフィリエイトの最新ガイドラインを再確認すること
