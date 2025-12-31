'use client'

import { useMemo } from 'react'
import { CheckCircle, XCircle, Loader2, Clock, AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type BatchItemStatus = 'pending' | 'scraping' | 'translating' | 'completed' | 'error'

export interface BatchItem {
  id: string
  url: string
  status: BatchItemStatus
  productTitle?: string
  error?: string
  progress?: number
}

interface BatchProgressProps {
  items: BatchItem[]
  onCancel?: () => void
  onRetry?: (id: string) => void
}

function StatusIcon({ status }: { status: BatchItemStatus }) {
  switch (status) {
    case 'pending':
      return <Clock className="w-4 h-4 text-muted-foreground" />
    case 'scraping':
    case 'translating':
      return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
    case 'completed':
      return <CheckCircle className="w-4 h-4 text-green-500" />
    case 'error':
      return <XCircle className="w-4 h-4 text-red-500" />
    default:
      return null
  }
}

function StatusText({ status }: { status: BatchItemStatus }) {
  switch (status) {
    case 'pending':
      return <span className="text-muted-foreground">대기 중</span>
    case 'scraping':
      return <span className="text-blue-500">크롤링 중...</span>
    case 'translating':
      return <span className="text-blue-500">번역 중...</span>
    case 'completed':
      return <span className="text-green-500">완료</span>
    case 'error':
      return <span className="text-red-500">오류</span>
    default:
      return null
  }
}

export function BatchProgress({ items, onCancel, onRetry }: BatchProgressProps) {
  const stats = useMemo(() => {
    const completed = items.filter(i => i.status === 'completed').length
    const errors = items.filter(i => i.status === 'error').length
    const pending = items.filter(i => i.status === 'pending').length
    const processing = items.filter(i => 
      i.status === 'scraping' || i.status === 'translating'
    ).length
    
    return { completed, errors, pending, processing, total: items.length }
  }, [items])

  const progress = Math.round(
    ((stats.completed + stats.errors) / stats.total) * 100
  )

  const isProcessing = stats.processing > 0 || stats.pending > 0

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">배치 처리 현황</CardTitle>
          
          {isProcessing && onCancel && (
            <Button variant="outline" size="sm" onClick={onCancel}>
              취소
            </Button>
          )}
        </div>
        
        {/* 진행률 바 */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              {stats.completed + stats.errors} / {stats.total} 완료
            </span>
            <span className="font-medium">{progress}%</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div 
              className={cn(
                "h-full transition-all duration-300",
                stats.errors > 0 ? "bg-yellow-500" : "bg-green-500"
              )}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
        
        {/* 통계 */}
        <div className="flex gap-4 text-sm mt-2">
          <span className="flex items-center gap-1">
            <CheckCircle className="w-3 h-3 text-green-500" />
            성공: {stats.completed}
          </span>
          {stats.errors > 0 && (
            <span className="flex items-center gap-1">
              <XCircle className="w-3 h-3 text-red-500" />
              실패: {stats.errors}
            </span>
          )}
          {isProcessing && (
            <span className="flex items-center gap-1">
              <Loader2 className="w-3 h-3 text-blue-500 animate-spin" />
              처리 중: {stats.processing}
            </span>
          )}
        </div>
      </CardHeader>
      
      <CardContent>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {items.map((item, idx) => (
            <div
              key={item.id}
              className={cn(
                "flex items-center gap-3 p-3 rounded-lg border",
                item.status === 'completed' && "bg-green-50/50 border-green-200",
                item.status === 'error' && "bg-red-50/50 border-red-200",
                (item.status === 'scraping' || item.status === 'translating') && 
                  "bg-blue-50/50 border-blue-200",
                item.status === 'pending' && "bg-muted/30"
              )}
            >
              {/* 순번 */}
              <span className="shrink-0 w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                {idx + 1}
              </span>
              
              {/* 상태 아이콘 */}
              <StatusIcon status={item.status} />
              
              {/* 정보 */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {item.productTitle || item.url}
                </p>
                {item.error && (
                  <p className="text-xs text-red-500 truncate">
                    {item.error}
                  </p>
                )}
                {!item.productTitle && !item.error && (
                  <p className="text-xs text-muted-foreground truncate">
                    {item.url}
                  </p>
                )}
              </div>
              
              {/* 상태 텍스트 */}
              <div className="shrink-0 text-xs">
                <StatusText status={item.status} />
              </div>
              
              {/* 재시도 버튼 */}
              {item.status === 'error' && onRetry && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onRetry(item.id)}
                  className="shrink-0"
                >
                  재시도
                </Button>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
