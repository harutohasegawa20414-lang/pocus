"""プロジェクト共有定数（POCUS）"""

from importlib.metadata import version as pkg_version

# ── バージョン ──
try:
    VERSION = pkg_version("pocus")
except Exception:
    VERSION = "0.1.0"

# ── 地理 ──
EARTH_RADIUS_KM = 6371.0
NEAR_MAX_DISTANCE_DEG = 0.45  # ~50km（35度付近の緯度）
NEAR_MAX_DISTANCE_DEG_SQ = NEAR_MAX_DISTANCE_DEG ** 2

# ── 大会バイイン閾値 ──
JACK_MAX_BUYIN = 1000    # Jack: 1,000円以下
QUEEN_MAX_BUYIN = 3000   # Queen: 3,000円以下

# ── 低信頼度閾値 ──
LOW_CONFIDENCE_THRESHOLD = 0.5

# ── テーブル数フィルタ ──
MANY_TABLES_THRESHOLD = 6

# ── クローラー ──
LOG_FIELD_MAX_LEN = 500
MAX_RESCAN_INTERVAL_HOURS = 8760  # 1年
DEFAULT_DIRECTORY_RESCAN_HOURS = 24
MAX_TOURNAMENTS_PER_PAGE = 10
MAX_REASONABLE_PRICE = 100_000     # 10万円超は誤検知とみなす
MAX_TABLE_COUNT = 200
MAX_TABLE_COUNT_SIMPLE = 100
SPA_FRAMEWORK_JP_THRESHOLD = 200
SPA_MIN_JAPANESE_CHARS = 50

# ── 名寄せ ──
TOURNAMENT_TITLE_SIMILARITY_THRESHOLD = 0.8
ADDRESS_MATCH_THRESHOLD = 0.6
GRAY_ZONE_ADDRESS_THRESHOLD = 0.4
GRAY_ZONE_PROXIMITY_MULTIPLIER = 4
DEDUP_MAX_VENUES = 1000

# ── 信頼度スコアマッピング ──
CONFIDENCE_SCORES = {"H": 1.0, "M": 0.7, "L": 0.4}

# ── フィールド最大長 ──
FIELD_MAX_LENGTHS = {
    "default": 500,
    "address": 100,
    "hours": 120,
    "price_note": 80,
    "peak_time": 50,
    "summary": 300,
    "venue_name": 100,
    "meta_description": 300,
}

# ── 時間定数 ──
MS_PER_DAY = 86_400_000

# ── デフォルト地図 ──
DEFAULT_MAP_CENTER = (35.6762, 139.6503)  # 東京
DEFAULT_MAP_ZOOM = 11

# ── タイルサーバー ──
TILE_URL_DARK = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
TILE_ATTRIBUTION_DARK = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
TILE_URL_LIGHT = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_ATTRIBUTION_LIGHT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

# ── デフォルトピン取得上限 ──
DEFAULT_PIN_LIMIT = 500
NEAR_RADIUS_KM = 50

# ── 管理画面 ──
STALE_VENUES_LIMIT = 200

# ── クローラー追加定数 ──
JUNK_FILTER_NAME_MAX_LEN = 40
DOMAIN_LOCKS_MAX = 1000
ROBOTS_FETCH_TIMEOUT = 10

# ── リンク抽出デフォルト ──
EXTRACT_VENUE_LINKS_MAX = 200
EXTRACT_EXTERNAL_LINKS_MAX = 100

# ── パーサースキャン範囲 ──
SCAN_LIMIT_SHORT = 3000
SCAN_LIMIT_MEDIUM = 5000
SCAN_LIMIT_LONG = 6000
SCAN_LIMIT_FULL = 10000
