import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { LayoutDashboard, Loader2, Menu, X } from 'lucide-react'
import {
  setAdminToken,
  hasAdminToken,
  clearAdminToken,
  fetchAdminStats,
} from '../api/client'

interface NavItemProps {
  icon: React.ReactNode
  label: string
  active?: boolean
  onClick: () => void
  dark?: boolean
}

function NavItem({ icon, label, active, onClick, dark }: NavItemProps) {
  if (dark) {
    return (
      <button
        onClick={onClick}
        className={`
          w-full flex items-center gap-2.5 py-2 rounded-lg text-sm font-medium
          transition-all duration-150 text-left
          ${active
            ? 'px-[10px] bg-gold-500/10 text-gold-400 border-l-2 border-gold-500'
            : 'px-3 text-[#5a5450] hover:bg-white/5 hover:text-gold-400 border-l-2 border-transparent'
          }
        `}
      >
        <span className="flex-shrink-0">{icon}</span>
        {label}
      </button>
    )
  }

  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium
        transition-all duration-150 text-left
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

interface SidebarProps {
  subtitle?: string
  children?: React.ReactNode
  dark?: boolean
  onLogoClick?: () => void
  mobileOpen?: boolean
  onMobileToggle?: () => void
}

// スワイプ検出の定数
const EDGE_WIDTH = 24         // 左端の検出幅(px)
const SWIPE_THRESHOLD = 60    // 開閉に必要なスワイプ距離(px)
const DRAWER_WIDTH = 256      // ドロワー幅(w-64 = 256px)

export default function Sidebar({ subtitle, children, dark, onLogoClick, mobileOpen, onMobileToggle }: SidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()

  // 管理ログインモーダル
  const [showLogin, setShowLogin] = useState(false)
  const [loginToken, setLoginToken] = useState('')
  const [loginError, setLoginError] = useState<string | null>(null)
  const [loginChecking, setLoginChecking] = useState(false)

  // スワイプ状態
  const [dragging, setDragging] = useState(false)
  const [dragX, setDragX] = useState(0)
  const touchRef = useRef<{ startX: number; startY: number; started: boolean; edgeSwipe: boolean }>({
    startX: 0, startY: 0, started: false, edgeSwipe: false,
  })

  function closeMobileDrawer() {
    if (mobileOpen) onMobileToggle?.()
  }

  function handleAdminClick() {
    if (hasAdminToken()) {
      closeMobileDrawer()
      navigate('/admin')
    } else {
      closeMobileDrawer()
      setShowLogin(true)
      setLoginToken('')
      setLoginError(null)
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoginChecking(true)
    setLoginError(null)
    setAdminToken(loginToken)
    try {
      await fetchAdminStats()
      setShowLogin(false)
      onMobileToggle?.()
      navigate('/admin')
    } catch (err) {
      clearAdminToken()
      const msg = err instanceof Error ? err.message : ''
      setLoginError(msg === '401' ? 'キーが正しくありません' : 'バックエンドに接続できません')
    } finally {
      setLoginChecking(false)
    }
  }

  // ── スワイプで開く: 画面左端からの右スワイプを検出 ──
  const handleTouchStart = useCallback((e: TouchEvent) => {
    // md以上（デスクトップ）では無効
    if (window.innerWidth >= 768) return
    const t = e.touches[0]
    const isEdge = t.clientX < EDGE_WIDTH
    touchRef.current = { startX: t.clientX, startY: t.clientY, started: false, edgeSwipe: isEdge }
  }, [])

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (window.innerWidth >= 768) return
    const ref = touchRef.current
    const t = e.touches[0]
    const dx = t.clientX - ref.startX
    const dy = t.clientY - ref.startY

    // まだドラッグ開始していない場合
    if (!ref.started) {
      // 縦スクロールの方が大きければ無視
      if (Math.abs(dy) > Math.abs(dx)) return
      // 横移動が10px超えたら開始判定
      if (Math.abs(dx) < 10) return

      if (mobileOpen) {
        // ドロワーが開いている → 左スワイプで閉じる
        if (dx < 0) {
          ref.started = true
          setDragging(true)
        }
      } else if (ref.edgeSwipe && dx > 0) {
        // ドロワーが閉じている → 左端から右スワイプで開く
        ref.started = true
        setDragging(true)
      }
      if (!ref.started) return
    }

    e.preventDefault()

    if (mobileOpen) {
      // 閉じ方向: 0 〜 -DRAWER_WIDTH
      setDragX(Math.max(-DRAWER_WIDTH, Math.min(0, dx)))
    } else {
      // 開き方向: 0 〜 DRAWER_WIDTH
      setDragX(Math.max(0, Math.min(DRAWER_WIDTH, dx)))
    }
  }, [mobileOpen])

  const handleTouchEnd = useCallback(() => {
    if (!touchRef.current.started) {
      setDragging(false)
      setDragX(0)
      return
    }

    if (mobileOpen) {
      // 閉じ方向: 十分にスワイプしたら閉じる
      if (dragX < -SWIPE_THRESHOLD) {
        onMobileToggle?.()
      }
    } else {
      // 開き方向: 十分にスワイプしたら開く
      if (dragX > SWIPE_THRESHOLD) {
        onMobileToggle?.()
      }
    }

    touchRef.current.started = false
    setDragging(false)
    setDragX(0)
  }, [mobileOpen, dragX, onMobileToggle])

  useEffect(() => {
    document.addEventListener('touchstart', handleTouchStart, { passive: true })
    document.addEventListener('touchmove', handleTouchMove, { passive: false })
    document.addEventListener('touchend', handleTouchEnd, { passive: true })
    return () => {
      document.removeEventListener('touchstart', handleTouchStart)
      document.removeEventListener('touchmove', handleTouchMove)
      document.removeEventListener('touchend', handleTouchEnd)
    }
  }, [handleTouchStart, handleTouchMove, handleTouchEnd])

  // ドラッグ中のドロワー位置を計算
  const drawerTranslateX = dragging
    ? mobileOpen
      ? dragX                              // 開いた状態から左へ
      : -DRAWER_WIDTH + dragX              // 閉じた状態から右へ
    : mobileOpen
      ? 0                                  // 完全に開いた位置
      : -DRAWER_WIDTH                      // 完全に閉じた位置

  const overlayOpacity = dragging
    ? mobileOpen
      ? Math.max(0, 1 + dragX / DRAWER_WIDTH)
      : Math.min(1, dragX / DRAWER_WIDTH)
    : mobileOpen ? 1 : 0

  const showDrawer = mobileOpen || dragging

  const sidebarContent = (
    <>
      {/* ロゴ */}
      <div
        className={`px-5 h-12 flex items-center justify-between border-b flex-shrink-0 ${dark ? 'border-[#1e1e1e]' : 'border-stone-100'}`}
      >
        <div
          className="cursor-pointer transition-opacity hover:opacity-80"
          onClick={() => { if (onLogoClick) onLogoClick(); onMobileToggle?.(); navigate('/') }}
        >
          <h1 className={`font-bold text-lg tracking-widest leading-none ${dark ? 'text-[#e8e4dc]' : 'text-stone-900'}`}>
            <span className="text-gold-500">P</span>OCUS
          </h1>
          {subtitle && (
            <p className={`text-xs mt-0.5 ${dark ? 'text-[#4a4540]' : 'text-stone-400'}`}>{subtitle}</p>
          )}
        </div>
        {/* モバイル閉じるボタン */}
        <button
          onClick={onMobileToggle}
          className={`md:hidden p-1 rounded-lg transition-colors ${dark ? 'text-[#5a5450] hover:text-[#e8e4dc]' : 'text-stone-400 hover:text-stone-700'}`}
        >
          <X size={18} />
        </button>
      </div>

      {/* ページ固有ナビ */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {children}
      </div>

      {/* 共通フッターナビ */}
      <div className={`p-2 border-t space-y-0.5 flex-shrink-0 ${dark ? 'border-[#1e1e1e]' : 'border-stone-100'}`}>
        <NavItem
          icon={<LayoutDashboard size={15} />}
          label="管理"
          active={location.pathname === '/admin'}
          onClick={handleAdminClick}
          dark={dark}
        />
      </div>
    </>
  )

  return (
    <>
      {/* デスクトップ: 固定サイドバー */}
      <aside className={`hidden md:flex w-48 flex-shrink-0 h-screen flex-col ${dark
          ? 'bg-[#0c0c0c] border-r border-[#1e1e1e]'
          : 'bg-white border-r border-stone-100'
        }`}>
        {sidebarContent}
      </aside>

      {/* モバイル: スワイプ対応ドロワー */}
      {showDrawer && (
        <div className="md:hidden fixed inset-0 z-40" style={{ pointerEvents: overlayOpacity > 0 ? 'auto' : 'none' }}>
          {/* 背景オーバーレイ */}
          <div
            className="absolute inset-0 bg-black"
            style={{ opacity: overlayOpacity * 0.5 }}
            onClick={onMobileToggle}
          />
          {/* ドロワー本体 */}
          <aside
            className={`absolute top-0 left-0 w-64 h-full flex flex-col shadow-xl ${dark
                ? 'bg-[#0c0c0c]'
                : 'bg-white'
              }`}
            style={{
              transform: `translateX(${drawerTranslateX}px)`,
              transition: dragging ? 'none' : 'transform 0.3s ease',
              willChange: 'transform',
            }}
          >
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* 管理ログインモーダル */}
      {showLogin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
             onClick={() => setShowLogin(false)}>
          <form
            onClick={e => e.stopPropagation()}
            onSubmit={handleLogin}
            className="bg-gray-900 rounded-xl p-8 w-80 flex flex-col gap-4 shadow-xl relative"
          >
            <button
              type="button"
              onClick={() => setShowLogin(false)}
              className="absolute top-3 right-3 text-gray-500 hover:text-gray-300 transition-colors"
            >
              <X size={16} />
            </button>
            <h2 className="text-white text-lg font-semibold text-center">Admin ログイン</h2>
            <input
              type="password"
              placeholder="シークレットキー"
              value={loginToken}
              onChange={e => setLoginToken(e.target.value)}
              className="bg-gray-800 text-white rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            {loginError && <p className="text-red-400 text-sm text-center">{loginError}</p>}
            <button
              type="submit"
              disabled={loginChecking || !loginToken}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg py-2 font-medium
                         flex items-center justify-center gap-2"
            >
              {loginChecking && <Loader2 size={14} className="animate-spin" />}
              {loginChecking ? '確認中...' : '入室'}
            </button>
          </form>
        </div>
      )}
    </>
  )
}

/** モバイル用ハンバーガーメニューボタン */
export function MobileMenuButton({ onClick, dark }: { onClick: () => void; dark?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`md:hidden fixed top-3 left-3 p-2 rounded-xl shadow-lg backdrop-blur-sm transition-colors ${dark
          ? 'bg-[#0c0c0c]/90 text-[#e8e4dc] border border-[#2a2a2a]'
          : 'bg-white/90 text-stone-700 border border-stone-200'
        }`}
      style={{ zIndex: 1100 }}
    >
      <Menu size={20} />
    </button>
  )
}

export { NavItem }
