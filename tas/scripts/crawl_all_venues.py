"""全73件の venue.website_url をクロールしてデータ充実化するスクリプト

既存値がある場合は上書きしない（preserve-first）。
空欄のフィールドのみ parse_html の結果で埋める。
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from tas.crawler.fetcher import fetch
from tas.crawler.parser import parse_html
from tas.db.models import Venue
from tas.db.session import AsyncSessionLocal, engine


# parse_html → venue に書き込むマッピング
FIELD_MAP = {
    "hours_raw": "hours_today",
    "price_entry_min": "price_entry_min",
    "price_note": "price_note",
    "drink_required": "drink_required",
    "food_level": "food_level",
    "table_count": "table_count",
    "peak_time": "peak_time",
    "summary": "summary",
}


async def main():
    async with AsyncSessionLocal() as session:
        r = await session.execute(
            text("SELECT id, name, website_url FROM venues ORDER BY name")
        )
        venues = [dict(zip(r.keys(), row)) for row in r.fetchall()]

    print(f"対象: {len(venues)} 件")

    results = {"success": 0, "error": 0, "blocked": 0, "no_url": 0, "updated_fields": 0}

    for i, v in enumerate(venues, 1):
        name = v["name"]
        url = v.get("website_url")
        vid = str(v["id"])

        if not url:
            print(f"[{i:2d}/{len(venues)}] SKIP (URL無し): {name}")
            results["no_url"] += 1
            continue

        print(f"[{i:2d}/{len(venues)}] {name} → {url}")

        try:
            fr = await fetch(url)
        except Exception as e:
            print(f"  !! fetch例外: {e}")
            results["error"] += 1
            continue

        if not fr.ok:
            reason = "robots" if fr.robots_blocked else (fr.error or f"HTTP {fr.status_code}")
            print(f"  !! fetch失敗: {reason}")
            if fr.robots_blocked:
                results["blocked"] += 1
            else:
                results["error"] += 1
            continue

        parsed = parse_html(url, fr.html)

        # DB更新: 空欄フィールドのみ埋める
        updated = []
        async with AsyncSessionLocal() as session:
            venue = await session.get(Venue, vid)
            if not venue:
                print(f"  !! DB上にvenueが見つからない: {vid}")
                results["error"] += 1
                continue

            for parsed_field, db_field in FIELD_MAP.items():
                parsed_val = getattr(parsed, parsed_field, None)
                current_val = getattr(venue, db_field, None)

                if parsed_val is not None and not current_val:
                    setattr(venue, db_field, parsed_val)
                    updated.append(db_field)

            # sns_links: マージ（既存を残しつつ追加）
            if parsed.sns_links:
                existing_sns = venue.sns_links or {}
                if isinstance(existing_sns, str):
                    try:
                        existing_sns = json.loads(existing_sns)
                    except Exception:
                        existing_sns = {}
                merged = {**parsed.sns_links, **existing_sns}  # existing優先
                if merged != (venue.sns_links or {}):
                    venue.sns_links = merged
                    updated.append("sns_links")

            # field_confidence: マージ
            if parsed.field_confidence:
                existing_fc = venue.field_confidence or {}
                if isinstance(existing_fc, str):
                    try:
                        existing_fc = json.loads(existing_fc)
                    except Exception:
                        existing_fc = {}
                merged_fc = {**parsed.field_confidence, **existing_fc}
                if merged_fc != (venue.field_confidence or {}):
                    venue.field_confidence = merged_fc
                    updated.append("field_confidence")

            if updated:
                await session.commit()
                results["updated_fields"] += len(updated)
                print(f"  ✓ 更新: {', '.join(updated)}")
            else:
                print(f"  - 更新なし（既存データで充足）")

        results["success"] += 1

        # ドメインへの負荷軽減のため少し待つ
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"完了: 成功={results['success']}, エラー={results['error']}, "
          f"ブロック={results['blocked']}, URL無し={results['no_url']}")
    print(f"更新フィールド合計: {results['updated_fields']}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
