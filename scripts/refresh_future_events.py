import os
import sys
import json
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# リポジトリルートをパスに追加（重要！）
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# .env自動読み込み
from dotenv import load_dotenv
load_dotenv()  # ← これだけで.envが読み込まれる

from supabase import create_client

# スクレイパーのインポート
from scrapers import (
    marinemesse_a,
    marinemesse_b,
    kokusai_center,
    congress_b,
    sunpalace,
    paypay_dome,
    paypay_dome_events,
    best_denki_stadium
)

JST = ZoneInfo("Asia/Tokyo")

def run_scraper_safe(scraper_module):
    """スクレイパーを安全に実行"""
    try:
        scraper_module.main()
        return True, None
    except Exception as e:
        err_msg = str(e)
        print(f"[refresh][WARN] {scraper_module.__name__} failed: {err_msg}")
        return False, err_msg

def generate_hash(event: dict) -> str:
    """イベントのハッシュを生成（フォールバック用）"""
    key = f"{event['date']}|{event.get('time', '')}|{event['title']}|{event['venue']}"
    return hashlib.sha1(key.encode('utf-8')).hexdigest()

def collect_scraped_events(today: str):
    """storage/からスクレイピング結果を収集し、件数も集計する"""
    events = []
    venue_counts = {}
    
    venue_codes = ['a', 'b', 'c', 'd', 'e', 'f', 'f_event', 'g']
    storage_dir = Path(__file__).resolve().parents[1] / "storage"
    
    print(f"[refresh] Looking for storage at: {storage_dir}")
    
    for code in venue_codes:
        storage_file = storage_dir / f"{today}_{code}.json"
        
        if storage_file.exists():
            try:
                with open(storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    for event in data:
                        # event_type = 'auto' を明示
                        event['event_type'] = 'auto'
                        
                        # ★★★ source → source_url のマッピング変換を追加 ★★★
                        if 'source' in event and 'source_url' not in event:
                            event['source_url'] = event.pop('source')
                        
                        # ★★★ hash → data_hash の変換（後方互換性） ★★★
                        if 'hash' in event and 'data_hash' not in event:
                            event['data_hash'] = event.pop('hash')
                        
                        # ★★★ data_hashがない場合は生成（フォールバック） ★★★
                        if 'data_hash' not in event or not event.get('data_hash'):
                            event['data_hash'] = generate_hash(event)
                            print(f"[refresh] Generated missing hash for: {event['title']}")
                    
                    events.extend(data)
                    venue_counts[code] = len(data)
                    print(f"[refresh] Loaded {len(data)} events from {code}")
            except Exception as e:
                print(f"[refresh][ERROR] Failed to load {code}: {e}")
                venue_counts[code] = 0
        else:
            print(f"[refresh][WARN] Not found: {storage_file}")
            venue_counts[code] = 0
    
    return events, venue_counts

def main():
    print("[refresh] === Future Events Refresh Start ===")
    
    # 1. 今日の日付取得（JST）
    today = datetime.now(JST).strftime("%Y-%m-%d")
    print(f"[refresh] Today (JST): {today}")
    print(f"[refresh] Strategy: DELETE date >= {today} AND event_type = 'auto'")
    print(f"[refresh] Protected: date < {today} OR event_type = 'manual'")
    
    # 2. 全スクレイパー実行
    print("[refresh] Running all scrapers...")
    scrapers = [
        marinemesse_a,
        marinemesse_b,
        kokusai_center,
        congress_b,
        sunpalace,
        paypay_dome,
        paypay_dome_events,
        best_denki_stadium
    ]
    
    success_count = 0
    errors = []
    for scraper in scrapers:
        success, err_msg = run_scraper_safe(scraper)
        if success:
            success_count += 1
        else:
            errors.append(f"{scraper.__name__.split('.')[-1]}: {err_msg}")
    
    print(f"[refresh] Scrapers: {success_count}/{len(scrapers)} succeeded")
    
    # 3. スクレイピング結果と件数を収集
    all_events, venue_counts = collect_scraped_events(today)
    
    # ★ 3.5 0件警告対象会場（常時イベントがある会場）の判定
    zero_warnings = []
    critical_venues = {
        'a': 'マリンメッセA館',
        'b': 'マリンメッセB館',
        'c': '福岡国際センター',
        'd': '福岡国際会議場',
        'e': '福岡サンパレス'
    }
    for code, name in critical_venues.items():
        if venue_counts.get(code, 0) == 0:
            zero_warnings.append(f"{name} ({code})")
            print(f"[refresh][WARN] Zero events detected for critical venue: {name}")

    # ★ 4. Slack/LINEに件数・異常ログを送信
    try:
        from notify import dispatch
        dispatch.send_log(venue_counts, errors, zero_warnings)
    except Exception as e:
        print(f"[refresh][WARN] Failed to send dispatch log: {e}")
    
    print(f"[refresh] Collected {len(all_events)} total events")
    
    if not all_events:
        print("[refresh][WARN] No events collected, skipping refresh")
        return
    
    # 4. DB保存の有効/無効チェック
    enable_db_save = os.getenv("ENABLE_DB_SAVE", "0") == "1"
    
    if not enable_db_save:
        print("[refresh] ENABLE_DB_SAVE=0, skipping database operations")
        print(f"[refresh] ✅ Collected {len(all_events)} events and saved to JSON files")
        print("[refresh] === Future Events Refresh Complete ===")
        return
    
    # 5. Supabase接続（.envから自動読み込み）
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("[refresh][ERROR] Missing SUPABASE credentials in .env")
        print("[refresh][INFO] Set ENABLE_DB_SAVE=0 to skip database operations")
        sys.exit(1)
    
    supabase = create_client(supabase_url, supabase_key)
    
    # 6. トランザクション実行
    try:
        print("[refresh] Executing transaction...")
        result = supabase.rpc('refresh_future_auto_events', {
            'today_date': today,
            'new_events': all_events
        }).execute()
        
        if result.data:
            deleted = result.data[0].get('deleted_count', 0)
            inserted = result.data[0].get('inserted_count', 0)
            print(f"[OK] [refresh] Transaction success: deleted {deleted}, inserted {inserted}")
        else:
            print(f"[OK] [refresh] Transaction success: inserted {len(all_events)} events")
            
    except Exception as e:
        print(f"[FAIL] [refresh] Transaction failed: {e}")
        print("[refresh] Attempting fallback (no transaction)...")
        
        # フォールバック（トランザクションなし）
        try:
            # 削除
            del_result = supabase.table('events').delete()\
                .gte('date', today)\
                .eq('event_type', 'auto')\
                .execute()
            
            deleted_count = len(del_result.data) if del_result.data else 0
            print(f"[DELETE] [refresh] Fallback: deleted {deleted_count} events")
            
            # 挿入
            supabase.table('events').insert(all_events).execute()
            print(f"[OK] [refresh] Fallback: inserted {len(all_events)} events")
            
        except Exception as fe:
            print(f"[FAIL] [refresh] Fallback failed: {fe}")
            sys.exit(1)
    
    print("[refresh] === Future Events Refresh Complete ===")

if __name__ == "__main__":
    main()
