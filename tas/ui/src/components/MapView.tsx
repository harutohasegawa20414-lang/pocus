import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MapContainer, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import type { VenuePin } from '../types/api'
import type { Filters } from './FilterBar'
import { formatPrice } from '../api/client'
import { MS_PER_DAY, MANY_TABLES_THRESHOLD, DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM, TILE_URL_DARK, TILE_ATTRIBUTION_DARK, TILE_URL_LIGHT, TILE_ATTRIBUTION_LIGHT } from '../constants'

/** HTML特殊文字をエスケープする */
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

// ── 時間帯判定 ────────────────────────────────────────────────

function isCurrentlyNight(): boolean {
  // const h = new Date().getHours()
  // return h < 6 || h >= 18
  return false // 一旦夜モードをオフにする
}

// ── 各店舗のスーツモードをスコアで決定 ─────────────────────────

type SuitMode = 'default' | 'tournament' | 'price' | 'open' | 'facility'

/** 営業時間テキストからざっくり営業時間数を推定 */
function estimateHours(hours: string): number {
  const m = hours.match(/(\d{1,2}):(\d{2})\s*[〜～~\-]\s*(?:翌)?(\d{1,2}):(\d{2})/)
  if (!m) return 0
  const open = parseInt(m[1]) * 60 + parseInt(m[2])
  let close = parseInt(m[3]) * 60 + parseInt(m[4])
  if (close <= open) close += 1440 // 翌日
  return (close - open) / 60
}

/** 店舗ごとにスーツ別スコアを計算し、最高スコアのスーツを返す */
function getPinSuitMode(pin: VenuePin): SuitMode {
  // ♠ 営業スコア: open_status + 営業時間の長さ
  let spade = 0
  if (pin.open_status === 'open') spade += 0.5
  if (pin.hours_today) {
    const h = estimateHours(pin.hours_today)
    spade += Math.min(h / 18, 1) * 0.5 // 18時間で満点
  }

  // ♥ 大会スコア: 大会の有無 + 近さ
  let heart = 0
  if (pin.next_tournament_title) {
    heart += 0.6
    if (pin.next_tournament_start) {
      const days = (new Date(pin.next_tournament_start).getTime() - Date.now()) / MS_PER_DAY
      if (days <= 1) heart += 0.4
      else if (days <= 3) heart += 0.3
      else if (days <= 7) heart += 0.2
      else heart += 0.1
    }
  }

  // ♦ 価格スコア: 安いほど高い
  let diamond = 0
  if (pin.price_entry_min != null) {
    diamond = Math.max(0.1, 1 - pin.price_entry_min / 5000)
  }

  // ♣ 施設スコア: フード + テーブル数 + ドリンク
  let club = 0
  if (pin.food_level === 'rich') club += 0.5
  else if (pin.food_level === 'basic') club += 0.2
  if (pin.table_count != null && pin.table_count >= MANY_TABLES_THRESHOLD) club += 0.3
  else if (pin.table_count != null && pin.table_count >= 3) club += 0.15
  if (pin.drink_required) club += 0.2

  // 最高スコアのスーツを選択（同点は優先度順: ♥ > ♣ > ♠ > ♦）
  const scores: [SuitMode, number][] = [
    ['tournament', heart],
    ['facility', club],
    ['open', spade],
    ['price', diamond],
  ]
  const best = scores.reduce((a, b) => b[1] > a[1] ? b : a)

  // 最高スコアが低すぎる → デフォルト（Pチップ）
  if (best[1] < 0.2) return 'default'
  return best[0]
}

// ── ピン SVG ──────────────────────────────────────────────────

interface SuitTheme {
  suit: string
  dayBody: string
  nightBody: string
  dayStroke: string
  nightStroke: string
  symbolColor: string
}

const SUIT_THEMES: Record<SuitMode, SuitTheme> = {
  default: { suit: '', dayBody: '#C9A94D', nightBody: '#9a7a2e', dayStroke: '#9a7a2e', nightStroke: '#6a4e1e', symbolColor: 'white' },
  tournament: { suit: '♥', dayBody: '#DC143C', nightBody: '#8b0000', dayStroke: '#9b0e2c', nightStroke: '#5a0000', symbolColor: '#DC143C' },
  price: { suit: '♦', dayBody: '#C9A94D', nightBody: '#8a6525', dayStroke: '#9a7a2e', nightStroke: '#5a4010', symbolColor: '#C9A94D' },
  open: { suit: '♠', dayBody: '#292524', nightBody: '#111111', dayStroke: '#0a0a0a', nightStroke: '#000000', symbolColor: '#1C1917' },
  facility: { suit: '♣', dayBody: '#14532d', nightBody: '#052e16', dayStroke: '#0d3a18', nightStroke: '#021a0b', symbolColor: '#14532d' },
}

function createPinIcon(mode: SuitMode, isOpen: boolean): L.DivIcon {
  const theme = SUIT_THEMES[mode]
  const night = isCurrentlyNight()
  const closed = !isOpen

  const bodyColor = closed ? '#A8A29E' : (night ? theme.nightBody : theme.dayBody)
  const opacity = closed ? 0.65 : 1

  // 夜間 + 営業中: グロー付きシャドウ / それ以外: 通常シャドウ
  const dropShadow = night && !closed
    ? `drop-shadow(0 0 8px ${bodyColor}cc) drop-shadow(0 2px 6px rgba(0,0,0,0.5))`
    : `drop-shadow(0 2px 10px rgba(0,0,0,0.4))`

  if (mode === 'default') {
    // ポーカスブランドピン: ゴールドのポーカーチップ
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 58" width="48" height="58"
        style="opacity:${opacity};overflow:visible">
      <g style="filter:${dropShadow}">
        <circle cx="24" cy="22" r="17" fill="${bodyColor}" stroke="white" stroke-width="2.5"/>
        <circle cx="24" cy="22" r="12" fill="none" stroke="white" stroke-width="1.2" opacity="0.55"/>
      </g>
      <text x="24" y="22"
        text-anchor="middle" dominant-baseline="middle"
        font-size="15" fill="white" font-weight="900"
        font-family="-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif"
      >P</text>
      <ellipse cx="24" cy="56" rx="9" ry="2.8" fill="rgba(0,0,0,0.2)"/>
    </svg>`
    return L.divIcon({
      html: svg, className: 'pocus-pin',
      iconSize: [48, 58], iconAnchor: [24, 58], popupAnchor: [0, -60],
    })
  }

  // スーツモード: スーツシンボルそのものがピン（白アウトライン + カラーフィル）
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 58" width="48" height="58"
      style="opacity:${opacity};overflow:visible">
    <g style="filter:${dropShadow}">
      <text x="24" y="28"
        text-anchor="middle" dominant-baseline="middle"
        font-size="42" fill="white"
        font-family="Georgia,'Times New Roman',serif"
        stroke="white" stroke-width="6"
      >${theme.suit}</text>
      <text x="24" y="28"
        text-anchor="middle" dominant-baseline="middle"
        font-size="42" fill="${bodyColor}"
        font-family="Georgia,'Times New Roman',serif"
      >${theme.suit}</text>
    </g>
    <ellipse cx="24" cy="56" rx="9" ry="2.8" fill="rgba(0,0,0,0.2)"/>
  </svg>`
  return L.divIcon({
    html: svg, className: 'pocus-pin',
    iconSize: [48, 58], iconAnchor: [24, 58], popupAnchor: [0, -60],
  })
}

// ── ピンレイヤー ─────────────────────────────────────────────

interface PinLayerProps {
  pins: VenuePin[]
  filters: Filters
  onBoundsChange: (bbox: string) => void
}

function PinLayer({ pins, filters, onBoundsChange }: PinLayerProps) {
  const map = useMap()
  const navigate = useNavigate()
  const markersRef = useRef<L.Marker[]>([])

  useMapEvents({
    moveend: () => {
      const b = map.getBounds()
      onBoundsChange(
        `${b.getWest().toFixed(4)},${b.getSouth().toFixed(4)},${b.getEast().toFixed(4)},${b.getNorth().toFixed(4)}`
      )
    },
  })

  useEffect(() => {
    markersRef.current.forEach(m => m.remove())
    markersRef.current = []

    pins.forEach(pin => {
      const isOpen = pin.open_status === 'open'
      const mode = getPinSuitMode(pin)
      const marker = L.marker([pin.lat, pin.lng], {
        icon: createPinIcon(mode, isOpen),
      })

      const statusColor = pin.open_status === 'open' ? '#059669'
        : pin.open_status === 'closed' ? '#9ca3af' : '#d97706'
      const statusLabel = pin.open_status === 'open' ? '営業中'
        : pin.open_status === 'closed' ? '本日休業' : '時間不明'
      const safeName = escapeHtml(pin.display_name)
      const priceHtml = pin.price_entry_min
        ? `<p style="margin:4px 0 0;font-size:13px;font-weight:600;color:#92400e;">${escapeHtml(formatPrice(pin.price_entry_min))}</p>`
        : ''
      const tournamentHtml = pin.next_tournament_title
        ? `<p style="margin:4px 0 0;font-size:12px;color:#d97706;">🏆 ${escapeHtml(pin.next_tournament_title)}</p>`
        : ''
      const hoursHtml = pin.hours_today
        ? `<p style="margin:4px 0 0;font-size:12px;color:#78716c;">🕐 ${escapeHtml(pin.hours_today)}</p>`
        : ''

      marker.bindPopup(
        `<div style="padding:12px;min-width:200px;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif;">
          <p style="margin:0;font-size:14px;font-weight:700;color:#1c1917;line-height:1.3;">${safeName}</p>
          <span style="display:inline-flex;align-items:center;gap:4px;margin-top:6px;padding:2px 8px;
                       border-radius:999px;font-size:11px;font-weight:600;
                       background:${pin.open_status === 'open' ? '#ecfdf5' : '#f5f5f4'};
                       color:${statusColor};border:1px solid ${statusColor}40;">
            <span style="width:6px;height:6px;border-radius:50%;background:${statusColor};display:inline-block;"></span>
            ${statusLabel}
          </span>
          ${hoursHtml}${priceHtml}${tournamentHtml}
          <button
            class="pocus-detail-btn"
            style="margin-top:10px;width:100%;padding:6px 0;font-size:12px;font-weight:600;
                   background:#C9A94D;color:white;border:none;border-radius:8px;cursor:pointer;">
            詳細を見る →
          </button>
        </div>`,
        { className: 'pocus-popup' }
      )

      marker.on('popupopen', () => {
        const btn = marker.getPopup()?.getElement()?.querySelector('.pocus-detail-btn')
        btn?.addEventListener('click', () => navigate(`/venues/${pin.id}`))
      })

      marker.addTo(map)
      markersRef.current.push(marker)
    })

    return () => {
      markersRef.current.forEach(m => m.remove())
      markersRef.current = []
    }
  }, [pins, map, navigate])

  return null
}

// ── MapView ──────────────────────────────────────────────────

interface Props {
  pins: VenuePin[]
  filters: Filters
  onBoundsChange: (bbox: string) => void
}

export default function MapView({ pins, filters, onBoundsChange }: Props) {
  // 初回レンダリング時の時間帯で固定（タイルは頻繁に切り替えない）
  const [night] = useState(isCurrentlyNight())

  return (
    <MapContainer
      center={DEFAULT_MAP_CENTER}
      zoom={DEFAULT_MAP_ZOOM}
      style={{ height: '100%', width: '100%' }}
      zoomControl={false}
    >
      {night ? (
        <TileLayer
          url={TILE_URL_DARK}
          attribution={TILE_ATTRIBUTION_DARK}
          maxZoom={19}
        />
      ) : (
        <TileLayer
          url={TILE_URL_LIGHT}
          attribution={TILE_ATTRIBUTION_LIGHT}
          maxZoom={19}
        />
      )}
      <PinLayer pins={pins} filters={filters} onBoundsChange={onBoundsChange} />
    </MapContainer>
  )
}
