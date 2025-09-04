# notify/dispatch.py Ver.1.3対応版（PayPayドーム追加・通知フィルター対応）
import os
import json
import hashlib
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any
from pathlib import Path
import requests

# パス解決
sys.path.append(str(Path(__file__).parent.parent))
try:
    from utils.paths import STORAGE_DIR
except ImportError:
    # STORAGE_DIRを直接定義
    STORAGE_DIR = Path(__file__).parent.parent / "storage"
    STORAGE_DIR.mkdir(exist_ok=True)

# --- 設定 ---------------------------------------------------------------
JST = timezone(timedelta(hours=9))
VENUES: List[Tuple[str, str]] = [
    ("a", "マリンメッセA館"),
    ("b", "マリンメッセB館"),
    ("c", "福岡国際センター"),
    ("d", "福岡国際会議場"),
    ("e", "福岡サンパレス"),
    ("f", "みずほPayPayドーム"),  # Ver.1.3追加
    ("f_event", "みずほPayPayドーム（イベント）"),  # 1.4実装
]
CODE_INDEX: Dict[str, int] = {c: i for i, (c, _) in enumerate(VENUES)}
CODE2NAME: Dict[str, str] = {c: n for c, n in VENUES}
LAST_SENT_PATH = (STORAGE_DIR / "last_sent.txt")

# ★ 環境変数から取得
def get_webhook_urls():
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    line_token = os.getenv("LINE_NOTIFY_TOKEN")
    
    if not slack_url:
        print("[dispatch][WARN] SLACK_WEBHOOK_URL not set")
    
    return slack_url, line_token

def get_github_pages_url():
    """GitHub Pages URLを取得（環境変数から）"""
    return os.getenv("GITHUB_PAGES_URL", "")

# --- ユーティリティ ------------------------------------------------------
def determine_today() -> str:
    override = os.getenv("DISPATCH_TARGET_DATE")
    if override:
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")

def _read_json_array(path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return []

def _time_key(t: str | None) -> str:
    return t if (t and len(t) == 5) else "99:99"

def _sort_key(ev: Dict[str, Any]):
    return (_time_key(ev.get("time")), ev.get("title", ""), CODE_INDEX.get(ev.get("code",""), 10**9))

# --- コア ---------------------------------------------------------------
def load_events_for(today: str) -> tuple[list[Dict[str, Any]], list[str]]:
    all_ev: list[Dict[str, Any]] = []
    missing: list[str] = []

    for code, _name in VENUES:
        path = STORAGE_DIR / f"{today}_{code}.json"
        try:
            arr = _read_json_array(path)
        except FileNotFoundError:
            missing.append(code)
            continue
        except Exception as e:
            print(f"[dispatch][WARN] read fail code={code} msg=\"{e}\"")
            missing.append(code)
            continue

        for obj in arr:
            date = obj.get("date")
            title = obj.get("title")
            if not date or not title:
                continue
            if date != today:
                continue
            
            # Ver.1.3: PayPayドーム用通知フィルター
            # for_notification が false の場合は通知対象外（試合終了など）
            if obj.get("for_notification") == False:
                print(f"[dispatch] Skipping non-notification event: {title}")
                continue
            
            ev = {
                "date": date,
                "time": obj.get("time"),
                "title": title,
                "venue": obj.get("venue") or CODE2NAME.get(code, ""),
                "source": obj.get("source"),
                "hash": obj.get("hash"),
                "code": code,
                "game_status": obj.get("game_status"),  # PayPayドーム用
                "score": obj.get("score"),  # PayPayドーム用
            }
            all_ev.append(ev)

    seen: set[str] = set()
    uniq: list[Dict[str, Any]] = []
    for ev in all_ev:
        key = ev.get("hash") or f"{ev['date']}|{ev.get('time') or ''}|{ev['title']}|{ev['venue']}"
        if key in seen:
            continue
        seen.add(key)
        uniq.append(ev)

    uniq.sort(key=_sort_key)
    return uniq, missing

# --- 整形 ---------------------------------------------------------------
def format_message(today: str, events: list[Dict[str, Any]], missing: list[str], pages_url: str = "") -> str:
    lines: list[str] = [f"【本日のイベント】{today}"]

    if not events:
        lines.append("本日の掲載イベントは見つかりませんでした。")
    else:
        for ev in events:
            t = ev.get("time") if ev.get("time") else "（時刻未定）"
            lines.append(f"- {t}｜{ev.get('title','')}（{ev.get('venue','')}）")

    if missing:
        missing_names = [CODE2NAME.get(code, code) for code in missing]
        lines.append("取得できなかった会場: " + ", ".join(missing_names))

    # Ver.1.3: Web URL追加
    if pages_url:
        lines.append(f"詳細: {pages_url}")

    return "\n".join(lines)

# --- 再送防止（保存だけ残す） --------------------------------------------
def _body_sha1(body: str) -> str:
    return hashlib.sha1(body.encode("utf-8")).hexdigest()

def save_body_hash(body: str) -> None:
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LAST_SENT_PATH, "w", encoding="utf-8") as f:
            f.write(_body_sha1(body))
    except Exception as e:
        print(f"[dispatch][WARN] last_sent write fail msg=\"{e}\"")

# --- 送信 ---------------------------------------------------------------
def send_to_slack(text: str, webhook_url: str) -> bool:
    if not webhook_url:
        print("[dispatch][WARN] No Slack URL -> skip Slack")
        return False
    try:
        r = requests.post(webhook_url, json={"text": text}, timeout=15)
        print(f"[dispatch] slack status={r.status_code}")
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[dispatch][ERROR] Slack msg=\"{e}\"")
        return False

def send_to_line(text: str, line_token: str) -> bool:
    if not line_token:
        return False
    try:
        r = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {line_token}"},
            data={"message": text},
            timeout=15,
        )
        print(f"[dispatch] line status={r.status_code}")
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[dispatch][ERROR] LINE msg=\"{e}\"")
        return False

# --- build_message 関数（Web出力と共用） ----------------------------------
def build_message(today: str, events: list[Dict[str, Any]], missing: list[str], pages_url: str = "") -> str:
    """Slack通知とWeb出力で共用する純関数（Ver.1.3: Web URL対応）"""
    return format_message(today, events, missing, pages_url)

# --- main ----------------------------------------------------------------
def main() -> None:
    print("[dispatch] start Ver.1.3")
    today = determine_today()
    events, missing = load_events_for(today)
    print(f"[dispatch] gathered items={len(events)} missing={missing}")

    # GitHub Pages URL取得
    pages_url = get_github_pages_url()
    if pages_url:
        print(f"[dispatch] pages_url={pages_url}")

    body = build_message(today, events, missing, pages_url)
    print("[dispatch] preview:\n" + body)

    # DRY_RUN チェック
    if os.getenv("DRY_RUN") == "1":
        print("[dispatch] DRY_RUN mode - not sending")
        return

    # ★ 環境変数から取得
    slack_url, line_token = get_webhook_urls()

    # 送信実行
    sent = False
    sent = send_to_slack(body, slack_url) or sent
    sent = send_to_line(body, line_token) or sent

    print(f"[dispatch] sent={sent} venues={len(VENUES)}")
    if sent:
        save_body_hash(body)

if __name__ == "__main__":
    main()

