"""Firestore → PostgreSQL (pocusdb) 同期スクリプト

Firestore の venues コレクションから全ドキュメントを読み取り、
ローカル pocusdb の venues テーブルに upsert する。
既存のレコード（同じ id）は上書きされる。
"""

import asyncio
import json
import os
import sys

import firebase_admin
from firebase_admin import credentials, firestore

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from tas.db.session import AsyncSessionLocal, engine


def init_firestore():
    """Firebase Admin SDK を初期化して Firestore クライアントを返す"""
    # .env からサービスアカウント JSON を読む
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON not set in .env")

    sa_dict = json.loads(sa_json)
    cred = credentials.Certificate(sa_dict)
    firebase_admin.initialize_app(cred)
    return firestore.client()


def extract_venue_row(doc_id: str, data: dict) -> dict | None:
    """Firestore ドキュメントから venues テーブルの行データを生成"""
    # detail が最も情報が多い、なければ card、なければ pin
    detail = data.get("detail") or data.get("card") or data.get("pin")
    if not detail:
        return None

    pin = data.get("pin", {})
    card = data.get("card", {})

    # id は doc_id を優先
    venue_id = doc_id

    row = {
        "id": venue_id,
        "name": detail.get("name") or pin.get("display_name", ""),
        "address": detail.get("address") or card.get("address") or "",
        "area_prefecture": detail.get("area_prefecture") or pin.get("area_prefecture"),
        "area_city": detail.get("area_city") or pin.get("area_city"),
        "lat": detail.get("lat") or pin.get("lat"),
        "lng": detail.get("lng") or pin.get("lng"),
        "open_status": detail.get("open_status") or pin.get("open_status") or "unknown",
        "hours_today": detail.get("hours_today") or pin.get("hours_today"),
        "price_entry_min": detail.get("price_entry_min") or card.get("price_entry_min"),
        "price_note": detail.get("price_note") or card.get("price_note"),
        "drink_required": detail.get("drink_required"),
        "food_level": detail.get("food_level"),
        "table_count": detail.get("table_count"),
        "peak_time": detail.get("peak_time"),
        "website_url": detail.get("website_url"),
        "sns_links": detail.get("sns_links"),
        "sources": detail.get("sources") or card.get("sources"),
        "summary": detail.get("summary"),
        "field_confidence": detail.get("field_confidence"),
        "verification_status": detail.get("verification_status") or "unverified",
        "visibility_status": detail.get("visibility_status") or "visible",
        "match_confidence": detail.get("match_confidence"),
        "country_code": detail.get("country_code") or "JP",
        "locale": detail.get("locale") or "ja",
        "time_zone": detail.get("time_zone") or "Asia/Tokyo",
    }
    return row


async def sync():
    print("Firestore に接続中...")
    fs_client = init_firestore()

    print("Firestore venues コレクションを取得中...")
    docs = fs_client.collection("venues").stream()

    rows = []
    for doc in docs:
        data = doc.to_dict()
        row = extract_venue_row(doc.id, data)
        if row:
            rows.append(row)

    print(f"Firestore から {len(rows)} 件取得")

    if not rows:
        print("データなし。終了。")
        return

    # UPSERT: INSERT ... ON CONFLICT DO UPDATE
    upsert_sql = text("""
        INSERT INTO venues (
            id, name, address, area_prefecture, area_city,
            lat, lng, open_status, hours_today,
            price_entry_min, price_note, drink_required, food_level,
            table_count, peak_time, website_url, sns_links,
            sources, summary, field_confidence,
            verification_status, visibility_status, match_confidence,
            country_code, locale, time_zone
        ) VALUES (
            :id, :name, :address, :area_prefecture, :area_city,
            :lat, :lng, :open_status, :hours_today,
            :price_entry_min, :price_note, :drink_required, :food_level,
            :table_count, :peak_time, :website_url,
            :sns_links::jsonb, :sources::jsonb, :summary, :field_confidence::jsonb,
            :verification_status, :visibility_status, :match_confidence,
            :country_code, :locale, :time_zone
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            address = EXCLUDED.address,
            area_prefecture = EXCLUDED.area_prefecture,
            area_city = EXCLUDED.area_city,
            lat = EXCLUDED.lat,
            lng = EXCLUDED.lng,
            open_status = EXCLUDED.open_status,
            hours_today = EXCLUDED.hours_today,
            price_entry_min = EXCLUDED.price_entry_min,
            price_note = EXCLUDED.price_note,
            drink_required = EXCLUDED.drink_required,
            food_level = EXCLUDED.food_level,
            table_count = EXCLUDED.table_count,
            peak_time = EXCLUDED.peak_time,
            website_url = EXCLUDED.website_url,
            sns_links = EXCLUDED.sns_links,
            sources = EXCLUDED.sources,
            summary = EXCLUDED.summary,
            field_confidence = EXCLUDED.field_confidence,
            verification_status = EXCLUDED.verification_status,
            visibility_status = EXCLUDED.visibility_status,
            match_confidence = EXCLUDED.match_confidence,
            country_code = EXCLUDED.country_code,
            locale = EXCLUDED.locale,
            time_zone = EXCLUDED.time_zone,
            updated_at = now()
    """)

    async with AsyncSessionLocal() as session:
        inserted = 0
        for row in rows:
            # JSONB カラムは文字列に変換
            params = dict(row)
            for jcol in ("sns_links", "sources", "field_confidence"):
                val = params[jcol]
                params[jcol] = json.dumps(val) if val is not None else None

            await session.execute(upsert_sql, params)
            inserted += 1

        await session.commit()
        print(f"pocusdb に {inserted} 件 upsert 完了")

    # 確認
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM venues"))
        total = result.scalar()
        result2 = await session.execute(
            text("SELECT COUNT(*) FROM venues WHERE visibility_status='visible'")
        )
        visible = result2.scalar()
        print(f"DB状態: total={total}, visible={visible}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(sync())
