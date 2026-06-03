import { Event } from '@/types';
import EventCard from './EventCard';

type Props = {
  /** ヘッダーに表示するタイトル（例: "2026年6月3日（水）のイベント"） */
  title: string;
  events: Event[];
  loading: boolean;
  /** イベントが0件のときのメッセージ */
  emptyMessage?: string;
};

/**
 * EventSection - 日付ヘッダー＋イベントリストをまとめたグレー枠ボックス
 * カレンダー・ポータル共通
 */
export default function EventSection({
  title,
  events,
  loading,
  emptyMessage = 'イベントはありません',
}: Props) {
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 mb-6">
      {/* 日付ヘッダー */}
      <div className="font-bold text-lg text-gray-800 border-b border-gray-300 pb-2 mb-4">
        {title}
      </div>

      {/* コンテンツ */}
      {loading ? (
        <p className="text-center text-gray-500 py-6">読み込み中...</p>
      ) : events.length > 0 ? (
        <div className="space-y-3">
          {events.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      ) : (
        <p className="text-center text-gray-500 py-8 text-sm">
          {emptyMessage}
        </p>
      )}
    </div>
  );
}
