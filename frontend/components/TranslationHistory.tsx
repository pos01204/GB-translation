'use client'

import { useState, useEffect, useCallback } from 'react'
import { History, Trash2, ExternalLink, Clock, Globe, ChevronRight, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { toast } from '@/components/ui/toaster'
import {
  getTranslationHistory,
  deleteHistoryItem,
  clearAllHistory,
  formatTimestamp,
  type TranslationHistoryItem,
} from '@/lib/storage'
import { getLanguageDisplayName } from '@/lib/utils'
import type { ProductData, TranslatedProduct } from '@/lib/api'

interface TranslationHistoryProps {
  onLoadHistory: (original: ProductData, translated: TranslatedProduct) => void
  currentUrl?: string
}

export function TranslationHistory({ onLoadHistory, currentUrl }: TranslationHistoryProps) {
  const [history, setHistory] = useState<TranslationHistoryItem[]>([])
  const [isExpanded, setIsExpanded] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  // 히스토리 로드
  useEffect(() => {
    setHistory(getTranslationHistory())
    setIsLoading(false)
  }, [])

  // 히스토리 항목 삭제
  const handleDelete = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    if (deleteHistoryItem(id)) {
      setHistory(prev => prev.filter(item => item.id !== id))
      toast({
        title: '삭제 완료',
        description: '히스토리 항목이 삭제되었습니다.',
      })
    }
  }, [])

  // 전체 삭제
  const handleClearAll = useCallback(() => {
    if (window.confirm('모든 번역 히스토리를 삭제하시겠습니까?')) {
      if (clearAllHistory()) {
        setHistory([])
        toast({
          title: '전체 삭제 완료',
          description: '모든 히스토리가 삭제되었습니다.',
        })
      }
    }
  }, [])

  // 히스토리 항목 로드
  const handleLoad = useCallback((item: TranslationHistoryItem) => {
    onLoadHistory(item.originalData, item.translatedData)
    toast({
      title: '불러오기 완료',
      description: `"${item.productTitle.slice(0, 30)}..." 번역 결과를 불러왔습니다.`,
    })
  }, [onLoadHistory])

  if (isLoading) {
    return null
  }

  if (history.length === 0) {
    return null
  }

  return (
    <Card className="mb-6">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-2 hover:text-primary transition-colors"
          >
            <History className="w-4 h-4" />
            <CardTitle className="text-base">최근 번역 히스토리</CardTitle>
            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
              {history.length}
            </span>
            <ChevronRight 
              className={cn(
                "w-4 h-4 transition-transform",
                isExpanded && "rotate-90"
              )} 
            />
          </button>
          
          {isExpanded && history.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={handleClearAll}
            >
              <Trash2 className="w-3 h-3 mr-1" />
              전체 삭제
            </Button>
          )}
        </div>
      </CardHeader>
      
      {isExpanded && (
        <CardContent className="pt-0">
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {history.map((item) => (
              <div
                key={item.id}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors",
                  "hover:bg-muted/80 border border-transparent",
                  currentUrl === item.url && "border-primary/30 bg-primary/5"
                )}
                onClick={() => handleLoad(item)}
              >
                {/* 언어 아이콘 */}
                <div className="shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Globe className="w-4 h-4 text-primary" />
                </div>
                
                {/* 정보 */}
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">
                    {item.productTitle}
                  </p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{getLanguageDisplayName(item.targetLanguage)}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTimestamp(item.timestamp)}
                    </span>
                  </div>
                </div>
                
                {/* 액션 버튼 */}
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={(e) => {
                      e.stopPropagation()
                      window.open(item.url, '_blank')
                    }}
                  >
                    <ExternalLink className="w-3 h-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive hover:text-destructive"
                    onClick={(e) => handleDelete(item.id, e)}
                  >
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
          
          <p className="text-xs text-muted-foreground mt-3 text-center">
            최근 {history.length}개의 번역 기록 (최대 20개 저장)
          </p>
        </CardContent>
      )}
    </Card>
  )
}
