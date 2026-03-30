// プロジェクト共有定数
export const EARTH_RADIUS_KM = 6371
export const NEAR_RADIUS_KM = 50
export const MS_PER_DAY = 86_400_000
export const MANY_TABLES_THRESHOLD = 6
export const DEFAULT_PIN_LIMIT = 500
export const DEFAULT_MAP_CENTER: [number, number] = [35.6762, 139.6503]  // 東京
export const DEFAULT_MAP_ZOOM = 11
export const TILE_URL_DARK = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
export const TILE_ATTRIBUTION_DARK = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
export const TILE_URL_LIGHT = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
export const TILE_ATTRIBUTION_LIGHT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

// Admin defaults
export const DEFAULT_LIST_LIMIT = 30
export const DEFAULT_CRAWL_BATCH = 20
export const DEFAULT_STALE_DAYS = 30
export const DEFAULT_RECENT_LIMIT = 30
export const MS_PER_HOUR = 3_600_000
export const GPS_TIMEOUT_MS = 10_000
export const GPS_MAX_AGE_MS = 60_000
export const PIN_JITTER_RANGE = 0.004
