'use client';

import { useEffect } from 'react';
import { venueLinks } from '@/lib/constants';

// QRコードのエンコード用URL (ポータルのURL)
const PORTAL_URL = 'https://fukuoka-events-calendar.com/portal';

export default function Flyer() {
  // ページが開かれたら自動で印刷ダイアログを起動
  useEffect(() => {
    // 読み込み完了後、少し待ってから印刷を起動（レンダリング崩れ防止）
    const timer = setTimeout(() => {
      window.print();
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flyer-container">
      {/* 印刷用のスタイル定義 */}
      <style jsx global>{`
        @page {
          size: A4 portrait;
          margin: 12mm 15mm;
        }
        body {
          background: #ffffff !important;
          color: #111827 !important;
          font-family: "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
          -webkit-print-color-adjust: exact;
          print-color-adjust: exact;
        }
        .flyer-container {
          max-width: 800px;
          margin: 0 auto;
          box-sizing: border-box;
        }
        /* 印刷時以外のブラウザ表示用調整 */
        @media screen {
          body {
            background-color: #f3f4f6 !important;
            padding: 20px;
          }
          .flyer-container {
            background: #ffffff;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
          }
        }
      `}</style>

      {/* チラシヘッダー */}
      <div className="text-center border-b-4 border-blue-600 pb-5 mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-gray-900 mb-2" style={{ wordBreak: 'keep-all', overflowWrap: 'break-word' }}>
          「今日のイベント、何時からだっけ？」を<span className="whitespace-nowrap">1秒で解決！</span>
        </h1>
        <p className="text-xl font-bold text-blue-600">
          福岡イベント情報カレンダー（完全無料・登録不要）
        </p>
      </div>

      {/* 導入文 */}
      <div className="bg-gray-50 border-l-4 border-blue-500 p-4 rounded-r-lg mb-6">
        <p className="text-sm font-semibold text-gray-700 leading-relaxed">
          本サイトは、福岡市内の主要イベント会場のスケジュール情報をリアルタイムに自動集約する、
          タクシードライバー専用の営業支援サイトです。出庫前の需要予測や、効率的な送迎ルートの選定による売上向上にぜひご活用ください。
        </p>
      </div>

      {/* 2カラム構成（メリットと対応会場） */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* メリット */}
        <div className="border border-gray-200 p-5 rounded-lg">
          <h2 className="text-base font-bold text-gray-800 border-b border-gray-200 pb-2 mb-3">
            💡 ドライバーの皆様への3大メリット
          </h2>
          <ul className="text-xs space-y-3 text-gray-600 font-medium">
            <li className="flex items-start gap-1">
              <span className="text-blue-500 font-bold">1.</span>
              <span><strong>出庫前のルート確認に！</strong><br />ドームやマリンメッセの「開始・終演時間」を事前に把握し、渋滞回避やスムーズな送迎に役立ちます。</span>
            </li>
            <li className="flex items-start gap-1">
              <span className="text-blue-500 font-bold">2.</span>
              <span><strong>アクセスするだけで自動更新！</strong><br />野球、コンサート、大型展示会などのスケジュールを常に最新情報で一元管理しています。</span>
            </li>
            <li className="flex items-start gap-1">
              <span className="text-blue-500 font-bold">3.</span>
              <span><strong>スマホ対応・アプリ感覚！</strong><br />インストール不要。ホーム画面に追加すれば、いつでもワンタップで起動します。</span>
            </li>
          </ul>
        </div>

        {/* 対応会場 */}
        <div className="border border-gray-200 p-5 rounded-lg">
          <h2 className="text-base font-bold text-gray-800 border-b border-gray-200 pb-2 mb-3">
            📍 対応している会場（7大施設）
          </h2>
          <ul className="text-xs grid grid-cols-1 gap-2 text-gray-600 font-bold pl-2 list-disc list-inside">
            {venueLinks.map((venue) => (
              <li key={venue.name} className="marker:text-blue-500">
                {venue.name}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* QRコードセクション */}
      <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 p-6 rounded-lg mb-6 bg-gray-50/50">
        <p className="text-sm font-extrabold text-gray-800 mb-3">
          👇 スマートフォンのカメラでQRコードを読み取ってアクセス！
        </p>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/qr-code.png"
          alt="福岡イベント情報ポータル QRコード"
          className="w-48 h-48 border border-gray-200 bg-white p-1 rounded-sm shadow-sm"
        />
        <p className="text-xs text-blue-600 font-bold mt-2">
          {PORTAL_URL}
        </p>
      </div>

      {/* フッター注意書き */}
      <div className="text-center text-[10px] text-gray-500 leading-relaxed border-t border-gray-200 pt-4">
        <p className="font-semibold text-gray-600 mb-1">
          【運行管理者の皆様・ドライバーの皆様へ】
        </p>
        <p>
          本システムは、福岡の現役タクシードライバーが「日々の業務効率化」のために個人で開発・運営している非公式ツールです。<br />
          会場の追加要望や情報の修正依頼などは、サイト内の「ご意見フォーム」からお気軽にお寄せください。
        </p>
      </div>
    </div>
  );
}
