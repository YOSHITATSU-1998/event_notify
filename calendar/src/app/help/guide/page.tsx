'use client';

import Link from 'next/link';

export default function GuidePage() {
  return (
    <div className="min-h-screen bg-gray-50 py-6">
      <div className="max-w-xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-md p-6">
          
          {/* ヘッダー */}
          <div className="flex items-center justify-between mb-6 border-b border-gray-100 pb-4">
            <Link
              href="/help"
              className="text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 text-sm bg-blue-50 px-3 py-2 rounded-lg"
            >
              <span>←</span>
              <span>注意点ページ</span>
            </Link>
            <h1 className="text-lg font-bold text-gray-800">このサイトについて</h1>
            <Link
              href="/"
              className="text-emerald-600 hover:text-emerald-800 font-medium flex items-center gap-1 text-sm bg-emerald-50 px-3 py-2 rounded-lg"
            >
              <span>カレンダー</span>
              <span>→</span>
            </Link>
          </div>

          <div className="space-y-8">
            
            {/* なぜ作ったのか？ */}
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-5">
              <h2 className="font-bold text-blue-900 text-base mb-3 flex items-center gap-1.5">
                <span className="text-lg">💡</span> なぜこのサイトを作ったのか？
              </h2>
              <div className="text-sm text-blue-950 leading-relaxed space-y-3">
                <p>
                  新人時代、とにかく必死に走り回っていた私ですが、ある日ベテランさんが異常なまでの売上を上げていました。
                  理由を聞くと、<strong>「今日、PayPayドームで1日中大きなイベントがあっていたからだよ」</strong>と。
                </p>
                <p>
                  その情報は社内の掲示板にも載っておらず、知っているベテランだけが稼げる状態でした。
                  <strong>「知っている人だけが稼げて、新人が知らないという情報の格差をなくしたい」</strong>と思ったのがきっかけです。
                </p>
                <p>
                  とはいえ、毎回すべての会場のスケジュールを個別に調べるのはとても手間がかかります。
                  そこで、福岡市内の主要イベントを一発で確認できるこのサイトを作りました。みんなで効率よく稼ぎましょう！
                </p>
              </div>
            </div>

            {/* 使い方動画セクション */}
            <div className="border-t border-gray-100 pt-5">
              <h2 className="font-bold text-gray-800 text-base mb-3 flex items-center gap-1.5">
                <span className="text-xl">🎬</span> 動画でわかる！使い方ガイド
              </h2>
              
              <div className="bg-gray-100 rounded-xl overflow-hidden border border-gray-200 aspect-video w-full">
                <iframe
                  src="https://www.youtube.com/embed/HKbmpnqUrx8"
                  title="福岡イベントカレンダー 使い方ガイド"
                  frameBorder="0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                  className="w-full h-full rounded-xl"
                ></iframe>
              </div>
            </div>

            {/* 各機能の使い方解説 */}
            <div className="border-t border-gray-100 pt-5 space-y-4">
              <h2 className="font-bold text-gray-800 text-base mb-1 flex items-center gap-1.5">
                <span className="text-xl">🚕</span> 主要機能の使い方
              </h2>

              {/* ポータル */}
              <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-gray-850 text-sm">
                    1. 今日のイベント
                  </h3>
                  <Link
                    href="/portal"
                    className="text-xs text-blue-600 hover:text-blue-800 font-bold bg-blue-50 px-2.5 py-1 rounded-lg transition-colors border border-blue-100"
                  >
                    ページを開く ↗
                  </Link>
                </div>
                <p className="text-xs text-gray-650 leading-relaxed">
                  当日のイベント、開演時間、会場周辺のピンポイント天気をまとめて確認できます。その日の営業ルート選びや、渋滞を避けるための運行計画に最適です。
                </p>
              </div>

              {/* カレンダー */}
              <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-gray-850 text-sm">
                    2. 月間カレンダー
                  </h3>
                  <Link
                    href="/"
                    className="text-xs text-emerald-600 hover:text-emerald-800 font-bold bg-emerald-50 px-2.5 py-1 rounded-lg transition-colors border border-emerald-100"
                  >
                    カレンダーを開く ↗
                  </Link>
                </div>
                <p className="text-xs text-gray-650 leading-relaxed">
                  イベントが重なる日は、セルの色が「緑（通常）➡️ 橙（混雑）➡️ 赤（大混雑）」と変化します。狙い目の乗車地や、効率の良い出勤日を計画する目安になります。
                </p>
              </div>

              {/* シフト連動 */}
              <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-gray-850 text-sm">
                    3. シフト入力 ＆ 🚕マーク連動
                  </h3>
                  <Link
                    href="/shift"
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-bold bg-indigo-50 px-2.5 py-1 rounded-lg transition-colors border border-indigo-200"
                  >
                    シフト入力を開く ↗
                  </Link>
                </div>
                <p className="text-xs text-gray-650 leading-relaxed">
                  「シフト入力」から自分の出勤予定を登録すると、カレンダー上に「🚕」マークが表示されます。イベント開催日と自分の乗務日がパッと視覚的に重なるため、狙い目がひと目でわかります。
                </p>
              </div>

              {/* 売上管理 */}
              <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-gray-850 text-sm">
                    4. 売上・目標管理
                  </h3>
                  <Link
                    href="/sales"
                    className="text-xs text-emerald-700 hover:text-emerald-950 font-bold bg-emerald-50 px-2.5 py-1 rounded-lg transition-colors border border-emerald-200"
                  >
                    売上管理を開く ↗
                  </Link>
                </div>
                <p className="text-xs text-gray-650 leading-relaxed mb-2">
                  「売上管理」画面から日々の売上を記録し、今月の売上目標を入力すると、カレンダー上部に「目標達成まであといくらか」が自動で計算・表示されます。
                </p>
                <p className="text-[10px] text-gray-500 border-t border-gray-200 pt-2 leading-relaxed">
                  ※入力した売上やシフトはインターネット上のサーバーには一切保存されません。ログイン不要で、あなただけの「秘密メモ」としてスマホ（ブラウザ）の中にだけ安全に保存されます。
                </p>
              </div>
            </div>

            {/* お問い合わせ先 */}
            <div className="border-t-2 border-dashed border-gray-200 pt-5 text-center">
              <p className="text-sm font-bold text-gray-800">
                💬 不明点・ご要望があれば
              </p>
              <p className="text-base font-black text-blue-700 mt-1 bg-blue-50 inline-block px-4 py-2 rounded-xl border border-blue-100">
                中原（NAKAHARA）までお気軽に！
              </p>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
