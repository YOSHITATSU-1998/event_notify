import os
import sys
import json
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any, List, Optional

# Windows環境でのUnicodeEncodeError防止
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# リポジトリルートをsys.pathに追加
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# .envが存在すれば自動読み込み（ローカル実行時用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

JST = ZoneInfo("Asia/Tokyo")


def get_current_jst() -> datetime:
    """現在時刻（JST）を取得"""
    return datetime.now(JST)


def normalize_time(time_value: Any) -> Optional[str]:
    """
    時刻の正規化。
    '18:00:00' -> '18:00'
    未定、None、空文字 -> None
    """
    if time_value is None:
        return None
    time_str = str(time_value).strip()
    if not time_str or time_str in ("（時刻未定）", "None", "null"):
        return None
    # 'HH:MM:SS' または 'HH:MM'
    if len(time_str) >= 5 and ":" in time_str[:5]:
        return time_str[:5]
    return time_str


def sanitize_error_message(err: Exception) -> str:
    """
    エラーメッセージからURL、APIキー等の機密情報を安全に除去
    """
    msg = str(err)
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    if supabase_key and supabase_key in msg:
        msg = msg.replace(supabase_key, "[REDACTED_KEY]")
    if supabase_url and supabase_url in msg:
        msg = msg.replace(supabase_url, "[REDACTED_URL]")
    return msg[:300]


def build_audit_data(
    status: str,
    target_date: str,
    events: List[Dict[str, Any]],
    error_message: Optional[str] = None
) -> Dict[str, Any]:
    """監査用JSONデータを生成"""
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    run_number_str = os.getenv("GITHUB_RUN_NUMBER", "0")
    run_attempt_str = os.getenv("GITHUB_RUN_ATTEMPT", "1")
    source_sha = os.getenv("GITHUB_SHA", "unknown")

    try:
        run_number = int(run_number_str)
    except ValueError:
        run_number = 0

    try:
        run_attempt = int(run_attempt_str)
    except ValueError:
        run_attempt = 1

    generated_at = get_current_jst().isoformat(timespec="seconds")

    audit: Dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "run_number": run_number,
        "run_attempt": run_attempt,
        "source_sha": source_sha,
        "generated_at": generated_at,
        "target_date": target_date,
        "timezone": "Asia/Tokyo",
        "status": status,
        "data_source": "supabase.events",
        "event_count": len(events),
        "events": events
    }

    if error_message:
        audit["error_message"] = error_message

    return audit


def print_and_save_audit(audit_data: Dict[str, Any], output_path: Path):
    """マーカー付きでログ出力し、JSONファイルに保存"""
    json_str = json.dumps(audit_data, indent=2, ensure_ascii=False)

    # 1. ファイル保存（UTF-8）
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str + "\n")
        print(f"[audit] Audit log saved to: {output_path}")
    except Exception as e:
        print(f"[audit][ERROR] Failed to save audit file: {e}", file=sys.stderr)

    # 2. 開始・終了マーカー付きでログ出力
    print("EVENT_AUDIT_BEGIN")
    print(json_str)
    print("EVENT_AUDIT_END")


def fetch_today_events(target_date: str) -> List[Dict[str, Any]]:
    """
    Supabaseから直接当日のイベント一覧を取得。
    フォールバックは行わない。
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment variables")

    from supabase import create_client
    client = create_client(supabase_url, supabase_key)

    # ポータル公開側と同一の条件: date == target_date, order by time ASC
    # NULLSの順序を安定させるためPython側でもtimeソートを実施
    response = client.table("events")\
        .select("date, venue, title, time, event_type, source_url")\
        .eq("date", target_date)\
        .order("time", desc=False)\
        .execute()

    if not hasattr(response, "data") or response.data is None:
        raise RuntimeError("Supabase returned no data object")

    raw_records = response.data
    normalized_events: List[Dict[str, Any]] = []

    for item in raw_records:
        norm_event = {
            "date": str(item.get("date") or target_date),
            "venue": str(item.get("venue") or ""),
            "title": str(item.get("title") or ""),
            "time": normalize_time(item.get("time")),
            "event_type": str(item.get("event_type") or "auto"),
            "source_url": item.get("source_url") or None
        }
        normalized_events.append(norm_event)

    # 時刻順ソート（未定/Noneは末尾）
    def sort_key(ev: Dict[str, Any]):
        t = ev.get("time")
        time_sort = t if t else "99:99"
        return (time_sort, ev.get("venue", ""), ev.get("title", ""))

    normalized_events.sort(key=sort_key)
    return normalized_events


def main():
    parser = argparse.ArgumentParser(description="Generate audit log for today's events")
    parser.add_argument("--date", type=str, default=None, help="Target date in YYYY-MM-DD (defaults to JST today)")
    parser.add_argument("--output", type=str, default="today-event-audit.json", help="Output JSON file path")
    args = parser.parse_args()

    # 1. 対象日の決定（JST）
    if args.date:
        target_date = args.date
    else:
        target_date = get_current_jst().strftime("%Y-%m-%d")

    output_path = Path(args.output).resolve()
    print(f"[audit] Starting audit log generation for date: {target_date}")

    # 2. Supabaseから取得
    try:
        events = fetch_today_events(target_date)
        print(f"[audit] Successfully fetched {len(events)} events from Supabase")

        audit_data = build_audit_data(
            status="ok",
            target_date=target_date,
            events=events
        )
        print_and_save_audit(audit_data, output_path)
        sys.exit(0)

    except Exception as e:
        safe_msg = sanitize_error_message(e)
        print(f"[audit][ERROR] Failed to fetch events from Supabase: {safe_msg}", file=sys.stderr)

        audit_data = build_audit_data(
            status="error",
            target_date=target_date,
            events=[],
            error_message=safe_msg
        )
        print_and_save_audit(audit_data, output_path)
        # 監査ステップを失敗させる
        sys.exit(1)


if __name__ == "__main__":
    main()
