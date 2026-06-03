import { venueLinks } from '@/lib/constants';

/**
 * VenueList - 対応会場リスト（カレンダー・ポータル共通）
 */
export default function VenueList() {
  return (
    <div className="bg-gray-100 p-4 rounded-lg border border-gray-200 mb-6">
      <div className="font-bold text-sm text-gray-700 mb-2 border-b border-gray-300 pb-1">
        【対応会場】
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
  );
}
