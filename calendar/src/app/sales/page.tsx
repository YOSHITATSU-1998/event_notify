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

export default function SalesPage() {
  const [mounted, setMounted] = useState(false);
  const [currentDate, setCurrentDate] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  
  const [salesData, setSalesData] = useState<Record<string, number | null>>({});
  const [goalAmount, setGoalAmount] = useState<number>(0);
  const [goalInput, setGoalInput] = useState<string>('');
  const [shiftData, setShiftData] = useState<Record<string, boolean>>({}); // シフトデータの保持

  // モーダル用State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeDateStr, setActiveDateStr] = useState<string | null>(null);
  const [modalInputValue, setModalInputValue] = useState('');
  const [isConfirming, setIsConfirming] = useState(false);
  const [isSuccessShown, setIsSuccessShown] = useState(false);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth(); // 0-11
  const monthKey = `${year}-${(month + 1).toString().padStart(2, '0')}`; // YYYY-MM
  const goalKey = `goal-${monthKey}`;

  // ハイドレーション不一致を防ぐため、マウント完了後にLocalStorageを読み込む
  useEffect(() => {
    setMounted(true);
    
    // 売上データ、シフトデータ、目標金額のロード
    const sales: Record<string, number | null> = {};
    const shifts: Record<string, boolean> = {};
    let goalVal = 0;

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key) {
        if (/^\d{4}-\d{2}-\d{2}$/.test(key)) {
          try {
            const item = JSON.parse(localStorage.getItem(key) || '{}');
            if (item) {
              if (typeof item.sales !== 'undefined') {
                sales[key] = item.sales;
              }
              if (item.is_shift === true) {
                shifts[key] = true;
              }
            }
          } catch (e) {
            console.error('Error parsing localStorage key:', key, e);
          }
        }
      }
    }

    const storedGoal = localStorage.getItem(`goal-${monthKey}`);
    if (storedGoal) {
      goalVal = parseInt(storedGoal, 10) || 0;
    }

    setSalesData(sales);
    setShiftData(shifts);
    setGoalAmount(goalVal);
    setGoalInput(goalVal > 0 ? goalVal.toString() : '');
  }, [monthKey]);

  if (!mounted) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="text-gray-500 text-lg">読み込み中...</div>
      </div>
    );
  }

  // 前月・次月切り替え
  const handlePrevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  // その月の日付一覧を生成 (時刻は12:00:00に固定して安全性を高める)
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

  // 売上合計値の計算
  const totalSales = days.reduce((sum, dateObj) => {
    const dateStr = transDay(dateObj);
    const val = salesData[dateStr];
    return sum + (val || 0);
  }, 0);

  // 残り目標金額の計算
  const remainingAmount = Math.max(0, goalAmount - totalSales);

  // 目標金額の更新
  const handleSaveGoal = (valStr: string) => {
    const val = parseInt(valStr, 10) || 0;
    setGoalAmount(val);
    if (val > 0) {
      localStorage.setItem(goalKey, val.toString());
    } else {
      localStorage.removeItem(goalKey);
    }
  };

  // モーダルを開く
  const openInputModal = (dateStr: string) => {
    const existingVal = salesData[dateStr];
    setActiveDateStr(dateStr);
    setModalInputValue(existingVal !== null && existingVal !== undefined ? existingVal.toString() : '');
    setIsConfirming(false);
    setIsSuccessShown(false);
    setIsModalOpen(true);
  };

  // 金額入力確定 (確認画面へ)
  const handleConfirm = () => {
    setIsConfirming(true);
  };

  // 登録処理 (Y)
  const handleRegister = () => {
    if (!activeDateStr) return;

    const val = modalInputValue === '' ? null : parseInt(modalInputValue, 10) || 0;

    // state更新
    setSalesData((prev) => ({ ...prev, [activeDateStr]: val }));

    // LocalStorage更新
    try {
      const existing = localStorage.getItem(activeDateStr);
      let dayObj: DayData = { is_shift: false, sales: null, memo: '' };
      if (existing) {
        dayObj = JSON.parse(existing);
      }
      dayObj.sales = val;
      localStorage.setItem(activeDateStr, JSON.stringify(dayObj));
    } catch (e) {
      console.error('Failed to save sales to localStorage:', e);
    }

    setIsSuccessShown(true);

    // 1.2秒後に閉じる
    setTimeout(() => {
      setIsModalOpen(false);
      setActiveDateStr(null);
      setIsConfirming(false);
      setIsSuccessShown(false);
    }, 1200);
  };

  // キャンセル・戻る処理 (N)
  const handleCancel = () => {
    if (isConfirming) {
      setIsConfirming(false);
    } else {
      setIsModalOpen(false);
      setActiveDateStr(null);
    }
  };

  const weekDays = ['日', '月', '火', '水', '木', '金', '土'];

  return (
    <div className="min-h-screen bg-gray-50 py-6">
      <div className="max-w-md mx-auto px-4">
        <div className="bg-white rounded-lg shadow-md p-6">
          {/* ヘッダー・戻るボタン */}
          <div className="flex items-center justify-between mb-6">
            <Link
              href="/"
              className="text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 text-sm bg-blue-50 px-3 py-2 rounded-lg"
            >
              <span>←</span>
              <span>カレンダー</span>
            </Link>
            <h1 className="text-xl font-bold text-gray-800">売上管理 <span className="text-xs bg-orange-100 text-orange-800 px-1.5 py-0.5 rounded ml-1 font-normal">β</span></h1>
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

          {/* 目標設定エリア */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              🎯 今月の目標金額 (円)
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 font-semibold">¥</span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={goalInput}
                  onChange={(e) => {
                    const val = e.target.value.replace(/[^0-9]/g, '');
                    setGoalInput(val);
                  }}
                  onBlur={() => handleSaveGoal(goalInput)}
                  onFocus={(e) => e.target.select()}
                  placeholder="未設定"
                  className="w-full bg-white border border-gray-300 rounded-lg pl-8 pr-3 py-2 text-base text-gray-900 font-bold focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  style={{ fontSize: '16px' }} // iOSの自動ズーム防止
                />
              </div>
            </div>
          </div>

          {/* 売上状況サマリー */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
              <p className="text-xs text-green-800 font-medium">合計売上</p>
              <p className="text-xl font-bold text-green-900 mt-1">
                {totalSales.toLocaleString()} <span className="text-xs font-normal">円</span>
              </p>
            </div>
            {goalAmount > 0 && totalSales >= goalAmount ? (
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-center flex flex-col justify-center items-center">
                <p className="text-xs text-emerald-800 font-medium">目標状況</p>
                <p className="text-base font-bold text-emerald-950 mt-1">
                  目標達成！🎉
                </p>
              </div>
            ) : (
              <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-center">
                <p className="text-xs text-orange-800 font-medium">目標まであと</p>
                <p className="text-xl font-bold text-orange-900 mt-1">
                  {goalAmount > 0 ? `${remainingAmount.toLocaleString()} 円` : '目標未設定'}
                </p>
              </div>
            )}
          </div>

          {/* 注意書き */}
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3.5 mb-6 text-xs text-yellow-800 leading-relaxed">
            ⚠️ 売上データはご使用のスマホにのみ保存されます。履歴削除などでデータが消えるのを防ぐため、必ずこちらの{' '}
            <Link href="/help" className="text-blue-700 underline font-bold hover:text-blue-900">
              【データ保存の注意点】
            </Link>{' '}
            をご確認ください。
          </div>

          {/* 日付別売上入力リスト */}
          <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1 border-t border-gray-100 pt-4">
            {days.map((dateObj) => {
              const dateStr = transDay(dateObj);
              const value = salesData[dateStr];
              const inputValue = (value === null || value === undefined) ? '' : value.toString();
              const dayOfWeek = dateObj.getDay();
              const isHoliday = HolidayJp.isHoliday(dateObj);

              // 曜日の色分け
              let dayColorClass = 'text-gray-700';
              if (isHoliday || dayOfWeek === 0) {
                dayColorClass = 'text-red-600 font-semibold';
              } else if (dayOfWeek === 6) {
                dayColorClass = 'text-blue-600 font-semibold';
              }

              let holidayName = '';
              if (isHoliday) {
                const holidays = HolidayJp.between(dateObj, dateObj);
                if (holidays.length > 0) {
                  holidayName = holidays[0].name;
                }
              }

              return (
                <div
                  key={dateStr}
                  className="flex items-center justify-between p-3 border border-gray-100 rounded-lg bg-gray-50/30"
                  style={{ minHeight: '52px' }}
                >
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-gray-900 flex items-center gap-1">
                      <span>{dateObj.getDate()}日</span>
                      <span className={`text-xs ${dayColorClass}`}>
                        （{weekDays[dayOfWeek]}）
                      </span>
                      {shiftData[dateStr] && (
                        <span className="text-sm ml-0.5" title="出勤日">🚕</span>
                      )}
                    </span>
                    {holidayName && (
                      <span className="text-[10px] text-red-500 font-normal mt-0.5">
                        {holidayName}
                      </span>
                    )}
                  </div>

                  <button
                    onClick={() => openInputModal(dateStr)}
                    className={`px-4 py-2 rounded-xl text-sm font-bold min-w-32 transition-all active:scale-[0.96] shadow-xs text-right border ${
                      value !== null && value !== undefined
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100'
                        : 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100 text-center'
                    }`}
                    style={{ minHeight: '44px' }}
                  >
                    {value !== null && value !== undefined
                      ? `¥ ${value.toLocaleString()}`
                      : '入力する'}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 入力用モーダルポップアップ */}
      {isModalOpen && activeDateStr && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-xs w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            {isSuccessShown ? (
              // 登録完了表示
              <div className="text-center py-6">
                <span className="text-4xl block mb-2">✅</span>
                <h3 className="text-lg font-bold text-gray-800">
                  {parseInt(activeDateStr.split('-')[2], 10)}日の売上を
                </h3>
                <p className="text-base text-gray-600 font-medium">登録しました！</p>
              </div>
            ) : isConfirming ? (
              // 確認画面 (Y/N)
              <div>
                <h3 className="text-base font-bold text-gray-800 text-center mb-6">
                  {parseInt(activeDateStr.split('-')[2], 10)}日の売上を登録しますか？
                </h3>
                
                <div className="bg-gray-50 rounded-xl p-4 mb-6 border border-gray-100 text-center">
                  <p className="text-xs text-gray-500 font-medium">登録金額</p>
                  <p className="text-2xl font-black text-gray-900 mt-1">
                    {modalInputValue === '' ? '未設定 (0)' : parseInt(modalInputValue, 10).toLocaleString()} <span className="text-sm font-normal">円</span>
                  </p>
                </div>

                <div className="flex gap-4">
                  <button
                    onClick={handleCancel}
                    className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold py-3 px-4 rounded-xl text-center active:scale-[0.98] transition-all text-sm"
                  >
                    戻る
                  </button>
                  <button
                    onClick={handleRegister}
                    className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-3 px-4 rounded-xl text-center shadow-md shadow-emerald-200 active:scale-[0.98] transition-all text-sm"
                  >
                    登録する
                  </button>
                </div>
              </div>
            ) : (
              // 入力画面
              <div>
                <h3 className="text-lg font-bold text-gray-800 text-center mb-4">
                  {parseInt(activeDateStr.split('-')[2], 10)}日の売り上げを入力
                </h3>

                <div className="relative mb-6">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 font-bold text-lg">¥</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    value={modalInputValue}
                    onChange={(e) => {
                      const val = e.target.value.replace(/[^0-9]/g, '');
                      setModalInputValue(val);
                    }}
                    placeholder="金額を入力"
                    autoFocus
                    className="w-full bg-gray-50 border border-gray-300 rounded-xl pl-9 pr-4 py-3 text-lg font-bold text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-right"
                    style={{ fontSize: '16px' }} // iOSズーム防止
                    onFocus={(e) => e.target.select()}
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={handleCancel}
                    className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 px-4 rounded-xl text-sm transition-all"
                  >
                    キャンセル
                  </button>
                  <button
                    onClick={handleConfirm}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-xl text-sm transition-all shadow-sm active:scale-[0.98]"
                  >
                    入力確定
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
