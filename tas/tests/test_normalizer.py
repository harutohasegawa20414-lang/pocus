"""normalizer.py のユニットテスト"""

import pytest

from tas.crawler.normalizer import (
    build_match_evidence,
    find_duplicate_candidate,
    name_similarity,
    normalize_prefecture,
    normalize_venue_name,
    normalize_text,
    normalize_url,
    prefecture_to_coords,
    url_domain_match,
)


def test_normalize_text_nfkc():
    assert normalize_text("ＡＢＣＤ") == "ABCD"
    assert normalize_text("　hello　") == "hello"


def test_normalize_url():
    assert normalize_url("https://example.com/") == "https://example.com"
    assert normalize_url("//example.com") == "https://example.com"
    assert normalize_url("  https://example.com  ") == "https://example.com"


def test_normalize_venue_name():
    assert normalize_venue_name("渋谷ポーカールーム") == "渋谷"
    assert normalize_venue_name("SHIBUYA POKER ROOM") != ""


def test_name_similarity_exact():
    assert name_similarity("SHIBUYA INK", "SHIBUYA INK") == 1.0


def test_name_similarity_partial():
    score = name_similarity("渋谷ポーカー", "渋谷Poker")
    assert 0.0 < score < 1.0


def test_name_similarity_different():
    score = name_similarity("東京ポーカールーム", "大阪カジノバー")
    assert score < 0.5


def test_url_domain_match_same():
    assert url_domain_match("https://example.com/page1", "https://example.com/page2") is True


def test_url_domain_match_different():
    assert url_domain_match("https://studio-a.jp/", "https://studio-b.jp/") is False


def test_url_domain_match_trailing_slash():
    assert url_domain_match("https://example.com/", "https://example.com") is True


def test_prefecture_to_coords_tokyo():
    coords = prefecture_to_coords("東京")
    assert coords is not None
    lat, lng = coords
    assert 35.0 < lat < 36.0
    assert 139.0 < lng < 140.0


def test_prefecture_to_coords_osaka():
    coords = prefecture_to_coords("大阪")
    assert coords is not None


def test_prefecture_to_coords_unknown():
    assert prefecture_to_coords("不明地域") is None


def test_normalize_prefecture():
    assert normalize_prefecture("東京都渋谷区") == "東京"
    assert normalize_prefecture("大阪府北区") == "大阪"
    assert normalize_prefecture("unknown") is None


def test_find_duplicate_url_match():
    existing = [
        {"name": "別スタジオ", "website_url": "https://example.com/", "id": "abc"},
    ]
    dup = find_duplicate_candidate(
        name="全く違う名前",
        website_url="https://example.com/about",
        existing=existing,
    )
    assert dup is not None
    assert dup["id"] == "abc"


def test_find_duplicate_name_match():
    existing = [
        {"name": "渋谷インク", "website_url": None, "id": "xyz"},
    ]
    dup = find_duplicate_candidate(
        name="渋谷インク",
        website_url="https://different.com/",
        existing=existing,
    )
    assert dup is not None
    assert dup["id"] == "xyz"


def test_find_duplicate_no_match():
    existing = [
        {"name": "大阪ポーカー", "website_url": "https://osaka.jp/", "id": "111"},
    ]
    dup = find_duplicate_candidate(
        name="東京ポーカー",
        website_url="https://tokyo.jp/",
        existing=existing,
    )
    assert dup is None


def test_build_match_evidence():
    candidate = {"name": "渋谷インク", "website_url": "https://shibuya.jp/"}
    evidence = build_match_evidence(
        name="渋谷インク",
        website_url="https://shibuya.jp/about",
        candidate=candidate,
    )
    assert evidence["url_match"] is True
    assert evidence["name_similarity"] == 1.0
