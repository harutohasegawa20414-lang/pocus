"""seedData JSON → PostgreSQL (pocusdb) インポートスクリプト

scripts/seed_venues.json を読み取り、pocusdb の venues テーブルに upsert する。
ORM モデルを直接使用。
"""

import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, text
from tas.db.models import Venue
from tas.db.session import AsyncSessionLocal, engine


def seed_id_to_uuid(seed_id: str) -> str:
    """seed-xxx 形式の ID を再現可能な UUID に変換"""
    if seed_id.startswith("seed-"):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"pocus:{seed_id}"))
    return seed_id


def to_venue(v: dict) -> dict:
    """seed JSON → Venue フィールド辞書"""
    return {
        "id": seed_id_to_uuid(v.get("id", "")),
        "name": v.get("name", ""),
        "address": v.get("address") or "",
        "area_prefecture": v.get("area_prefecture"),
        "area_city": v.get("area_city"),
        "lat": v.get("lat"),
        "lng": v.get("lng"),
        "open_status": v.get("open_status") or "unknown",
        "hours_today": v.get("hours_today"),
        "price_entry_min": v.get("price_entry_min"),
        "price_note": v.get("price_note"),
        "drink_required": v.get("drink_required") if v.get("drinkRich") is None else v.get("drinkRich"),
        "food_level": v.get("food_level") or v.get("foodLevel"),
        "table_count": v.get("table_count") or v.get("tableCount"),
        "peak_time": v.get("peak_time") or v.get("peakTime"),
        "website_url": v.get("website_url"),
        "sns_links": v.get("sns_links"),
        "sources": v.get("sources"),
        "summary": v.get("summary"),
        "field_confidence": v.get("field_confidence"),
        "verification_status": v.get("verification_status") or "unverified",
        "visibility_status": v.get("visibility_status") or "visible",
        "match_confidence": v.get("match_confidence"),
        "country_code": v.get("country_code") or "JP",
        "locale": v.get("locale") or "ja",
        "time_zone": v.get("time_zone") or "Asia/Tokyo",
    }


async def main():
    json_path = os.path.join(os.path.dirname(__file__), "seed_venues.json")
    with open(json_path) as f:
        venues = json.load(f)

    print(f"seed_venues.json: {len(venues)} 件")

    async with AsyncSessionLocal() as session:
        inserted = 0
        updated = 0
        for v in venues:
            fields = to_venue(v)
            vid = fields["id"]

            existing = await session.get(Venue, vid)
            if existing:
                for key, val in fields.items():
                    if key != "id":
                        setattr(existing, key, val)
                updated += 1
            else:
                venue = Venue(**fields)
                session.add(venue)
                inserted += 1

        await session.commit()
        print(f"inserted={inserted}, updated={updated}")

    # 確認
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM venues"))
        total = result.scalar()
        result2 = await session.execute(
            text("SELECT COUNT(*) FROM venues WHERE visibility_status='visible'")
        )
        visible = result2.scalar()
        print(f"DB: total={total}, visible={visible}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
