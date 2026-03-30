"""国土地理院 住所検索API を使ったジオコーダー（無料・認証不要）

API: https://msearch.gsi.go.jp/address-search/AddressSearch?q=東京都渋谷区
レスポンス: [{"geometry": {"coordinates": [lng, lat]}, "properties": {"title": "..."}}]

精度方針: 小数2桁に丸め（約1km精度）でプライバシー配慮
"""

import logging
from collections import OrderedDict

import httpx

from tas.config import settings

logger = logging.getLogger(__name__)

GSI_URL = settings.gsi_geocode_url

# in-memory キャッシュ（プロセス内、最大N件LRU）
_CACHE_MAX = settings.geocoder_cache_max
_cache: OrderedDict[str, tuple[float, float] | None] = OrderedDict()

# 都道府県略称 → 正式名称（国土地理院APIは正式名称でないと誤マッチする）
_PREF_FULL: dict[str, str] = {
    "北海道": "北海道",
    "青森": "青森県", "岩手": "岩手県", "宮城": "宮城県", "秋田": "秋田県",
    "山形": "山形県", "福島": "福島県",
    "茨城": "茨城県", "栃木": "栃木県", "群馬": "群馬県", "埼玉": "埼玉県",
    "千葉": "千葉県", "東京": "東京都", "神奈川": "神奈川県",
    "新潟": "新潟県", "富山": "富山県", "石川": "石川県", "福井": "福井県",
    "山梨": "山梨県", "長野": "長野県", "岐阜": "岐阜県", "静岡": "静岡県",
    "愛知": "愛知県", "三重": "三重県",
    "滋賀": "滋賀県", "京都": "京都府", "大阪": "大阪府", "兵庫": "兵庫県",
    "奈良": "奈良県", "和歌山": "和歌山県",
    "鳥取": "鳥取県", "島根": "島根県", "岡山": "岡山県", "広島": "広島県",
    "山口": "山口県",
    "徳島": "徳島県", "香川": "香川県", "愛媛": "愛媛県", "高知": "高知県",
    "福岡": "福岡県", "佐賀": "佐賀県", "長崎": "長崎県", "熊本": "熊本県",
    "大分": "大分県", "宮崎": "宮崎県", "鹿児島": "鹿児島県", "沖縄": "沖縄県",
}


def _full_prefecture(pref: str) -> str:
    """'東京' → '東京都' のように正式名称に変換する"""
    return _PREF_FULL.get(pref, pref)


async def geocode(address: str) -> tuple[float, float] | None:
    """
    住所文字列 → (lat, lng) を返す。見つからなければ None。
    結果は小数2桁（約1km精度）に丸めて返す。
    """
    if not address or not address.strip():
        return None

    key = address.strip()
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]

    try:
        async with httpx.AsyncClient(timeout=settings.geocoder_timeout) as client:
            resp = await client.get(GSI_URL, params={"q": key})
            if resp.status_code != 200:
                logger.debug("GSI geocode failed: %d for %r", resp.status_code, key)
                _cache[key] = None
                if len(_cache) > _CACHE_MAX:
                    _cache.popitem(last=False)
                return None

            try:
                data = resp.json()
            except Exception:
                logger.debug("GSI geocode: invalid JSON for %r", key)
                _cache[key] = None
                if len(_cache) > _CACHE_MAX:
                    _cache.popitem(last=False)
                return None

            if not isinstance(data, list) or not data:
                _cache[key] = None
                if len(_cache) > _CACHE_MAX:
                    _cache.popitem(last=False)
                return None

            # coordinates = [lng, lat]
            coords = data[0].get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                _cache[key] = None
                if len(_cache) > _CACHE_MAX:
                    _cache.popitem(last=False)
                return None
            lat = round(coords[1], 2)  # 小数2桁 ≈ 1.1km精度
            lng = round(coords[0], 2)
            result: tuple[float, float] = (lat, lng)
            _cache[key] = result
            if len(_cache) > _CACHE_MAX:
                _cache.popitem(last=False)
            logger.debug("GSI geocode OK: %r → %s", key, result)
            return result

    except Exception as exc:
        logger.warning("GSI geocode error for %r: %s", key, exc)
        _cache[key] = None
        if len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
        return None


async def geocode_area(prefecture: str | None, city: str | None) -> tuple[float, float] | None:
    """
    都道府県 + 市区町村から座標を取得する。
    正式名称（東京都/大阪府など）に変換してからAPIを呼ぶ。
    cityがなければprefectureだけで試みる。
    """
    pref_full = _full_prefecture(prefecture) if prefecture else None

    if pref_full and city:
        result = await geocode(f"{pref_full}{city}")
        if result:
            return result

    if pref_full:
        return await geocode(pref_full)

    return None
