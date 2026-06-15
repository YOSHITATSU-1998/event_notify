import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Analytics } from '@vercel/analytics/react';

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "福岡イベントカレンダー",
  description: "福岡市内の主要イベント情報を一瞬で確認できる、タクシードライバー向けイベントカレンダーです。",
  manifest: "/manifest.json",
  icons: {
    icon: "/icon-192.png",
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "福岡イベントカレンダー",
    description: "福岡市内の主要イベント情報を一瞬で確認できる、タクシードライバー向けイベントカレンダーです。",
    url: "https://www.fukuoka-events-calendar.com",
    siteName: "福岡イベントカレンダー",
    locale: "ja_JP",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "福岡イベントカレンダー",
    description: "福岡市内の主要イベント情報を一瞬で確認できる、タクシードライバー向けイベントカレンダーです。",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <head>
        {/* Google AdSense 所有権確認用メタタグ（クローラー検出率100%） */}
        <meta name="google-adsense-account" content="ca-pub-2581133893639149" />
        {/* Google AdSense 審査用スクリプト（直書きで静的検出を確実に） */}
        <script
          async
          src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2581133893639149"
          crossOrigin="anonymous"
        ></script>
        {/* PWA サービスワーカー登録用スクリプト */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                  navigator.serviceWorker.register('/sw.js').then(
                    function(reg) {
                      console.log('ServiceWorker registered:', reg.scope);
                    },
                    function(err) {
                      console.log('ServiceWorker registration failed:', err);
                    }
                  );
                });
              }
            `,
          }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
        <Analytics />
      </body>
    </html>
  );
}
