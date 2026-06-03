import { Event } from '@/types';
import { formatTime } from '@/lib/constants';

type Props = {
  event: Event;
  /** 現在は両ページとも同一スタイル。将来の分岐用に残す */
  variant?: 'calendar' | 'portal';
};

/**
 * EventCard - イベント1件の表示カード（カレンダー・ポータル共通）
 * デザインはポータルスタイル（白背景・角丸・シャドウ）に統一
 */
export default function EventCard({ event }: Props) {
  return (
    <div className="border-l-4 border-blue-500 pl-4 py-1 bg-white p-3 rounded shadow-sm">
      {/* 時刻・会場 */}
      <div className="flex items-center gap-2 mb-1">
        <span className="font-semibold text-blue-600 text-sm">
          {formatTime(event.time)}
        </span>
        <span className="text-xs text-gray-500">
          {event.venue}
        </span>
      </div>

      {/* イベント名（URL付きなら黒リンク） */}
      <h3 className="font-semibold text-gray-800 text-base">
        {event.source_url ? (
          <a
            href={event.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-800 hover:text-black hover:underline transition-colors"
          >
            {event.title}
          </a>
        ) : (
          event.title
        )}
      </h3>

      {/* 備考（game_status: を除く） */}
      {event.notes && !event.notes.includes('game_status:') && (
        <p className="text-xs text-gray-600 mt-1">
          {event.notes}
        </p>
      )}
    </div>
  );
}
