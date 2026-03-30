import { useState, useEffect, useCallback } from 'react'
import {
  Map, List, AlertCircle, Loader2, MapPin, Trophy,
  Navigation, Utensils, LayoutGrid, Coffee, RotateCcw,
  WifiOff, ChevronDown, ChevronUp,
} from 'lucide-react'
import type { VenuePin, VenueCard } from '../types/api'
import { fetchPins, fetchVenues } from '../api/client'
import { MANY_TABLES_THRESHOLD, DEFAULT_LIST_LIMIT, GPS_TIMEOUT_MS, GPS_MAX_AGE_MS } from '../constants'
import type { Filters } from '../components/FilterBar'
import MapView from '../components/MapView'
import VenueCardComponent from '../components/VenueCard'
import Sidebar, { NavItem, MobileMenuButton } from '../components/Sidebar'

type ViewMode = 'map' | 'list'

const DEFAULT_FILTERS: Filters = {
  openNow: false,
  hasTournament: false,
  tournamentMonthFrom: null,
  tournamentMonthTo: null,
  near: false,
  prefectures: [],
  foodRich: false,
  manyTables: false,
  drinkRich: false,
}

// 都道府県リスト
const PREFECTURES = [
  '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
  '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
  '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
  '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
  '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
  '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
  '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
]

// ── 月セレクト ───────────────────────────────────────
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

export default function HomePage() {
  const [viewMode, setViewMode] = useState<ViewMode>('map')
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [pins, setPins] = useState<VenuePin[]>([])
  const [venues, setVenues] = useState<VenueCard[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [bbox, setBbox] = useState<string | undefined>(undefined)
  const [userPos, setUserPos] = useState<{ lat: number; lng: number } | null>(null)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const LIMIT = DEFAULT_LIST_LIMIT

  // GPS ステータス
  type GpsStatus = 'idle' | 'loading' | 'ok' | 'denied' | 'unsupported' | 'error'
  const [gpsStatus, setGpsStatus] = useState<GpsStatus>('idle')

  // 近くの店舗トグル（GPS確認付き）
  async function handleNearToggle() {
    if (filters.near) {
      // OFF
      setFilters(f => ({ ...f, near: false }))
      setPage(0)
      return
    }

    // ブラウザがGeolocationをサポートしていない
    if (!navigator.geolocation) {
      setGpsStatus('unsupported')
      return
    }

    setGpsStatus('loading')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setFilters(f => ({ ...f, near: true }))
        setPage(0)
        setGpsStatus('ok')
      },
      (err) => {
        if (err.code === 1 /* PERMISSION_DENIED */) {
          setGpsStatus('denied')
        } else if (err.code === 2 /* POSITION_UNAVAILABLE */) {
          setGpsStatus('error')
        } else {
          setGpsStatus('error')
        }
      },
      { timeout: GPS_TIMEOUT_MS, maximumAge: GPS_MAX_AGE_MS, enableHighAccuracy: false }
    )
  }



  // マップピン取得
  const loadPins = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchPins({
        bbox,
        prefecture: filters.prefectures.length ? filters.prefectures : undefined,
        open_now: filters.openNow || undefined,
        has_tournament: filters.hasTournament || undefined,
        tournament_month_from: filters.tournamentMonthFrom ?? undefined,
        tournament_month_to: filters.tournamentMonthTo ?? undefined,
        food_level: filters.foodRich ? 'rich' : undefined,
        min_tables: filters.manyTables ? MANY_TABLES_THRESHOLD : undefined,
        drink_rich: filters.drinkRich || undefined,
        user_lat: filters.near && userPos ? userPos.lat : undefined,
        user_lng: filters.near && userPos ? userPos.lng : undefined,
      })
      setPins(res.pins)
    } catch (e) {
      // client.ts 側でシードデータにフォールバック済み
      // ここに来る場合はフォールバックすらも失敗
      console.warn('ピン取得失敗:', e)
      setPins([])
    } finally {
      setLoading(false)
    }
  }, [bbox, filters, userPos])

  // リスト取得
  const loadVenues = useCallback(async (offset = 0) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchVenues({
        prefecture: filters.prefectures.length ? filters.prefectures : undefined,
        open_status: filters.openNow ? 'open' : undefined,
        has_tournament: filters.hasTournament || undefined,
        tournament_month_from: filters.tournamentMonthFrom ?? undefined,
        tournament_month_to: filters.tournamentMonthTo ?? undefined,
        food_level: filters.foodRich ? 'rich' : undefined,
        min_tables: filters.manyTables ? MANY_TABLES_THRESHOLD : undefined,
        drink_rich: filters.drinkRich || undefined,
        sort: filters.near && userPos ? 'near' : 'updated',
        user_lat: filters.near && userPos ? userPos.lat : undefined,
        user_lng: filters.near && userPos ? userPos.lng : undefined,
        offset,
        limit: LIMIT,
      })
      if (offset === 0) {
        setVenues(res.items)
      } else {
        setVenues(prev => [...prev, ...res.items])
      }
      setTotal(res.total)
      setPage(Math.floor(offset / LIMIT))
    } catch (e) {
      // client.ts 側でシードデータにフォールバック済み
      // ここに来る場合はフォールバックすらも失敗
      console.warn('リスト取得失敗:', e)
      if (offset === 0) setVenues([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [filters, userPos])

  // フィルタ / ビュー変更 → 再取得
  useEffect(() => {
    if (viewMode === 'map') loadPins()
    else loadVenues(0)
  }, [viewMode, filters, userPos, loadPins, loadVenues])

  // bbox変更時のピン再取得
  useEffect(() => {
    if (viewMode === 'map' && bbox != null) loadPins()
  }, [bbox]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleFiltersChange(f: Filters) {
    setFilters(f)
    setPage(0)
  }

  function handleBoundsChange(newBbox: string) {
    setBbox(newBbox)
  }

  // アクティブなフィルタが1つ以上あるか
  const hasActiveFilters = Object.entries(filters).some(([, v]) => {
    if (Array.isArray(v)) return v.length > 0
    return v !== false && v !== null
  })

  return (
    <div className="flex h-screen bg-stone-50">
      {/* モバイルメニューボタン */}
      <MobileMenuButton onClick={() => setSidebarOpen(true)} />

      {/* ─── サイドバー ─── */}
      <Sidebar
        onLogoClick={() => { setFilters(DEFAULT_FILTERS); setViewMode('map'); setPage(0) }}
        mobileOpen={sidebarOpen}
        onMobileToggle={() => setSidebarOpen(o => !o)}
      >
        {/* 表示切替 */}
        <div className="px-1 pt-1 pb-1">
          <p className="text-[10px] font-semibold text-stone-400 px-2 pb-1 uppercase tracking-wider">
            表示
          </p>
          <NavItem
            icon={<Map size={14} />}
            label="地図"
            active={viewMode === 'map'}
            onClick={() => { setViewMode('map'); setSidebarOpen(false) }}
          />
          <NavItem
            icon={<List size={14} />}
            label="リスト"
            active={viewMode === 'list'}
            onClick={() => { setViewMode('list'); setSidebarOpen(false) }}
          />
        </div>

        {/* ─── フィルタ ─── */}
        <div className="border-t border-stone-100 pb-1">

          {/* ♠ 基本 */}
          <SuitSection suit="♠" label="基本" red={false}>
            <FilterToggle
              active={filters.openNow}
              icon={<MapPin size={13} />}
              label="営業中"
              onClick={() => handleFiltersChange({ ...filters, openNow: !filters.openNow })}
            />
          </SuitSection>

          {/* ♥ 大会 */}
          <SuitSection suit="♥" label="大会" red>
            <FilterToggle
              active={filters.hasTournament}
              icon={<Trophy size={13} />}
              label="大会あり"
              onClick={() => handleFiltersChange({ ...filters, hasTournament: !filters.hasTournament })}
            />
            {/* 期間ピッカー（大会ありON時のみ表示） */}
            {filters.hasTournament && (
              <div className="px-3 pt-0.5 pb-2">
                <p className="text-[10px] text-stone-400 mb-1">開催月を絞り込む</p>
                <div className="flex items-center gap-1">
                  <select
                    value={filters.tournamentMonthFrom ?? ''}
                    onChange={e => handleFiltersChange({
                      ...filters,
                      tournamentMonthFrom: e.target.value ? Number(e.target.value) : null,
                    })}
                    className="flex-1 min-w-0 text-xs border border-stone-200 rounded-md py-1 px-1
                               bg-stone-50 text-stone-600 focus:outline-none focus:border-gold-400
                               cursor-pointer"
                  >
                    <option value="">全月</option>
                    {MONTHS.map(m => <option key={m} value={m}>{m}月</option>)}
                  </select>
                  <span className="text-stone-300 text-[10px] flex-shrink-0">〜</span>
                  <select
                    value={filters.tournamentMonthTo ?? ''}
                    onChange={e => handleFiltersChange({
                      ...filters,
                      tournamentMonthTo: e.target.value ? Number(e.target.value) : null,
                    })}
                    className="flex-1 min-w-0 text-xs border border-stone-200 rounded-md py-1 px-1
                               bg-stone-50 text-stone-600 focus:outline-none focus:border-gold-400
                               cursor-pointer"
                  >
                    <option value="">全月</option>
                    {MONTHS.map(m => <option key={m} value={m}>{m}月</option>)}
                  </select>
                </div>
              </div>
            )}

          </SuitSection>

          {/* エリア（都道府県） */}
          <PrefectureSection
            selected={filters.prefectures}
            onChange={pref => handleFiltersChange({ ...filters, prefectures: pref })}
          />

          {/* ♦ アクセス */}
          <SuitSection suit="♦" label="アクセス" red>
            <FilterToggle
              active={filters.near}
              disabled={gpsStatus === 'loading'}
              icon={gpsStatus === 'loading'
                ? <Loader2 size={13} className="animate-spin" />
                : <Navigation size={13} />
              }
              label={gpsStatus === 'loading' ? '取得中...' : '近くの店舗'}
              onClick={handleNearToggle}
            />
            {/* GPS ステータスインジケーター */}
            {gpsStatus === 'ok' && filters.near && (
              <p className="flex items-center gap-1 px-3 pb-1.5 text-[10px] text-emerald-500">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse inline-block" />
                GPS 有効・現在地取得済み
              </p>
            )}
            {gpsStatus === 'denied' && (
              <p className="flex items-start gap-1 px-3 pb-1.5 text-[10px] text-red-400 leading-snug">
                <WifiOff size={10} className="mt-0.5 flex-shrink-0" />
                位置情報へのアクセスが<br />拒否されています
              </p>
            )}
            {gpsStatus === 'unsupported' && (
              <p className="flex items-start gap-1 px-3 pb-1.5 text-[10px] text-stone-400 leading-snug">
                <WifiOff size={10} className="mt-0.5 flex-shrink-0" />
                このブラウザはGPSを<br />サポートしていません
              </p>
            )}
            {gpsStatus === 'error' && (
              <p className="flex items-start gap-1 px-3 pb-1.5 text-[10px] text-amber-500 leading-snug">
                <WifiOff size={10} className="mt-0.5 flex-shrink-0" />
                位置情報を取得できませんでした。
                <button
                  onClick={handleNearToggle}
                  className="underline ml-0.5"
                >再試行</button>
              </p>
            )}
          </SuitSection>

          {/* ♣ 設備・こだわり */}
          <SuitSection suit="♣" label="設備・こだわり" red={false}>
            <FilterToggle
              active={filters.foodRich}
              icon={<Utensils size={13} />}
              label="フード充実"
              onClick={() => handleFiltersChange({ ...filters, foodRich: !filters.foodRich })}
            />
            <FilterToggle
              active={filters.manyTables}
              icon={<LayoutGrid size={13} />}
              label="テーブル 6卓以上"
              onClick={() => handleFiltersChange({ ...filters, manyTables: !filters.manyTables })}
            />
            <FilterToggle
              active={filters.drinkRich}
              icon={<Coffee size={13} />}
              label="1ドリンク制あり"
              onClick={() => handleFiltersChange({ ...filters, drinkRich: !filters.drinkRich })}
            />
          </SuitSection>

          {/* リセット（1つ以上アクティブ時） */}
          {hasActiveFilters && (
            <div className="px-2 pt-1">
              <button
                onClick={() => handleFiltersChange(DEFAULT_FILTERS)}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg
                           text-xs text-stone-400 hover:text-gold-600 hover:bg-gold-50 transition-colors"
              >
                <RotateCcw size={11} />
                フィルタをリセット
              </button>
            </div>
          )}
        </div>
      </Sidebar>

      {/* ─── メインコンテンツ ─── */}
      <main className="flex-1 overflow-hidden relative">
        {loading && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20
                          bg-white rounded-full shadow-md px-4 py-1.5
                          flex items-center gap-2 text-sm text-stone-500">
            <Loader2 size={14} className="animate-spin text-gold-500" />
            読み込み中…
          </div>
        )}

        {error && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20
                          bg-red-50 border border-red-200 rounded-full shadow-sm
                          px-4 py-1.5 flex items-center gap-2 text-sm text-red-600">
            <AlertCircle size={14} />
            {error}
          </div>
        )}

        {/* 地図ビュー */}
        {viewMode === 'map' && (
          <div className="h-full w-full">
            <MapView pins={pins} filters={filters} onBoundsChange={handleBoundsChange} />
            {pins.length > 0 && (
              <div className="absolute bottom-4 right-4 z-20
                              bg-white/90 backdrop-blur-sm rounded-full
                              shadow-md px-3 py-1 text-xs text-stone-500">
                {pins.length} 件
              </div>
            )}
          </div>
        )}

        {/* リストビュー */}
        {viewMode === 'list' && (
          <div className="h-full overflow-y-auto">
            <div className="max-w-2xl mx-auto px-4 py-3">
              {!loading && total > 0 && (
                <p className="text-xs text-stone-400 mb-3">
                  {total} 件中 {venues.length} 件表示
                </p>
              )}
              <div className="space-y-3">
                {venues.map(venue => (
                  <VenueCardComponent key={venue.id} venue={venue} />
                ))}
              </div>
              {!loading && venues.length < total && (
                <button
                  onClick={() => loadVenues((page + 1) * LIMIT)}
                  className="mt-4 w-full py-3 text-sm text-stone-500 border border-stone-200
                             rounded-xl hover:border-gold-300 hover:text-gold-600 transition-colors"
                >
                  もっと見る
                </button>
              )}
              {!loading && venues.length === 0 && (
                <div className="py-16 text-center text-stone-400">
                  <Map size={40} className="mx-auto mb-3 opacity-30" />
                  <p className="text-sm">条件に合う店舗が見つかりませんでした</p>
                  <button
                    onClick={() => handleFiltersChange(DEFAULT_FILTERS)}
                    className="mt-3 text-xs text-gold-500 hover:underline"
                  >
                    フィルタをリセット
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

// ─── ユーティリティコンポーネント ───────────────────────

/** トランプ絵柄のセクションヘッダー */
function SuitSection({
  suit, label, red, children,
}: {
  suit: string
  label: string
  red: boolean
  children: React.ReactNode
}) {
  const badgeClasses = red
    ? "bg-gradient-to-br from-red-600 to-rose-800 border-red-500 ring-red-400/30 text-white shadow-red-900/20"
    : "bg-gradient-to-br from-stone-800 to-black border-stone-700 ring-stone-500/30 text-gold-400 shadow-stone-900/20"

  return (
    <div className="px-1 mb-2">
      <div className="flex items-center gap-2.5 px-2 pt-4 pb-2">
        <div className={`flex items-center justify-center w-7 h-7 rounded-lg border shadow-sm ring-1 ring-inset ${badgeClasses}`}>
          <span className="text-[15px] leading-none select-none drop-shadow-md pb-[1px]">
            {suit}
          </span>
        </div>
        <span className="text-[11px] font-bold text-stone-600 uppercase tracking-widest">
          {label}
        </span>
      </div>
      <div className="pl-1">
        {children}
      </div>
    </div>
  )
}


/** エリア（都道府県）複数選択セクション */
function PrefectureSection({
  selected, onChange,
}: {
  selected: string[]
  onChange: (v: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const toggle = (pref: string) => {
    onChange(
      selected.includes(pref)
        ? selected.filter(p => p !== pref)
        : [...selected, pref]
    )
  }
  return (
    <div className="px-1 mb-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-2 pt-4 pb-2 group"
      >
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-7 h-7 rounded-lg border shadow-sm ring-1 ring-inset bg-gradient-to-br from-stone-800 to-black border-stone-700 ring-stone-500/30 text-gold-400 shadow-stone-900/20">
            <span className="drop-shadow-md">
              <MapPin size={15} strokeWidth={2.5} />
            </span>
          </div>
          <span className="text-[11px] font-bold text-stone-600 uppercase tracking-widest">エリア</span>
          {selected.length > 0 && (
            <span className="inline-flex items-center justify-center w-4 h-4 rounded-full
                             bg-gold-500 text-white text-[9px] font-bold leading-none">
              {selected.length}
            </span>
          )}
        </div>
        {open
          ? <ChevronUp size={11} className="text-stone-300 group-hover:text-stone-500" />
          : <ChevronDown size={11} className="text-stone-300 group-hover:text-stone-500" />
        }
      </button>
      {!open && selected.length > 0 && (
        <div className="px-2 pb-1 flex flex-wrap gap-1">
          {selected.map(p => (
            <span
              key={p}
              onClick={() => toggle(p)}
              className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full
                         text-[10px] bg-gold-50 text-gold-700 border border-gold-200 cursor-pointer"
            >
              {p}
              <span className="text-gold-400 hover:text-gold-600">×</span>
            </span>
          ))}
        </div>
      )}
      {open && (
        <div className="px-2 pb-2 pt-1">
          <div className="grid grid-cols-2 gap-x-1 gap-y-0.5 max-h-48 overflow-y-auto
                          pr-1 scrollbar-thin scrollbar-thumb-stone-200">
            {PREFECTURES.map(pref => {
              const checked = selected.includes(pref)
              return (
                <button
                  key={pref}
                  onClick={() => toggle(pref)}
                  className={`text-left text-[11px] px-2 py-1 rounded-md transition-colors truncate
                    ${checked
                      ? 'bg-gold-50 text-gold-700 font-medium'
                      : 'text-stone-500 hover:bg-stone-50 hover:text-stone-700'
                    }`}
                >
                  {checked && <span className="mr-0.5 text-gold-500">✓</span>}
                  {pref}
                </button>
              )
            })}
          </div>
          {selected.length > 0 && (
            <button
              onClick={() => onChange([])}
              className="mt-1.5 w-full text-[10px] text-stone-400 hover:text-red-400 transition-colors"
            >
              選択をクリア
            </button>
          )}
        </div>
      )}
    </div>
  )
}

/** フィルタトグルボタン */
function FilterToggle({
  active, icon, label, onClick, disabled = false,
}: {
  active: boolean
  icon: React.ReactNode
  label: string
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-sm font-medium
        transition-all duration-150 text-left
        disabled:opacity-40 disabled:cursor-not-allowed
        ${active
          ? 'bg-gold-50 text-gold-700'
          : 'text-stone-500 hover:bg-stone-50 hover:text-stone-700'
        }
      `}
    >
      <span className="flex-shrink-0">{icon}</span>
      {label}
    </button>
  )
}
