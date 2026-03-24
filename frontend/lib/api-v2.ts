/**
 * v2 API 클라이언트 — 작가웹 연동 GB 등록용
 */

// 기존 api.ts에서 base URL 유틸리티 재사용
function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL || ''
  if (!envUrl) return 'http://localhost:8000'
  if (envUrl.startsWith('http://') || envUrl.startsWith('https://')) {
    return envUrl.replace(/\/$/, '')
  }
  return `https://${envUrl}`.replace(/\/$/, '')
}

const API_V2_BASE = `${getApiBaseUrl()}/api/v2`

// ============ Types ============

export interface ImageText {
  image_url: string
  original_text: string
  translated_text: string
  order_index: number
  translated_image_base64?: string | null
}

export interface LoginRequest {
  email: string
  password: string
}

export interface SessionStatus {
  initialized?: boolean
  authenticated: boolean
  current_url?: string | null
}

export interface ProductSummary {
  product_id: string
  title: string
  price: number
  thumbnail_url: string | null
  status: string
  global_status: string
  global_languages: string[]
}

export interface ProductImage {
  url: string
  order: number
  is_representative: boolean
}

export interface OptionValue {
  value: string
  additional_price: number
}

export interface DomesticOption {
  name: string
  values: OptionValue[]
  option_type: string
}

export interface DomesticProduct {
  product_id: string
  title: string
  price: number
  quantity: number
  category_path: string
  category_restricted: boolean
  product_images: ProductImage[]
  intro: string | null
  features: string[]
  process_steps: string[]
  description_html: string
  options: DomesticOption[]
  keywords: string[]
  gift_wrapping: boolean
  status: string
  global_status: string
  detail_images: ProductImage[]
}

export interface DescriptionBlock {
  uuid: string
  type: 'TEXT' | 'SUBJECT' | 'IMAGE' | 'SPLIT_IMAGE' | 'LINE' | 'BLANK'
  label: string
  value: string | string[]
}

export interface LanguageData {
  title: string
  description_html: string
  description_blocks: DescriptionBlock[]
  keywords: string[]
  use_domestic_images: boolean
  image_texts: ImageText[]
}

export interface GlobalOption {
  original_name: string
  name_en: string
  name_ja: string
  values_en: string[]
  values_ja: string[]
}

export interface GlobalProductData {
  source_product_id: string
  en: LanguageData | null
  ja: LanguageData | null
  global_options: GlobalOption[]
}

export interface TranslatePreviewResponse {
  success: boolean
  message: string
  domestic_data: DomesticProduct | null
  global_data: GlobalProductData | null
}

export interface RegistrationResult {
  product_id: string
  success: boolean
  languages_registered: string[]
  languages_failed: string[]
  error_message: string | null
  saved_as_draft: boolean
}

export interface BatchProgressItem {
  product_id: string
  status: string
  error_message: string | null
}

export interface BatchProgress {
  total: number
  completed: number
  failed: number
  is_done: boolean
  success_rate: number
  items: BatchProgressItem[]
}

// ============ Session API ============

export async function loginArtistWeb(
  email: string,
  password: string
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_V2_BASE}/session/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || `로그인 실패 (${response.status})`)
  }
  return response.json()
}

export async function getSessionStatus(): Promise<SessionStatus> {
  const response = await fetch(`${API_V2_BASE}/session/status`)
  if (!response.ok) {
    throw new Error(`세션 상태 확인 실패 (${response.status})`)
  }
  return response.json()
}

export async function logoutArtistWeb(): Promise<void> {
  await fetch(`${API_V2_BASE}/session/logout`, { method: 'POST' })
}

// ============ Products API ============

export async function getProductList(
  status: string = 'selling'
): Promise<{ success: boolean; message: string; products: ProductSummary[]; total_count: number; debug_info?: Record<string, unknown> | null }> {
  const response = await fetch(`${API_V2_BASE}/products/?status=${status}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || `작품 목록 조회 실패 (${response.status})`)
  }
  return response.json()
}

export async function getDomesticData(
  productId: string
): Promise<{ success: boolean; data: DomesticProduct }> {
  const response = await fetch(
    `${API_V2_BASE}/products/${productId}/domestic`
  )
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || `작품 상세 조회 실패 (${response.status})`)
  }
  return response.json()
}

// ============ Translation API ============

export async function translatePreview(
  productId: string,
  targetLanguages: string[] = ['en', 'ja']
): Promise<TranslatePreviewResponse> {
  const response = await fetch(`${API_V2_BASE}/translate/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_id: productId,
      target_languages: targetLanguages,
    }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || `번역 미리보기 실패 (${response.status})`)
  }
  return response.json()
}

// ============ Registration API ============

export async function registerSingle(
  productId: string,
  options: {
    targetLanguages?: string[]
    saveAsDraft?: boolean
    globalData?: GlobalProductData
  } = {}
): Promise<{ success: boolean; message: string; result: RegistrationResult | null }> {
  const response = await fetch(`${API_V2_BASE}/register/single`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_id: productId,
      target_languages: options.targetLanguages || ['en', 'ja'],
      save_as_draft: options.saveAsDraft ?? true,
      global_data: options.globalData || null,
    }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || `등록 실패 (${response.status})`)
  }
  return response.json()
}

export async function registerBatch(
  productIds: string[],
  options: {
    targetLanguages?: string[]
    saveAsDraft?: boolean
  } = {}
): Promise<{ success: boolean; message: string; progress: BatchProgress | null }> {
  const response = await fetch(`${API_V2_BASE}/register/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_ids: productIds,
      target_languages: options.targetLanguages || ['en', 'ja'],
      save_as_draft: options.saveAsDraft ?? true,
    }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || `일괄 등록 실패 (${response.status})`)
  }
  return response.json()
}

// ============ Utility ============

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return '알 수 없는 오류가 발생했습니다.'
}
