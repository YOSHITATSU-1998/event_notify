'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

type Event = {
  id: number;
  date: string;
  time?: string;
  title: string;
  venue: string;
  source_url?: string;
  notes?: string;
};

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
  const jstOffset = 9 * 60; // JSTはUTC+9時間
  const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
  const jstDate = new Date(utc + (3600000 * 9));
  
  const y = jstDate.getFullYear();
  const m = (jstDate.getMonth() + 1).toString().padStart(2, '0');
  const d = jstDate.getDate().toString().padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const weatherMap: Record<number, { icon: string; text: string }> = {
  0: { icon: '☀', text: '晴れ' },
  1: { icon: '☀', text: '晴れ' },
  2: { icon: '⛅', text: '曇り' },
  3: { icon: '☁', text: '曇り' },
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
  99: { icon: '⚡', text: '雷雨' }
};

const venueLinks = [
  { name: 'マリンメッセA館', url: 'https://www.marinemesse.or.jp/messe/event/' },
  { name: 'マリンメッセB館', url: 'https://www.marinemesse.or.jp/messe-b/event/' },
  { name: '福岡国際センター', url: 'https://www.marinemesse.or.jp/kokusai/event/' },
  { name: '福岡国際会議場', url: 'https://www.marinemesse.or.jp/congress/event/' },
  { name: '福岡サンパレス', url: 'https://www.f-sunpalace.com/hall/#hallEvent' },
  { name: 'みずほPayPayドーム', url: 'https://www.softbankhawks.co.jp/' },
  { name: 'ベスト電器スタジアム', url: 'https://www.avispa.co.jp/game_practice' }
];

export default function Portal() {
  const [todayStr, setTodayStr] = useState('');
  const [events, setEvents] = useState<Event[]>([]);
  const [weather, setWeather] = useState<WeatherInfo | null>(null);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [weatherError, setWeatherError] = useState(false);

  // マウント時に今日の日付を設定
  useEffect(() => {
    setTodayStr(getJstTodayStr());
  }, []);

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
      
      setWeather({
        icon: mapped.icon,
        text: mapped.text,
        temp,
        timeStr
      });
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

  // 天気情報の初回取得とタイマー/Visibility設定
  useEffect(() => {
    fetchWeather();

    // 30分毎に更新
    const weatherInterval = setInterval(fetchWeather, 1800000);

    // タブがアクティブになったときに更新
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        fetchWeather();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(weatherInterval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  const formatTime = (time?: string) => {
    if (!time) return '（時刻未定）';
    return time.substring(0, 5);
  };

  return (
    <div className="min-h-screen bg-gray-100 py-6 px-4">
      <div className="max-w-xl mx-auto bg-white rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold text-center text-gray-800 border-b-2 border-blue-500 pb-3 mb-4">
          福岡イベント情報
        </h1>

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

        <div className="text-center text-xs text-gray-500 mb-1">最終更新: {todayStr} (リアルタイム自動連動)</div>
        <div className="text-center text-xs text-green-700 font-bold bg-green-50 border border-green-100 rounded py-1 px-3 max-w-[180px] mx-auto mb-6">
          データソース: データベース
        </div>

        {/* 本日のイベントコンテンツ */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 mb-6">
          <div className="font-bold text-lg text-gray-800 border-b border-gray-300 pb-2 mb-4">
            【本日のイベント】{todayStr}
          </div>

          {loadingEvents ? (
            <p className="text-center text-gray-500 py-6">読み込み中...</p>
          ) : events.length > 0 ? (
            <div className="space-y-4">
              {events.map((event) => (
                <div key={event.id} className="border-l-4 border-blue-500 pl-4 py-1 bg-white p-3 rounded shadow-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-blue-600 text-sm">
                      {formatTime(event.time)}
                    </span>
                    <span className="text-xs text-gray-500">
                      {event.venue}
                    </span>
                  </div>
                  <h3 className="font-semibold text-gray-800 text-base">
                    {event.source_url ? (
                      <a
                        href={event.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 hover:underline transition-colors"
                      >
                        {event.title}
                      </a>
                    ) : (
                      event.title
                    )}
                  </h3>
                  {event.notes && !event.notes.includes('game_status:') && (
                    <p className="text-xs text-gray-600 mt-1">
                      {event.notes}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-gray-500 py-8 text-sm">
              本日の掲載イベントは見つかりませんでした。
            </p>
          )}
        </div>

        {/* 対応会場セクション */}
        <div className="bg-gray-100 p-4 rounded-lg border border-gray-200 mb-6">
          <div className="font-bold text-sm text-gray-700 mb-2 border-b border-gray-300 pb-1">
            【現在の対応会場】
          </div>
          <ul className="text-xs space-y-1.5 list-disc pl-4 text-gray-600 font-medium">
            {venueLinks.map((venue) => (
              <li key={venue.name}>
                <a
                  href={venue.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 hover:underline"
                >
                  {venue.name}
                </a>
              </li>
            ))}
          </ul>
        </div>

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
        <div className="bg-amber-50 border border-amber-100 p-4 rounded-lg text-center mb-6 shadow-sm">
          <h3 className="font-bold text-amber-800 text-sm mb-1">ご意見・ご要望</h3>
          <p className="text-xs text-amber-700 mb-3">会場追加のご希望や情報漏れのご報告をお待ちしています</p>
          <a
            href="https://docs.google.com/forms/d/e/1FAIpQLSfX2EtHu3hZ2FgMfUjSOx1YYQqt2BaB3BGniVPF5TMCtgLByw/viewform"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-500 hover:bg-amber-600 text-white font-bold text-sm py-2 px-6 rounded transition-colors shadow-sm"
          >
            ご意見・ご要望はこちら
          </a>
        </div>

        {/* フッター */}
        <div className="border-t border-gray-200 pt-4 mt-6 text-center text-xs text-gray-500 space-y-2">
          <p>福岡市内主要イベント会場の情報を自動収集・配信しています</p>
          <p>Ver.4.3 (Next.js Portal統合版)</p>
          <p className="font-semibold text-gray-700 mt-2">
            Developed by YOSHITATSU NAKAHARA
          </p>
          <p>© 2026 All Rights Reserved.</p>
          <p className="pt-2">
            <Link href="/admin" className="text-gray-400 hover:text-gray-600 hover:underline">
              管理者ページへ
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
