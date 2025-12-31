'use client'

import { useState, useCallback } from 'react'
import { Plus, Trash2, Link, AlertCircle, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { isValidIdusUrl } from '@/lib/utils'

export interface BatchUrlItem {
  id: string
  url: string
  isValid: boolean
}

interface BatchUrlInputProps {
  onSubmit: (urls: string[]) => void
  isProcessing: boolean
  maxUrls?: number
}

export function BatchUrlInput({ onSubmit, isProcessing, maxUrls = 10 }: BatchUrlInputProps) {
  const [inputMode, setInputMode] = useState<'single' | 'bulk'>('single')
  const [urls, setUrls] = useState<BatchUrlItem[]>([
    { id: '1', url: '', isValid: false }
  ])
  const [bulkText, setBulkText] = useState('')

  // 단일 URL 추가
  const addUrl = useCallback(() => {
    if (urls.length >= maxUrls) return
    setUrls(prev => [
      ...prev,
      { id: Date.now().toString(), url: '', isValid: false }
    ])
  }, [urls.length, maxUrls])

  // URL 삭제
  const removeUrl = useCallback((id: string) => {
    if (urls.length <= 1) return
    setUrls(prev => prev.filter(item => item.id !== id))
  }, [urls.length])

  // URL 변경
  const updateUrl = useCallback((id: string, url: string) => {
    setUrls(prev => prev.map(item => 
      item.id === id 
        ? { ...item, url, isValid: isValidIdusUrl(url) }
        : item
    ))
  }, [])

  // 벌크 텍스트에서 URL 파싱
  const parseBulkUrls = useCallback((text: string): BatchUrlItem[] => {
    const lines = text.split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0)
      .slice(0, maxUrls)
    
    return lines.map((url, idx) => ({
      id: `bulk-${idx}`,
      url,
      isValid: isValidIdusUrl(url)
    }))
  }, [maxUrls])

  // 제출
  const handleSubmit = useCallback(() => {
    let validUrls: string[]
    
    if (inputMode === 'single') {
      validUrls = urls
        .filter(item => item.isValid)
        .map(item => item.url)
    } else {
      const parsedUrls = parseBulkUrls(bulkText)
      validUrls = parsedUrls
        .filter(item => item.isValid)
        .map(item => item.url)
    }
    
    if (validUrls.length === 0) return
    onSubmit(validUrls)
  }, [inputMode, urls, bulkText, parseBulkUrls, onSubmit])

  // 유효한 URL 개수
  const validCount = inputMode === 'single'
    ? urls.filter(item => item.isValid).length
    : parseBulkUrls(bulkText).filter(item => item.isValid).length

  const totalCount = inputMode === 'single'
    ? urls.filter(item => item.url.trim()).length
    : parseBulkUrls(bulkText).length

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Link className="w-5 h-5" />
            배치 번역
          </CardTitle>
          
          {/* 입력 모드 전환 */}
          <div className="flex gap-1 bg-muted p-1 rounded-lg">
            <button
              onClick={() => setInputMode('single')}
              className={cn(
                "px-3 py-1 text-sm rounded-md transition-colors",
                inputMode === 'single' 
                  ? "bg-background shadow-sm" 
                  : "hover:bg-background/50"
              )}
            >
              개별 입력
            </button>
            <button
              onClick={() => setInputMode('bulk')}
              className={cn(
                "px-3 py-1 text-sm rounded-md transition-colors",
                inputMode === 'bulk' 
                  ? "bg-background shadow-sm" 
                  : "hover:bg-background/50"
              )}
            >
              일괄 입력
            </button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {inputMode === 'single' ? (
          <>
            {/* 개별 URL 입력 */}
            <div className="space-y-2">
              {urls.map((item, idx) => (
                <div key={item.id} className="flex gap-2">
                  <div className="flex-1 relative">
                    <Input
                      value={item.url}
                      onChange={(e) => updateUrl(item.id, e.target.value)}
                      placeholder={`https://www.idus.com/v2/product/...`}
                      className={cn(
                        "pr-8",
                        item.url && !item.isValid && "border-red-300 focus:border-red-500"
                      )}
                      disabled={isProcessing}
                    />
                    {item.url && (
                      <span className={cn(
                        "absolute right-3 top-1/2 -translate-y-1/2 text-xs",
                        item.isValid ? "text-green-500" : "text-red-500"
                      )}>
                        {item.isValid ? '✓' : '✗'}
                      </span>
                    )}
                  </div>
                  
                  {urls.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeUrl(item.id)}
                      disabled={isProcessing}
                      className="shrink-0"
                    >
                      <Trash2 className="w-4 h-4 text-muted-foreground" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
            
            {/* URL 추가 버튼 */}
            {urls.length < maxUrls && (
              <Button
                variant="outline"
                size="sm"
                onClick={addUrl}
                disabled={isProcessing}
                className="w-full"
              >
                <Plus className="w-4 h-4 mr-2" />
                URL 추가 ({urls.length}/{maxUrls})
              </Button>
            )}
          </>
        ) : (
          <>
            {/* 일괄 입력 */}
            <div className="space-y-2">
              <Label>URL 목록 (줄바꿈으로 구분)</Label>
              <Textarea
                value={bulkText}
                onChange={(e) => setBulkText(e.target.value)}
                placeholder={`https://www.idus.com/v2/product/12345678\nhttps://www.idus.com/v2/product/87654321\n...`}
                rows={6}
                disabled={isProcessing}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                최대 {maxUrls}개의 URL을 한 번에 처리할 수 있습니다.
              </p>
            </div>
          </>
        )}
        
        {/* 상태 표시 */}
        {totalCount > 0 && (
          <div className={cn(
            "flex items-center gap-2 p-3 rounded-lg text-sm",
            validCount === totalCount 
              ? "bg-green-50 text-green-700" 
              : "bg-yellow-50 text-yellow-700"
          )}>
            <AlertCircle className="w-4 h-4" />
            <span>
              {validCount === totalCount 
                ? `${validCount}개 URL 준비 완료`
                : `${totalCount}개 중 ${validCount}개 유효 (${totalCount - validCount}개 오류)`
              }
            </span>
          </div>
        )}
        
        {/* 제출 버튼 */}
        <Button
          onClick={handleSubmit}
          disabled={validCount === 0 || isProcessing}
          className="w-full"
          size="lg"
        >
          {isProcessing ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              처리 중...
            </>
          ) : (
            <>
              배치 번역 시작 ({validCount}개)
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  )
}
