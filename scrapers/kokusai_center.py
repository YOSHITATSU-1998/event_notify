# scrapers/kokusai_center.py
import os
import json
import time
import hashlib
from datetime import datetime
from typing import List, Dict
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from event_notify.utils.parser import split_and_normalize, JST  # 正規化＆展開は共通関数に委譲

# ---- メタ情報（変更に強いヘッダ部） -----------------------------------------
META = {
    "name": "kokusai_center",
    "venue": "福岡国際センター",
    "venue_code": "c",  # ファイル名に使用（storage/{date}_c.json）
    "url": "https://www.marinemesse.or.jp/kokusai/event/",
    "schema_version": "1.0",
    "selector_profile": "primary: table.table_list01>tr / fallback: table>tr (2+ tds)",
}

SELECTORS = {
    "primary_rows": "table.table_list01 tr",
    "fallback_rows": "table tr",
}

# ---- HTTP / Fetch ------------------------------------------------------------
DEFAULT_UA = (
    os.getenv("SCRAPER_UA")
    or "event_notify-bot/1.0 (+contact: your-mail-or-site) "
       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.marinemesse.or.jp/",
    "Connection": "keep-alive",
}
DEBUG = os.getenv("DEBUG_IC", "0") == "1"

def _storage_path(date_str: str, code: str) -> Path:
    """共通のストレージパス生成（他のスクレイパーと統一）"""
    root = Path(__file__).resolve().parents[1]  # repo root (= event_notify/)
    storage = root / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"{date_str}_{code}.json"

def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _requests_session() -> requests.Session:
    retry = Retry(
        total=3, connect=2, read=2,
        backoff_factor=0.7,
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s = requests.Session()
    s.headers.update(HEADERS)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

def _fetch_html(url: str) -> str:
    """段階的フェッチ: requests → cloudscraper（必要時のみ）"""
    sess = _requests_session()
    r = sess.get(url, timeout=20)
    if DEBUG:
        print(f"[{META['name']}] fetch status={r.status_code} len={len(r.text or '')}")
    if r.status_code == 200 and r.text:
        return r.text

    # フォールバック（必要時のみ）
    time.sleep(1.0)
    try:
        import cloudscraper  # type: ignore
    except ImportError as e:
        raise RuntimeError("cloudscraper 未インストール。`pip install cloudscraper`") from e

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False, "desktop": True},
        delay=5,
    )
    scraper.headers.update(HEADERS)
    r2 = scraper.get(url, timeout=25)
    if DEBUG:
        print(f"[{META['name']}] cloudscraper status={r2.status_code} len={len(r2.text or '')}")
    if r2.status_code != 200 or not r2.text:
        raise RuntimeError(f"cloudscraperでも取得失敗: status={r2.status_code}")
    return r2.text

# ---- Parse -------------------------------------------------------------------
def _extract_rows(soup: BeautifulSoup) -> List:
    rows = soup.select(SELECTORS["primary_rows"])
    if not rows or len(rows) <= 1:
        rows = soup.select(SELECTORS["fallback_rows"])
    return rows

def fetch_raw_events() -> List[Dict[str, str]]:
    """
    国際センター（https://www.marinemesse.or.jp/kokusai/event/）
    1行=1イベント（ヘッダ行は除外）
      - 1列目: 日付/期間（+時刻が含まれる場合あり）
      - 2列目: タイトル（<a>優先）
    """
    html = _fetch_html(META["url"])
    soup = BeautifulSoup(html, "html.parser")

    events = []
    rows = _extract_rows(soup)

    for tr in rows:
        # ヘッダ行スキップ
        if tr.find("th"):
            continue
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        # 1列目（日付・時間）改行をスペースに
        dt_text = " ".join(tds[0].get_text(" ", strip=True).split())

        # 2列目（タイトル）リンク優先
        a = tds[1].find("a")
        title = a.get_text(" ", strip=True) if a else tds[1].get_text(" ", strip=True)

        # ナビ行/空行除外
        if not title or "前月" in title or "翌月" in title:
            continue

        events.append({"datetime": dt_text, "title": title})

    return events

# ---- Normalize / Build -------------------------------------------------------
def _norm_for_hash(s: str) -> str:
    """ハッシュ用の軽量正規化：空白圧縮＋trim（NFKCや引用符統一はsplit_and_normalize側で実施想定）"""
    return " ".join((s or "").split()).strip()

def build_output(today_str: str, raw: List[Dict[str, str]]) -> List[Dict]:
    # 共通正規化＆展開（date/time/title/venue を返す想定）
    normalized = []
    for e in raw:
        normalized.extend(split_and_normalize(e["datetime"], e["title"], META["venue"]))

    # 当日分だけ抽出
    todays = [x for x in normalized if x.get("date") == today_str]

    # 重複排除（キー順序：date|time|title|venue）
    seen = set()
    out = []
    extracted_at = datetime.now(JST).isoformat(timespec="seconds")
    for it in todays:
        date_v = _norm_for_hash(it.get("date", ""))
        time_v = _norm_for_hash(it.get("time", ""))  # 省略可
        title_v = _norm_for_hash(it.get("title", ""))
        venue_v = _norm_for_hash(it.get("venue", META["venue"]))
        key = f"{date_v}|{time_v}|{title_v}|{venue_v}"
        h = _sha1(key)
        if h in seen:
            continue
        seen.add(h)
        out.append({
            "schema_version": META["schema_version"],
            "date": date_v,
            **({"time": time_v} if time_v else {}),
            "title": title_v,
            "venue": venue_v,
            "source": META["url"],
            "hash": h,
            "extracted_at": extracted_at,
        })

    # 整列（date, time, title）
    def sort_key(ev):
        t = ev.get("time") or "99:99"
        return (ev.get("date", ""), t, ev.get("title", ""))
    out.sort(key=sort_key)
    return out

# ---- Save / Main -------------------------------------------------------------
def _save(today_str: str, items: List[Dict]) -> str:
    path = _storage_path(today_str, META['venue_code'])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return str(path)

def main():
    t0 = time.time()
    today = datetime.now(JST).date()
    today_str = today.strftime("%Y-%m-%d")

    raw = fetch_raw_events()
    out = build_output(today_str, raw)

    # 成功（0件でも成功扱いで保存する＝当日の「0件」を明示化）
    path = _save(today_str, out)
    ms = int((time.time() - t0) * 1000)
    print(f"[{META['name']}] date={today_str} items={len(out)} ms={ms} url={META['url']} → {path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 失敗時：ファイルは生成しない（ディスパッチ側がmissing検出）
        msg = str(e).replace("\n", " ")
        print(f"[{META['name']}][ERROR] msg=\"{msg}\"")
        # exit 0（全体は止めない）
