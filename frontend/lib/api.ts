/**
 * Backend API 클라이언트
 */

// API URL 설정 - https:// 프로토콜 보장
function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL || ''
  
  // 환경 변수가 없으면 localhost 사용
  if (!envUrl) {
    return 'http://localhost:8000'
  }
  
  // 이미 프로토콜이 있으면 그대로 사용
  if (envUrl.startsWith('http://') || envUrl.startsWith('https://')) {
    // 끝에 슬래시 제거
    return envUrl.replace(/\/$/, '')
  }
  
  // 프로토콜이 없으면 https:// 추가
  return `https://${envUrl}`.replace(/\/$/, '')
}

const API_BASE_URL = getApiBaseUrl()

// Debug: API URL 확인
if (typeof window !== 'undefined') {
  console.log('🔗 API Base URL:', API_BASE_URL)
  console.log('🔗 ENV value:', process.env.NEXT_PUBLIC_API_URL)
}

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
  console.log('🏥 Health check:', `${API_BASE_URL}/api/health`)
  
  const response = await fetch(`${API_BASE_URL}/api/health`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  })
  
  if (!response.ok) {
    throw new Error(`서버에 연결할 수 없습니다. (${response.status})`)
  }
  
  return response.json()
}

/**
 * 상품 페이지 크롤링
 */
export async function scrapeProduct(url: string): Promise<ScrapeResponse> {
  console.log('🔍 Scrape request:', `${API_BASE_URL}/api/scrape`)
  
  const response = await fetch(`${API_BASE_URL}/api/scrape`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({ url }),
  })

  console.log('📥 Scrape response status:', response.status)

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    console.error('❌ Scrape error:', error)
    throw new Error(error.detail || error.message || `크롤링 요청에 실패했습니다. (${response.status})`)
  }

  const data = await response.json()
  console.log('✅ Scrape success:', data.success)
  return data
}

/**
 * 상품 데이터 번역
 */
export async function translateProduct(
  productData: ProductData,
  targetLanguage: TargetLanguage
): Promise<TranslateResponse> {
  console.log('🌐 Translate request:', `${API_BASE_URL}/api/translate`)
  
  const response = await fetch(`${API_BASE_URL}/api/translate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({
      product_data: productData,
      target_language: targetLanguage,
    }),
  })

  console.log('📥 Translate response status:', response.status)

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    console.error('❌ Translate error:', error)
    throw new Error(error.detail || error.message || `번역 요청에 실패했습니다. (${response.status})`)
  }

  const data = await response.json()
  console.log('✅ Translate success:', data.success)
  return data
}

/**
 * 크롤링 + 번역 통합 처리
 */
export async function scrapeAndTranslate(
  url: string,
  targetLanguage: TargetLanguage
): Promise<TranslateResponse> {
  const endpoint = `${API_BASE_URL}/api/scrape-and-translate?url=${encodeURIComponent(url)}&target_language=${targetLanguage}`
  console.log('🚀 Scrape & Translate request:', endpoint)
  
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
    },
  })

  console.log('📥 Response status:', response.status)

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    console.error('❌ Error:', error)
    throw new Error(error.detail || error.message || `처리 요청에 실패했습니다. (${response.status})`)
  }

  const data = await response.json()
  console.log('✅ Success:', data.success, data.message)
  
  // API가 성공했지만 data.success가 false인 경우 처리
  if (!data.success) {
    throw new Error(data.message || '처리에 실패했습니다.')
  }
  
  return data
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
