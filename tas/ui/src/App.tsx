import { Component, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import HomePage from './pages/HomePage'
import VenueDetailPage from './pages/VenueDetailPage'
import AdminDashboardPage from './pages/AdminDashboardPage'

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen bg-stone-50 gap-4">
          <p className="text-lg font-bold text-stone-700">予期しないエラーが発生しました</p>
          <button
            onClick={() => { this.setState({ hasError: false }); window.location.href = '/' }}
            className="text-sm text-gold-500 hover:underline"
          >
            トップに戻る
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center h-screen bg-stone-50 gap-4">
      <p className="text-6xl font-bold text-stone-200">404</p>
      <p className="text-sm text-stone-500">ページが見つかりませんでした</p>
      <Link to="/" className="text-sm text-gold-500 hover:underline">トップに戻る</Link>
    </div>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/venues/:id" element={<VenueDetailPage />} />
          <Route path="/admin" element={<AdminDashboardPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
