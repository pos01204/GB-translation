/**
 * Backend API 클라이언트
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ============ Types ============

export type TargetLanguage = 'en' | 'ja'

export interface ProductOption {
  name: string
  values: string[]
}

export interface ImageText {
  image_url: string
  original_text: string
  translated_text: string | null
}

export interface ProductData {
  url: string
  title: string
  artist_name: string
  price: string
  description: string
  options: ProductOption[]
  detail_images: string[]
  image_texts: ImageText[]
}

export interface TranslatedProduct {
  original: ProductData
  translated_title: string
  translated_description: string
  translated_options: ProductOption[]
  translated_image_texts: ImageText[]
  target_language: TargetLanguage
}

export interface ScrapeResponse {
  success: boolean
  message: string
  data: ProductData | null
}

export interface TranslateResponse {
  success: boolean
  message: string
  data: TranslatedProduct | null
}

export interface HealthResponse {
  status: string
  version: string
}

// ============ API Functions ============

/**
 * API 헬스체크
 */
export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`)
  
  if (!response.ok) {
    throw new Error('서버에 연결할 수 없습니다.')
  }
  
  return response.json()
}

/**
 * 상품 페이지 크롤링
 */
export async function scrapeProduct(url: string): Promise<ScrapeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/scrape`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || '크롤링 요청에 실패했습니다.')
  }

  return response.json()
}

/**
 * 상품 데이터 번역
 */
export async function translateProduct(
  productData: ProductData,
  targetLanguage: TargetLanguage
): Promise<TranslateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/translate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      product_data: productData,
      target_language: targetLanguage,
    }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || '번역 요청에 실패했습니다.')
  }

  return response.json()
}

/**
 * 크롤링 + 번역 통합 처리
 */
export async function scrapeAndTranslate(
  url: string,
  targetLanguage: TargetLanguage
): Promise<TranslateResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/scrape-and-translate?url=${encodeURIComponent(url)}&target_language=${targetLanguage}`,
    {
      method: 'POST',
    }
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || '처리 요청에 실패했습니다.')
  }

  return response.json()
}

// ============ Utility Functions ============

/**
 * 에러 메시지 추출
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }
  return '알 수 없는 오류가 발생했습니다.'
}

