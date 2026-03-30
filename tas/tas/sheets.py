"""Google Sheets 連携サービス"""

import json
import logging
import re
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from tas.config import settings

_SHEET_NAME_RE = re.compile(r"^[\w\s\-]+$", re.UNICODE)
_SHEET_NAME_MAX_LEN = 100


def _validate_sheet_name(sheet_name: str) -> None:
    """sheet_name が安全な文字のみで構成されているか検証する。

    許可: 英数字、アンダースコア、ハイフン、スペース、日本語文字（\\w でカバー）。
    最大長: 100文字。
    """
    if not sheet_name or len(sheet_name) > _SHEET_NAME_MAX_LEN:
        raise ValueError(
            f"sheet_name must be 1-{_SHEET_NAME_MAX_LEN} characters, "
            f"got {len(sheet_name) if sheet_name else 0}"
        )
    if not _SHEET_NAME_RE.match(sheet_name):
        raise ValueError(
            f"sheet_name contains invalid characters: {sheet_name!r}. "
            "Only alphanumeric, spaces, hyphens, and underscores are allowed."
        )

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_service():
    if not settings.google_service_account_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません")
    if not settings.google_sheets_id:
        raise ValueError("GOOGLE_SHEETS_ID が設定されていません")

    info = json.loads(settings.google_service_account_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _ensure_sheet(service, sheet_name: str) -> None:
    """指定名のシートが存在しなければ新規作成する。"""
    meta = service.spreadsheets().get(
        spreadsheetId=settings.google_sheets_id
    ).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if sheet_name not in existing:
        body = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
        service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_id, body=body
        ).execute()
        logger.info("[Sheets] created sheet %r", sheet_name)


def append_rows(sheet_name: str, rows: list[list[Any]]) -> int:
    """指定シートに行を追記する。書き込んだ行数を返す。"""
    _validate_sheet_name(sheet_name)
    if not rows:
        return 0
    try:
        service = _get_service()
        _ensure_sheet(service, sheet_name)
        range_ = f"{sheet_name}!A1"
        body = {"values": rows}
        result = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=settings.google_sheets_id,
                range=range_,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )
        updated = result.get("updates", {}).get("updatedRows", len(rows))
        logger.info("[Sheets] appended %d rows to %r", updated, sheet_name)
        return updated
    except HttpError as e:
        logger.error("[Sheets] HttpError: %s", e)
        raise


def clear_and_write(sheet_name: str, rows: list[list[Any]]) -> int:
    """シートをクリアしてから全行を書き込む。書き込んだ行数を返す。"""
    _validate_sheet_name(sheet_name)
    try:
        service = _get_service()
        _ensure_sheet(service, sheet_name)
        range_ = f"{sheet_name}!A1:ZZ"
        service.spreadsheets().values().clear(
            spreadsheetId=settings.google_sheets_id,
            range=range_,
            body={},
        ).execute()

        if not rows:
            return 0

        body = {"values": rows}
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=settings.google_sheets_id,
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )
        updated = result.get("updatedRows", len(rows))
        logger.info("[Sheets] wrote %d rows to %r", updated, sheet_name)
        return updated
    except HttpError as e:
        logger.error("[Sheets] HttpError: %s", e)
        raise
