'use client';

import { useState, useEffect } from 'react';
import {
  SURVEY_FORM_URL,
  SURVEY_END_DATE,
  SURVEY_SESSION_KEY,
  SURVEY_NEVER_KEY,
} from '@/lib/constants';

/**
 * SurveyPopup - アンケート誘導ポップアップ（Ver.4.4）
 * 表示条件：
 *   ① 現在日時が SURVEY_END_DATE 以前
 *   ② sessionStorage に SESSION_KEY が存在しない
 *   ③ localStorage に NEVER_KEY が存在しない
 * ポータルページマウントから3秒後に表示。
 */
export default function SurveyPopup() {
  const [visible, setVisible] = useState(false);
  const [neverShow, setNeverShow] = useState(false);

  useEffect(() => {
    const now = new Date();
    const expired = now > SURVEY_END_DATE;
    const sessionSeen = sessionStorage.getItem(SURVEY_SESSION_KEY);
    const localNever = localStorage.getItem(SURVEY_NEVER_KEY);

    if (!expired && !sessionSeen && !localNever) {
      const timer = setTimeout(() => setVisible(true), 3000);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleClose = () => {
    sessionStorage.setItem(SURVEY_SESSION_KEY, 'true');
    if (neverShow) {
      localStorage.setItem(SURVEY_NEVER_KEY, 'true');
    }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <>
      {/* オーバーレイ */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={handleClose}
      />

      {/* ポップアップ本体 */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-[90%] max-w-sm bg-white rounded-2xl shadow-2xl p-5 border border-blue-100">

        {/* ×ボタン */}
        <button
          onClick={handleClose}
          className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 text-xl font-bold leading-none"
          aria-label="閉じる"
        >
          ×
        </button>

        {/* アイコン＋タイトル */}
        <div className="text-center mb-4">
          <p className="text-base font-bold text-gray-800 leading-snug">
            5問・タップのみ・30秒で終わります🙏
          </p>
          <p className="text-sm text-gray-600 mt-1">
            使い心地を教えてください
          </p>
        </div>

        {/* アンケートボタン */}
        <a
          href={SURVEY_FORM_URL}
          target="_blank"
          rel="noopener noreferrer"
          onClick={handleClose}
          className="block w-full text-center bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm py-3 rounded-xl transition-colors shadow-sm mb-4"
        >
          📋 アンケートに答える
        </a>

        {/* 今後表示しないチェック */}
        <label className="flex items-center gap-2 justify-center cursor-pointer text-xs text-gray-400">
          <input
            type="checkbox"
            checked={neverShow}
            onChange={(e) => setNeverShow(e.target.checked)}
            className="w-3.5 h-3.5 accent-blue-500"
          />
          今後表示しない
        </label>
      </div>
    </>
  );
}
