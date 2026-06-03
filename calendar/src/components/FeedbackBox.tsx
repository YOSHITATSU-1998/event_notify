import { FEEDBACK_FORM_URL } from '@/lib/constants';

/**
 * FeedbackBox - ご意見・ご要望セクション（カレンダー・ポータル共通）
 */
export default function FeedbackBox() {
  return (
    <div className="bg-amber-50 border border-amber-100 p-4 rounded-lg text-center mb-6 shadow-sm">
      <h3 className="font-bold text-amber-800 text-sm mb-1">ご意見・ご要望</h3>
      <p className="text-xs text-amber-700 mb-3">
        会場追加のご希望や情報漏れのご報告をお待ちしています
      </p>
      <a
        href={FEEDBACK_FORM_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-block bg-amber-500 hover:bg-amber-600 text-white font-bold text-sm py-2 px-6 rounded transition-colors shadow-sm"
      >
        ご意見・ご要望はこちら
      </a>
    </div>
  );
}
