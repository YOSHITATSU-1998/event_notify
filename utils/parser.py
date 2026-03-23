# utils/parser.py
import re
from datetime import date, time as dtime, datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

# 単日日付（例: 8.29(金) / 8.29）
_date_pat = re.compile(r'(?P<m>\d{1,2})[./](?P<d>\d{1,2})(?:\([^)]+\))?')

# 期間（例: 8.13(水)～8.31(日) / 8/13〜8/31 / 8.13-8.31 / 9.3(水)～7(日)）
_RANGE_PAT = re.compile(
    r'(?P<m1>\d{1,2})[./](?P<d1>\d{1,2})(?:\([^)]+\))?\s*'
    r'[～~\-–—〜]\s*'
    r'(?:(?P<m2>\d{1,2})[./])?(?P<d2>\d{1,2})(?:\([^)]+\))?'  # m2を任意に変更
)

# 時刻は「～」の有無や後続文字を気にせず拾えるように（例: 10:00 / 10:00～18:00）
_TIME_ANY = re.compile(r'(?P<h>\d{1,2}):(?P<mi>\d{2})')

def _expand_dates(y: int, m1: int, d1: int, m2: int, d2: int):
    """年 y で [m1/d1 .. m2/d2] を両端含めて日ごと展開。
    年跨ぎ対応: m2 < m1 の場合は終了日を翌年として展開する。
    例: _expand_dates(2026, 12, 30, 1, 2) → 12/30, 12/31, 1/1, 1/2
    """
    out = []
    try:
        cur = date(y, m1, d1)
        # 年跨ぎ: 終了月 < 開始月 の場合は翌年
        end_year = y + 1 if m2 < m1 else y
        end = date(end_year, m2, d2)
    except ValueError:
        return out
    if cur > end:
        return out
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out

def _infer_year(base_year: int, month: int, current_month: int) -> int:
    """年跨ぎ推定: 10月以降に実行し、1-3月のイベントが出た場合は翌年と推定。
    
    例:
      current_month=12, month=1 → base_year + 1（翌年1月）
      current_month=12, month=3 → base_year + 1（翌年3月）
      current_month=3,  month=1 → base_year（今年1月 = 過去、filterで除外される）
      current_month=6,  month=8 → base_year（今年8月 = 未来）
    """
    if current_month >= 10 and month <= 3:
        return base_year + 1
    return base_year

def split_and_normalize(dt_text: str, title: str, venue: str, year: int | None = None):
    """
    '8.29(金) 10:30～ 14:00～ 8.30(土) 10:00～'
      → [{'date':'YYYY-MM-DD','time':'HH:MM','title':..., 'venue':...}, ...]

    '8.13(水)～8.31(日) 10:00～18:00'
      → 8/13〜8/31 を日ごと展開（時間は先頭の 10:00 を採用）
      
    '9.3(水)～7(日)'  ← 月省略パターンに対応
      → 9/3〜9/7 を日ごと展開（開始月を終了日にも適用）
      
    '12.30(火)～1.2(金)' ← 年跨ぎ対応
      → 12/30〜翌年1/2 を日ごと展開
    """
    # year=None → 自動推定モード（年跨ぎ補正あり）
    _auto_infer = (year is None)
    if year is None:
        year = datetime.now(JST).year
    _current_month = datetime.now(JST).month

    out = []
    # '|' 以降に施設備考が来ることがあるので手前だけ使う
    left = dt_text.split('|', 1)[0].strip()
    # 全角/半角の揺れを軽く標準化
    left = left.replace('〜', '～').replace('－', '-').replace('—', '–')

    # 1) 期間表記（レンジ）を先に処理
    rm = _RANGE_PAT.search(left)
    if rm:
        m1 = int(rm.group('m1')); d1 = int(rm.group('d1'))
        # 終了月が省略されている場合は開始月を継承
        m2 = int(rm.group('m2')) if rm.group('m2') else m1
        d2 = int(rm.group('d2'))

        # テキスト中の時刻を全部拾い、先頭ひとつを開始時刻として採用
        times = []
        for mt in _TIME_ANY.finditer(left):
            try:
                hh = int(mt.group('h')); mi = int(mt.group('mi'))
                times.append(f"{hh:02d}:{mi:02d}")
            except Exception:
                pass
        use_time = times[0] if times else None

        for d in _expand_dates(year, m1, d1, m2, d2):
            out.append({
                "date": d.strftime("%Y-%m-%d"),
                "time": use_time,     # 展示などは開始時刻のみ。方針次第で None や終日にも可。
                "title": title,
                "venue": venue
            })
        return out

    # 2) 単日＋複数時刻など、従来ロジック
    tokens = re.split(r'\s+', left)
    current_date = None
    for tok in tokens:
        # 日付トークン？
        dm = _date_pat.fullmatch(tok)
        if dm:
            mm = int(dm.group('m')); dd = int(dm.group('d'))
            try:
                use_year = _infer_year(year, mm, _current_month) if _auto_infer else year
                current_date = date(use_year, mm, dd)
            except ValueError:
                current_date = None
            continue

        # 時刻トークン？（末尾に '～' 等が付いていてもOKにするため search）
        if current_date:
            tm = _TIME_ANY.search(tok)
            if tm:
                try:
                    hh = int(tm.group('h')); mi = int(tm.group('mi'))
                    out.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "time": f"{hh:02d}:{mi:02d}",
                        "title": title,
                        "venue": venue
                    })
                except ValueError:
                    pass

    # 3) 時刻が1つも無い場合は日付のみで登録（従来のフォールバック）
    if not out:
        for dm in _date_pat.finditer(left):
            mm = int(dm.group('m')); dd = int(dm.group('d'))
            try:
                use_year = _infer_year(year, mm, _current_month) if _auto_infer else year
                d = date(use_year, mm, dd)
                out.append({
                    "date": d.strftime("%Y-%m-%d"),
                    "time": None,
                    "title": title,
                    "venue": venue
                })
            except ValueError:
                pass

    return out
