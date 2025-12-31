/**
 * 번역 품질 검증 유틸리티
 */

import type { TranslatedProduct, TargetLanguage } from './api'

// 품질 이슈 타입
export interface QualityIssue {
  type: 'warning' | 'error' | 'info'
  category: 'length' | 'numbers' | 'formatting' | 'completeness' | 'terminology'
  message: string
  field: string
  suggestion?: string
}

// 품질 검증 결과
export interface QualityCheckResult {
  score: number // 0-100
  grade: 'A' | 'B' | 'C' | 'D' | 'F'
  issues: QualityIssue[]
  summary: string
}

/**
 * 텍스트에서 숫자 추출
 */
function extractNumbers(text: string): string[] {
  // 숫자 패턴 (정수, 소수, 콤마 포함)
  const matches = text.match(/[\d,]+\.?\d*/g) || []
  return matches.map(n => n.replace(/,/g, ''))
}

/**
 * 텍스트에서 단위 추출
 */
function extractUnits(text: string): string[] {
  const unitPatterns = [
    /\d+\s*(cm|mm|m|kg|g|ml|L|개|장|세트|박스)/gi,
    /\d+\s*(원|₩|엔|¥|\$|달러)/gi,
  ]
  
  const units: string[] = []
  unitPatterns.forEach(pattern => {
    const matches = text.match(pattern) || []
    units.push(...matches)
  })
  
  return units
}

/**
 * 길이 비율 검증
 */
function checkLengthRatio(
  original: string,
  translated: string,
  targetLanguage: TargetLanguage
): QualityIssue | null {
  if (!original || !translated) return null
  
  const ratio = translated.length / original.length
  
  // 언어별 예상 비율
  // 한국어 → 영어: 보통 1.1~1.8배
  // 한국어 → 일본어: 보통 0.8~1.3배
  const expectedRange = targetLanguage === 'en' 
    ? { min: 0.8, max: 2.5 }
    : { min: 0.5, max: 1.8 }
  
  if (ratio < expectedRange.min) {
    return {
      type: 'warning',
      category: 'length',
      message: `번역이 원문보다 너무 짧습니다 (${Math.round(ratio * 100)}%)`,
      field: 'description',
      suggestion: '중요한 내용이 누락되었을 수 있습니다. 원문을 다시 확인해주세요.',
    }
  }
  
  if (ratio > expectedRange.max) {
    return {
      type: 'warning',
      category: 'length',
      message: `번역이 원문보다 너무 깁니다 (${Math.round(ratio * 100)}%)`,
      field: 'description',
      suggestion: '불필요한 내용이 추가되었을 수 있습니다.',
    }
  }
  
  return null
}

/**
 * 숫자 누락 검증
 */
function checkNumberConsistency(
  original: string,
  translated: string
): QualityIssue | null {
  const originalNumbers = extractNumbers(original)
  const translatedNumbers = extractNumbers(translated)
  
  // 원문의 숫자가 번역에 있는지 확인
  const missingNumbers = originalNumbers.filter(
    num => !translatedNumbers.some(tNum => 
      tNum === num || 
      parseFloat(tNum) === parseFloat(num)
    )
  )
  
  if (missingNumbers.length > 0) {
    return {
      type: 'error',
      category: 'numbers',
      message: `숫자 정보가 누락되었을 수 있습니다: ${missingNumbers.slice(0, 3).join(', ')}`,
      field: 'description',
      suggestion: '사이즈, 수량, 가격 등의 숫자 정보를 확인해주세요.',
    }
  }
  
  return null
}

/**
 * 제목 길이 검증
 */
function checkTitleLength(
  translatedTitle: string,
  targetLanguage: TargetLanguage
): QualityIssue | null {
  // 마켓플레이스별 권장 제목 길이
  const maxLength = targetLanguage === 'en' ? 200 : 100
  const minLength = 10
  
  if (translatedTitle.length < minLength) {
    return {
      type: 'warning',
      category: 'length',
      message: '제목이 너무 짧습니다',
      field: 'title',
      suggestion: '검색 최적화를 위해 더 상세한 제목을 권장합니다.',
    }
  }
  
  if (translatedTitle.length > maxLength) {
    return {
      type: 'info',
      category: 'length',
      message: `제목이 권장 길이(${maxLength}자)를 초과합니다`,
      field: 'title',
      suggestion: '일부 마켓플레이스에서 잘릴 수 있습니다.',
    }
  }
  
  return null
}

/**
 * 한국어 잔존 검증
 */
function checkKoreanRemaining(translated: string): QualityIssue | null {
  // 한글 패턴
  const koreanPattern = /[가-힣]/g
  const koreanMatches = translated.match(koreanPattern)
  
  if (koreanMatches && koreanMatches.length > 5) {
    return {
      type: 'error',
      category: 'completeness',
      message: '한국어가 번역되지 않고 남아있습니다',
      field: 'description',
      suggestion: '번역이 완료되지 않은 부분이 있습니다.',
    }
  }
  
  return null
}

/**
 * 옵션 번역 검증
 */
function checkOptionsTranslation(
  originalOptions: { name: string; values: string[] }[],
  translatedOptions: { name: string; values: string[] }[]
): QualityIssue | null {
  if (originalOptions.length !== translatedOptions.length) {
    return {
      type: 'warning',
      category: 'completeness',
      message: '옵션 개수가 원본과 다릅니다',
      field: 'options',
      suggestion: '일부 옵션이 누락되었을 수 있습니다.',
    }
  }
  
  // 옵션값 개수 확인
  for (let i = 0; i < originalOptions.length; i++) {
    if (translatedOptions[i] && 
        originalOptions[i].values.length !== translatedOptions[i].values.length) {
      return {
        type: 'warning',
        category: 'completeness',
        message: `"${originalOptions[i].name}" 옵션의 값 개수가 다릅니다`,
        field: 'options',
        suggestion: '옵션값이 누락되었을 수 있습니다.',
      }
    }
  }
  
  return null
}

/**
 * 전체 품질 검증
 */
export function checkTranslationQuality(
  data: TranslatedProduct
): QualityCheckResult {
  const issues: QualityIssue[] = []
  
  // 1. 제목 검증
  const titleIssue = checkTitleLength(data.translated_title, data.target_language)
  if (titleIssue) issues.push(titleIssue)
  
  // 2. 설명 길이 비율 검증
  const lengthIssue = checkLengthRatio(
    data.original.description,
    data.translated_description,
    data.target_language
  )
  if (lengthIssue) issues.push(lengthIssue)
  
  // 3. 숫자 누락 검증
  const numberIssue = checkNumberConsistency(
    data.original.description,
    data.translated_description
  )
  if (numberIssue) issues.push(numberIssue)
  
  // 4. 한국어 잔존 검증
  const koreanIssue = checkKoreanRemaining(data.translated_description)
  if (koreanIssue) issues.push(koreanIssue)
  
  // 5. 옵션 검증
  const optionIssue = checkOptionsTranslation(
    data.original.options,
    data.translated_options
  )
  if (optionIssue) issues.push(optionIssue)
  
  // 점수 계산
  let score = 100
  issues.forEach(issue => {
    if (issue.type === 'error') score -= 20
    else if (issue.type === 'warning') score -= 10
    else if (issue.type === 'info') score -= 5
  })
  score = Math.max(0, score)
  
  // 등급 결정
  let grade: 'A' | 'B' | 'C' | 'D' | 'F'
  if (score >= 90) grade = 'A'
  else if (score >= 80) grade = 'B'
  else if (score >= 70) grade = 'C'
  else if (score >= 60) grade = 'D'
  else grade = 'F'
  
  // 요약 메시지
  let summary: string
  if (issues.length === 0) {
    summary = '번역 품질이 우수합니다.'
  } else if (issues.filter(i => i.type === 'error').length > 0) {
    summary = '확인이 필요한 문제가 있습니다.'
  } else if (issues.filter(i => i.type === 'warning').length > 0) {
    summary = '일부 개선이 권장됩니다.'
  } else {
    summary = '전반적으로 양호합니다.'
  }
  
  return { score, grade, issues, summary }
}

/**
 * 등급별 색상 반환
 */
export function getGradeColor(grade: string): string {
  switch (grade) {
    case 'A': return 'text-green-600 bg-green-100'
    case 'B': return 'text-blue-600 bg-blue-100'
    case 'C': return 'text-yellow-600 bg-yellow-100'
    case 'D': return 'text-orange-600 bg-orange-100'
    case 'F': return 'text-red-600 bg-red-100'
    default: return 'text-gray-600 bg-gray-100'
  }
}

/**
 * 이슈 타입별 아이콘 색상
 */
export function getIssueColor(type: QualityIssue['type']): string {
  switch (type) {
    case 'error': return 'text-red-500'
    case 'warning': return 'text-yellow-500'
    case 'info': return 'text-blue-500'
    default: return 'text-gray-500'
  }
}
