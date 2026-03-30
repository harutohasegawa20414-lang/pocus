export type OpenStatus = 'open' | 'closed' | 'unknown'
export type FoodLevel = 'none' | 'basic' | 'rich'

export interface VenuePin {
  id: string
  type: 'venue'
  lat: number
  lng: number
  display_name: string
  open_status: OpenStatus
  hours_today: string | null
  price_entry_min: number | null
  next_tournament_title: string | null
  next_tournament_start: string | null
  area_prefecture: string | null
  area_city: string | null
  verification_status: string
  detail_url: string
  booking_url: string | null
  // スコア算出用
  food_level: FoodLevel | null
  table_count: number | null
  drink_required: boolean | null
}

export interface VenuePinsResponse {
  pins: VenuePin[]
  total: number
}

export interface VenueCard {
  id: string
  name: string
  open_status: OpenStatus
  hours_today: string | null
  price_entry_min: number | null
  price_note: string | null
  next_tournament_title: string | null
  next_tournament_start: string | null
  next_tournament_url: string | null
  drink_required: boolean | null
  food_level: FoodLevel | null
  table_count: number | null
  peak_time: string | null
  address: string | null
  area_prefecture: string | null
  area_city: string | null
  lat: number | null
  lng: number | null
  last_updated_at: string | null
  updated_at: string | null
  data_age_days: number | null
  sources: string[] | null
}

export interface VenueListResponse {
  items: VenueCard[]
  total: number
  offset: number
  limit: number
}

export interface TournamentBrief {
  id: string
  title: string
  start_at: string | null
  buy_in: number | null
  guarantee: number | null
  capacity: number | null
  url: string
  status: string
}

export interface VenueDetail extends VenueCard {
  website_url: string | null
  sns_links: Record<string, string> | null
  summary: string | null
  verification_status: string
  visibility_status: string
  match_confidence: number | null
  field_confidence: Record<string, string> | null
  country_code: string
  locale: string
  time_zone: string
  created_at: string
  updated_at: string
  tournaments: TournamentBrief[]
}

// ── 管理ダッシュボード ──

export interface AdminStats {
  total_venues: number
  total_tournaments: number
  total_sources: number
  pending_sources: number
  running_sources: number
  error_sources: number
  done_sources: number
  disabled_sources: number
  blocked_suspected_sources: number
  total_crawl_logs: number
  low_confidence_venues: number
  pending_reports: number
  pending_merge_candidates: number
}

export interface RecentEntry {
  id: string
  name: string
  type: string
  area_prefecture: string | null
  area_city: string | null
  match_confidence: number | null
  created_at: string
}

export interface SourceItem {
  id: string
  seed_url: string
  seed_type: string | null
  status: string
  fail_count: number
  last_run_at: string | null
  error_reason: string | null
}

export interface ReportItem {
  id: string
  report_type: string
  entity_type: string
  entity_id: string
  status: string
  reporter_name: string | null
  details: string | null
  resolved_by: string | null
  created_at: string
}

export interface MergeCandidateItem {
  id: string
  venue_a_id: string
  venue_b_id: string
  similarity_score: number | null
  evidence: Record<string, unknown> | null
  status: string
  resolved_at: string | null
  resolved_by: string | null
  resolution_note: string | null
  created_at: string
}

export interface DiscoveryVenueItem {
  id: string
  name: string
  address: string | null
  area_prefecture: string | null
  area_city: string | null
  website_url: string | null
  sources: string[] | null
  match_confidence: number | null
  hours_today: string | null
  price_entry_min: number | null
  price_note: string | null
  table_count: number | null
  food_level: string | null
  summary: string | null
  lat: number | null
  lng: number | null
  created_at: string
}
