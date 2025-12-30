'use client'

import { useState } from 'react'
import { Download, ImageIcon, CheckCircle2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from '@/components/ui/toaster'

interface ImageGalleryProps {
  images: string[]
  productTitle?: string
}

export function ImageGallery({ images, productTitle = 'product' }: ImageGalleryProps) {
  const [selectedImages, setSelectedImages] = useState<Set<number>>(new Set())
  const [downloading, setDownloading] = useState(false)
  const [downloadedCount, setDownloadedCount] = useState(0)

  // 이미지 선택 토글
  const toggleSelection = (index: number) => {
    const newSelected = new Set(selectedImages)
    if (newSelected.has(index)) {
      newSelected.delete(index)
    } else {
      newSelected.add(index)
    }
    setSelectedImages(newSelected)
  }

  // 전체 선택/해제
  const toggleSelectAll = () => {
    if (selectedImages.size === images.length) {
      setSelectedImages(new Set())
    } else {
      setSelectedImages(new Set(images.map((_, i) => i)))
    }
  }

  // 단일 이미지 다운로드
  const downloadImage = async (url: string, index: number) => {
    try {
      const response = await fetch(url)
      const blob = await response.blob()
      
      // 파일 확장자 추출
      const contentType = blob.type
      let ext = 'jpg'
      if (contentType.includes('png')) ext = 'png'
      else if (contentType.includes('webp')) ext = 'webp'
      else if (contentType.includes('gif')) ext = 'gif'
      
      const filename = `${productTitle.replace(/[^a-zA-Z0-9가-힣]/g, '_')}_${index + 1}.${ext}`
      
      const downloadUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(downloadUrl)
      
      return true
    } catch (error) {
      console.error(`이미지 다운로드 실패: ${url}`, error)
      return false
    }
  }

  // 선택된 이미지 일괄 다운로드
  const downloadSelected = async () => {
    const indices = selectedImages.size > 0 
      ? Array.from(selectedImages) 
      : images.map((_, i) => i)
    
    if (indices.length === 0) {
      toast({
        title: '다운로드할 이미지가 없습니다',
        variant: 'destructive',
      })
      return
    }

    setDownloading(true)
    setDownloadedCount(0)

    let successCount = 0
    for (let i = 0; i < indices.length; i++) {
      const index = indices[i]
      const success = await downloadImage(images[index], index)
      if (success) successCount++
      setDownloadedCount(i + 1)
      
      // 브라우저가 멈추지 않도록 짧은 딜레이
      await new Promise(resolve => setTimeout(resolve, 300))
    }

    setDownloading(false)
    
    toast({
      title: '다운로드 완료',
      description: `${successCount}개의 이미지가 다운로드되었습니다.`,
      variant: 'success',
    })
  }

  if (images.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <ImageIcon className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">수집된 이미지가 없습니다.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* 액션 바 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <ImageIcon className="w-5 h-5" />
              상품 이미지 ({images.length}개)
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={toggleSelectAll}
              >
                {selectedImages.size === images.length ? '전체 해제' : '전체 선택'}
              </Button>
              <Button
                onClick={downloadSelected}
                disabled={downloading}
                size="sm"
              >
                {downloading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    {downloadedCount}/{selectedImages.size || images.length}
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 mr-2" />
                    {selectedImages.size > 0 
                      ? `선택 다운로드 (${selectedImages.size})`
                      : '전체 다운로드'
                    }
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* 이미지 그리드 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {images.map((url, index) => (
          <div
            key={index}
            className={`relative group cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
              selectedImages.has(index)
                ? 'border-primary ring-2 ring-primary/20'
                : 'border-transparent hover:border-muted-foreground/30'
            }`}
            onClick={() => toggleSelection(index)}
          >
            {/* 이미지 */}
            <div className="aspect-square bg-muted">
              <img
                src={url}
                alt={`상품 이미지 ${index + 1}`}
                className="w-full h-full object-cover"
                loading="lazy"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23f0f0f0" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%23999" font-size="12">이미지 로드 실패</text></svg>'
                }}
              />
            </div>
            
            {/* 선택 체크 표시 */}
            {selectedImages.has(index) && (
              <div className="absolute top-2 right-2 bg-primary text-primary-foreground rounded-full p-1">
                <CheckCircle2 className="w-4 h-4" />
              </div>
            )}
            
            {/* 인덱스 표시 */}
            <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
              {index + 1}
            </div>
            
            {/* 호버 시 다운로드 버튼 */}
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <Button
                size="sm"
                variant="secondary"
                onClick={(e) => {
                  e.stopPropagation()
                  downloadImage(url, index)
                  toast({
                    title: '다운로드 시작',
                    description: `이미지 ${index + 1} 다운로드 중...`,
                  })
                }}
              >
                <Download className="w-4 h-4 mr-1" />
                다운로드
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

