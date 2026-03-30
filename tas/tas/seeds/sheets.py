"""Google Sheets API連携（読み取り + 書き戻し）"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tas.config import settings
from tas.db.models import Source

logger = logging.getLogger(__name__)


def _safe_priority(raw: str | None) -> int:
    """セル値を安全にpriority整数へ変換する（1〜10にクランプ）"""
    try:
        return max(1, min(10, int(raw or "5")))
    except (ValueError, TypeError):
        return 5

# 期待するシートのヘッダー列マッピング
SHEET_COLUMNS = {
    "seed_url": 0,
    "seed_type": 1,
    "region_hint": 2,
    "priority": 3,
    "page_kind": 4,
    "owner": 5,
    "source_name": 6,
    "note": 7,
    "status": 8,       # 書き戻し先
    "last_run_at": 9,  # 書き戻し先
    "error_reason": 10, # 書き戻し先
}


class SheetsClient:
    def __init__(self) -> None:
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service

        if not settings.google_service_account_json:
            raise RuntimeError(
                "GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません。"
                ".env を確認してください。"
            )

        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_dict = json.loads(settings.google_service_account_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self._service = build("sheets", "v4", credentials=creds)
        return self._service

    def _get_sheet_id(self) -> str:
        if not settings.google_sheets_id:
            raise RuntimeError("GOOGLE_SHEETS_ID が設定されていません。")
        return settings.google_sheets_id

    def read_pending_rows(self, sheet_name: str = "seeds") -> list[dict]:
        """statusが空またはpendingの行を読み取る"""
        service = self._get_service()
        sheet_id = self._get_sheet_id()

        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range=f"{sheet_name}!A:K")
            .execute()
        )
        rows = result.get("values", [])
        if not rows:
            return []

        # 1行目がヘッダー
        pending = []
        for i, row in enumerate(rows[1:], start=2):
            # 空行スキップ
            if not row or not row[0].strip():
                continue

            def get_col(col_idx: int) -> str:
                return row[col_idx].strip() if len(row) > col_idx else ""

            status = get_col(SHEET_COLUMNS["status"])
            if status in ("", "pending"):
                pending.append(
                    {
                        "row_num": i,
                        "seed_url": get_col(SHEET_COLUMNS["seed_url"]),
                        "seed_type": get_col(SHEET_COLUMNS["seed_type"]) or "manual",
                        "region_hint": get_col(SHEET_COLUMNS["region_hint"]),
                        "priority": _safe_priority(get_col(SHEET_COLUMNS["priority"])),
                        "page_kind": get_col(SHEET_COLUMNS["page_kind"]),
                        "owner": get_col(SHEET_COLUMNS["owner"]),
                        "source_name": get_col(SHEET_COLUMNS["source_name"]),
                        "note": get_col(SHEET_COLUMNS["note"]),
                    }
                )
        return pending

    def write_back(
        self,
        row_num: int,
        status: str,
        error_reason: Optional[str] = None,
        sheet_name: str = "seeds",
    ) -> None:
        """ステータス・実行日時・エラー理由をシートに書き戻す"""
        service = self._get_service()
        sheet_id = self._get_sheet_id()

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        col_status = chr(ord("A") + SHEET_COLUMNS["status"])
        col_last_run = chr(ord("A") + SHEET_COLUMNS["last_run_at"])
        col_error = chr(ord("A") + SHEET_COLUMNS["error_reason"])

        updates = [
            {
                "range": f"{sheet_name}!{col_status}{row_num}",
                "values": [[status]],
            },
            {
                "range": f"{sheet_name}!{col_last_run}{row_num}",
                "values": [[now_str]],
            },
            {
                "range": f"{sheet_name}!{col_error}{row_num}",
                "values": [[error_reason or ""]],
            },
        ]

        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()

    async def sync_to_db(self, session: AsyncSession, sheet_name: str = "seeds") -> int:
        """シートのpending行をDBのsourcesに同期する"""
        import asyncio
        rows = await asyncio.to_thread(self.read_pending_rows, sheet_name=sheet_name)
        added = 0

        for row in rows:
            url = row["seed_url"]
            if not url:
                continue

            existing = await session.execute(
                select(Source).where(Source.seed_url == url)
            )
            if existing.scalar_one_or_none():
                logger.debug("Skip existing: %.200s", url)
                continue

            source = Source(
                seed_url=url,
                seed_type=row["seed_type"],
                region_hint=row["region_hint"] or None,
                priority=row["priority"],
                page_kind=row["page_kind"] or None,
                owner=row["owner"] or None,
                source_name=row["source_name"] or None,
                note=row["note"] or None,
                status="pending",
                sheet_row_num=row["row_num"],
            )
            session.add(source)
            added += 1

        if added:
            await session.commit()

        return added
