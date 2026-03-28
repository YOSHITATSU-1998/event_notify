'use client';

import { useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import Link from 'next/link';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

export default function ManualEventPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  
  // フォームの状態
  const [eventType, setEventType] = useState('');
  const [title, setTitle] = useState('');
  const [venue, setVenue] = useState('');
  const [singleDate, setSingleDate] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [time, setTime] = useState('');
  const [notes, setNotes] = useState('');
  
  // UI状態
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  // 認証処理
  const handleLogin = () => {
    if (password === '19981006') {
      setIsAuthenticated(true);
      setAuthError('');
    } else {
      setAuthError('パスワードが間違っています');
    }
  };

  // フォームリセット
  const resetForm = () => {
    setEventType('');
    setTitle('');
    setVenue('');
    setSingleDate('');
    setStartDate('');
    setEndDate('');
    setTime('');
    setNotes('');
    setSuccessMessage('');
    setErrorMessage('');
  };

  // ハッシュ生成（簡易版）
  const generateHash = (date: string, title: string, venue: string) => {
    const str = `${date}|${title}|${venue}`;
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash).toString(16);
  };

  // Supabaseにイベントを投入
  const insertEventToDatabase = async (eventData: {
    date: string;
    time: string | null;
    title: string;
    venue: string;
    source_url: string | null;
    data_hash: string;
    event_type: string;
    notes: string | null;
    extracted_at: string;
  }) => {
    try {
      const { data, error } = await supabase
        .from('events')
        .insert([eventData])
        .select();

      if (error) {
        throw error;
      }

      return data;
    } catch (error) {
      console.error('Database insert error:', error);
      throw error;
    }
  };

  // 期間指定イベントの日付展開
  const expandDateRange = (startDate: string, endDate: string) => {
    const dates = [];
    const start = new Date(startDate);
    const end = new Date(endDate);
    
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      dates.push(new Date(d).toISOString().split('T')[0]);
    }
    
    return dates;
  };

  // イベント送信処理
  const handleSubmit = async () => {
    // バリデーション
    if (!eventType || !title || !venue) {
      setErrorMessage('必須項目（イベントタイプ、イベント名、会場名）を入力してください');
      return;
    }

    if (eventType === 'oneshot' && !singleDate) {
      setErrorMessage('開催日を選択してください');
      return;
    }

    if (eventType === 'recurring' && (!startDate || !endDate)) {
      setErrorMessage('開始日と終了日を選択してください');
      return;
    }

    if (eventType === 'recurring' && startDate > endDate) {
      setErrorMessage('開始日は終了日より前の日付にしてください');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const now = new Date().toISOString();
      const events = [];

      if (eventType === 'oneshot') {
        // 単発イベント
        const eventData = {
          date: singleDate,
          time: time || null,
          title: title,
          venue: venue,
          source_url: null,
          data_hash: generateHash(singleDate, title, venue),
          event_type: 'manual',
          notes: notes || null,
          extracted_at: now
        };
        events.push(eventData);
      } else {
        // 期間指定イベント（各日付に個別イベントとして展開）
        const dates = expandDateRange(startDate, endDate);
        for (const date of dates) {
          const eventData = {
            date: date,
            time: time || null,
            title: title,
            venue: venue,
            source_url: null,
            data_hash: generateHash(date, title, venue),
            event_type: 'manual',
            notes: notes || null,
            extracted_at: now
          };
          events.push(eventData);
        }
      }

      // データベースに投入
      for (const event of events) {
        await insertEventToDatabase(event);
      }

      // 成功メッセージ
      const dateDisplay = eventType === 'oneshot' 
        ? singleDate 
        : `${startDate} ～ ${endDate}`;
      const timeDisplay = time ? time : '時刻未定';
      
      setSuccessMessage(
        `✅ イベントが正常に追加されました！\n` +
        `${title} (${venue}) - ${dateDisplay} ${timeDisplay}\n` +
        `データベースに${events.length}件のイベントを投入しました。`
      );

      // フォームリセット
      resetForm();

    } catch (error: unknown) {
      console.error('Event submission error:', error);
      const errorMessage = error instanceof Error ? error.message : 'データベースへの投入に失敗';
      setErrorMessage(`エラーが発生しました: ${errorMessage}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 認証前の画面
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md w-full">
          <div className="text-center mb-6">
            <Link href="/admin" className="text-blue-600 hover:underline text-sm">
              ← 管理者ページに戻る
            </Link>
          </div>
          
          <h1 className="text-2xl font-bold text-center text-gray-800 mb-6">
            手動イベント追加
          </h1>
          
          <p className="text-center text-gray-600 mb-6">
            イベント情報を手動で追加するには認証が必要です
          </p>
          
          <div className="space-y-4">
            <input
              type="password"
              placeholder="パスワードを入力"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
            />
            <button
              onClick={handleLogin}
              className="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
            >
              ログイン
            </button>
            {authError && (
              <div className="text-red-600 text-center text-sm">{authError}</div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // 今日の日付を取得（最小値用）
  const today = new Date().toISOString().split('T')[0];

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-lg p-8">
          {/* ヘッダー */}
          <div className="text-center mb-8">
            <Link href="/admin" className="text-blue-600 hover:underline text-sm">
              ← 管理者ページに戻る
            </Link>
            <h1 className="text-3xl font-bold text-gray-800 mt-4 mb-2">
              手動イベント追加
            </h1>
            <p className="text-gray-600">
              イベント情報を直接データベースに追加します
            </p>
          </div>

          {/* 成功・エラーメッセージ */}
          {successMessage && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
              <div className="text-green-800 whitespace-pre-line">{successMessage}</div>
            </div>
          )}

          {errorMessage && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <div className="text-red-800">{errorMessage}</div>
            </div>
          )}

          {/* フォーム */}
          <div className="space-y-6">
            {/* イベントタイプ */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                イベントタイプ <span className="text-red-500">*</span>
              </label>
              <select
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
              >
                <option value="">選択してください</option>
                <option value="oneshot">単発イベント（1日のみ）</option>
                <option value="recurring">期間指定イベント（複数日）</option>
              </select>
            </div>

            {/* イベント名 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                イベント名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="例: 放生屋"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
              />
            </div>

            {/* 会場名 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                会場名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={venue}
                onChange={(e) => setVenue(e.target.value)}
                placeholder="例: 箱崎宮"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
              />
            </div>

            {/* 単発イベント用の日付 */}
            {eventType === 'oneshot' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  開催日 <span className="text-red-500">*</span>
                </label>
                <input
                  type="date"
                  value={singleDate}
                  onChange={(e) => setSingleDate(e.target.value)}
                  min={today}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                />
              </div>
            )}

            {/* 期間指定イベント用の日付 */}
            {eventType === 'recurring' && (
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    開始日 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    min={today}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    終了日 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    min={startDate || today}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  />
                </div>
              </div>
            )}

            {/* 時刻 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                時刻（任意）
              </label>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
              />
              <p className="text-sm text-gray-500 mt-1">
                空欄の場合「時刻未定」として表示されます
              </p>
            </div>

            {/* 備考 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                備考（任意）
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="追加情報があれば記入してください"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
              />
            </div>

            {/* 送信ボタン */}
            <div className="pt-4">
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className={`w-full py-3 px-4 rounded-lg font-medium transition-colors ${
                  isSubmitting
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-green-600 hover:bg-green-700'
                } text-white`}
              >
                {isSubmitting ? '追加中...' : 'イベント追加'}
              </button>
            </div>
          </div>

          {/* ログアウト */}
          <div className="text-center pt-6 mt-8 border-t border-gray-200">
            <button
              onClick={() => setIsAuthenticated(false)}
              className="text-gray-500 hover:text-gray-700 text-sm"
            >
              ログアウト
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}