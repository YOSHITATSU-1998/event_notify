'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import { venueLinks, FEEDBACK_FORM_URL } from '@/lib/constants';
import { Event, Notice } from '@/types';
import EventSection from '@/components/EventSection';
import VenueList from '@/components/VenueList';
import FeedbackBox from '@/components/FeedbackBox';
import AppFooter from '@/components/AppFooter';

type WeatherInfo = {
  icon: string;
  text: string;
  temp: number;
  timeStr: string;
};

// JST基準で今日の日付を取得する関数（YYYY-MM-DD）
const getJstTodayStr = () => {
  const now = new Date();
  // 日本標準時に補正
  const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
  const jstDate = new Date(utc + (3600000 * 9));

  const y = jstDate.getFullYear();
  const m = (jstDate.getMonth() + 1).toString().padStart(2, '0');
  const d = jstDate.getDate().toString().padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const WEEK_DAYS = ['日', '月', '火', '水', '木', '金', '土'];

// 「YYYY-MM-DD」→「YYYY年M月D日（曜）」にフォーマット
const formatDateJa = (dateStr: string): string => {
  if (!dateStr) return '';
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  const week = WEEK_DAYS[date.getDay()];
  return `${y}年${m}月${d}日（${week}）`;
};

const weatherMap: Record<number, { icon: string; text: string }> = {
  0:  { icon: '☀', text: '晴れ' },
  1:  { icon: '☀', text: '晴れ' },
  2:  { icon: '⛅', text: '曇り' },
  3:  { icon: '☁', text: '曇り' },
  45: { icon: '🌫', text: '霧' },
  48: { icon: '🌫', text: '霧' },
  51: { icon: '☔', text: '小雨' },
  53: { icon: '☔', text: '小雨' },
  55: { icon: '☔', text: '小雨' },
  61: { icon: '☔', text: '雨' },
  63: { icon: '☔', text: '雨' },
  65: { icon: '☔', text: '雨' },
  71: { icon: '☃', text: '雪' },
  73: { icon: '☃', text: '雪' },
  75: { icon: '☃', text: '雪' },
  80: { icon: '⚡', text: '雷雨' },
  81: { icon: '⚡', text: '雷雨' },
  82: { icon: '⚡', text: '雷雨' },
  95: { icon: '⚡', text: '雷雨' },
  96: { icon: '⚡', text: '雷雨' },
  99: { icon: '⚡', text: '雷雨' },
};

export default function Portal() {
  const [todayStr, setTodayStr] = useState('');
  const [events, setEvents] = useState<Event[]>([]);
  const [weather, setWeather] = useState<WeatherInfo | null>(null);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [weatherError, setWeatherError] = useState(false);
  const [notices, setNotices] = useState<Notice[]>([]);

  // PWA関連のステート
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [showAndroidInstall, setShowAndroidInstall] = useState(false);
  const [showIosInstallTip, setShowIosInstallTip] = useState(false);

  // マウント時に今日の日付を設定
  useEffect(() => {
    setTodayStr(getJstTodayStr());
  }, []);

  // PWAデバイス検知とリスナーの登録
  useEffect(() => {
    // サーバーサイドレンダリング時のエラーを防ぐ
    if (typeof window === 'undefined') return;

    const ua = navigator.userAgent;
    const isIOSDevice = /iPad|iPhone|iPod/.test(ua) && !(window as any).MSStream;
    const isStandaloneMode = window.matchMedia('(display-mode: standalone)').matches || (navigator as any).standalone;

    if (!isStandaloneMode) {
      if (isIOSDevice) {
        // iOSかつスタンドアロン起動ではない場合、案内トーストの表示を検討
        // 毎回出るとウザいので、sessionStorageで「このセッションで一度閉じた」場合は出さないようにする
        const closedThisSession = sessionStorage.getItem('pwa_ios_tip_closed');
        if (!closedThisSession) {
          // 画面が落ち着いてから出すため、1.5秒遅らせて表示
          const timer = setTimeout(() => {
            setShowIosInstallTip(true);
          }, 1500);
          return () => clearTimeout(timer);
        }
      } else {
        // Android（およびChromeデスクトップなど）のbeforeinstallpromptイベントリスナー
        const handleBeforeInstallPrompt = (e: any) => {
          e.preventDefault();
          setDeferredPrompt(e);
          setShowAndroidInstall(true);
        };
        window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
        return () => {
          window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
        };
      }
    }
  }, []);

  // Androidアプリ保存ボタンのクリックハンドラ
  const handleAndroidInstallClick = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log(`User response to install: ${outcome}`);
    setDeferredPrompt(null);
    setShowAndroidInstall(false);
  };

  // iOS吹き出しガイドのクローズハンドラ
  const handleCloseIosTip = () => {
    setShowIosInstallTip(false);
    sessionStorage.setItem('pwa_ios_tip_closed', 'true');
  };

  // 天気情報取得
  const fetchWeather = async () => {
    try {
      const response = await fetch(
        'https://api.open-meteo.com/v1/forecast?latitude=33.59&longitude=130.40&current=temperature_2m,weather_code&timezone=Asia/Tokyo'
      );
      if (!response.ok) throw new Error('Network response was not ok');
      const data = await response.json();

      const temp = Math.round(data.current.temperature_2m);
      const code = data.current.weather_code;
      const mapped = weatherMap[code] || { icon: '☁', text: '曇り' };

      const now = new Date();
      const timeStr = now.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });

      setWeather({ icon: mapped.icon, text: mapped.text, temp, timeStr });
      setWeatherError(false);
    } catch (error) {
      console.error('天気情報の取得に失敗しました:', error);
      setWeatherError(true);
    }
  };

  // イベントフェッチ
  useEffect(() => {
    if (!todayStr) return;

    const fetchTodayEvents = async () => {
      setLoadingEvents(true);
      try {
        const { data, error } = await supabase
          .from('events')
          .select('*')
          .eq('date', todayStr)
          .order('time', { ascending: true });

        if (error) throw error;
        setEvents(data || []);
      } catch (error) {
        console.error('本日のイベントフェッチエラー:', error);
      } finally {
        setLoadingEvents(false);
      }
    };

    fetchTodayEvents();
  }, [todayStr]);

  // お知らせ取得
  useEffect(() => {
    const fetchNotices = async () => {
      const today = getJstTodayStr();
      const { data } = await supabase
        .from('notices')
        .select('*')
        .eq('is_active', true)
        .lte('start_at', today)
        .gte('end_at', today)
        .order('created_at', { ascending: false });
      if (data) setNotices(data);
    };
    fetchNotices();
  }, []);

  // 天気情報の初回取得とタイマー/Visibility設定
  useEffect(() => {
    fetchWeather();

    // 30分毎に更新
    const weatherInterval = setInterval(fetchWeather, 1800000);

    // タブがアクティブになったときに更新
    const handleVisibilityChange = () => {
      if (!document.hidden) fetchWeather();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(weatherInterval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 py-6 px-4">
      {/* iOS用ホーム画面追加トースト */}
      {showIosInstallTip && (
        <div className="fixed bottom-4 left-4 right-4 z-50 bg-white/95 backdrop-blur-md border border-gray-200 p-4 rounded-2xl shadow-2xl flex items-start gap-3 max-w-md mx-auto animate-slide-up">
          <div className="bg-blue-100 p-2.5 rounded-xl text-blue-600 text-xl flex-shrink-0">
            📱
          </div>
          <div className="flex-1 space-y-1">
            <h4 className="font-bold text-gray-800 text-sm">ホーム画面に追加してアプリ化</h4>
            <p className="text-xs text-gray-600 leading-relaxed">
              iPhone（Safari）の方は、画面下部の
              <span className="inline-flex items-center justify-center bg-gray-100 border border-gray-300 rounded px-1.5 py-0.5 mx-1">
                <svg className="w-3.5 h-3.5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
                </svg>
              </span>
              （共有ボタン）を押し、メニュー内の<strong>「ホーム画面に追加」</strong>を選択すると、ワンタップで起動できるようになります。
            </p>
          </div>
          <button 
            onClick={handleCloseIosTip}
            className="text-gray-400 hover:text-gray-600 p-1 hover:bg-gray-100 rounded-lg transition-colors text-xs font-bold"
          >
            ✕
          </button>
        </div>
      )}

      <div className="max-w-xl mx-auto bg-white rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold text-center text-gray-800 border-b-2 border-blue-500 pb-3 mb-4">
          福岡イベント情報
        </h1>

        {/* Android用アプリ保存ボタン */}
        {showAndroidInstall && (
          <div className="bg-blue-50 border border-blue-200 p-4 rounded-xl text-center mb-6 shadow-sm flex flex-col items-center gap-2">
            <div className="flex items-center gap-2 text-blue-900 font-bold text-sm">
              <span className="text-xl">📱</span>
              <span>アプリとしてホーム画面に保存できます</span>
            </div>
            <p className="text-xs text-blue-700">アイコンからワンタップで即起動できるようになります</p>
            <button
              onClick={handleAndroidInstallClick}
              className="w-full mt-1 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm py-2.5 px-4 rounded-lg transition-colors shadow-md hover:shadow-lg flex items-center justify-center gap-1.5"
            >
              <span>アプリを保存する</span>
              <span>→</span>
            </button>
          </div>
        )}

        {/* 天気セクション */}
        {!weatherError && weather ? (
          <div className="flex justify-center items-center gap-2.5 bg-sky-50 border border-sky-100 text-sky-800 font-bold p-3 rounded-lg text-lg mb-6 shadow-sm">
            <span className="text-2xl">{weather.icon}</span>
            <span>{weather.text} / 気温: {weather.temp}℃</span>
            <span className="text-xs text-gray-400 font-normal">({weather.timeStr}更新)</span>
          </div>
        ) : (
          !weatherError && (
            <div className="flex justify-center items-center bg-sky-50 text-sky-800 font-bold p-3 rounded-lg text-lg mb-6 shadow-sm">
              <span className="animate-spin mr-2">⌛</span>
              天気読み込み中...
            </div>
          )
        )}

        {/* お知らせバナー（DBから動的取得） */}
        {notices.map((notice) => (
          <div key={notice.id} className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-lg mb-6 shadow-sm">
            <h3 className="font-bold text-amber-800 text-sm mb-2">{notice.title}</h3>
            <p className="text-xs text-amber-700 leading-relaxed whitespace-pre-wrap">
              {notice.body}
            </p>
          </div>
        ))}

        {/* 本日のイベントコンテンツ */}
        <EventSection
          title={`${formatDateJa(todayStr)}のイベント`}
          events={events}
          loading={loadingEvents}
          emptyMessage="本日の掲載イベントは見つかりませんでした。"
        />

        {/* 対応会場セクション */}
        <VenueList />

        {/* カレンダーリンク */}
        <div className="bg-emerald-50 border border-emerald-100 p-4 rounded-lg text-center mb-6 shadow-sm">
          <h3 className="font-bold text-emerald-800 text-sm mb-1">📅 月間カレンダー表示</h3>
          <p className="text-xs text-emerald-700 mb-3">イベント情報を月間カレンダー形式で確認できます</p>
          <Link
            href="/"
            className="inline-block bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm py-2 px-6 rounded transition-colors shadow-sm"
          >
            月間カレンダーを開く
          </Link>
        </div>

        {/* ご意見・ご要望 */}
        <FeedbackBox />

        {/* 共通フッター */}
        <AppFooter />
      </div>
    </div>
  );
}
