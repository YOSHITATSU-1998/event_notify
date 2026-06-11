import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'このサイトについて | 福岡イベントカレンダー',
  description: '福岡市内のタクシードライバー向けに作られた、主要イベント会場のスケジュール確認・売上管理ツールの使い方ガイドです。新人ドライバーとベテランの情報格差をなくすために開発しました。',
};

export default function GuideLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
