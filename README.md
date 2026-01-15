# 福岡イベント自動通知システム

福岡市内の主要会場のイベント情報を自動収集し、Slack/LINEで通知するシステムです。

## 📋 概要

このシステムは以下の流れで動作します：

```
スクレイピング → データ保存 → HTML生成 → 通知送信
     ↓              ↓           ↓          ↓
  8つの会場      JSON + DB   GitHub Pages  Slack/LINE
```

### 対応会場

| # | 会場名 | コード | 取得期間 |
|---|--------|--------|----------|
| 1 | マリンメッセ福岡A館 | `a` | 当月1日〜翌月末日 |
| 2 | マリンメッセ福岡B館 | `b` | 当月1日〜翌月末日 |
| 3 | 福岡国際センター | `c` | 当月1日〜翌月末日 |
| 4 | 福岡国際会議場 | `d` | 当月1日〜翌月末日 |
| 5 | 福岡サンパレス | `e` | 当月1日〜翌月末日 |
| 6 | PayPayドーム（野球） | `f` | 8週間分 |
| 7 | PayPayドーム（イベント） | `f_event` | 当月1日〜翌月末日 |
| 8 | ベスト電器スタジアム | `g` | 当月1日〜翌月末日 |

## 🏗️ システム構成

### ディレクトリ構造

```
event_notify/
├── scrapers/          # スクレイパー（8会場分）
│   ├── marinemesse_a.py
│   ├── marinemesse_b.py
│   ├── kokusai_center.py
│   ├── congress_b.py
│   ├── sunpalace.py
│   ├── paypay_dome.py
│   ├── paypay_dome_events.py
│   └── best_denki_stadium.py
├── scripts/           # 実行スクリプト
│   └── refresh_future_events.py  # メイン実行スクリプト
├── utils/             # 共通ユーティリティ
│   └── parser.py      # 日付・時刻パース処理
├── notify/            # 通知・HTML生成
│   ├── dispatch.py    # Slack/LINE通知
│   └── html_export.py # HTML生成
├── storage/           # スクレイピング結果（JSON）
│   ├── YYYY-MM-DD_a.json
│   ├── YYYY-MM-DD_b.json
│   └── ...
├── site/              # 生成されたHTML（GitHub Pages用）
│   ├── index.html
│   └── manual.html
├── run/               # ローカル実行用スクリプト
│   └── dispatch.ps1   # PowerShell一括実行スクリプト
└── .env               # 環境変数設定（要作成）
```

## 🚀 セットアップ

### 1. 必要な環境

- **Python 3.11+**
- **PowerShell**（Windowsの場合）
- **インターネット接続**

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

主な依存パッケージ：
- `requests` - HTTP通信
- `beautifulsoup4` - HTMLパース
- `supabase` - データベース（オプション）
- `python-dotenv` - 環境変数管理
- `python-dateutil` - 日付処理

### 3. 環境変数の設定

`.env`ファイルをプロジェクトルートに作成：



## 💻 ローカル実行

### Windows (PowerShell)

```powershell
# プロジェクトルートに移動
cd c:\path\to\event_notify

# 一括実行スクリプトを実行
.\run\dispatch.ps1
```

実行内容：
1. **データリフレッシュ** - 全8会場のスクレイピング実行
2. **JSON保存** - `storage/`フォルダに保存
3. **DB保存** - Supabase（`ENABLE_DB_SAVE=1`の場合）
4. **HTML生成** - `site/index.html`と`site/manual.html`を生成
5. **Slack通知** - 完了通知を送信

### Python直接実行

```bash
# スクレイピング + DB保存のみ
python -m scripts.refresh_future_events

# HTML生成のみ
python -m notify.html_export

# Slack通知のみ
python -m notify.dispatch
```

## 🔧 動作の仕組み

### 1. スクレイピング処理

各スクレイパーは以下の処理を実行：

```python
# 例: marinemesse_a.py
1. 当月と翌月のURLを生成
   https://www.marinemesse.or.jp/messe/event/?yy=2026&mm=1
   https://www.marinemesse.or.jp/messe/event/?yy=2026&mm=2

2. HTMLを取得してパース（BeautifulSoup）

3. イベント情報を抽出
   - 日付（date）
   - 時刻（time）
   - タイトル（title）
   - 会場（venue）

4. 正規化処理（utils/parser.py）
   - 日付フォーマット統一（YYYY-MM-DD）
   - 時刻フォーマット統一（HH:MM）
   - 全角/半角の統一

5. 重複排除（data_hashで判定）

6. JSONファイルに保存
   storage/2026-01-16_a.json
```

### 2. データベース保存

`ENABLE_DB_SAVE=1`の場合、Supabaseに保存：

```python
# refresh_future_events.py
1. 全スクレイパーからJSONを収集
2. Supabaseトランザクション実行
   - 未来のautoイベントを削除
   - 新しいイベントを挿入
3. 手動イベント（manual）は保護
```

### 3. HTML生成

```python
# notify/html_export.py
1. Supabase（またはJSON）からイベント取得
2. 日付順にソート
3. HTMLテンプレートに埋め込み
4. site/index.html と site/manual.html を生成
```

### 4. 通知送信

```python
# notify/dispatch.py
1. 今週のイベント情報を集計
2. Slack Webhook経由で通知
3. LINE通知（設定されている場合）
```

## 🤖 GitHub Actions自動実行

`.github/workflows/main.yml`で定義：

- **実行タイミング**: 毎日JST 00:37（UTC 15:37）
- **処理内容**:
  1. スクレイピング実行
  2. DB更新
  3. HTML生成
  4. GitHub Pagesデプロイ
  5. Slack通知
  6. スクリーンショット保存

## 📊 データ形式

### JSONフォーマット（storage/）

```json
[
  {
    "schema_version": "1.0",
    "date": "2026-01-25",
    "time": "18:00",
    "title": "福岡コンサート2026",
    "venue": "マリンメッセA館",
    "source": "https://www.marinemesse.or.jp/messe/event/",
    "hash": "abc123...",
    "extracted_at": "2026-01-16T07:00:00+09:00"
  }
]
```

### データベーススキーマ（Supabase）

```sql
CREATE TABLE events (
  id SERIAL PRIMARY KEY,
  date DATE NOT NULL,
  time TIME,
  title VARCHAR(255) NOT NULL,
  venue VARCHAR(100) NOT NULL,
  source_url TEXT,
  data_hash VARCHAR(40) UNIQUE,
  event_type VARCHAR(20) DEFAULT 'auto',
  extracted_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW(),
  notes TEXT
);
```

## 🔍 トラブルシューティング

### スクレイピングが失敗する

- **会場サイトのHTML構造が変更された可能性**
  - 該当スクレイパーのセレクタを更新する必要あり
  
- **ネットワークエラー**
  - タイムアウト設定を確認（通常15秒）

### データベース接続エラー

```
[Errno 11001] getaddrinfo failed
```

- Supabase URLが存在しない、または削除された
- `.env`ファイルの`ENABLE_DB_SAVE=0`で無効化可能

### Slack通知が届かない

- `SLACK_WEBHOOK_URL`が正しいか確認
- Webhookの有効期限が切れていないか確認

## 📝 開発履歴

- **Ver.1.0** - 基本的なスクレイピング機能
- **Ver.1.8** - 8会場対応、GitHub Actions統合
- **Ver.2.0** - Supabase統合、2ヶ月分データ取得、年跨ぎ対応
- **Ver.3.1.2** - リトライ戦略実装（GitHub Pages）

## 📄 ライセンス

このプロジェクトは個人利用目的で作成されています。

## 👤 作成者

ヨッシー + Claude

---

**最終更新**: 2026年1月16日
