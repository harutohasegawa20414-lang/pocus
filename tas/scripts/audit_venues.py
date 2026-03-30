"""既存21件の精査 + seedData56件との重複検出スクリプト"""

import asyncio
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from tas.db.session import AsyncSessionLocal, engine


class Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return str(o)


async def main():
    # 1. DB から全件取得
    async with AsyncSessionLocal() as s:
        r = await s.execute(text(
            "SELECT id, name, address, area_prefecture, area_city, "
            "lat, lng, website_url, created_at "
            "FROM venues ORDER BY created_at, name"
        ))
        all_venues = [dict(zip(r.keys(), row)) for row in r.fetchall()]

    # seedData JSON 読み込み
    seed_path = os.path.join(os.path.dirname(__file__), "seed_venues.json")
    with open(seed_path) as f:
        seeds = json.load(f)
    seed_urls = {s.get("website_url", "").rstrip("/").lower() for s in seeds if s.get("website_url")}
    seed_names = {s.get("name", "") for s in seeds}

    # 2. 元の21件 vs seed56件を分離（created_atで判別）
    # seed は直近にインポートしたのでcreated_atが新しい
    sorted_by_time = sorted(all_venues, key=lambda v: str(v["created_at"]))
    original = sorted_by_time[:21] if len(sorted_by_time) >= 21 else sorted_by_time

    print("=" * 80)
    print(f"既存 {len(original)} 件の精査結果")
    print("=" * 80)

    duplicates = []
    issues = []

    for v in original:
        vid = str(v["id"])
        name = v["name"]
        url = (v.get("website_url") or "").rstrip("/").lower()
        lat = float(v["lat"]) if v["lat"] else None
        lng = float(v["lng"]) if v["lng"] else None
        pref = v.get("area_prefecture") or ""
        addr = v.get("address") or ""

        row_issues = []

        # 重複チェック: URLで一致
        if url and url in seed_urls:
            duplicates.append({"id": vid, "name": name, "match_type": "URL", "url": url})

        # 重複チェック: 名前の部分一致
        for sn in seed_names:
            if sn and name and (sn in name or name in sn) and sn != name:
                duplicates.append({"id": vid, "name": name, "match_type": "name_partial", "seed_name": sn})
            elif sn == name:
                duplicates.append({"id": vid, "name": name, "match_type": "name_exact"})

        # 座標チェック: 都道府県と座標の整合性
        if lat and lng:
            # 大まかな範囲チェック
            if pref == "東京" or "東京" in addr:
                if not (35.5 <= lat <= 35.9 and 139.4 <= lng <= 139.9):
                    row_issues.append(f"座標が東京の範囲外: lat={lat}, lng={lng}")
            elif pref == "大阪" or "大阪" in addr:
                if not (34.5 <= lat <= 34.9 and 135.3 <= lng <= 135.7):
                    row_issues.append(f"座標が大阪の範囲外: lat={lat}, lng={lng}")
            elif pref == "神奈川" or "神奈川" in addr or "横浜" in addr:
                if not (35.2 <= lat <= 35.7 and 139.4 <= lng <= 139.8):
                    row_issues.append(f"座標が神奈川の範囲外: lat={lat}, lng={lng}")
            elif pref == "愛知" or "名古屋" in name:
                if not (34.9 <= lat <= 35.4 and 136.7 <= lng <= 137.2):
                    row_issues.append(f"座標が愛知の範囲外: lat={lat}, lng={lng}")
            elif pref == "沖縄" or "沖縄" in addr or "NAHA" in name:
                if not (26.0 <= lat <= 26.9 and 127.5 <= lng <= 128.3):
                    row_issues.append(f"座標が沖縄の範囲外: lat={lat}, lng={lng}")
            elif pref == "千葉" or "千葉" in addr or "松戸" in name:
                if not (35.3 <= lat <= 36.0 and 139.7 <= lng <= 140.5):
                    row_issues.append(f"座標が千葉の範囲外: lat={lat}, lng={lng}")
            elif pref == "茨城" or "茨城" in addr or "取手" in name:
                if not (35.7 <= lat <= 36.5 and 139.7 <= lng <= 140.7):
                    row_issues.append(f"座標が茨城の範囲外: lat={lat}, lng={lng}")
            elif pref == "群馬" or "群馬" in addr or "伊勢崎" in name:
                if not (36.0 <= lat <= 36.8 and 138.8 <= lng <= 139.7):
                    row_issues.append(f"座標が群馬の範囲外: lat={lat}, lng={lng}")
            elif pref == "長野" or "松本" in name:
                if not (35.5 <= lat <= 37.0 and 137.5 <= lng <= 138.8):
                    row_issues.append(f"座標が長野の範囲外: lat={lat}, lng={lng}")
            elif pref == "高知" or "高知" in name:
                if not (33.0 <= lat <= 33.8 and 132.5 <= lng <= 134.3):
                    row_issues.append(f"座標が高知の範囲外: lat={lat}, lng={lng}")

        # 名前チェック
        if name and ("ポーカーをしよう" in name or "プライベート空間" in name):
            row_issues.append(f"店名がキャッチコピー風: {name}")

        if not addr or addr == "":
            row_issues.append("住所なし")

        if row_issues:
            issues.append({"id": vid, "name": name, "issues": row_issues,
                           "lat": lat, "lng": lng, "pref": pref, "url": v.get("website_url")})

    # 出力
    print("\n--- 重複候補 ---")
    seen = set()
    for d in duplicates:
        key = (d["id"], d.get("match_type"))
        if key in seen:
            continue
        seen.add(key)
        print(f"  [{d['match_type']}] {d['name']}")
        if d.get("seed_name"):
            print(f"    → seed側: {d['seed_name']}")
        if d.get("url"):
            print(f"    URL: {d['url']}")

    print(f"\n--- データ問題 ({len(issues)} 件) ---")
    for iss in issues:
        print(f"\n  {iss['name']} (pref={iss['pref']})")
        print(f"    URL: {iss.get('url')}")
        print(f"    lat={iss['lat']}, lng={iss['lng']}")
        for i in iss["issues"]:
            print(f"    !! {i}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
