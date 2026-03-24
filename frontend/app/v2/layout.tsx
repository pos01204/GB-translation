'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect } from 'react'
import { getSessionStatus, logoutArtistWeb, type SessionStatus } from '@/lib/api-v2'
import {
  LayoutDashboard,
  Globe,
  LogOut,
  ChevronLeft,
  Menu,
  User,
} from 'lucide-react'

export default function V2Layout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const [session, setSession] = useState<SessionStatus | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  useEffect(() => {
    getSessionStatus()
      .then(setSession)
      .catch(() => setSession({ authenticated: false }))
  }, [pathname])

  const handleLogout = async () => {
    await logoutArtistWeb()
    setSession({ authenticated: false })
    window.location.href = '/v2'
  }

  const navItems = [
    {
      href: '/v2',
      label: '대시보드',
      icon: LayoutDashboard,
      active: pathname === '/v2',
    },
    {
      href: '/v2/register',
      label: 'GB 등록 현황',
      icon: Globe,
      active: pathname === '/v2/register',
    },
  ]

  return (
    <div className="flex h-[calc(100vh-4rem-4.5rem)] overflow-hidden">
      {/* 사이드바 */}
      <aside
        className={`${
          sidebarOpen ? 'w-60' : 'w-16'
        } transition-all duration-200 border-r bg-gray-50/50 flex flex-col shrink-0`}
      >
        {/* 사이드바 토글 */}
        <div className="flex items-center justify-between p-3 border-b">
          {sidebarOpen && (
            <span className="text-sm font-semibold text-gray-700">
              v2 글로벌 등록
            </span>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-md hover:bg-gray-200 transition-colors"
            title={sidebarOpen ? '사이드바 접기' : '사이드바 펼치기'}
          >
            {sidebarOpen ? (
              <ChevronLeft className="w-4 h-4" />
            ) : (
              <Menu className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 py-2">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 mx-2 rounded-md text-sm transition-colors ${
                item.active
                  ? 'bg-orange-50 text-orange-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`}
              title={item.label}
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {sidebarOpen && <span>{item.label}</span>}
            </Link>
          ))}
        </nav>

        {/* 세션 정보 */}
        {session?.authenticated && (
          <div className="border-t p-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-orange-100 flex items-center justify-center shrink-0">
                <User className="w-3.5 h-3.5 text-orange-600" />
              </div>
              {sidebarOpen && (
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-500 truncate">
                    작가웹 연결됨
                  </p>
                  <button
                    onClick={handleLogout}
                    className="text-xs text-red-500 hover:text-red-700 flex items-center gap-1 mt-0.5"
                  >
                    <LogOut className="w-3 h-3" />
                    로그아웃
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </aside>

      {/* 메인 콘텐츠 */}
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  )
}
