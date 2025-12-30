'use client'

import { useState, useMemo } from 'react'
import { Copy, Check, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toaster'
import type { ImageText, ProductOption } from '@/lib/api'

interface FinalTranslationProps {
  translatedTitle: string
  translatedDescription: string
  translatedOptions: ProductOption[]
  translatedImageTexts: ImageText[]
  targetLanguage: string
}

export function FinalTranslation({
  translatedTitle,
  translatedDescription,
  translatedOptions,
  translatedImageTexts,
  targetLanguage,
}: FinalTranslationProps) {
  const [copied, setCopied] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editedText, setEditedText] = useState('')

  // 최종 번역본을 논리적으로 재구성
  const finalText = useMemo(() => {
    const sections: string[] = []

    // 1. 상품명
    sections.push(`【${targetLanguage === 'ja' ? '商品名' : 'Product Name'}】`)
    sections.push(translatedTitle)
    sections.push('')

    // 2. 상품 설명
    sections.push(`【${targetLanguage === 'ja' ? '商品説明' : 'Description'}】`)
    sections.push(translatedDescription)
    sections.push('')

    // 3. 옵션 정보 (있는 경우)
    if (translatedOptions.length > 0) {
      sections.push(`【${targetLanguage === 'ja' ? 'オプション' : 'Options'}】`)
      translatedOptions.forEach((opt) => {
        sections.push(`• ${opt.name}: ${opt.values.join(', ')}`)
      })
      sections.push('')
    }

    // 4. 이미지 OCR 텍스트 (순서대로 정렬하여 표시)
    if (translatedImageTexts.length > 0) {
      sections.push(`【${targetLanguage === 'ja' ? '画像内テキスト' : 'Image Text (OCR)'}】`)
      sections.push('')
      
      // 이미지 URL에서 순서 추출하여 정렬
      const sortedTexts = [...translatedImageTexts].sort((a, b) => {
        // URL에서 파일명 추출하여 정렬
        const getFileName = (url: string) => {
          const match = url.match(/files\/([a-f0-9]+)/i)
          return match ? match[1] : url
        }
        return getFileName(a.image_url).localeCompare(getFileName(b.image_url))
      })

      sortedTexts.forEach((item, index) => {
        sections.push(`[${targetLanguage === 'ja' ? '画像' : 'Image'} ${index + 1}]`)
        sections.push(item.translated_text || item.original_text || '')
        sections.push('')
      })
    }

    return sections.join('\n')
  }, [translatedTitle, translatedDescription, translatedOptions, translatedImageTexts, targetLanguage])

  // 클립보드에 복사
  const handleCopy = async () => {
    const textToCopy = isEditing ? editedText : finalText
    try {
      await navigator.clipboard.writeText(textToCopy)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      toast({
        title: '복사 완료',
        description: '클립보드에 복사되었습니다.',
      })
    } catch {
      toast({
        title: '복사 실패',
        description: '클립보드 복사에 실패했습니다.',
        variant: 'destructive',
      })
    }
  }

  // 편집 모드 토글
  const handleEdit = () => {
    if (!isEditing) {
      setEditedText(finalText)
    }
    setIsEditing(!isEditing)
  }

  // 텍스트 파일로 다운로드
  const handleDownloadText = () => {
    const textToDownload = isEditing ? editedText : finalText
    const blob = new Blob([textToDownload], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `translation-${targetLanguage}-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
    toast({
      title: '다운로드 완료',
      description: '텍스트 파일이 다운로드되었습니다.',
    })
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="flex items-center gap-2">
          <FileText className="w-5 h-5" />
          최종 번역본
        </CardTitle>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleEdit}>
            {isEditing ? '완료' : '편집'}
          </Button>
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied ? (
              <Check className="w-4 h-4 mr-1" />
            ) : (
              <Copy className="w-4 h-4 mr-1" />
            )}
            복사
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownloadText}>
            TXT 다운로드
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-4">
          상품 등록에 바로 사용할 수 있도록 번역 결과를 정리했습니다.
          {isEditing && ' 직접 수정하실 수 있습니다.'}
        </p>
        
        {isEditing ? (
          <Textarea
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            className="min-h-[500px] font-mono text-sm"
          />
        ) : (
          <div className="bg-muted/50 rounded-lg p-4 min-h-[500px] max-h-[700px] overflow-y-auto">
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
              {finalText}
            </pre>
          </div>
        )}

        {/* 통계 */}
        <div className="mt-4 pt-4 border-t flex items-center gap-6 text-sm text-muted-foreground">
          <span>총 글자 수: {(isEditing ? editedText : finalText).length}자</span>
          <span>OCR 이미지: {translatedImageTexts.length}개</span>
          <span>옵션: {translatedOptions.length}개</span>
        </div>
      </CardContent>
    </Card>
  )
}

