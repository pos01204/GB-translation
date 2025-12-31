'use client'

import { useState, useCallback } from 'react'
import { Download, Copy, Eye, ChevronDown, ChevronUp, FileText, FileJson } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { toast } from '@/components/ui/toaster'
import { getLanguageDisplayName } from '@/lib/utils'
import { formatStructuredText, formatIdusGlobal, copyToClipboard } from '@/lib/formatters'
import type { TranslatedProduct, ProductData } from '@/lib/api'

export interface BatchResultItem {
  id: string
  url: string
  originalData: ProductData
  translatedData: TranslatedProduct
}

interface BatchResultsProps {
  results: BatchResultItem[]
  onViewDetail: (item: BatchResultItem) => void
  onReset: () => void
}

export function BatchResults({ results, onViewDetail, onReset }: BatchResultsProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // 전체 복사
  const handleCopyAll = useCallback(async () => {
    const allText = results
      .map((item, idx) => {
        const header = `\n${'='.repeat(60)}\n[${idx + 1}] ${item.originalData.title}\n${'='.repeat(60)}\n`
        return header + formatStructuredText(item.translatedData)
      })
      .join('\n\n')
    
    const success = await copyToClipboard(allText)
    if (success) {
      toast({ title: '복사 완료', description: '전체 번역 결과가 복사되었습니다.' })
    }
  }, [results])

  // 개별 복사
  const handleCopySingle = useCallback(async (item: BatchResultItem, format: 'full' | 'idus') => {
    const text = format === 'full' 
      ? formatStructuredText(item.translatedData)
      : formatIdusGlobal(item.translatedData)
    
    const success = await copyToClipboard(text)
    if (success) {
      toast({ title: '복사 완료', description: '번역 결과가 복사되었습니다.' })
    }
  }, [])

  // 전체 JSON 다운로드
  const handleDownloadAllJson = useCallback(() => {
    const exportData = {
      exported_at: new Date().toISOString(),
      total_count: results.length,
      results: results.map(item => ({
        url: item.url,
        original: {
          title: item.originalData.title,
          description: item.originalData.description,
          artist_name: item.originalData.artist_name,
          price: item.originalData.price,
          options: item.originalData.options,
        },
        translated: {
          title: item.translatedData.translated_title,
          description: item.translatedData.translated_description,
          options: item.translatedData.translated_options,
          image_texts: item.translatedData.translated_image_texts,
        },
        target_language: item.translatedData.target_language,
      }))
    }
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { 
      type: 'application/json;charset=utf-8' 
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `idus-batch-translation-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
    
    toast({ title: '다운로드 완료', description: 'JSON 파일이 다운로드되었습니다.' })
  }, [results])

  // 전체 TXT 다운로드
  const handleDownloadAllTxt = useCallback(() => {
    const content = results
      .map((item, idx) => {
        const header = `${'='.repeat(60)}\n[${idx + 1}] ${item.originalData.title}\n${'='.repeat(60)}\n\n`
        return header + formatStructuredText(item.translatedData)
      })
      .join('\n\n' + '─'.repeat(60) + '\n\n')
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `idus-batch-translation-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
    
    toast({ title: '다운로드 완료', description: 'TXT 파일이 다운로드되었습니다.' })
  }, [results])

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">
            배치 번역 결과 ({results.length}개)
          </CardTitle>
          
          <div className="flex gap-2">
            {/* 전체 복사 */}
            <Button variant="outline" size="sm" onClick={handleCopyAll}>
              <Copy className="w-4 h-4 mr-2" />
              전체 복사
            </Button>
            
            {/* 다운로드 옵션 */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  <Download className="w-4 h-4 mr-2" />
                  다운로드
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleDownloadAllTxt}>
                  <FileText className="w-4 h-4 mr-2" />
                  TXT 파일
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleDownloadAllJson}>
                  <FileJson className="w-4 h-4 mr-2" />
                  JSON 파일
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            
            {/* 새 배치 */}
            <Button variant="default" size="sm" onClick={onReset}>
              새 배치 시작
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        <div className="space-y-2">
          {results.map((item, idx) => (
            <div
              key={item.id}
              className="border rounded-lg overflow-hidden"
            >
              {/* 헤더 */}
              <div 
                className="flex items-center gap-3 p-3 bg-muted/30 cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
              >
                <span className="shrink-0 w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-medium">
                  {idx + 1}
                </span>
                
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">
                    {item.originalData.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {item.originalData.artist_name} • {getLanguageDisplayName(item.translatedData.target_language)}
                  </p>
                </div>
                
                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      onViewDetail(item)
                    }}
                  >
                    <Eye className="w-4 h-4 mr-1" />
                    상세
                  </Button>
                  
                  {expandedId === item.id ? (
                    <ChevronUp className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  )}
                </div>
              </div>
              
              {/* 확장 내용 */}
              {expandedId === item.id && (
                <div className="p-4 border-t bg-background space-y-4">
                  {/* 번역된 제목 */}
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">번역된 제목</p>
                    <p className="font-medium">{item.translatedData.translated_title}</p>
                  </div>
                  
                  {/* 번역된 설명 (미리보기) */}
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">번역된 설명</p>
                    <p className="text-sm line-clamp-3">
                      {item.translatedData.translated_description}
                    </p>
                  </div>
                  
                  {/* 옵션 */}
                  {item.translatedData.translated_options.length > 0 && (
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">옵션</p>
                      <div className="flex flex-wrap gap-1">
                        {item.translatedData.translated_options.map((opt, optIdx) => (
                          <span 
                            key={optIdx}
                            className="text-xs bg-muted px-2 py-1 rounded"
                          >
                            {opt.name}: {opt.values.length}개
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* OCR 결과 */}
                  {item.translatedData.translated_image_texts.length > 0 && (
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">
                        OCR 결과: {item.translatedData.translated_image_texts.length}개 이미지
                      </p>
                    </div>
                  )}
                  
                  {/* 개별 복사 버튼 */}
                  <div className="flex gap-2 pt-2 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleCopySingle(item, 'full')}
                    >
                      <Copy className="w-3 h-3 mr-1" />
                      전체 복사
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleCopySingle(item, 'idus')}
                    >
                      <Copy className="w-3 h-3 mr-1" />
                      아이디어스 형식
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
