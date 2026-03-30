"""正規化・名寄せ・重複排除（POCUS：ポーカー店舗向け）"""

import math
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlparse

from tas.constants import ADDRESS_MATCH_THRESHOLD, EARTH_RADIUS_KM, GRAY_ZONE_ADDRESS_THRESHOLD


# 都道府県→緯度経度（市区町村中心・約1km精度に丸め）
PREFECTURE_COORDS: dict[str, tuple[float, float]] = {
    "北海道": (43.0642, 141.3469),
    "青森": (40.8244, 140.7400),
    "岩手": (39.7036, 141.1527),
    "宮城": (38.2688, 140.8721),
    "秋田": (39.7186, 140.1024),
    "山形": (38.2404, 140.3636),
    "福島": (37.7503, 140.4676),
    "茨城": (36.3418, 140.4468),
    "栃木": (36.5658, 139.8836),
    "群馬": (36.3911, 139.0608),
    "埼玉": (35.8570, 139.6489),
    "千葉": (35.6074, 140.1065),
    "東京": (35.6895, 139.6917),
    "神奈川": (35.4478, 139.6425),
    "新潟": (37.9022, 139.0236),
    "富山": (36.6953, 137.2113),
    "石川": (36.5947, 136.6256),
    "福井": (36.0652, 136.2216),
    "山梨": (35.6641, 138.5684),
    "長野": (36.6513, 138.1810),
    "岐阜": (35.3912, 136.7223),
    "静岡": (34.9769, 138.3831),
    "愛知": (35.1802, 136.9066),
    "三重": (34.7303, 136.5086),
    "滋賀": (35.0045, 135.8686),
    "京都": (35.0211, 135.7556),
    "大阪": (34.6864, 135.5200),
    "兵庫": (34.6913, 135.1830),
    "奈良": (34.6851, 135.8049),
    "和歌山": (34.2261, 135.1675),
    "鳥取": (35.5036, 134.2381),
    "島根": (35.4722, 133.0505),
    "岡山": (34.6618, 133.9350),
    "広島": (34.3963, 132.4596),
    "山口": (34.1858, 131.4706),
    "徳島": (34.0657, 134.5593),
    "香川": (34.3428, 134.0434),
    "愛媛": (33.8417, 132.7656),
    "高知": (33.5597, 133.5311),
    "福岡": (33.6064, 130.4183),
    "佐賀": (33.2494, 130.2988),
    "長崎": (32.7503, 129.8777),
    "熊本": (32.7898, 130.7417),
    "大分": (33.2382, 131.6126),
    "宮崎": (31.9111, 131.4239),
    "鹿児島": (31.5602, 130.5581),
    "沖縄": (26.2124, 127.6809),
}


def normalize_text(text: str) -> str:
    """NFKC正規化 + 全角英数→半角 + 前後空白除去"""
    text = unicodedata.normalize("NFKC", text)
    return text.strip()


def normalize_url(url: str) -> str:
    """URLを正規化する（スキーム統一、末尾スラッシュ除去）"""
    url = url.strip().rstrip("/")
    if url.startswith("//"):
        url = "https:" + url
    return url


def normalize_venue_name(name: str) -> str:
    """店舗名を正規化する"""
    name = normalize_text(name)
    # よくある不要サフィックスを除去（最初にマッチしたもので停止し二重除去を防ぐ）
    for suffix in ["ポーカールーム", "ポーカーバー", "ポーカー", "poker room", "poker bar", "poker"]:
        pattern = re.compile(re.escape(suffix), re.I)
        if pattern.search(name):
            cleaned = pattern.sub("", name).strip()
            if cleaned:
                name = cleaned
            break  # マッチした時点で終了（空になる場合も元の名前を維持）
    return name


def name_similarity(a: str, b: str) -> float:
    """名前の類似度を0.0〜1.0で返す"""
    a_norm = normalize_venue_name(a).lower()
    b_norm = normalize_venue_name(b).lower()
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def url_domain_match(url_a: str, url_b: str) -> bool:
    """2つのURLが同じドメインか判定する"""
    try:
        a = urlparse(normalize_url(url_a)).netloc.lower()
        b = urlparse(normalize_url(url_b)).netloc.lower()
        return a == b and a != ""
    except Exception:
        return False


def prefecture_to_coords(prefecture: str) -> tuple[float, float] | None:
    """都道府県名から緯度経度（約1km精度）を返す"""
    for key, coords in PREFECTURE_COORDS.items():
        if key in prefecture or prefecture in key:
            # 1km精度に丸め（小数4桁: ~11m → 2桁: ~1.1km）
            lat = round(coords[0], 2)
            lng = round(coords[1], 2)
            return lat, lng
    return None


def normalize_prefecture(text: str) -> str | None:
    """テキストから都道府県名を正規化して返す"""
    text = normalize_text(text)
    for pref in PREFECTURE_COORDS:
        if pref in text:
            return pref
    return None


def address_similarity(a: str, b: str) -> float:
    """住所の類似度を0.0〜1.0で返す"""
    a_norm = normalize_text(a).lower()
    b_norm = normalize_text(b).lower()
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点間のhaversine距離（km）を返す"""
    R = EARTH_RADIUS_KM
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def url_exact_match(url_a: str, url_b: str) -> bool:
    """2つのURLが同一パスか判定する（スキーム・末尾スラッシュを無視）"""
    try:
        a = urlparse(normalize_url(url_a))
        b = urlparse(normalize_url(url_b))
        return a.netloc.lower() == b.netloc.lower() and a.path.rstrip("/") == b.path.rstrip("/")
    except Exception:
        return False


def _is_root_page(url: str) -> bool:
    """URLがルートページ（深さ0）かどうかを判定する"""
    try:
        path = urlparse(url).path
        depth = len([p for p in path.split("/") if p])
        return depth == 0
    except Exception:
        return True


def find_duplicate_candidate(
    name: str,
    website_url: str | None,
    existing: list[dict],
    name_threshold: float = 0.85,
    address: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    proximity_km: float = 0.5,
) -> dict | None:
    """
    既存スタジオリストから重複候補を見つける。
    URL完全一致 → ドメイン一致（ルートページのみ） → 名前+住所+座標近接 の順で判定。

    existing: [{"name": str, "website_url": str|None, "address": str|None,
                "lat": float|None, "lng": float|None, ...}, ...]
    """
    # 1. URL完全一致（最優先）
    if website_url:
        for item in existing:
            if item.get("website_url") and url_exact_match(website_url, item["website_url"]):
                return item

    # 2. ドメイン一致（双方がルートページの場合のみ）
    if website_url and _is_root_page(website_url):
        for item in existing:
            if item.get("website_url") and _is_root_page(item["website_url"]) and url_domain_match(website_url, item["website_url"]):
                return item

    # 3. 名前類似度 + 住所または座標近接による複合判定
    for item in existing:
        name_sim = name_similarity(name, item.get("name", ""))
        if name_sim < name_threshold:
            continue

        # 名前が閾値以上の場合、住所または座標で確認
        item_lat = item.get("lat")
        item_lng = item.get("lng")
        if lat is not None and lng is not None and item_lat is not None and item_lng is not None:
            dist = haversine_distance_km(lat, lng, float(item_lat), float(item_lng))
            if dist <= proximity_km:
                return item
            # 座標が離れていれば別店舗とみなす（名前だけで誤マッチしない）
            continue

        # 座標がない場合は住所類似度で補完
        if address and item.get("address"):
            addr_sim = address_similarity(address, item["address"])
            if addr_sim >= ADDRESS_MATCH_THRESHOLD:
                return item
            continue

        # 住所も座標もない場合は名前のみで判定（後退フォールバック）
        return item

    return None


def find_gray_zone_candidates(
    name: str,
    website_url: str | None,
    existing: list[dict],
    min_score: float = 0.5,
    max_score: float = 0.85,
    address: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    proximity_km: float = 2.0,
) -> list[dict]:
    """
    名前類似度がmin_score以上max_score未満 かつ 住所または座標が近い候補（グレーゾーン）を返す。
    VenueMergeCandidateの自動登録に使用する。
    """
    candidates = []
    for item in existing:
        name_sim = name_similarity(name, item.get("name", ""))
        if not (min_score <= name_sim < max_score):
            continue

        # 座標が両方ある場合は近接チェック
        item_lat = item.get("lat")
        item_lng = item.get("lng")
        if lat is not None and lng is not None and item_lat is not None and item_lng is not None:
            dist = haversine_distance_km(lat, lng, float(item_lat), float(item_lng))
            if dist <= proximity_km:
                candidates.append(item)
            continue

        # 住所がある場合は住所類似度チェック
        if address and item.get("address"):
            addr_sim = address_similarity(address, item["address"])
            if addr_sim >= GRAY_ZONE_ADDRESS_THRESHOLD:
                candidates.append(item)
            continue

        # 住所も座標もない場合は名前類似度だけで候補登録
        candidates.append(item)

    return candidates


def build_match_evidence(
    name: str,
    website_url: str | None,
    candidate: dict,
    address: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict:
    """名寄せ根拠を構造化して返す"""
    evidence: dict = {}
    if website_url and candidate.get("website_url"):
        evidence["url_match"] = url_domain_match(website_url, candidate["website_url"])
    evidence["name_similarity"] = round(
        name_similarity(name, candidate.get("name", "")), 3
    )
    if address and candidate.get("address"):
        evidence["address_similarity"] = round(
            address_similarity(address, candidate["address"]), 3
        )
    item_lat = candidate.get("lat")
    item_lng = candidate.get("lng")
    if lat is not None and lng is not None and item_lat is not None and item_lng is not None:
        evidence["distance_km"] = round(
            haversine_distance_km(lat, lng, float(item_lat), float(item_lng)), 3
        )
    return evidence
