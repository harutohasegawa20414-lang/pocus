"""ディレクトリページからのリンク抽出・フィルタリング

ディレクトリページ（全国ポーカー店舗一覧等）をクロールした際に、
個別店舗ページと思われるURLを抽出してSourceに追加するための処理。
"""

import re
from urllib.parse import urlparse

from tas.constants import EXTRACT_EXTERNAL_LINKS_MAX, EXTRACT_VENUE_LINKS_MAX

# 外部リンク抽出時に除外するドメイン（SNS・大手サービス等）
_EXTERNAL_SKIP_DOMAINS: set[str] = {
    "twitter.com", "x.com",
    "instagram.com",
    "facebook.com", "fb.com",
    "youtube.com", "youtu.be",
    "tiktok.com",
    "line.me", "lin.ee",
    "linktr.ee",
    "google.com", "google.co.jp", "goo.gl",
    "maps.google.com",
    "tabelog.com",
    "hotpepper.jp",
    "gnavi.co.jp",
    "retty.me",
    "tripadvisor.jp", "tripadvisor.com",
    "wikipedia.org",
    "amazon.co.jp", "amazon.com",
    "apple.com", "apps.apple.com",
    "play.google.com",
    "note.com",
    "ameblo.jp",
    "github.com",
    "wordpress.org", "wordpress.com",
    "wp.com",
}

# ポーカー関連キーワード（外部リンクスコアリング用）
_POKER_HINT_RE = re.compile(
    r"poker|ポーカー|bar|room|club|lounge|amusement|casino|カジノ|アミューズメント",
    re.I,
)

# 個別スタジオページ以外の典型的なパスパターン（除外対象）
_SKIP_PATH_RE = re.compile(
    r"/page/\d+"             # ページネーション
    r"|/tag/"
    r"|/category/"
    r"|/search"
    r"|/login"
    r"|/register"
    r"|/signup"
    r"|/contact"
    r"|/about"
    r"|/privacy"
    r"|/terms"
    r"|/sitemap"
    r"|/feed"
    r"|/rss"
    r"|/wp-"
    r"|/admin"
    r"|\.xml$"
    r"|\.json$"
    r"|\.pdf$"
    r"|/news/"
    r"|/column/"
    r"|/blog/"
    r"|/magazine/"
    r"|/event/"
    r"|/campaign/"
    r"|/feature/"
    # 記事・ディレクトリ系パス（ゴミフィルター）
    r"|/area/"
    r"|/rule/"
    r"|/strategy/"
    r"|/interview/"
    r"|/review/"
    r"|/rec-online-casino/"
    r"|/bookmaker/"
    r"|/online-poker/"
    r"|/author/"
    r"|/writer/"
    r"|/toolsmaterials/"
    r"|/work/",
    re.I,
)

# 店舗ページっぽいパス（スコア加点）
_VENUE_HINT_RE = re.compile(
    r"/(venue|shop|store|poker|club|bar|room|place|lounge|スポット|店舗|店|bar)/",
    re.I,
)

# 数字IDを含むパス（個別ページの可能性高）
_NUMERIC_ID_RE = re.compile(r"/\d{2,}")


def extract_venue_links(
    links: list[str],
    source_url: str,
    max_links: int = EXTRACT_VENUE_LINKS_MAX,
) -> list[str]:
    """
    ディレクトリページのリンク一覧から、店舗個別ページと思われるURLを抽出する。

    フィルタリング基準:
    - 同一ドメインのリンクのみ
    - パス深さ >= 2（/venue/12345/ 等）
    - ページネーション・ユーティリティURLを除外
    - スコアリングして上位 max_links 件を返す
    """
    try:
        base = urlparse(source_url)
        base_domain = base.netloc.lower()
        base_path = base.path.rstrip("/")
    except Exception:
        return []

    scored: list[tuple[int, str]] = []
    seen: set[str] = set()

    for link in links:
        try:
            parsed = urlparse(link)
        except Exception:
            continue

        # 同一ドメインのみ
        if parsed.netloc.lower() != base_domain:
            continue

        path = parsed.path

        # 自分自身を除外
        if path.rstrip("/") == base_path:
            continue

        # クエリ・フラグメント付きURLを除外
        if parsed.query or parsed.fragment:
            continue

        # スキップパターンに一致
        if _SKIP_PATH_RE.search(path):
            continue

        # 正規化してdedup（末尾スラッシュを統一）
        normalized = f"{parsed.scheme}://{parsed.netloc}{path.rstrip('/')}/"
        if normalized in seen:
            continue
        seen.add(normalized)

        # パス深さ（最低2階層: /studio/12345/ など）
        depth = len([p for p in path.split("/") if p])
        if depth < 2:
            continue

        # スコアリング（高いほど個別店舗ページらしい）
        score = 0
        if _VENUE_HINT_RE.search(path):
            score += 3
        if _NUMERIC_ID_RE.search(path):
            score += 2
        if depth == 2:
            score += 1  # 深すぎない適度な深さ

        scored.append((score, normalized))

    # スコア降順ソートして上位を返す
    scored.sort(key=lambda x: -x[0])
    return [url for _, url in scored[:max_links]]


def extract_external_venue_links(
    links: list[str],
    source_url: str,
    max_links: int = EXTRACT_EXTERNAL_LINKS_MAX,
) -> list[str]:
    """
    ディレクトリページのリンク一覧から、外部ドメインの店舗公式サイトと思われるURLを抽出する。

    - 同一ドメインのリンクは除外（既存の extract_venue_links で処理）
    - SNS・食べログ等の大手サービスドメインを除外
    - ポーカー関連キーワードでスコアリング
    - 上位 max_links 件を返す
    """
    try:
        base = urlparse(source_url)
        base_domain = base.netloc.lower()
    except Exception:
        return []

    scored: list[tuple[int, str]] = []
    seen: set[str] = set()

    for link in links:
        try:
            parsed = urlparse(link)
        except Exception:
            continue

        # スキーム確認
        if parsed.scheme not in ("http", "https"):
            continue

        domain = parsed.netloc.lower()
        if not domain:
            continue

        # 同一ドメインは除外
        if domain == base_domain:
            continue

        # 除外ドメイン判定（完全一致またはサブドメイン一致）
        skip = False
        for sd in _EXTERNAL_SKIP_DOMAINS:
            if domain == sd or domain.endswith(f".{sd}"):
                skip = True
                break
        if skip:
            continue

        # クエリ・フラグメントを除去して正規化
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}/"
        if normalized in seen:
            continue
        seen.add(normalized)

        # スコアリング
        score = 0
        url_text = f"{domain}{parsed.path}"
        if _POKER_HINT_RE.search(url_text):
            score += 3
        # パスが浅い（トップページ or /about 程度）→ 公式サイトのトップの可能性が高い
        depth = len([p for p in parsed.path.split("/") if p])
        if depth <= 1:
            score += 1

        scored.append((score, normalized))

    scored.sort(key=lambda x: -x[0])
    return [url for _, url in scored[:max_links]]
