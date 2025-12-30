'use client'

import { useState } from 'react'
import { Search, Globe, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { isValidIdusUrl } from '@/lib/utils'
import type { TargetLanguage } from '@/lib/api'

interface UrlInputFormProps {
  onSubmit: (url: string, language: TargetLanguage) => void
  isLoading: boolean
  disabled?: boolean
}

export function UrlInputForm({ onSubmit, isLoading, disabled }: UrlInputFormProps) {
  const [url, setUrl] = useState('')
  const [language, setLanguage] = useState<TargetLanguage>('en')
  const [error, setError] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!url.trim()) {
      setError('URL을 입력해주세요.')
      return
    }

    if (!isValidIdusUrl(url)) {
      setError('유효한 아이디어스 URL이 아닙니다. (예: https://www.idus.com/v2/product/...)')
      return
    }

    onSubmit(url.trim(), language)
  }

  return (
    <Card className="border-2 border-dashed border-primary/20 hover:border-primary/40 transition-colors">
      <CardContent className="pt-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* URL 입력 */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground flex items-center gap-2">
              <Search className="w-4 h-4 text-primary" />
              아이디어스 상품 URL
            </label>
            <div className="relative">
              <Input
                type="url"
                placeholder="https://www.idus.com/v2/product/12345678"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value)
                  setError('')
                }}
                disabled={disabled || isLoading}
                className="pr-4 h-12 text-base"
              />
            </div>
            {error && (
              <p className="text-sm text-destructive animate-fade-in">{error}</p>
            )}
          </div>

          {/* 언어 선택 */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground flex items-center gap-2">
              <Globe className="w-4 h-4 text-primary" />
              번역 언어 선택
            </label>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setLanguage('en')}
                disabled={disabled || isLoading}
                className={`
                  flex-1 py-3 px-4 rounded-lg border-2 transition-all duration-200
                  flex items-center justify-center gap-2 font-medium
                  ${language === 'en'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/50 text-muted-foreground hover:text-foreground'
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed
                `}
              >
                <span className="text-xl">🇺🇸</span>
                <span>English</span>
              </button>
              <button
                type="button"
                onClick={() => setLanguage('ja')}
                disabled={disabled || isLoading}
                className={`
                  flex-1 py-3 px-4 rounded-lg border-2 transition-all duration-200
                  flex items-center justify-center gap-2 font-medium
                  ${language === 'ja'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/50 text-muted-foreground hover:text-foreground'
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed
                `}
              >
                <span className="text-xl">🇯🇵</span>
                <span>日本語</span>
              </button>
            </div>
          </div>

          {/* 제출 버튼 */}
          <Button
            type="submit"
            size="lg"
            disabled={disabled || isLoading || !url.trim()}
            className="w-full h-12 text-base font-semibold"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                <span>번역 중</span>
                <span className="loading-dots"></span>
              </>
            ) : (
              <>
                <Search className="w-5 h-5 mr-2" />
                크롤링 & 번역 시작
              </>
            )}
          </Button>
        </form>

        {/* 안내 텍스트 */}
        <div className="mt-4 pt-4 border-t border-border">
          <p className="text-xs text-muted-foreground text-center">
            💡 아이디어스 상품 페이지 URL을 입력하면 상품 정보와 이미지 내 텍스트를 자동으로 추출하여 번역합니다.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

