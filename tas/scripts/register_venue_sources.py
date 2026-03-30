"""
店舗URL → Sourceテーブル一括登録スクリプト

venuesテーブルのwebsite_urlを取得し、
sourcesテーブルに未登録のURLをSourceレコードとして登録する。
既存スケジューラが自動で週次再クロールを実行するようになる。

Usage:
    cd tas/
    python -m scripts.register_venue_sources
"""

import asyncio
import sys
from pathlib import Path

# tas パッケージを import できるように sys.path を調整
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from tas.db.models import Source, Venue
from tas.db.session import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as session:
        # 1. venuesテーブルからwebsite_urlを取得
        result = await session.execute(
            select(Venue.id, Venue.name, Venue.website_url).where(
                Venue.visibility_status == "visible",
                Venue.website_url.is_not(None),
                Venue.website_url != "",
            )
        )
        venues = result.all()
        print(f"対象店舗数: {len(venues)}")

        # 2. 既存sourcesのseed_urlを取得（重複チェック用）
        existing_result = await session.execute(select(Source.seed_url))
        existing_urls = {row[0] for row in existing_result.all()}
        print(f"既存ソース数: {len(existing_urls)}")

        # 3. 未登録URLをSourceとして追加
        added = 0
        skipped = 0
        for venue_id, venue_name, website_url in venues:
            url = website_url.strip()
            if not url:
                continue

            if url in existing_urls:
                skipped += 1
                continue

            source = Source(
                seed_url=url,
                status="done",  # 初回クロールは済んでいるため
                update_interval_hours=168,  # 週1回の再クロール
                seed_type="venue_official",
                page_kind="home",
                priority=5,
                note=f"auto-registered from venue: {venue_name}",
            )
            session.add(source)
            existing_urls.add(url)  # 同一URL重複防止
            added += 1
            print(f"  + {url} ({venue_name})")

        await session.commit()
        print(f"\n完了: 追加={added}, スキップ(既存)={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
