"""APIエンドポイントのユニットテスト（DBモック使用）"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from httpx import ASGITransport, AsyncClient

from tas.api.main import app
from tas.db.models import Report, Venue, VenueMergeCandidate
from tas.db.session import get_session


# ── テストヘルパー ─────────────────────────────────────────────

def _make_scalars(items: list):
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=items)
    scalars.__iter__ = MagicMock(return_value=iter(items))
    return scalars


def _make_execute_result(items=None, scalar_one_or_none=None, scalar_one=0):
    result = MagicMock()
    result.scalars = MagicMock(return_value=_make_scalars(items or []))
    result.scalar_one_or_none = MagicMock(return_value=scalar_one_or_none)
    result.scalar_one = MagicMock(return_value=scalar_one)
    return result


def _make_session(execute_result=None, scalar_return=0, get_return=None):
    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result or _make_execute_result())
    session.scalar = AsyncMock(return_value=scalar_return)
    session.get = AsyncMock(return_value=get_return)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    return session


def _override(session):
    async def _dep():
        yield session

    app.dependency_overrides[get_session] = _dep


def _clear():
    app.dependency_overrides.clear()


def _venue_mock(id="v1", name="テスト店舗"):
    v = MagicMock(spec=Venue)
    v.id = id
    v.name = name
    v.open_status = "unknown"
    v.visibility_status = "visible"
    v.verification_status = "unverified"
    v.address = "東京都渋谷区"
    v.area_prefecture = "東京"
    v.area_city = "渋谷区"
    v.lat = 35.66
    v.lng = 139.70
    v.hours_today = None
    v.price_entry_min = None
    v.price_note = None
    v.drink_required = None
    v.food_level = None
    v.table_count = None
    v.peak_time = None
    v.website_url = None
    v.sns_links = None
    v.sources = None
    v.summary = None
    v.field_confidence = None
    v.match_confidence = None
    v.country_code = "JP"
    v.locale = "ja"
    v.time_zone = "Asia/Tokyo"
    v.last_updated_at = None
    v.updated_at = datetime.now(timezone.utc)
    v.created_at = datetime.now(timezone.utc)
    v.tournaments = []
    return v


def _tournament_mock(id="t1", venue_id="v1"):
    t = MagicMock()
    t.id = id
    t.venue_id = venue_id
    t.title = "ウィークリートーナメント"
    t.start_at = datetime(2025, 4, 1, 19, 0, tzinfo=timezone.utc)
    t.buy_in = 3000
    t.guarantee = None
    t.capacity = 20
    t.url = "https://poker.jp/tournament/weekly"
    t.status = "scheduled"
    t.created_at = datetime.now(timezone.utc)
    return t


# ── /health ────────────────────────────────────────────────

async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "pocus"


# ── GET /venues/ ────────────────────────────────────────────

async def test_list_venues_empty():
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            r = MagicMock()
            r.scalar_one = MagicMock(return_value=0)
            return r
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venues/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []
    finally:
        _clear()


async def test_list_venues_returns_items():
    venue = _venue_mock()
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            r = MagicMock()
            r.scalar_one = MagicMock(return_value=1)
            return r
        elif call_n == 2:
            return _make_execute_result(items=[venue])
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venues/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "テスト店舗"
    finally:
        _clear()


# ── GET /venue/{id} ──────────────────────────────────────────

async def test_get_venue_not_found():
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(scalar_one_or_none=None))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venue/nonexistent-id")
        assert resp.status_code == 404
    finally:
        _clear()


async def test_get_venue_found():
    venue = _venue_mock(id="abc-123")
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _make_execute_result(scalar_one_or_none=venue)
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venue/abc-123")
        assert resp.status_code == 200
        assert resp.json()["id"] == "abc-123"
    finally:
        _clear()


# ── POST /venue/{id}/report ──────────────────────────────────

async def test_report_venue_not_found():
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(scalar_one_or_none=None))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/venue/nonexistent/report",
                json={"report_type": "remove", "entity_type": "venue", "entity_id": "nonexistent"},
            )
        assert resp.status_code == 404
    finally:
        _clear()


async def test_report_venue_created():
    venue = _venue_mock(id="v-99")
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(scalar_one_or_none=venue))

    async def mock_refresh(obj):
        obj.id = "r-1"
        obj.report_type = "remove"
        obj.entity_type = "venue"
        obj.entity_id = "v-99"
        obj.status = "pending"
        obj.reporter_name = None
        obj.details = "閉店しました"
        obj.resolved_by = None
        obj.created_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=mock_refresh)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/venue/v-99/report",
                json={
                    "report_type": "remove",
                    "entity_type": "venue",
                    "entity_id": "v-99",
                    "details": "閉店しました",
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending"
        assert body["report_type"] == "remove"
    finally:
        _clear()


# ── GET /admin/stats ─────────────────────────────────────────

async def test_admin_stats():
    session = _make_session()
    session.scalar = AsyncMock(return_value=0)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/admin/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_venues" in body
        assert "pending_merge_candidates" in body
        assert "disabled_sources" in body
    finally:
        _clear()


# ── PATCH /admin/merge-candidates/{id} ──────────────────────

async def test_resolve_merge_candidate_not_found():
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(scalar_one_or_none=None))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.patch(
                "/admin/merge-candidates/nonexistent",
                json={"action": "rejected"},
            )
        assert resp.status_code == 404
    finally:
        _clear()


async def test_resolve_merge_candidate_already_resolved():
    candidate = MagicMock(spec=VenueMergeCandidate)
    candidate.id = "mc-1"
    candidate.venue_a_id = "va"
    candidate.venue_b_id = "vb"
    candidate.status = "merged"
    candidate.similarity_score = 0.9
    candidate.evidence = {}
    candidate.resolved_at = datetime.now(timezone.utc)
    candidate.resolved_by = None
    candidate.resolution_note = None
    candidate.created_at = datetime.now(timezone.utc)

    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(scalar_one_or_none=candidate))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.patch(
                "/admin/merge-candidates/mc-1",
                json={"action": "rejected"},
            )
        assert resp.status_code == 409
    finally:
        _clear()


# ── GET /admin/venues/stale ──────────────────────────────────

async def test_stale_venues_empty():
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(items=[]))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/admin/venues/stale")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        _clear()


async def test_stale_venues_custom_days():
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(items=[]))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/admin/venues/stale?days=7")
        assert resp.status_code == 200
    finally:
        _clear()


# ── T4: /health — enable_3d / phase フラグ公開 ──────────────

async def test_health_includes_3d_flag():
    """T4: health レスポンスに enable_3d と phase が含まれる（3D基盤フラグ）"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "enable_3d" in body
    assert isinstance(body["enable_3d"], bool)
    assert "phase" in body
    assert isinstance(body["phase"], int)


# ── GET /map/pins ─────────────────────────────────────────────

async def test_map_pins_empty():
    """GET /map/pins — 店舗なし → 空レスポンス"""
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/map/pins")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pins"] == []
        assert body["total"] == 0
    finally:
        _clear()


async def test_map_pins_returns_venues():
    """GET /map/pins — 店舗あり → ピンが返る"""
    venue = _venue_mock(id="map-v1")
    venue.lat = 35.66
    venue.lng = 139.70
    venue.open_status = "open"
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _make_execute_result(items=[venue])
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/map/pins")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["pins"]) == 1
        pin = body["pins"][0]
        assert pin["display_name"] == "テスト店舗"
        assert abs(pin["lat"] - 35.66) < 0.001
        assert abs(pin["lng"] - 139.70) < 0.001
        assert pin["open_status"] == "open"
    finally:
        _clear()


async def test_map_pins_with_bbox():
    """GET /map/pins — bbox パラメータを受け付ける"""
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(items=[]))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/map/pins?bbox=139.0,35.0,140.0,36.0")
        assert resp.status_code == 200
        body = resp.json()
        assert "pins" in body
        assert "total" in body
    finally:
        _clear()


async def test_map_pins_with_next_tournament():
    """GET /map/pins — 次回大会情報がピンに含まれる"""
    venue = _venue_mock(id="v-tour")
    venue.lat = 35.66
    venue.lng = 139.70
    tournament = _tournament_mock(venue_id="v-tour")
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _make_execute_result(items=[venue])
        return _make_execute_result(items=[tournament])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/map/pins")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["pins"]) == 1
        assert body["pins"][0]["next_tournament_title"] == "ウィークリートーナメント"
    finally:
        _clear()


# ── GET /tournaments/ ────────────────────────────────────────

async def test_list_tournaments_empty():
    """GET /tournaments/ — 大会なし → 空配列"""
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(items=[]))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/tournaments/")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        _clear()


async def test_list_tournaments_returns_items():
    """GET /tournaments/ — 大会あり → 正しく返る"""
    t = _tournament_mock()
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(items=[t]))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/tournaments/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["title"] == "ウィークリートーナメント"
        assert body[0]["buy_in"] == 3000
        assert body[0]["status"] == "scheduled"
    finally:
        _clear()


async def test_list_tournaments_filter_by_venue():
    """GET /tournaments/?venue_id= — 店舗IDフィルタが受け付けられる"""
    session = _make_session()
    session.execute = AsyncMock(return_value=_make_execute_result(items=[]))
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/tournaments/?venue_id=some-venue-id")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        _clear()


# ── T13: パース失敗フィールドのフォールバック保証 ────────────

async def test_venue_with_no_optional_fields_returns_200():
    """T13: P0/P1 フィールドがすべて None でも API が 200 を返す（フィールド単位で落とす）"""
    venue = _venue_mock(id="sparse-v")  # 全任意フィールドが None
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return _make_execute_result(scalar_one_or_none=venue)
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venue/sparse-v")
        assert resp.status_code == 200
        body = resp.json()
        # P0: 不明値は null で返る（"?" 表示禁止、T13 準拠）
        assert body["hours_today"] is None
        assert body["price_entry_min"] is None
        # P1: 全 None
        assert body["drink_required"] is None
        assert body["food_level"] is None
        assert body["table_count"] is None
        assert body["peak_time"] is None
        # 大会なし → 空配列（T13: 大会欄を隠す）
        assert body["tournaments"] == []
    finally:
        _clear()


# ── T14 異常系: 金額なし / 大会あり ─────────────────────────

async def test_venue_card_missing_price_returns_null():
    """T14 異常系: 金額なしの店舗カードは price_entry_min が null で返る（推測表示しない）"""
    venue = _venue_mock(id="no-price-v")
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            r = MagicMock()
            r.scalar_one = MagicMock(return_value=1)
            return r
        elif call_n == 2:
            return _make_execute_result(items=[venue])
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venues/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"][0]["price_entry_min"] is None
    finally:
        _clear()


async def test_venue_card_with_tournament_shows_next():
    """T14 正常系: 大会がある店舗カードに next_tournament_title が出る"""
    venue = _venue_mock(id="v-with-tour")
    venue.open_status = "open"
    tournament = _tournament_mock(venue_id="v-with-tour")
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            r = MagicMock()
            r.scalar_one = MagicMock(return_value=1)
            return r
        elif call_n == 2:
            return _make_execute_result(items=[venue])
        return _make_execute_result(items=[tournament])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venues/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"][0]["next_tournament_title"] == "ウィークリートーナメント"
    finally:
        _clear()


# ── T14 正常系: フィルタ ──────────────────────────────────────

async def test_list_venues_open_filter():
    """T14 正常系: open_status=open フィルタが受け付けられる"""
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            r = MagicMock()
            r.scalar_one = MagicMock(return_value=0)
            return r
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venues/?open_status=open")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
    finally:
        _clear()


async def test_list_venues_has_price_filter():
    """T14 正常系: has_price=true フィルタが受け付けられる"""
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            r = MagicMock()
            r.scalar_one = MagicMock(return_value=0)
            return r
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venues/?has_price=true")
        assert resp.status_code == 200
    finally:
        _clear()


async def test_list_venues_has_tournament_filter():
    """T14 正常系: has_tournament=true フィルタが受け付けられる"""
    session = _make_session()
    call_n = 0

    async def _exec(q):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            r = MagicMock()
            r.scalar_one = MagicMock(return_value=0)
            return r
        return _make_execute_result(items=[])

    session.execute = AsyncMock(side_effect=_exec)
    _override(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/venues/?has_tournament=true")
        assert resp.status_code == 200
    finally:
        _clear()
