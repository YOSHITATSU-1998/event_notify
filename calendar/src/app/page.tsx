'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { createClient } from '@supabase/supabase-js';
import HolidayJp from '@holiday-jp/holiday_jp';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

type Event = {
  id: number;
  date: string;
  time?: string;
  title: string;
  venue: string;
  source_url?: string;
  notes?: string;
};

// ユーザーローカル時間で今日の日付を取得する関数
const getLocalToday = () => {
  const now = new Date();
  // ユーザーのローカル時間をそのまま使用
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0);
};

// 日付オブジェクトから YYYY-MM-DD 文字列をローカル時間基準で取得する関数（タイムゾーンのズレ防止）
const transDay = (date: Date) => {
  const y = date.getFullYear();
  const m = (date.getMonth() + 1).toString().padStart(2, '0');
  const d = date.getDate().toString().padStart(2, '0');
  return `${y}-${m}-${d}`;
};

export default function Home() {
  // ローカル時間基準で今日を初期値に設定
  const [currentDate, setCurrentDate] = useState(getLocalToday);
  const [selectedDate, setSelectedDate] = useState(getLocalToday);
  const [events, setEvents] = useState<Event[]>([]);
  const [monthlyEvents, setMonthlyEvents] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [shiftDates, setShiftDates] = useState<Record<string, boolean>>({});
  const [salesData, setSalesData] = useState<Record<string, number | null>>({});
  const [goalAmount, setGoalAmount] = useState<number>(0);

  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth(); // 0-11

  // マウント時にLocalStorageからシフト情報と売上情報を取得
  useEffect(() => {
    const shifts: Record<string, boolean> = {};
    const sales: Record<string, number | null> = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && /^\d{4}-\d{2}-\d{2}$/.test(key)) {
        try {
          const item = JSON.parse(localStorage.getItem(key) || '{}');
          if (item) {
            if (item.is_shift === true) {
              shifts[key] = true;
            }
            if (typeof item.sales !== 'undefined') {
              sales[key] = item.sales;
            }
          }
        } catch (e) {
          console.error(e);
        }
      }
    }
    setShiftDates(shifts);
    setSalesData(sales);
  }, []);

  // 表示月が切り替わったときに目標金額をリロード
  useEffect(() => {
    const monthKey = `${currentYear}-${(currentMonth + 1).toString().padStart(2, '0')}`;
    const storedGoal = localStorage.getItem(`goal-${monthKey}`);
    if (storedGoal) {
      setGoalAmount(parseInt(storedGoal, 10) || 0);
    } else {
      setGoalAmount(0);
    }
  }, [currentYear, currentMonth]);

  // 表示月の合計売上を算出
  const getMonthlySalesTotal = () => {
    let total = 0;
    const date = new Date(currentYear, currentMonth, 1);
    while (date.getMonth() === currentMonth) {
      const dateStr = transDay(date);
      total += salesData[dateStr] || 0;
      date.setDate(date.getDate() + 1);
    }
    return total;
  };

  const monthlySalesTotal = getMonthlySalesTotal();
  const remainingGoal = Math.max(0, goalAmount - monthlySalesTotal);


  // 画面サイズ検知
  useEffect(() => {
    const checkScreenSize = () => {
      setIsMobile(window.innerWidth <= 480);
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // 月間データ取得
  useEffect(() => {
    const fetchMonthlyData = async () => {
      const year = currentYear;
      const month = currentMonth + 1; // 1-12に変換

      // その月の1日から最終日まで
      const firstDay = `${year}-${month.toString().padStart(2, '0')}-01`;
      const lastDay = new Date(year, month, 0).getDate(); // その月の最終日
      const lastDate = `${year}-${month.toString().padStart(2, '0')}-${lastDay.toString().padStart(2, '0')}`;

      console.log(`データ取得範囲: ${firstDay} から ${lastDate}`);

      try {
        const { data, error } = await supabase
          .from('events')
          .select('date')
          .gte('date', firstDay)
          .lte('date', lastDate);

        if (error) {
          console.error('データ取得エラー:', error);
          return;
        }

        console.log(`取得データ数: ${data?.length || 0}件`);

        // 日別カウント
        const counts: Record<string, number> = {};
        data?.forEach((event) => {
          counts[event.date] = (counts[event.date] || 0) + 1;
        });

        console.log('日別カウント:', counts);
        setMonthlyEvents(counts);

      } catch (error) {
        console.error('取得エラー:', error);
      }
    };

    fetchMonthlyData();
  }, [currentYear, currentMonth]);

  // 選択日のイベント詳細取得
  useEffect(() => {
    const fetchDayEvents = async () => {
      setLoading(true);
      const dateStr = transDay(selectedDate);

      // デバッグログ追加
      console.log('イベント取得:', {
        selectedDate: selectedDate.toString(),
        dateStr,
        isToday: dateStr === transDay(getLocalToday())
      });

      try {
        const { data, error } = await supabase
          .from('events')
          .select('*')
          .eq('date', dateStr)
          .order('time', { ascending: true });

        console.log(`取得イベント数: ${data?.length || 0}件`);
        setEvents(data || []);
      } catch (error) {
        console.error('日別データ取得エラー:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchDayEvents();
  }, [selectedDate]);

  // カレンダー生成関数
  const generateCalendar = () => {
    const year = currentYear;
    const month = currentMonth;

    console.log('カレンダー生成:', { year, month });

    // その月の1日と最終日（UTC時刻で固定して計算）
    const firstDay = new Date(year, month, 1, 12, 0, 0); // 正午で固定
    const lastDay = new Date(year, month + 1, 0, 12, 0, 0); // 正午で固定

    // カレンダーの週開始位置と日数
    const startDayOfWeek = firstDay.getDay(); // 0=日曜
    const daysInMonth = lastDay.getDate();

    const calendar = [];

    // 前月の末尾を埋める
    const prevMonthLastDay = new Date(year, month, 0, 12, 0, 0).getDate();
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const day = prevMonthLastDay - i;
      calendar.push({
        day,
        date: new Date(year, month - 1, day, 12, 0, 0),
        isCurrentMonth: false
      });
    }

    // 当月の日付（デバッグログ追加）
    for (let day = 1; day <= daysInMonth; day++) {
      const dateObj = new Date(year, month, day, 12, 0, 0);
      if (day === 1) {
        console.log('1日生成:', {
          year,
          month,
          day,
          dateObj,
          isoString: dateObj.toISOString(),
          dateString: transDay(dateObj)
        });
      }

      calendar.push({
        day,
        date: dateObj,
        isCurrentMonth: true
      });
    }

    // 次月の先頭を埋める（6週間分まで）
    const remaining = 42 - calendar.length;
    for (let day = 1; day <= remaining; day++) {
      calendar.push({
        day,
        date: new Date(year, month + 1, day, 12, 0, 0),
        isCurrentMonth: false
      });
    }

    return calendar;
  };

  const calendar = generateCalendar();

  const monthNames = [
    '1月', '2月', '3月', '4月', '5月', '6月',
    '7月', '8月', '9月', '10月', '11月', '12月'
  ];

  const weekDays = ['日', '月', '火', '水', '木', '金', '土'];

  const formatTime = (time?: string) => {
    if (!time) return '（時刻未定）';
    return time.substring(0, 5);
  };

  const handlePrevMonth = () => {
    const newDate = new Date(currentYear, currentMonth - 1, 1);
    setCurrentDate(newDate);

    // 現在月（ローカル時間基準）かどうかを判定
    const localToday = getLocalToday();
    const isCurrentMonth = (newDate.getFullYear() === localToday.getFullYear() &&
      newDate.getMonth() === localToday.getMonth());

    if (isCurrentMonth) {
      setSelectedDate(localToday);  // 今月なら今日を選択
    } else {
      setSelectedDate(newDate);   // 他月なら1日を選択
    }
  };

  const handleNextMonth = () => {
    const newDate = new Date(currentYear, currentMonth + 1, 1);
    setCurrentDate(newDate);

    // 現在月（ローカル時間基準）かどうかを判定
    const localToday = getLocalToday();
    const isCurrentMonth = (newDate.getFullYear() === localToday.getFullYear() &&
      newDate.getMonth() === localToday.getMonth());

    if (isCurrentMonth) {
      setSelectedDate(localToday);  // 今月なら今日を選択
    } else {
      setSelectedDate(newDate);   // 他月なら1日を選択
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* 全体を1つの白い背景でまとめる */}
        <div className="bg-white rounded-lg shadow-lg p-8">
          <h1 className="text-3xl font-bold text-center text-gray-800 mb-4 drop-shadow-lg">
            福岡イベントカレンダー
          </h1>

          {/* 個人管理ツール用ナビゲーション (ヘッダー) */}
          <div className="flex justify-center gap-4 mb-6">
            <Link
              href="/sales"
              className="flex-1 max-w-[160px] text-center bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-semibold py-2.5 px-3 rounded-lg border border-emerald-200 text-sm shadow-sm transition-colors"
            >
              💰 売上管理 <span className="text-[10px] bg-emerald-200 text-emerald-900 px-1 py-0.2 rounded ml-0.5 font-normal">β</span>
            </Link>
            <Link
              href="/shift"
              className="flex-1 max-w-[160px] text-center bg-indigo-50 hover:bg-indigo-100 text-indigo-800 font-semibold py-2.5 px-3 rounded-lg border border-indigo-200 text-sm shadow-sm transition-colors"
            >
              🚕 シフト入力 <span className="text-[10px] bg-indigo-200 text-indigo-900 px-1 py-0.2 rounded ml-0.5 font-normal">β</span>
            </Link>
          </div>

          {/* 今日のイベントリンク */}
          <div className="text-center mb-8 border-b border-gray-200 pb-6">
            <Link
              href="/portal"
              className="inline-block bg-sky-500 hover:bg-sky-600 text-white font-medium px-6 py-3 rounded-lg shadow-2xl transition-colors duration-200 text-lg"
            >
              今日のイベントはこちら
            </Link>
          </div>

          {/* カレンダー */}
          <div className="mb-8">
            {/* ヘッダー */}
            <div className="flex items-center justify-between mb-6">
              <button
                onClick={handlePrevMonth}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded transition-colors text-gray-700 font-medium flex items-center gap-1"
              >
                <span>←</span>
                <span>{monthNames[(currentMonth + 11) % 12]}</span>
              </button>

              <h2 className="text-2xl font-semibold text-gray-800">
                {currentYear}年{monthNames[currentMonth]}
              </h2>

              <button
                onClick={handleNextMonth}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded transition-colors text-gray-700 font-medium flex items-center gap-1"
              >
                <span>{monthNames[(currentMonth + 1) % 12]}</span>
                <span>→</span>
              </button>
            </div>

            {/* 目標金額・売上サマリー */}
            {goalAmount > 0 && (
              <div className={`text-center mb-6 rounded-lg py-2.5 px-4 max-w-sm mx-auto shadow-sm border ${
                monthlySalesTotal >= goalAmount
                  ? 'bg-emerald-50 border-emerald-200'
                  : 'bg-orange-50 border-orange-200'
              }`}>
                {monthlySalesTotal >= goalAmount ? (
                  <>
                    <span className="text-sm font-semibold text-emerald-800">🎉 目標達成！</span>
                    <span className="text-lg font-black text-emerald-950 block mt-0.5">
                      おめでとうございます！
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-sm font-semibold text-orange-800">🎯 目標まであと：</span>
                    <span className="text-lg font-bold text-orange-950">
                      {remainingGoal.toLocaleString()} 円
                    </span>
                  </>
                )}
                <span className={`text-xs block mt-1 ${
                  monthlySalesTotal >= goalAmount ? 'text-emerald-700' : 'text-orange-700'
                }`}>
                  (目標: {goalAmount.toLocaleString()}円 / 売上: {monthlySalesTotal.toLocaleString()}円)
                </span>
              </div>
            )}

            {/* 曜日ヘッダー */}
            <div className="grid grid-cols-7 mb-2">
              {weekDays.map((day, index) => (
                <div key={day} className={`text-center font-medium py-2 ${index === 0 ? 'text-red-600' :
                    index === 6 ? 'text-blue-600' : 'text-gray-700'
                  }`}>
                  {day}
                </div>
              ))}
            </div>

            {/* カレンダーグリッド */}
            <div className="grid grid-cols-7 gap-1">
              {calendar.map((dayInfo, index) => {
                const dateString = transDay(dayInfo.date);
                const eventCount = dayInfo.isCurrentMonth ? (monthlyEvents[dateString] || 0) : 0;
                const isSelected = selectedDate.toDateString() === dayInfo.date.toDateString();
                const isToday = getLocalToday().toDateString() === dayInfo.date.toDateString();
                const isHoliday = HolidayJp.isHoliday(dayInfo.date);
                const weekDay = dayInfo.date.getDay();

                // デバッグログ（今日の日付のみ）
                if (isToday) {
                  console.log('今日のセル:', {
                    day: dayInfo.day,
                    dateString,
                    eventCount,
                    rawCount: monthlyEvents[dateString],
                    isCurrentMonth: dayInfo.isCurrentMonth,
                    isToday,
                    isSelected
                  });
                }

                // 文字色決定
                let textColor = 'text-gray-700';
                if (!dayInfo.isCurrentMonth) {
                  textColor = 'text-gray-300';
                } else if (isHoliday || weekDay === 0) {
                  textColor = 'text-red-600';
                } else if (weekDay === 6) {
                  textColor = 'text-blue-600';
                }

                return (
                  <button
                    key={index}
                    onClick={() => setSelectedDate(dayInfo.date)}
                    className={`
                      min-h-[80px] p-2 border border-gray-200 hover:bg-gray-50 
                      flex flex-col items-center justify-start rounded relative
                      ${isSelected ? 'ring-2 ring-blue-500 bg-blue-50' : ''}
                      ${isToday ? 'bg-yellow-50' : ''}
                    `}
                  >
                    <span className={`text-sm font-medium ${textColor} mb-1`}>
                      {dayInfo.day}
                    </span>

                    {/* 出勤シフト「🚕」表示 */}
                    {dayInfo.isCurrentMonth && shiftDates[dateString] && (
                      <span className="shift-badge-taxi" title="出勤日">
                        🚕
                      </span>
                    )}

                    {dayInfo.isCurrentMonth && eventCount > 0 && (
                      <span className={`${isMobile ? 'text-xs px-2 py-1' : 'text-sm px-3 py-1.5'} rounded font-medium ${eventCount >= 5 ? 'bg-red-100 text-red-800' :
                          eventCount >= 3 ? 'bg-orange-100 text-orange-800' :
                            'bg-green-100 text-green-800'
                        }`}>
                        {eventCount}件
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* イベント詳細 */}
          <div className="border-t border-gray-200 pt-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              {selectedDate.getFullYear()}年{selectedDate.getMonth() + 1}月{selectedDate.getDate()}日（{['日', '月', '火', '水', '木', '金', '土'][selectedDate.getDay()]}）のイベント
            </h2>

            {loading ? (
              <p className="text-gray-600">読み込み中...</p>
            ) : events.length > 0 ? (
              <div className="space-y-4">
                {events.map((event) => (
                  <div key={event.id} className="border-l-4 border-blue-500 pl-4 py-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-blue-600">
                        {formatTime(event.time)}
                      </span>
                      <span className="text-sm text-gray-500">
                        {event.venue}
                      </span>
                    </div>
                    <h3 className="text-lg font-medium text-gray-800">
                      {event.source_url ? (
                        <a
                          href={event.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-800 hover:text-black hover:underline transition-colors"
                        >
                          {event.title}
                        </a>
                      ) : (
                        event.title
                      )}
                    </h3>
                    {event.notes && !event.notes.includes('game_status:') && (
                      <p className="text-sm text-gray-600 mt-1">
                        {event.notes}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-gray-500 text-lg">
                  イベントはありません
                </p>
              </div>
            )}

            {/* 意見箱セクション */}
            <div
              className="mt-8 border-l-4 border-orange-400 p-6 rounded-lg"
              style={{ backgroundColor: '#fff5cd' }}
            >
              <div className="text-center">
                <h3 className="text-lg font-semibold text-gray-800 mb-2">ご意見・ご要望</h3>
                <p className="text-gray-600 mb-4">会場追加のご希望や情報漏れのご報告をお待ちしています</p>
                <a
                  href="https://docs.google.com/forms/d/e/1FAIpQLSfX2EtHu3hZ2FgMfUjSOx1YYQqt2BaB3BGniVPF5TMCtgLByw/viewform"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block text-white font-medium px-6 py-3 rounded-lg transition-colors duration-200"
                  style={{ backgroundColor: '#f39c12' }}
                  onMouseEnter={(e) => {
                    const target = e.target as HTMLElement;
                    target.style.backgroundColor = '#e67e22';
                  }}
                  onMouseLeave={(e) => {
                    const target = e.target as HTMLElement;
                    target.style.backgroundColor = '#f39c12';
                  }}
                >
                  ご意見・ご要望はこちら
                </a>
              </div>
            </div>

            {/* フッター */}
            <div className="mt-8 pt-6 border-t border-gray-100 text-center">
              <div className="space-y-2 text-sm text-gray-600">
                {/* PC版（1行） */}
                <p className="venue-list-desktop">福岡市内主要イベント会場の情報を自動収集・配信しています (Ver.3.4)</p>

                {/* スマホ版（2行） */}
                <div className="venue-list-mobile">
                  <p>福岡市内主要イベント会場の情報を</p>
                  <p>自動収集・配信しています (Ver.3.4)</p>
                </div>

                {/* PC版（横並び・リンク付き） */}
                <div className="venue-list-desktop space-y-1 mt-8">
                  <p className="font-medium">【対応会場】</p>
                  <p>
                    <a href="https://www.marinemesse.or.jp/messe/event/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">マリンメッセA館</a>・
                    <a href="https://www.marinemesse.or.jp/messe-b/event/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">マリンメッセB館</a>・
                    <a href="https://www.marinemesse.or.jp/kokusai/event/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">福岡国際センター</a>・
                    <a href="https://www.marinemesse.or.jp/congress/event/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">福岡国際会議場</a>
                  </p>
                  <p>
                    <a href="https://www.f-sunpalace.com/hall/#hallEvent" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">福岡サンパレス</a>・
                    <a href="https://www.softbankhawks.co.jp/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">みずほPayPayドーム</a>・
                    <a href="https://www.avispa.co.jp/game_practice" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">ベスト電器スタジアム</a>
                  </p>
                </div>

                {/* スマホ版（縦列・リンク付き） */}
                <div className="venue-list-mobile mt-8">
                  <p className="font-medium mb-2">【対応会場】</p>
                  <ul>
                    <li><a href="https://www.marinemesse.or.jp/messe/event/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">マリンメッセA館</a></li>
                    <li><a href="https://www.marinemesse.or.jp/messe-b/event/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">マリンメッセB館</a></li>
                    <li><a href="https://www.marinemesse.or.jp/kokusai/event/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">福岡国際センター</a></li>
                    <li><a href="https://www.marinemesse.or.jp/congress/event/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">福岡国際会議場</a></li>
                    <li><a href="https://www.f-sunpalace.com/hall/#hallEvent" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">福岡サンパレス</a></li>
                    <li><a href="https://www.softbankhawks.co.jp/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">みずほPayPayドーム</a></li>
                    <li><a href="https://www.avispa.co.jp/game_practice" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">ベスト電器スタジアム</a></li>
                  </ul>
                </div>

                {/* 個人管理ツール用ナビゲーション (フッター) */}
                <div className="mt-6 pt-4 border-t border-gray-100 flex justify-center gap-4 max-w-sm mx-auto">
                  <Link
                    href="/sales"
                    className="flex-1 text-center bg-gray-50 hover:bg-gray-100 text-gray-700 font-medium py-2 px-3 rounded-lg border border-gray-200 text-xs transition-colors shadow-sm"
                  >
                    💰 売上管理 β
                  </Link>
                  <Link
                    href="/shift"
                    className="flex-1 text-center bg-gray-50 hover:bg-gray-100 text-gray-700 font-medium py-2 px-3 rounded-lg border border-gray-200 text-xs transition-colors shadow-sm"
                  >
                    🚕 シフト入力 β
                  </Link>
                </div>

                <div className="mt-4 pt-3 border-t border-gray-100">
                  <p className="text-blue-600 font-medium">
                    <Link
                      href="/portal"
                      className="hover:underline inline-flex items-center gap-1"
                    >
                      📅 今日のイベント情報はこちら
                    </Link>
                  </p>
                </div>

                {/* 管理者ページリンク */}
                <div className="mt-2">
                  <a
                    href="/admin"
                    className="text-xs text-gray-400 hover:text-gray-600 hover:underline"
                  >
                    管理者ページ
                  </a>
                </div>

                {/* 著作権・製作者クレジット */}
                <div className="mt-6 pt-4 border-t border-gray-100 text-xs text-gray-400 space-y-1">
                  <p className="font-semibold text-gray-600">
                    Developed by YOSHITATSU NAKAHARA
                  </p>
                  <p>© 2026 All Rights Reserved.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}