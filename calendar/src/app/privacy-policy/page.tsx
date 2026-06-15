'use client';

import Link from 'next/link';

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-xl mx-auto bg-white rounded-lg shadow-md p-6">
        
        {/* ヘッダー */}
        <div className="flex items-center justify-between mb-6 border-b border-gray-100 pb-4">
          <Link
            href="/"
            className="text-gray-600 hover:text-gray-800 font-medium flex items-center gap-1 text-sm bg-gray-100 px-3 py-2 rounded-lg"
          >
            <span>←</span>
            <span>戻る</span>
          </Link>
          <h1 className="text-lg font-bold text-gray-800">プライバシーポリシー</h1>
          <div className="w-16"></div> {/* 左右対称にするためのダミー */}
        </div>

        <div className="space-y-6 text-sm text-gray-700 leading-relaxed">
          
          <section className="space-y-2">
            <h2 className="font-bold text-gray-900 text-base border-l-4 border-blue-500 pl-2">
              広告の配信について
            </h2>
            <p>
              当サイトでは、第三者配信事業者（Googleなど）による広告配信サービス「Google AdSense」を利用、または今後利用する予定です。
            </p>
            <p>
              広告配信事業者は、ユーザーの興味に応じた商品やサービスの広告を表示するため、当サイトや他サイトへのアクセスに関する情報「Cookie」（氏名、住所、メールアドレス、電話番号は含まれません）を使用することがあります。
            </p>
            <p>
              パーソナライズ広告を無効にする方法や、Cookieの使用に関する詳細については、Googleの
              <a 
                href="https://policies.google.com/technologies/ads" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline mx-1"
              >
                広告とプライバシーに関するポリシー
              </a>
              をご参照ください。また、ユーザーはブラウザの設定によりCookieを無効にすることも可能です。
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-bold text-gray-900 text-base border-l-4 border-blue-500 pl-2">
              アクセス解析ツールについて
            </h2>
            <p>
              当サイトでは、サイトの利用状況を把握し、より良いサービスを提供するために「Vercel Analytics」を利用しています。
            </p>
            <p>
              Vercel Analyticsは個人を特定する情報（氏名や正確な位置情報など）を含まない形で、匿名化されたアクセスログ（閲覧ページ、ブラウザの種類、アクセス日時など）を収集します。収集されたデータはサイトの改善・分析のみに使用されます。
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-bold text-gray-900 text-base border-l-4 border-blue-500 pl-2">
              免責事項
            </h2>
            <p>
              当サイトに掲載されている情報（イベントスケジュール、開演時間、天気情報など）は、可能な限り正確な情報を掲載するよう努めておりますが、その完全性、正確性を保証するものではありません。
            </p>
            <p>
              イベントの急な中止、延期、内容変更、および当サイトの情報を利用したことによって生じたトラブルやいかなる損失・損害についても、当サイト運営者は一切の責任を負いかねますのでご了承ください。必ず公式のイベント情報も併せてご確認ください。
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-bold text-gray-900 text-base border-l-4 border-blue-500 pl-2">
              策定日
            </h2>
            <p className="text-xs text-gray-500">
              策定：2026年6月15日
            </p>
          </section>

        </div>
      </div>
    </div>
  );
}
