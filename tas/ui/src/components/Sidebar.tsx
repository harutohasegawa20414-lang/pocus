import { useState } from 'react'
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

export default function Sidebar({ subtitle, children, dark, onLogoClick, mobileOpen, onMobileToggle }: SidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()

  // 管理ログインモーダル
  const [showLogin, setShowLogin] = useState(false)
  const [loginToken, setLoginToken] = useState('')
  const [loginError, setLoginError] = useState<string | null>(null)
  const [loginChecking, setLoginChecking] = useState(false)

  function handleAdminClick() {
    if (hasAdminToken()) {
      onMobileToggle?.()
      navigate('/admin')
    } else {
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

      {/* モバイル: オーバーレイドロワー */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          {/* 背景オーバーレイ */}
          <div className="absolute inset-0 bg-black/50" onClick={onMobileToggle} />
          {/* ドロワー */}
          <aside className={`relative w-64 h-full flex flex-col shadow-xl ${dark
              ? 'bg-[#0c0c0c]'
              : 'bg-white'
            }`}>
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* 管理ログインモーダル */}
      {showLogin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <form
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
      className={`md:hidden fixed top-3 left-3 z-30 p-2 rounded-xl shadow-lg backdrop-blur-sm transition-colors ${dark
          ? 'bg-[#0c0c0c]/90 text-[#e8e4dc] border border-[#2a2a2a]'
          : 'bg-white/90 text-stone-700 border border-stone-200'
        }`}
    >
      <Menu size={20} />
    </button>
  )
}

export { NavItem }
