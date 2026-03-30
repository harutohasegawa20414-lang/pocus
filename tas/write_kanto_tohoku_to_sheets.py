"""関東・東北ポーカー情報をGoogleシートに書き込む"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from tas import sheets as svc

# ══════════════════════════════════════════════════════
# Sheet: 店舗一覧（関東・東北）
# ══════════════════════════════════════════════════════
venues_header = [
    "地方", "都道府県", "店舗名", "住所", "営業状況",
    "公式URL", "SNS", "備考",
]

venues_rows = [
    # ─── 関東 ───────────────────────────────────────
    ["関東", "東京", "ROOTS Shibuya",
     "東京都渋谷区宇田川町31-1", "営業中",
     "https://roots-poker.com", "", "大型ポーカールーム"],
    ["関東", "東京", "m HOLD'EM 目黒",
     "東京都目黒区目黒1-3-15", "営業中",
     "https://mpj-portal.jp", "", "リング・トーナメント"],
    ["関東", "東京", "GoodGame Poker Live 渋谷",
     "東京都渋谷区宇田川町12-9", "営業中",
     "https://ggpokerlive.jp", "", "初心者講習あり"],
    ["関東", "東京", "KKLIVE POKER Shibuya",
     "東京都渋谷区宇田川町12-7", "営業中",
     "https://kklivepoker.com", "", "キャッシュレス対応"],
    ["関東", "東京", "KKLIVE POKER Shinjuku",
     "東京都新宿区歌舞伎町1-23-15", "営業中",
     "https://kklivepoker.com", "", "大型ポーカールーム"],
    ["関東", "神奈川", "LIVE ACE Yokohama",
     "神奈川県横浜市西区南幸2-6-22", "営業中",
     "https://live-ace.site", "", "トーナメント中心"],
    ["関東", "神奈川", "PreFlop Yokohama",
     "神奈川県横浜市西区南幸1-13-13", "営業中",
     "https://preflop.jp", "", "横浜駅近く"],
    ["関東", "神奈川", "Poker Bar GOLD JOKER",
     "神奈川県横浜市中区吉田町12-1", "営業中",
     "https://sites.google.com/view/goldjoker", "", "初心者講習あり"],
    ["関東", "千葉", "KINGS 千葉",
     "千葉県千葉市中央区栄町41-10", "営業中",
     "https://kingscasino.jp", "", "スクールあり"],
    ["関東", "千葉", "Poker House POM",
     "千葉県船橋市前原西2-15-1", "営業中",
     "https://pokerhouse-pom.com", "", "津田沼駅近"],
    ["関東", "千葉", "RAT POKER",
     "千葉県千葉市中央区富士見2-15-8", "営業中",
     "http://ratspoker.chu-rou-dou.com", "", "深夜営業"],
    ["関東", "茨城", "BACKDOOR 水戸",
     "茨城県水戸市大工町1-6-18", "営業中",
     "https://mito.backdoor.casino", "", "カジノゲーム併設"],
    ["関東", "茨城", "KINGS 取手",
     "茨城県取手市取手2-3-1", "営業中",
     "https://kingscasino.jp", "", "リングゲーム"],
    ["関東", "栃木", "BACKDOOR 宇都宮",
     "栃木県宇都宮市江野町1-1", "営業中",
     "https://utsunomiya.backdoor.casino", "", "初心者講習あり"],
    # ─── 東北 ───────────────────────────────────────
    ["東北", "青森", "8Quads",
     "青森県八戸市長横町7-1", "営業中",
     "", "Instagram等", "アミューズメントカジノ"],
    ["東北", "青森", "OUTS 弘前",
     "青森県弘前市土手町4", "営業中",
     "", "SNS中心", "リング/トーナメント"],
    ["東北", "青森", "HAKU Poker Bar",
     "青森県弘前市代官町45-1", "営業中",
     "", "Instagram", "初心者講習"],
    ["東北", "青森", "CHIPS POKER",
     "青森県五所川原市寺町54-1", "営業中",
     "", "Instagram", "初心者歓迎"],
    ["東北", "岩手", "Poker Bar BLUFF",
     "岩手県盛岡市大通2-3-3", "営業中",
     "https://pokerbar-bluff.com", "", "ポーカーバー"],
    ["東北", "宮城", "9High 仙台",
     "宮城県仙台市青葉区花京院1-4-47", "営業中",
     "https://9high.jp/sendai", "", "トーナメント"],
    ["東北", "宮城", "BACKDOOR 仙台",
     "宮城県仙台市青葉区国分町2-1-15", "営業中",
     "https://sendai.backdoor.casino", "", "カジノゲーム"],
    ["東北", "宮城", "DEERGOLD",
     "宮城県仙台市青葉区一番町4-9-1", "営業中",
     "https://www.unputenpu0308.com/deergold", "", "大型店"],
    ["東北", "山形", "5656ポーカー倶楽部",
     "山形県鶴岡市本町1-6-21", "営業中",
     "https://5656.jimdosite.com", "", "庄内エリア初"],
    ["東北", "山形", "Brilliant Space LOL",
     "山形県山形市七日町2-7-38", "営業中",
     "", "SNS中心", "毎日トーナメント"],
    ["東北", "福島", "ACE&KING FUKUSHIMA",
     "福島県福島市栄町12-12", "営業中",
     "https://aceking.site", "", "アミューズメントカジノ"],
    ["東北", "福島", "Casino Bar Alice",
     "福島県いわき市平白銀町5-11", "営業中",
     "https://alice-iwaki.com", "", "プロディーラー在籍"],
]

# ══════════════════════════════════════════════════════
# Sheet: 大会・イベント（関東・東北）
# ══════════════════════════════════════════════════════
events_header = [
    "大会名", "地方", "開催地", "会場", "開催頻度",
    "公式URL", "規模・備考",
]

events_rows = [
    ["JOPT Tokyo",
     "関東", "東京都新宿区", "ベルサール高田馬場",
     "定期開催", "https://japanopenpoker.com", "国内最大級大会"],
    ["百花繚乱ポーカー",
     "東北", "宮城県仙台市", "秋保リゾートホテル",
     "年1回", "https://light-three.com/hyakkaryouran", "東北大型大会"],
]

# ══════════════════════════════════════════════════════
# 書き込み実行
# ══════════════════════════════════════════════════════
sheets = [
    ("店舗一覧（関東・東北）", [venues_header] + venues_rows),
    ("大会・イベント（関東・東北）", [events_header] + events_rows),
]

for name, rows in sheets:
    print(f"シート「{name}」を書き込み中...")
    n = svc.clear_and_write(name, rows)
    print(f"  → {n} 行完了")

print("\n✓ 全シートへの書き込みが完了しました。")
