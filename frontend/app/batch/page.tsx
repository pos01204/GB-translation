'use client'

import { useState, useCallback } from 'react'
import { ArrowLeft, Package } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toaster'

import { BatchUrlInput } from '@/components/BatchUrlInput'
import { BatchProgress, type BatchItem, type BatchItemStatus } from '@/components/BatchProgress'
import { BatchResults, type BatchResultItem } from '@/components/BatchResults'

import { 
  batchTranslate,
  type TargetLanguage,
  type ProductData,
  type TranslatedProduct,
} from '@/lib/api'
import { saveTranslationHistory } from '@/lib/storage'

type BatchStatus = 'input' | 'processing' | 'completed'

export default function BatchPage() {
  const [status, setStatus] = useState<BatchStatus>('input')
  const [targetLanguage, setTargetLanguage] = useState<TargetLanguage>('en')
  const [progressItems, setProgressItems] = useState<BatchItem[]>([])
  const [results, setResults] = useState<BatchResultItem[]>([])
  const [isCancelled, setIsCancelled] = useState(false)

  // 배치 처리 시작
  const handleSubmit = useCallback(async (urls: string[]) => {
    setStatus('processing')
    setIsCancelled(false)
    setResults([])
    
    // 진행 상태 초기화
    const initialItems: BatchItem[] = urls.map((url, idx) => ({
      id: `batch-${idx}`,
      url,
      status: 'pending' as BatchItemStatus,
    }))
    setProgressItems(initialItems)

    try {
      // 첫 번째 항목을 처리 중으로 표시
      setProgressItems(prev => prev.map((item, idx) => 
        idx === 0 ? { ...item, status: 'scraping' } : item
      ))

      // 배치 API 호출
      const response = await batchTranslate(urls, targetLanguage)
      
      if (isCancelled) return

      // 결과 처리
      const successResults: BatchResultItem[] = []
      const updatedItems: BatchItem[] = []

      response.results.forEach((result, idx) => {
        if (result.success && result.data && result.original_data) {
          successResults.push({
            id: `result-${idx}`,
            url: result.url,
            originalData: result.original_data,
            translatedData: result.data,
          })
          
          // 히스토리에 저장
          saveTranslationHistory(result.original_data, result.data)
          
          updatedItems.push({
            id: `batch-${idx}`,
            url: result.url,
            status: 'completed',
            productTitle: result.original_data.title,
          })
        } else {
          updatedItems.push({
            id: `batch-${idx}`,
            url: result.url,
            status: 'error',
            error: result.message,
          })
        }
      })

      setProgressItems(updatedItems)
      setResults(successResults)
      setStatus('completed')

      toast({
        title: '배치 처리 완료',
        description: `${response.success_count}개 성공, ${response.failed_count}개 실패`,
        variant: response.failed_count > 0 ? 'default' : 'success',
      })

    } catch (error) {
      console.error('Batch error:', error)
      
      // 모든 항목을 에러로 표시
      setProgressItems(prev => prev.map(item => ({
        ...item,
        status: 'error' as BatchItemStatus,
        error: error instanceof Error ? error.message : '알 수 없는 오류',
      })))

      toast({
        title: '배치 처리 실패',
        description: error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.',
        variant: 'destructive',
      })
    }
  }, [targetLanguage, isCancelled])

  // 처리 취소
  const handleCancel = useCallback(() => {
    setIsCancelled(true)
    toast({
      title: '처리 취소됨',
      description: '배치 처리가 취소되었습니다.',
    })
  }, [])

  // 재시도
  const handleRetry = useCallback((id: string) => {
    const item = progressItems.find(i => i.id === id)
    if (!item) return
    
    // 단일 URL로 다시 처리
    handleSubmit([item.url])
  }, [progressItems, handleSubmit])

  // 상세 보기 (단일 결과 페이지로 이동)
  const handleViewDetail = useCallback((item: BatchResultItem) => {
    // 결과를 세션 스토리지에 저장하고 메인 페이지로 이동
    sessionStorage.setItem('batchDetailItem', JSON.stringify(item))
    window.location.href = '/?fromBatch=true'
  }, [])

  // 리셋
  const handleReset = useCallback(() => {
    setStatus('input')
    setProgressItems([])
    setResults([])
    setIsCancelled(false)
  }, [])

  return (
    <div className="container mx-auto max-w-4xl px-4 py-8">
      {/* 헤더 */}
      <div className="flex items-center gap-4 mb-8">
        <Link href="/">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Package className="w-6 h-6" />
            배치 번역
          </h1>
          <p className="text-sm text-muted-foreground">
            여러 상품을 한 번에 번역합니다 (최대 10개)
          </p>
        </div>
      </div>

      {/* 언어 선택 */}
      {status === 'input' && (
        <div className="mb-6">
          <label className="text-sm font-medium mb-2 block">번역 언어</label>
          <div className="flex gap-2">
            <Button
              variant={targetLanguage === 'en' ? 'default' : 'outline'}
              onClick={() => setTargetLanguage('en')}
            >
              🇺🇸 English
            </Button>
            <Button
              variant={targetLanguage === 'ja' ? 'default' : 'outline'}
              onClick={() => setTargetLanguage('ja')}
            >
              🇯🇵 日本語
            </Button>
          </div>
        </div>
      )}

      {/* 입력 상태 */}
      {status === 'input' && (
        <BatchUrlInput
          onSubmit={handleSubmit}
          isProcessing={false}
          maxUrls={10}
        />
      )}

      {/* 처리 중 상태 */}
      {status === 'processing' && (
        <BatchProgress
          items={progressItems}
          onCancel={handleCancel}
          onRetry={handleRetry}
        />
      )}

      {/* 완료 상태 */}
      {status === 'completed' && (
        <div className="space-y-6">
          {/* 진행 상황 요약 */}
          <BatchProgress
            items={progressItems}
            onRetry={handleRetry}
          />
          
          {/* 성공한 결과 */}
          {results.length > 0 && (
            <BatchResults
              results={results}
              onViewDetail={handleViewDetail}
              onReset={handleReset}
            />
          )}
          
          {/* 결과가 없을 때 */}
          {results.length === 0 && (
            <div className="text-center py-12">
              <p className="text-muted-foreground mb-4">
                성공적으로 처리된 항목이 없습니다.
              </p>
              <Button onClick={handleReset}>
                다시 시도
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
