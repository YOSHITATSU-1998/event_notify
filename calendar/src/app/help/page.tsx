'use client';

import Link from 'next/link';

export default function HelpPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-6">
      <div className="max-w-md mx-auto px-4">
        <div className="bg-white rounded-lg shadow-md p-6">
          {/* ヘッダー */}
          <div className="flex items-center justify-between mb-6 border-b border-gray-100 pb-4">
            <Link
              href="/"
              className="text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 text-sm bg-blue-50 px-3 py-2 rounded-lg"
            >
              <span>←</span>
              <span>カレンダー</span>
            </Link>
            <h1 className="text-lg font-bold text-gray-800">データの保存と注意点</h1>
            <div className="w-16"></div>
          </div>

          <div className="space-y-6">
            {/* はじめに */}
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
              <h2 className="font-bold text-blue-900 text-base mb-1">
                売上・シフトデータはどこにある？
              </h2>
              <p className="text-sm text-blue-900 leading-relaxed">
                このカレンダーで入力した売上やシフトのデータは、インターネット上（サーバー）ではなく、<strong>あなたが今使っているスマホ（ブラウザ）の中にだけ直接保存</strong>されます。
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div className="bg-white rounded-lg p-2 text-emerald-800 border border-emerald-100">
                  <p className="font-bold">⭕ メリット</p>
                  <p className="mt-0.5">面倒なログインがなく、売上を誰にも見られないので安心です。</p>
                </div>
                <div className="bg-white rounded-lg p-2 text-red-800 border border-red-100">
                  <p className="font-bold">❌ デメリット</p>
                  <p className="mt-0.5">スマホのお掃除機能等でデータを消すと、元に戻せません。</p>
                </div>
              </div>
            </div>

            {/* iPhone ユーザーへの注意 */}
            <div className="border-t border-gray-100 pt-4">
              <h2 className="font-bold text-gray-800 text-base mb-2 flex items-center gap-1.5">
                <span className="text-xl">🍎</span> iPhone (Safari) をお使いの方
              </h2>
              <div className="bg-gray-50 rounded-xl p-3.5 border border-gray-100 text-sm text-gray-700 space-y-2 leading-relaxed">
                <p>
                  iPhoneの「設定」アプリ ＞「Safari」にある <strong>「履歴とWebサイトデータを消去」</strong> を実行すると、売上やシフトのデータが<strong>すべて消去されます</strong>。
                </p>
                <p className="text-xs text-red-600 font-bold">
                  ⚠️ 履歴の削除とデータの削除がセットになっているため、履歴を消そうとすると売上も一緒に消えてしまいますのでご注意ください。
                </p>
              </div>
            </div>

            {/* Android ユーザーへの注意 */}
            <div className="border-t border-gray-100 pt-4">
              <h2 className="font-bold text-gray-800 text-base mb-2 flex items-center gap-1.5">
                <span className="text-xl">🤖</span> Android (Chrome) をお使いの方
              </h2>
              <div className="bg-gray-50 rounded-xl p-3.5 border border-gray-100 text-sm text-gray-700 space-y-2 leading-relaxed">
                <p>
                  Chromeブラウザの履歴消去を行う際に、 <strong>「Cookie と他のサイトデータ」</strong> にチェックを入れたまま削除を実行すると、売上データが<strong>すべて消去されます</strong>。
                </p>
                <p className="text-xs text-red-600 font-bold">
                  ⚠️ 消したくない場合は、履歴削除を行うときに「Cookie と他のサイトデータ」のチェックを外して削除してください。
                </p>
              </div>
            </div>

            {/* シークレットモードの注意 */}
            <div className="border-t border-gray-100 pt-4">
              <h2 className="font-bold text-gray-800 text-base mb-2 flex items-center gap-1.5">
                <span className="text-xl">🕶️</span> シークレットモードでの使用
              </h2>
              <div className="bg-gray-50 rounded-xl p-3.5 border border-gray-100 text-sm text-gray-700 leading-relaxed">
                <p>
                  画面が黒くなる「プライベートブラウズ」や「シークレットタブ」で開いている場合、<strong>ページを閉じた瞬間にデータはすべて自動で消去</strong>されます。必ず通常モードで開いてご入力ください。
                </p>
              </div>
            </div>

            {/* バックアップの推奨 */}
            <div className="border-t border-gray-100 pt-4">
              <h2 className="font-bold text-gray-800 text-base mb-2 flex items-center gap-1.5">
                <span className="text-xl">📸</span> データの控えについて
              </h2>
              <div className="bg-gray-50 rounded-xl p-3.5 border border-gray-100 text-sm text-gray-700 leading-relaxed">
                <p>
                  万が一に備え、月の終わりなどには<strong>画面のスクリーンショット（写真）を撮るなどして、売上の金額を別途控えておくこと</strong>をお勧めします。
                </p>
              </div>
            </div>

            {/* お問い合わせ先 */}
            <div className="border-t-2 border-dashed border-gray-200 pt-5 text-center">
              <p className="text-sm font-bold text-gray-800">
                💬 わからないことがあれば
              </p>
              <p className="text-base font-black text-blue-700 mt-1 bg-blue-50 inline-block px-4 py-2 rounded-xl border border-blue-100">
                B勤中原まで
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
