'use client';

import Link from 'next/link';
import { FEEDBACK_FORM_URL } from '@/lib/constants';

export default function ContactPage() {
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
          <h1 className="text-lg font-bold text-gray-800">お問い合わせ</h1>
          <div className="w-16"></div> {/* 左右対称にするためのダミー */}
        </div>

        <div className="space-y-6 text-sm text-gray-700 leading-relaxed">
          
          <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-blue-900">
            当サイト「福岡イベントカレンダー」に関するご意見、ご要望、バグ報告、またはその他のお問い合わせは、以下のフォームよりご連絡をお願いいたします。
          </div>

          <section className="space-y-4">
            <h2 className="font-bold text-gray-900 text-base border-l-4 border-blue-500 pl-2">
              お問い合わせ窓口
            </h2>
            <p>
              お問い合わせは、Googleフォームにて24時間受け付けております。以下のリンクからフォームを開き、必要事項をご記入の上送信してください。
            </p>
            
            <div className="pt-2 text-center">
              <a
                href={FEEDBACK_FORM_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-bold px-6 py-3 rounded-lg shadow-md hover:shadow-lg transition-all text-base"
              >
                お問い合わせ・ご要望フォームを開く ↗
              </a>
            </div>
          </section>

          <section className="space-y-2 pt-4 border-t border-gray-100">
            <h2 className="font-bold text-gray-900 text-base border-l-4 border-blue-500 pl-2">
              運営者情報
            </h2>
            <div className="bg-gray-50 rounded-lg p-4 space-y-1 text-xs">
              <p><strong>運営者名:</strong> 中原（NAKAHARA）</p>
              <p><strong>サイト名:</strong> 福岡イベントカレンダー</p>
              <p><strong>目的:</strong> 福岡のタクシードライバー（特に新人・他社ドライバー）の情報格差をなくし、営業効率を向上させるためのコミュニティツール運営</p>
            </div>
          </section>

        </div>
      </div>
    </div>
  );
}
