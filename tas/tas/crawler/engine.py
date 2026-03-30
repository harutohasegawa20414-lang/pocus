"""クロールオーケストレータ（POCUS：ポーカー店舗向け）"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tas.config import settings
from tas.constants import (
    DEDUP_MAX_VENUES,
    DEFAULT_DIRECTORY_RESCAN_HOURS,
    GRAY_ZONE_PROXIMITY_MULTIPLIER,
    JUNK_FILTER_NAME_MAX_LEN,
    LOG_FIELD_MAX_LEN,
    MAX_RESCAN_INTERVAL_HOURS,
    TOURNAMENT_TITLE_SIMILARITY_THRESHOLD,
)
from tas.crawler.fetcher import fetch
from tas.crawler.geocoder import geocode, geocode_area
from tas.crawler.link_extractor import extract_external_venue_links, extract_venue_links
from tas.crawler.normalizer import (
    build_match_evidence,
    find_duplicate_candidate,
    find_gray_zone_candidates,
    name_similarity,
    prefecture_to_coords,
)
from tas.crawler.parser import ParsedTournament, parse_html
from tas.db.models import CrawlLog, Source, Tournament, Venue, VenueMergeCandidate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ゴミフィルター: 自動発見で見つかった非店舗ページを除外する
# ---------------------------------------------------------------------------

# A. URLパスパターンで除外
_JUNK_PATH_RE = re.compile(
    r"/area/"
    r"|/rule/"
    r"|/strategy/"
    r"|/interview/"
    r"|/review/"
    r"|/rec-online-casino/"
    r"|/bookmaker/"
    r"|/online-poker/"
    r"|/author/"
    r"|/writer/"
    r"|/contact/"
    r"|/toolsmaterials/"
    r"|/work/",
    re.I,
)

# B. 名前に含まれる記事キーワード
_ARTICLE_KEYWORDS = (
    "おすすめ", "ランキング", "最新版", "徹底解説", "完全ガイド",
    "まとめ", "入門", "解説", "紹介", "とは？",
)

# B. 都道府県名そのもの（名前がこれだけなら店舗ではない）
_PREFECTURES = {
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
}

# C. オンカジ/ギャンブル系キーワード
_GAMBLING_KEYWORDS = (
    "オンラインカジノ", "ブックメーカー", "スロット",
    "バカラ", "ブラックジャック", "ボーナス",
)

_NAME_MAX_LEN = JUNK_FILTER_NAME_MAX_LEN


def _sanitize_for_log(value: str, max_len: int = 200) -> str:
    """ログ出力用にサニタイズ: 改行・制御文字を除去し、長さを制限する。"""
    return value.replace("\n", " ").replace("\r", " ")[:max_len]


def _classify_venue(name: str, url: str, page) -> str | None:
    """
    自動発見されたページがポーカー店舗かゴミかを判定する。

    Returns:
        None  — 通過（店舗として作成してOK）
        str   — スキップ理由（ログ用）
    """
    safe_name = _sanitize_for_log(name)

    # A. URLパスパターン
    try:
        path = urlparse(url).path
    except Exception:
        path = ""
    if _JUNK_PATH_RE.search(path):
        return f"junk_url_path: {_sanitize_for_log(path)}"

    # B. 名前ベース
    if name in _PREFECTURES:
        return f"prefecture_name: {safe_name}"
    if len(name) > _NAME_MAX_LEN:
        return f"name_too_long ({len(name)} chars): {safe_name[:50]}"
    for kw in _ARTICLE_KEYWORDS:
        if kw in name:
            return f"article_keyword '{kw}' in name: {safe_name}"

    # C. コンテンツベース — オンカジ/ギャンブル系
    for kw in _GAMBLING_KEYWORDS:
        if kw in name:
            return f"gambling_keyword '{kw}' in name: {safe_name}"

    # C. 店舗情報ゼロ（住所なし＋営業時間なし＋料金なし）
    has_address = bool(getattr(page, "address", None))
    has_hours = bool(getattr(page, "hours_raw", None))
    has_price = getattr(page, "price_entry_min", None) is not None
    if not has_address and not has_hours and not has_price:
        return f"no_venue_info (address/hours/price all empty): {safe_name}"

    return None  # 通過


class CrawlEngine:
    def __init__(self, session: AsyncSession, dry_run: bool = False) -> None:
        self.session = session
        self.dry_run = dry_run

    async def run(self, limit: int = 10, source_id: Optional[str] = None) -> int:
        """pending + cooldown期限切れのソースをlimit件クロールする"""
        now = datetime.now(timezone.utc)
        query = select(Source).where(
            or_(
                Source.status == "pending",
                (Source.status == "cooldown") & (Source.cooldown_until <= now),
                # update_interval_hours が設定されたdone済みソースの再クロール
                (Source.status == "done")
                & Source.update_interval_hours.is_not(None)
                & Source.last_run_at.is_not(None)
                & (
                    Source.last_run_at
                    + func.make_interval(0, 0, 0, 0, Source.update_interval_hours)
                    <= now
                ),
            )
        )
        if source_id:
            query = query.where(Source.id == source_id)
        query = query.order_by(Source.priority.desc(), Source.created_at).limit(limit)

        result = await self.session.execute(query)
        sources = result.scalars().all()

        count = 0
        for source in sources:
            try:
                await self._process_source(source)
                count += 1
            except Exception as exc:
                logger.error(
                    "Error processing source %s: %s",
                    source.id, _sanitize_for_log(str(exc)),
                )
                if not self.dry_run:
                    source.status = "error"
                    source.error_reason = "parse_fail"
                    source.fail_count += 1
                    await self.session.commit()
            finally:
                if not self.dry_run:
                    await self._sheets_write_back(source)

        return count

    async def _sheets_write_back(self, source: Source) -> None:
        """sheet_row_numがあればGoogleスプレッドシートにステータスを書き戻す"""
        if not source.sheet_row_num:
            return
        if not settings.google_service_account_json or not settings.google_sheets_id:
            return
        try:
            from tas.seeds.sheets import SheetsClient
            client = SheetsClient()
            await asyncio.to_thread(
                client.write_back,
                row_num=source.sheet_row_num,
                status=source.status,
                error_reason=source.error_reason,
            )
        except Exception as exc:
            logger.warning(
                "Sheets write-back failed for source %s: %s",
                source.id, _sanitize_for_log(str(exc)),
            )

    def _is_directory(self, source: Source) -> bool:
        """ディレクトリ型ソース（リンクフォローモード）かどうかを判定する"""
        return source.seed_type == "directory" or source.page_kind in ("directory",)

    async def _process_source(self, source: Source) -> None:
        if not self.dry_run:
            source.status = "running"
            source.last_run_at = datetime.now(timezone.utc)
            await self.session.commit()

        fetch_result = await fetch(source.seed_url)

        log = CrawlLog(
            source_id=source.id,
            url=fetch_result.url,
            status_code=fetch_result.status_code,
            robots_blocked=fetch_result.robots_blocked,
            error=fetch_result.error,
            crawled_at=datetime.now(timezone.utc),
        )

        if not fetch_result.ok:
            if not self.dry_run:
                self.session.add(log)
                source.fail_count += 1
                source.error_reason = fetch_result.error
                await self._decay_venue_confidence(source)
                if source.fail_count >= settings.crawler_max_fails:
                    # サーキットブレーカー: 永続無効化
                    source.status = "disabled"
                    logger.warning(
                        "[CIRCUIT BREAKER] %s disabled after %d failures",
                        _sanitize_for_log(source.seed_url), source.fail_count,
                    )
                elif source.fail_count >= settings.crawler_cooldown_fail_threshold:
                    source.status = "cooldown"
                    source.cooldown_until = datetime.now(timezone.utc) + timedelta(
                        hours=settings.crawler_cooldown_hours
                    )
                else:
                    source.status = "error"
                await self.session.commit()
            return

        # HTML解析
        page = parse_html(fetch_result.url, fetch_result.html)

        log.fetched_title = page.title[:LOG_FIELD_MAX_LEN] if page.title else None
        log.meta_description = page.meta_description[:LOG_FIELD_MAX_LEN] if page.meta_description else None
        log.h1 = page.h1[:LOG_FIELD_MAX_LEN] if page.h1 else None
        log.links_count = page.links_count
        log.checksum = fetch_result.checksum
        log.parse_method = page.parse_method
        log.field_confidence = page.field_confidence

        if self._is_directory(source):
            await self._process_directory(source, fetch_result, page, log)
        else:
            await self._process_venue_page(source, fetch_result, page, log)

    async def _process_directory(self, source: Source, fetch_result, page, log: CrawlLog) -> None:
        """
        ディレクトリページ処理：個別店舗URLを抽出して新規Sourceに追加する。
        同一ドメインのリンク＋外部ドメインの公式サイトリンクの両方を抽出する。
        店舗情報の抽出は行わない。
        """
        venue_links = extract_venue_links(page.links, source.seed_url)
        external_links = extract_external_venue_links(page.links, source.seed_url)

        if self.dry_run:
            logger.info(
                "[DRY RUN][DIRECTORY] %.200s  total links=%d, same_domain=%d, external=%d",
                source.seed_url, page.links_count, len(venue_links), len(external_links),
            )
            for link in venue_links[:10]:
                logger.info("    → %.200s", link)
            if len(venue_links) > 10:
                logger.info("    ... 他 %d 件（同一ドメイン）", len(venue_links) - 10)
            for link in external_links[:10]:
                logger.info("    ⇒ %.200s", link)
            if len(external_links) > 10:
                logger.info("    ... 他 %d 件（外部）", len(external_links) - 10)
            return

        # 既存Venue.website_urlを取得して重複チェック用に使う
        venue_urls_result = await self.session.execute(
            select(Venue.website_url).where(Venue.website_url.is_not(None)).limit(50000)
        )
        existing_venue_urls: set[str] = {
            u.rstrip("/") + "/" for u in venue_urls_result.scalars().all() if u
        }

        # 新規Sourceを追加（同一ドメイン）
        added = 0
        for link in venue_links:
            existing = await self.session.execute(
                select(Source).where(Source.seed_url == link)
            )
            if existing.scalar_one_or_none():
                continue

            new_source = Source(
                seed_url=link,
                seed_type="venue_official",
                region_hint=source.region_hint,
                priority=max(1, source.priority - 1),
                page_kind="home",
                status="pending",
            )
            self.session.add(new_source)
            added += 1

        # 外部リンクもSourceとして登録
        ext_added = 0
        for link in external_links:
            # 既存Sourceとの重複チェック
            existing = await self.session.execute(
                select(Source).where(Source.seed_url == link)
            )
            if existing.scalar_one_or_none():
                continue
            # 既存Venue.website_urlとの重複チェック
            if link in existing_venue_urls:
                continue

            new_source = Source(
                seed_url=link,
                seed_type="web_search",
                region_hint=source.region_hint,
                priority=max(1, source.priority - 2),
                page_kind="home",
                status="pending",
            )
            self.session.add(new_source)
            ext_added += 1

        self.session.add(log)
        source.status = "done"
        source.canonical_url = fetch_result.redirected_url or source.seed_url
        source.fail_count = 0
        source.error_reason = None

        # 新規ソースが0件 → このまとめサイトは枯れている → 再スキャン間隔を倍に
        total_new = added + ext_added
        if total_new == 0 and source.update_interval_hours:
            old_interval = source.update_interval_hours
            source.update_interval_hours = min(old_interval * 2, MAX_RESCAN_INTERVAL_HOURS)  # 最大1年
            logger.info(
                "[DIRECTORY BACKOFF] %s — 新規0件、再スキャン間隔 %dh → %dh",
                _sanitize_for_log(source.seed_url), old_interval, source.update_interval_hours,
            )
        elif total_new > 0 and source.update_interval_hours:
            # 新規があれば通常間隔に戻す
            source.update_interval_hours = DEFAULT_DIRECTORY_RESCAN_HOURS

        await self.session.commit()

        logger.info(
            "[DIRECTORY] %s → links=%d, new_sources=%d (same-domain), %d (external)",
            _sanitize_for_log(source.seed_url), page.links_count, added, ext_added,
        )

    async def _process_venue_page(self, source: Source, fetch_result, page, log: CrawlLog) -> None:
        """
        店舗個別ページ処理：店舗情報を抽出してDBに保存する。
        """
        if self.dry_run:
            coords = await geocode_area(page.area_prefecture, page.area_city)
            if coords is None:
                coords = prefecture_to_coords(page.area_prefecture or "")
            logger.info(
                "[DRY RUN][VENUE] %.200s  name=%r  address=%r  area=%s %s  "
                "coords=%s  hours=%r  price=%s  drink=%s food=%s tables=%s  "
                "tournaments=%d  sns=%s  confidence=%s",
                source.seed_url, page.venue_name, page.address,
                page.area_prefecture, page.area_city, coords,
                page.hours_raw, page.price_entry_min,
                page.drink_required, page.food_level, page.table_count,
                len(page.tournaments), list(page.sns_links.keys()),
                page.overall_confidence(),
            )
            return

        self.session.add(log)

        venue: Optional[Venue] = None
        # parse_method=="error" の場合はパース失敗とみなし upsert をスキップする
        if page.venue_name and page.parse_method != "error":
            venue = await self._upsert_venue(source, page)

        # 大会情報の保存
        if venue and page.tournaments:
            for t in page.tournaments:
                await self._upsert_tournament(venue, t)

        source.status = "done"
        source.canonical_url = fetch_result.redirected_url or source.seed_url
        source.fail_count = 0
        source.error_reason = None
        await self.session.commit()

        logger.info(
            "[VENUE] %s → name=%s, tournaments=%d, conf=%.2f",
            _sanitize_for_log(source.seed_url),
            _sanitize_for_log(page.venue_name or ""),
            len(page.tournaments),
            page.overall_confidence(),
        )

    async def _upsert_venue(self, source: Source, page) -> "Venue | None":
        """店舗を新規作成または更新する（名寄せ込み）"""
        result = await self.session.execute(
            select(Venue).where(Venue.visibility_status == "visible").limit(DEDUP_MAX_VENUES)
        )
        existing_venues = [
            {
                "name": v.name,
                "website_url": v.website_url,
                "id": v.id,
                "address": v.address,
                "lat": float(v.lat) if v.lat is not None else None,
                "lng": float(v.lng) if v.lng is not None else None,
            }
            for v in result.scalars().all()
        ]

        # 座標解決を先に行い重複チェックに使用する
        coords = None
        if page.address:
            coords = await geocode(page.address)
        if coords is None:
            coords = await geocode_area(page.area_prefecture, page.area_city)
        if coords is None:
            coords = prefecture_to_coords(page.area_prefecture or "")

        dup = find_duplicate_candidate(
            name=page.venue_name,
            website_url=source.seed_url,
            existing=existing_venues,
            address=page.address,
            lat=coords[0] if coords else None,
            lng=coords[1] if coords else None,
            name_threshold=settings.dedup_name_threshold,
            proximity_km=settings.dedup_proximity_km,
        )

        venue: Venue | None = None
        if dup:
            venue = await self.session.get(Venue, dup["id"])
            if venue:
                # エリア情報（空欄のみ更新）
                if page.area_prefecture and not venue.area_prefecture:
                    venue.area_prefecture = page.area_prefecture
                if page.area_city and not venue.area_city:
                    venue.area_city = page.area_city
                # 住所（空欄のみ更新）
                if page.address and not venue.address:
                    venue.address = page.address
                # 座標（空欄のみ更新）
                if coords and not venue.lat:
                    venue.lat, venue.lng = coords
                # SNSリンク（マージ）
                if page.sns_links:
                    venue.sns_links = {**(venue.sns_links or {}), **page.sns_links}
                # summary（空欄のみ更新）
                if page.summary and not venue.summary:
                    venue.summary = page.summary
                # P0フィールド（新規取得値で上書き）
                if page.hours_raw:
                    venue.hours_today = page.hours_raw
                if page.price_entry_min is not None:
                    venue.price_entry_min = page.price_entry_min
                    if page.price_note is not None:
                        venue.price_note = page.price_note
                # P1フィールド（空欄のみ更新）
                if page.drink_required is not None and venue.drink_required is None:
                    venue.drink_required = page.drink_required
                if page.food_level and not venue.food_level:
                    venue.food_level = page.food_level
                if page.table_count and not venue.table_count:
                    venue.table_count = page.table_count
                if page.peak_time and not venue.peak_time:
                    venue.peak_time = page.peak_time
                # 根拠URLを追記
                existing_sources = venue.sources or []
                if source.seed_url not in existing_sources:
                    venue.sources = existing_sources + [source.seed_url]
                venue.match_confidence = page.overall_confidence()
                venue.field_confidence = page.field_confidence or None
                venue.last_updated_at = datetime.now(timezone.utc)
        else:
            # ゴミフィルター: 自動発見の新規作成前に判定
            skip_reason = _classify_venue(page.venue_name, source.seed_url, page)
            if skip_reason:
                logger.info(
                    "[JUNK FILTER] skipped: %s — %s",
                    _sanitize_for_log(source.seed_url), skip_reason,
                )
                return None

            venue = Venue(
                name=page.venue_name,
                address=page.address or "",
                website_url=source.seed_url,
                area_prefecture=page.area_prefecture,
                area_city=page.area_city,
                lat=coords[0] if coords else None,
                lng=coords[1] if coords else None,
                sns_links=page.sns_links or None,
                sources=[source.seed_url],
                summary=page.summary,
                match_confidence=page.overall_confidence(),
                field_confidence=page.field_confidence or None,
                open_status="unknown",
                hours_today=page.hours_raw,
                price_entry_min=page.price_entry_min,
                price_note=page.price_note,
                drink_required=page.drink_required,
                food_level=page.food_level,
                table_count=page.table_count,
                peak_time=page.peak_time,
                verification_status="unverified",
                visibility_status="visible",
                last_updated_at=datetime.now(timezone.utc),
            )
            self.session.add(venue)
            await self.session.flush()

            # グレーゾーン重複の検出 → VenueMergeCandidateに登録
            await self._register_merge_candidates(venue, existing_venues, page)

        return venue

    async def _upsert_tournament(self, venue: Venue, t: ParsedTournament) -> None:
        """大会情報を新規作成または更新する"""
        # 既存の大会を検索（同一venue + start_at一致 or タイトル類似）
        query = select(Tournament).where(Tournament.venue_id == venue.id)
        if t.start_at:
            query = query.where(Tournament.start_at == t.start_at)
        result = await self.session.execute(query)
        existing_list = result.scalars().all()

        existing: Optional[Tournament] = None
        for ex in existing_list:
            if ex.title == t.title:
                existing = ex
                break
            if name_similarity(ex.title, t.title) > TOURNAMENT_TITLE_SIMILARITY_THRESHOLD:
                existing = ex
                break

        now = datetime.now(timezone.utc)

        if existing:
            # 更新（取れた値のみ上書き）
            if t.buy_in is not None:
                existing.buy_in = t.buy_in
            if t.guarantee is not None:
                existing.guarantee = t.guarantee
            if t.capacity is not None:
                existing.capacity = t.capacity
            if t.url:
                existing.url = t.url
            existing.last_updated_at = now
        else:
            tournament = Tournament(
                venue_id=venue.id,
                title=t.title,
                start_at=t.start_at,
                buy_in=t.buy_in,
                guarantee=t.guarantee,
                capacity=t.capacity,
                url=t.url or "",
                status=t.status,
                last_updated_at=now,
            )
            self.session.add(tournament)

    async def _decay_venue_confidence(self, source: Source) -> None:
        """フェッチ失敗時、関連する店舗の field_confidence を H→M→L に劣化させる"""
        _DECAY: dict[str, str] = {"H": "M", "M": "L", "L": "L"}
        try:
            result = await self.session.execute(
                select(Venue).where(Venue.sources.contains([source.seed_url]))
            )
            for venue in result.scalars():
                if venue.field_confidence:
                    venue.field_confidence = {
                        k: _DECAY.get(v, v) for k, v in venue.field_confidence.items()
                    }
        except Exception as exc:
            logger.warning(
                "[DECAY] field_confidence decay failed for %s: %s",
                _sanitize_for_log(source.seed_url), _sanitize_for_log(str(exc)),
            )

    async def _register_merge_candidates(self, venue: Venue, existing: list[dict], page) -> None:
        """名前類似度がグレーゾーン(0.5〜0.85)の既存店舗をVenueMergeCandidateに登録する"""
        venue_lat = float(venue.lat) if venue.lat is not None else None
        venue_lng = float(venue.lng) if venue.lng is not None else None
        gray = find_gray_zone_candidates(
            name=page.venue_name,
            website_url=venue.website_url,
            existing=existing,
            address=venue.address or None,
            lat=venue_lat,
            lng=venue_lng,
            min_score=settings.dedup_gray_zone_min,
            max_score=settings.dedup_gray_zone_max,
            proximity_km=settings.dedup_proximity_km * GRAY_ZONE_PROXIMITY_MULTIPLIER,  # グレーゾーンは広め
        )
        for candidate in gray:
            already = await self.session.execute(
                select(VenueMergeCandidate).where(
                    or_(
                        (VenueMergeCandidate.venue_a_id == venue.id)
                        & (VenueMergeCandidate.venue_b_id == candidate["id"]),
                        (VenueMergeCandidate.venue_a_id == candidate["id"])
                        & (VenueMergeCandidate.venue_b_id == venue.id),
                    )
                )
            )
            if already.scalar_one_or_none():
                continue

            evidence = build_match_evidence(
                name=page.venue_name,
                website_url=venue.website_url,
                candidate=candidate,
                address=venue.address or None,
                lat=venue_lat,
                lng=venue_lng,
            )
            self.session.add(
                VenueMergeCandidate(
                    venue_a_id=venue.id,
                    venue_b_id=candidate["id"],
                    similarity_score=evidence.get("name_similarity"),
                    evidence=evidence,
                    status="pending",
                )
            )
