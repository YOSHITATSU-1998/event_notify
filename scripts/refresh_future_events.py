import os
import sys
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# .env自動読み込み
from dotenv import load_dotenv
load_dotenv()  # ← これだけで.envが読み込まれる

from supabase import create_client

# スクレイパーのインポート
from event_notify.scrapers import (
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
        return True
    except Exception as e:
        print(f"[refresh][WARN] {scraper_module.__name__} failed: {e}")
        return False

def collect_scraped_events(today: str):
    """storage/からスクレイピング結果を収集"""
    events = []
    
    venue_codes = ['a', 'b', 'c', 'd', 'e', 'f', 'f_event', 'g']
    storage_dir = Path(__file__).resolve().parents[1] / "storage"
    
    print(f"[refresh] Looking for storage at: {storage_dir}")
    
    for code in venue_codes:
        storage_file = storage_dir / f"{today}_{code}.json"
        
        if storage_file.exists():
            try:
                with open(storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # event_type = 'auto' を明示
                    for event in data:
                        event['event_type'] = 'auto'
                    events.extend(data)
                    print(f"[refresh] Loaded {len(data)} events from {code}")
            except Exception as e:
                print(f"[refresh][ERROR] Failed to load {code}: {e}")
        else:
            print(f"[refresh][WARN] Not found: {storage_file}")
    
    return events

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
    for scraper in scrapers:
        if run_scraper_safe(scraper):
            success_count += 1
    
    print(f"[refresh] Scrapers: {success_count}/{len(scrapers)} succeeded")
    
    # 3. スクレイピング結果を収集
    all_events = collect_scraped_events(today)
    print(f"[refresh] Collected {len(all_events)} total events")
    
    if not all_events:
        print("[refresh][WARN] No events collected, skipping refresh")
        return
    
    # 4. Supabase接続（.envから自動読み込み）
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("[refresh][ERROR] Missing SUPABASE credentials in .env")
        sys.exit(1)
    
    supabase = create_client(supabase_url, supabase_key)
    
    # 5. トランザクション実行
    try:
        print("[refresh] Executing transaction...")
        result = supabase.rpc('refresh_future_auto_events', {
            'today_date': today,
            'new_events': all_events
        }).execute()
        
        if result.data:
            deleted = result.data[0].get('deleted_count', 0)
            inserted = result.data[0].get('inserted_count', 0)
            print(f"✅ [refresh] Transaction success: deleted {deleted}, inserted {inserted}")
        else:
            print(f"✅ [refresh] Transaction success: inserted {len(all_events)} events")
            
    except Exception as e:
        print(f"❌ [refresh] Transaction failed: {e}")
        print("[refresh] Attempting fallback (no transaction)...")
        
        # フォールバック（トランザクションなし）
        try:
            # 削除
            del_result = supabase.table('events').delete()\
                .gte('date', today)\
                .eq('event_type', 'auto')\
                .execute()
            
            deleted_count = len(del_result.data) if del_result.data else 0
            print(f"🗑️ [refresh] Fallback: deleted {deleted_count} events")
            
            # 挿入
            supabase.table('events').insert(all_events).execute()
            print(f"✅ [refresh] Fallback: inserted {len(all_events)} events")
            
        except Exception as fe:
            print(f"❌ [refresh] Fallback failed: {fe}")
            sys.exit(1)
    
    print("[refresh] === Future Events Refresh Complete ===")

if __name__ == "__main__":
    main()
