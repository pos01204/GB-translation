import type { Metadata } from 'next'
import './globals.css'
import { Toaster } from '@/components/ui/toaster'

export const metadata: Metadata = {
  title: '글로벌 작품 등록 서비스',
  description: '아이디어스 핸드메이드 작품을 글로벌 마켓에 자동 등록하세요. AI 기반 번역과 Playwright 자동화로 간편하게 등록합니다.',
  keywords: ['아이디어스', 'idus', '글로벌', '핸드메이드', '등록', '자동화'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-background antialiased">
        <div className="relative flex min-h-screen flex-col">
          {/* 헤더 */}
          <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex h-16 items-center justify-between px-4 mx-auto max-w-7xl">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-idus-orange to-idus-coral flex items-center justify-center">
                  <span className="text-white font-bold text-sm">ID</span>
                </div>
                <span className="font-bold text-xl">
                  <span className="gradient-text">글로벌</span>
                  <span className="text-foreground"> 작품 등록</span>
                </span>
              </div>
            </div>
          </header>

          {/* 메인 콘텐츠 */}
          <main className="flex-1">
            {children}
          </main>

          {/* 푸터 */}
          <footer className="border-t py-6 md:py-0">
            <div className="container flex flex-col items-center justify-between gap-4 md:h-16 md:flex-row px-4 mx-auto max-w-7xl">
              <p className="text-sm text-muted-foreground">
                © 2024 Idus Translator. 글로벌 비즈니스 자동화 도구.
              </p>
              <p className="text-xs text-muted-foreground">
                Powered by Claude AI & Playwright
              </p>
            </div>
          </footer>
        </div>
        <Toaster />
      </body>
    </html>
  )
}

