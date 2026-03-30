"""fetcher.py のユニットテスト"""

import pytest
import respx
import httpx

from tas.crawler.fetcher import (
    _detect_block,
    _get_domain,
    _is_blocked_domain,
    fetch,
)


def test_get_domain():
    assert _get_domain("https://example.com/path") == "example.com"
    assert _get_domain("http://sub.example.co.jp/") == "sub.example.co.jp"


def test_is_blocked_domain():
    assert _is_blocked_domain("https://google.com/search") is True
    assert _is_blocked_domain("https://maps.google.com/") is True
    assert _is_blocked_domain("https://example-poker.jp/") is False


def test_detect_block_status_code():
    assert _detect_block(403, "") is True
    assert _detect_block(429, "") is True
    assert _detect_block(200, "") is False


def test_detect_block_captcha_html():
    html = "<html><body>Please complete the CAPTCHA to continue</body></html>"
    assert _detect_block(200, html) is True


def test_detect_block_cloudflare():
    html = "<html><body>Checking if Cloudflare...</body></html>"
    assert _detect_block(200, html) is True


def test_detect_block_normal():
    html = "<html><body><h1>Tokyo Poker Room</h1></body></html>"
    assert _detect_block(200, html) is False


@pytest.mark.asyncio
async def test_fetch_blocked_domain():
    result = await fetch("https://google.com/search?q=poker")
    assert result.robots_blocked is True
    assert result.error == "blocked_domain"
    assert result.ok is False


@pytest.mark.asyncio
@respx.mock
async def test_fetch_success():
    html_content = "<html><head><title>Test Poker Room</title></head><body><h1>Test</h1></body></html>"
    respx.get("https://example-poker.jp/").mock(
        return_value=httpx.Response(200, text=html_content)
    )
    # robots.txt mock
    respx.get("https://example-poker.jp/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )

    result = await fetch("https://example-poker.jp/")
    assert result.status_code == 200
    assert result.ok is True
    assert result.html == html_content
    assert len(result.checksum) == 64  # SHA256 hex


@pytest.mark.asyncio
@respx.mock
async def test_fetch_robots_blocked():
    respx.get("https://no-bots.jp/robots.txt").mock(
        return_value=httpx.Response(
            200,
            text="User-agent: *\nDisallow: /",
        )
    )

    result = await fetch("https://no-bots.jp/page")
    assert result.robots_blocked is True
    assert result.error == "robots_block"
    assert result.ok is False


@pytest.mark.asyncio
@respx.mock
async def test_fetch_timeout():
    respx.get("https://slow-site.jp/robots.txt").mock(
        return_value=httpx.Response(200, text="")
    )
    respx.get("https://slow-site.jp/").mock(side_effect=httpx.TimeoutException("timeout"))

    result = await fetch("https://slow-site.jp/")
    assert result.ok is False
    assert "timeout" in (result.error or "")
