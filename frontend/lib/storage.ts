/**
 * 번역 히스토리 및 로컬 스토리지 관리
 */

import type { TranslatedProduct, ProductData, TargetLanguage } from './api'

// 히스토리 항목 타입
export interface TranslationHistoryItem {
  id: string
  timestamp: number
  url: string
  productTitle: string
  targetLanguage: TargetLanguage
  originalData: ProductData
  translatedData: TranslatedProduct
}

// 스토리지 키
const STORAGE_KEYS = {
  HISTORY: 'idus-translator-history',
  GLOSSARY: 'idus-translator-glossary',
  SETTINGS: 'idus-translator-settings',
} as const

// 최대 히스토리 개수
const MAX_HISTORY_ITEMS = 20

/**
 * 고유 ID 생성
 */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

/**
 * 번역 히스토리 저장
 */
export function saveTranslationHistory(
  originalData: ProductData,
  translatedData: TranslatedProduct
): TranslationHistoryItem {
  const historyItem: TranslationHistoryItem = {
    id: generateId(),
    timestamp: Date.now(),
    url: originalData.url,
    productTitle: originalData.title,
    targetLanguage: translatedData.target_language,
    originalData,
    translatedData,
  }

  try {
    const existing = getTranslationHistory()
    
    // 같은 URL의 이전 기록 제거 (최신 것만 유지)
    const filtered = existing.filter(item => item.url !== originalData.url)
    
    // 새 항목 추가 (맨 앞에)
    const updated = [historyItem, ...filtered].slice(0, MAX_HISTORY_ITEMS)
    
    localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(updated))
    
    return historyItem
  } catch (error) {
    console.error('히스토리 저장 실패:', error)
    return historyItem
  }
}

/**
 * 번역 히스토리 조회
 */
export function getTranslationHistory(): TranslationHistoryItem[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.HISTORY)
    if (!stored) return []
    
    const parsed = JSON.parse(stored) as TranslationHistoryItem[]
    return parsed
  } catch (error) {
    console.error('히스토리 조회 실패:', error)
    return []
  }
}

/**
 * 특정 히스토리 항목 조회
 */
export function getHistoryItem(id: string): TranslationHistoryItem | null {
  const history = getTranslationHistory()
  return history.find(item => item.id === id) || null
}

/**
 * URL로 히스토리 항목 조회
 */
export function getHistoryByUrl(url: string): TranslationHistoryItem | null {
  const history = getTranslationHistory()
  return history.find(item => item.url === url) || null
}

/**
 * 히스토리 항목 삭제
 */
export function deleteHistoryItem(id: string): boolean {
  try {
    const history = getTranslationHistory()
    const filtered = history.filter(item => item.id !== id)
    localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(filtered))
    return true
  } catch (error) {
    console.error('히스토리 삭제 실패:', error)
    return false
  }
}

/**
 * 전체 히스토리 삭제
 */
export function clearAllHistory(): boolean {
  try {
    localStorage.removeItem(STORAGE_KEYS.HISTORY)
    return true
  } catch (error) {
    console.error('히스토리 전체 삭제 실패:', error)
    return false
  }
}

/**
 * 히스토리 항목 업데이트 (편집된 내용 저장)
 */
export function updateHistoryItem(
  id: string,
  translatedData: TranslatedProduct
): boolean {
  try {
    const history = getTranslationHistory()
    const index = history.findIndex(item => item.id === id)
    
    if (index === -1) return false
    
    history[index] = {
      ...history[index],
      translatedData,
      timestamp: Date.now(), // 수정 시간 업데이트
    }
    
    localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(history))
    return true
  } catch (error) {
    console.error('히스토리 업데이트 실패:', error)
    return false
  }
}

/**
 * 타임스탬프를 읽기 쉬운 형식으로 변환
 */
export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return '방금 전'
  if (diffMins < 60) return `${diffMins}분 전`
  if (diffHours < 24) return `${diffHours}시간 전`
  if (diffDays < 7) return `${diffDays}일 전`
  
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// getLanguageDisplayName은 utils.ts에서 import하여 사용

// ============ 용어집 관리 ============

// 용어집 항목 타입
export interface GlossaryItem {
  id: string
  korean: string
  english: string
  japanese: string
  category: string
  notes?: string
  createdAt: number
  updatedAt: number
}

// 기본 카테고리
export const GLOSSARY_CATEGORIES = [
  '소재/재료',
  '색상',
  '크기/사이즈',
  '제작/공정',
  '배송/결제',
  '기타',
] as const

/**
 * 용어집 저장
 */
export function saveGlossaryItem(item: Omit<GlossaryItem, 'id' | 'createdAt' | 'updatedAt'>): GlossaryItem {
  const newItem: GlossaryItem = {
    ...item,
    id: generateId(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }

  try {
    const existing = getGlossary()
    
    // 중복 체크 (같은 한국어 용어)
    const isDuplicate = existing.some(g => g.korean === item.korean)
    if (isDuplicate) {
      throw new Error('이미 등록된 용어입니다.')
    }
    
    const updated = [newItem, ...existing]
    localStorage.setItem(STORAGE_KEYS.GLOSSARY, JSON.stringify(updated))
    
    return newItem
  } catch (error) {
    console.error('용어집 저장 실패:', error)
    throw error
  }
}

/**
 * 용어집 조회
 */
export function getGlossary(): GlossaryItem[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.GLOSSARY)
    if (!stored) return []
    return JSON.parse(stored) as GlossaryItem[]
  } catch (error) {
    console.error('용어집 조회 실패:', error)
    return []
  }
}

/**
 * 용어집 항목 수정
 */
export function updateGlossaryItem(id: string, updates: Partial<GlossaryItem>): boolean {
  try {
    const glossary = getGlossary()
    const index = glossary.findIndex(item => item.id === id)
    
    if (index === -1) return false
    
    glossary[index] = {
      ...glossary[index],
      ...updates,
      updatedAt: Date.now(),
    }
    
    localStorage.setItem(STORAGE_KEYS.GLOSSARY, JSON.stringify(glossary))
    return true
  } catch (error) {
    console.error('용어집 수정 실패:', error)
    return false
  }
}

/**
 * 용어집 항목 삭제
 */
export function deleteGlossaryItem(id: string): boolean {
  try {
    const glossary = getGlossary()
    const filtered = glossary.filter(item => item.id !== id)
    localStorage.setItem(STORAGE_KEYS.GLOSSARY, JSON.stringify(filtered))
    return true
  } catch (error) {
    console.error('용어집 삭제 실패:', error)
    return false
  }
}

/**
 * 용어 검색 (한국어 기준)
 */
export function searchGlossary(query: string): GlossaryItem[] {
  const glossary = getGlossary()
  const lowerQuery = query.toLowerCase()
  
  return glossary.filter(item =>
    item.korean.toLowerCase().includes(lowerQuery) ||
    item.english.toLowerCase().includes(lowerQuery) ||
    item.japanese.includes(query)
  )
}

/**
 * 카테고리별 용어집 조회
 */
export function getGlossaryByCategory(category: string): GlossaryItem[] {
  const glossary = getGlossary()
  return glossary.filter(item => item.category === category)
}

/**
 * 기본 용어집 초기화 (핸드메이드 관련 기본 용어)
 */
export function initializeDefaultGlossary(): void {
  const existing = getGlossary()
  if (existing.length > 0) return // 이미 데이터가 있으면 스킵
  
  const defaultTerms: Omit<GlossaryItem, 'id' | 'createdAt' | 'updatedAt'>[] = [
    { korean: '수제', english: 'handmade', japanese: 'ハンドメイド', category: '제작/공정' },
    { korean: '가죽', english: 'leather', japanese: 'レザー', category: '소재/재료' },
    { korean: '자개', english: 'mother-of-pearl', japanese: '螺鈿', category: '소재/재료' },
    { korean: '천연', english: 'natural', japanese: '天然', category: '소재/재료' },
    { korean: '작가', english: 'artist', japanese: '作家', category: '기타' },
    { korean: '작품', english: 'handmade creation', japanese: '作品', category: '기타' },
    { korean: '제작 기간', english: 'production time', japanese: '制作期間', category: '제작/공정' },
    { korean: '주문 제작', english: 'made to order', japanese: 'オーダーメイド', category: '제작/공정' },
  ]
  
  defaultTerms.forEach(term => {
    try {
      saveGlossaryItem(term)
    } catch (e) {
      // 중복 무시
    }
  })
}
