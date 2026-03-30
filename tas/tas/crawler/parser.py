"""HTML解析・フィールド抽出・確度付与（POCUS：ポーカー店舗向け）"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

from bs4 import BeautifulSoup

from tas.constants import (
    CONFIDENCE_SCORES,
    FIELD_MAX_LENGTHS,
    MAX_REASONABLE_PRICE,
    MAX_TABLE_COUNT,
    MAX_TABLE_COUNT_SIMPLE,
    MAX_TOURNAMENTS_PER_PAGE,
    SCAN_LIMIT_FULL,
    SCAN_LIMIT_LONG,
    SCAN_LIMIT_MEDIUM,
    SCAN_LIMIT_SHORT,
)

_SCAN_LIMIT_SHORT = SCAN_LIMIT_SHORT
_SCAN_LIMIT_MEDIUM = SCAN_LIMIT_MEDIUM
_SCAN_LIMIT_LONG = SCAN_LIMIT_LONG
_SCAN_LIMIT_FULL = SCAN_LIMIT_FULL

# コンプライアンス: 個人情報パターン除外
_PERSONAL_EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
)
_MOBILE_JP_RE = re.compile(r"(?<!\d)(070|080|090)[0-9\-]{9,11}(?!\d)")

# SNS URL パターン
_SNS_PATTERNS: dict[str, re.Pattern] = {
    "instagram": re.compile(r"instagram\.com/([^/?#\s]+)", re.I),
    "twitter": re.compile(r"(?:twitter|x)\.com/([^/?#\s]+)", re.I),
    "tiktok": re.compile(r"tiktok\.com/@([^/?#\s]+)", re.I),
    "facebook": re.compile(r"facebook\.com/([^/?#\s]+)", re.I),
    "youtube": re.compile(r"youtube\.com/(?:c/|channel/|@)?([^/?#\s]+)", re.I),
    "linktree": re.compile(r"linktr\.ee/([^/?#\s]+)", re.I),
}

# 予約ページパターン
_BOOKING_PATTERNS = re.compile(
    r"(?:contact|booking|book|予約|お問合|お問い合わせ|reserve|appointment)",
    re.I,
)

# booking_urlとして保存しない外部ドメイン（ディレクトリ・フォームサービス等）
_BOOKING_BLOCK_DOMAINS = {
    "docs.google.com",
    "forms.gle",
}

# 都道府県リスト
PREFECTURES = [
    "北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島",
    "茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川",
    "新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜",
    "静岡", "愛知", "三重", "滋賀", "京都", "大阪", "兵庫",
    "奈良", "和歌山", "鳥取", "島根", "岡山", "広島", "山口",
    "徳島", "香川", "愛媛", "高知", "福岡", "佐賀", "長崎",
    "熊本", "大分", "宮崎", "鹿児島", "沖縄",
]
_PREF_RE = re.compile("|".join(re.escape(p) for p in PREFECTURES))

# ── 住所パターン ──────────────────────────────────────────────
_PREF_UNION = "|".join(re.escape(p) for p in PREFECTURES)
# 郵便番号付き住所（〒XXX-XXXX 東京都...）
_ADDRESS_POSTAL_RE = re.compile(
    r"(?:〒\s*)?(\d{3}[-－]\d{4})\s+(?:" + _PREF_UNION + r")[^\n\t<>「」\[\]{}/]{3,50}"
)
# 都道府県始まりの住所
_ADDRESS_PREFIX_RE = re.compile(
    r"(?:" + _PREF_UNION + r")(?:都|道|府|県)?[^\n\t<>「」\[\]{}/]{5,50}"
)

# ── 営業時間パターン ──────────────────────────────────────────
_HOURS_KEYWORD_RE = re.compile(
    r"(?:営業時間|open\s*(?:hours?|time)|hours?)[^\S\n]*[：:：]?\s*(.{3,100})",
    re.I,
)
_TIME_RANGE_RE = re.compile(
    r"(\d{1,2}:\d{2})\s*[〜~～\-–—]\s*(?:翌\s*)?(\d{1,2}:\d{2}|翌\s*\d{1,2}:\d{2})"
)

# ── 料金パターン ──────────────────────────────────────────────
_PRICE_CONTEXT_RE = re.compile(
    r"(?:初回|入場料?|チャージ|バイイン|buy.?in|エントリー)[^\d¥￥\n]{0,20}"
    r"[¥￥]?\s*(\d{1,3}(?:[,，]\d{3})*)",
    re.I,
)
_PRICE_NOTE_RE = re.compile(
    r"(?:初回|入場料?|チャージ|バイイン|エントリー)[^\n。]{0,60}",
    re.I,
)

# ── P1フィールドパターン ──────────────────────────────────────
_DRINK_RE = re.compile(r"ワンドリンク|1ドリンク|1\s*drink|ワンオーダー", re.I)
_FOOD_RICH_RE = re.compile(
    r"フードメニュー|お食事|ランチ|ディナー|料理|フード充実|キッチン|お料理", re.I
)
_FOOD_BASIC_RE = re.compile(r"軽食|スナック|おつまみ|フードあり", re.I)
_FOOD_NONE_RE = re.compile(r"フードなし|お食事なし|フード(?:の提供)?はございません", re.I)
_TABLE_COUNT_RE = re.compile(
    r"(?:ポーカー卓|ポーカーテーブル|テーブル数)[^\d\n]{0,10}(\d+)\s*(?:台|卓|テーブル)?"
    r"|(\d+)\s*(?:台|卓)\s*(?:のポーカー|テーブル|ポーカー)",
    re.I,
)
_TABLE_SIMPLE_RE = re.compile(r"(\d+)\s*(?:台|卓)")
_PEAK_RE = re.compile(
    r"(?:ピーク|混雑|賑やか)[^\n]{0,20}?(\d{1,2}:\d{2}[^\n]{0,30})",
    re.I,
)

# ── トーナメントパターン ──────────────────────────────────────
_TOURNAMENT_KW_RE = re.compile(
    r"(?:トーナメント|大会|tournament|イベント(?!情報)|event)", re.I
)
_DATE_JP_RE = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")
_DATE_SLASH_RE = re.compile(
    r"(\d{1,2})[/／](\d{1,2})(?:[/／](\d{4}|\d{2}))?"
)
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_BUY_IN_RE = re.compile(
    r"(?:バイイン|buy.?in|参加費|エントリー(?:フィー|料)?)[^\d¥￥\n]{0,20}"
    r"[¥￥]?\s*(\d{1,3}(?:[,，]\d{3})*)",
    re.I,
)
_GUARANTEE_RE = re.compile(
    r"(?:ギャランティ|保証額?|guarantee)[^\d¥￥\n]{0,20}"
    r"[¥￥]?\s*(\d{1,3}(?:[,，]\d{3})*)",
    re.I,
)
_CAPACITY_RE = re.compile(
    r"定員\s*[：:]\s*(\d+)|(\d+)\s*名(?:様)?(?:限定|まで|定員)"
)


@dataclass
class ParsedTournament:
    """パース済み大会情報"""
    title: str
    url: str = ""
    start_at: Optional[datetime] = None
    buy_in: Optional[int] = None
    guarantee: Optional[int] = None
    capacity: Optional[int] = None
    status: str = "scheduled"


@dataclass
class ParsedPage:
    url: str
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    links: list[str] = field(default_factory=list)
    links_count: int = 0
    parse_method: str = "fallback"

    # 基本情報
    venue_name: str | None = None
    address: str | None = None
    area_prefecture: str | None = None
    area_city: str | None = None

    # P0
    hours_raw: str | None = None       # 営業時間テキスト（hours_today に保存）
    price_entry_min: int | None = None
    price_note: str | None = None

    # P1
    drink_required: bool | None = None
    food_level: str | None = None      # none / basic / rich
    table_count: int | None = None
    peak_time: str | None = None

    # メタ
    sns_links: dict[str, str] = field(default_factory=dict)
    booking_url: str | None = None
    summary: str | None = None

    # 大会情報
    tournaments: list[ParsedTournament] = field(default_factory=list)

    # フィールドごとの確度 (H/M/L)
    field_confidence: dict[str, str] = field(default_factory=dict)

    def overall_confidence(self) -> float:
        """H=1.0, M=0.7, L=0.4 の平均"""
        scores = CONFIDENCE_SCORES
        values = [scores.get(v, 0.4) for v in self.field_confidence.values()]
        return round(sum(values) / len(values), 2) if values else 0.0


# ── ユーティリティ ────────────────────────────────────────────

def _clean_text(text: str, max_len: int = FIELD_MAX_LENGTHS["default"]) -> str:
    return " ".join(text.split())[:max_len]


def _remove_personal_info(text: str) -> str:
    text = _PERSONAL_EMAIL_RE.sub("[EMAIL_REMOVED]", text)
    text = _MOBILE_JP_RE.sub("[PHONE_REMOVED]", text)
    return text


def _parse_amount(s: str) -> Optional[int]:
    """カンマ区切りの金額文字列を整数に変換"""
    cleaned = re.sub(r"[,，\s¥￥]", "", s)
    try:
        v = int(cleaned)
        return v if v > 0 else None
    except ValueError:
        return None


# ── フィールド抽出関数 ────────────────────────────────────────

def _extract_sns_links(soup: BeautifulSoup, base_url: str) -> dict[str, str]:
    try:
        result: dict[str, str] = {}
        all_links = [a.get("href", "") for a in soup.find_all("a", href=True)]
        full_text = " ".join(all_links)

        for platform, pattern in _SNS_PATTERNS.items():
            m = pattern.search(full_text)
            if m:
                for link in all_links:
                    if platform in link.lower() or ("x.com" in link and platform == "twitter"):
                        result[platform] = link
                        break
        return result
    except Exception as e:
        logger.warning("_extract_sns_links failed: %s", e)
        return {}


def _extract_booking_url(soup: BeautifulSoup, base_url: str) -> str | None:
    try:
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)
            full = urljoin(base_url, href)
            parsed = urlparse(full)
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc.lower() in _BOOKING_BLOCK_DOMAINS:
                continue
            if _BOOKING_PATTERNS.search(parsed.path) or _BOOKING_PATTERNS.search(text):
                return full
    except Exception as e:
        logger.warning("_extract_booking_url failed: %s", e)
    return None


_IG_RE = re.compile(r"instagram\.com/([^/?#\s]+)", re.I)


def _extract_prefecture(text: str) -> str | None:
    m = _PREF_RE.search(text)
    return m.group(0) if m else None


def _extract_city(text: str, prefecture: str | None) -> str | None:
    """都市名を簡易抽出（市区町村）"""
    search_text = text
    if prefecture:
        idx = text.find(prefecture)
        if idx >= 0:
            search_text = text[idx:]
    city_pattern = re.compile(r"([^\s　都道府県市区町村]{1,6}(?:市|区|町|村))")
    matches = city_pattern.findall(search_text)
    return matches[0] if matches else None


def _extract_address(body_text: str) -> Optional[str]:
    """住所を抽出する（郵便番号付き優先）"""
    try:
        m = _ADDRESS_POSTAL_RE.search(body_text)
        if m:
            return m.group(0).strip()[:FIELD_MAX_LENGTHS["address"]]
        m = _ADDRESS_PREFIX_RE.search(body_text[:_SCAN_LIMIT_FULL])
        if m:
            addr = m.group(0).strip()
            if len(addr) >= 8:
                return addr[:FIELD_MAX_LENGTHS["address"]]
    except Exception as e:
        logger.warning("_extract_address failed: %s", e)
    return None


def _extract_hours(soup: BeautifulSoup, body_text: str) -> Optional[str]:
    """営業時間テキストを抽出する"""
    try:
        m = _HOURS_KEYWORD_RE.search(body_text[:_SCAN_LIMIT_LONG])
        if m:
            raw = m.group(1).strip()
            if raw:
                return raw[:FIELD_MAX_LENGTHS["hours"]]
        ranges = _TIME_RANGE_RE.findall(body_text[:_SCAN_LIMIT_LONG])
        if ranges:
            return f"{ranges[0][0]}〜{ranges[0][1]}"
    except Exception as e:
        logger.warning("_extract_hours failed: %s", e)
    return None


def _extract_price(body_text: str) -> tuple[Optional[int], Optional[str]]:
    """初回入場料金（price_entry_min, price_note）を抽出する"""
    try:
        m = _PRICE_CONTEXT_RE.search(body_text[:_SCAN_LIMIT_LONG])
        if not m:
            return None, None
        price_int = _parse_amount(m.group(1))
        if price_int is None or price_int > MAX_REASONABLE_PRICE:  # 10万円超は誤検知
            return None, None
        note_m = _PRICE_NOTE_RE.search(body_text[:_SCAN_LIMIT_LONG])
        note = note_m.group(0).strip()[:FIELD_MAX_LENGTHS["price_note"]] if note_m else None
        return price_int, note
    except Exception as e:
        logger.warning("_extract_price failed: %s", e)
        return None, None


def _extract_drink_required(body_text: str) -> Optional[bool]:
    """ワンドリンク制かどうかを検出する"""
    try:
        return True if _DRINK_RE.search(body_text) else None
    except Exception as e:
        logger.warning("_extract_drink_required failed: %s", e)
        return None


def _extract_food_level(body_text: str) -> Optional[str]:
    """フードレベルを抽出する（none/basic/rich）"""
    try:
        if _FOOD_NONE_RE.search(body_text):
            return "none"
        if _FOOD_RICH_RE.search(body_text):
            return "rich"
        if _FOOD_BASIC_RE.search(body_text):
            return "basic"
    except Exception as e:
        logger.warning("_extract_food_level failed: %s", e)
    return None


def _extract_table_count(body_text: str) -> Optional[int]:
    """テーブル数を抽出する"""
    try:
        m = _TABLE_COUNT_RE.search(body_text[:_SCAN_LIMIT_MEDIUM])
        if m:
            n = m.group(1) or m.group(2)
            if n:
                v = int(n)
                if 1 <= v <= MAX_TABLE_COUNT:
                    return v
        if re.search(r"(?:テーブル|卓|ポーカー)", body_text[:_SCAN_LIMIT_SHORT]):
            m2 = _TABLE_SIMPLE_RE.search(body_text[:_SCAN_LIMIT_SHORT])
            if m2:
                v = int(m2.group(1))
                if 1 <= v <= MAX_TABLE_COUNT_SIMPLE:
                    return v
    except Exception as e:
        logger.warning("_extract_table_count failed: %s", e)
    return None


def _extract_peak_time(body_text: str) -> Optional[str]:
    """ピークタイムを抽出する"""
    try:
        m = _PEAK_RE.search(body_text[:_SCAN_LIMIT_MEDIUM])
        if m:
            return m.group(1).strip()[:FIELD_MAX_LENGTHS["peak_time"]]
    except Exception as e:
        logger.warning("_extract_peak_time failed: %s", e)
    return None


def _parse_tournament_datetime(text: str, ref_year: int) -> Optional[datetime]:
    """テキストから大会日時をパースする"""
    # YYYY年MM月DD日
    m = _DATE_JP_RE.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        t = _TIME_RE.search(text[m.end(): m.end() + 30])
        h, mi = (int(t.group(1)), int(t.group(2))) if t else (0, 0)
        try:
            return datetime(y, mo, d, h, mi)
        except ValueError:
            return None
    # MM/DD 形式
    m = _DATE_SLASH_RE.search(text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return None
        yr_raw = m.group(3)
        y = int(yr_raw) if yr_raw else ref_year
        if y < 100:
            y += 2000
        t = _TIME_RE.search(text[m.end(): m.end() + 30])
        h, mi = (int(t.group(1)), int(t.group(2))) if t else (0, 0)
        try:
            return datetime(y, mo, d, h, mi)
        except ValueError:
            return None
    return None


def _extract_tournaments(
    soup: BeautifulSoup, base_url: str, body_text: str
) -> list[ParsedTournament]:
    """大会情報のリストを抽出する"""
    try:
        tournaments: list[ParsedTournament] = []
        ref_year = datetime.now().year
        seen_titles: set[str] = set()

        for tag in soup.find_all(["li", "tr", "p", "div", "article", "section"]):
            try:
                text = tag.get_text(separator=" ", strip=True)

                if not _TOURNAMENT_KW_RE.search(text):
                    continue
                has_date = bool(_DATE_JP_RE.search(text) or _DATE_SLASH_RE.search(text))
                has_time = bool(_TIME_RE.search(text))
                if not (has_date or has_time):
                    continue
                if len(text) > 800:
                    continue

                heading = tag.find(re.compile(r"^h[1-6]$"))
                if heading:
                    title = heading.get_text(strip=True)[:80]
                else:
                    words = text.split()[:12]
                    title = " ".join(words)[:80]

                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                start_at = _parse_tournament_datetime(text, ref_year)

                buy_in: Optional[int] = None
                bm = _BUY_IN_RE.search(text)
                if bm:
                    buy_in = _parse_amount(bm.group(1))

                guarantee: Optional[int] = None
                gm = _GUARANTEE_RE.search(text)
                if gm:
                    guarantee = _parse_amount(gm.group(1))

                capacity: Optional[int] = None
                cm = _CAPACITY_RE.search(text)
                if cm:
                    n = cm.group(1) or cm.group(2)
                    try:
                        capacity = int(n) if n else None
                    except ValueError:
                        pass

                url = ""
                link = tag.find("a", href=True)
                if link:
                    href = link.get("href", "")
                    if href and not href.startswith(("#", "javascript:", "mailto:")):
                        url = urljoin(base_url, href)

                tournaments.append(
                    ParsedTournament(
                        title=title,
                        url=url,
                        start_at=start_at,
                        buy_in=buy_in,
                        guarantee=guarantee,
                        capacity=capacity,
                    )
                )

                if len(tournaments) >= MAX_TOURNAMENTS_PER_PAGE:
                    break
            except Exception as e:
                logger.warning("_extract_tournaments element failed: %s", e)
                continue

        return tournaments
    except Exception as e:
        logger.warning("_extract_tournaments failed: %s", e)
        return []


# ── メイン ────────────────────────────────────────────────────

def parse_html(url: str, html: str) -> ParsedPage:
    """HTMLを解析してPageオブジェクトを返す。解析失敗時は空のPageを返す（クラッシュしない）。"""
    try:
        return _parse_html_inner(url, html)
    except Exception as e:
        logger.error("parse_html critical failure for %.200s: %s", url, e, exc_info=True)
        return ParsedPage(url=url, parse_method="error")


def _parse_html_inner(url: str, html: str) -> ParsedPage:
    """parse_html の内部実装"""
    soup = BeautifulSoup(html, "lxml")
    page = ParsedPage(url=url)

    # ── 基本メタ情報 ──
    title_tag = soup.find("title")
    page.title = _clean_text(title_tag.get_text() if title_tag else "")

    meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    if meta_desc:
        page.meta_description = _clean_text(meta_desc.get("content", ""), max_len=FIELD_MAX_LENGTHS["meta_description"])

    h1_tag = soup.find("h1")
    page.h1 = _clean_text(h1_tag.get_text() if h1_tag else "")

    # ── リンク収集 ──
    all_links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if href and not href.startswith(("javascript:", "#", "mailto:", "tel:")):
            full = urljoin(url, href)
            if urlparse(full).scheme in ("http", "https"):
                all_links.append(full)
    page.links = list(dict.fromkeys(all_links))
    page.links_count = len(page.links)

    # ── 店舗名推定 ──
    og_title = soup.find("meta", property="og:title")
    og_site = soup.find("meta", property="og:site_name")

    og_title_raw = _clean_text(og_title.get("content", "") if og_title else "", max_len=200)
    og_site_raw = _clean_text(og_site.get("content", "") if og_site else "", max_len=100)

    def _split_title(t: str) -> str:
        for sep in [" | ", " - ", " – ", " — ", "｜"]:
            if sep in t:
                part = t.split(sep)[0].strip()
                if len(part) >= 2:
                    return part
        return t.strip()

    og_title_name = _split_title(og_title_raw) if og_title_raw else ""

    if og_title_name and og_site_raw and og_title_name == og_site_raw:
        page.venue_name = og_site_raw[:FIELD_MAX_LENGTHS["venue_name"]]
        page.field_confidence["venue_name"] = "H"
    elif og_title_name and og_site_raw and og_title_name != og_site_raw:
        page.venue_name = og_title_name[:FIELD_MAX_LENGTHS["venue_name"]]
        page.field_confidence["venue_name"] = "M"
    elif og_site_raw:
        page.venue_name = og_site_raw[:FIELD_MAX_LENGTHS["venue_name"]]
        page.field_confidence["venue_name"] = "H"
    elif og_title_name:
        page.venue_name = og_title_name[:FIELD_MAX_LENGTHS["venue_name"]]
        page.field_confidence["venue_name"] = "M"
    elif page.h1:
        page.venue_name = page.h1[:FIELD_MAX_LENGTHS["venue_name"]]
        page.field_confidence["venue_name"] = "L"
    elif page.title:
        page.venue_name = _split_title(page.title)[:FIELD_MAX_LENGTHS["venue_name"]]
        page.field_confidence["venue_name"] = "L"

    # ── ボディテキスト（各抽出の共通入力）──
    body_text = soup.get_text(separator=" ", strip=True)

    # ── エリア抽出 ──
    page.area_prefecture = _extract_prefecture(body_text)
    if page.area_prefecture:
        page.field_confidence["area_prefecture"] = "M"
        page.area_city = _extract_city(body_text, page.area_prefecture)
        if page.area_city:
            page.field_confidence["area_city"] = "M"

    # ── 住所抽出 ──
    page.address = _extract_address(body_text)
    if page.address:
        page.field_confidence["address"] = "M"

    # ── 営業時間抽出 ──
    page.hours_raw = _extract_hours(soup, body_text)
    if page.hours_raw:
        page.field_confidence["hours_raw"] = "M"

    # ── 料金抽出 ──
    page.price_entry_min, page.price_note = _extract_price(body_text)
    if page.price_entry_min is not None:
        page.field_confidence["price_entry_min"] = "M"

    # ── P1フィールド抽出 ──
    page.drink_required = _extract_drink_required(body_text)
    if page.drink_required is not None:
        page.field_confidence["drink_required"] = "M"

    page.food_level = _extract_food_level(body_text)
    if page.food_level is not None:
        page.field_confidence["food_level"] = "M"

    page.table_count = _extract_table_count(body_text)
    if page.table_count is not None:
        page.field_confidence["table_count"] = "M"

    page.peak_time = _extract_peak_time(body_text)
    if page.peak_time is not None:
        page.field_confidence["peak_time"] = "M"

    # ── summary（meta_descriptionベース）──
    if page.meta_description:
        safe = _remove_personal_info(page.meta_description)
        page.summary = safe[:FIELD_MAX_LENGTHS["summary"]]
        page.field_confidence["summary"] = "M"

    # ── SNSリンク ──
    page.sns_links = _extract_sns_links(soup, url)
    if page.sns_links:
        page.field_confidence["sns_links"] = "H"

    # ── 予約URL ──
    page.booking_url = _extract_booking_url(soup, url)
    if page.booking_url:
        page.field_confidence["booking_url"] = "M"

    # ── 大会情報抽出 ──
    page.tournaments = _extract_tournaments(soup, url, body_text)
    if page.tournaments:
        page.field_confidence["tournaments"] = "M"

    # ── parse_method判定 ──
    if og_site or og_title:
        page.parse_method = "pattern"
    elif page.h1:
        page.parse_method = "selector"
    else:
        page.parse_method = "fallback"

    return page
