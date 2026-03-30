import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  MapPin,
  Clock,
  Trophy,
  ExternalLink,
  GlassWater,
  UtensilsCrossed,
  LayoutGrid,
  Flag,
  Globe,
  Loader2,
  AlertCircle,
  ChevronRight,
  Users,
  Banknote,
  Calendar,
} from 'lucide-react'
import type { VenueDetail, TournamentBrief } from '../types/api'
import { fetchVenueDetail, formatPrice, formatDate, formatUpdatedAt } from '../api/client'
import { MS_PER_DAY } from '../constants'
import { normalizeUrl } from '../utils/url'
import StatusBadge from '../components/StatusBadge'

type ReportType = 'remove' | 'correct' | 'claim_owner'

export default function VenueDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [venue, setVenue] = useState<VenueDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showReport, setShowReport] = useState(false)
  const [reportSending, setReportSending] = useState(false)
  const [reportDone, setReportDone] = useState(false)

  const MOCK_VENUES: Record<string, VenueDetail> = import.meta.env.DEV ? {
    'mock-001': {
      id: 'mock-001',
      name: 'POKER ROOM SHINJUKU（テスト）',
      open_status: 'open',
      hours_today: '13:00〜翌5:00',
      price_entry_min: 3000,
      price_note: '1ドリンク込み',
      next_tournament_title: '週末トーナメント',
      next_tournament_start: new Date(Date.now() + 2 * MS_PER_DAY).toISOString(),
      next_tournament_url: null,
      drink_required: true,
      food_level: 'basic',
      table_count: 8,
      peak_time: '20:00〜24:00',
      address: '東京都新宿区歌舞伎町1丁目',
      area_prefecture: '東京都',
      area_city: '新宿区',
      lat: 35.6938,
      lng: 139.7036,
      website_url: null,
      sns_links: { twitter: 'https://twitter.com', instagram: 'https://instagram.com' },
      summary: '新宿歌舞伎町エリアにある本格ポーカールーム。初心者から上級者まで楽しめる環境を提供しています。',
      verification_status: 'verified',
      visibility_status: 'visible',
      match_confidence: 0.95,
      field_confidence: null,
      country_code: 'JP',
      locale: 'ja',
      time_zone: 'Asia/Tokyo',
      last_updated_at: null,
      data_age_days: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      sources: null,
      tournaments: [
        {
          id: 'mock-t-001',
          title: '週末トーナメント',
          start_at: new Date(Date.now() + 2 * MS_PER_DAY).toISOString(),
          buy_in: 5000,
          guarantee: 100000,
          capacity: 40,
          url: '#',
          status: 'scheduled',
        },
        {
          id: 'mock-t-002',
          title: '先週のトーナメント',
          start_at: new Date(Date.now() - 7 * MS_PER_DAY).toISOString(),
          buy_in: 5000,
          guarantee: 80000,
          capacity: 32,
          url: '#',
          status: 'finished',
        },
      ],
    },
  } : {}

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)
    fetchVenueDetail(id)
      .then(setVenue)
      .catch(() => {
        if (MOCK_VENUES[id]) {
          setVenue(MOCK_VENUES[id])
        } else {
          setError('店舗情報の取得に失敗しました')
        }
      })
      .finally(() => setLoading(false))
  }, [id])

  async function submitReport(type: ReportType, details: string) {
    if (!id) return
    setReportSending(true)
    try {
      const res = await fetch(`/api/venue/${id}/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_type: type,
          entity_type: 'venue',
          entity_id: id,
          details,
        }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      setReportDone(true)
      setShowReport(false)
    } catch {
      alert('レポートの送信に失敗しました')
    } finally {
      setReportSending(false)
    }
  }

  // ───────── ローディング / エラー ─────────
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-stone-50">
        <div className="flex flex-col items-center gap-3">
          <Loader2 size={32} className="animate-spin text-gold-500" />
          <p className="text-sm text-stone-400">読み込み中…</p>
        </div>
      </div>
    )
  }

  if (error || !venue) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-stone-50 gap-4">
        <AlertCircle size={40} className="text-red-400" />
        <p className="text-sm text-red-500">{error || '店舗が見つかりませんでした'}</p>
        <button
          onClick={() => navigate('/')}
          className="text-sm text-gold-500 hover:underline"
        >
          トップに戻る
        </button>
      </div>
    )
  }

  const tournaments = venue.tournaments ?? []
  const scheduledTournaments = tournaments.filter(t => t.status === 'scheduled')
  const pastTournaments = tournaments.filter(t => t.status !== 'scheduled')
  const foodLabel: Record<string, string> = {
    none: 'フードなし',
    basic: '軽食あり',
    rich: 'フード充実',
  }

  return (
    <div className="min-h-screen bg-stone-50">
      {/* ─── ヘッダー ─── */}
      <header className="sticky top-0 z-20 bg-white border-b border-stone-100 shadow-sm">
        <div className="max-w-2xl mx-auto flex items-center h-12 px-4 gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-1.5 rounded-lg hover:bg-stone-100 transition-colors text-stone-500"
          >
            <ArrowLeft size={18} />
          </button>
          <h1 className="font-bold text-stone-900 truncate text-base flex-1">
            {venue.name}
          </h1>
          {normalizeUrl(venue.website_url) && (
            <a
              href={normalizeUrl(venue.website_url)!}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded-lg hover:bg-stone-100 transition-colors text-stone-400"
              title="公式サイト"
            >
              <Globe size={18} />
            </a>
          )}
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-4 space-y-4 pb-24">
        {/* ─── セクション1: ステータス・料金・次回大会 ─── */}
        <section className="bg-white rounded-2xl border border-stone-100 shadow-sm p-5 space-y-4">
          {/* 営業ステータス */}
          <div className="flex items-start justify-between gap-3">
            <div>
              <StatusBadge status={venue.open_status} hoursToday={venue.hours_today} />
            </div>
            <span className="text-xs text-stone-300 flex items-center gap-1 mt-1">
              <Clock size={10} />
              {formatUpdatedAt(venue.updated_at)}
            </span>
          </div>

          {/* 料金 */}
          {venue.price_entry_min != null && (
            <div className="flex items-baseline gap-2">
              <Banknote size={16} className="text-gold-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-lg font-bold text-gold-700">
                  {formatPrice(venue.price_entry_min)}
                </p>
                {venue.price_note && (
                  <p className="text-xs text-stone-400 mt-0.5">{venue.price_note}</p>
                )}
              </div>
            </div>
          )}

          {/* 次回大会（あれば） */}
          {scheduledTournaments.length > 0 && (
            <div className="bg-amber-50 rounded-xl p-3 space-y-1">
              <p className="text-xs font-medium text-amber-700 flex items-center gap-1">
                <Trophy size={12} />
                次回大会
              </p>
              <p className="text-sm font-bold text-stone-900">
                {scheduledTournaments[0].title}
              </p>
              <p className="text-xs text-amber-600">
                {formatDate(scheduledTournaments[0].start_at)}
                {scheduledTournaments[0].buy_in != null && (
                  <> · バイイン ¥{scheduledTournaments[0].buy_in.toLocaleString('ja-JP')}</>
                )}
                {scheduledTournaments[0].guarantee != null && (
                  <> · GTD ¥{scheduledTournaments[0].guarantee.toLocaleString('ja-JP')}</>
                )}
              </p>
            </div>
          )}
        </section>

        {/* ─── セクション2: 大会一覧 ─── */}
        {tournaments.length > 0 && (
          <section className="bg-white rounded-2xl border border-stone-100 shadow-sm p-5 space-y-3">
            <h2 className="text-sm font-bold text-stone-800 flex items-center gap-1.5">
              <Trophy size={14} className="text-gold-500" />
              大会一覧
            </h2>

            {/* 予定大会 */}
            {scheduledTournaments.length > 0 && (
              <div className="space-y-2">
                {scheduledTournaments.map(t => (
                  <TournamentRow key={t.id} tournament={t} />
                ))}
              </div>
            )}

            {/* 過去の大会 */}
            {pastTournaments.length > 0 && (
              <details className="group">
                <summary className="text-xs text-stone-400 cursor-pointer hover:text-stone-600 transition-colors py-1">
                  過去の大会 ({pastTournaments.length})
                </summary>
                <div className="space-y-2 mt-2">
                  {pastTournaments.map(t => (
                    <TournamentRow key={t.id} tournament={t} past />
                  ))}
                </div>
              </details>
            )}
          </section>
        )}

        {/* ─── セクション3: 施設情報 ─── */}
        <section className="bg-white rounded-2xl border border-stone-100 shadow-sm p-5 space-y-3">
          <h2 className="text-sm font-bold text-stone-800">施設情報</h2>

          <div className="grid grid-cols-2 gap-2">
            {venue.drink_required === true && (
              <InfoChip icon={<GlassWater size={14} />} label="1ドリンク制" />
            )}
            {venue.food_level && venue.food_level !== 'none' && (
              <InfoChip icon={<UtensilsCrossed size={14} />} label={foodLabel[venue.food_level] || venue.food_level} />
            )}
            {venue.table_count != null && (
              <InfoChip icon={<LayoutGrid size={14} />} label={`テーブル ${venue.table_count}台`} />
            )}
            {venue.peak_time && (
              <InfoChip icon={<Clock size={14} />} label={`ピーク: ${venue.peak_time}`} />
            )}
          </div>

          {venue.summary && (
            <p className="text-sm text-stone-600 leading-relaxed mt-2">{venue.summary}</p>
          )}
        </section>

        {/* ─── セクション4: 住所・地図・外部リンク ─── */}
        <section className="bg-white rounded-2xl border border-stone-100 shadow-sm p-5 space-y-4">
          <h2 className="text-sm font-bold text-stone-800">アクセス</h2>

          {/* 住所 */}
          <div className="flex items-start gap-2">
            <MapPin size={14} className="text-stone-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm text-stone-700">{venue.address}</p>
              {(venue.area_prefecture || venue.area_city) && (
                <p className="text-xs text-stone-400 mt-0.5">
                  {[venue.area_prefecture, venue.area_city].filter(Boolean).join(' ')}
                </p>
              )}
            </div>
          </div>

          {/* Google Mapsリンク */}
          {venue.lat != null && venue.lng != null && (
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${venue.lat},${venue.lng}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-gold-600 hover:text-gold-700
                         border border-gold-200 rounded-lg px-3 py-2 hover:bg-gold-50 transition-colors"
            >
              <MapPin size={14} />
              Google Maps で開く
              <ExternalLink size={12} />
            </a>
          )}

          {/* 外部リンク */}
          <div className="space-y-1.5">
            {venue.website_url && (
              <ExternalLinkRow label="公式サイト" url={venue.website_url} />
            )}
            {venue.sns_links && Object.entries(venue.sns_links).map(([key, url]) => (
              <ExternalLinkRow key={key} label={snsLabel(key)} url={url} />
            ))}
            {venue.sources && venue.sources.map((src, i) => {
              const url = typeof src === 'string' ? src : null
              if (!url) return null
              return <ExternalLinkRow key={i} label={sourceLabel(url)} url={url} />
            })}
          </div>
        </section>

        {/* ─── レポートボタン ─── */}
        {!reportDone && (
          <button
            onClick={() => setShowReport(true)}
            className="w-full flex items-center justify-center gap-2 py-3 text-sm
                       text-stone-400 hover:text-red-500 transition-colors"
          >
            <Flag size={14} />
            情報の修正を報告する
          </button>
        )}
        {reportDone && (
          <p className="text-center text-sm text-emerald-600 py-3">
            ✓ レポートを送信しました。ありがとうございます。
          </p>
        )}
      </div>

      {/* ─── レポートモーダル ─── */}
      {showReport && (
        <ReportModal
          sending={reportSending}
          onClose={() => setShowReport(false)}
          onSubmit={submitReport}
        />
      )}
    </div>
  )
}

// ── URLバリデーション ─────────────────────────────────────

// ── サブコンポーネント ──────────────────────────────────────

function TournamentRow({ tournament, past }: { tournament: TournamentBrief; past?: boolean }) {
  const validUrl = normalizeUrl(tournament.url)
  const baseClass = `
    flex items-center gap-3 p-3 rounded-xl border transition-all duration-150
    ${past
      ? 'border-stone-100 bg-stone-50 opacity-60'
      : 'border-stone-100 bg-white'
    }
  `

  const inner = (
    <>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium truncate ${past ? 'text-stone-500' : 'text-stone-900'}`}>
          {tournament.title}
        </p>
        <div className="flex items-center gap-2 mt-0.5 text-xs text-stone-400 flex-wrap">
          {tournament.start_at && (
            <span className="flex items-center gap-1">
              <Calendar size={10} />
              {formatDate(tournament.start_at)}
            </span>
          )}
          {tournament.buy_in != null && (
            <span className="flex items-center gap-1">
              <Banknote size={10} />
              ¥{tournament.buy_in.toLocaleString('ja-JP')}
            </span>
          )}
          {tournament.guarantee != null && (
            <span>GTD ¥{tournament.guarantee.toLocaleString('ja-JP')}</span>
          )}
          {tournament.capacity != null && (
            <span className="flex items-center gap-1">
              <Users size={10} />
              {tournament.capacity}名
            </span>
          )}
        </div>
      </div>
      {validUrl
        ? <ChevronRight size={14} className="text-stone-300 flex-shrink-0" />
        : <span className="text-xs text-stone-300 flex-shrink-0">—</span>
      }
    </>
  )

  if (validUrl) {
    return (
      <a
        href={validUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={`${baseClass} hover:opacity-80 hover:border-gold-200 hover:shadow-sm`}
      >
        {inner}
      </a>
    )
  }
  return <div className={baseClass}>{inner}</div>
}

function InfoChip({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-stone-600 bg-stone-50
                    border border-stone-200 rounded-lg px-3 py-2">
      <span className="text-stone-400">{icon}</span>
      {label}
    </div>
  )
}

function ExternalLinkRow({ label, url }: { label: string; url: string | null | undefined }) {
  const validUrl = normalizeUrl(url)
  if (!validUrl) return null
  return (
    <a
      href={validUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center justify-between py-2 px-3 rounded-lg
                 hover:bg-stone-50 transition-colors group"
    >
      <span className="text-sm text-stone-600 group-hover:text-gold-600 transition-colors">
        {label}
      </span>
      <ExternalLink size={12} className="text-stone-300 group-hover:text-gold-400" />
    </a>
  )
}

function sourceLabel(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '')
    const known: Record<string, string> = {
      'tabelog.com': '食べログ',
      'retty.me': 'Retty',
      'gnavi.co.jp': 'ぐるなび',
      'hotpepper.jp': 'ホットペッパー',
      'google.com': 'Google',
      'ggpokerlive.jp': 'GoodGame Poker Live',
      'kingscasino.jp': 'KINGS Casino',
      'backdoor.casino': 'BACKDOOR',
      'roots-poker.com': 'ROOTS',
      'pokerfans.jp': 'PokerFans',
      'owst.jp': 'OWSTグルメ',
      'jimdosite.com': 'Jimdo',
      'wixsite.com': 'Wix',
      'lit.link': 'lit.link',
      'linktree.com': 'Linktree',
    }
    for (const [domain, label] of Object.entries(known)) {
      if (host === domain || host.endsWith('.' + domain)) return label
    }
    // ドメイン名からそれらしいラベルを生成
    const parts = host.split('.')
    const name = parts.length >= 2 ? parts[parts.length - 2] : host
    return name.charAt(0).toUpperCase() + name.slice(1)
  } catch {
    return url
  }
}

function snsLabel(key: string): string {
  const map: Record<string, string> = {
    twitter: 'Twitter / X',
    x: 'Twitter / X',
    instagram: 'Instagram',
    facebook: 'Facebook',
    line: 'LINE',
    youtube: 'YouTube',
  }
  return map[key.toLowerCase()] || key
}

function ReportModal({
  sending,
  onClose,
  onSubmit,
}: {
  sending: boolean
  onClose: () => void
  onSubmit: (type: ReportType, details: string) => void
}) {
  const [type, setType] = useState<ReportType>('correct')
  const [details, setDetails] = useState('')

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl p-6 space-y-4
                      animate-slide-up">
        <h3 className="font-bold text-stone-900">情報の修正を報告</h3>

        <div className="space-y-2">
          {([
            { value: 'correct' as const, label: '情報の修正', desc: '営業時間や料金などの誤りを報告' },
            { value: 'remove' as const, label: '削除リクエスト', desc: '閉店済み・重複などの理由で削除を依頼' },
            { value: 'claim_owner' as const, label: 'オーナー申請', desc: 'この店舗のオーナーであることを申請' },
          ] as const).map(opt => (
            <label
              key={opt.value}
              className={`
                block p-3 rounded-xl border cursor-pointer transition-all
                ${type === opt.value
                  ? 'border-gold-400 bg-gold-50 shadow-sm'
                  : 'border-stone-200 hover:border-stone-300'
                }
              `}
            >
              <input
                type="radio"
                name="reportType"
                value={opt.value}
                checked={type === opt.value}
                onChange={() => setType(opt.value)}
                className="sr-only"
              />
              <p className="text-sm font-medium text-stone-800">{opt.label}</p>
              <p className="text-xs text-stone-400 mt-0.5">{opt.desc}</p>
            </label>
          ))}
        </div>

        <textarea
          value={details}
          onChange={e => setDetails(e.target.value)}
          placeholder="詳細を入力してください（任意）"
          rows={3}
          className="w-full border border-stone-200 rounded-xl p-3 text-sm text-stone-700
                     placeholder:text-stone-300 focus:outline-none focus:border-gold-400
                     focus:ring-2 focus:ring-gold-100 resize-none transition-all"
        />

        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 text-sm text-stone-500 border border-stone-200
                       rounded-xl hover:bg-stone-50 transition-colors"
          >
            キャンセル
          </button>
          <button
            onClick={() => onSubmit(type, details)}
            disabled={sending}
            className="flex-1 py-2.5 text-sm text-white bg-gold-500 hover:bg-gold-600
                       rounded-xl font-medium transition-colors disabled:opacity-50"
          >
            {sending ? '送信中…' : '送信'}
          </button>
        </div>
      </div>
    </div>
  )
}
