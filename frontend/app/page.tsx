'use client'

import { useState, useCallback } from 'react'
import { RefreshCw, Download, AlertCircle, Copy, ClipboardCopy, FileText, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from '@/components/ui/toaster'

import { UrlInputForm } from '@/components/UrlInputForm'
import { LoadingState } from '@/components/LoadingState'
import { SideBySideView } from '@/components/SideBySideView'
import { OptionTable } from '@/components/OptionTable'
import { ImageOcrResults } from '@/components/ImageOcrResults'
import { ImageGallery } from '@/components/ImageGallery'
import { ImageOcrMapping } from '@/components/ImageOcrMapping'
import { TranslationHistory } from '@/components/TranslationHistory'
import { QualityCheck } from '@/components/QualityCheck'

import { 
  scrapeProduct, 
  translateProduct,
  getErrorMessage,
  type TargetLanguage,
  type ProductData,
  type TranslatedProduct,
} from '@/lib/api'
import { getLanguageDisplayName } from '@/lib/utils'
import {
  formatStructuredText,
  formatIdusGlobal,
  formatTitleOnly,
  formatDescriptionOnly,
  formatOptionsOnly,
  formatOcrOnly,
  copyToClipboard,
  downloadTxt,
  downloadJson,
} from '@/lib/formatters'
import { saveTranslationHistory } from '@/lib/storage'

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

      // 히스토리에 저장
      saveTranslationHistory(scrapeResult.data, translateResult.data)

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

  // 히스토리에서 불러오기
  const handleLoadHistory = useCallback((original: ProductData, translated: TranslatedProduct) => {
    setOriginalData(original)
    setTranslatedData(translated)
    setCurrentLanguage(translated.target_language)
    setStatus('completed')
    setError(null)
  }, [])

  // 전체 복사
  const handleCopyAll = useCallback(async () => {
    if (!translatedData) return
    const text = formatStructuredText(translatedData)
    const success = await copyToClipboard(text)
    if (success) {
      toast({ title: '복사 완료', description: '전체 번역 결과가 클립보드에 복사되었습니다.' })
    }
  }, [translatedData])

  // 아이디어스 형식 복사
  const handleCopyIdusFormat = useCallback(async () => {
    if (!translatedData) return
    const text = formatIdusGlobal(translatedData)
    const success = await copyToClipboard(text)
    if (success) {
      toast({ title: '복사 완료', description: '아이디어스 글로벌 형식으로 복사되었습니다.' })
    }
  }, [translatedData])

  // 제목만 복사
  const handleCopyTitle = useCallback(async () => {
    if (!translatedData) return
    const success = await copyToClipboard(formatTitleOnly(translatedData))
    if (success) {
      toast({ title: '복사 완료', description: '제목이 복사되었습니다.' })
    }
  }, [translatedData])

  // 설명만 복사
  const handleCopyDescription = useCallback(async () => {
    if (!translatedData) return
    const success = await copyToClipboard(formatDescriptionOnly(translatedData))
    if (success) {
      toast({ title: '복사 완료', description: '설명이 복사되었습니다.' })
    }
  }, [translatedData])

  // 옵션만 복사
  const handleCopyOptions = useCallback(async () => {
    if (!translatedData) return
    const text = formatOptionsOnly(translatedData)
    if (!text) {
      toast({ title: '알림', description: '옵션 정보가 없습니다.' })
      return
    }
    const success = await copyToClipboard(text)
    if (success) {
      toast({ title: '복사 완료', description: '옵션이 복사되었습니다.' })
    }
  }, [translatedData])

  // OCR만 복사
  const handleCopyOcr = useCallback(async () => {
    if (!translatedData) return
    const text = formatOcrOnly(translatedData)
    if (!text) {
      toast({ title: '알림', description: 'OCR 결과가 없습니다.' })
      return
    }
    const success = await copyToClipboard(text)
    if (success) {
      toast({ title: '복사 완료', description: 'OCR 결과가 복사되었습니다.' })
    }
  }, [translatedData])

  // TXT 다운로드
  const handleDownloadTxt = useCallback(() => {
    if (!translatedData) return
    downloadTxt(translatedData)
    toast({ title: '다운로드 완료', description: 'TXT 파일이 다운로드되었습니다.' })
  }, [translatedData])

  // JSON 다운로드
  const handleDownloadJson = useCallback(() => {
    if (!translatedData || !originalData) return
    downloadJson(translatedData, originalData)
    toast({ title: '다운로드 완료', description: 'JSON 파일이 다운로드되었습니다.' })
  }, [translatedData, originalData])

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

  // OCR 텍스트 수정 핸들러
  const handleEditOcr = useCallback((index: number, newText: string) => {
    if (translatedData) {
      const updatedImageTexts = [...translatedData.translated_image_texts]
      if (updatedImageTexts[index]) {
        updatedImageTexts[index] = {
          ...updatedImageTexts[index],
          translated_text: newText
        }
        setTranslatedData({
          ...translatedData,
          translated_image_texts: updatedImageTexts
        })
      }
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
          {/* 히스토리 컴포넌트 */}
          <TranslationHistory 
            onLoadHistory={handleLoadHistory}
            currentUrl={originalData?.url}
          />
          
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
              {/* 빠른 복사 버튼 */}
              <Button variant="default" onClick={handleCopyAll}>
                <Copy className="w-4 h-4 mr-2" />
                전체 복사
              </Button>
              
              {/* 복사 옵션 드롭다운 */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline">
                    <ClipboardCopy className="w-4 h-4 mr-2" />
                    복사 옵션
                    <ChevronDown className="w-4 h-4 ml-2" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuItem onClick={handleCopyIdusFormat}>
                    <FileText className="w-4 h-4 mr-2" />
                    아이디어스 글로벌 형식
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleCopyTitle}>
                    📌 제목만 복사
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleCopyDescription}>
                    📝 설명만 복사
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleCopyOptions}>
                    🏷️ 옵션만 복사
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleCopyOcr}>
                    🖼️ OCR 결과만 복사
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              
              {/* 다운로드 드롭다운 */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline">
                    <Download className="w-4 h-4 mr-2" />
                    다운로드
                    <ChevronDown className="w-4 h-4 ml-2" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={handleDownloadTxt}>
                    📄 TXT 파일
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleDownloadJson}>
                    📦 JSON 파일
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              
              <Button variant="outline" onClick={handleReset}>
                <RefreshCw className="w-4 h-4 mr-2" />
                새 번역
              </Button>
            </div>
          </div>

          {/* 품질 검증 */}
          <QualityCheck data={translatedData} />

          {/* 탭 네비게이션 */}
          <Tabs defaultValue="content" className="w-full">
            <TabsList className="grid w-full grid-cols-4 max-w-lg">
              <TabsTrigger value="content">상품 정보</TabsTrigger>
              <TabsTrigger value="options">옵션</TabsTrigger>
              <TabsTrigger value="gallery">
                이미지
                {originalData.detail_images.length > 0 && (
                  <span className="ml-1 px-1.5 py-0.5 text-xs bg-muted-foreground/20 rounded">
                    {originalData.detail_images.length}
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="ocr">
                OCR
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

            {/* 이미지 갤러리 탭 */}
            <TabsContent value="gallery" className="mt-6">
              <ImageGallery 
                images={originalData.detail_images}
                productTitle={originalData.title}
              />
            </TabsContent>

            {/* 이미지 OCR 탭 - 매핑 뷰 적용 */}
            <TabsContent value="ocr" className="mt-6">
              <ImageOcrMapping
                images={originalData.detail_images}
                ocrResults={translatedData.translated_image_texts}
                onEditOcr={handleEditOcr}
              />
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  )
}

