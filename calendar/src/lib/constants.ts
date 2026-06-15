// アプリ全体で共有する定数

export const APP_VERSION = 'Ver.4.6';

export const APP_DESCRIPTION = '福岡市内主要イベント会場の情報を自動収集・配信しています';

export const FEEDBACK_FORM_URL =
  'https://docs.google.com/forms/d/e/1FAIpQLSfX2EtHu3hZ2FgMfUjSOx1YYQqt2BaB3BGniVPF5TMCtgLByw/viewform';

export const venueLinks = [
  { name: 'マリンメッセA館',   url: 'https://www.marinemesse.or.jp/messe/event/' },
  { name: 'マリンメッセB館',   url: 'https://www.marinemesse.or.jp/messe-b/event/' },
  { name: '福岡国際センター',   url: 'https://www.marinemesse.or.jp/kokusai/event/' },
  { name: '福岡国際会議場',    url: 'https://www.marinemesse.or.jp/congress/event/' },
  { name: '福岡サンパレス',    url: 'https://www.f-sunpalace.com/hall/#hallEvent' },
  { name: 'みずほPayPayドーム', url: 'https://www.softbankhawks.co.jp/' },
  { name: 'ベスト電器スタジアム', url: 'https://www.avispa.co.jp/game_practice' },
];

// 時刻フォーマット（HH:MM）
export const formatTime = (time?: string): string => {
  if (!time) return '（時刻未定）';
  return time.substring(0, 5);
};
