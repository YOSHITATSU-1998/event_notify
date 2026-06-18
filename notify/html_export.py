# notify/html_export.py Ver.3.1.4（天気情報自動更新機能追加版）
import os
import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Tuple, Dict, Any

# パス解決
sys.path.append(str(Path(__file__).parent.parent))

# Supabase投入用（オプション）
try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    load_dotenv()
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# JST定義
JST = timezone(timedelta(hours=9))

# 会場定義（Ver.1.8: 8会場対応）
VENUES = [
    ("a", "マリンメッセA館"),
    ("b", "マリンメッセB館"),
    ("c", "福岡国際センター"),
    ("d", "福岡国際会議場"),
    ("e", "福岡サンパレス"),
    ("f", "みずほPayPayドーム"),
    ("f_event", "みずほPayPayドーム（イベント）"),  
    ("g", "ベスト電器スタジアム")  # Ver.1.8対応
]

# 会場リンクマッピング
VENUE_LINKS = {
    "マリンメッセA館": "https://www.marinemesse.or.jp/messe/event/",
    "マリンメッセB館": "https://www.marinemesse.or.jp/messe-b/event/",
    "福岡国際センター": "https://www.marinemesse.or.jp/kokusai/event/",
    "福岡国際会議場": "https://www.marinemesse.or.jp/congress/event/",
    "福岡サンパレス": "https://www.f-sunpalace.com/hall/#hallEvent",
    "みずほPayPayドーム": "https://www.softbankhawks.co.jp/",
    "ベスト電器スタジアム": "https://www.avispa.co.jp/game_practice"
}

# Google Forms URL
OPINION_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfX2EtHu3hZ2FgMfUjSOx1YYQqt2BaB3BGniVPF5TMCtgLByw/viewform"

def determine_today_standalone() -> str:
    """今日の日付を取得（単独動作版）"""
    return datetime.now(JST).strftime("%Y-%m-%d")

def get_storage_dir() -> Path:
    """ストレージディレクトリを取得（単独動作版）"""
    try:
        from utils.paths import STORAGE_DIR
        return STORAGE_DIR
    except ImportError:
        storage_dir = Path(__file__).parent.parent / "storage"
        storage_dir.mkdir(exist_ok=True)
        return storage_dir

def get_supabase_client() -> Client:
    """Supabaseクライアントを取得（デバッグ強化版）"""
    print(f"[html_export] DEBUG - SUPABASE_AVAILABLE: {SUPABASE_AVAILABLE}")
    
    if not SUPABASE_AVAILABLE:
        raise RuntimeError("Supabase dependencies not available")
    
    # 環境変数デバッグ出力
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    print(f"[html_export] DEBUG - SUPABASE_URL: {url[:30] if url else 'None'}...")
    print(f"[html_export] DEBUG - SUPABASE_KEY: {key[:20] if key else 'None'}...")
    print(f"[html_export] DEBUG - URL type: {type(url)}")
    print(f"[html_export] DEBUG - KEY type: {type(key)}")
    
    if not url or not key:
        error_msg = f"Environment variables missing - URL: {bool(url)}, KEY: {bool(key)}"
        print(f"[html_export] DEBUG - {error_msg}")
        raise RuntimeError(f"SUPABASE_URL or SUPABASE_KEY not set in environment. {error_msg}")
    
    return create_client(url, key)

def main():
    """メイン実行関数（デバッグ版）"""
    # 最初に環境変数を表示
    print(f"[html_export] DEBUG - Environment check:")
    print(f"[html_export] DEBUG - SUPABASE_URL present: {bool(os.getenv('SUPABASE_URL'))}")
    print(f"[html_export] DEBUG - SUPABASE_KEY present: {bool(os.getenv('SUPABASE_KEY'))}")
    print(f"[html_export] DEBUG - ENABLE_DB_SAVE: {os.getenv('ENABLE_DB_SAVE', 'NOT_SET')}")
    
    export_html()

def load_events_from_database(today: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Ver.2.5: Supabaseから当日のイベントを取得（時刻表示正規化対応）"""
    try:
        print(f"[html_export] Attempting database connection...")
        supabase = get_supabase_client()
        print(f"[html_export] Supabase client created successfully")
        
        # 当日のイベントを取得
        print(f"[html_export] Querying events for date: {today}")
        result = supabase.table('events').select('*').eq('date', today).execute()
        
        print(f"[html_export] DEBUG - Query result type: {type(result)}")
        print(f"[html_export] DEBUG - Result.data type: {type(result.data) if hasattr(result, 'data') else 'No data attribute'}")
        print(f"[html_export] DEBUG - Result.data length: {len(result.data) if hasattr(result, 'data') and result.data is not None else 'No data or None'}")
        
        if not hasattr(result, 'data') or result.data is None:
            print(f"[html_export] No data attribute or data is None")
            return [], []
        
        if not result.data:
            print(f"[html_export] No events found in database for {today}")
            return [], []
        
        # Supabaseデータを標準形式に変換
        events = []
        print(f"[html_export] DEBUG - Starting data conversion for {len(result.data)} records")
        
        for i, db_record in enumerate(result.data):
            print(f"[html_export] DEBUG - Processing record {i+1}: {type(db_record)}")
            
            # デバッグ: レコード内容確認
            print(f"[html_export] DEBUG - Record keys: {list(db_record.keys()) if db_record else 'None record'}")
            
            # 時刻データの正規化処理
            time_value = db_record.get("time")
            print(f"[html_export] DEBUG - time_value: {time_value} (type: {type(time_value)})")
            
            if time_value:
                # PostgreSQLのTIME型から文字列への変換対応
                time_str = str(time_value)
                print(f"[html_export] DEBUG - time_str: {time_str}")
                # HH:MM:SS → HH:MM に変換（秒を削除）
                if len(time_str) >= 5:
                    time_value = time_str[:5]  # "18:00:00" → "18:00"
            else:
                time_value = None  # None維持（後で（時刻未定）に変換）
            
            event = {
                "date": db_record.get("date"),
                "time": time_value,  # 正規化済み時刻
                "title": db_record.get("title", ""),
                "venue": db_record.get("venue", ""),
                "source": db_record.get("source_url", ""),
                "hash": db_record.get("data_hash", ""),
                "event_type": db_record.get("event_type", "auto"),
                "notes": db_record.get("notes", "")
            }
            
            # PayPayドーム用の追加情報をnotesから抽出
            notes = event.get("notes", "")
            print(f"[html_export] DEBUG - notes value: {notes} (type: {type(notes)})")
            
            # None チェックを追加
            if notes is not None and "game_status:" in notes:
                try:
                    # "game_status: 試合前, score: None" のような形式から抽出
                    import re
                    game_status_match = re.search(r'game_status:\s*([^,]+)', notes)
                    score_match = re.search(r'score:\s*([^,\n]+)', notes)
                    
                    if game_status_match:
                        event["game_status"] = game_status_match.group(1).strip()
                    if score_match:
                        score_value = score_match.group(1).strip()
                        event["score"] = None if score_value in ["None", "null"] else score_value
                except Exception as e:
                    print(f"[html_export] Error parsing notes: {e}")
            events.append(event)
        
        # 時刻順ソート
        def sort_key(event):
            time_str = event.get("time", "99:99")
            if not time_str or time_str == "（時刻未定）":
                return ("99:99", event.get("title", ""), event.get("venue", ""))
            return (time_str, event.get("title", ""), event.get("venue", ""))
        
        events.sort(key=sort_key)
        
        print(f"[html_export] Successfully loaded {len(events)} events from database")
        
        # Ver.2.5: missingは空（DB直結のため会場別の失敗概念なし）
        return events, []
        
    except Exception as e:
        print(f"[html_export] Database connection failed: {e}")
        raise

def load_events_standalone(today: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """イベントデータを読み込み（従来のJSONファイル版・フォールバック用）"""
    storage_dir = get_storage_dir()
    events = []
    missing = []
    
    print(f"[html_export] Loading events from storage: {storage_dir}")
    
    for code, venue_name in VENUES:
        json_path = storage_dir / f"{today}_{code}.json"
        
        try:
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # リスト形式の場合
                if isinstance(data, list):
                    events.extend(data)
                    print(f"[html_export] Loaded {len(data)} events from {code}")
                # 単一オブジェクトの場合
                elif isinstance(data, dict):
                    events.append(data)
                    print(f"[html_export] Loaded 1 event from {code}")
                else:
                    print(f"[html_export] Unexpected data format in {code}: {type(data)}")
            else:
                missing.append(code)
                print(f"[html_export] Missing file: {json_path}")
                
        except Exception as e:
            missing.append(code)
            print(f"[html_export] Error loading {code}: {e}")
    
    # 今日のイベントのみフィルタ
    today_events = [ev for ev in events if ev.get("date") == today]
    
    # 時刻順ソート
    def sort_key(event):
        time_str = event.get("time", "99:99")
        if not time_str or time_str == "（時刻未定）":
            return ("99:99", event.get("title", ""), event.get("venue", ""))
        return (time_str, event.get("title", ""), event.get("venue", ""))
    
    today_events.sort(key=sort_key)
    
    print(f"[html_export] Filtered to {len(today_events)} events for {today}")
    return today_events, missing

def build_message_standalone(today: str, events: List[Dict[str, Any]], missing: List[str]) -> str:
    """Ver.1.6: Slack通知と同じメッセージを生成（スマホファースト・2行表示対応）"""
    lines = [f"【本日のイベント】{today}"]
    
    if not events:
        lines.append("")  # タイトルとの区切り
        lines.append("本日の掲載イベントは見つかりませんでした。")
    else:
        lines.append("")  # タイトルとイベント一覧の区切り
        for i, ev in enumerate(events):
            time_value = ev.get("time")
            time_str = time_value if time_value else "（時刻未定）"
            title = ev.get("title", "")
            venue = ev.get("venue", "")
            
            # Ver.1.6: 2行表示
            lines.append(f"- {time_str}｜{venue}")
            lines.append(title)
            
            # 最後のイベント以外に空白行追加
            if i != len(events) - 1:
                lines.append("")

    if missing:
        lines.append("")  # イベントとmissing情報の区切り
        lines.append(f"取得できなかった会場: {', '.join(missing)}")

    return "\n".join(lines)


def build_clean_cards_standalone(today: str, events: List[Dict[str, Any]], missing: List[str]) -> str:
    """Ver.4.0: シンプル＆クリーンUI用のHTMLカードを生成"""
    lines = [f'<div class="event-header">【本日のイベント】{today}</div>']
    
    if not events:
        lines.append('<div class="empty-event">本日の掲載イベントは見つかりませんでした。</div>')
    else:
        for ev in events:
            time_value = ev.get("time")
            time_str = time_value if time_value else "（時刻未定）"
            title = ev.get("title", "")
            venue = ev.get("venue", "")
            source_url = ev.get("source", "")
            
            if source_url:
                title_html = f'<a href="{source_url}" target="_blank" rel="noopener noreferrer">{title}</a>'
            else:
                title_html = title
            
            lines.append(f"""
            <div class="event-item">
                <div class="event-meta">
                    <span class="event-time">{time_str}</span>
                    <span class="event-venue">{venue}</span>
                </div>
                <div class="event-title">{title_html}</div>
            </div>
            """)
            
    if missing:
        lines.append(f'<div class="missing-alert"><br>取得できなかった会場: {", ".join(missing)}</div>')

    return "\n".join(lines)
def generate_venue_list() -> str:
    """VENUES配列から会場一覧HTMLを生成（リンク化・PayPayドーム統合）"""
    # PayPayドーム重複削除
    unique_venues = []
    seen_venues = set()
    
    for code, name in VENUES:
        # PayPayドーム系は統合
        if "みずほPayPayドーム" in name:
            if "みずほPayPayドーム" not in seen_venues:
                unique_venues.append("みずほPayPayドーム")
                seen_venues.add("みずほPayPayドーム")
        else:
            if name not in seen_venues:
                unique_venues.append(name)
                seen_venues.add(name)
    
    # リンク化してHTML生成
    lines = ["【現在の対応会場】"]
    for venue_name in unique_venues:
        if venue_name in VENUE_LINKS:
            url = VENUE_LINKS[venue_name]
            lines.append(f'・<a href="{url}" target="_blank" class="venue-link">{venue_name}</a>')
        else:
            lines.append(f"・{venue_name}")
    
    return "\n".join(lines)

def create_html_content(today: str, event_message: str, venue_list: str, data_source: str) -> str:
    """Ver.3.2.2: キャッシュ無効化＋天気情報自動更新機能版HTML生成"""
    current_time = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <script>
        // Ver.4.3.1: 新ポータルサイト（Vercel）への自動リダイレクト
        window.location.replace("https://fukuoka-events-calendar.com/portal");
    </script>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>福岡イベント情報 - {today}</title>
    <style>

        body {{
            font-family: "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            background-color: #f0f2f5;
            color: #1a1a1a;
        }}
        .container {{
            background: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        h1 {{
            color: #1a1a1a;
            text-align: center;
            margin-bottom: 20px;
            font-size: 1.8em;
            border-bottom: 3px solid #1877f2;
            padding-bottom: 15px;
        }}
        .weather-section {{
            text-align: center;
            margin-bottom: 20px;
            padding: 12px;
            background: #e7f3ff;
            border-radius: 6px;
            border: 1px solid #cce4ff;
            font-weight: bold;
            color: #1877f2;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            font-size: 1.1em;
        }}
        .weather-icon {{
            font-size: 1.5em;
        }}
        .update-time {{
            text-align: center;
            color: #65676b;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}
        .data-source {{
            text-align: center;
            color: #2e890c;
            font-size: 0.85em;
            font-weight: bold;
            margin-bottom: 25px;
            padding: 8px;
            background: #f0fcf0;
            border: 1px solid #d4f4d4;
            border-radius: 6px;
        }}
        .content {{
            background: #fafafa;
            padding: 25px;
            border-radius: 8px;
            margin-bottom: 30px;
            border: 1px solid #e4e6eb;
        }}
        
        .event-header {{ 
            font-weight: bold; 
            font-size: 1.1em; 
            color: #1a1a1a;
            margin-bottom: 20px; 
            border-bottom: 2px solid #ccd0d5; 
            padding-bottom: 8px; 
        }}
        .event-item {{ 
            margin-bottom: 20px; 
            padding: 8px 0 8px 16px; 
            border-left: 4px solid #3b82f6; 
        }}
        .event-item:last-child {{ 
            margin-bottom: 0; 
        }}
        .event-meta {{ 
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px; 
        }}
        .event-time {{ 
            font-weight: 600; 
            color: #2563eb; 
            font-size: 1em; 
            letter-spacing: 0.5px;
        }}
        .event-venue {{ 
            color: #6b7280; 
            font-size: 0.875rem; 
            font-weight: normal; 
        }}
        .event-title {{ 
            font-size: 1.125rem; 
            font-weight: 500; 
            color: #1f2937; 
            line-height: 1.4; 
            margin-top: 4px;
        }}
        .event-title a {{
            color: #1f2937;
            text-decoration: none;
        }}
        .event-title a:hover {{
            text-decoration: underline;
            color: #000000;
        }}
        .empty-event {{ 
            color: #65676b; 
            padding: 20px 0; 
            text-align: center; 
        }}
        .missing-alert {{
            color: #dc3545;
            font-weight: bold;
            font-size: 0.95em;
        }}
        
        pre {{ 
            white-space: pre-wrap;
            word-wrap: break-word;
            font-size: 14px;
            line-height: 1.6;
            color: #1a1a1a;
            font-family: inherit;
            margin: 0;
        }}
        .venue-section {{
            background: #f0f2f5;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #1877f2;
            margin-bottom: 30px;
        }}
        .venue-link {{
            color: #1877f2;
            text-decoration: none;
            font-weight: bold;
        }}
        .venue-link:hover {{
            color: #0c56c2;
            text-decoration: underline;
        }}
        .calendar-section {{
            background: #f0fcf0;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #2e890c;
            text-align: center;
            margin-bottom: 30px;
        }}
        .calendar-link {{
            display: inline-block;
            background: #2e890c;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 1.1em;
            transition: background-color 0.2s ease;
            margin-top: 10px;
        }}
        .calendar-link:hover {{
            background: #23690a;
        }}
        .opinion-section {{
            background: #fff8e6;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #f5a623;
            text-align: center;
            margin-bottom: 30px;
        }}
        .opinion-link {{
            display: inline-block;
            background: #f5a623;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 1.1em;
            transition: background-color 0.2s ease;
            margin-top: 10px;
        }}
        .opinion-link:hover {{
            background: #d68f1c;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e4e6eb;
            color: #65676b;
            font-size: 0.9em;
        }}
        @media (max-width: 600px) {{
            body {{ padding: 8px; }}
            .container {{ padding: 15px; }}
            .event-time {{ font-size: 1.1em; }}
            .event-title {{ font-size: 1.2em; }}
            .calendar-link, .opinion-link {{ font-size: 1em; padding: 12px 20px; width: 90%; }}
        }}
    
</style>
</head>
<body>
    <div class="container">
        <h1>福岡イベント情報</h1>
        
        <div id="weather-section" class="weather-section">
            <span class="weather-icon">⌛</span> 天気読み込み中...
        </div>
        
        <div class="update-time">最終更新: {current_time}</div>
        <div class="data-source">データソース: {data_source}</div>
        
        <div class="content">
            {event_message}
        </div>
        
        <div class="venue-section">
            <pre>{venue_list}</pre>
        </div>
        
        <div class="calendar-section">
            <h3>📅 月間カレンダー表示</h3>
            <p>イベント情報を月間カレンダー形式で確認できます</p>
            <a href="https://fukuoka-events-calendar.vercel.app/" target="_blank" class="calendar-link">今月のカレンダーはこちら</a>
            <p style="font-size: 0.8em; color: #666; margin-top: 10px;">
                ※ 日付をクリックして詳細表示
            </p>
        </div>
        
        <div class="opinion-section">
            <h3>ご意見・ご要望</h3>
            <p>会場追加のご希望や情報漏れのご報告をお待ちしています</p>
            <a href="{OPINION_FORM_URL}" target="_blank" class="opinion-link">ご意見・ご要望はこちら</a>
            <p style="font-size: 0.8em; color: #666; margin-top: 10px;">
                ※ Googleアカウントが必要です
            </p>
        </div>
        
        <div class="footer">
            <p>福岡市内主要イベント会場の情報を自動収集・配信しています</p>
            <p>Ver.3.4.3 - 8会場対応</p>
            <p><a href="https://fukuoka-events-calendar.vercel.app/admin" style="color: #95a5a6; text-decoration: none; font-size: 0.8em;">管理者ページへ</a></p>
        </div>
    </div>
    
    <script>
    // Ver.3.2.2: 日付ベースのキャッシュバスター（ローカル時間=JST基準）
    (function() {{
        const now = new Date();
        const today = now.getFullYear() + '-'
            + String(now.getMonth() + 1).padStart(2, '0') + '-'
            + String(now.getDate()).padStart(2, '0');
        const url = new URL(window.location);
        const lastLoad = url.searchParams.get('t');
        if (lastLoad !== today) {{
            url.searchParams.set('t', today);
            window.location.replace(url.toString());
            return; // リダイレクト後は以降のスクリプトを実行しない
        }}
    }})();

    (function() {{
        const weatherSection = document.getElementById('weather-section');
        
        // 天気取得ロジックを関数化（Ver.3.1.4）
        const fetchWeather = () => {{
            console.log('🌤 天気情報更新開始: ' + new Date().toLocaleTimeString('ja-JP'));
            
            fetch('https://api.open-meteo.com/v1/forecast?latitude=33.59&longitude=130.40&current=temperature_2m,weather_code&timezone=Asia/Tokyo')
                .then(response => response.json())
                .then(data => {{
                    const temp = Math.round(data.current.temperature_2m);
                    const code = data.current.weather_code;
                    
                    const weatherMap = {{
                        0: {{ icon: '☀', text: '晴れ' }},
                        1: {{ icon: '☀', text: '晴れ' }},
                        2: {{ icon: '⛅', text: '曇り' }},
                        3: {{ icon: '☁', text: '曇り' }},
                        45: {{ icon: '🌫', text: '霧' }},
                        48: {{ icon: '🌫', text: '霧' }},
                        51: {{ icon: '☔', text: '小雨' }},
                        53: {{ icon: '☔', text: '小雨' }},
                        55: {{ icon: '☔', text: '小雨' }},
                        61: {{ icon: '☔', text: '雨' }},
                        63: {{ icon: '☔', text: '雨' }},
                        65: {{ icon: '☔', text: '雨' }},
                        71: {{ icon: '☃', text: '雪' }},
                        73: {{ icon: '☃', text: '雪' }},
                        75: {{ icon: '☃', text: '雪' }},
                        80: {{ icon: '⚡', text: '雷雨' }},
                        81: {{ icon: '⚡', text: '雷雨' }},
                        82: {{ icon: '⚡', text: '雷雨' }},
                        95: {{ icon: '⚡', text: '雷雨' }},
                        96: {{ icon: '⚡', text: '雷雨' }},
                        99: {{ icon: '⚡', text: '雷雨' }}
                    }};
                    
                    const weather = weatherMap[code] || {{ icon: '☁', text: '曇り' }};
                    
                    // 現在時刻を取得（更新時刻表示用）
                    const now = new Date();
                    const timeStr = now.toLocaleTimeString('ja-JP', {{ hour: '2-digit', minute: '2-digit' }});
                    
                    // HTML更新（更新時刻を表示）
                    weatherSection.innerHTML = `
                        <span class="weather-icon">${{weather.icon}}</span>
                        <span>${{weather.text}} / 気温: ${{temp}}℃</span>
                        <span style="font-size: 0.7em; color: #888; margin-left: 5px;">(${{timeStr}}更新)</span>
                    `;
                    
                    console.log('✅ 天気情報更新完了: ' + weather.text + ' / ' + temp + '℃');
                }})
                .catch(error => {{
                    console.error('❌ 天気情報の取得に失敗:', error);
                    
                    // エラー時の挙動（Ver.3.1.4）
                    if (weatherSection.innerHTML.includes('読み込み中')) {{
                        // 初回取得失敗の場合のみ非表示
                        weatherSection.style.display = 'none';
                        console.log('初回取得失敗のため天気セクションを非表示にしました');
                    }} else {{
                        // 2回目以降の更新失敗は前回の表示を維持
                        console.log('前回の天気情報を維持します');
                    }}
                }});
        }};
        
        // 1. 初回実行（ページ読み込み時に即座に取得）
        fetchWeather();
        
        // 2. 定期実行（30分 = 1,800,000ミリ秒ごとに自動更新）
        setInterval(fetchWeather, 1800000);
        
        // 3. Visibility API対応（タブ復帰時に即座更新）
        document.addEventListener('visibilitychange', () => {{
            if (!document.hidden) {{
                console.log('📱 タブがアクティブになりました - 天気情報を即座更新');
                fetchWeather();
            }}
        }});
    }})();
    </script>
</body>
</html>"""
    return html

# create_manual_html() は Ver.3.4.3 で廃止
# アーカイブ: notify/old/html_export_v3.4.2_with_manual.py
# 管理画面は Vercel (calendar/src/app/admin/) に移行済み



def export_html():
    """Ver.3.1.4: データベース優先・フォールバック対応版HTMLファイル生成"""
    try:
        print("[html_export] Starting Ver.3.1.4 HTML generation (with auto-updating weather)...")
        
        # 今日の日付を取得
        today = determine_today_standalone()
        print(f"[html_export] Target date: {today}")
        
        # データソース・イベント取得（優先度制御）
        data_source = "データベース"
        events = []
        missing = []
        
        try:
            # 1. データベース接続を試行（最優先）
            events, missing = load_events_from_database(today)
            print(f"[html_export] Database success: {len(events)} events loaded")
            
        except Exception as db_error:
            print(f"[html_export] Database failed, falling back to storage: {db_error}")
            data_source = "ストレージファイル（フォールバック）"
            
            try:
                # 2. フォールバック：JSONファイル読み込み
                events, missing = load_events_standalone(today)
                print(f"[html_export] Storage fallback success: {len(events)} events loaded")
                
            except Exception as storage_error:
                print(f"[html_export] Storage fallback also failed: {storage_error}")
                data_source = "データ取得失敗"
                events, missing = [], []
        
        # メッセージ生成（Ver.1.6: 2行表示対応）
        event_message = build_clean_cards_standalone(today, events, missing)
        print(f"[html_export] Generated message: {len(event_message)} characters")
        
        # 会場一覧を生成（リンク化・統合処理）
        venue_list = generate_venue_list()
        print(f"[html_export] Generated venue list with links")
        
        # index.html全体を構築（データソース表示追加）
        html_content = create_html_content(today, event_message, venue_list, data_source)
        
        # site/index.html に保存
        site_dir = Path(__file__).parent.parent / "site"
        site_dir.mkdir(exist_ok=True)
        output_path = site_dir / "index.html"
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"[html_export] Successfully generated: {output_path}")
        print(f"[html_export] File size: {len(html_content)} bytes")
        print(f"[html_export] Events included: {len(events)}")
        print(f"[html_export] Missing venues: {missing}")
        print(f"[html_export] Data source: {data_source}")
        print(f"[html_export] Ver.3.1.4 - Auto-updating weather feature added")
        print(f"[html_export] Weather updates: Every 30 minutes + on tab activation")
        
        # Ver.3.4.3: manual.html は廃止（Vercel adminに移行済み）
        print("[html_export] manual.html generation skipped (moved to Vercel)")
        
    except Exception as e:
        print(f"[html_export][ERROR] Critical failure in HTML generation: {e}")
        import traceback
        traceback.print_exc()
        raise

def main():
    """メイン実行関数"""
    export_html()

if __name__ == "__main__":
    main()
    