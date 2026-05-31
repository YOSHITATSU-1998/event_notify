'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import HolidayJp from '@holiday-jp/holiday_jp';

type DayData = {
  is_shift: boolean;
  sales: number | null;
  memo: string;
};

// 日付オブジェクトから YYYY-MM-DD 文字列をローカル時間基準で取得する関数（タイムゾーンのズレ防止）
const transDay = (date: Date) => {
  const y = date.getFullYear();
  const m = (date.getMonth() + 1).toString().padStart(2, '0');
  const d = date.getDate().toString().padStart(2, '0');
  return `${y}-${m}-${d}`;
};

export default function ShiftPage() {
  const [mounted, setMounted] = useState(false);
  const [currentDate, setCurrentDate] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const [shiftData, setShiftData] = useState<Record<string, boolean>>({});      // 確定値
  const [tempShiftData, setTempShiftData] = useState<Record<string, boolean>>({});  // 下書き値
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSuccessShown, setIsSuccessShown] = useState(false);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth(); // 0-11

  // ハイドレーション不一致を防ぐため、マウント完了後にLocalStorageを読み込む
  useEffect(() => {
    setMounted(true);
    const data: Record<string, boolean> = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && /^\d{4}-\d{2}-\d{2}$/.test(key)) {
        try {
          const item = JSON.parse(localStorage.getItem(key) || '{}');
          if (item && typeof item.is_shift === 'boolean') {
            data[key] = item.is_shift;
          }
        } catch (e) {
          console.error('Error parsing localStorage key:', key, e);
        }
      }
    }
    setShiftData(data);
    setTempShiftData(data);
  }, []);

  if (!mounted) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="text-gray-500 text-lg">読み込み中...</div>
      </div>
    );
  }

  // 変更があるかどうか判定
  const hasChanges = () => {
    return JSON.stringify(shiftData) !== JSON.stringify(tempShiftData);
  };

  // カレンダーに戻る前の警告確認
  const handleBackConfirm = (e: React.MouseEvent) => {
    if (hasChanges()) {
      if (!window.confirm('変更されたシフトが登録されていません。登録せずにカレンダーに戻りますか？')) {
        e.preventDefault();
      }
    }
  };

  // 前月・次月切り替え (未登録の警告付き)
  const handlePrevMonth = () => {
    if (hasChanges()) {
      if (!window.confirm('変更されたシフトが登録されていません。登録せずに前月に切り替えますか？')) {
        return;
      }
    }
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const handleNextMonth = () => {
    if (hasChanges()) {
      if (!window.confirm('変更されたシフトが登録されていません。登録せずに翌月に切り替えますか？')) {
        return;
      }
    }
    setCurrentDate(new Date(year, month + 1, 1));
  };

  // その月の日付一覧を生成 (時刻は12:00:00に固定)
  const getDaysInMonth = () => {
    const days = [];
    const date = new Date(year, month, 1, 12, 0, 0);
    while (date.getMonth() === month) {
      days.push(new Date(date));
      date.setDate(date.getDate() + 1);
    }
    return days;
  };

  const days = getDaysInMonth();

  // シフト（下書き）のトグル処理
  const handleToggleShift = (dateStr: string) => {
    setTempShiftData((prev) => ({
      ...prev,
      [dateStr]: !prev[dateStr]
    }));
  };

  // 登録確定処理 (Y)
  const handleRegister = () => {
    // 表示されている月の日付をすべてLocalStorageに登録
    days.forEach((dateObj) => {
      const dateStr = transDay(dateObj);
      const newIsShift = tempShiftData[dateStr] === true;

      try {
        const existing = localStorage.getItem(dateStr);
        let dayObj: DayData = { is_shift: false, sales: null, memo: '' };
        if (existing) {
          dayObj = JSON.parse(existing);
        }
        dayObj.is_shift = newIsShift;
        localStorage.setItem(dateStr, JSON.stringify(dayObj));
      } catch (e) {
        console.error('Failed to save to localStorage:', e);
      }
    });

    // 確定値を下書き値と同期
    setShiftData({ ...tempShiftData });
    setIsSuccessShown(true);

    // 1.2秒後にモーダルを閉じる
    setTimeout(() => {
      setIsModalOpen(false);
      setIsSuccessShown(false);
    }, 1200);
  };

  // 今月の出勤日数の合計（下書き値基準）
  const activeShiftCount = days.filter((d) => {
    const dateStr = transDay(d);
    return tempShiftData[dateStr] === true;
  }).length;

  const weekDays = ['日', '月', '火', '水', '木', '金', '土'];

  return (
    <div className="min-h-screen bg-gray-50 py-6">
      <div className="max-w-md mx-auto px-4">
        <div className="bg-white rounded-lg shadow-md p-6">
          {/* ヘッダー・戻るボタン */}
          <div className="flex items-center justify-between mb-6">
            <Link
              href="/"
              onClick={handleBackConfirm}
              className="text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 text-sm bg-blue-50 px-3 py-2 rounded-lg"
            >
              <span>←</span>
              <span>カレンダー</span>
            </Link>
            <h1 className="text-xl font-bold text-gray-800">
              シフト入力 <span className="text-xs bg-orange-100 text-orange-800 px-1.5 py-0.5 rounded ml-1 font-normal">β</span>
            </h1>
            <div className="w-16"></div>
          </div>

          {/* 月選択ナビゲーション */}
          <div className="flex items-center justify-between mb-6 bg-gray-50 p-2 rounded-lg">
            <button
              onClick={handlePrevMonth}
              className="px-3 py-2 bg-white hover:bg-gray-100 rounded shadow-sm text-sm text-gray-700 font-medium transition-colors"
            >
              ← {month === 0 ? 12 : month}月
            </button>
            <span className="text-lg font-semibold text-gray-800">
              {year}年 {month + 1}月
            </span>
            <button
              onClick={handleNextMonth}
              className="px-3 py-2 bg-white hover:bg-gray-100 rounded shadow-sm text-sm text-gray-700 font-medium transition-colors"
            >
              {month === 11 ? 1 : month + 2}月 →
            </button>
          </div>

          {/* 出勤日数サマリー */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-center">
            <p className="text-sm text-blue-800 font-medium">
              今月の出勤日数 (予定)
            </p>
            <p className="text-3xl font-bold text-blue-900 mt-1">
              {activeShiftCount} <span className="text-lg font-normal">日</span>
            </p>
          </div>

          {/* 注意書き */}
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3.5 mb-6 text-xs text-yellow-800 leading-relaxed">
            ⚠️ シフト情報はご使用のスマホにのみ保存されます。履歴削除などでデータが消えるのを防ぐため、必ずこちらの{' '}
            <Link href="/help" className="text-blue-700 underline font-bold hover:text-blue-900">
              【データ保存の注意点】
            </Link>{' '}
            をご確認ください。
          </div>

          {/* 日付リスト */}
          <div className="space-y-2 max-h-[50vh] overflow-y-auto pr-1 border-t border-gray-100 pt-4">
            {days.map((dateObj) => {
              const dateStr = transDay(dateObj);
              const isChecked = tempShiftData[dateStr] === true;
              const dayOfWeek = dateObj.getDay();
              const isHoliday = HolidayJp.isHoliday(dateObj);

              // 曜日の色分け
              let dayColorClass = 'text-gray-700';
              if (isHoliday || dayOfWeek === 0) {
                dayColorClass = 'text-red-600 font-semibold';
              } else if (dayOfWeek === 6) {
                dayColorClass = 'text-blue-600 font-semibold';
              }

              // 祝日名
              let holidayName = '';
              if (isHoliday) {
                const holidays = HolidayJp.between(dateObj, dateObj);
                if (holidays.length > 0) {
                  holidayName = holidays[0].name;
                }
              }

              return (
                <label
                  key={dateStr}
                  className={`flex items-center justify-between p-3.5 border rounded-lg cursor-pointer transition-all active:scale-[0.98] ${
                    isChecked
                      ? 'bg-blue-50/50 border-blue-300 shadow-sm'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                  style={{ minHeight: '52px' }}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => handleToggleShift(dateStr)}
                      className="w-6 h-6 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                    <span className="text-base text-gray-900 font-medium">
                      {dateObj.getDate()}日
                      <span className={`ml-1 text-sm ${dayColorClass}`}>
                        （{weekDays[dayOfWeek]}）
                      </span>
                      {holidayName && (
                        <span className="ml-2 text-xs text-red-500 font-normal">
                          {holidayName}
                        </span>
                      )}
                    </span>
                  </div>
                  {isChecked && (
                    <span className="text-xl" title="出勤">🚕</span>
                  )}
                </label>
              );
            })}
          </div>

          {/* 登録するボタン */}
          <div className="mt-6 border-t border-gray-100 pt-6">
            <button
              onClick={() => setIsModalOpen(true)}
              disabled={!hasChanges()}
              className={`w-full font-bold py-3.5 px-4 rounded-xl text-base transition-all shadow-md text-center flex items-center justify-center gap-1.5 ${
                hasChanges()
                  ? 'bg-blue-600 hover:bg-blue-700 text-white active:scale-[0.98] shadow-blue-100'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200 shadow-none'
              }`}
              style={{ minHeight: '48px' }}
            >
              <span>🚕</span>
              <span>シフトを登録する</span>
            </button>
          </div>
        </div>
      </div>

      {/* 登録確認モーダル */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-xs w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            {isSuccessShown ? (
              // 登録成功表示
              <div className="text-center py-6">
                <span className="text-4xl block mb-2">✅</span>
                <h3 className="text-lg font-bold text-gray-800">
                  {year}年{month + 1}月のシフトを
                </h3>
                <p className="text-base text-gray-600 font-medium">登録しました！</p>
              </div>
            ) : (
              // 確認画面
              <div>
                <h3 className="text-base font-bold text-gray-800 text-center mb-6">
                  {year}年{month + 1}月のシフトを登録しますか？
                </h3>
                
                <div className="flex gap-4">
                  <button
                    onClick={() => setIsModalOpen(false)} // 戻る
                    className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold py-3 px-4 rounded-xl text-center active:scale-[0.98] transition-all text-sm"
                  >
                    戻る
                  </button>
                  <button
                    onClick={handleRegister} // 登録
                    className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-3 px-4 rounded-xl text-center shadow-md shadow-emerald-200 active:scale-[0.98] transition-all text-sm"
                  >
                    登録する
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
