"""parser.py のユニットテスト（POCUS：ポーカー店舗向け）"""

import pytest

from tas.crawler.parser import (
    ParsedTournament,
    _extract_address,
    _extract_drink_required,
    _extract_food_level,
    _extract_hours,
    _extract_peak_time,
    _extract_price,
    _extract_table_count,
    _extract_tournaments,
    _remove_personal_info,
    _extract_prefecture,
    parse_html,
)
from bs4 import BeautifulSoup


SAMPLE_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
  <title>渋谷ポーカールーム | SHIBUYA POKER</title>
  <meta name="description" content="東京都渋谷区のポーカールーム。毎日営業中。予約はDMまたはお問合せフォームから。">
  <meta property="og:title" content="SHIBUYA POKER">
  <meta property="og:site_name" content="SHIBUYA POKER">
</head>
<body>
  <h1>SHIBUYA POKER - 渋谷のポーカールーム</h1>
  <p>東京都渋谷区道玄坂にあるポーカールームです。</p>
  <a href="https://www.instagram.com/shibuya_poker/">Instagram</a>
  <a href="/contact">予約・お問合せ</a>
  <a href="https://twitter.com/shibuya_poker">Twitter</a>
</body>
</html>"""


# ─── 既存テスト ───────────────────────────────────────────────

def test_parse_basic_fields():
    page = parse_html("https://shibuya-poker.jp/", SAMPLE_HTML)
    assert page.title == "渋谷ポーカールーム | SHIBUYA POKER"
    assert "東京都渋谷区" in page.meta_description
    assert page.h1 == "SHIBUYA POKER - 渋谷のポーカールーム"


def test_parse_venue_name_from_og_site():
    page = parse_html("https://shibuya-poker.jp/", SAMPLE_HTML)
    assert page.venue_name == "SHIBUYA POKER"
    assert page.field_confidence.get("venue_name") == "H"


def test_parse_area_prefecture():
    page = parse_html("https://shibuya-poker.jp/", SAMPLE_HTML)
    assert page.area_prefecture == "東京"


def test_parse_area_city():
    page = parse_html("https://shibuya-poker.jp/", SAMPLE_HTML)
    assert page.area_city is not None


def test_parse_sns_links():
    page = parse_html("https://shibuya-poker.jp/", SAMPLE_HTML)
    assert "instagram" in page.sns_links


def test_parse_booking_url():
    page = parse_html("https://shibuya-poker.jp/", SAMPLE_HTML)
    assert page.booking_url is not None
    assert "contact" in page.booking_url


def test_parse_links_count():
    page = parse_html("https://shibuya-poker.jp/", SAMPLE_HTML)
    assert page.links_count >= 2


def test_overall_confidence():
    page = parse_html("https://shibuya-poker.jp/", SAMPLE_HTML)
    conf = page.overall_confidence()
    assert 0.0 <= conf <= 1.0


def test_remove_personal_info_email():
    text = "問い合わせ: john.doe@private-poker.co.jp まで"
    result = _remove_personal_info(text)
    assert "john.doe@private-poker.co.jp" not in result
    assert "[EMAIL_REMOVED]" in result


def test_remove_personal_info_phone():
    text = "TEL: 090-1234-5678"
    result = _remove_personal_info(text)
    assert "090-1234-5678" not in result
    assert "[PHONE_REMOVED]" in result


def test_extract_prefecture():
    assert _extract_prefecture("東京都渋谷区") == "東京"
    assert _extract_prefecture("大阪市北区") == "大阪"
    assert _extract_prefecture("北海道札幌市") == "北海道"
    assert _extract_prefecture("no prefecture here") is None


def test_parse_minimal_html():
    minimal = "<html><body><h1>Test Poker Room</h1></body></html>"
    page = parse_html("https://test.jp/", minimal)
    assert page.venue_name == "Test Poker Room"
    assert page.field_confidence.get("venue_name") == "L"


def test_parse_empty_html():
    page = parse_html("https://test.jp/", "")
    assert page.title == ""
    assert page.venue_name is None


# ─── 新規テスト: 住所抽出 ────────────────────────────────────

def test_extract_address_with_postal():
    body = "所在地: 〒150-0043 東京都渋谷区道玄坂1-2-3 ポーカービル"
    result = _extract_address(body)
    assert result is not None
    assert "東京" in result


def test_extract_address_prefecture_prefix():
    body = "東京都新宿区歌舞伎町1-2-3 にあります"
    result = _extract_address(body)
    assert result is not None
    assert "東京都新宿区" in result


def test_extract_address_none_when_missing():
    body = "ポーカーが楽しめる店です"
    result = _extract_address(body)
    assert result is None


# ─── 新規テスト: 営業時間抽出 ────────────────────────────────

def test_extract_hours_with_keyword():
    html = "<html><body><p>営業時間: 18:00〜翌3:00</p></body></html>"
    soup = BeautifulSoup(html, "lxml")
    body = soup.get_text(separator=" ")
    result = _extract_hours(soup, body)
    assert result is not None
    assert "18:00" in result


def test_extract_hours_time_range_only():
    html = "<html><body><p>毎日 19:00〜翌5:00 営業</p></body></html>"
    soup = BeautifulSoup(html, "lxml")
    body = soup.get_text(separator=" ")
    result = _extract_hours(soup, body)
    assert result is not None
    assert "19:00" in result


def test_extract_hours_none_when_missing():
    html = "<html><body><p>ポーカールームです</p></body></html>"
    soup = BeautifulSoup(html, "lxml")
    body = soup.get_text(separator=" ")
    result = _extract_hours(soup, body)
    assert result is None


# ─── 新規テスト: 料金抽出 ────────────────────────────────────

def test_extract_price_basic():
    body = "初回入場料 ¥2,000 より"
    price, note = _extract_price(body)
    assert price == 2000
    assert note is not None


def test_extract_price_buyin():
    body = "バイイン 3,000円 ワンドリンク込み"
    price, note = _extract_price(body)
    assert price == 3000


def test_extract_price_none_when_missing():
    body = "ポーカーが楽しめます"
    price, note = _extract_price(body)
    assert price is None
    assert note is None


# ─── 新規テスト: P1フィールド抽出 ────────────────────────────

def test_extract_drink_required_true():
    assert _extract_drink_required("ワンドリンク制です") is True


def test_extract_drink_required_none():
    assert _extract_drink_required("ポーカールームです") is None


def test_extract_food_level_rich():
    assert _extract_food_level("フードメニュー充実！ランチも営業") == "rich"


def test_extract_food_level_basic():
    assert _extract_food_level("軽食もご用意しています") == "basic"


def test_extract_food_level_none_keyword():
    assert _extract_food_level("フードなし、ドリンクのみ") == "none"


def test_extract_food_level_unknown():
    assert _extract_food_level("ポーカーを楽しめます") is None


def test_extract_table_count_basic():
    body = "ポーカーテーブル8台完備"
    result = _extract_table_count(body)
    assert result == 8


def test_extract_table_count_none():
    body = "ポーカーが楽しめます"
    result = _extract_table_count(body)
    assert result is None


def test_extract_peak_time():
    body = "ピークタイムは20:00〜24:00です"
    result = _extract_peak_time(body)
    assert result is not None
    assert "20:00" in result


# ─── 新規テスト: トーナメント抽出 ───────────────────────────

TOURNAMENT_HTML = """<html>
<body>
  <ul>
    <li>
      <h3>ウィークリートーナメント</h3>
      <p>3/15 20:00スタート バイイン: 3,000円 定員:30名</p>
      <a href="/tournament/weekly">詳細</a>
    </li>
    <li>
      <h3>スペシャルイベント</h3>
      <p>2025年4月1日 18:00〜 バイイン: ¥5,000 ギャランティ: 100,000円</p>
      <a href="/tournament/special">詳細</a>
    </li>
  </ul>
</body>
</html>"""


def test_extract_tournaments_finds_entries():
    soup = BeautifulSoup(TOURNAMENT_HTML, "lxml")
    body = soup.get_text(separator=" ")
    results = _extract_tournaments(soup, "https://poker.jp/", body)
    assert len(results) >= 1


def test_extract_tournament_title():
    soup = BeautifulSoup(TOURNAMENT_HTML, "lxml")
    body = soup.get_text(separator=" ")
    results = _extract_tournaments(soup, "https://poker.jp/", body)
    titles = [t.title for t in results]
    assert any("ウィークリー" in title or "スペシャル" in title for title in titles)


def test_extract_tournament_buy_in():
    soup = BeautifulSoup(TOURNAMENT_HTML, "lxml")
    body = soup.get_text(separator=" ")
    results = _extract_tournaments(soup, "https://poker.jp/", body)
    buy_ins = [t.buy_in for t in results if t.buy_in is not None]
    assert len(buy_ins) > 0
    assert any(b in (3000, 5000) for b in buy_ins)


def test_extract_tournament_with_date():
    soup = BeautifulSoup(TOURNAMENT_HTML, "lxml")
    body = soup.get_text(separator=" ")
    results = _extract_tournaments(soup, "https://poker.jp/", body)
    dated = [t for t in results if t.start_at is not None]
    assert len(dated) >= 1


def test_extract_tournaments_empty_html():
    html = "<html><body><p>普通のページです</p></body></html>"
    soup = BeautifulSoup(html, "lxml")
    body = soup.get_text(separator=" ")
    results = _extract_tournaments(soup, "https://poker.jp/", body)
    assert results == []


def test_parse_html_with_full_venue_info():
    """parse_html が新フィールドを統合して抽出する統合テスト"""
    html = """<html>
    <head>
      <meta property="og:site_name" content="新宿ポーカークラブ">
      <meta name="description" content="東京都新宿区のポーカールーム。初回入場料2,000円。ポーカーテーブル10台。">
    </head>
    <body>
      <p>〒160-0021 東京都新宿区歌舞伎町1-2-3</p>
      <p>営業時間: 18:00〜翌4:00</p>
      <p>初回入場 ¥2,000（ワンドリンク込み）</p>
      <p>ポーカーテーブル10台完備</p>
      <p>軽食もご用意しています</p>
    </body>
    </html>"""
    page = parse_html("https://shinjuku-poker.jp/", html)
    assert page.venue_name == "新宿ポーカークラブ"
    assert page.area_prefecture == "東京"
    assert page.address is not None
    assert page.hours_raw is not None
    assert page.price_entry_min == 2000
    assert page.drink_required is True
    assert page.table_count == 10
    assert page.food_level in ("basic", "rich", None)
