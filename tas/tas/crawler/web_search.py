"""新店舗の自動発見：ディレクトリSeed登録 + DuckDuckGo検索

- seed_directory_sources(): まとめサイトをSourceに登録
- search_discover(): 47都道府県を Web 検索して新店舗URLを発見
- discover_new_directories(): 新しいまとめサイトをWeb検索で発見
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tas.config import settings
from tas.constants import DEFAULT_DIRECTORY_RESCAN_HOURS
from tas.crawler.link_extractor import _EXTERNAL_SKIP_DOMAINS
from tas.db.models import Source, Venue

logger = logging.getLogger(__name__)


def _sanitize_for_log(value: str, max_len: int = 200) -> str:
    """ログ出力用にサニタイズ: 改行・制御文字を除去し、長さを制限する。"""
    return value.replace("\n", " ").replace("\r", " ")[:max_len]

# ── まとめサイト定義 ──

DIRECTORY_SITES: list[dict] = [
    {
        "url": "https://nexus-poker.jp/poker_spot/",
        "name": "Nexus Poker",
        "priority": 8,
    },
    {
        "url": "https://pokerfans.jp/spots",
        "name": "PokerFans",
        "priority": 8,
    },
    {
        "url": "https://poker-choice.com/amusement-casino/",
        "name": "Poker Choice",
        "priority": 7,
    },
    {
        "url": "https://pokerdiary.net/search/",
        "name": "PokerDiary",
        "priority": 7,
    },
    {
        "url": "https://casinojapan-inc.jp/pokerdirectory_2022/",
        "name": "Casino Japan",
        "priority": 7,
    },
    {
        "url": "https://poker.dmm.com/",
        "name": "DMM Poker",
        "priority": 7,
    },
]

# ── 47都道府県 ──

PREFECTURES: list[str] = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

# 検索クエリテンプレート
_SEARCH_QUERIES = [
    "アミューズメントポーカー {pref}",
    "ポーカールーム {pref}",
]

# DuckDuckGo Lite のベースURL
_DDG_LITE_URL = settings.ddg_lite_url

# 検索結果から除外するドメイン（SNS + 大手サービス + まとめサイト自身）
_SEARCH_SKIP_DOMAINS: set[str] = _EXTERNAL_SKIP_DOMAINS | {
    "nexus-poker.jp",
    "pokerfans.jp",
    "poker-choice.com",
    "pokerdiary.net",
    "casinojapan-inc.jp",
    "poker.dmm.com",
    "tabelog.com",
    "hotpepper.jp",
    "gnavi.co.jp",
    "retty.me",
    "tripadvisor.jp",
    "tripadvisor.com",
    "yelp.co.jp",
    "jalan.net",
    "travel.rakuten.co.jp",
    "ikyu.com",
}

# 検索結果のURLパターン：ポーカー関連度を判定
_POKER_URL_RE = re.compile(
    r"poker|ポーカー|bar|room|club|lounge|amusement|casino|カジノ|アミューズメント",
    re.I,
)

# ── まとめサイト自動発見用 ──

# 既知のまとめサイトドメイン（DIRECTORY_SITESから自動生成 + 除外対象）
_KNOWN_DIRECTORY_DOMAINS: set[str] = {
    urlparse(s["url"]).netloc for s in DIRECTORY_SITES
}

# まとめサイト発見用の検索クエリ
_DIRECTORY_DISCOVER_QUERIES: list[str] = [
    "ポーカー 店舗一覧 まとめ",
    "アミューズメントポーカー 一覧",
    "ポーカールーム 全国 まとめサイト",
    "ポーカースポット 日本 一覧",
    "poker spot japan list",
]

# まとめサイトっぽいURLパターン
_DIRECTORY_URL_RE = re.compile(
    r"一覧|まとめ|list|spots?|directory|search|店舗|map|poker",
    re.I,
)


async def seed_directory_sources(
    session: AsyncSession,
    dry_run: bool = False,
) -> int:
    """まとめサイトのURLをSourceに登録する（重複スキップ）"""
    added = 0
    for site in DIRECTORY_SITES:
        url = site["url"]
        existing = await session.execute(
            select(Source).where(Source.seed_url == url)
        )
        if existing.scalar_one_or_none():
            if dry_run:
                logger.info("[DRY RUN][SKIP] 既存: %.200s", url)
            continue

        if dry_run:
            logger.info("[DRY RUN][DIRECTORY] %s: %.200s", site['name'], url)
            added += 1
            continue

        source = Source(
            seed_url=url,
            seed_type="directory",
            page_kind="directory",
            priority=site["priority"],
            update_interval_hours=DEFAULT_DIRECTORY_RESCAN_HOURS,  # 1日1回再スキャン
            source_name=site["name"],
            status="pending",
        )
        session.add(source)
        added += 1

    if not dry_run and added > 0:
        await session.commit()

    logger.info("[DIRECTORY SEED] %d 件登録%s", added, "予定" if dry_run else "完了")
    return added


async def _ddg_search(query: str, client: httpx.AsyncClient) -> list[str]:
    """DuckDuckGo Lite で検索し、結果URLのリストを返す"""
    try:
        resp = await client.post(
            _DDG_LITE_URL,
            data={"q": query, "kl": "jp-jp"},
            headers={
                "User-Agent": settings.web_search_user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=settings.crawler_timeout_seconds,
        )
        if resp.status_code != 200:
            logger.warning(
                "[DDG] HTTP %d for query: %s",
                resp.status_code, _sanitize_for_log(query),
            )
            return []
    except Exception as exc:
        logger.warning(
            "[DDG] Request failed for query: %s: %s",
            _sanitize_for_log(query), _sanitize_for_log(str(exc)),
        )
        return []

    # HTMLから結果リンクを抽出
    urls: list[str] = []
    # DuckDuckGo Lite の結果リンクは <a class="result-link" href="..."> 形式
    # または <a rel="nofollow" href="..."> 形式
    for m in re.finditer(r'href="(https?://[^"]+)"', resp.text):
        url = m.group(1)
        # DuckDuckGo 自身のリンクを除外
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if "duckduckgo.com" in domain:
            continue
        urls.append(url)

    return urls


def _is_skip_domain(domain: str) -> bool:
    """除外ドメインかどうか判定"""
    for sd in _SEARCH_SKIP_DOMAINS:
        if domain == sd or domain.endswith(f".{sd}"):
            return True
    return False


async def search_discover(
    session: AsyncSession,
    prefectures: list[str] | None = None,
    dry_run: bool = False,
    delay_seconds: float | None = None,
    max_new: int | None = None,
) -> int:
    """
    47都道府県（または指定県）をDuckDuckGoで検索し、
    ポーカー店舗っぽいURLをSourceとして登録する。
    max_new: 今回追加する上限（Noneならsettings.discovery_daily_limit）
    """
    delay = delay_seconds if delay_seconds is not None else settings.discovery_search_delay_seconds
    target_prefs = prefectures if prefectures else PREFECTURES
    added = 0

    # 1日あたりの上限チェック
    limit = max_new if max_new is not None else settings.discovery_daily_limit
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = (
        await session.scalar(
            select(func.count(Source.id)).where(
                Source.seed_type == "web_search",
                Source.created_at >= today_start,
            )
        )
    ) or 0
    remaining = limit - today_count
    if remaining <= 0:
        logger.info("[SEARCH DISCOVER] 本日の上限(%d件)に達しています（既に%d件）", limit, today_count)
        return 0

    # 既存Venue.website_urlを取得して重複チェック用
    venue_urls_result = await session.execute(
        select(Venue.website_url).where(Venue.website_url.is_not(None)).limit(50000)
    )
    existing_venue_urls: set[str] = {
        u.rstrip("/") + "/" for u in venue_urls_result.scalars().all() if u
    }

    async with httpx.AsyncClient() as client:
        for pref in target_prefs:
            for template in _SEARCH_QUERIES:
                query = template.format(pref=pref)

                urls = await _ddg_search(query, client)

                for url in urls:
                    try:
                        parsed = urlparse(url)
                        domain = parsed.netloc.lower()
                    except Exception:
                        continue

                    if _is_skip_domain(domain):
                        continue

                    # 正規化
                    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}/"

                    # 既存Sourceチェック
                    existing = await session.execute(
                        select(Source).where(Source.seed_url == normalized)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    # 既存Venue.website_urlチェック
                    if normalized in existing_venue_urls:
                        continue

                    if dry_run:
                        logger.info("[DRY RUN][SEARCH] %s: %.200s", pref, normalized)
                        added += 1
                        if added >= remaining:
                            break
                        continue

                    source = Source(
                        seed_url=normalized,
                        seed_type="web_search",
                        region_hint=pref,
                        priority=5,
                        page_kind="home",
                        status="pending",
                    )
                    session.add(source)
                    added += 1
                    if added >= remaining:
                        break

                if added >= remaining:
                    break
                # レート制限：検索間に待機
                await asyncio.sleep(delay)

            if added >= remaining:
                break

    if not dry_run and added > 0:
        await session.commit()

    logger.info(
        "[SEARCH DISCOVER] %d 県検索 → %d 件%s（上限: %d, 本日既存: %d）",
        len(target_prefs), added, "発見予定" if dry_run else "登録完了",
        limit, today_count,
    )
    return added


async def discover_new_directories(
    session: AsyncSession,
    dry_run: bool = False,
    delay_seconds: float | None = None,
) -> int:
    """
    Web検索で新しいポーカーまとめサイト/ディレクトリサイトを発見し、
    Sourceとして登録する。既に登録済みのドメインはスキップする。
    """
    delay = delay_seconds if delay_seconds is not None else settings.discovery_search_delay_seconds
    # 既存のdirectory型SourceのドメインをDBから取得
    existing_result = await session.execute(
        select(Source.seed_url).where(Source.seed_type == "directory")
    )
    existing_dir_domains: set[str] = set()
    for url in existing_result.scalars().all():
        try:
            existing_dir_domains.add(urlparse(url).netloc.lower())
        except Exception:
            pass

    added = 0

    async with httpx.AsyncClient() as client:
        for query in _DIRECTORY_DISCOVER_QUERIES:
            urls = await _ddg_search(query, client)

            for url in urls:
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc.lower()
                except Exception:
                    continue

                # 除外ドメイン
                if _is_skip_domain(domain):
                    continue

                # 既知のまとめサイトドメインはスキップ
                if domain in existing_dir_domains or domain in _KNOWN_DIRECTORY_DOMAINS:
                    continue

                # URLにまとめサイトっぽいパターンがあるか確認
                full_url = parsed.geturl()
                if not _DIRECTORY_URL_RE.search(full_url) and not _POKER_URL_RE.search(full_url):
                    continue

                # 正規化
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}/"

                # 既存Sourceチェック
                existing = await session.execute(
                    select(Source).where(Source.seed_url == normalized)
                )
                if existing.scalar_one_or_none():
                    continue

                if dry_run:
                    logger.info("[DRY RUN][NEW DIRECTORY] %.200s", normalized)
                    added += 1
                    continue

                source = Source(
                    seed_url=normalized,
                    seed_type="directory",
                    page_kind="directory",
                    priority=6,
                    update_interval_hours=DEFAULT_DIRECTORY_RESCAN_HOURS,  # 1日1回再スキャン
                    status="pending",
                )
                session.add(source)
                # 同一ドメインから複数ページ登録しないように記録
                existing_dir_domains.add(domain)
                added += 1

            await asyncio.sleep(delay)

    if not dry_run and added > 0:
        await session.commit()

    logger.info(
        "[DIRECTORY DISCOVER] %d クエリ検索 → %d 件の新まとめサイト%s",
        len(_DIRECTORY_DISCOVER_QUERIES), added, "発見予定" if dry_run else "登録完了",
    )
    return added
