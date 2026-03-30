import { useState, useEffect, useCallback } from 'react'
import { Navigate } from 'react-router-dom'
import {
    BarChart3,
    MapPin,
    Trophy,
    Globe,
    AlertTriangle,
    Loader2,
    RefreshCw,
    CheckCircle2,
    XCircle,
    Clock,
    Flag,
    GitMerge,
    ExternalLink,
    Play,
    RotateCcw,
    Search,
    Zap,
} from 'lucide-react'
import Sidebar, { NavItem, MobileMenuButton } from '../components/Sidebar'
import type {
    AdminStats,
    RecentEntry,
    SourceItem,
    ReportItem,
    MergeCandidateItem,
    DiscoveryVenueItem,
} from '../types/api'
import {
    fetchAdminStats,
    fetchRecentEntries,
    fetchSources,
    fetchReports,
    fetchMergeCandidates,
    fetchDiscoveryPending,
    resolveReport,
    reviewDiscoveryVenue,
    bulkReviewDiscoveryVenues,
    triggerCrawl,
    resetStaleSources,
    fetchSchedulerStatus,
    triggerDiscovery,
    formatUpdatedAt,
    hasAdminToken,
    clearAdminToken,
} from '../api/client'
import type { SchedulerStatus, CrawlTriggerResponse, CrawlResetStaleResponse, DiscoveryTriggerResponse } from '../api/client'
import { normalizeUrl } from '../utils/url'
import { DEFAULT_CRAWL_BATCH, DEFAULT_STALE_DAYS } from '../constants'

type Tab = 'overview' | 'sources' | 'reports' | 'merges' | 'discovery'

export default function AdminDashboardPage() {
    const [authed, setAuthed] = useState(hasAdminToken())
    const [tab, setTab] = useState<Tab>('overview')
    const [stats, setStats] = useState<AdminStats | null>(null)
    const [recent, setRecent] = useState<RecentEntry[]>([])
    const [sources, setSources] = useState<SourceItem[]>([])
    const [reports, setReports] = useState<ReportItem[]>([])
    const [merges, setMerges] = useState<MergeCandidateItem[]>([])
    const [discovery, setDiscovery] = useState<DiscoveryVenueItem[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(false)
    const [sidebarOpen, setSidebarOpen] = useState(false)

    const load = useCallback(async () => {
        setLoading(true)
        setError(false)
        try {
            const [s, r] = await Promise.all([fetchAdminStats(), fetchRecentEntries(20)])
            setStats(s)
            setRecent(r)
        } catch (err) {
            const msg = err instanceof Error ? err.message : ''
            if (msg === '401') {
                clearAdminToken()
                setAuthed(false)
                return
            }
            setError(true)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { if (authed) load() }, [load, authed])

    useEffect(() => {
        if (!authed) return
        if (tab === 'sources') fetchSources().then(setSources).catch(() => { })
        if (tab === 'reports') fetchReports().then(setReports).catch(() => { })
        if (tab === 'merges') fetchMergeCandidates().then(setMerges).catch(() => { })
        if (tab === 'discovery') fetchDiscoveryPending().then(setDiscovery).catch(() => { })
    }, [tab, authed])

    // 未認証 → 地図ページにリダイレクト（Sidebarの「管理」ボタンでログイン）
    if (!authed) return <Navigate to="/" replace />

    async function handleResolve(reportId: string, status: 'resolved' | 'rejected') {
        try {
            await resolveReport(reportId, { status, resolved_by: 'admin' })
            setReports(prev => prev.map(r =>
                r.id === reportId ? { ...r, status } : r
            ))
        } catch {
            alert('処理に失敗しました')
        }
    }

    const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
        { key: 'overview', label: '概要', icon: <BarChart3 size={14} /> },
        { key: 'sources', label: 'ソース', icon: <Globe size={14} /> },
        { key: 'reports', label: 'レポート', icon: <Flag size={14} /> },
        { key: 'merges', label: '統合候補', icon: <GitMerge size={14} /> },
        { key: 'discovery', label: '発見', icon: <Search size={14} /> },
    ]

    return (
        <div className="flex h-screen bg-[#080808]">
            {/* モバイルメニューボタン */}
            <MobileMenuButton onClick={() => setSidebarOpen(true)} dark />

            {/* ─── サイドバー ─── */}
            <Sidebar subtitle="Admin" dark mobileOpen={sidebarOpen} onMobileToggle={() => setSidebarOpen(o => !o)}>
                <div className="px-1 pt-1">
                    <p className="text-[10px] font-semibold text-[#3a3530] px-3 pb-1.5 uppercase tracking-[0.15em]">
                        メニュー
                    </p>
                    {TABS.map(t => (
                        <NavItem
                            key={t.key}
                            icon={t.icon}
                            label={t.label}
                            active={tab === t.key}
                            onClick={() => { setTab(t.key); setSidebarOpen(false) }}
                            dark
                        />
                    ))}
                </div>
                <div className="px-1 pt-2 border-t border-[#1e1e1e] mt-2">
                    <button
                        onClick={load}
                        disabled={loading}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium
                                   text-[#4a4540] hover:bg-white/5 hover:text-gold-500 transition-all
                                   disabled:opacity-30"
                    >
                        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                        更新
                    </button>
                </div>
            </Sidebar>

            {/* ─── メインコンテンツ ─── */}
            <main className="flex-1 overflow-y-auto" style={{ scrollbarColor: '#2a2a2a #080808' }}>
                <div className="max-w-4xl mx-auto px-5 py-6">

                    {/* ページヘッダー */}
                    <div className="mb-6 flex items-center justify-between">
                        <div>
                            <h1 className="text-sm font-bold text-gold-500/80 tracking-[0.25em] uppercase">
                                Dashboard
                            </h1>
                            <p className="text-xs text-[#3a3530] mt-0.5">管理パネル</p>
                        </div>
                        <div className="text-3xl text-[#1e1e1e] select-none font-serif leading-none">
                            ♠♥♦♣
                        </div>
                    </div>

                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-24 gap-3">
                            <Loader2 size={24} className="animate-spin text-gold-600/60" />
                            <p className="text-xs text-[#3a3530]">読み込み中...</p>
                        </div>
                    ) : error || !stats ? (
                        <div className="flex flex-col items-center py-24 gap-3">
                            <div className="w-12 h-12 rounded-xl bg-[#1a0608] border border-[#c41e3a]/20
                                            flex items-center justify-center">
                                <AlertTriangle size={20} className="text-[#c41e3a]/80" />
                            </div>
                            <p className="text-sm text-[#9a948c]">バックエンドに接続できません</p>
                            <p className="text-xs text-[#3a3530]">
                                APIサーバーが起動しているか確認してください
                            </p>
                            <button
                                onClick={load}
                                className="mt-1 px-4 py-1.5 text-xs text-gold-500/80 border border-gold-900/50
                                           rounded-lg hover:bg-gold-900/20 hover:border-gold-700/50 transition-colors"
                            >
                                再試行
                            </button>
                        </div>
                    ) : (
                        <>
                            {tab === 'overview' && <OverviewTab stats={stats} recent={recent} />}
                            {tab === 'sources' && <SourcesTab sources={sources} />}
                            {tab === 'reports' && <ReportsTab reports={reports} onResolve={handleResolve} />}
                            {tab === 'merges' && <MergesTab merges={merges} />}
                            {tab === 'discovery' && (
                                <DiscoveryTab
                                    venues={discovery}
                                    onReview={async (id, action) => {
                                        try {
                                            await reviewDiscoveryVenue(id, action)
                                            setDiscovery(prev => prev.filter(v => v.id !== id))
                                        } catch {
                                            alert('処理に失敗しました')
                                        }
                                    }}
                                    onBulkReview={async (ids, action) => {
                                        try {
                                            await bulkReviewDiscoveryVenues(ids, action)
                                            setDiscovery(prev => prev.filter(v => !ids.includes(v.id)))
                                        } catch {
                                            alert('一括処理に失敗しました')
                                        }
                                    }}
                                />
                            )}
                        </>
                    )}
                </div>
            </main>
        </div>
    )
}

// ══════════════════════════════════════════════
// 概要タブ
// ══════════════════════════════════════════════

function OverviewTab({ stats, recent }: { stats: AdminStats; recent: RecentEntry[] }) {
    return (
        <div className="space-y-4">
            {/* 統計カード */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <StatCard
                    label="店舗"
                    value={stats.total_venues}
                    icon={<MapPin size={15} />}
                    suit="♠"
                />
                <StatCard
                    label="大会"
                    value={stats.total_tournaments}
                    icon={<Trophy size={15} />}
                    suit="♥"
                    red
                />
                <StatCard
                    label="ソース"
                    value={stats.total_sources}
                    icon={<Globe size={15} />}
                    suit="♦"
                    red
                />
                <StatCard
                    label="クロールログ"
                    value={stats.total_crawl_logs}
                    icon={<BarChart3 size={15} />}
                    suit="♣"
                />
            </div>

            {/* アラート行 */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <AlertCard label="未処理レポート" value={stats.pending_reports} warn={stats.pending_reports > 0} />
                <AlertCard label="低信頼度店舗" value={stats.low_confidence_venues} warn={stats.low_confidence_venues > 0} />
                <AlertCard label="エラーソース" value={stats.error_sources} warn={stats.error_sources > 0} />
                <AlertCard label="統合候補" value={stats.pending_merge_candidates} warn={stats.pending_merge_candidates > 0} />
            </div>

            {/* ソースステータス内訳 */}
            <Section title="ソースステータス">
                <div className="flex gap-2 flex-wrap">
                    <StatusPill label="待機中" count={stats.pending_sources} variant="neutral" />
                    <StatusPill label="実行中" count={stats.running_sources} variant="blue" />
                    <StatusPill label="完了" count={stats.done_sources} variant="green" />
                    <StatusPill label="エラー" count={stats.error_sources} variant="red" />
                    <StatusPill label="ブロック疑い" count={stats.blocked_suspected_sources} variant="amber" />
                </div>
            </Section>

            {/* 最近追加 */}
            <Section title="最近追加された店舗">
                {recent.length === 0 ? (
                    <p className="text-xs text-[#3a3530] py-4 text-center">まだデータがありません</p>
                ) : (
                    <div className="space-y-0.5">
                        {recent.map(entry => (
                            <div
                                key={entry.id}
                                className="flex items-center gap-3 py-2 px-2 rounded-lg hover:bg-white/[0.03] transition-colors"
                            >
                                <MapPin size={12} className="text-gold-700/40 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm text-[#c8c4bc] truncate">{entry.name}</p>
                                    <p className="text-xs text-[#4a4540]">
                                        {[entry.area_prefecture, entry.area_city].filter(Boolean).join(' ')}
                                        {entry.match_confidence != null && (
                                            <span className={`ml-2 ${entry.match_confidence < 0.5
                                                ? 'text-[#c41e3a]/60'
                                                : 'text-emerald-700/70'
                                            }`}>
                                                {Math.round(entry.match_confidence * 100)}%
                                            </span>
                                        )}
                                    </p>
                                </div>
                                <span className="text-[10px] text-[#2e2e2e]">
                                    {formatUpdatedAt(entry.created_at)}
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </Section>
        </div>
    )
}

// ══════════════════════════════════════════════
// ソースタブ
// ══════════════════════════════════════════════

function SourcesTab({ sources }: { sources: SourceItem[] }) {
    const [crawling, setCrawling] = useState(false)
    const [resetting, setResetting] = useState(false)
    const [discovering, setDiscovering] = useState(false)
    const [crawlResult, setCrawlResult] = useState<CrawlTriggerResponse | null>(null)
    const [resetResult, setResetResult] = useState<CrawlResetStaleResponse | null>(null)
    const [discoveryResult, setDiscoveryResult] = useState<DiscoveryTriggerResponse | null>(null)
    const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null)

    useEffect(() => {
        fetchSchedulerStatus().then(setScheduler).catch(() => {})
    }, [])

    async function handleTriggerCrawl() {
        setCrawling(true)
        setCrawlResult(null)
        try {
            const result = await triggerCrawl(DEFAULT_CRAWL_BATCH)
            setCrawlResult(result)
        } catch {
            alert('クロール実行に失敗しました')
        } finally {
            setCrawling(false)
        }
    }

    async function handleResetStale() {
        setResetting(true)
        setResetResult(null)
        try {
            const result = await resetStaleSources(DEFAULT_STALE_DAYS)
            setResetResult(result)
        } catch {
            alert('リセットに失敗しました')
        } finally {
            setResetting(false)
        }
    }

    async function handleDiscovery() {
        setDiscovering(true)
        setDiscoveryResult(null)
        try {
            const result = await triggerDiscovery('all')
            setDiscoveryResult(result)
        } catch {
            alert('新店舗発見に失敗しました')
        } finally {
            setDiscovering(false)
        }
    }

    const statusStyle: Record<string, string> = {
        pending: 'bg-[#181818] text-[#4a4540] border border-[#272727]',
        running: 'bg-blue-950/60 text-blue-400 border border-blue-900/40',
        done: 'bg-emerald-950/60 text-emerald-400 border border-emerald-900/40',
        error: 'bg-[#c41e3a]/10 text-[#e06070] border border-[#c41e3a]/25',
        blocked_suspected: 'bg-amber-950/60 text-amber-400 border border-amber-900/40',
    }

    return (
        <div className="space-y-4">
            {/* クローラー操作パネル */}
            <div className="bg-[#0c0c0c] rounded-xl border border-[#1e1e1e] p-5">
                <h2 className="flex items-center gap-2 text-[10px] font-bold text-[#5a5040]
                               uppercase tracking-[0.2em] mb-3.5">
                    <span className="w-0.5 h-3 bg-gold-600/50 rounded-full" />
                    クローラー操作
                </h2>

                {/* スケジューラ状態 */}
                {scheduler && (
                    <div className="flex items-center gap-3 mb-4 text-xs flex-wrap">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium ${
                            scheduler.enabled
                                ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-900/40'
                                : 'bg-[#181818] text-[#4a4540] border border-[#272727]'
                        }`}>
                            <Zap size={10} />
                            クロール {scheduler.enabled ? '有効' : '無効'}
                        </span>
                        <span className="text-[#4a4540]">
                            間隔: {scheduler.interval_minutes}分
                        </span>
                        <span className="text-[#4a4540]">
                            バッチ: {scheduler.batch_size}件
                        </span>
                        <span className="text-[#4a4540]">|</span>
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium ${
                            scheduler.discovery_enabled
                                ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-900/40'
                                : 'bg-[#181818] text-[#4a4540] border border-[#272727]'
                        }`}>
                            <Search size={10} />
                            自動発見 {scheduler.discovery_enabled ? '有効' : '無効'}
                        </span>
                        <span className="text-[#4a4540]">
                            間隔: {scheduler.discovery_interval_hours}時間
                        </span>
                    </div>
                )}

                {/* 操作ボタン */}
                <div className="flex items-center gap-3 flex-wrap">
                    <button
                        onClick={handleTriggerCrawl}
                        disabled={crawling}
                        className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium
                                   text-gold-500/80 border border-gold-900/50 rounded-lg
                                   hover:bg-gold-900/20 hover:border-gold-700/60 transition-colors
                                   disabled:opacity-40"
                    >
                        {crawling ? (
                            <Loader2 size={12} className="animate-spin" />
                        ) : (
                            <Play size={12} />
                        )}
                        今すぐクロール
                    </button>

                    <button
                        onClick={handleResetStale}
                        disabled={resetting}
                        className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium
                                   text-[#9a948c] border border-[#2a2a2a] rounded-lg
                                   hover:bg-white/5 hover:border-[#3a3a3a] transition-colors
                                   disabled:opacity-40"
                    >
                        {resetting ? (
                            <Loader2 size={12} className="animate-spin" />
                        ) : (
                            <RotateCcw size={12} />
                        )}
                        古いデータを再取得
                    </button>

                    <button
                        onClick={handleDiscovery}
                        disabled={discovering}
                        className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium
                                   text-emerald-400/80 border border-emerald-900/50 rounded-lg
                                   hover:bg-emerald-900/20 hover:border-emerald-700/60 transition-colors
                                   disabled:opacity-40"
                    >
                        {discovering ? (
                            <Loader2 size={12} className="animate-spin" />
                        ) : (
                            <Search size={12} />
                        )}
                        新店舗を発見
                    </button>
                </div>

                {/* 結果表示 */}
                {crawlResult && (
                    <div className="mt-3 px-3 py-2 rounded-lg bg-emerald-950/40 border border-emerald-900/30 text-xs text-emerald-400">
                        {crawlResult.message}
                    </div>
                )}
                {resetResult && (
                    <div className="mt-3 px-3 py-2 rounded-lg bg-blue-950/40 border border-blue-900/30 text-xs text-blue-400">
                        {resetResult.message}
                    </div>
                )}
                {discoveryResult && (
                    <div className="mt-3 px-3 py-2 rounded-lg bg-emerald-950/40 border border-emerald-900/30 text-xs text-emerald-400">
                        {discoveryResult.message}
                    </div>
                )}
            </div>

            {/* ソーステーブル */}
            <div className="bg-[#0c0c0c] rounded-xl border border-[#1e1e1e] overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="bg-[#111] border-b border-[#1e1e1e]">
                                {['URL', '種別', 'ステータス', '失敗', '最終実行', 'エラー'].map(h => (
                                    <th
                                        key={h}
                                        className="text-left px-4 py-3 text-[10px] font-semibold
                                                   text-[#3a3530] uppercase tracking-widest"
                                    >
                                        {h}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {sources.map((s, i) => (
                                <tr
                                    key={s.id}
                                    className={`border-b border-[#141414] hover:bg-white/[0.02] transition-colors ${
                                        i % 2 === 0 ? '' : 'bg-white/[0.01]'
                                    }`}
                                >
                                    <td className="px-4 py-2.5 max-w-[250px]">
                                        {normalizeUrl(s.seed_url) ? (
                                            <a
                                                href={normalizeUrl(s.seed_url)!}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-gold-600/80 hover:text-gold-400 hover:underline
                                                           truncate flex items-center gap-1 transition-colors"
                                            >
                                                {(() => { try { return new URL(s.seed_url).hostname } catch { return s.seed_url } })()}
                                                <ExternalLink size={9} className="opacity-40 flex-shrink-0" />
                                            </a>
                                        ) : (
                                            <span className="text-[#4a4540] truncate">{s.seed_url}</span>
                                        )}
                                    </td>
                                    <td className="px-4 py-2.5 text-[#4a4540] text-xs">
                                        {s.seed_type || '—'}
                                    </td>
                                    <td className="px-4 py-2.5">
                                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium
                                                          ${statusStyle[s.status] ?? statusStyle.pending}`}>
                                            {s.status}
                                        </span>
                                    </td>
                                    <td className="px-4 py-2.5">
                                        {s.fail_count > 0 ? (
                                            <span className="text-[#e06070] font-semibold text-xs">
                                                {s.fail_count}
                                            </span>
                                        ) : (
                                            <span className="text-[#2e2e2e] text-xs">0</span>
                                        )}
                                    </td>
                                    <td className="px-4 py-2.5 text-[#3a3530] text-xs">
                                        {s.last_run_at ? formatUpdatedAt(s.last_run_at) : '—'}
                                    </td>
                                    <td className="px-4 py-2.5 text-[10px] text-[#c41e3a]/50 max-w-[160px] truncate">
                                        {s.error_reason || '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {sources.length === 0 && (
                        <p className="text-xs text-[#3a3530] py-10 text-center">ソースがありません</p>
                    )}
                </div>
            </div>
        </div>
    )
}

// ══════════════════════════════════════════════
// レポートタブ
// ══════════════════════════════════════════════

function ReportsTab({
    reports,
    onResolve,
}: {
    reports: ReportItem[]
    onResolve: (id: string, status: 'resolved' | 'rejected') => void
}) {
    const typeLabel: Record<string, string> = {
        remove: '削除',
        correct: '修正',
        claim_owner: 'オーナー申請',
    }
    const statusStyle: Record<string, string> = {
        pending: 'bg-amber-950/60 text-amber-400 border border-amber-900/40',
        resolved: 'bg-emerald-950/60 text-emerald-400 border border-emerald-900/40',
        rejected: 'bg-[#181818] text-[#4a4540] border border-[#272727]',
    }

    return (
        <div className="space-y-3">
            {reports.length === 0 && (
                <p className="text-xs text-[#3a3530] py-10 text-center
                              bg-[#0c0c0c] rounded-xl border border-[#1e1e1e]">
                    レポートがありません
                </p>
            )}
            {reports.map(r => (
                <div
                    key={r.id}
                    className="bg-[#0c0c0c] rounded-xl border border-[#1e1e1e] p-4 space-y-2.5
                               hover:border-[#2a2a2a] transition-colors"
                >
                    <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${statusStyle[r.status] ?? ''}`}>
                                {r.status}
                            </span>
                            <span className="text-[10px] text-[#3a3530] bg-[#141414]
                                             border border-[#222] rounded px-1.5 py-0.5">
                                {typeLabel[r.report_type] ?? r.report_type}
                            </span>
                        </div>
                        <span className="text-[10px] text-[#2e2e2e] flex items-center gap-1 flex-shrink-0">
                            <Clock size={9} />
                            {formatUpdatedAt(r.created_at)}
                        </span>
                    </div>

                    {r.details && (
                        <p className="text-xs text-[#7a7268] border-l-2 border-[#2a2a2a] pl-3 py-0.5">
                            {r.details}
                        </p>
                    )}

                    <div className="flex items-center justify-between gap-2">
                        <p className="text-[10px] text-[#3a3530]">
                            {r.reporter_name && (
                                <>報告者: <span className="text-[#5a5450]">{r.reporter_name}</span> · </>
                            )}
                            対象: {r.entity_type}{' '}
                            <span className="font-mono text-[#4a4540]">
                                ({r.entity_id.slice(0, 8)}…)
                            </span>
                        </p>

                        {r.status === 'pending' && (
                            <div className="flex gap-1.5 flex-shrink-0">
                                <button
                                    onClick={() => onResolve(r.id, 'resolved')}
                                    className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium
                                               text-gold-500/80 border border-gold-900/50 rounded-lg
                                               hover:bg-gold-900/20 hover:border-gold-700/60 transition-colors"
                                >
                                    <CheckCircle2 size={11} />
                                    承認
                                </button>
                                <button
                                    onClick={() => onResolve(r.id, 'rejected')}
                                    className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium
                                               text-[#e06070]/70 border border-[#c41e3a]/30 rounded-lg
                                               hover:bg-[#c41e3a]/10 hover:border-[#c41e3a]/50 transition-colors"
                                >
                                    <XCircle size={11} />
                                    却下
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            ))}
        </div>
    )
}

// ══════════════════════════════════════════════
// 統合候補タブ
// ══════════════════════════════════════════════

function MergesTab({ merges }: { merges: MergeCandidateItem[] }) {
    const statusStyle: Record<string, string> = {
        pending: 'bg-amber-950/60 text-amber-400 border border-amber-900/40',
        merged: 'bg-emerald-950/60 text-emerald-400 border border-emerald-900/40',
        rejected: 'bg-[#181818] text-[#4a4540] border border-[#272727]',
    }

    return (
        <div className="space-y-3">
            {merges.length === 0 && (
                <p className="text-xs text-[#3a3530] py-10 text-center
                              bg-[#0c0c0c] rounded-xl border border-[#1e1e1e]">
                    統合候補がありません
                </p>
            )}
            {merges.map(mc => (
                <div
                    key={mc.id}
                    className="bg-[#0c0c0c] rounded-xl border border-[#1e1e1e] p-4 space-y-2.5
                               hover:border-[#2a2a2a] transition-colors"
                >
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <GitMerge size={13} className="text-gold-700/40" />
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${statusStyle[mc.status] ?? ''}`}>
                                {mc.status}
                            </span>
                        </div>
                        <span className="text-[10px] text-[#2e2e2e]">
                            {formatUpdatedAt(mc.created_at)}
                        </span>
                    </div>
                    <div className="bg-[#111] rounded-lg p-3 border border-[#1a1a1a] space-y-1.5">
                        <p className="text-xs text-[#4a4540]">
                            店舗A:{' '}
                            <span className="font-mono text-[#6a6460]">{mc.venue_a_id.slice(0, 12)}…</span>
                        </p>
                        <p className="text-xs text-[#4a4540]">
                            店舗B:{' '}
                            <span className="font-mono text-[#6a6460]">{mc.venue_b_id.slice(0, 12)}…</span>
                        </p>
                        {mc.similarity_score != null && (
                            <div className="flex items-center gap-2 pt-0.5">
                                <span className="text-[10px] text-[#3a3530]">類似度</span>
                                <div className="flex-1 h-1 bg-[#1e1e1e] rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-gold-600/60 rounded-full transition-all"
                                        style={{ width: `${mc.similarity_score * 100}%` }}
                                    />
                                </div>
                                <span className="text-xs font-bold text-gold-500/80">
                                    {Math.round(mc.similarity_score * 100)}%
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            ))}
        </div>
    )
}

// ══════════════════════════════════════════════
// 発見タブ
// ══════════════════════════════════════════════

function DiscoveryTab({
    venues,
    onReview,
    onBulkReview,
}: {
    venues: DiscoveryVenueItem[]
    onReview: (id: string, action: 'approve' | 'reject') => void
    onBulkReview: (ids: string[], action: 'approve' | 'reject') => void
}) {
    const [selected, setSelected] = useState<Set<string>>(new Set())
    const [expandedId, setExpandedId] = useState<string | null>(null)

    const toggleSelect = (id: string) => {
        setSelected(prev => {
            const next = new Set(prev)
            if (next.has(id)) next.delete(id)
            else next.add(id)
            return next
        })
    }
    const selectAll = () => setSelected(new Set(venues.map(v => v.id)))
    const selectNone = () => setSelected(new Set())

    const foodLabel = (fl: string | null) => {
        if (!fl) return null
        return fl === 'rich' ? 'フード充実' : fl === 'basic' ? '軽食あり' : 'フードなし'
    }

    return (
        <div className="space-y-3">
            {/* 一括操作バー */}
            {venues.length > 0 && (
                <div className="flex items-center justify-between bg-[#0c0c0c] rounded-xl
                                border border-[#1e1e1e] px-4 py-2.5">
                    <div className="flex items-center gap-3">
                        <span className="text-xs text-[#4a4540]">
                            {venues.length}件中 {selected.size}件選択
                        </span>
                        <button onClick={selectAll}
                            className="text-[10px] text-gold-600/60 hover:text-gold-400 transition-colors">
                            全選択
                        </button>
                        <button onClick={selectNone}
                            className="text-[10px] text-[#4a4540] hover:text-[#6a6560] transition-colors">
                            解除
                        </button>
                    </div>
                    {selected.size > 0 && (
                        <div className="flex gap-1.5">
                            <button
                                onClick={() => { onBulkReview([...selected], 'approve'); selectNone() }}
                                className="flex items-center gap-1 px-3 py-1 text-[10px] font-medium
                                           text-gold-500/80 border border-gold-900/50 rounded-lg
                                           hover:bg-gold-900/20 hover:border-gold-700/60 transition-colors"
                            >
                                <CheckCircle2 size={11} />
                                一括承認
                            </button>
                            <button
                                onClick={() => { onBulkReview([...selected], 'reject'); selectNone() }}
                                className="flex items-center gap-1 px-3 py-1 text-[10px] font-medium
                                           text-[#e06070]/70 border border-[#c41e3a]/30 rounded-lg
                                           hover:bg-[#c41e3a]/10 hover:border-[#c41e3a]/50 transition-colors"
                            >
                                <XCircle size={11} />
                                一括却下
                            </button>
                        </div>
                    )}
                </div>
            )}

            {venues.length === 0 && (
                <p className="text-xs text-[#3a3530] py-10 text-center
                              bg-[#0c0c0c] rounded-xl border border-[#1e1e1e]">
                    レビュー待ちの店舗がありません
                </p>
            )}
            {venues.map(v => {
                const isExpanded = expandedId === v.id
                const isSelected = selected.has(v.id)
                return (
                    <div
                        key={v.id}
                        className={`bg-[#0c0c0c] rounded-xl border p-4 space-y-2.5
                                   hover:border-[#2a2a2a] transition-colors
                                   ${isSelected ? 'border-gold-900/60' : 'border-[#1e1e1e]'}`}
                    >
                        <div className="flex items-start gap-2">
                            {/* チェックボックス */}
                            <button onClick={() => toggleSelect(v.id)}
                                className={`mt-0.5 w-4 h-4 rounded border flex-shrink-0
                                           flex items-center justify-center transition-colors
                                           ${isSelected
                                    ? 'bg-gold-600/30 border-gold-600/60'
                                    : 'border-[#2a2a2a] hover:border-[#3a3a3a]'}`}
                            >
                                {isSelected && <CheckCircle2 size={10} className="text-gold-500" />}
                            </button>

                            <div className="flex-1 min-w-0 cursor-pointer"
                                onClick={() => setExpandedId(isExpanded ? null : v.id)}>
                                <div className="flex items-start justify-between gap-2">
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm text-[#c8c4bc] font-medium truncate">{v.name}</p>
                                        <p className="text-xs text-[#4a4540] mt-0.5">
                                            {[v.area_prefecture, v.area_city].filter(Boolean).join(' ') || '—'}
                                            {v.address && <span className="ml-2 text-[#3a3530]">{v.address}</span>}
                                        </p>
                                    </div>
                                    <span className="text-[10px] text-[#2e2e2e] flex items-center gap-1 flex-shrink-0">
                                        <Clock size={9} />
                                        {formatUpdatedAt(v.created_at)}
                                    </span>
                                </div>

                                {/* サマリー行: 主要情報をコンパクトに */}
                                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2">
                                    {normalizeUrl(v.website_url) && (
                                        <a href={normalizeUrl(v.website_url)!} target="_blank" rel="noopener noreferrer"
                                            onClick={e => e.stopPropagation()}
                                            className="text-xs text-gold-600/80 hover:text-gold-400 hover:underline
                                                       truncate flex items-center gap-1 transition-colors max-w-[200px]">
                                            {(() => { try { return new URL(v.website_url!).hostname } catch { return v.website_url } })()}
                                            <ExternalLink size={9} className="opacity-40 flex-shrink-0" />
                                        </a>
                                    )}
                                    {v.price_entry_min != null && (
                                        <span className="text-[10px] text-[#5a5550]">
                                            ¥{v.price_entry_min.toLocaleString()}〜
                                        </span>
                                    )}
                                    {v.table_count != null && (
                                        <span className="text-[10px] text-[#5a5550]">
                                            {v.table_count}卓
                                        </span>
                                    )}
                                    {v.food_level && (
                                        <span className="text-[10px] text-[#5a5550]">
                                            {foodLabel(v.food_level)}
                                        </span>
                                    )}
                                    {v.lat != null && v.lng != null && (
                                        <span className="text-[10px] text-[#3a3530]">
                                            📍{v.lat.toFixed(2)},{v.lng.toFixed(2)}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* 信頼度バー */}
                        {v.match_confidence != null && (
                            <div className="flex items-center gap-2 ml-6">
                                <span className="text-[10px] text-[#3a3530]">信頼度</span>
                                <div className="flex-1 h-1 bg-[#1e1e1e] rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all ${
                                            v.match_confidence >= 0.7 ? 'bg-green-600/60'
                                            : v.match_confidence >= 0.4 ? 'bg-gold-600/60'
                                            : 'bg-red-600/60'
                                        }`}
                                        style={{ width: `${v.match_confidence * 100}%` }}
                                    />
                                </div>
                                <span className={`text-xs font-bold ${
                                    v.match_confidence >= 0.7 ? 'text-green-500/80'
                                    : v.match_confidence >= 0.4 ? 'text-gold-500/80'
                                    : 'text-red-500/80'
                                }`}>
                                    {Math.round(v.match_confidence * 100)}%
                                </span>
                            </div>
                        )}

                        {/* 展開時の詳細 */}
                        {isExpanded && (
                            <div className="ml-6 space-y-2 border-t border-[#1a1a1a] pt-2.5">
                                {v.hours_today && (
                                    <div className="text-xs text-[#5a5550]">
                                        <span className="text-[#3a3530] mr-2">営業時間</span>{v.hours_today}
                                    </div>
                                )}
                                {v.price_note && (
                                    <div className="text-xs text-[#5a5550]">
                                        <span className="text-[#3a3530] mr-2">料金備考</span>{v.price_note}
                                    </div>
                                )}
                                {v.summary && (
                                    <div className="text-xs text-[#5a5550] leading-relaxed">
                                        <span className="text-[#3a3530] mr-2">概要</span>{v.summary}
                                    </div>
                                )}
                                {v.sources && v.sources.length > 0 && (
                                    <div className="text-xs text-[#3a3530]">
                                        <span className="mr-2">ソース ({v.sources.length})</span>
                                        {v.sources.map((src, i) => normalizeUrl(src) ? (
                                            <a key={i} href={normalizeUrl(src)!} target="_blank" rel="noopener noreferrer"
                                                className="block text-gold-600/50 hover:text-gold-400 truncate mt-0.5">
                                                {src}
                                            </a>
                                        ) : (
                                            <span key={i} className="block text-[#4a4540] truncate mt-0.5">{src}</span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* アクションボタン */}
                        <div className="flex justify-end gap-1.5 ml-6">
                            <button
                                onClick={() => onReview(v.id, 'approve')}
                                className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium
                                           text-gold-500/80 border border-gold-900/50 rounded-lg
                                           hover:bg-gold-900/20 hover:border-gold-700/60 transition-colors"
                            >
                                <CheckCircle2 size={11} />
                                承認
                            </button>
                            <button
                                onClick={() => onReview(v.id, 'reject')}
                                className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium
                                           text-[#e06070]/70 border border-[#c41e3a]/30 rounded-lg
                                           hover:bg-[#c41e3a]/10 hover:border-[#c41e3a]/50 transition-colors"
                            >
                                <XCircle size={11} />
                                却下
                            </button>
                        </div>
                    </div>
                )
            })}
        </div>
    )
}

// ══════════════════════════════════════════════
// ユーティリティコンポーネント
// ══════════════════════════════════════════════

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section className="bg-[#0c0c0c] rounded-xl border border-[#1e1e1e] p-5">
            <h2 className="flex items-center gap-2 text-[10px] font-bold text-[#5a5040]
                           uppercase tracking-[0.2em] mb-3.5">
                <span className="w-0.5 h-3 bg-gold-600/50 rounded-full" />
                {title}
            </h2>
            {children}
        </section>
    )
}

function StatCard({
    label,
    value,
    icon,
    suit,
    red = false,
}: {
    label: string
    value: number
    icon: React.ReactNode
    suit: string
    red?: boolean
}) {
    return (
        <div className="bg-[#0c0c0c] rounded-xl border border-[#1e1e1e] p-4 relative overflow-hidden
                        group hover:border-[#2a2a2a] transition-all">
            {/* スーツ透かし */}
            <div className={`absolute right-2 top-0 text-6xl opacity-[0.05] select-none font-serif
                             leading-none group-hover:opacity-[0.09] transition-opacity
                             ${red ? 'text-[#c41e3a]' : 'text-gold-500'}`}>
                {suit}
            </div>
            {/* アイコン */}
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                red
                    ? 'bg-[#c41e3a]/8 border border-[#c41e3a]/15 text-[#c41e3a]/60'
                    : 'bg-gold-500/8 border border-gold-800/30 text-gold-600/70'
            }`}>
                {icon}
            </div>
            {/* 値 */}
            <p className={`text-3xl font-bold mt-3 tabular-nums ${
                red ? 'text-[#d84060]' : 'text-gold-400/90'
            }`}>
                {value.toLocaleString('ja-JP')}
            </p>
            <p className="text-[10px] text-[#3a3530] mt-0.5 uppercase tracking-wider">{label}</p>
        </div>
    )
}

function AlertCard({ label, value, warn }: { label: string; value: number; warn: boolean }) {
    return (
        <div className={`rounded-xl border p-3 flex items-center gap-2.5 transition-colors ${
            warn
                ? 'bg-[#150506] border-[#c41e3a]/20 hover:border-[#c41e3a]/35'
                : 'bg-[#0c0c0c] border-[#1e1e1e]'
        }`}>
            {warn ? (
                <div className="w-6 h-6 rounded-lg bg-[#c41e3a]/10 border border-[#c41e3a]/20
                                flex items-center justify-center flex-shrink-0">
                    <AlertTriangle size={12} className="text-[#c41e3a]/70" />
                </div>
            ) : (
                <div className="w-6 h-6 rounded-lg bg-[#141414] border border-[#222]
                                flex items-center justify-center flex-shrink-0">
                    <CheckCircle2 size={12} className="text-emerald-800/60" />
                </div>
            )}
            <div>
                <p className={`text-xl font-bold tabular-nums ${
                    warn ? 'text-[#d84060]' : 'text-[#3a3530]'
                }`}>
                    {value}
                </p>
                <p className="text-[9px] text-[#3a3530] leading-tight uppercase tracking-wider">
                    {label}
                </p>
            </div>
        </div>
    )
}

function StatusPill({
    label,
    count,
    variant,
}: {
    label: string
    count: number
    variant: 'neutral' | 'blue' | 'green' | 'red' | 'amber'
}) {
    const styles: Record<string, string> = {
        neutral: 'bg-[#141414] text-[#4a4540] border border-[#222]',
        blue:    'bg-blue-950/60 text-blue-400/80 border border-blue-900/30',
        green:   'bg-emerald-950/60 text-emerald-400/80 border border-emerald-900/30',
        red:     'bg-[#c41e3a]/8 text-[#e06070]/80 border border-[#c41e3a]/20',
        amber:   'bg-amber-950/60 text-amber-400/80 border border-amber-900/30',
    }
    return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                          text-[10px] font-medium ${styles[variant]}`}>
            {label}
            <span className="font-bold opacity-70">{count}</span>
        </span>
    )
}
