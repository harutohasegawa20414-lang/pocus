"""HTTPフェッチ + robots.txt + レート制御 + Playwright (SPA対応)"""

import asyncio
import collections
import hashlib
import ipaddress
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from tas.config import settings
from tas.constants import DOMAIN_LOCKS_MAX, ROBOTS_FETCH_TIMEOUT, SPA_FRAMEWORK_JP_THRESHOLD, SPA_MIN_JAPANESE_CHARS

# ── SSRF防御: プライベート/予約済みIPレンジへのリクエストをブロック ──


def _is_dangerous_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """IPアドレスが内部ネットワーク・予約済み・リンクローカル等に該当するか判定する。

    IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) も自動的にカバーする。
    """
    # IPv4-mapped IPv6の場合、内包されるIPv4アドレスもチェックする
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        ipv4 = addr.ipv4_mapped
        if ipv4.is_private or ipv4.is_loopback or ipv4.is_reserved or ipv4.is_link_local:
            return True

    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_reserved
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
    )


def _resolve_host(hostname: str) -> list[str]:
    """ホスト名をDNS解決し、解決済みIPアドレスのリストを返す。"""
    resolved: list[str] = []
    for info in socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP):
        ip_str = info[4][0]
        if ip_str not in resolved:
            resolved.append(ip_str)
    return resolved


def _check_url(url: str) -> tuple[bool, str | None]:
    """URLのホストが内部ネットワークを指していないか確認する。

    Returns:
        (is_private, resolved_ip): is_private=True の場合はブロック対象。
        resolved_ip は DNS rebinding 対策用に返す（呼び出し元が直接使用する）。
    """
    hostname = urlparse(url).hostname
    if not hostname:
        return True, None
    try:
        resolved_ips = _resolve_host(hostname)
        if not resolved_ips:
            return True, None
        for ip_str in resolved_ips:
            addr = ipaddress.ip_address(ip_str)
            if _is_dangerous_ip(addr):
                return True, None
        # 全IPが安全 → 最初の解決済みIPを返す
        return False, resolved_ips[0]
    except (socket.gaierror, ValueError):
        return True, None


def _is_private_url(url: str) -> bool:
    """URLのホストが内部ネットワークを指していないか確認する（後方互換）。"""
    is_private, _ = _check_url(url)
    return is_private

# SPA判定: scriptタグを除いた後の日本語テキスト量で判定
_SPA_FRAMEWORK_MARKERS = ["/_next/static/", "/_nuxt/", "data-reactroot", "data-n-head"]
# SPA_MIN_JAPANESE_CHARS: script除去後の日本語文字数がこれ未満ならSPA (constants.py で定義)


def _is_spa(html: str) -> bool:
    """SPAシェルか判定する。scriptタグを除いた後の日本語テキスト量で判定。"""
    if not html or len(html) < 500:
        return False
    import re
    # scriptとstyleを除去してから日本語テキスト量を計測
    stripped = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    stripped = re.sub(r"<style[\s\S]*?</style>", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"<[^>]+>", "", stripped)
    japanese = re.findall(r"[ぁ-んァ-ン一-龥]", stripped)
    jp_count = len(japanese)
    # 日本語テキストが極端に少ない場合はSPA
    if jp_count < SPA_MIN_JAPANESE_CHARS:
        return True
    # SPAフレームワークマーカーがあり、かつ日本語が少ない場合
    has_framework = any(m in html for m in _SPA_FRAMEWORK_MARKERS)
    return has_framework and jp_count < SPA_FRAMEWORK_JP_THRESHOLD


def _is_spa_framework(html: str) -> bool:
    """Next.js / Nuxt等のSPAフレームワークを使っているか判定する（コンテンツ量問わず）。"""
    return any(m in html for m in _SPA_FRAMEWORK_MARKERS)

# ドメインごとのレート制限管理（LRU方式で上限を設けて無制限の肥大化を防ぐ）
_DOMAIN_LOCKS_MAX = DOMAIN_LOCKS_MAX
_domain_locks: collections.OrderedDict[str, asyncio.Lock] = collections.OrderedDict()
_domain_last_access: dict[str, float] = {}

# robots.txtキャッシュ (domain -> (parser, expire_ts))
_robots_cache: dict[str, tuple[RobotFileParser, float]] = {}

# robots.txtフェッチ用タイムアウト
_ROBOTS_FETCH_TIMEOUT = ROBOTS_FETCH_TIMEOUT

# ブロック検知パターン
CAPTCHA_PATTERNS = [
    "captcha",
    "robot check",
    "are you human",
    "bot detection",
    "access denied",
    "cloudflare",
]


@dataclass
class FetchResult:
    url: str
    status_code: int = 0
    html: str = ""
    checksum: str = ""
    robots_blocked: bool = False
    error: str | None = None
    redirected_url: str | None = None

    @property
    def ok(self) -> bool:
        return self.status_code == 200 and not self.robots_blocked and self.error is None


def _get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _is_blocked_domain(url: str) -> bool:
    domain = _get_domain(url)
    for blocked in settings.blocked_domains_set:
        if domain == blocked or domain.endswith(f".{blocked}"):
            return True
    return False


async def _get_robots_parser(domain: str, scheme: str) -> RobotFileParser | None:
    now = time.time()
    if domain in _robots_cache:
        parser, expire = _robots_cache[domain]
        if now < expire:
            return parser

    robots_url = f"{scheme}://{domain}/robots.txt"
    try:
        async with httpx.AsyncClient(
            timeout=_ROBOTS_FETCH_TIMEOUT,
            headers={"User-Agent": settings.crawler_user_agent},
            follow_redirects=True,
        ) as client:
            resp = await client.get(robots_url)
            content = resp.text if resp.status_code == 200 else ""
    except Exception:
        content = ""

    parser = RobotFileParser()
    parser.parse(content.splitlines())
    _robots_cache[domain] = (parser, now + settings.crawler_robots_cache_ttl)
    return parser


def _is_robots_allowed(parser: RobotFileParser | None, url: str) -> bool:
    if parser is None:
        return True
    return parser.can_fetch(settings.crawler_user_agent, url)


async def _rate_limit(domain: str) -> None:
    if domain not in _domain_locks:
        # 上限を超えたら最も古いエントリを削除
        while len(_domain_locks) >= _DOMAIN_LOCKS_MAX:
            evicted_domain, _ = _domain_locks.popitem(last=False)
            _domain_last_access.pop(evicted_domain, None)
        _domain_locks[domain] = asyncio.Lock()
    else:
        # LRU: アクセスされたドメインを末尾に移動
        _domain_locks.move_to_end(domain)

    async with _domain_locks[domain]:
        now = time.monotonic()
        last = _domain_last_access.get(domain, 0.0)
        wait = settings.crawler_rate_limit_seconds - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _domain_last_access[domain] = time.monotonic()


def _detect_block(status_code: int, html: str) -> bool:
    if status_code in (403, 429):
        return True
    html_lower = html[:2000].lower()
    return any(p in html_lower for p in CAPTCHA_PATTERNS)


async def fetch(url: str) -> FetchResult:
    """URLをフェッチして結果を返す。robots.txt・レート制限・ブロック検知を行う。"""
    is_private, resolved_ip = _check_url(url)
    if is_private:
        raise ValueError(f"SSRF blocked: {url} resolves to a private IP")

    if _is_blocked_domain(url):
        return FetchResult(
            url=url,
            robots_blocked=True,
            error="blocked_domain",
        )

    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    scheme = parsed.scheme

    # robots.txtチェック
    parser = await _get_robots_parser(domain, scheme)
    if not _is_robots_allowed(parser, url):
        return FetchResult(
            url=url,
            robots_blocked=True,
            error="robots_block",
        )

    # レート制限
    await _rate_limit(domain)

    # DNS rebinding対策: 解決済みIPを直接使い、Hostヘッダで元のホスト名を送信する
    hostname = parsed.hostname or ""
    if resolved_ip and resolved_ip != hostname:
        # URLのホスト部分を解決済みIPに置換（IPv6はブラケットで囲む）
        ip_host = f"[{resolved_ip}]" if ":" in resolved_ip else resolved_ip
        port_suffix = f":{parsed.port}" if parsed.port else ""
        fetch_url = f"{scheme}://{ip_host}{port_suffix}{parsed.path}"
        if parsed.query:
            fetch_url += f"?{parsed.query}"
        host_header = parsed.netloc
    else:
        fetch_url = url
        host_header = None

    # HTTPリクエスト（exponential backoff）
    last_error: str | None = None
    for attempt in range(settings.crawler_max_retries):
        try:
            headers = {
                "User-Agent": settings.crawler_user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": settings.crawler_accept_language,
            }
            if host_header:
                headers["Host"] = host_header
            async with httpx.AsyncClient(
                timeout=settings.crawler_timeout_seconds,
                headers=headers,
                follow_redirects=True,
                max_redirects=settings.crawler_max_redirects,
            ) as client:
                resp = await client.get(fetch_url)

            html = resp.text
            redirected = str(resp.url) if str(resp.url) != url else None

            # SSRF防御: リダイレクト先が内部IPでないか再チェック
            if redirected and _is_private_url(redirected):
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    error="ssrf_redirect_blocked",
                    redirected_url=redirected,
                )

            if _detect_block(resp.status_code, html):
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    robots_blocked=False,
                    error="blocked_suspected",
                    redirected_url=redirected,
                )

            if resp.status_code != 200:
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    error=f"http_{resp.status_code}",
                    redirected_url=redirected,
                )

            checksum = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
            result = FetchResult(
                url=url,
                status_code=resp.status_code,
                html=html,
                checksum=checksum,
                redirected_url=redirected,
            )

            # SPAと判定されたらPlaywrightで再取得
            if _is_spa(html):
                pw_result = await _fetch_with_playwright(url)
                if pw_result.ok:
                    return pw_result
            # SPA框架（Next.js等）でhttpxより大幅に多いコンテンツが取れる場合はPlaywrightを優先
            elif _is_spa_framework(html):
                pw_result = await _fetch_with_playwright(url)
                if pw_result.ok and len(pw_result.html) > len(html) * 1.3:
                    return pw_result

            return result

        except httpx.TimeoutException:
            last_error = "timeout"
        except httpx.RequestError as exc:
            last_error = f"request_error:{type(exc).__name__}"

        # exponential backoff
        if attempt < settings.crawler_max_retries - 1:
            wait = 2 ** attempt
            await asyncio.sleep(wait)

    return FetchResult(
        url=url,
        status_code=0,
        error=last_error or "unknown_error",
    )


async def _fetch_with_playwright(url: str) -> FetchResult:
    """Playwrightでヘッドレスブラウザを使いJSレンダリング後のHTMLを取得する。

    NOTE: DNS rebinding はブラウザコンテキストでは悪用が困難（ブラウザ自身の
    same-origin policy や DNS ピンニングにより緩和される）。ただし SSRF チェックは
    フェッチ直前に再実行して、少なくともリクエスト開始時点での安全性を担保する。
    """
    if _is_private_url(url):
        raise ValueError(f"SSRF blocked: {url} resolves to a private IP")
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=settings.crawler_user_agent,
                locale="ja-JP",
            )
            page = await context.new_page()
            resp = await page.goto(url, wait_until="networkidle", timeout=settings.crawler_timeout_seconds * 1000)
            html = await page.content()
            await browser.close()

            status = resp.status if resp else 0
            checksum = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
            return FetchResult(
                url=url,
                status_code=status,
                html=html,
                checksum=checksum,
            )
    except Exception as exc:
        return FetchResult(
            url=url,
            status_code=0,
            error=f"playwright_error:{type(exc).__name__}",
        )


async def fetch_many(urls: list[str], concurrency: int | None = None) -> list[FetchResult]:
    """複数URLを並列フェッチする（ドメイン単位の並列数制限付き）"""
    sem = asyncio.Semaphore(concurrency or settings.crawler_max_concurrent_domains)

    async def _guarded(url: str) -> FetchResult:
        async with sem:
            return await fetch(url)

    return await asyncio.gather(*[_guarded(u) for u in urls])
