'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';
import Link from 'next/link';
import { Notice } from '@/types';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

export default function MessagesPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [notices, setNotices] = useState<Notice[]>([]);
  const [loading, setLoading] = useState(false);

  // フォーム入力
  const [title, setTitle] = useState('🔔 運営からのお知らせ');
  const [body, setBody] = useState('');
  const [startAt, setStartAt] = useState('');
  const [endAt, setEndAt] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  // 認証
  const handleLogin = async () => {
    try {
      const res = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (data.success) {
        setIsAuthenticated(true);
      } else {
        alert(data.message || 'パスワードが正しくありません');
      }
    } catch {
      alert('認証サーバーとの通信に失敗しました');
    }
  };

  // お知らせ一覧取得
  const fetchNotices = async () => {
    setLoading(true);
    const { data, error } = await supabase
      .from('notices')
      .select('*')
      .order('created_at', { ascending: false });

    if (!error && data) setNotices(data);
    setLoading(false);
  };

  useEffect(() => {
    if (isAuthenticated) fetchNotices();
  }, [isAuthenticated]);

  // お知らせ作成
  const handleCreate = async () => {
    if (!title || !body || !startAt || !endAt) {
      setMessage('❌ 全項目を入力してください');
      return;
    }
    if (startAt > endAt) {
      setMessage('❌ 終了日は開始日以降にしてください');
      return;
    }

    setSubmitting(true);
    const { error } = await supabase.from('notices').insert([
      { title, body, start_at: startAt, end_at: endAt, is_active: isActive },
    ]);

    if (error) {
      setMessage(`❌ 作成失敗: ${error.message}`);
    } else {
      setMessage('✅ お知らせを作成しました');
      setBody('');
      setStartAt('');
      setEndAt('');
      setIsActive(true);
      fetchNotices();
    }
    setSubmitting(false);
    setTimeout(() => setMessage(''), 4000);
  };

  // お知らせ削除
  const handleDelete = async (id: number) => {
    if (!confirm('このお知らせを削除しますか？')) return;
    const { error } = await supabase.from('notices').delete().eq('id', id);
    if (error) {
      alert(`削除失敗: ${error.message}`);
    } else {
      fetchNotices();
    }
  };

  // 認証前
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md w-full">
          <h1 className="text-2xl font-bold text-center text-gray-800 mb-6">
            管理者ページ
          </h1>
          <div className="space-y-4">
            <input
              type="password"
              placeholder="パスワードを入力"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
            />
            <button
              onClick={handleLogin}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
            >
              ログイン
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-lg p-8">

          {/* ヘッダー */}
          <div className="flex justify-between items-center mb-8">
            <h1 className="text-2xl font-bold text-gray-800">
              📢 お知らせ管理
            </h1>
            <div className="flex gap-3">
              <Link
                href="/admin"
                className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm transition-colors"
              >
                管理者TOPへ
              </Link>
              <button
                onClick={() => setIsAuthenticated(false)}
                className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-4 py-2 rounded-lg text-sm transition-colors"
              >
                ログアウト
              </button>
            </div>
          </div>

          {/* 作成フォーム */}
          <div className="bg-amber-50 border border-amber-200 p-6 rounded-lg mb-8">
            <h2 className="text-lg font-bold text-amber-800 mb-4">
              ＋ 新規お知らせを作成
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  見出し
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-400"
                  placeholder="🔔 運営からのお知らせ"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  本文
                </label>
                <textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-400"
                  placeholder="ユーザーに伝える内容を入力..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    表示開始日
                  </label>
                  <input
                    type="date"
                    value={startAt}
                    onChange={(e) => setStartAt(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    表示終了日
                  </label>
                  <input
                    type="date"
                    value={endAt}
                    onChange={(e) => setEndAt(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-400"
                  />
                </div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="w-4 h-4 accent-amber-500"
                />
                <span className="text-sm font-medium text-gray-700">
                  有効にする（表示期間内に自動表示）
                </span>
              </label>

              {message && (
                <p className="text-sm font-medium text-center py-2">{message}</p>
              )}

              <button
                onClick={handleCreate}
                disabled={submitting}
                className="w-full bg-amber-500 hover:bg-amber-600 disabled:bg-gray-300 text-white font-bold py-3 rounded-lg transition-colors"
              >
                {submitting ? '作成中...' : '作成する'}
              </button>
            </div>
          </div>

          {/* お知らせ一覧 */}
          <div>
            <h2 className="text-lg font-bold text-gray-800 mb-4">
              📋 お知らせ一覧
            </h2>
            {loading ? (
              <p className="text-center text-gray-500 py-8">読み込み中...</p>
            ) : notices.length === 0 ? (
              <p className="text-center text-gray-400 py-8">お知らせはありません</p>
            ) : (
              <div className="space-y-3">
                {notices.map((notice) => (
                  <div
                    key={notice.id}
                    className={`border rounded-lg p-4 ${
                      notice.is_active ? 'border-amber-300 bg-amber-50' : 'border-gray-200 bg-gray-50'
                    }`}
                  >
                    <div className="flex justify-between items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-bold text-sm text-gray-800">
                            {notice.title}
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            notice.is_active
                              ? 'bg-green-100 text-green-700'
                              : 'bg-gray-200 text-gray-500'
                          }`}>
                            {notice.is_active ? '有効' : '無効'}
                          </span>
                        </div>
                        <p className="text-xs text-gray-600 mb-2 whitespace-pre-wrap">
                          {notice.body}
                        </p>
                        <p className="text-xs text-gray-400">
                          📅 {notice.start_at} 〜 {notice.end_at}
                          　作成: {new Date(notice.created_at).toLocaleDateString('ja-JP')}
                        </p>
                      </div>
                      <button
                        onClick={() => handleDelete(notice.id)}
                        className="flex-shrink-0 bg-red-500 hover:bg-red-600 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
                      >
                        削除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
