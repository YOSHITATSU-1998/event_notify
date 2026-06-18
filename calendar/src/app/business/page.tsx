'use client';

import Link from 'next/link';

export default function BusinessGuide() {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto bg-white rounded-xl shadow-md overflow-hidden p-8 border border-gray-200">
        
        {/* ヘッダー */}
        <div className="border-b border-gray-200 pb-5 mb-6 text-center">
          <span className="text-3xl">🚖</span>
          <h1 className="text-2xl font-bold text-gray-900 mt-2">
            タクシー事業者様・運行管理者の皆様へ
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            福岡イベントカレンダー 営業所掲示用チラシのご案内
          </p>
        </div>

        {/* 導入説明 */}
        <div className="space-y-4 text-sm text-gray-600 leading-relaxed mb-8">
          <p>
            いつも福岡での乗務、お疲れ様です。
          </p>
          <p>
            本サイト「福岡イベントカレンダー」は、福岡市内の主要イベント会場のスケジュール（開始時間・終演時間など）をリアルタイムに自動集約しているドライバー支援サイトです。
          </p>
          <p>
            ドライバーの皆様が点呼前や休憩時にスマホでサッと確認し、<strong>「無駄のない送迎計画」</strong>や<strong>「混雑回避」</strong>に繋げることで、売上の向上と事故防止にお役立ていただけます。
          </p>
          <p>
            ぜひ、貴営業所の点呼場や休憩室などに「案内チラシ」を掲示いただき、ドライバー同士での共有にご活用ください。
          </p>
        </div>

        {/* 印刷のステップ */}
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-5 mb-8">
          <h2 className="text-base font-bold text-blue-900 mb-3 flex items-center gap-1.5">
            <span>📄</span> チラシの印刷方法
          </h2>
          <ol className="text-xs space-y-3 text-blue-800 font-semibold list-decimal list-inside pl-1">
            <li>下記の「掲示用チラシ (PDF) をダウンロード」ボタンをクリックします。</li>
            <li>ダウンロードされたPDFファイルを開きます。</li>
            <li>お手持ちのプリンターから「A4サイズ・縦」で印刷し、営業所内にご掲示ください。</li>
          </ol>
        </div>

        {/* アクションボタン */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-8">
          <a
            href="/fukuoka_event_guide.pdf"
            download="fukuoka_event_guide.pdf"
            className="w-full sm:w-auto inline-flex justify-center items-center bg-blue-600 hover:bg-blue-700 text-white font-bold text-base py-3 px-8 rounded-lg transition-colors shadow-sm text-center cursor-pointer"
          >
            📥 掲示用チラシ (PDF) をダウンロード
          </a>
          <Link
            href="/portal"
            className="w-full sm:w-auto inline-flex justify-center items-center bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold text-base py-3 px-8 rounded-lg transition-colors text-center"
          >
            📱 ポータルサイトへ戻る
          </Link>
        </div>

        {/* 注意事項 */}
        <div className="border-t border-gray-200 pt-5 text-xs text-gray-400 leading-relaxed">
          <p>
            ※ 本ツールは現役ドライバーによる個人運営の非公式ツールです。完全無料でお使いいただけます。
          </p>
          <p className="mt-1">
            ※ スマホから直接コンビニ（セブンイレブン、ローソン、ファミリーマート等）のネットプリントサービスにPDFを登録して印刷することも可能です。
          </p>
        </div>

      </div>
    </div>
  );
}
