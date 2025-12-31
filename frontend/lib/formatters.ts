/**
 * 번역 결과 포맷터 유틸리티
 * 다양한 형식으로 번역 결과를 변환
 */

import type { TranslatedProduct, ProductData, TargetLanguage, ImageText } from './api'

/**
 * 언어별 표시 이름
 */
function getLanguageLabel(lang: TargetLanguage): string {
  return lang === 'ja' ? '日本語' : 'English'
}

/**
 * OCR 결과를 순서대로 정렬
 */
function sortOcrResults(imageTexts: ImageText[]): ImageText[] {
  return [...imageTexts].sort((a, b) => {
    const orderA = a.order_index ?? 999
    const orderB = b.order_index ?? 999
    return orderA - orderB
  })
}

/**
 * 구조화된 전체 텍스트 생성 (복사/붙여넣기용)
 */
export function formatStructuredText(data: TranslatedProduct): string {
  const lang = getLanguageLabel(data.target_language)
  const lines: string[] = []
  
  // 구분선
  const divider = '═'.repeat(50)
  
  // 제목
  lines.push(divider)
  lines.push('📦 상품명 / Product Title')
  lines.push(divider)
  lines.push(`[한국어] ${data.original.title}`)
  lines.push(`[${lang}] ${data.translated_title}`)
  lines.push('')
  
  // 설명
  lines.push(divider)
  lines.push('📝 상품 설명 / Description')
  lines.push(divider)
  lines.push(data.translated_description)
  lines.push('')
  
  // 옵션
  if (data.translated_options.length > 0) {
    lines.push(divider)
    lines.push('🏷️ 옵션 / Options')
    lines.push(divider)
    data.translated_options.forEach(opt => {
      lines.push(`• ${opt.name}: ${opt.values.join(' / ')}`)
    })
    lines.push('')
  }
  
  // OCR 결과 (순서대로)
  if (data.translated_image_texts.length > 0) {
    lines.push(divider)
    lines.push('🖼️ 이미지 텍스트 / Image Text (순서대로)')
    lines.push(divider)
    
    const sortedOcr = sortOcrResults(data.translated_image_texts)
    sortedOcr.forEach((imgText, idx) => {
      lines.push('')
      lines.push(`[이미지 ${idx + 1}]`)
      lines.push(`원문: ${imgText.original_text}`)
      lines.push(`번역: ${imgText.translated_text || 'N/A'}`)
    })
  }
  
  return lines.join('\n')
}

/**
 * 아이디어스 글로벌 등록용 포맷 (일본어)
 */
export function formatIdusJapanese(data: TranslatedProduct): string {
  const lines: string[] = []
  
  // 작품 소개
  lines.push('[作品紹介]')
  lines.push(data.translated_description)
  lines.push('')
  
  // 옵션이 있으면 추가
  if (data.translated_options.length > 0) {
    lines.push('[オプション]')
    data.translated_options.forEach(opt => {
      lines.push(`・${opt.name}: ${opt.values.join('・')}`)
    })
    lines.push('')
  }
  
  // 이미지 텍스트 (순서대로)
  if (data.translated_image_texts.length > 0) {
    lines.push('[詳細情報]')
    const sortedOcr = sortOcrResults(data.translated_image_texts)
    sortedOcr.forEach(imgText => {
      if (imgText.translated_text) {
        lines.push(imgText.translated_text)
        lines.push('')
      }
    })
  }
  
  // 필수 문구
  lines.push('もし作品の制作時間や詳細について知りたい場合は、アイディアス(idus)アプリのメッセージ機能を通じてご連絡ください。')
  
  return lines.join('\n')
}

/**
 * 아이디어스 글로벌 등록용 포맷 (영어)
 */
export function formatIdusEnglish(data: TranslatedProduct): string {
  const lines: string[] = []
  
  // 작품 설명
  lines.push('[Item Description]')
  lines.push(data.translated_description)
  lines.push('')
  
  // 옵션
  if (data.translated_options.length > 0) {
    lines.push('[Item Details]')
    data.translated_options.forEach(opt => {
      lines.push(`- ${opt.name}: ${opt.values.join(', ')}`)
    })
    lines.push('')
  }
  
  // 이미지 텍스트 (순서대로)
  if (data.translated_image_texts.length > 0) {
    lines.push('[Additional Information]')
    const sortedOcr = sortOcrResults(data.translated_image_texts)
    sortedOcr.forEach(imgText => {
      if (imgText.translated_text) {
        lines.push(imgText.translated_text)
        lines.push('')
      }
    })
  }
  
  // 배송 정보
  lines.push('[Shipping Information]')
  lines.push('International delivery time may vary depending on your location.')
  lines.push('On average, delivery takes about 2 weeks after shipping.')
  lines.push('For details, please contact via the message function on the idus app.')
  
  return lines.join('\n')
}

/**
 * 아이디어스 글로벌 포맷 (언어 자동 감지)
 */
export function formatIdusGlobal(data: TranslatedProduct): string {
  if (data.target_language === 'ja') {
    return formatIdusJapanese(data)
  }
  return formatIdusEnglish(data)
}

/**
 * 제목만 추출
 */
export function formatTitleOnly(data: TranslatedProduct): string {
  return data.translated_title
}

/**
 * 설명만 추출
 */
export function formatDescriptionOnly(data: TranslatedProduct): string {
  return data.translated_description
}

/**
 * 옵션만 추출
 */
export function formatOptionsOnly(data: TranslatedProduct): string {
  if (data.translated_options.length === 0) {
    return ''
  }
  
  return data.translated_options
    .map(opt => `${opt.name}: ${opt.values.join(', ')}`)
    .join('\n')
}

/**
 * OCR 결과만 추출 (순서대로)
 */
export function formatOcrOnly(data: TranslatedProduct): string {
  if (data.translated_image_texts.length === 0) {
    return ''
  }
  
  const sortedOcr = sortOcrResults(data.translated_image_texts)
  
  return sortedOcr
    .map((imgText, idx) => {
      return `[이미지 ${idx + 1}]\n${imgText.translated_text || imgText.original_text}`
    })
    .join('\n\n')
}

/**
 * JSON 내보내기용 데이터 생성
 */
export function formatExportJson(
  data: TranslatedProduct, 
  originalData: ProductData
): string {
  const exportData = {
    original: {
      title: originalData.title,
      description: originalData.description,
      artist_name: originalData.artist_name,
      price: originalData.price,
      options: originalData.options,
      image_count: originalData.detail_images.length,
    },
    translated: {
      title: data.translated_title,
      description: data.translated_description,
      options: data.translated_options,
      image_texts: sortOcrResults(data.translated_image_texts).map((t, idx) => ({
        order: idx + 1,
        original: t.original_text,
        translated: t.translated_text,
      })),
    },
    target_language: data.target_language,
    exported_at: new Date().toISOString(),
  }
  
  return JSON.stringify(exportData, null, 2)
}

/**
 * TXT 파일 다운로드
 */
export function downloadTxt(data: TranslatedProduct, filename?: string): void {
  const content = formatStructuredText(data)
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `idus-translation-${data.target_language}-${Date.now()}.txt`
  a.click()
  
  URL.revokeObjectURL(url)
}

/**
 * JSON 파일 다운로드
 */
export function downloadJson(
  data: TranslatedProduct, 
  originalData: ProductData,
  filename?: string
): void {
  const content = formatExportJson(data, originalData)
  const blob = new Blob([content], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `idus-translation-${data.target_language}-${Date.now()}.json`
  a.click()
  
  URL.revokeObjectURL(url)
}

/**
 * 클립보드에 복사
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (err) {
    console.error('클립보드 복사 실패:', err)
    return false
  }
}
