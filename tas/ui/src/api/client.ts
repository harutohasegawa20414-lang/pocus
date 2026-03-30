import type {
  VenuePinsResponse,
  VenueListResponse,
  VenueDetail,
  AdminStats,
  RecentEntry,
  SourceItem,
  ReportItem,
  MergeCandidateItem,
  DiscoveryVenueItem,
} from '../types/api'
import { getAllSeedPins, getAllSeedCards, getSeedVenueDetail, FILTER_MAP } from '../data/seedData'
import { getFirestorePins, getFirestoreCards, getFirestoreVenueDetail } from '../lib/firestore'
import { EARTH_RADIUS_KM, NEAR_RADIUS_KM, MS_PER_DAY, MS_PER_HOUR, DEFAULT_PIN_LIMIT, DEFAULT_LIST_LIMIT, DEFAULT_CRAWL_BATCH, DEFAULT_STALE_DAYS, DEFAULT_RECENT_LIMIT } from '../constants'

const BASE = '/api'

// ── Admin token ──

let _adminToken: string | null = sessionStorage.getItem('adminToken')

export function setAdminToken(token: string): void {
  _adminToken = token
  sessionStorage.setItem('adminToken', token)
}

export function clearAdminToken(): void {
  _adminToken = null
  sessionStorage.removeItem('adminToken')
}

export function hasAdminToken(): boolean {
  return _adminToken !== null
}

// ── HTTP helpers ──

async function get<T>(path: string, params?: Record<string, string | number | boolean | string[] | undefined>): Promise<T> {
  const sp = new URLSearchParams()
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null) continue
      if (Array.isArray(v)) {
        v.forEach(item => sp.append(k, item))
      } else {
        sp.set(k, String(v))
      }
    }
  }
  const query = sp.toString()
  const res = await fetch(`${BASE}${path}${query ? '?' + query : ''}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function adminGet<T>(path: string, params?: Record<string, string | number | boolean | string[] | undefined>): Promise<T> {
  const sp = new URLSearchParams()
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null) continue
      if (Array.isArray(v)) {
        v.forEach(item => sp.append(k, item))
      } else {
        sp.set(k, String(v))
      }
    }
  }
  const query = sp.toString()
  const res = await fetch(`${BASE}${path}${query ? '?' + query : ''}`, {
    headers: { 'Authorization': `Bearer ${_adminToken ?? ''}` },
  })
  if (res.status === 401) throw new Error('401')
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export interface PinsParams {
  bbox?: string
  prefecture?: string[]
  open_now?: boolean
  has_tournament?: boolean
  tournament_month_from?: number
  tournament_month_to?: number
  jack_tournament?: boolean
  queen_tournament?: boolean
  king_tournament?: boolean
  food_level?: string
  min_tables?: number
  drink_rich?: boolean
  user_lat?: number
  user_lng?: number
  limit?: number
}

export async function fetchPins(params: PinsParams = {}): Promise<VenuePinsResponse> {
  try {
    return await get<VenuePinsResponse>('/map/pins', {
      ...params,
      limit: params.limit ?? DEFAULT_PIN_LIMIT,
    })
  } catch {
    // API 不通時は Firestore → seedData の順にフォールバック
    let pins: import('../types/api').VenuePin[]
    try {
      const fsPins = await getFirestorePins()
      pins = fsPins.length > 0 ? fsPins : getAllSeedPins()
    } catch {
      pins = getAllSeedPins()
    }
    // 都道府県フィルター
    if (params.prefecture && params.prefecture.length > 0) {
      pins = pins.filter(p => params.prefecture!.includes(p.area_prefecture ?? ''))
    }
    // 営業中フィルター
    if (params.open_now) {
      pins = pins.filter(p => p.open_status === 'open')
    }
    // 大会ありフィルター
    if (params.has_tournament) {
      pins = pins.filter(p => p.next_tournament_title != null)
    }
    // フード充実フィルター
    if (params.food_level === 'rich') {
      pins = pins.filter(p => FILTER_MAP[p.id]?.foodLevel === 'rich')
    }
    // テーブル数フィルター
    if (params.min_tables) {
      pins = pins.filter(p => (FILTER_MAP[p.id]?.tableCount ?? 0) >= params.min_tables!)
    }
    // ドリンク充実フィルター
    if (params.drink_rich) {
      pins = pins.filter(p => FILTER_MAP[p.id]?.drinkRich === true)
    }
    // bbox フィルター（地図の表示範囲）
    if (params.bbox) {
      const [swLng, swLat, neLng, neLat] = params.bbox.split(',').map(Number)
      if (!isNaN(swLng) && !isNaN(swLat) && !isNaN(neLng) && !isNaN(neLat)) {
        pins = pins.filter(p =>
          p.lat >= swLat && p.lat <= neLat &&
          p.lng >= swLng && p.lng <= neLng
        )
      }
    }
    // 近くの店舗（50km以内に絞り込み ＋ 距離順ソート）
    if (params.user_lat != null && params.user_lng != null) {
      const uLat = params.user_lat
      const uLng = params.user_lng
      pins = pins.filter(p => haversineDistance(uLat, uLng, p.lat, p.lng) <= NEAR_RADIUS_KM)
      pins = [...pins].sort((a, b) =>
        haversineDistance(uLat, uLng, a.lat, a.lng) -
        haversineDistance(uLat, uLng, b.lat, b.lng)
      )
    }
    return { pins, total: pins.length }
  }
}

export interface ListParams {
  prefecture?: string[]
  open_status?: string
  has_tournament?: boolean
  tournament_month_from?: number
  tournament_month_to?: number
  jack_tournament?: boolean
  queen_tournament?: boolean
  king_tournament?: boolean
  food_level?: string
  min_tables?: number
  drink_rich?: boolean
  sort?: 'updated' | 'name' | 'near'
  user_lat?: number
  user_lng?: number
  offset?: number
  limit?: number
}

export async function fetchVenues(params: ListParams = {}): Promise<VenueListResponse> {
  try {
    return await get<VenueListResponse>('/venues/', {
      ...params,
      limit: params.limit ?? DEFAULT_LIST_LIMIT,
    })
  } catch {
    // API 不通時は Firestore → seedData の順にフォールバック
    let items: import('../types/api').VenueCard[]
    try {
      const fsCards = await getFirestoreCards()
      items = fsCards.length > 0 ? fsCards : getAllSeedCards()
    } catch {
      items = getAllSeedCards()
    }
    // 都道府県フィルター
    if (params.prefecture && params.prefecture.length > 0) {
      items = items.filter(v => params.prefecture!.includes(v.area_prefecture ?? ''))
    }
    // 営業中フィルター
    if (params.open_status === 'open') {
      items = items.filter(v => v.open_status === 'open')
    }
    // 大会ありフィルター
    if (params.has_tournament) {
      items = items.filter(v => v.next_tournament_title != null)
    }
    // フード充実フィルター
    if (params.food_level === 'rich') {
      items = items.filter(v => v.food_level === 'rich')
    }
    // テーブル数フィルター
    if (params.min_tables) {
      items = items.filter(v => (v.table_count ?? 0) >= params.min_tables!)
    }
    // ドリンク充実フィルター
    if (params.drink_rich) {
      items = items.filter(v => v.drink_required === true)
    }
    // 近くの店舗（50km以内に絞り込み ＋ 距離順ソート）
    if (params.sort === 'near' && params.user_lat != null && params.user_lng != null) {
      const uLat = params.user_lat
      const uLng = params.user_lng
      items = items.filter(v => haversineDistance(uLat, uLng, v.lat ?? 0, v.lng ?? 0) <= NEAR_RADIUS_KM)
      items = [...items].sort((a, b) =>
        haversineDistance(uLat, uLng, a.lat ?? 0, a.lng ?? 0) -
        haversineDistance(uLat, uLng, b.lat ?? 0, b.lng ?? 0)
      )
    }
    const offset = params.offset ?? 0
    const limit = params.limit ?? DEFAULT_LIST_LIMIT
    const sliced = items.slice(offset, offset + limit)
    return { items: sliced, total: items.length, offset, limit }
  }
}

/** 2点間の距離(km)を簡易計算（Haversine公式） */
function haversineDistance(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = EARTH_RADIUS_KM
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export async function fetchVenueDetail(id: string): Promise<VenueDetail> {
  try {
    return await get<VenueDetail>(`/venue/${id}`)
  } catch {
    // API 不通時は Firestore → seedData の順にフォールバック
    try {
      const fsDetail = await getFirestoreVenueDetail(id)
      if (fsDetail) return fsDetail
    } catch {
      // Firestore も不通 → seedData にフォールバック
    }
    const detail = getSeedVenueDetail(id)
    if (detail) return detail
    throw new Error(`Venue ${id} not found`)
  }
}

// ── Admin API ──

export async function fetchAdminStats(): Promise<AdminStats> {
  return adminGet<AdminStats>('/admin/stats')
}

export async function fetchRecentEntries(limit = DEFAULT_RECENT_LIMIT): Promise<RecentEntry[]> {
  return adminGet<RecentEntry[]>('/admin/recent', { limit })
}

export async function fetchSources(): Promise<SourceItem[]> {
  return adminGet<SourceItem[]>('/admin/sources')
}

export async function fetchReports(status?: string): Promise<ReportItem[]> {
  return adminGet<ReportItem[]>('/admin/reports', status ? { status } : {})
}

export async function fetchMergeCandidates(status?: string): Promise<MergeCandidateItem[]> {
  return adminGet<MergeCandidateItem[]>('/admin/merge-candidates', status ? { status } : {})
}

export async function resolveReport(
  reportId: string,
  body: { status: 'resolved' | 'rejected'; resolved_by?: string; note?: string }
): Promise<ReportItem> {
  const res = await fetch(`${BASE}/admin/reports/${reportId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${_adminToken ?? ''}`,
    },
    body: JSON.stringify(body),
  })
  if (res.status === 401) throw new Error('401')
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<ReportItem>
}

// ── Admin Crawl API ──

export interface CrawlTriggerResponse {
  processed: number
  message: string
}

export interface CrawlResetStaleResponse {
  reset_count: number
  message: string
}

export interface SchedulerStatus {
  enabled: boolean
  interval_minutes: number
  batch_size: number
  discovery_enabled: boolean
  discovery_interval_hours: number
}

export async function triggerCrawl(limit = DEFAULT_CRAWL_BATCH, sourceId?: string): Promise<CrawlTriggerResponse> {
  const params: Record<string, string> = { limit: String(limit) }
  if (sourceId) params.source_id = sourceId
  const sp = new URLSearchParams(params)
  const res = await fetch(`${BASE}/admin/crawl/trigger?${sp}`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${_adminToken ?? ''}` },
  })
  if (res.status === 401) throw new Error('401')
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<CrawlTriggerResponse>
}

export async function resetStaleSources(staleDays = DEFAULT_STALE_DAYS): Promise<CrawlResetStaleResponse> {
  const sp = new URLSearchParams({ stale_days: String(staleDays) })
  const res = await fetch(`${BASE}/admin/crawl/reset-stale?${sp}`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${_adminToken ?? ''}` },
  })
  if (res.status === 401) throw new Error('401')
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<CrawlResetStaleResponse>
}

export async function fetchSchedulerStatus(): Promise<SchedulerStatus> {
  return adminGet<SchedulerStatus>('/admin/crawl/scheduler-status')
}

// ── Admin Discovery API ──

export interface DiscoveryTriggerResponse {
  directories_added: number
  search_added: number
  message: string
}

export async function triggerDiscovery(
  mode: 'directories' | 'search' | 'all' = 'all'
): Promise<DiscoveryTriggerResponse> {
  const sp = new URLSearchParams({ mode })
  const res = await fetch(`${BASE}/admin/discovery/trigger?${sp}`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${_adminToken ?? ''}` },
  })
  if (res.status === 401) throw new Error('401')
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<DiscoveryTriggerResponse>
}

// ── Admin Discovery Review API ──

export async function fetchDiscoveryPending(): Promise<DiscoveryVenueItem[]> {
  return adminGet<DiscoveryVenueItem[]>('/admin/discovery/pending')
}

export async function reviewDiscoveryVenue(
  venueId: string,
  action: 'approve' | 'reject'
): Promise<DiscoveryVenueItem> {
  const res = await fetch(`${BASE}/admin/discovery/venues/${venueId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${_adminToken ?? ''}`,
    },
    body: JSON.stringify({ action }),
  })
  if (res.status === 401) throw new Error('401')
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<DiscoveryVenueItem>
}

export async function bulkReviewDiscoveryVenues(
  venueIds: string[],
  action: 'approve' | 'reject'
): Promise<{ updated: number; action: string }> {
  const res = await fetch(`${BASE}/admin/discovery/bulk-review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${_adminToken ?? ''}`,
    },
    body: JSON.stringify({ venue_ids: venueIds, action }),
  })
  if (res.status === 401) throw new Error('401')
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<{ updated: number; action: string }>
}

// ── フォーマッター ──

export function formatPrice(price: number | null): string {
  if (price == null) return ''
  return `¥${price.toLocaleString('ja-JP')}〜`
}

export function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.round((target.getTime() - today.getTime()) / MS_PER_DAY)

  const time = d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
  if (diffDays === 0) return `今日 ${time}`
  if (diffDays === 1) return `明日 ${time}`
  if (diffDays > 1 && diffDays <= 7)
    return `${d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric', weekday: 'short' })} ${time}`
  return `${d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' })} ${time}`
}

export function formatUpdatedAt(iso: string | null): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / MS_PER_HOUR)
  if (h < 1) return '1時間以内'
  if (h < 24) return `${h}時間前`
  const d = Math.floor(h / 24)
  if (d < 30) return `${d}日前`
  return new Date(iso).toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' })
}

