# utils/marinemesse_api.py
"""
マリンメッセ系4会場 (A/B/C/D) — Studio Design CMS API 共通モジュール

旧サイトは table + BeautifulSoup でパースしていたが、
Nuxt.js (Vue.js) リニューアルにより静的HTMLにデータが存在しなくなった。
ブラウザDevToolsで発見した Studio Design CMS の公開APIを直接叩く方式に切り替え。
"""
import os
import re
import json
import time
import base64
import hashlib
import unicodedata
import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Optional
from pathlib import Path

from utils.parser import split_and_normalize, JST

# Supabase投入用（オプション）
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# ============================================================
# API設定（4会場共通）
# ============================================================
API_URL = "https://api.cms.studiodesignapp.com/v2/search"
PROJECT_ID = "gjliOqGf6PL86iEKnjya"
SCHEMA_KEY = "rMR9xdMj"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://www.marinemesse.or.jp",
    "Referer": "https://www.marinemesse.or.jp/",
}

# Studio Design CMS のフィールドキー
FIELD_DATETIME = "RIeOyB9L"
FIELD_ORGANIZER = "Q2l5jeWo"
FIELD_DETAIL_URL = "TyvtSOey"


# ============================================================
# ユーティリティ
# ============================================================
def _storage_path(date_str: str, code: str) -> Path:
    """共通のストレージパス生成（他のスクレイパーと統一）"""
    root = Path(__file__).resolve().parents[1]
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _normalize_for_hash(s: str) -> str:
    """ハッシュ用の軽量正規化"""
    if s is None:
        return ""
    x = unicodedata.normalize("NFKC", s)
    x = x.replace("\u201c", '"').replace("\u201d", '"').replace("\u201f", '"')
    x = x.replace("\u301d", '"').replace("\u301e", '"')
    x = x.replace("\u2018", "'").replace("\u2019", "'").replace("\uff07", "'")
    x = re.sub(r"\s+", " ", x).strip()
    return x


def _resolve_target_date() -> str:
    """SCRAPER_TARGET_DATE=YYYY-MM-DD があればそれを優先。なければJSTの今日。"""
    override = os.getenv("SCRAPER_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")


def _get_target_date_range() -> tuple[str, str]:
    """当月1日～翌月末日の期間を取得"""
    today = datetime.now(JST)
    start_date = today.replace(day=1)
    next_month_first = start_date + relativedelta(months=1)
    end_date = next_month_first + relativedelta(months=1) - timedelta(days=1)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def _filter_date_range(items: List[Dict], start_date: str, end_date: str) -> List[Dict]:
    """指定期間内のイベントのみ抽出"""
    return [e for e in items if start_date <= e.get("date", "") <= end_date]


# ============================================================
# API呼び出し
# ============================================================
def _build_query(venue_filter_id: str, offset: int = 0, limit: int = 100) -> str:
    """Base64エンコードされたAPIクエリを生成"""
    query = {
        "project_id": PROJECT_ID,
        "schema_key": SCHEMA_KEY,
        "filters": f"zu0OnEpi:ref[equals]{venue_filter_id}",
        "orders": "order",
        "offset": offset,
        "limit": limit,
    }
    return base64.b64encode(json.dumps(query).encode()).decode()


def _extract_string(fields: dict, key: str) -> str:
    """fields辞書から stringValue を安全に抽出"""
    field = fields.get(key, {})
    if isinstance(field, dict):
        return field.get("stringValue", "")
    return ""


def fetch_raw_events(venue_filter_id: str, name: str) -> List[Dict]:
    """
    Studio Design CMS API からイベント生データを取得。
    ページネーション対応（100件超にも対応）。
    """
    all_items = []
    offset = 0
    limit = 100

    while True:
        q = _build_query(venue_filter_id, offset, limit)
        url = f"{API_URL}?q={q}"

        print(f"[{name}] API request: offset={offset} limit={limit}")
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()

        if not data:
            break

        for item in data:
            doc = item.get("document", {})
            fields = (
                doc.get("fields", {})
                .get("default", {})
                .get("mapValue", {})
                .get("fields", {})
            )

            title = _extract_string(fields, "title").strip()
            datetime_raw = _extract_string(fields, FIELD_DATETIME)

            if not title:
                continue

            detail_url = _extract_string(fields, FIELD_DETAIL_URL).strip()

            all_items.append({
                "title": title,
                "datetime_raw": datetime_raw,
                "detail_url": detail_url,
            })

        if len(data) < limit:
            break
        offset += limit

    print(f"[{name}] API returned {len(all_items)} events")
    return all_items


# ============================================================
# 日程文字列の前処理（parser.py に渡す前の変換）
# ============================================================
def preprocess_datetime(raw: str) -> str:
    """
    API日程文字列を parser.py が処理できる形式に前処理。

    入力例:
      "3.25(水)～29(日)<br>10:00～17:00"
      "4.5(日) ①18:00～<br>4.6(月) ①12:00～／②17:00～"
      "4.4(土) 17：00～"

    出力例:
      "3.25(水)～29(日) 10:00～17:00"
      "4.5(日) 18:00～ 4.6(月) 12:00～ 17:00～"
      "4.4(土) 17:00～"
    """
    if not raw:
        return ""

    text = raw

    # <br> → スペース
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)

    # 全角スラッシュ → スペース（半角 / は日付内 4/1 で使われるので残す）
    text = text.replace('／', ' ')

    # 全角コロン → 半角コロン（時刻 17：00 → 17:00）
    text = text.replace('：', ':')

    # 丸数字を除去 ①②③...
    text = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]', '', text)

    # 装飾記号を除去
    text = re.sub(r'[★☆●○◆◇■□▲△▼▽]', '', text)

    # ※注記を除去（※以降の文字列を丸ごと削除）
    text = re.sub(r'※.*', '', text)

    # 日付と時刻の結合を分離: "7.4(土)13:00" → "7.4(土) 13:00"
    text = re.sub(r'(\))(\d)', r'\1 \2', text)

    # 全角波ダッシュ等の統一
    text = text.replace('〜', '～').replace('－', '-').replace('—', '–')

    # 空白正規化（全角スペース含む）
    text = re.sub(r'\s+', ' ', text).strip()

    return text


# ============================================================
# Supabase保存
# ============================================================
def _get_supabase_client() -> "Client":
    if not SUPABASE_AVAILABLE:
        raise RuntimeError("Supabase依存関係が不足: pip install supabase python-dotenv")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("環境変数 SUPABASE_URL, SUPABASE_KEY が設定されていません")
    return create_client(url, key)


def _save_to_supabase(events: List[Dict], name: str) -> None:
    """イベントデータをSupabaseに保存"""
    if not events:
        print(f"[{name}] DB投入: データなし")
        return
    try:
        supabase = _get_supabase_client()
        db_records = []
        for event in events:
            record = {
                "date": event.get("date"),
                "time": event.get("time"),
                "title": event.get("title", ""),
                "venue": event.get("venue", ""),
                "source_url": event.get("source", ""),
                "data_hash": event.get("hash", ""),
                "event_type": "auto",
                "notes": event.get("notes"),
            }
            db_records.append(record)
        result = supabase.table('events').upsert(
            db_records, on_conflict="data_hash"
        ).execute()
        print(f"[{name}] DB投入成功: {len(result.data)}件")
    except Exception as e:
        print(f"[{name}][ERROR] DB投入失敗: {e}")


# ============================================================
# メインパイプライン（各スクレイパーから呼ばれる）
# ============================================================
def run_venue_scraper(meta: Dict) -> None:
    """
    1つの会場の完全なスクレイピングパイプラインを実行。

    meta = {
        "name": "marinemesse_a",
        "venue": "マリンメッセA館",
        "code": "a",
        "filter_id": "sdl2o80Z",
        "source_url": "https://www.marinemesse.or.jp/messe/event/",
        "schema_version": "1.0",
    }
    """
    t0 = time.time()
    name = meta["name"]
    venue = meta["venue"]
    code = meta["code"]
    source_url = meta["source_url"]
    schema_version = meta["schema_version"]

    target_date = _resolve_target_date()
    print(f"[{name}] target_date={target_date}")

    # 1) API からイベント取得
    raw_events = fetch_raw_events(meta["filter_id"], name)

    # 2) 日程文字列を前処理 → parser.py で正規化・展開
    #    year=None で呼ぶことで自動年推定モード（年跨ぎ補正あり）を有効化
    normalized: List[Dict] = []
    for ev in raw_events:
        dt_text = preprocess_datetime(ev["datetime_raw"])
        if not dt_text:
            # 日程なし → 日付不明イベント（スキップ）
            print(f"[{name}] Skipping (no date): {ev['title'][:40]}")
            continue

        try:
            parsed = split_and_normalize(dt_text, ev["title"], venue)
            for p in parsed:
                p["detail_url"] = ev.get("detail_url")
            normalized.extend(parsed)
        except Exception as e:
            print(f"[{name}][WARN] Parse failed for '{dt_text}': {e}")
            continue

    print(f"[{name}] Parsed {len(normalized)} event records from {len(raw_events)} API items")

    # 3) 期間フィルタリング（当月1日～翌月末日）
    start_date, end_date = _get_target_date_range()
    print(f"[{name}] Target range: {start_date} ~ {end_date}")
    filtered = _filter_date_range(normalized, start_date, end_date)
    print(f"[{name}] Filtered to {len(filtered)} events")

    # 4) 重複排除 & メタ情報付与
    seen = set()
    out: List[Dict] = []
    extracted_at = datetime.now(JST).isoformat()

    for it in filtered:
        title_norm = _normalize_for_hash(it.get("title", ""))
        venue_norm = _normalize_for_hash(it.get("venue", ""))
        date_part = it.get("date", "")
        time_part = it.get("time") or ""

        key = f"{date_part}|{time_part}|{title_norm}|{venue_norm}"
        h = _sha1(key)
        if h in seen:
            continue
        seen.add(h)

        out.append({
            "schema_version": schema_version,
            **it,  # date / time / title / venue
            "source": it.get("detail_url") or source_url,
            "hash": h,
            "extracted_at": extracted_at,
        })

    print(f"[{name}] After deduplication: {len(out)} events")

    # 5) ソート（date, time, title）
    def _sort_key(ev: Dict):
        t = ev.get("time")
        tkey = t if (t and re.fullmatch(r"\d{2}:\d{2}", t)) else "99:99"
        return (ev.get("date", ""), tkey, ev.get("title", ""))

    out.sort(key=_sort_key)

    # 6) JSON保存
    path = _storage_path(target_date, code)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[{name}] Saved {len(out)} events to {path}")

    # 7) Supabase投入
    db_enabled = os.getenv("ENABLE_DB_SAVE", "0") == "1"
    if db_enabled and SUPABASE_AVAILABLE:
        _save_to_supabase(out, name)
    elif db_enabled:
        print(f"[{name}] DB投入スキップ: Supabase依存関係不足")

    # 8) ログ
    ms = int((time.time() - t0) * 1000)
    print(f"[{name}] date={target_date} items={len(out)} range={start_date}~{end_date} ms={ms} → {path}")
