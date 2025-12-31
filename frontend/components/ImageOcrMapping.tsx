'use client'

import { useState, useMemo, useCallback } from 'react'
import { Copy, Check, ChevronLeft, ChevronRight, Edit3, X } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { toast } from '@/components/ui/toaster'
import type { ImageText } from '@/lib/api'

interface ImageOcrMappingProps {
  images: string[]
  ocrResults: ImageText[]
  onCopyText?: (text: string) => void
  onEditOcr?: (index: number, newText: string) => void
}

export function ImageOcrMapping({ images, ocrResults, onCopyText, onEditOcr }: ImageOcrMappingProps) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [imageLoadError, setImageLoadError] = useState<Set<number>>(new Set())
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editedText, setEditedText] = useState('')

  // OCR 결과를 이미지 URL로 매핑 (순서 정보 포함)
  const ocrMap = useMemo(() => {
    const map = new Map<string, ImageText & { displayOrder: number }>()
    
    // 순서대로 정렬
    const sortedResults = [...ocrResults].sort((a, b) => {
      const orderA = a.order_index ?? 999
      const orderB = b.order_index ?? 999
      return orderA - orderB
    })
    
    sortedResults.forEach((ocr, idx) => {
      map.set(ocr.image_url, { ...ocr, displayOrder: idx + 1 })
    })
    
    return map
  }, [ocrResults])

  // OCR이 있는 이미지만 필터링
  const imagesWithOcr = useMemo(() => {
    return images.filter(url => ocrMap.has(url))
  }, [images, ocrMap])

  // 현재 선택된 이미지의 OCR 정보
  const currentOcr = useMemo(() => {
    if (selectedIndex >= 0 && selectedIndex < images.length) {
      return ocrMap.get(images[selectedIndex])
    }
    return null
  }, [selectedIndex, images, ocrMap])

  // 복사 핸들러
  const handleCopy = useCallback(async (text: string | null | undefined, index: number) => {
    if (!text) return
    
    try {
      await navigator.clipboard.writeText(text)
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
      
      toast({
        title: '복사 완료',
        description: '텍스트가 클립보드에 복사되었습니다.',
      })
      
      onCopyText?.(text)
    } catch (err) {
      toast({
        title: '복사 실패',
        description: '클립보드 복사에 실패했습니다.',
        variant: 'destructive',
      })
    }
  }, [onCopyText])

  // 이전/다음 이미지 네비게이션
  const goToPrevious = useCallback(() => {
    setSelectedIndex(prev => Math.max(0, prev - 1))
  }, [])

  const goToNext = useCallback(() => {
    setSelectedIndex(prev => Math.min(images.length - 1, prev + 1))
  }, [images.length])

  // 이미지 로드 에러 핸들러
  const handleImageError = useCallback((index: number) => {
    setImageLoadError(prev => new Set(prev).add(index))
  }, [])

  // 편집 시작
  const startEditing = useCallback((ocrIndex: number, currentText: string) => {
    setEditingIndex(ocrIndex)
    setEditedText(currentText || '')
  }, [])

  // 편집 저장
  const saveEdit = useCallback(() => {
    if (editingIndex !== null && onEditOcr) {
      onEditOcr(editingIndex, editedText)
      toast({
        title: '저장 완료',
        description: '번역 텍스트가 수정되었습니다.',
      })
    }
    setEditingIndex(null)
    setEditedText('')
  }, [editingIndex, editedText, onEditOcr])

  // 편집 취소
  const cancelEdit = useCallback(() => {
    setEditingIndex(null)
    setEditedText('')
  }, [])

  if (images.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">이미지가 없습니다.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* 상단 통계 */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          전체 이미지: <strong className="text-foreground">{images.length}</strong>개 | 
          OCR 추출: <strong className="text-green-600">{ocrResults.length}</strong>개
        </span>
        <span>
          {selectedIndex + 1} / {images.length}
        </span>
      </div>

      {/* 썸네일 스트립 */}
      <div className="relative">
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-muted">
          {images.map((url, idx) => {
            const hasOcr = ocrMap.has(url)
            const ocrInfo = ocrMap.get(url)
            
            return (
              <button
                key={`${url}-${idx}`}
                onClick={() => setSelectedIndex(idx)}
                className={cn(
                  "relative shrink-0 w-16 h-16 md:w-20 md:h-20 rounded border-2 overflow-hidden transition-all",
                  selectedIndex === idx 
                    ? "border-primary ring-2 ring-primary/30" 
                    : "border-transparent hover:border-muted-foreground/30",
                  hasOcr && "ring-2 ring-green-500/50"
                )}
              >
                {!imageLoadError.has(idx) ? (
                  <img 
                    src={url} 
                    alt={`이미지 ${idx + 1}`}
                    className="object-cover w-full h-full"
                    onError={() => handleImageError(idx)}
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full bg-muted flex items-center justify-center">
                    <span className="text-xs text-muted-foreground">로드 실패</span>
                  </div>
                )}
                
                {/* 순서 번호 */}
                <span className="absolute top-0.5 left-0.5 bg-black/70 text-white text-[10px] px-1 rounded">
                  {idx + 1}
                </span>
                
                {/* OCR 표시 */}
                {hasOcr && (
                  <span className="absolute bottom-0.5 right-0.5 bg-green-500 text-white text-[10px] px-1 rounded">
                    OCR {ocrInfo?.displayOrder}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* 메인 뷰: 선택된 이미지 + OCR 결과 */}
      <Card>
        <CardContent className="p-4">
          <div className="grid md:grid-cols-2 gap-4">
            {/* 이미지 영역 */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">이미지 {selectedIndex + 1}</Label>
                <div className="flex gap-1">
                  <Button 
                    variant="outline" 
                    size="icon" 
                    className="h-7 w-7"
                    onClick={goToPrevious}
                    disabled={selectedIndex === 0}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <Button 
                    variant="outline" 
                    size="icon" 
                    className="h-7 w-7"
                    onClick={goToNext}
                    disabled={selectedIndex === images.length - 1}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
              
              <div className="relative bg-muted rounded-lg overflow-hidden">
                {!imageLoadError.has(selectedIndex) ? (
                  <img 
                    src={images[selectedIndex]} 
                    alt={`이미지 ${selectedIndex + 1}`}
                    className="w-full h-auto max-h-[400px] object-contain"
                    onError={() => handleImageError(selectedIndex)}
                  />
                ) : (
                  <div className="w-full h-48 flex items-center justify-center">
                    <span className="text-muted-foreground">이미지를 불러올 수 없습니다</span>
                  </div>
                )}
                
                {/* OCR 여부 배지 */}
                {currentOcr && (
                  <div className="absolute top-2 right-2 bg-green-500 text-white text-xs px-2 py-1 rounded-full">
                    OCR #{currentOcr.displayOrder}
                  </div>
                )}
              </div>
            </div>
            
            {/* OCR 결과 영역 */}
            <div className="space-y-3">
              {currentOcr ? (
                <>
                  {/* 원문 */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <Label className="text-sm font-medium">원문 (한국어)</Label>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2"
                        onClick={() => handleCopy(currentOcr.original_text, selectedIndex * 2)}
                      >
                        {copiedIndex === selectedIndex * 2 ? (
                          <Check className="w-3 h-3 mr-1 text-green-500" />
                        ) : (
                          <Copy className="w-3 h-3 mr-1" />
                        )}
                        복사
                      </Button>
                    </div>
                    <div className="bg-muted p-3 rounded-lg text-sm max-h-32 overflow-y-auto">
                      {currentOcr.original_text}
                    </div>
                  </div>
                  
                  {/* 번역 - 인라인 편집 지원 */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <Label className="text-sm font-medium">번역</Label>
                      <div className="flex items-center gap-1">
                        {editingIndex !== selectedIndex && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2"
                              onClick={() => startEditing(selectedIndex, currentOcr.translated_text || '')}
                            >
                              <Edit3 className="w-3 h-3 mr-1" />
                              편집
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2"
                              onClick={() => handleCopy(currentOcr.translated_text, selectedIndex * 2 + 1)}
                            >
                              {copiedIndex === selectedIndex * 2 + 1 ? (
                                <Check className="w-3 h-3 mr-1 text-green-500" />
                              ) : (
                                <Copy className="w-3 h-3 mr-1" />
                              )}
                              복사
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                    
                    {editingIndex === selectedIndex ? (
                      <div className="space-y-2">
                        <Textarea
                          value={editedText}
                          onChange={(e) => setEditedText(e.target.value)}
                          className="min-h-[100px] border-primary text-sm"
                          autoFocus
                        />
                        <div className="flex gap-2 justify-end">
                          <Button variant="ghost" size="sm" onClick={cancelEdit}>
                            <X className="w-3 h-3 mr-1" /> 취소
                          </Button>
                          <Button size="sm" onClick={saveEdit}>
                            <Check className="w-3 h-3 mr-1" /> 저장
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div 
                        className="bg-primary/10 p-3 rounded-lg text-sm max-h-32 overflow-y-auto cursor-pointer hover:bg-primary/15 transition-colors"
                        onClick={() => startEditing(selectedIndex, currentOcr.translated_text || '')}
                      >
                        {currentOcr.translated_text || '번역 결과 없음'}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="h-full flex items-center justify-center text-center py-12">
                  <div className="space-y-2">
                    <div className="text-4xl">📷</div>
                    <p className="text-muted-foreground">
                      이 이미지에서 추출된 텍스트가 없습니다.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      OCR이 있는 이미지: {imagesWithOcr.length}개
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* OCR 결과 요약 리스트 */}
      {ocrResults.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium mb-3 block">
              OCR 결과 요약 ({ocrResults.length}개)
            </Label>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {[...ocrResults]
                .sort((a, b) => (a.order_index ?? 999) - (b.order_index ?? 999))
                .map((ocr, idx) => {
                  const imageIndex = images.findIndex(url => url === ocr.image_url)
                  
                  return (
                    <div 
                      key={`ocr-${idx}`}
                      className={cn(
                        "flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-colors",
                        imageIndex === selectedIndex 
                          ? "bg-primary/10 border border-primary/30" 
                          : "hover:bg-muted"
                      )}
                      onClick={() => imageIndex >= 0 && setSelectedIndex(imageIndex)}
                    >
                      <span className="shrink-0 w-6 h-6 rounded-full bg-green-500 text-white text-xs flex items-center justify-center">
                        {idx + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-muted-foreground truncate">
                          {ocr.original_text.slice(0, 50)}...
                        </p>
                        <p className="text-sm truncate">
                          {ocr.translated_text?.slice(0, 50) || '번역 없음'}...
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 shrink-0"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleCopy(ocr.translated_text, 1000 + idx)
                        }}
                      >
                        {copiedIndex === 1000 + idx ? (
                          <Check className="w-3 h-3 text-green-500" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </Button>
                    </div>
                  )
                })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
