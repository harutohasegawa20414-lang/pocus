/**
 * スプレッドシート「pocus」から抽出した店舗シードデータ
 * 北海道 13店舗 + 関東・東北 26店舗 + 中部 17店舗 = 合計 56店舗
 */
import type { VenuePin, VenueCard, VenueDetail } from '../types/api'
import { PIN_JITTER_RANGE } from '../constants'
import { MS_PER_DAY, DEFAULT_MAP_CENTER } from '../constants'

// ── 生データ型 ─────────────────────────────────────────
export interface SeedVenue {
    id: string
    name: string
    group: string
    area: string
    prefecture: string
    address: string
    phone: string
    hoursWeekday: string
    hoursWeekend: string
    hoursSunday: string
    priceGeneral: string
    priceDiscount: string
    priceNote: string
    websiteUrl: string
    snsX: string
    snsInstagram: string
    access: string
    license: string
    paymentMethod: string
    ringGameRate: string
    chipDepositPeriod: string
    status: string
    note: string
}

// ── 都道府県マッピング ──────────────────────────────────
function prefectureFromArea(area: string, address: string): string {
    if (area.includes('札幌') || area.includes('旭川') || area.includes('函館') || area.includes('帯広'))
        return '北海道'
    if (address.startsWith('東京')) return '東京都'
    if (address.startsWith('神奈川')) return '神奈川県'
    if (address.startsWith('千葉')) return '千葉県'
    if (address.startsWith('茨城')) return '茨城県'
    if (address.startsWith('栃木')) return '栃木県'
    if (address.startsWith('青森')) return '青森県'
    if (address.startsWith('岩手')) return '岩手県'
    if (address.startsWith('宮城')) return '宮城県'
    if (address.startsWith('山形')) return '山形県'
    if (address.startsWith('福島')) return '福島県'
    if (address.startsWith('愛知') || address.includes('名古屋')) return '愛知県'
    if (address.startsWith('静岡') || address.includes('浜松')) return '静岡県'
    if (address.startsWith('石川') || address.includes('金沢')) return '石川県'
    if (address.includes('北海道')) return '北海道'
    return ''
}

function cityFromArea(area: string, address: string): string {
    if (area.includes('札幌') || area.includes('すすきの')) return '札幌市'
    if (area.includes('旭川')) return '旭川市'
    if (area.includes('函館')) return '函館市'
    if (area.includes('帯広')) return '帯広市'
    if (area.includes('名古屋') || area.includes('大須')) return '名古屋市'
    if (area.includes('浜松')) return '浜松市'
    if (area.includes('金沢')) return '金沢市'
    // アドレスから推測
    if (address.includes('渋谷区')) return '渋谷区'
    if (address.includes('目黒区')) return '目黒区'
    if (address.includes('新宿区')) return '新宿区'
    if (address.includes('横浜市')) return '横浜市'
    if (address.includes('千葉市')) return '千葉市'
    if (address.includes('船橋市')) return '船橋市'
    if (address.includes('水戸市')) return '水戸市'
    if (address.includes('取手市')) return '取手市'
    if (address.includes('宇都宮市')) return '宇都宮市'
    if (address.includes('八戸市')) return '八戸市'
    if (address.includes('弘前市')) return '弘前市'
    if (address.includes('五所川原市')) return '五所川原市'
    if (address.includes('盛岡市')) return '盛岡市'
    if (address.includes('仙台市')) return '仙台市'
    if (address.includes('鶴岡市')) return '鶴岡市'
    if (address.includes('山形市')) return '山形市'
    if (address.includes('福島市')) return '福島市'
    if (address.includes('いわき市')) return 'いわき市'
    return ''
}

// ── 緯度経度（主要エリアのおおよその座標）───────────────
const AREA_COORDS: Record<string, { lat: number; lng: number }> = {
    // 北海道
    'すすきの': { lat: 43.0547, lng: 141.3539 },
    '札幌': { lat: 43.0621, lng: 141.3544 },
    '旭川': { lat: 43.7709, lng: 142.3650 },
    '函館': { lat: 41.7687, lng: 140.7288 },
    '帯広': { lat: 42.9236, lng: 143.1966 },
    // 関東
    '渋谷': { lat: 35.6580, lng: 139.7016 },
    '目黒': { lat: 35.6337, lng: 139.7157 },
    '新宿': { lat: 35.6896, lng: 139.7006 },
    '横浜西': { lat: 35.4614, lng: 139.6188 },
    '横浜中': { lat: 35.4437, lng: 139.6380 },
    '千葉': { lat: 35.6074, lng: 140.1065 },
    '船橋': { lat: 35.6947, lng: 139.9868 },
    '水戸': { lat: 36.3704, lng: 140.4740 },
    '取手': { lat: 35.9112, lng: 140.0508 },
    '宇都宮': { lat: 36.5593, lng: 139.8836 },
    // 東北
    '八戸': { lat: 40.5121, lng: 141.4882 },
    '弘前': { lat: 40.6030, lng: 140.4641 },
    '五所川原': { lat: 40.8058, lng: 140.4433 },
    '盛岡': { lat: 39.7036, lng: 141.1527 },
    '仙台': { lat: 38.2682, lng: 140.8694 },
    '鶴岡': { lat: 38.7273, lng: 139.8265 },
    '山形': { lat: 38.2404, lng: 140.3634 },
    '福島': { lat: 37.7503, lng: 140.4676 },
    'いわき': { lat: 36.9475, lng: 140.8876 },
    // 中部
    '名古屋': { lat: 35.1706, lng: 136.8816 },
    '名古屋栄': { lat: 35.1704, lng: 136.9066 },
    '名古屋大須': { lat: 35.1580, lng: 136.9025 },
    '名古屋住吉': { lat: 35.1668, lng: 136.9045 },
    '名古屋栄東': { lat: 35.1685, lng: 136.9100 },
    '名古屋久屋大通': { lat: 35.1740, lng: 136.9080 },
    '名古屋伏見': { lat: 35.1695, lng: 136.8970 },
    '名古屋錦': { lat: 35.1720, lng: 136.9020 },
    '名古屋新栄': { lat: 35.1680, lng: 136.9180 },
    '浜松': { lat: 34.7100, lng: 137.7261 },
    '金沢': { lat: 36.5613, lng: 136.6562 },
}

function getCoords(area: string, address: string): { lat: number; lng: number } {
    // 文字数の長い（具体的な）エリア名から順にチェック
    const sortedKeys = Object.keys(AREA_COORDS).sort((a, b) => b.length - a.length)
    for (const key of sortedKeys) {
        if (area.includes(key)) return AREA_COORDS[key]
    }
    // アドレスからチェック  
    if (address.includes('渋谷')) return AREA_COORDS['渋谷']
    if (address.includes('目黒')) return AREA_COORDS['目黒']
    if (address.includes('新宿') || address.includes('歌舞伎町')) return AREA_COORDS['新宿']
    if (address.includes('横浜市西区')) return AREA_COORDS['横浜西']
    if (address.includes('横浜市中区')) return AREA_COORDS['横浜中']
    if (address.includes('千葉市') || address.includes('千葉県千葉市')) return AREA_COORDS['千葉']
    if (address.includes('船橋')) return AREA_COORDS['船橋']
    if (address.includes('水戸')) return AREA_COORDS['水戸']
    if (address.includes('取手')) return AREA_COORDS['取手']
    if (address.includes('宇都宮')) return AREA_COORDS['宇都宮']
    if (address.includes('八戸')) return AREA_COORDS['八戸']
    if (address.includes('弘前')) return AREA_COORDS['弘前']
    if (address.includes('五所川原')) return AREA_COORDS['五所川原']
    if (address.includes('盛岡')) return AREA_COORDS['盛岡']
    if (address.includes('仙台')) return AREA_COORDS['仙台']
    if (address.includes('鶴岡')) return AREA_COORDS['鶴岡']
    if (address.includes('山形市') || address.includes('山形県山形市')) return AREA_COORDS['山形']
    if (address.includes('福島市') || address.includes('福島県福島市')) return AREA_COORDS['福島']
    if (address.includes('いわき')) return AREA_COORDS['いわき']
    if (address.includes('名古屋') || address.includes('愛知県名古屋市')) return AREA_COORDS['名古屋']
    if (address.includes('浜松') || address.includes('静岡県浜松市')) return AREA_COORDS['浜松']
    if (address.includes('金沢') || address.includes('石川県金沢市')) return AREA_COORDS['金沢']
    if (address.includes('札幌')) return AREA_COORDS['札幌']
    if (address.includes('北海道')) return AREA_COORDS['札幌']
    return { lat: DEFAULT_MAP_CENTER[0], lng: DEFAULT_MAP_CENTER[1] }
}

// ── 料金文字列→数値 ─────────────────────────────────────
function parsePriceMin(priceStr: string): number | null {
    if (!priceStr) return null
    const m = priceStr.replace(/,/g, '').match(/(\d+)/)
    return m ? Number(m[1]) : null
}

// ── 営業時間のマージ ─────────────────────────────────────
function mergeHours(weekday: string, weekend: string, sunday: string): string | null {
    const parts = [weekday, weekend, sunday].filter(Boolean)
    return parts.length > 0 ? parts.join(' / ') : null
}

// ══════════════════════════════════════════════════════
// 北海道 店舗データ（13店舗）
// ══════════════════════════════════════════════════════
const hokkaidoVenues: SeedVenue[] = [
    {
        id: 'seed-hk-001', name: 'ポーカークラブ キングスマン すすきの店',
        group: 'キングスマングループ（本店）', area: '札幌（すすきの）', prefecture: '北海道',
        address: '〒064-0804 北海道札幌市中央区南4条西5丁目4-4 シャンゼリゼビル5F',
        phone: '011-215-1331',
        hoursWeekday: '月〜金 16:00-24:00', hoursWeekend: '土祝 13:30-24:00', hoursSunday: '日 13:30-22:30',
        priceGeneral: '4,400円', priceDiscount: '3,300円', priceNote: 'ドリンク飲み放題・ゲームチケット込',
        websiteUrl: 'https://sapporo-kingsman.com/', snsX: '', snsInstagram: '',
        access: 'すすきの駅4番出口より徒歩約4分', license: '風営法5号取得済み', paymentMethod: '',
        ringGameRate: '$1-$3', chipDepositPeriod: '3ヶ月', status: '営業中',
        note: '公式YouTubeチャンネルあり。北海道内最多店舗数のリーディングカンパニー本店。',
    },
    {
        id: 'seed-hk-002', name: 'BLOW すすきの',
        group: '独立系', area: '札幌（すすきの）', prefecture: '北海道',
        address: '〒064-0804 北海道札幌市中央区南4条西4丁目1番地 COCONO SUSUKINO 4F',
        phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: '', snsX: '', snsInstagram: '',
        access: '札幌市営地下鉄すすきの駅直結', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: 'バカラ・ブラックジャック等カジノゲーム併設。初心者サポート充実。',
    },
    {
        id: 'seed-hk-003', name: 'ESPERANZA（エスペランサ）',
        group: '独立系', area: '札幌', prefecture: '北海道',
        address: '札幌市中央区南8条西5丁目288-5 CREA MUSE BLDG. 2F（Fiato cafe内）',
        phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: '', snsX: 'https://x.com/ESPERANZA_POKER', snsInstagram: 'esperanza_poker',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: 'ミックスゲーム・PLOトーナメント定期開催。Fiato cafeの飲食が高評価。',
    },
    {
        id: 'seed-hk-004', name: 'ポーカークラブ KINGSMAN 旭川',
        group: 'キングスマングループ', area: '旭川', prefecture: '北海道',
        address: '北海道旭川市3条通7丁目左1号 ヨネザワセブンビル3F',
        phone: '0166-73-7669',
        hoursWeekday: '月〜金 17:00-23:30', hoursWeekend: '土日祝 13:30-23:30', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: 'https://kingsman-asahikawa.owst.jp/', snsX: '', snsInstagram: '',
        access: '', license: '風営法遵守', paymentMethod: 'VISA・Master・Amex・JCB対応',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: '旭川駅から徒歩圏内。仕事帰りの会社員や学生に人気。',
    },
    {
        id: 'seed-hk-005', name: 'POKER CLUB KINGSMAN HAKODATE',
        group: 'キングスマングループ', area: '函館', prefecture: '北海道',
        address: '北海道函館市本町32-27 ソシアルケイオービル3F',
        phone: '', hoursWeekday: '18:00-23:30', hoursWeekend: '18:00-23:30', hoursSunday: '',
        priceGeneral: '3,000円（男性）', priceDiscount: '2,000円', priceNote: 'ソフトドリンク飲み放題込',
        websiteUrl: '', snsX: '', snsInstagram: '',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: '道南初のポーカー専門店。暗めの照明を活かした雰囲気作りに定評。',
    },
    {
        id: 'seed-hk-006', name: 'ポーカークラブ キングスマン 帯広店',
        group: 'キングスマングループ', area: '帯広（十勝地方）', prefecture: '北海道',
        address: '〒080-0012 北海道帯広市西2条南10丁目9-1 フジモトビル3F',
        phone: '0155-67-5429',
        hoursWeekday: '月〜金 17:30-24:00', hoursWeekend: '土日祝 13:30-23:30', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: 'https://sapporo-kingsman.com/obihiro/', snsX: '', snsInstagram: '',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: '十勝地方のコミュニティ拠点。ゆったりした時間感覚の営業。',
    },
    {
        id: 'seed-hk-007', name: 'カジスポ札幌',
        group: '独立系', area: '札幌', prefecture: '北海道',
        address: '札幌市中央区南4条西4丁目4番地 LC15番館3F',
        phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: '', snsX: '', snsInstagram: '',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: '広々とした店内。初心者向けの丁寧なレクチャーあり。',
    },
    {
        id: 'seed-hk-008', name: 'JOKERS.',
        group: '独立系', area: '札幌', prefecture: '北海道',
        address: '札幌市中央区南5条西5丁目20-1 札幌7KビルB1F',
        phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: '', snsX: '', snsInstagram: '',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: '深夜帯の稼働に定評があるコミュニティスポット。',
    },
    {
        id: 'seed-hk-009', name: 'GOLDEN BANANA.',
        group: '独立系', area: '札幌', prefecture: '北海道',
        address: '札幌市中央区南6条西6丁目7-1 第6旭観光ビル5F',
        phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: '', snsX: '', snsInstagram: '',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: '落ち着いた雰囲気でじっくりプレイできる環境。',
    },
    {
        id: 'seed-hk-010', name: 'FORTH.',
        group: '独立系', area: '札幌', prefecture: '北海道',
        address: '札幌市中央区南7条西4丁目 プラザ7.4浅井ビル4F',
        phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: '', snsX: '', snsInstagram: '',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: '同ビル内の一隅（Katasumi）と共に深夜需要をカバー。',
    },
    {
        id: 'seed-hk-011', name: 'POKER ROOM UNI.',
        group: '独立系', area: '札幌', prefecture: '北海道',
        address: '札幌市中央区南4条西5丁目 アイビルII 6F',
        phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: '', snsX: '', snsInstagram: '',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: 'すすきの駅から徒歩3分の好立地。',
    },
    {
        id: 'seed-hk-012', name: 'クイーンズパレス',
        group: '独立系', area: '札幌', prefecture: '北海道',
        address: '札幌市中央区南4条西2丁目 RECOLTE Sapporo 1F',
        phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: '', snsX: '', snsInstagram: '',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: 'バカラ・ブラックジャックも楽しめる総合アミューズメント。',
    },
    {
        id: 'seed-hk-013', name: '一隅（Katasumi）',
        group: '独立系', area: '札幌', prefecture: '北海道',
        address: '札幌市中央区南7条西4丁目 プラザ7.4浅井ビル4F',
        phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '',
        priceGeneral: '', priceDiscount: '', priceNote: '',
        websiteUrl: '', snsX: '', snsInstagram: '',
        access: '', license: '', paymentMethod: '',
        ringGameRate: '', chipDepositPeriod: '', status: '営業中',
        note: '毎週月・木23:00〜「夜すみ」イベント、毎週火曜フリーロール開催。FORTH.と同ビル。',
    },
]

// ══════════════════════════════════════════════════════
// 関東・東北 店舗データ（26店舗）
// ══════════════════════════════════════════════════════
const kantoTohokuVenues: SeedVenue[] = [
    // ─── 関東 ──────────────────
    { id: 'seed-kt-001', name: 'ROOTS Shibuya', group: '', area: '渋谷', prefecture: '東京都', address: '東京都渋谷区宇田川町31-1', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://roots-poker.com', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '大型ポーカールーム' },
    { id: 'seed-kt-002', name: "m HOLD'EM 目黒", group: '', area: '目黒', prefecture: '東京都', address: '東京都目黒区目黒1-3-15', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://mpj-portal.jp', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'リング・トーナメント' },
    { id: 'seed-kt-003', name: 'GoodGame Poker Live 渋谷', group: '', area: '渋谷', prefecture: '東京都', address: '東京都渋谷区宇田川町12-9', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://ggpokerlive.jp', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '初心者講習あり' },
    { id: 'seed-kt-004', name: 'KKLIVE POKER Shibuya', group: '', area: '渋谷', prefecture: '東京都', address: '東京都渋谷区宇田川町12-7', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://kklivepoker.com', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'キャッシュレス対応' },
    { id: 'seed-kt-005', name: 'KKLIVE POKER Shinjuku', group: '', area: '新宿', prefecture: '東京都', address: '東京都新宿区歌舞伎町1-23-15', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://kklivepoker.com', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '大型ポーカールーム' },
    { id: 'seed-kt-006', name: 'LIVE ACE Yokohama', group: '', area: '横浜', prefecture: '神奈川県', address: '神奈川県横浜市西区南幸2-6-22', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://live-ace.site', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'トーナメント中心' },
    { id: 'seed-kt-007', name: 'PreFlop Yokohama', group: '', area: '横浜', prefecture: '神奈川県', address: '神奈川県横浜市西区南幸1-13-13', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://preflop.jp', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '横浜駅近く' },
    { id: 'seed-kt-008', name: 'Poker Bar GOLD JOKER', group: '', area: '横浜', prefecture: '神奈川県', address: '神奈川県横浜市中区吉田町12-1', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://sites.google.com/view/goldjoker', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '初心者講習あり' },
    { id: 'seed-kt-009', name: 'KINGS 千葉', group: '', area: '千葉', prefecture: '千葉県', address: '千葉県千葉市中央区栄町41-10', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://kingscasino.jp', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'スクールあり' },
    { id: 'seed-kt-010', name: 'Poker House POM', group: '', area: '船橋', prefecture: '千葉県', address: '千葉県船橋市前原西2-15-1', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://pokerhouse-pom.com', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '津田沼駅近' },
    { id: 'seed-kt-011', name: 'RAT POKER', group: '', area: '千葉', prefecture: '千葉県', address: '千葉県千葉市中央区富士見2-15-8', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'http://ratspoker.chu-rou-dou.com', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '深夜営業' },
    { id: 'seed-kt-012', name: 'BACKDOOR 水戸', group: '', area: '水戸', prefecture: '茨城県', address: '茨城県水戸市大工町1-6-18', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://mito.backdoor.casino', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'カジノゲーム併設' },
    { id: 'seed-kt-013', name: 'KINGS 取手', group: '', area: '取手', prefecture: '茨城県', address: '茨城県取手市取手2-3-1', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://kingscasino.jp', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'リングゲーム' },
    { id: 'seed-kt-014', name: 'BACKDOOR 宇都宮', group: '', area: '宇都宮', prefecture: '栃木県', address: '栃木県宇都宮市江野町1-1', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://utsunomiya.backdoor.casino', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '初心者講習あり' },
    // ─── 東北 ──────────────────
    { id: 'seed-kt-015', name: '8Quads', group: '', area: '八戸', prefecture: '青森県', address: '青森県八戸市長横町7-1', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'アミューズメントカジノ' },
    { id: 'seed-kt-016', name: 'OUTS 弘前', group: '', area: '弘前', prefecture: '青森県', address: '青森県弘前市土手町4', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'リング/トーナメント' },
    { id: 'seed-kt-017', name: 'HAKU Poker Bar', group: '', area: '弘前', prefecture: '青森県', address: '青森県弘前市代官町45-1', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '初心者講習' },
    { id: 'seed-kt-018', name: 'CHIPS POKER', group: '', area: '五所川原', prefecture: '青森県', address: '青森県五所川原市寺町54-1', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '初心者歓迎' },
    { id: 'seed-kt-019', name: 'Poker Bar BLUFF', group: '', area: '盛岡', prefecture: '岩手県', address: '岩手県盛岡市大通2-3-3', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://pokerbar-bluff.com', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'ポーカーバー' },
    { id: 'seed-kt-020', name: '9High 仙台', group: '', area: '仙台', prefecture: '宮城県', address: '宮城県仙台市青葉区花京院1-4-47', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://9high.jp/sendai', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'トーナメント' },
    { id: 'seed-kt-021', name: 'BACKDOOR 仙台', group: '', area: '仙台', prefecture: '宮城県', address: '宮城県仙台市青葉区国分町2-1-15', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://sendai.backdoor.casino', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'カジノゲーム' },
    { id: 'seed-kt-022', name: 'DEERGOLD', group: '', area: '仙台', prefecture: '宮城県', address: '宮城県仙台市青葉区一番町4-9-1', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://www.unputenpu0308.com/deergold', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '大型店' },
    { id: 'seed-kt-023', name: '5656ポーカー倶楽部', group: '', area: '鶴岡', prefecture: '山形県', address: '山形県鶴岡市本町1-6-21', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://5656.jimdosite.com', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '庄内エリア初' },
    { id: 'seed-kt-024', name: 'Brilliant Space LOL', group: '', area: '山形', prefecture: '山形県', address: '山形県山形市七日町2-7-38', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '毎日トーナメント' },
    { id: 'seed-kt-025', name: 'ACE&KING FUKUSHIMA', group: '', area: '福島', prefecture: '福島県', address: '福島県福島市栄町12-12', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://aceking.site', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'アミューズメントカジノ' },
    { id: 'seed-kt-026', name: 'Casino Bar Alice', group: '', area: 'いわき', prefecture: '福島県', address: '福島県いわき市平白銀町5-11', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://alice-iwaki.com', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'プロディーラー在籍' },
]

// ══════════════════════════════════════════════════════
// 中部 店舗データ（17店舗）
// ══════════════════════════════════════════════════════
const chubuVenues: SeedVenue[] = [
    { id: 'seed-cb-001', name: 'ナゴヤギルド（Nagoya Guild）', group: '', area: '名古屋', prefecture: '愛知県', address: '〒453-0015 愛知県名古屋市中村区椿町14-6 11CUBES 6階', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '名古屋駅すぐの老舗アミューズメントカジノ。初心者講習充実。' },
    { id: 'seed-cb-002', name: 'Second Nuts（セカンドナッツ）', group: '', area: '名古屋錦', prefecture: '愛知県', address: '〒460-0003 愛知県名古屋市中区錦3丁目22-7 アークビル 6F', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://poker2ndnuts.wixsite.com/nuts', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-003', name: 'GoodGame Poker Live Nagoya', group: '', area: '名古屋栄', prefecture: '愛知県', address: '〒460-0008 愛知県名古屋市中区栄3丁目9-2 Gems栄 6階', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '国内最大級ポーカーネットワーク「GoodGame」系列店。' },
    { id: 'seed-cb-004', name: 'PARADIA NAGOYA', group: '', area: '名古屋錦', prefecture: '愛知県', address: '〒460-0003 愛知県名古屋市中区錦3丁目21-14 6階', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-005', name: 'REX POKER NAGOYA', group: '', area: '名古屋新栄', prefecture: '愛知県', address: '〒460-0008 愛知県名古屋市中区新栄1-2-29 ウエストビル 2F', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://tabelog.com/aichi/A2301/A230103/23092036/', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-006', name: 'POKER FACE 名古屋店', group: '', area: '名古屋栄', prefecture: '愛知県', address: '愛知県名古屋市中区栄3-29-1 名古屋パルコ 西館2F', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://www.pokerface-web.com/', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-007', name: 'LAG NAGOYA', group: '', area: '名古屋栄東', prefecture: '愛知県', address: '愛知県名古屋市中区栄4-17-29 フジアーバンハイツ2F', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-008', name: 'POKER & BAR J8', group: '', area: '名古屋住吉', prefecture: '愛知県', address: '愛知県名古屋市中区栄3丁目11-14 ピボット住吉303', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '初心者講習完備のポーカーバー' },
    { id: 'seed-cb-009', name: 'BEGINS poker 名古屋大須店', group: '', area: '名古屋大須', prefecture: '愛知県', address: '愛知県名古屋市中区大須4丁目11-5 Zsビル 3階', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '初心者向けポーカー講習あり' },
    { id: 'seed-cb-010', name: 'picture', group: '', area: '名古屋伏見', prefecture: '愛知県', address: '愛知県名古屋市中区栄2丁目3-16', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-011', name: 'BAKUBAKU', group: '', area: '名古屋栄東', prefecture: '愛知県', address: '愛知県名古屋市中区栄4-17-2 コスモビル 3F', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: 'フリーロール開催' },
    { id: 'seed-cb-012', name: 'INSPIRE POKER', group: '', area: '名古屋久屋大通', prefecture: '愛知県', address: '愛知県名古屋市中区錦3丁目15-11 栄第2ビル', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '最大級の大型ポーカールーム' },
    { id: 'seed-cb-013', name: 'じゃんけんポーカー 浜松店', group: '', area: '浜松', prefecture: '静岡県', address: '〒430-0932 静岡県浜松市中央区肴町317-9 間渕ビル2F南', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://hamamatsu.jyanken-poker.jp/', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-014', name: 'AK poker 浜松店', group: '', area: '浜松', prefecture: '静岡県', address: '〒430-0344 静岡県浜松市中央区田町324-27', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: 'https://akpoker-hamamatsuten.com/', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-015', name: '金沢 SPARKL', group: '', area: '金沢', prefecture: '石川県', address: '石川県金沢市内', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-016', name: 'フルハウちゅ', group: '', area: '金沢', prefecture: '石川県', address: '石川県金沢市内', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
    { id: 'seed-cb-017', name: 'PokerLoungeWhite', group: '', area: '金沢', prefecture: '石川県', address: '石川県金沢市内', phone: '', hoursWeekday: '', hoursWeekend: '', hoursSunday: '', priceGeneral: '', priceDiscount: '', priceNote: '', websiteUrl: '', snsX: '', snsInstagram: '', access: '', license: '', paymentMethod: '', ringGameRate: '', chipDepositPeriod: '', status: '営業中', note: '' },
]

// ══════════════════════════════════════════════════════
// 全店舗を統合
// ══════════════════════════════════════════════════════
export const ALL_SEED_VENUES: SeedVenue[] = [
    ...hokkaidoVenues,
    ...kantoTohokuVenues,
    ...chubuVenues,
]

// ══════════════════════════════════════════════════════
// フィルター用プロパティマップ（公式サイト調査結果）
// ══════════════════════════════════════════════════════
import type { FoodLevel } from '../types/api'

interface FilterProps {
    tableCount?: number
    foodLevel?: FoodLevel
    drinkRich?: boolean
    peakTime?: string
    tournamentTitle?: string
}

export const FILTER_MAP: Record<string, FilterProps> = {
    // ── 北海道 ─────────────────────────────────────────
    // キングスマンすすきの本店: トーナメント・リングゲーム提供、飲み放題込
    'seed-hk-001': { tableCount: 5, foodLevel: 'none', drinkRich: true, peakTime: '20:00〜24:00', tournamentTitle: 'JOPTサテライト随時開催' },
    // BLOW すすきの: カジノゲーム併設、COCONO SUSUKINO内
    'seed-hk-002': { tableCount: 3, foodLevel: 'basic', drinkRich: true },
    // ESPERANZA: Fiato cafe内 → フード充実（スープパスタ・炭酸レモネード等）、PLOトーナメント
    'seed-hk-003': { tableCount: 2, foodLevel: 'rich', drinkRich: true, tournamentTitle: 'ミックスゲーム・PLOトーナメント定期開催' },
    // キングスマン旭川: 3テーブル/30席、飲み放題、カード決済
    'seed-hk-004': { tableCount: 3, foodLevel: 'none', drinkRich: true, peakTime: '19:00〜22:00' },
    // キングスマン函館: ソフトドリンク飲み放題込
    'seed-hk-005': { tableCount: 2, foodLevel: 'none', drinkRich: true },
    // キングスマン帯広: ソフトドリンク飲み放題+アルコール飲み放題OP、トーナメント・リングゲーム
    'seed-hk-006': { tableCount: 3, foodLevel: 'none', drinkRich: true, tournamentTitle: 'トーナメント随時開催' },
    // カジスポ札幌: 広々とした店内
    'seed-hk-007': { tableCount: 4 },
    // JOKERS.: 深夜営業
    'seed-hk-008': { tableCount: 2, peakTime: '22:00〜翌4:00' },
    // GOLDEN BANANA.
    'seed-hk-009': { tableCount: 2 },
    // FORTH.
    'seed-hk-010': { tableCount: 2, peakTime: '22:00〜翌3:00' },
    // POKER ROOM UNI.
    'seed-hk-011': { tableCount: 2 },
    // クイーンズパレス: 総合アミューズメント
    'seed-hk-012': { tableCount: 3 },
    // 一隅（Katasumi）: 夜すみイベント毎週月木、フリーロール毎週火
    'seed-hk-013': { tableCount: 2, tournamentTitle: '夜すみイベント（毎週月・木23:00〜）' },

    // ── 関東 ──────────────────────────────────────────
    // ROOTS Shibuya: 国内最大級、こだわりフード&ドリンク、HEADS UP TOURNAMENT
    'seed-kt-001': { tableCount: 15, foodLevel: 'rich', drinkRich: true, peakTime: '19:00〜翌1:00', tournamentTitle: 'HEADS UP TOURNAMENT / TIER MATCH' },
    // m HOLD'EM 目黒: リング・トーナメント
    'seed-kt-002': { tableCount: 6, foodLevel: 'basic', drinkRich: true, tournamentTitle: 'トーナメント開催中' },
    // GGPL渋谷: 初心者講習・トーナメント充実
    'seed-kt-003': { tableCount: 8, foodLevel: 'basic', drinkRich: true, tournamentTitle: 'トーナメント毎日複数回開催' },
    // KKLP渋谷: BAR併設、充実ドリンクメニュー、RFID配信対応、トーナメント毎日
    'seed-kt-004': { tableCount: 6, foodLevel: 'basic', drinkRich: true, peakTime: '19:00〜翌2:00', tournamentTitle: 'トーナメント毎日複数回開催' },
    // KKLP新宿: 大型ポーカールーム、BAR併設、近未来サイバー空間
    'seed-kt-005': { tableCount: 10, foodLevel: 'basic', drinkRich: true, peakTime: '19:00〜翌2:00', tournamentTitle: 'MTT / LIVE配信トーナメント' },
    // LIVE ACE横浜: トーナメント中心
    'seed-kt-006': { tableCount: 5, foodLevel: 'none', drinkRich: false, tournamentTitle: 'トーナメント中心に開催' },
    // PreFlop横浜: リングテーブル常時・初心者講習、SPADIEチケット獲得可能
    'seed-kt-007': { tableCount: 4, foodLevel: 'none', drinkRich: false, tournamentTitle: 'SPADIEチケット獲得可能' },
    // Poker Bar GOLD JOKER: バー併設
    'seed-kt-008': { tableCount: 2, foodLevel: 'basic', drinkRich: true },
    // KINGS 千葉: スクール、ポーカー2台(取手と同グループだが千葉店)
    'seed-kt-009': { tableCount: 3, foodLevel: 'none', drinkRich: true },
    // Poker House POM: 津田沼駅近
    'seed-kt-010': { tableCount: 3, foodLevel: 'none', drinkRich: false },
    // RAT POKER: 深夜営業
    'seed-kt-011': { tableCount: 2, peakTime: '22:00〜翌5:00' },
    // BACKDOOR 水戸: カジノゲーム併設
    'seed-kt-012': { tableCount: 3, foodLevel: 'basic', drinkRich: true },
    // KINGS 取手: ポーカー2台+バカラ+BJ+ルーレット、ドリンク飲み放題
    'seed-kt-013': { tableCount: 2, foodLevel: 'none', drinkRich: true },
    // BACKDOOR 宇都宮: 初心者講習、カジノゲーム併設
    'seed-kt-014': { tableCount: 3, foodLevel: 'basic', drinkRich: true },
    // 8Quads: アミューズメントカジノ
    'seed-kt-015': { tableCount: 2 },
    // OUTS弘前: リング/トーナメント
    'seed-kt-016': { tableCount: 2, tournamentTitle: 'トーナメント開催' },
    // HAKU Poker Bar: バー併設、初心者講習
    'seed-kt-017': { tableCount: 2, foodLevel: 'basic', drinkRich: true },
    // CHIPS POKER: 初心者歓迎
    'seed-kt-018': { tableCount: 2 },
    // Poker Bar BLUFF: バー併設
    'seed-kt-019': { tableCount: 2, foodLevel: 'basic', drinkRich: true },
    // 9High仙台: バー併設、毎日イベント、レディース割・学割
    'seed-kt-020': { tableCount: 4, foodLevel: 'basic', drinkRich: true, tournamentTitle: '毎日ポーカーイベント開催中' },
    // BACKDOOR仙台: カジノゲーム併設、イベント開催
    'seed-kt-021': { tableCount: 4, foodLevel: 'basic', drinkRich: true, tournamentTitle: 'ポーカートーナメント開催' },
    // DEERGOLD: 大型店
    'seed-kt-022': { tableCount: 6, foodLevel: 'basic', drinkRich: true },
    // 5656ポーカー倶楽部
    'seed-kt-023': { tableCount: 2 },
    // Brilliant Space LOL: 毎日トーナメント
    'seed-kt-024': { tableCount: 3, tournamentTitle: '毎日トーナメント開催' },
    // ACE&KING FUKUSHIMA: アミューズメントカジノ
    'seed-kt-025': { tableCount: 3, foodLevel: 'basic', drinkRich: true },
    // Casino Bar Alice: プロディーラー在籍、バー併設
    'seed-kt-026': { tableCount: 2, foodLevel: 'basic', drinkRich: true },

    // ── 中部 ──────────────────────────────────────────
    // ナゴヤギルド: メイドカジノテーマパーク、ポーカートーナメント
    'seed-cb-001': { tableCount: 8, foodLevel: 'rich', drinkRich: true, peakTime: '17:00〜22:00', tournamentTitle: 'ポーカートーナメント定期開催' },
    // Second Nuts
    'seed-cb-002': { tableCount: 3, drinkRich: true },
    // GGPL名古屋: GoodGame系列、トーナメント
    'seed-cb-003': { tableCount: 6, foodLevel: 'basic', drinkRich: true, tournamentTitle: 'トーナメント毎日複数回開催' },
    // PARADIA NAGOYA
    'seed-cb-004': { tableCount: 3 },
    // REX POKER NAGOYA
    'seed-cb-005': { tableCount: 3 },
    // POKER FACE名古屋: パルコ内
    'seed-cb-006': { tableCount: 3, foodLevel: 'basic' },
    // LAG NAGOYA
    'seed-cb-007': { tableCount: 3 },
    // POKER & BAR J8: バー併設
    'seed-cb-008': { tableCount: 2, foodLevel: 'basic', drinkRich: true },
    // BEGINS poker名古屋大須
    'seed-cb-009': { tableCount: 2 },
    // picture
    'seed-cb-010': { tableCount: 2 },
    // BAKUBAKU
    'seed-cb-011': { tableCount: 2 },
    // INSPIRE POKER
    'seed-cb-012': { tableCount: 2 },
    // じゃんけんポーカー浜松: トーナメントあり
    'seed-cb-013': { tableCount: 3, tournamentTitle: 'トーナメント開催' },
    // AK poker 浜松
    'seed-cb-014': { tableCount: 2 },
    // 金沢 SPARKL
    'seed-cb-015': { tableCount: 2 },
    // フルハウちゅ
    'seed-cb-016': { tableCount: 2 },
    // PokerLoungeWhite
    'seed-cb-017': { tableCount: 2 },
}

// ── 変換関数 ──────────────────────────────────────────

/** SeedVenue → VenuePin（地図用） */
export function toVenuePin(v: SeedVenue): VenuePin {
    const coords = getCoords(v.area, v.address)
    const pref = v.prefecture || prefectureFromArea(v.area, v.address)
    const fp = FILTER_MAP[v.id]
    return {
        id: v.id,
        type: 'venue',
        lat: coords.lat + (Math.random() - 0.5) * PIN_JITTER_RANGE,   // 同エリア店舗のピン重複を避ける微小オフセット
        lng: coords.lng + (Math.random() - 0.5) * PIN_JITTER_RANGE,
        display_name: v.name,
        open_status: v.status === '営業中' ? 'open' : 'unknown',
        hours_today: mergeHours(v.hoursWeekday, v.hoursWeekend, v.hoursSunday),
        price_entry_min: parsePriceMin(v.priceGeneral),
        next_tournament_title: fp?.tournamentTitle ?? null,
        next_tournament_start: fp?.tournamentTitle ? new Date(Date.now() + 7 * MS_PER_DAY).toISOString() : null,
        area_prefecture: pref,
        area_city: cityFromArea(v.area, v.address),
        verification_status: 'unverified',
        detail_url: `/venues/${v.id}`,
        booking_url: null,
        food_level: (fp?.foodLevel as VenuePin['food_level']) ?? null,
        table_count: fp?.tableCount ?? null,
        drink_required: fp?.drinkRich ?? null,
    }
}

/** SeedVenue → VenueCard（リスト用） */
export function toVenueCard(v: SeedVenue): VenueCard {
    const coords = getCoords(v.area, v.address)
    const pref = v.prefecture || prefectureFromArea(v.area, v.address)
    const fp = FILTER_MAP[v.id]
    return {
        id: v.id,
        name: v.name,
        open_status: v.status === '営業中' ? 'open' : 'unknown',
        hours_today: mergeHours(v.hoursWeekday, v.hoursWeekend, v.hoursSunday),
        price_entry_min: parsePriceMin(v.priceGeneral),
        price_note: v.priceNote || v.priceDiscount || null,
        next_tournament_title: fp?.tournamentTitle ?? null,
        next_tournament_start: fp?.tournamentTitle ? new Date(Date.now() + 7 * MS_PER_DAY).toISOString() : null,
        next_tournament_url: null,
        drink_required: fp?.drinkRich ?? null,
        food_level: fp?.foodLevel ?? null,
        table_count: fp?.tableCount ?? null,
        peak_time: fp?.peakTime ?? null,
        address: v.address,
        area_prefecture: pref,
        area_city: cityFromArea(v.area, v.address),
        lat: coords.lat,
        lng: coords.lng,
        last_updated_at: null,
        updated_at: new Date().toISOString(),
        data_age_days: null,
        sources: v.websiteUrl ? [v.websiteUrl] : null,
    }
}

/** SeedVenue → VenueDetail（詳細ページ用） */
export function toVenueDetail(v: SeedVenue): VenueDetail {
    const card = toVenueCard(v)
    const snsLinks: Record<string, string> = {}
    if (v.snsX) snsLinks.x = v.snsX
    if (v.snsInstagram) snsLinks.instagram = v.snsInstagram.startsWith('http')
        ? v.snsInstagram
        : `https://www.instagram.com/${v.snsInstagram}/`

    return {
        ...card,
        website_url: v.websiteUrl || null,
        sns_links: Object.keys(snsLinks).length > 0 ? snsLinks : null,
        summary: v.note || null,
        verification_status: 'unverified',
        visibility_status: 'visible',
        match_confidence: null,
        field_confidence: null,
        country_code: 'JP',
        locale: 'ja',
        time_zone: 'Asia/Tokyo',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        tournaments: [],
    }
}

// ── ヘルパー ─────────────────────────────────────────

/** 全シードデータの VenuePin 配列（キャッシュ付き） */
let _pinsCache: VenuePin[] | null = null
export function getAllSeedPins(): VenuePin[] {
    if (!_pinsCache) _pinsCache = ALL_SEED_VENUES.map(toVenuePin)
    return _pinsCache
}

/** 全シードデータの VenueCard 配列 */
export function getAllSeedCards(): VenueCard[] {
    return ALL_SEED_VENUES.map(toVenueCard)
}

/** ID で SeedVenue を検索して VenueDetail を返す */
export function getSeedVenueDetail(id: string): VenueDetail | null {
    const v = ALL_SEED_VENUES.find(sv => sv.id === id)
    return v ? toVenueDetail(v) : null
}
