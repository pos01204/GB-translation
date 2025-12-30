'use client'

import { useState, useCallback } from 'react'
import { RefreshCw, Download, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from '@/components/ui/toaster'

import { UrlInputForm } from '@/components/UrlInputForm'
import { LoadingState } from '@/components/LoadingState'
import { SideBySideView } from '@/components/SideBySideView'
import { OptionTable } from '@/components/OptionTable'
import { ImageOcrResults } from '@/components/ImageOcrResults'

import { 
  scrapeProduct, 
  translateProduct,
  getErrorMessage,
  type TargetLanguage,
  type ProductData,
  type TranslatedProduct,
} from '@/lib/api'
import { getLanguageDisplayName } from '@/lib/utils'

type AppStatus = 'idle' | 'scraping' | 'translating' | 'completed' | 'error'

export default function Home() {
  const [status, setStatus] = useState<AppStatus>('idle')
  const [loadingStep, setLoadingStep] = useState<'scraping' | 'translating' | 'ocr'>('scraping')
  const [error, setError] = useState<string | null>(null)
  
  const [originalData, setOriginalData] = useState<ProductData | null>(null)
  const [translatedData, setTranslatedData] = useState<TranslatedProduct | null>(null)
  const [currentLanguage, setCurrentLanguage] = useState<TargetLanguage>('en')

  // 크롤링 + 번역 실행
  const handleSubmit = useCallback(async (url: string, language: TargetLanguage) => {
    setStatus('scraping')
    setLoadingStep('scraping')
    setError(null)
    setCurrentLanguage(language)

    try {
      // 1. 크롤링
      const scrapeResult = await scrapeProduct(url)
      
      if (!scrapeResult.success || !scrapeResult.data) {
        throw new Error(scrapeResult.message || '크롤링에 실패했습니다.')
      }

      setOriginalData(scrapeResult.data)
      
      // 2. 번역
      setStatus('translating')
      setLoadingStep('translating')
      
      const translateResult = await translateProduct(scrapeResult.data, language)
      
      if (!translateResult.success || !translateResult.data) {
        throw new Error(translateResult.message || '번역에 실패했습니다.')
      }

      // OCR이 있으면 OCR 단계 표시
      if (scrapeResult.data.detail_images.length > 0) {
        setLoadingStep('ocr')
      }

      setTranslatedData(translateResult.data)
      setStatus('completed')

      toast({
        title: '번역 완료!',
        description: `${getLanguageDisplayName(language)}로 번역이 완료되었습니다.`,
        variant: 'success',
      })

    } catch (err) {
      const errorMessage = getErrorMessage(err)
      setError(errorMessage)
      setStatus('error')

      toast({
        title: '오류 발생',
        description: errorMessage,
        variant: 'destructive',
      })
    }
  }, [])

  // 새로고침 (다시 시작)
  const handleReset = useCallback(() => {
    setStatus('idle')
    setError(null)
    setOriginalData(null)
    setTranslatedData(null)
  }, [])

  // 결과 다운로드 (JSON)
  const handleDownload = useCallback(() => {
    if (!translatedData) return

    const exportData = {
      original: translatedData.original,
      translated: {
        title: translatedData.translated_title,
        description: translatedData.translated_description,
        options: translatedData.translated_options,
        image_texts: translatedData.translated_image_texts,
      },
      target_language: translatedData.target_language,
      exported_at: new Date().toISOString(),
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `idus-translation-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)

    toast({
      title: '다운로드 완료',
      description: 'JSON 파일이 다운로드되었습니다.',
    })
  }, [translatedData])

  // 번역 텍스트 수정 핸들러
  const handleEditTitle = useCallback((newTitle: string) => {
    if (translatedData) {
      setTranslatedData({ ...translatedData, translated_title: newTitle })
    }
  }, [translatedData])

  const handleEditDescription = useCallback((newDescription: string) => {
    if (translatedData) {
      setTranslatedData({ ...translatedData, translated_description: newDescription })
    }
  }, [translatedData])

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* 히어로 섹션 */}
      {status === 'idle' && (
        <div className="text-center mb-8 animate-fade-in">
          <h1 className="text-4xl font-bold mb-4">
            <span className="gradient-text">아이디어스</span> 작품을
            <br />
            전 세계에 소개하세요
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            URL만 입력하면 상품 정보와 이미지 내 텍스트까지 자동으로 번역합니다.
            <br />
            AI 기반 OCR과 GPT-4o 번역으로 정확한 글로벌 마케팅을 시작하세요.
          </p>
        </div>
      )}

      {/* URL 입력 폼 - idle 또는 error 상태에서 표시 */}
      {(status === 'idle' || status === 'error') && (
        <div className="max-w-2xl mx-auto mb-8 animate-slide-up">
          <UrlInputForm
            onSubmit={handleSubmit}
            isLoading={false}
            disabled={false}
          />
          
          {/* 에러 메시지 */}
          {status === 'error' && error && (
            <Card className="mt-4 border-destructive bg-destructive/5">
              <CardContent className="pt-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-destructive">오류가 발생했습니다</p>
                    <p className="text-sm text-muted-foreground mt-1">{error}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* 로딩 상태 */}
      {(status === 'scraping' || status === 'translating') && (
        <div className="max-w-2xl mx-auto animate-fade-in">
          <LoadingState currentStep={loadingStep} />
        </div>
      )}

      {/* 결과 표시 */}
      {status === 'completed' && translatedData && originalData && (
        <div className="space-y-6 animate-fade-in">
          {/* 상단 액션 바 */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">번역 결과</h2>
              <p className="text-sm text-muted-foreground">
                {getLanguageDisplayName(currentLanguage)} 번역 완료 • 
                클릭하여 직접 수정할 수 있습니다
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={handleDownload}>
                <Download className="w-4 h-4 mr-2" />
                JSON 다운로드
              </Button>
              <Button variant="outline" onClick={handleReset}>
                <RefreshCw className="w-4 h-4 mr-2" />
                새 번역
              </Button>
            </div>
          </div>

          {/* 탭 네비게이션 */}
          <Tabs defaultValue="content" className="w-full">
            <TabsList className="grid w-full grid-cols-3 max-w-md">
              <TabsTrigger value="content">상품 정보</TabsTrigger>
              <TabsTrigger value="options">옵션</TabsTrigger>
              <TabsTrigger value="images">
                이미지 OCR
                {translatedData.translated_image_texts.length > 0 && (
                  <span className="ml-1 px-1.5 py-0.5 text-xs bg-primary text-primary-foreground rounded">
                    {translatedData.translated_image_texts.length}
                  </span>
                )}
              </TabsTrigger>
            </TabsList>

            {/* 상품 정보 탭 */}
            <TabsContent value="content" className="mt-6">
              <SideBySideView
                originalTitle={originalData.title}
                originalContent={originalData.description}
                translatedTitle={translatedData.translated_title}
                translatedContent={translatedData.translated_description}
                onEditTitle={handleEditTitle}
                onEditContent={handleEditDescription}
                label={{
                  original: '원본 (한국어)',
                  translated: getLanguageDisplayName(currentLanguage),
                }}
              />

              {/* 기본 정보 카드 */}
              <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground mb-1">작가명</p>
                    <p className="font-medium">{originalData.artist_name}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground mb-1">가격</p>
                    <p className="font-medium">{originalData.price}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground mb-1">상세 이미지</p>
                    <p className="font-medium">{originalData.detail_images.length}개</p>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* 옵션 탭 */}
            <TabsContent value="options" className="mt-6">
              {originalData.options.length > 0 ? (
                <OptionTable
                  originalOptions={originalData.options}
                  translatedOptions={translatedData.translated_options}
                />
              ) : (
                <Card>
                  <CardContent className="py-12 text-center">
                    <p className="text-muted-foreground">옵션 정보가 없습니다.</p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* 이미지 OCR 탭 */}
            <TabsContent value="images" className="mt-6">
              {translatedData.translated_image_texts.length > 0 ? (
                <ImageOcrResults
                  imageTexts={translatedData.translated_image_texts}
                />
              ) : (
                <Card>
                  <CardContent className="py-12 text-center">
                    <p className="text-muted-foreground">
                      이미지에서 추출된 텍스트가 없습니다.
                    </p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  )
}

