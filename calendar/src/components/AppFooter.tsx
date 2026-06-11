import Link from 'next/link';
import { APP_VERSION, APP_DESCRIPTION } from '@/lib/constants';

/**
 * AppFooter - カレンダー・ポータル共通フッター（案A：シンプル統一型）
 */
export default function AppFooter() {
  return (
    <div className="border-t border-gray-200 pt-4 mt-6 text-center text-xs text-gray-500 space-y-2">
      <p>{APP_DESCRIPTION}</p>
      <p>{APP_VERSION}</p>
      <p className="font-semibold text-gray-700 mt-2">
        Developed by YOSHITATSU NAKAHARA
      </p>
      <p>© 2026 All Rights Reserved.</p>
      <p className="pt-2 space-x-3">
        <Link
          href="/help/guide"
          className="text-blue-500 hover:text-blue-700 hover:underline font-medium"
        >
          📖 ご利用ガイド
        </Link>
        <span className="text-gray-300">|</span>
        <Link
          href="/admin"
          className="text-gray-400 hover:text-gray-600 hover:underline"
        >
          管理者ページ
        </Link>
      </p>
    </div>
  );
}
