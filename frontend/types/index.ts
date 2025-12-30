/**
 * Frontend 타입 정의
 */

// API 타입 re-export
export type {
  TargetLanguage,
  ProductOption,
  ImageText,
  ProductData,
  TranslatedProduct,
  ScrapeResponse,
  TranslateResponse,
  HealthResponse,
} from '@/lib/api'

// ============ UI State Types ============

/**
 * 앱 전체 상태
 */
export type AppStatus = 
  | 'idle'           // 초기 상태
  | 'scraping'       // 크롤링 중
  | 'scraped'        // 크롤링 완료
  | 'translating'    // 번역 중
  | 'completed'      // 번역 완료
  | 'error'          // 에러 발생

/**
 * 편집 가능한 번역 필드
 */
export interface EditableTranslation {
  title: string
  description: string
  options: Array<{
    name: string
    values: string[]
  }>
  imageTexts: Array<{
    imageUrl: string
    originalText: string
    translatedText: string
  }>
}

/**
 * 편집 상태 추적
 */
export interface EditState {
  isEditing: boolean
  editedFields: Set<string>
  hasChanges: boolean
}

// ============ Component Props Types ============

/**
 * URL 입력 폼 Props
 */
export interface UrlInputFormProps {
  onSubmit: (url: string, language: 'en' | 'ja') => void
  isLoading: boolean
  disabled?: boolean
}

/**
 * 언어 선택 Props
 */
export interface LanguageSelectorProps {
  value: 'en' | 'ja'
  onChange: (value: 'en' | 'ja') => void
  disabled?: boolean
}

/**
 * Side-by-Side 뷰 Props
 */
export interface SideBySideViewProps {
  original: {
    title: string
    content: string
  }
  translated: {
    title: string
    content: string
  }
  onEdit?: (newContent: string) => void
  isEditable?: boolean
}

/**
 * 이미지 OCR 결과 Props
 */
export interface ImageOcrResultProps {
  imageUrl: string
  originalText: string
  translatedText: string
  onEditTranslation?: (newText: string) => void
}

/**
 * 옵션 테이블 Props
 */
export interface OptionTableProps {
  originalOptions: Array<{
    name: string
    values: string[]
  }>
  translatedOptions: Array<{
    name: string
    values: string[]
  }>
  onEditOption?: (index: number, newValues: string[]) => void
}

