"""共通テストフィクスチャ"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from tas.api.main import app
from tas.db.session import get_session


def _make_scalars(items: list):
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=items)
    scalars.__iter__ = MagicMock(return_value=iter(items))
    return scalars


def make_execute_result(items: list | None = None, scalar_one_or_none=None, scalar_one=0):
    """sqlalchemy execute() の戻り値モックを生成する"""
    result = MagicMock()
    result.scalars = MagicMock(return_value=_make_scalars(items or []))
    result.scalar_one_or_none = MagicMock(return_value=scalar_one_or_none)
    result.scalar_one = MagicMock(return_value=scalar_one)
    return result


def make_mock_session(
    execute_result=None,
    scalar_return: int = 0,
    get_return=None,
):
    """非同期セッションモックを生成する"""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result or make_execute_result())
    session.scalar = AsyncMock(return_value=scalar_return)
    session.get = AsyncMock(return_value=get_return)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
async def client():
    """DB依存なしのAPIテストクライアント"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def client_with_session(request):
    """セッションモックを注入したAPIテストクライアント"""
    session_mock = make_mock_session()

    async def override_get_session():
        yield session_mock

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, session_mock
    app.dependency_overrides.clear()
