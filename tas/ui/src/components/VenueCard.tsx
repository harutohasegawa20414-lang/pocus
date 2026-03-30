import { useNavigate } from 'react-router-dom'
import { MapPin, Clock, Trophy } from 'lucide-react'
import type { VenueCard as VenueCardType } from '../types/api'
import StatusBadge from './StatusBadge'
import P1Icons from './P1Icons'
import { formatPrice, formatDate, formatUpdatedAt } from '../api/client'

/** URLが安全な http(s) プロトコルか検証する */
function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null
  const trimmed = url.trim()
  if (!trimmed || trimmed === '#') return null
  try {
    const parsed = new URL(trimmed, 'https://placeholder.local')
    if (!['http:', 'https:'].includes(parsed.protocol)) return null
    return trimmed
  } catch { return null }
}

interface Props {
  venue: VenueCardType
}

export default function VenueCard({ venue }: Props) {
  const navigate = useNavigate()

  return (
    <article
      onClick={() => navigate(`/venues/${venue.id}`)}
      className="bg-white rounded-xl border border-stone-100 shadow-sm hover:shadow-md
                 hover:border-gold-200 transition-all duration-200 cursor-pointer p-4 space-y-3"
    >
      {/* 店舗名 + エリア */}
      <div>
        <h3 className="font-bold text-stone-900 text-base leading-tight line-clamp-1">
          {venue.name}
        </h3>
        {(venue.area_prefecture || venue.area_city) && (
          <p className="text-xs text-stone-400 mt-0.5 flex items-center gap-1">
            <MapPin size={11} className="flex-shrink-0" />
            {[venue.area_prefecture, venue.area_city].filter(Boolean).join(' ')}
          </p>
        )}
      </div>

      {/* P0 */}
      <div className="space-y-1.5">
        <StatusBadge status={venue.open_status} hoursToday={venue.hours_today} />

        {venue.price_entry_min != null && (
          <p className="text-sm font-semibold text-gold-700">
            {formatPrice(venue.price_entry_min)}
            {venue.price_note && (
              <span className="text-xs font-normal text-stone-400 ml-1">
                {venue.price_note}
              </span>
            )}
          </p>
        )}

        {venue.next_tournament_title && (
          <p className="text-xs text-amber-700 flex items-center gap-1 bg-amber-50 rounded-md px-2 py-1">
            <Trophy size={12} className="flex-shrink-0" />
            <span className="line-clamp-1">{venue.next_tournament_title}</span>
            {venue.next_tournament_start && (
              <span className="flex-shrink-0 ml-auto text-amber-500">
                {formatDate(venue.next_tournament_start)}
              </span>
            )}
          </p>
        )}
      </div>

      {/* P1 */}
      <P1Icons
        drinkRequired={venue.drink_required}
        foodLevel={venue.food_level}
        tableCount={venue.table_count}
        peakTime={venue.peak_time}
      />

      {/* フッター */}
      <div className="flex items-center justify-between pt-1 border-t border-stone-50">
        {venue.updated_at && (
          <p className="text-xs text-stone-300 flex items-center gap-1">
            <Clock size={10} />
            {formatUpdatedAt(venue.updated_at)}
          </p>
        )}
        {venue.sources && venue.sources.length > 0 && safeUrl(venue.sources[0]) && (
          <a
            href={safeUrl(venue.sources[0])!}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-xs text-stone-300 hover:text-gold-500 transition-colors"
          >
            公式サイト →
          </a>
        )}
      </div>
    </article>
  )
}
