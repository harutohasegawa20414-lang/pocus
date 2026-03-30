"""環境変数・設定管理"""

import logging
from functools import lru_cache
from typing import Optional
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    postgres_user: str = "pocus"
    postgres_password: str = ""
    postgres_db: str = "pocusdb"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: Optional[str] = None
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False  # SQLクエリのログ出力（debugとは独立）

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if self.database_url is None:
            self.database_url = (
                f"postgresql+asyncpg://{quote_plus(self.postgres_user)}:{quote_plus(self.postgres_password)}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self

    # API
    api_secret_key: str = ""
    admin_secret_key: str = ""

    # Rate limiting
    rate_limit_default: str = "100/minute"
    rate_limit_report: str = "5/hour"

    @model_validator(mode="after")
    def validate_secret_keys(self) -> "Settings":
        import secrets as _secrets

        _placeholder_keys = ("change-me-in-production", "change-me-admin-secret")
        for key_name in ("api_secret_key", "admin_secret_key"):
            val = getattr(self, key_name)
            if not val or val in _placeholder_keys:
                if not self.debug:
                    raise ValueError(
                        f"{key_name} must be set to a secure value in production. "
                        f"Set the {key_name.upper()} environment variable."
                    )
                # debug でも空/プレースホルダーの場合はランダム生成して安全に
                generated = _secrets.token_urlsafe(32)
                setattr(self, key_name, generated)
                _logger.warning(
                    "[CONFIG] %s was empty/placeholder — generated random value for debug. "
                    "Set a secure value before deploying.",
                    key_name,
                )
        return self

    api_host: str = "0.0.0.0"
    api_port: int = 6002
    debug: bool = False
    cors_allowed_origins: str = ""  # カンマ区切り。空の場合は cors_fallback_origins を使用
    cors_fallback_origins: str = "https://pocas-f0906.web.app,https://pocas-f0906.firebaseapp.com"

    # Crawler
    crawler_user_agent: str = "POCUS-Bot/0.1"
    crawler_rate_limit_seconds: float = 2.0
    crawler_max_retries: int = 3
    crawler_timeout_seconds: int = 30
    crawler_max_concurrent_domains: int = 5
    crawler_blocked_domains: str = "google.com,maps.google.com,google.co.jp"
    crawler_cooldown_fail_threshold: int = 3
    crawler_cooldown_hours: int = 24
    # この回数を超えると永続無効化（サーキットブレーカー）
    crawler_max_fails: int = 10
    crawler_robots_cache_ttl: int = 86400  # 24h
    crawler_max_redirects: int = 5
    crawler_accept_language: str = "ja,en;q=0.5"
    web_search_user_agent: str = "Mozilla/5.0 (compatible; POCUS/1.0)"

    # 外部API
    gsi_geocode_url: str = "https://msearch.gsi.go.jp/address-search/AddressSearch"
    ddg_lite_url: str = "https://lite.duckduckgo.com/lite/"
    geocoder_timeout: int = 10
    geocoder_cache_max: int = 1000
    discovery_search_delay_seconds: float = 3.0

    @property
    def blocked_domains_set(self) -> set[str]:
        return {d.strip() for d in self.crawler_blocked_domains.split(",") if d.strip()}

    # スケジューラ
    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = 30   # クロール定期実行の間隔
    scheduler_batch_size: int = 20         # 1回あたりの最大処理ソース数

    # 新店舗発見スケジューラ
    discovery_enabled: bool = True
    discovery_interval_hours: int = 24     # 発見実行の間隔（デフォルト: 1日1回）
    discovery_daily_limit: int = 50        # 1日あたりの新規発見上限

    # 名寄せ・重複排除閾値
    dedup_name_threshold: float = 0.85    # 重複と判定する名前類似度の下限
    dedup_proximity_km: float = 0.5       # 同一店舗とみなす距離（km）
    dedup_gray_zone_min: float = 0.5      # グレーゾーン類似度の下限
    dedup_gray_zone_max: float = 0.85     # グレーゾーン類似度の上限

    # フェーズ制御
    phase: int = 1                        # 機能フェーズ: 1=P0のみ, 2=P1追加, 3=フル機能
    enable_3d: bool = False               # 3Dビュー機能の有効化

    # データ鮮度モニタリング
    stale_days: int = 30                  # 鮮度切れとみなす日数

    # Google Sheets
    google_service_account_json: Optional[str] = None
    google_sheets_id: Optional[str] = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
