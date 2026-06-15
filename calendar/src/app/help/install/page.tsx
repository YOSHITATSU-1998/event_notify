'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

export default function InstallGuidePage() {
  const [deviceType, setDeviceType] = useState<'loading' | 'ios' | 'android' | 'pc'>('loading');
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isStandalone, setIsStandalone] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const ua = navigator.userAgent;
    const isIOS = /iPad|iPhone|iPod/.test(ua) && !(window as any).MSStream;
    const isAndroid = /Android/i.test(ua);
    const isStandaloneMode = window.matchMedia('(display-mode: standalone)').matches || (navigator as any).standalone;

    setIsStandalone(isStandaloneMode);

    if (isIOS) {
      setDeviceType('ios');
    } else if (isAndroid) {
      setDeviceType('android');

      // Android用のbeforeinstallpromptイベント登録
      const handleBeforeInstallPrompt = (e: any) => {
        e.preventDefault();
        setDeferredPrompt(e);
      };
      window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      return () => {
        window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      };
    } else {
      setDeviceType('pc');
    }
  }, []);

  // Android用のインストール実行処理
  const handleAndroidInstall = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log(`User response to install: ${outcome}`);
    setDeferredPrompt(null);
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-xl mx-auto bg-white rounded-lg shadow-md p-6">
        
        {/* ヘッダー */}
        <div className="flex items-center justify-between mb-6 border-b border-gray-100 pb-4">
          <Link
            href="/portal"
            className="text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 text-sm bg-blue-50 px-3 py-2 rounded-lg"
          >
            <span>←</span>
            <span>ポータルに戻る</span>
          </Link>
          <h1 className="text-lg font-bold text-gray-800">アプリとして保存</h1>
          <div className="w-24"></div> {/* 左右対称用 */}
        </div>

        {/* すでにアプリモード（スタンドアロン）で起動している場合 */}
        {isStandalone ? (
          <div className="text-center py-8 space-y-3">
            <div className="text-4xl">🎉</div>
            <h2 className="font-bold text-gray-800 text-base">すでにアプリとして起動しています</h2>
            <p className="text-xs text-gray-500 max-w-xs mx-auto leading-relaxed">
              この画面はブラウザ枠のない「全画面アプリモード」で表示されています。次回からもホーム画面のアイコンから起動してください。
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            
            {/* ローディング状態 */}
            {deviceType === 'loading' && (
              <div className="text-center py-12 text-gray-500 text-sm flex items-center justify-center gap-2">
                <span className="animate-spin text-lg">⌛</span>
                <span>お使いの端末を判定中...</span>
              </div>
            )}

            {/* iOS (iPhone/iPad) の表示 */}
            {deviceType === 'ios' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-blue-900 text-xs leading-relaxed">
                  iPhone（Safari）の方は、App Storeを通さずに、このサイトをスマホのホーム画面に「アプリ」として追加できます。
                </div>

                <div className="space-y-5">
                  <h2 className="font-bold text-gray-900 text-sm flex items-center gap-1.5 border-b border-gray-100 pb-2">
                    <span className="text-blue-600">📝</span> ホーム画面への追加手順
                  </h2>

                  <div className="space-y-4">
                    <div className="flex items-start gap-3">
                      <div className="bg-blue-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold mt-0.5 flex-shrink-0">
                        1
                      </div>
                      <p className="text-xs text-gray-700 leading-relaxed">
                        画面下部にある **「共有アイコン（四角から上矢印のマーク）」** をタップします。
                        <br />
                        <span className="text-[10px] text-gray-400">※ブラウザのメニューバーが隠れている場合は、画面下部を軽くタップすると表示されます。</span>
                      </p>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="bg-blue-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold mt-0.5 flex-shrink-0">
                        2
                      </div>
                      <p className="text-xs text-gray-700 leading-relaxed">
                        表示されたメニューを下にスクロールし、**「ホーム画面に追加」** をタップします。
                      </p>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="bg-blue-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold mt-0.5 flex-shrink-0">
                        3
                      </div>
                      <p className="text-xs text-gray-700 leading-relaxed">
                        右上の **「追加」** をタップすると、ホーム画面にアイコンが作成されます。次回からはそのアイコンから一瞬で開けます。
                      </p>
                    </div>
                  </div>
                </div>

                {/* 共有アイコンの図解風イラスト代わり */}
                <div className="bg-gray-50 border border-gray-100 rounded-xl p-4 flex flex-col items-center justify-center gap-2">
                  <span className="text-[10px] text-gray-400">Safariのこのアイコンをタップしてください</span>
                  <div className="bg-white border border-gray-300 p-2.5 rounded-lg text-blue-500 shadow-sm">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
                    </svg>
                  </div>
                </div>
              </div>
            )}

            {/* Android の表示 */}
            {deviceType === 'android' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-blue-900 text-xs leading-relaxed">
                  Android（Chrome）の方は、ボタンを1タップするだけで、このサイトをスマホに「アプリ」としてインストールできます。
                </div>

                {/* 1タップインストールボタン（deferredPromptがある場合） */}
                {deferredPrompt ? (
                  <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-center space-y-4 shadow-inner">
                    <div className="text-3xl">📱</div>
                    <div className="space-y-1">
                      <h3 className="font-bold text-gray-800 text-sm">アプリとして保存する準備ができました</h3>
                      <p className="text-[10px] text-gray-500">下のボタンを押すと公式の保存画面が開きます</p>
                    </div>
                    <button
                      onClick={handleAndroidInstall}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm py-3 px-6 rounded-lg transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-1.5"
                    >
                      <span>アプリとしてインストールする</span>
                      <span>→</span>
                    </button>
                  </div>
                ) : (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-900 text-xs space-y-1">
                    <p className="font-bold">⚠️ 1タップ保存が機能しない場合：</p>
                    <p>ブラウザの裏側でインストール準備を行っています。ボタンが表示されない場合は、以下の手動手順でも数秒でアプリ化できます。</p>
                  </div>
                )}

                {/* Android 手動追加手順 */}
                <div className="space-y-4">
                  <h2 className="font-bold text-gray-900 text-sm flex items-center gap-1.5 border-b border-gray-100 pb-2">
                    <span className="text-blue-600">📝</span> 手動での追加手順
                  </h2>

                  <div className="space-y-4 text-xs text-gray-700">
                    <div className="flex items-start gap-3">
                      <div className="bg-blue-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-[10px] font-bold mt-0.5 flex-shrink-0">
                        1
                      </div>
                      <p className="leading-relaxed">
                        Chromeブラウザの画面右上にある **「︙（メニューアイコン）」** をタップします。
                      </p>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="bg-blue-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-[10px] font-bold mt-0.5 flex-shrink-0">
                        2
                      </div>
                      <p className="leading-relaxed">
                        メニュー内の **「ホーム画面に追加」** （または「アプリをインストール」）をタップします。
                      </p>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="bg-blue-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-[10px] font-bold mt-0.5 flex-shrink-0">
                        3
                      </div>
                      <p className="leading-relaxed">
                        確認画面で **「追加（インストール）」** を選ぶと、ホーム画面にアイコンが即座に配置されます。
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* PC の表示 */}
            {deviceType === 'pc' && (
              <div className="text-center py-16 space-y-4">
                <div className="text-5xl font-black text-blue-600 animate-pulse">
                  TEST
                </div>
                <p className="text-xs text-gray-400">
                  （PC用のインストール手順は現在テスト表示モードです。スマホから開くとそれぞれの自動ガイドが開きます。）
                </p>
              </div>
            )}

          </div>
        )}
      </div>
    </div>
  );
}
