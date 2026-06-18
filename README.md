# 福岡イベント自動通知システム Ver.4.11

**公開ポータルURL**: [https://fukuoka-events-calendar.com/portal](https://fukuoka-events-calendar.com/portal)

福岡市内の主要8会場のイベント情報を自動収集し、Slack/LINEで通知するシステム、およびドライバー個人向けの売上・シフト管理システム。

## 📋 概要

```
データ取得 ─────→ 正規化 → JSON保存 → HTML生成 → 通知送信
  │                 ↓        ↓          ↓          ↓
  ├─ CMS API直叩き  parser.py  storage/   GitHub     Slack
  ├─ HTMLスクレイピング          ↓       Pages      LINE
  └─ Yahoo!APIパース          Supabase
```

### 対応会場 & データソース

| # | 会場名 | code | データソース | 取得方式 |
|---|--------|------|-------------|----------|
| 1 | マリンメッセ福岡A館 | `a` | Studio Design CMS API | `requests` JSON |
| 2 | マリンメッセ福岡B館 | `b` | Studio Design CMS API | `requests` JSON |
| 3 | 福岡国際センター | `c` | Studio Design CMS API | `requests` JSON |
| 4 | 福岡国際会議場 | `d` | Studio Design CMS API | `requests` JSON |
| 5 | 福岡サンパレス | `e` | 公式HP（静的HTML） | `requests` + BS4 |
| 6 | PayPayドーム（野球） | `f` | Yahoo!スポーツ | `requests` + BS4 |
| 7 | PayPayドーム（イベント） | `f_event` | 公式HP | `requests` + BS4 |
| 8 | ベスト電器スタジアム | `g` | Yahoo!スポーツ | `requests` + BS4 |

> **Note**: 会場1〜4は2026年3月のNuxt.js(Vue.js)リニューアルにより、
> HTMLスクレイピングからCMS API直叩きに移行。Playwright不要で高速化。

## 🏗️ システム構成

### ディレクトリ構造

```
event_notify/
├── calendar/              # Next.js カレンダーアプリ（Vercel連携用フロントエンド）
│   ├── src/app/           #   ページ・レイアウト群 (page.tsx, layout.tsx, etc.)
│   └── package.json       #   Node.js 依存関係・設定ファイル
├── scrapers/              # データ取得モジュール（8会場分）
│   ├── marinemesse_a.py   #   A館  — CMS API (薄いラッパー)
│   ├── marinemesse_b.py   #   B館  — CMS API
│   ├── kokusai_center.py  #   国際センター — CMS API
│   ├── congress_b.py      #   国際会議場 — CMS API
│   ├── sunpalace.py       #   サンパレス — HTMLパース (ul.schedule_table)
│   ├── paypay_dome.py     #   PayPayドーム(野球)
│   ├── paypay_dome_events.py  # PayPayドーム(イベント)
│   ├── best_denki_stadium.py  # ベスト電器スタジアム
│   └── old/               #   旧スクレイパーのアーカイブ
├── scripts/
│   └── refresh_future_events.py  # Supabase更新オーケストレーター
├── utils/
│   ├── parser.py          # 日付・時刻パーサー (split_and_normalize)
│   └── marinemesse_api.py # マリンメッセ系4会場 CMS API共通モジュール
├── notify/
│   ├── dispatch.py        # 実行ログ監視・Slackへのヘルスチェック通知（スクレイプ件数+DB件数）
│   ├── html_export.py     # HTML生成 (GitHub Pages用)
│   └── old/               # 旧通知システムのアーカイブ
├── storage/               # 出力JSON (YYYY-MM-DD_{code}.json)
├── site/                  # 生成HTML (index.html, manual.html)
├── run/
│   └── dispatch.ps1       # ローカル一括実行 (PowerShell)
└── .env                   # バックエンド用 環境変数設定
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
# スクレイピング + DB保存 + Slack通知（推奨）
python -m scripts.refresh_future_events

# HTML生成のみ
python -m notify.html_export
```

> **Note**: `dispatch.py`の単体実行（`python -m notify.dispatch`）は非対応です。
> Slack通知は `refresh_future_events.py` 経由で自動的に送信されます。

## 🔧 動作の仕組み

### 1. データ取得（会場タイプ別）

#### A) CMS API方式 — マリンメッセ系4会場 (a/b/c/d)

Nuxt.js(Vue.js)リニューアルにより静的HTMLにデータが存在しなくなったため、
バックエンドの **Studio Design CMS API** を直接叩く方式に移行（Ver.3.2）。

```python
# utils/marinemesse_api.py → run_venue_scraper(meta)
1. CMS API にGETリクエスト
   https://api.cms.studiodesignapp.com/v2/search?q={base64_json}
   - project_id: 共通 (4会場同一プロジェクト)
   - filter_id:  会場ごとに異なる (sdl2o80Z, zcqrIhoh, etc.)

2. JSONレスポンスからイベント情報を抽出
   - title:    fields.default.mapValue.fields.title.stringValue
   - datetime: fields.default.mapValue.fields.RIeOyB9L.stringValue

3. 日程文字列の前処理 (preprocess_datetime)
   - <br> → スペース
   - 全角スラッシュ／ → スペース
   - 全角コロン：→ 半角:
   - 丸数字①② / 装飾記号★ を除去
   - 日付時刻結合 "7.4(土)13:00" → "7.4(土) 13:00" に分離

4. parser.py の split_and_normalize() で正規化・展開
   期間表記 "3.25(水)～29(日)" → 5日間に展開
   複数公演 "18:00～ / 12:00～" → 別レコードに分離

5. 重複排除 → SHA-1ハッシュ → JSON保存
```

各スクレイパーは **META辞書のみ** を定義し `run_venue_scraper(META)` を呼ぶ薄いラッパー（約20行）。

#### B) HTMLスクレイピング方式 — サンパレス (e)

```python
# scrapers/sunpalace.py
1. 月別URLで2ページ取得
   https://www.f-sunpalace.com/hall/?ym=YYYY-MM#schedule

2. CSSセレクタでパース
   ul.schedule_table > li
     p.date > span.en  → 日付（数字）
     p.name            → タイトル
     p.starting        → 開演時刻 ("開演HH:MM" を正規表現で抽出)

3. 複数公演展開 → 重複排除 → JSON保存
```

#### C) その他の会場 (f/f_event/g)

PayPayドーム(野球/イベント)、ベスト電器スタジアムは従来方式を継続。

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
# notify/dispatch.py（refresh_future_events.py から呼び出し）
1. スクレイプ件数を会場ごとに集計
2. Supabaseからの実DB件数を取得（ENABLE_DB_SAVE=1の場合）
3. スクレイプ件数とDB件数の差異を検出し⚠️表示
4. Slack Webhook経由で実行ログを送信
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

### マリンメッセ系4会場 (a/b/c/d) のデータが取れない

- **CMS APIの仕様変更**: `api.cms.studiodesignapp.com` のエンドポイント/パラメータが変わった可能性
  - ブラウザDevToolsのNetworkタブで実際のAPIリクエストを確認
  - `utils/marinemesse_api.py` の `PROJECT_ID`, `SCHEMA_KEY`, フィールドキーを更新
- **会場フィルタIDの変更**: `filter_id` が変わった場合は各スクレイパーのMETAを更新

### サンパレス (e) のデータが取れない

- **HTML構造の変更**: `ul.schedule_table > li` のセレクタが変わった可能性
  - ブラウザでページを開き、実際のHTML構造を確認
- **URL形式の変更**: `?ym=YYYY-MM` のパラメータ形式を確認

### ネットワーク/タイムアウトエラー

- タイムアウト設定: 各スクレイパー15秒（`timeout=15`）
- GitHub Actions環境ではDNS解決に時間がかかる場合あり

### データベース接続エラー

```
[Errno 11001] getaddrinfo failed
```

- Supabase URLが存在しない、または削除された
- `.env`の`ENABLE_DB_SAVE=0`でDB保存をスキップ可能（JSON保存は継続）

### Slack通知が届かない

- `SLACK_WEBHOOK_URL`が正しいか確認
- Webhookの有効期限が切れていないか確認

## 📝 開発履歴

| Ver. | 内容 |
|------|------|
| 1.0 | 基本的なスクレイピング機能 |
| 1.8 | 8会場対応、GitHub Actions統合 |
| 2.0 | Supabase統合、2ヶ月分データ取得、年跨ぎ対応 |
| 3.1.2 | GitHub Pagesデプロイ リトライ戦略実装 (最大3回) |
| **3.2** | **マリンメッセ系4会場: Nuxt.jsリニューアル対応 → CMS API直叩きに移行** |
|     | **サンパレス: HP刷新対応 → 新HTML構造 (ul.schedule_table) に対応** |
|     | **共通API処理モジュール `utils/marinemesse_api.py` を新設** |
|     | **旧スクレイパーを `scrapers/old/` にアーカイブ** |
| 3.2.1 | API直叩きに伴う年跨ぎ問題・自動年推定の対応 (期間展開・単日) |
| 3.2.2 | iPhoneキャッシュ問題対応: metaタグ＋JSキャッシュバスター（日付ベース・JST） |
| 3.3 | システム監視強化: dispatch.pyを実行ログSlack送信専用に改修。スクレイパー全滅等の異常検知強化 |
| 3.4 | プロジェクト統合: 独立していたNext.jsカレンダ―のリポジトリを本リポジトリ内の `calendar/` に統合、Vercel連携および Next.js セキュリティアップデート（CVE-2025-66478）対応 |
| 3.4.1 | フロントエンドデザイン統一: GitHub Pages側の出力HTMLをNext.jsカレンダーアプリと同一のデザイン（Tailwind風のCSS）へ改修 |
| **3.4.2** | バグ修正: dispatch.pyダミーデータ送信・2重Slack送信を解消。DB件数送信機能追加（スクレイプ件数との差異検知⚠️対応） |
| **3.4.3** | **セキュリティ強化: カレンダー管理画面のパスワードハードコード廃止（API Route・Vercel環境変数対応）。旧manual.html廃止** |
| 3.4.4 | バグ修正と調査: アビスパ福岡の試合日程未表示の修正（WordPress化に伴うセクション全スキャン対応）と技術スタック調査 |
| **4.0** | **個人管理ツール統合: カレンダーに売上管理（/sales）、シフト入力（/shift）を統合。出勤日（🚕）や目標残高の相互連動表示、一括登録ポップアップ確認フロー、データの保存と注意点ヘルプページ（/help）の実装。** |
| 4.1 | テストリリース: カレンダー詳細および本家ポータルのイベントタイトルをDBのURLに基づいてリンク化（のちにバグ懸念のためロールバック） |
| **4.2** | **バグ修正と詳細URL抽出: 一括登録時のURLマッピング漏れによるURL消失バグを修正。マリンメッセのCMS APIから各イベントの公式個別詳細URLを抽出するようスクレイパーを拡張。イベントタイトルの直接リンク化を再適用** |
| **4.3.2** | **ポータルのNext.js移植とAnalytics導入: 旧ポータル（GitHub Pages）をNext.js上の `/portal` に移植し、旧ポータルからの自動リダイレクトを設定。Vercel Analyticsを導入し、イベントタイトルのリンク色のみを黒（ダークグレー）に微調整。** |
| **4.3.3** | **コンポーネント化リファクタリング: 共通型定義・Supabaseクライアント・定数を `src/types/` `src/lib/` に一元化。`AppFooter` `EventCard` `EventSection` `FeedbackBox` `VenueList` の5コンポーネントを新設し、カレンダー・ポータル間のデザインと文言を統一。ポータルの不要な「最終更新」「データソース」ラベルを削除、日付表示形式をカレンダーに統一。** |
| **4.4** | **アンケートポップアップ実装: Vercel Analytics分析（自作自演発覚・Brave挙動調査・実データ補正）を経て、ユーザー実態把握のためのGoogleフォーム誘導ポップアップをポータルに追加。期限付き表示（SURVEY_END_DATE）・sessionStorage/localStorageによるフラグ管理を実装。** |
| **4.5** | **緊急障害対応: SupabaseのRLS（Row Level Security）誤有効化によるデータ非表示障害を復旧、ポータルに期限付き障害お知らせバナーを直書きで追加。** |
Nuxt.js(Vue.js)リニューアルにより静的HTMLにデータが存在しなくなったため、
バックエンドの **Studio Design CMS API** を直接叩く方式に移行（Ver.3.2）。

```python
# utils/marinemesse_api.py → run_venue_scraper(meta)
1. CMS API にGETリクエスト
   https://api.cms.studiodesignapp.com/v2/search?q={base64_json}
   - project_id: 共通 (4会場同一プロジェクト)
   - filter_id:  会場ごとに異なる (sdl2o80Z, zcqrIhoh, etc.)

2. JSONレスポンスからイベント情報を抽出
   - title:    fields.default.mapValue.fields.title.stringValue
   - datetime: fields.default.mapValue.fields.RIeOyB9L.stringValue

3. 日程文字列の前処理 (preprocess_datetime)
   - <br> → スペース
   - 全角スラッシュ／ → スペース
   - 全角コロン：→ 半角:
   - 丸数字①② / 装飾記号★ を除去
   - 日付時刻結合 "7.4(土)13:00" → "7.4(土) 13:00" に分離

4. parser.py の split_and_normalize() で正規化・展開
   期間表記 "3.25(水)～29(日)" → 5日間に展開
   複数公演 "18:00～ / 12:00～" → 別レコードに分離

5. 重複排除 → SHA-1ハッシュ → JSON保存
```

各スクレイパーは **META辞書のみ** を定義し `run_venue_scraper(META)` を呼ぶ薄いラッパー（約20行）。

#### B) HTMLスクレイピング方式 — サンパレス (e)

```python
# scrapers/sunpalace.py
1. 月別URLで2ページ取得
   https://www.f-sunpalace.com/hall/?ym=YYYY-MM#schedule

2. CSSセレクタでパース
   ul.schedule_table > li
     p.date > span.en  → 日付（数字）
     p.name            → タイトル
     p.starting        → 開演時刻 ("開演HH:MM" を正規表現で抽出)

3. 複数公演展開 → 重複排除 → JSON保存
```

#### C) その他の会場 (f/f_event/g)

PayPayドーム(野球/イベント)、ベスト電器スタジアムは従来方式を継続。

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
# notify/dispatch.py（refresh_future_events.py から呼び出し）
1. スクレイプ件数を会場ごとに集計
2. Supabaseからの実DB件数を取得（ENABLE_DB_SAVE=1の場合）
3. スクレイプ件数とDB件数の差異を検出し⚠️表示
4. Slack Webhook経由で実行ログを送信
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

### マリンメッセ系4会場 (a/b/c/d) のデータが取れない

- **CMS APIの仕様変更**: `api.cms.studiodesignapp.com` のエンドポイント/パラメータが変わった可能性
  - ブラウザDevToolsのNetworkタブで実際のAPIリクエストを確認
  - `utils/marinemesse_api.py` の `PROJECT_ID`, `SCHEMA_KEY`, フィールドキーを更新
- **会場フィルタIDの変更**: `filter_id` が変わった場合は各スクレイパーのMETAを更新

### サンパレス (e) のデータが取れない

- **HTML構造の変更**: `ul.schedule_table > li` のセレクタが変わった可能性
  - ブラウザでページを開き、実際のHTML構造を確認
- **URL形式の変更**: `?ym=YYYY-MM` のパラメータ形式を確認

### ネットワーク/タイムアウトエラー

- タイムアウト設定: 各スクレイパー15秒（`timeout=15`）
- GitHub Actions環境ではDNS解決に時間がかかる場合あり

### データベース接続エラー

```
[Errno 11001] getaddrinfo failed
```

- Supabase URLが存在しない、または削除された
- `.env`の`ENABLE_DB_SAVE=0`でDB保存をスキップ可能（JSON保存は継続）

### Slack通知が届かない

- `SLACK_WEBHOOK_URL`が正しいか確認
- Webhookの有効期限が切れていないか確認

## 📝 開発履歴

| Ver. | 内容 |
|------|------|
| 1.0 | 基本的なスクレイピング機能 |
| 1.8 | 8会場対応、GitHub Actions統合 |
| 2.0 | Supabase統合、2ヶ月分データ取得、年跨ぎ対応 |
| 3.1.2 | GitHub Pagesデプロイ リトライ戦略実装 (最大3回) |
| **3.2** | **マリンメッセ系4会場: Nuxt.jsリニューアル対応 → CMS API直叩きに移行** |
|     | **サンパレス: HP刷新対応 → 新HTML構造 (ul.schedule_table) に対応** |
|     | **共通API処理モジュール `utils/marinemesse_api.py` を新設** |
|     | **旧スクレイパーを `scrapers/old/` にアーカイブ** |
| 3.2.1 | API直叩きに伴う年跨ぎ問題・自動年推定の対応 (期間展開・単日) |
| 3.2.2 | iPhoneキャッシュ問題対応: metaタグ＋JSキャッシュバスター（日付ベース・JST） |
| 3.3 | システム監視強化: dispatch.pyを実行ログSlack送信専用に改修。スクレイパー全滅等の異常検知強化 |
| 3.4 | プロジェクト統合: 独立していたNext.jsカレンダ―のリポジトリを本リポジトリ内の `calendar/` に統合、Vercel連携および Next.js セキュリティアップデート（CVE-2025-66478）対応 |
| 3.4.1 | フロントエンドデザイン統一: GitHub Pages側の出力HTMLをNext.jsカレンダーアプリと同一のデザイン（Tailwind風のCSS）へ改修 |
| **3.4.2** | バグ修正: dispatch.pyダミーデータ送信・2重Slack送信を解消。DB件数送信機能追加（スクレイプ件数との差異検知⚠️対応） |
| **3.4.3** | **セキュリティ強化: カレンダー管理画面のパスワードハードコード廃止（API Route・Vercel環境変数対応）。旧manual.html廃止** |
| 3.4.4 | バグ修正と調査: アビスパ福岡の試合日程未表示の修正（WordPress化に伴うセクション全スキャン対応）と技術スタック調査 |
| **4.0** | **個人管理ツール統合: カレンダーに売上管理（/sales）、シフト入力（/shift）を統合。出勤日（🚕）や目標残高の相互連動表示、一括登録ポップアップ確認フロー、データの保存と注意点ヘルプページ（/help）の実装。** |
| 4.1 | テストリリース: カレンダー詳細および本家ポータルのイベントタイトルをDBのURLに基づいてリンク化（のちにバグ懸念のためロールバック） |
| **4.2** | **バグ修正と詳細URL抽出: 一括登録時のURLマッピング漏れによるURL消失バグを修正。マリンメッセのCMS APIから各イベントの公式個別詳細URLを抽出するようスクレイパーを拡張。イベントタイトルの直接リンク化を再適用** |
| **4.3.2** | **ポータルのNext.js移植とAnalytics導入: 旧ポータル（GitHub Pages）をNext.js上の `/portal` に移植し、旧ポータルからの自動リダイレクトを設定。Vercel Analyticsを導入し、イベントタイトルのリンク色のみを黒（ダークグレー）に微調整。** |
| **4.3.3** | **コンポーネント化リファクタリング: 共通型定義・Supabaseクライアント・定数を `src/types/` `src/lib/` に一元化。`AppFooter` `EventCard` `EventSection` `FeedbackBox` `VenueList` の5コンポーネントを新設し、カレンダー・ポータル間のデザインと文言を統一。ポータルの不要な「最終更新」「データソース」ラベルを削除、日付表示形式をカレンダーに統一。** |
| **4.4** | **アンケートポップアップ実装: Vercel Analytics分析（自作自演発覚・Brave挙動調査・実データ補正）を経て、ユーザー実態把握のためのGoogleフォーム誘導ポップアップをポータルに追加。期限付き表示（SURVEY_END_DATE）・sessionStorage/localStorageによるフラグ管理を実装。** |
| **4.5** | **緊急障害対応: SupabaseのRLS（Row Level Security）誤有効化によるデータ非表示障害を復旧、ポータルに期限付き障害お知らせバナーを直書きで追加。** |
| **4.5.1** | **お知らせ機能の動的管理化: Supabaseに `notices` テーブルを新設し、管理者用お知らせ管理画面（/admin/messages）を作成。お知らせの作成・削除・有効化/無効化の切り替えをコード変更なしで行えるように改修。ポータルのバナーをDB動的取得に変更。** |
| **4.6** | **アンケート機能の終了とクリーンアップ、使い方ガイド動画のデプロイ: YouTube（限定公開）を用いたアスペクト比固定の埋め込み再生を実装。不要になった `SurveyPopup` 等を一括削除。** |
| **4.7** | **AdSense申請の準備と必須ページの設置: Cookieやアクセス解析に関する免責等を明記した「プライバシーポリシー」とお問い合わせGoogleフォームへの導線を新設。GitHub Pagesからのリダイレクト先を独自ドメイン（fukuoka-events-calendar.com）に変更。** |
| **4.8** | **PWA対応とオリジナルアプリアイコンの実装: スマホのホーム画面に追加できるPWA環境の構築（`/help/install` ページの新設）。ヨッシー社長の愛車ナンバー「福岡 42-23」の黄色コンフォートタクシーとお祭りカレンダーをあしらったプレミアムアプリアイコンを適用。iOSダークモード時の文字白飛びバグ解消。** |
| 4.9 | microCMSブログ連携（note風日記）の実装とバグ回収: microCMS SDKを導入し、ISR（60秒キャッシュ）および静的パス事前生成に対応した「運営ドライバーのぼちぼち日記」一覧・詳細画面を新規追加。Androidマニフェストアイコンのパースバグ、Tailwind v4非標準カラーの指定エラー、インストール案内ページの表示崩れ（マークダウン漏れ）を修正。 |
| **4.10** | **スクレイパー異常検知＆LINE緊急サイレン通知システムの実装とローカルデバッグスクリプト最新化**: LINE Notify廃止に伴う、LINE公式アカウントの「Messaging API」を利用したプッシュ通知システムを導入。例外クラッシュ時や重要5会場（マリンメッセA/B、国際センター、国際会議場、福岡サンパレス）のデータ「0件取得」警告を自動検知し、LINEへ緊急サイレンとしてプッシュ通知するロジックを実装。Windows環境下での絵文字出力時における `UnicodeEncodeError (cp932)` を回避。ローカル一括デバッグスクリプト `run/dispatch.ps1` をVer.4.10仕様（無駄な個別通知呼び出しの削除、全3ステップ化）にアップデート。 |
| **4.11** | **事業者様向け案内ページおよびA4チラシPDF直接ダウンロード機能の実装**: 他社の運行管理者やドライバーが本システムを発見した際、営業所の点呼場などに掲示して社内全体で使ってもらえるようにするための「事業者様向け案内ページ（`/business`）」および「A4印刷用チラシ（`/portal/flyer`）」を新規実装。現場のアナログ層を考慮し、ブラウザの印刷設定を使わせる複雑な動線を廃止、事前にPlaywright（ヘッドレスブラウザ）で生成した高品質なPDF（`fukuoka_event_guide.pdf`）をパブリックアセットとして同梱し、ワンクリックで直接ダウンロードできる親切設計に。正式な公開ドメイン（`fukuoka-events-calendar.com`）に合わせたQRコードやリダイレクトURLの最新化も実施。再現性確保のための特別仕様書（PDF作成マニュアル）を整備。 |

## 📄 ライセンス

このプロジェクトは個人利用目的で作成されています。

## 👤 作成者

YOSHITATSU NAKAHARA (ヨッシー) + Antigravity (Gemini 3.5 Flash / Claude 4.6 Sonnet)

---

**最終更新**: 2026年6月19日 JST
