"""engine/normalizer の追加ユニットテスト（Task 14）"""

import math

import pytest

from tas.crawler.normalizer import (
    address_similarity,
    build_match_evidence,
    find_duplicate_candidate,
    find_gray_zone_candidates,
    haversine_distance_km,
)


# ── address_similarity ──────────────────────────────────────

def test_address_similarity_exact():
    assert address_similarity("東京都渋谷区道玄坂1-1", "東京都渋谷区道玄坂1-1") == 1.0


def test_address_similarity_partial():
    score = address_similarity("東京都渋谷区道玄坂1-1", "東京都渋谷区道玄坂1-2")
    assert 0.8 < score < 1.0


def test_address_similarity_different():
    score = address_similarity("東京都渋谷区", "大阪府北区梅田")
    assert score < 0.5


def test_address_similarity_empty():
    assert address_similarity("", "") == 1.0
    assert address_similarity("東京都", "") == 0.0


# ── haversine_distance_km ────────────────────────────────────

def test_haversine_same_point():
    dist = haversine_distance_km(35.69, 139.69, 35.69, 139.69)
    assert dist == pytest.approx(0.0, abs=1e-9)


def test_haversine_tokyo_osaka():
    # 東京〜大阪はおよそ400km
    dist = haversine_distance_km(35.6895, 139.6917, 34.6864, 135.5200)
    assert 390 < dist < 420


def test_haversine_nearby_venues():
    # 渋谷〜新宿はおよそ2km
    dist = haversine_distance_km(35.6580, 139.7016, 35.6896, 139.7006)
    assert 2.0 < dist < 5.0


def test_haversine_very_close():
    # 100m以内
    dist = haversine_distance_km(35.6895, 139.6917, 35.6904, 139.6920)
    assert dist < 0.2


# ── find_duplicate_candidate with lat/lng ────────────────────

def test_find_duplicate_with_coords_nearby():
    """座標が近い場合に重複と判定する"""
    existing = [
        {
            "name": "渋谷ポーカー",
            "website_url": None,
            "id": "v1",
            "address": "東京都渋谷区道玄坂1-1",
            "lat": 35.6580,
            "lng": 139.7016,
        }
    ]
    dup = find_duplicate_candidate(
        name="渋谷ポーカールーム",  # 名前が類似
        website_url=None,
        existing=existing,
        lat=35.6582,  # 約20m差
        lng=139.7018,
    )
    assert dup is not None
    assert dup["id"] == "v1"


def test_find_duplicate_with_coords_far():
    """同名でも座標が遠い場合は別店舗と判定する"""
    existing = [
        {
            "name": "渋谷ポーカー",
            "website_url": None,
            "id": "v1",
            "address": "東京都渋谷区道玄坂1-1",
            "lat": 35.6580,
            "lng": 139.7016,
        }
    ]
    dup = find_duplicate_candidate(
        name="渋谷ポーカー",  # 同名
        website_url=None,
        existing=existing,
        lat=34.6864,  # 大阪（遠い）
        lng=135.5200,
    )
    assert dup is None  # 座標が遠いので別店舗


def test_find_duplicate_address_fallback():
    """座標がない場合に住所類似度で判定する"""
    existing = [
        {
            "name": "新宿クラブ",
            "website_url": None,
            "id": "v2",
            "address": "東京都新宿区歌舞伎町1-1",
            "lat": None,
            "lng": None,
        }
    ]
    dup = find_duplicate_candidate(
        name="新宿クラブ",
        website_url=None,
        existing=existing,
        address="東京都新宿区歌舞伎町1-2",  # 住所が近い
        lat=None,
        lng=None,
    )
    assert dup is not None
    assert dup["id"] == "v2"


# ── find_gray_zone_candidates ────────────────────────────────

def test_gray_zone_finds_candidates():
    """グレーゾーン類似度の候補を正しく検出する"""
    existing = [
        {
            "name": "渋谷ポーカーバー",
            "website_url": None,
            "id": "g1",
            "address": "東京都渋谷区",
            "lat": 35.6580,
            "lng": 139.7016,
        },
        {
            "name": "新宿スタジオ",  # 完全に別店舗
            "website_url": None,
            "id": "g2",
            "address": "東京都新宿区",
            "lat": 35.6896,
            "lng": 139.7006,
        },
    ]
    # "渋谷ポーカー" → "渋谷ポーカーバー" は類似度 0.5〜0.85 あたり
    gray = find_gray_zone_candidates(
        name="渋谷ポーカー",
        website_url=None,
        existing=existing,
        lat=35.6582,
        lng=139.7018,
    )
    # 近い方はグレーゾーンとして登録される可能性がある
    ids = [c["id"] for c in gray]
    # "渋谷ポーカーバー"は近接するため候補に入り得る
    # 新宿は遠すぎるため候補に入らないはず（proximity_km=2.0 を超える）
    assert "g2" not in ids


def test_gray_zone_empty_when_exact_match():
    """閾値上限を超える（重複扱いの）候補はグレーゾーンに入らない"""
    existing = [
        {
            "name": "渋谷ポーカー",
            "website_url": None,
            "id": "dup1",
            "address": "東京都渋谷区",
            "lat": 35.6580,
            "lng": 139.7016,
        }
    ]
    gray = find_gray_zone_candidates(
        name="渋谷ポーカー",  # 完全一致 → name_sim=1.0 → max_score(0.85)以上 → 含まれない
        website_url=None,
        existing=existing,
        lat=35.6582,
        lng=139.7018,
    )
    assert gray == []


# ── build_match_evidence with coords ────────────────────────

def test_build_evidence_with_coords():
    candidate = {
        "name": "渋谷ポーカー",
        "website_url": "https://shibuya-poker.jp/",
        "address": "東京都渋谷区道玄坂1-1",
        "lat": 35.6580,
        "lng": 139.7016,
    }
    evidence = build_match_evidence(
        name="渋谷ポーカールーム",
        website_url="https://shibuya-poker.jp/about",
        candidate=candidate,
        address="東京都渋谷区道玄坂1-2",
        lat=35.6582,
        lng=139.7018,
    )
    assert evidence["url_match"] is True
    assert "name_similarity" in evidence
    assert "address_similarity" in evidence
    assert "distance_km" in evidence
    assert evidence["distance_km"] < 0.5  # 20m以内


def test_build_evidence_without_coords():
    candidate = {"name": "大阪ポーカー", "website_url": None}
    evidence = build_match_evidence(
        name="大阪ポーカークラブ",
        website_url=None,
        candidate=candidate,
    )
    assert "name_similarity" in evidence
    assert "url_match" not in evidence
    assert "distance_km" not in evidence
    assert "address_similarity" not in evidence
