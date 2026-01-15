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
    """Ver.3.1.4: 天気情報自動更新機能追加版HTML生成"""
    current_time = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>福岡イベント情報 - {today}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP", sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            background-color: #f8f9fa;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 10px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
        }}
        .weather-section {{
            text-align: center;
            margin-bottom: 20px;
            padding: 10px;
            background: #e3f2fd;
            border-radius: 5px;
            border: 1px solid #bbdefb;
            font-weight: bold;
            color: #1565c0;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
        }}
        .weather-icon {{
            font-size: 1.5em;
        }}
        .update-time {{
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
            margin-bottom: 30px;
        }}
        .data-source {{
            text-align: center;
            color: #27ae60;
            font-size: 0.8em;
            font-weight: bold;
            margin-bottom: 20px;
            padding: 8px;
            background: #f0f8f0;
            border-radius: 4px;
        }}
        .content {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
        }}
        pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace;
            font-size: 14px;
            line-height: 1.5;
            color: #2c3e50;
            margin: 0;
        }}
        .venue-section {{
            background: #e8f4fd;
            padding: 20px;
            border-radius: 5px;
            border-left: 4px solid #3498db;
            margin-bottom: 30px;
        }}
        .venue-link {{
            color: #2980b9;
            text-decoration: none;
            transition: color 0.3s ease;
        }}
        .venue-link:hover {{
            color: #3498db;
            text-decoration: underline;
        }}
        .calendar-section {{
            background: #f0f8f0;
            padding: 20px;
            border-radius: 5px;
            border-left: 4px solid #27ae60;
            text-align: center;
            margin-bottom: 30px;
        }}
        .calendar-link {{
            display: inline-block;
            background: #27ae60;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 16px;
            transition: background-color 0.3s ease;
            margin-top: 10px;
        }}
        .calendar-link:hover {{
            background: #219a52;
            text-decoration: none;
        }}
        .opinion-section {{
            background: #fff5cd;
            padding: 20px;
            border-radius: 5px;
            border-left: 4px solid #f39c12;
            text-align: center;
            margin-bottom: 30px;
        }}
        .opinion-link {{
            display: inline-block;
            background: #f39c12;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 16px;
            transition: background-color 0.3s ease;
            margin-top: 10px;
        }}
        .opinion-link:hover {{
            background: #e67e22;
            text-decoration: none;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            color: #95a5a6;
            font-size: 0.85em;
        }}
        @media (max-width: 600px) {{
            body {{
                padding: 10px;
            }}
            .container {{
                padding: 15px;
            }}
            pre {{
                font-size: 13px;
            }}
            .calendar-link, .opinion-link {{
                font-size: 14px;
                padding: 10px 20px;
            }}
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
            <pre>{event_message}</pre>
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
            <p>Ver.3.1.4 - 8会場対応（天気情報自動更新機能）</p>
            <p><a href="manual.html" style="color: #95a5a6; text-decoration: none; font-size: 0.8em;">管理者ページへ</a></p>
        </div>
    </div>
    
    <script>
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

def create_manual_html() -> str:
    """Ver.1.8: manual.html を生成（パスワードはプレースホルダー）"""
    html = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>手動イベント追加 - 福岡イベント情報</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP", sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f8f9fa;
            line-height: 1.6;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .hidden { display: none; }
        .form-group {
            margin: 20px 0;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #2c3e50;
        }
        input, select, textarea {
            width: 100%;
            padding: 12px;
            margin-bottom: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 16px;
            box-sizing: border-box;
        }
        input:focus, select:focus, textarea:focus {
            border-color: #3498db;
            outline: none;
        }
        button {
            background: #3498db;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: background-color 0.3s ease;
        }
        button:hover {
            background: #2980b9;
        }
        .auth-section {
            text-align: center;
        }
        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
            border: 1px solid #c3e6cb;
        }
        .error-message {
            color: #e74c3c;
            margin-top: 10px;
            font-weight: bold;
        }
        .json-output {
            background: #2c3e50;
            color: #ecf0f1;
            border-radius: 6px;
            padding: 15px;
            font-family: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, monospace;
            font-size: 13px;
            white-space: pre-wrap;
            max-height: 300px;
            overflow-y: auto;
            margin: 10px 0;
        }
        .copy-button {
            background: #27ae60;
            margin-top: 10px;
        }
        .copy-button:hover {
            background: #219a52;
        }
        small {
            color: #7f8c8d;
            font-size: 14px;
        }
        .back-link {
            display: inline-block;
            margin-bottom: 20px;
            color: #3498db;
            text-decoration: none;
            font-weight: bold;
        }
        .back-link:hover {
            text-decoration: underline;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
        }
        h3 {
            color: #34495e;
        }
        .instruction {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #3498db;
            margin: 15px 0;
        }
        .instruction ol {
            margin: 10px 0;
            padding-left: 20px;
        }
        .instruction code {
            background: #e9ecef;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="index.html" class="back-link">← メインページに戻る</a>
        
        <h1>🎪 手動イベント追加</h1>
        
        <!-- パスワード認証セクション -->
        <div id="auth-section" class="auth-section">
            <h3>🔐 管理者認証</h3>
            <p>イベント情報を手動で追加するには認証が必要です</p>
            <div class="form-group">
                <input type="password" id="password" placeholder="パスワードを入力してください">
                <button onclick="authenticate()">ログイン</button>
            </div>
            <div id="auth-error" class="error-message"></div>
        </div>
        
        <!-- フォームセクション（初期状態：非表示） -->
        <div id="form-section" class="hidden">
            <h3>📝 イベント情報入力</h3>
            
            <div class="form-group">
                <label for="event-type">イベントタイプ:</label>
                <select id="event-type" onchange="toggleDateFields()">
                    <option value="">選択してください</option>
                    <option value="oneshot">単発イベント（1日のみ）</option>
                    <option value="recurring">期間指定イベント（複数日）</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="title">イベント名:</label>
                <input type="text" id="title" placeholder="例: 放生屋">
            </div>
            
            <div class="form-group">
                <label for="venue">会場名:</label>
                <input type="text" id="venue" placeholder="例: 箱崎宮">
            </div>
            
            <!-- 単発イベント用 -->
            <div id="oneshot-fields" class="hidden">
                <div class="form-group">
                    <label for="single-date">開催日:</label>
                    <input type="date" id="single-date">
                </div>
            </div>
            
            <!-- 期間指定イベント用 -->
            <div id="recurring-fields" class="hidden">
                <div class="form-group">
                    <label for="start-date">開始日:</label>
                    <input type="date" id="start-date">
                </div>
                <div class="form-group">
                    <label for="end-date">終了日:</label>
                    <input type="date" id="end-date">
                </div>
            </div>
            
            <div class="form-group">
                <label for="time">時刻（任意）:</label>
                <input type="time" id="time">
                <small>空欄の場合「時刻未定」として表示されます</small>
            </div>
            
            <div class="form-group">
                <label for="notes">備考（任意）:</label>
                <textarea id="notes" rows="3" placeholder="追加情報があれば記入してください"></textarea>
            </div>
            
            <button onclick="submitEvent()">🚀 イベント追加</button>
            
            <div id="success-message" class="success-message hidden"></div>
        </div>
    </div>

    <script>
        // パスワード認証
        function authenticate() {
            const password = document.getElementById('password').value;
            const correctPassword = 'PLACEHOLDER_PASSWORD'; // GitHub Actions で置換される
            
            if (password === correctPassword) {
                document.getElementById('auth-section').classList.add('hidden');
                document.getElementById('form-section').classList.remove('hidden');
                document.getElementById('auth-error').textContent = '';
            } else {
                document.getElementById('auth-error').textContent = 'パスワードが間違っています';
            }
        }
        
        // イベントタイプによる表示切り替え
        function toggleDateFields() {
            const eventType = document.getElementById('event-type').value;
            const oneshotFields = document.getElementById('oneshot-fields');
            const recurringFields = document.getElementById('recurring-fields');
            
            if (eventType === 'oneshot') {
                oneshotFields.classList.remove('hidden');
                recurringFields.classList.add('hidden');
            } else if (eventType === 'recurring') {
                oneshotFields.classList.add('hidden');
                recurringFields.classList.remove('hidden');
            } else {
                oneshotFields.classList.add('hidden');
                recurringFields.classList.add('hidden');
            }
        }
        
        // イベント追加処理
        function submitEvent() {
            const eventType = document.getElementById('event-type').value;
            const title = document.getElementById('title').value;
            const venue = document.getElementById('venue').value;
            const time = document.getElementById('time').value || null;
            const notes = document.getElementById('notes').value || '';
            
            if (!eventType || !title || !venue) {
                alert('必須項目（イベントタイプ、イベント名、会場名）を入力してください');
                return;
            }
            
            let eventData = {
                title: title,
                venue: venue,
                time: time,
                notes: notes,
                added_at: new Date().toISOString()
            };
            
            if (eventType === 'oneshot') {
                const date = document.getElementById('single-date').value;
                if (!date) {
                    alert('開催日を選択してください');
                    return;
                }
                eventData.date = date;
                generateJSON('oneshot', eventData);
            } else if (eventType === 'recurring') {
                const startDate = document.getElementById('start-date').value;
                const endDate = document.getElementById('end-date').value;
                if (!startDate || !endDate) {
                    alert('開始日と終了日を選択してください');
                    return;
                }
                if (startDate > endDate) {
                    alert('開始日は終了日より前の日付にしてください');
                    return;
                }
                eventData.start_date = startDate;
                eventData.end_date = endDate;
                generateJSON('recurring', eventData);
            }
        }
        
        // JSON生成・表示
        function generateJSON(type, eventData) {
            const jsonOutput = JSON.stringify([eventData], null, 2);
            
            // 成功メッセージ表示
            const successMsg = document.getElementById('success-message');
            const timeDisplay = eventData.time ? eventData.time : '時刻未定';
            const dateDisplay = type === 'oneshot' 
                ? eventData.date 
                : `${eventData.start_date} ～ ${eventData.end_date}`;
            
            successMsg.innerHTML = `
                <h4>✅ イベント情報が生成されました！</h4>
                <p><strong>追加予定:</strong> ${eventData.title} (${eventData.venue}) - ${dateDisplay} ${timeDisplay}</p>
                
                <div class="instruction">
                    <h5>📋 次の手順:</h5>
                    <ol>
                        <li>下のJSONをコピー</li>
                        <li><code>manual_events/${type}.json</code> ファイルを開く（なければ作成）</li>
                        <li>既存の配列に追加するか、新規作成</li>
                        <li>dispatch実行で反映確認</li>
                    </ol>
                </div>
                
                <div class="json-output" id="json-output-${type}">${jsonOutput}</div>
                <button class="copy-button" onclick="copyToClipboard(document.getElementById('json-output-${type}').textContent)">📋 JSONをコピー</button>
                
                <p><small>💡 ヒント: 既存のJSONファイルがある場合は、配列内に追加してください</small></p>
            `;
            successMsg.classList.remove('hidden');
            
            // フォームリセット
            resetForm();
        }
        
        // フォームリセット
        function resetForm() {
            document.getElementById('event-type').value = '';
            document.getElementById('title').value = '';
            document.getElementById('venue').value = '';
            document.getElementById('single-date').value = '';
            document.getElementById('start-date').value = '';
            document.getElementById('end-date').value = '';
            document.getElementById('time').value = '';
            document.getElementById('notes').value = '';
            
            // 日付フィールドを非表示に
            document.getElementById('oneshot-fields').classList.add('hidden');
            document.getElementById('recurring-fields').classList.add('hidden');
        }
        
        // クリップボードコピー（改良版）
        function copyToClipboard(text) {
            // モダンブラウザ対応
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text).then(() => {
                    alert('✅ JSONをクリップボードにコピーしました!\\nmanual_events/ フォルダの該当ファイルに貼り付けてください。');
                }).catch((err) => {
                    console.error('Clipboard API failed:', err);
                    fallbackCopy(text);
                });
            } else {
                // フォールバック方式
                fallbackCopy(text);
            }
        }
        
        // フォールバック方式でコピー
        function fallbackCopy(text) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            textarea.setSelectionRange(0, 99999); // モバイル対応
            
            try {
                const successful = document.execCommand('copy');
                if (successful) {
                    alert('✅ JSONをコピーしました（フォールバック方式）\\nmanual_events/ フォルダに貼り付けてください。');
                } else {
                    alert('❌ コピーに失敗しました。手動で選択してコピーしてください。');
                }
            } catch (err) {
                console.error('Fallback copy failed:', err);
                alert('❌ 自動コピーに失敗しました。\\nJSONを手動で選択してCtrl+Cでコピーしてください。');
            } finally {
                document.body.removeChild(textarea);
            }
        }
        
        // Enterキーでパスワード認証
        document.getElementById('password').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                authenticate();
            }
        });
        
        // ページ読み込み時に今日の日付を最小値に設定
        document.addEventListener('DOMContentLoaded', function() {
            const today = new Date().toISOString().split('T')[0];
            document.getElementById('single-date').min = today;
            document.getElementById('start-date').min = today;
            document.getElementById('end-date').min = today;
        });
    </script>
</body>
</html>"""
    return html

def export_manual_html():
    """Ver.1.8: manual.html を生成してsite/に保存"""
    try:
        print("[html_export] Generating manual.html...")
        
        # manual.html を生成
        manual_content = create_manual_html()
        
        # site/manual.html に保存
        site_dir = Path(__file__).parent.parent / "site"
        site_dir.mkdir(exist_ok=True)
        output_path = site_dir / "manual.html"
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(manual_content)
        
        print(f"[html_export] Successfully generated: {output_path}")
        print(f"[html_export] File size: {len(manual_content)} bytes")
        print(f"[html_export] Password placeholder: PLACEHOLDER_PASSWORD")
        
    except Exception as e:
        print(f"[html_export][ERROR] Failed to generate manual.html: {e}")
        import traceback
        traceback.print_exc()
        raise

def export_html():
    """Ver.3.1.4: データベース優先・フォールバック対応版HTMLファイル生成"""
    try:
        print("[html_export] Starting Ver.3.1.4 HTML generation (with auto-updating weather)...")
        
        # 今日の日付を取得
        today = determine_today_standalone()
        print(f"[html_export] Target date: {today}")
        
        # データソース・イベント取得（優先度制御）
        data_source = "データベース（GitHub Pages生成時点）"
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
        event_message = build_message_standalone(today, events, missing)
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
        
        # Ver.1.8: manual.html も生成
        export_manual_html()
        
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
