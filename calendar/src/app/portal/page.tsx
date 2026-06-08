'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import { venueLinks, FEEDBACK_FORM_URL } from '@/lib/constants';
import { Event } from '@/types';
import EventSection from '@/components/EventSection';
import VenueList from '@/components/VenueList';
import FeedbackBox from '@/components/FeedbackBox';
import AppFooter from '@/components/AppFooter';
import SurveyPopup from '@/components/SurveyPopup';

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
      {/* アンケートポップアップ */}
      <SurveyPopup />
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
