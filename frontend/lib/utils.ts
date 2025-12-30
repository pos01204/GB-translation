import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Tailwind CSS 클래스 병합 유틸리티
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * 아이디어스 URL 유효성 검사
 */
export function isValidIdusUrl(url: string): boolean {
  try {
    const urlObj = new URL(url)
    return urlObj.hostname.includes('idus.com')
  } catch {
    return false
  }
}

/**
 * URL에서 상품 ID 추출
 */
export function extractProductId(url: string): string | null {
  const match = url.match(/product\/(\d+)/)
  return match ? match[1] : null
}

/**
 * 텍스트 줄임 처리
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

/**
 * 딜레이 유틸리티
 */
export function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * 클립보드 복사
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

/**
 * 언어 코드를 표시명으로 변환
 */
export function getLanguageDisplayName(code: string): string {
  const names: Record<string, string> = {
    en: 'English',
    ja: '日本語',
    ko: '한국어',
  }
  return names[code] || code
}

/**
 * 가격 포맷팅
 */
export function formatPrice(price: string, targetLang: string): string {
  // 숫자만 추출
  const numbers = price.replace(/[^0-9]/g, '')
  if (!numbers) return price

  const amount = parseInt(numbers, 10)
  
  switch (targetLang) {
    case 'en':
      // 원화 → 달러 (대략적 환율)
      const usd = (amount / 1350).toFixed(2)
      return `$${usd} (₩${amount.toLocaleString()})`
    case 'ja':
      // 원화 → 엔 (대략적 환율)  
      const jpy = Math.round(amount / 9)
      return `¥${jpy.toLocaleString()} (₩${amount.toLocaleString()})`
    default:
      return price
  }
}

