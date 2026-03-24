'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  getDomesticData,
  translatePreview,
  registerSingle,
  getErrorMessage,
  type DomesticProduct,
  type GlobalProductData,
  type LanguageData,
} from '@/lib/api-v2'
import {
  ArrowLeft,
  Loader2,
  Globe,
  Languages,
  Save,
  Send,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Image as ImageIcon,
  Tag,
  FileText,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'

// ──────────── Collapsible Section ────────────
function Section({
  title,
  icon: Icon,
  defaultOpen = true,
  children,
}: {
  title: string
  icon: React.ElementType
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <Icon className="w-4 h-4" />
          {title}
        </span>
        {open ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>
      {open && <div className="p-4">{children}</div>}
    </div>
  )
}

// ──────────── Language Tab Content ────────────
function LanguagePanel({
  lang,
  langData,
  onChange,
}: {
  lang: 'en' | 'ja'
  langData: LanguageData | null
  onChange: (updated: LanguageData) => void
}) {
  if (!langData) {
    return (
      <div className="text-center py-8 text-gray-400">
        <Languages className="w-8 h-8 mx-auto mb-2" />
        <p className="text-sm">번역 미리보기를 실행하세요</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 작품명 */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">
          작품명 ({langData.title.length}/80)
        </label>
        <input
          type="text"
          value={langData.title}
          onChange={(e) =>
            onChange({ ...langData, title: e.target.value.slice(0, 80) })
          }
          maxLength={80}
          className={`w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500 outline-none ${
            langData.title.length > 80
              ? 'border-red-300 focus:ring-red-500'
              : ''
          }`}
        />
      </div>

      {/* 키워드 */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">
          키워드 ({langData.keywords.length}개)
        </label>
        <input
          type="text"
          value={langData.keywords.join(', ')}
          onChange={(e) =>
            onChange({
              ...langData,
              keywords: e.target.value
                .split(',')
                .map((k) => k.trim())
                .filter(Boolean),
            })
          }
          placeholder="keyword1, keyword2, ..."
          className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500 outline-none"
        />
      </div>

      {/* 설명 HTML */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">
          작품 설명 (HTML)
        </label>
        <textarea
          value={langData.description_html}
          onChange={(e) =>
            onChange({ ...langData, description_html: e.target.value })
          }
          rows={8}
          className="w-full px-3 py-2 border rounded-lg text-sm font-mono focus:ring-2 focus:ring-orange-500 outline-none resize-y"
        />
      </div>

      {/* 설명 미리보기 */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">
          미리보기
        </label>
        <div
          className="p-3 border rounded-lg text-sm bg-white prose prose-sm max-w-none"
          dangerouslySetInnerHTML={{ __html: langData.description_html }}
        />
      </div>
    </div>
  )
}

// ──────────── Main Page ────────────
export default function ProductDetailPage() {
  const params = useParams()
  const router = useRouter()
  const productId = params.id as string

  // 국내 데이터
  const [domestic, setDomestic] = useState<DomesticProduct | null>(null)
  const [domesticLoading, setDomesticLoading] = useState(true)
  const [domesticError, setDomesticError] = useState('')

  // 번역 데이터
  const [globalData, setGlobalData] = useState<GlobalProductData | null>(null)
  const [translateLoading, setTranslateLoading] = useState(false)
  const [translateMessage, setTranslateMessage] = useState('')
  const [translateError, setTranslateError] = useState('')

  // 등록
  const [registerLoading, setRegisterLoading] = useState(false)
  const [registerResult, setRegisterResult] = useState<{
    success: boolean
    message: string
  } | null>(null)

  // 언어 탭
  const [activeLang, setActiveLang] = useState<'en' | 'ja'>('en')

  // 국내 데이터 로드
  useEffect(() => {
    if (!productId) return
    setDomesticLoading(true)
    getDomesticData(productId)
      .then((res) => {
        if (res.success) setDomestic(res.data)
        else setDomesticError('국내 데이터를 불러올 수 없습니다.')
      })
      .catch((err) => setDomesticError(getErrorMessage(err)))
      .finally(() => setDomesticLoading(false))
  }, [productId])

  // 번역 미리보기
  const handleTranslate = async () => {
    setTranslateLoading(true)
    setTranslateError('')
    setTranslateMessage('')
    try {
      const result = await translatePreview(productId)
      if (result.success && result.global_data) {
        setGlobalData(result.global_data)
        setTranslateMessage(result.message || '번역 완료')
      } else {
        setTranslateError(result.message || '번역 실패: 결과를 받지 못했습니다.')
      }
    } catch (err) {
      setTranslateError(getErrorMessage(err))
    } finally {
      setTranslateLoading(false)
    }
  }

  // 언어 데이터 업데이트
  const updateLangData = (lang: 'en' | 'ja', updated: LanguageData) => {
    if (!globalData) return
    setGlobalData({ ...globalData, [lang]: updated })
  }

  // GB 등록
  const handleRegister = async (saveAsDraft: boolean) => {
    setRegisterLoading(true)
    setRegisterResult(null)
    try {
      const result = await registerSingle(productId, {
        saveAsDraft,
        globalData: globalData || undefined,
      })
      setRegisterResult({
        success: result.success,
        message: result.message,
      })
    } catch (err) {
      setRegisterResult({
        success: false,
        message: getErrorMessage(err),
      })
    } finally {
      setRegisterLoading(false)
    }
  }

  // 로딩
  if (domesticLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-orange-500 mx-auto mb-2" />
          <p className="text-sm text-gray-500">국내 데이터 불러오는 중...</p>
        </div>
      </div>
    )
  }

  // 에러
  if (domesticError) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <button
          onClick={() => router.push('/v2')}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          목록으로
        </button>
        <div className="p-6 bg-red-50 border border-red-200 rounded-lg text-center">
          <XCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-sm text-red-700">{domesticError}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* 뒤로가기 + 제목 */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push('/v2')}
          className="p-1.5 rounded-md hover:bg-gray-100 transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-gray-500" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-gray-900 truncate">
            {domestic?.title || '작품 상세'}
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">{productId}</p>
        </div>
        {domestic?.category_restricted && (
          <span className="flex items-center gap-1 px-3 py-1 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
            <AlertTriangle className="w-3.5 h-3.5" />
            글로벌 판매 제한
          </span>
        )}
      </div>

      {/* 2컬럼 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 좌측: 국내 원본 */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
            <FileText className="w-4 h-4" />
            국내 원본
          </h2>

          {/* 이미지 */}
          {domestic?.product_images && domestic.product_images.length > 0 && (
            <Section title="작품 이미지" icon={ImageIcon}>
              <div className="grid grid-cols-3 gap-2">
                {domestic.product_images.map((img, i) => (
                  <div
                    key={i}
                    className={`aspect-square rounded-lg overflow-hidden border ${
                      img.is_representative ? 'ring-2 ring-orange-400' : ''
                    }`}
                  >
                    <img
                      src={img.url}
                      alt={`작품 이미지 ${i + 1}`}
                      className="w-full h-full object-cover"
                    />
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* 기본 정보 */}
          <Section title="기본 정보" icon={Tag}>
            <dl className="space-y-2 text-sm">
              <div className="flex">
                <dt className="w-24 text-gray-500 shrink-0">가격</dt>
                <dd className="text-gray-900">
                  {domestic?.price?.toLocaleString()}원
                </dd>
              </div>
              <div className="flex">
                <dt className="w-24 text-gray-500 shrink-0">카테고리</dt>
                <dd className="text-gray-900">{domestic?.category_path}</dd>
              </div>
              <div className="flex">
                <dt className="w-24 text-gray-500 shrink-0">재고</dt>
                <dd className="text-gray-900">{domestic?.quantity}개</dd>
              </div>
              {domestic?.keywords && domestic.keywords.length > 0 && (
                <div className="flex">
                  <dt className="w-24 text-gray-500 shrink-0">키워드</dt>
                  <dd className="flex flex-wrap gap-1">
                    {domestic.keywords.map((kw, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-gray-100 rounded-full text-xs text-gray-600"
                      >
                        {kw}
                      </span>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </Section>

          {/* 작품 설명 */}
          {domestic?.description_html && (
            <Section title="작품 설명" icon={FileText} defaultOpen={false}>
              <div
                className="prose prose-sm max-w-none text-gray-700"
                dangerouslySetInnerHTML={{
                  __html: domestic.description_html,
                }}
              />
            </Section>
          )}

          {/* 옵션 */}
          {domestic?.options && domestic.options.length > 0 && (
            <Section title="옵션" icon={Tag} defaultOpen={false}>
              <div className="space-y-3">
                {domestic.options.map((opt, i) => (
                  <div key={i}>
                    <p className="text-sm font-medium text-gray-700">
                      {opt.name}
                    </p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {opt.values.map((v, j) => (
                        <span
                          key={j}
                          className="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600"
                        >
                          {v.value}
                          {v.additional_price > 0 &&
                            ` (+${v.additional_price.toLocaleString()}원)`}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>

        {/* 우측: 번역 결과 */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Globe className="w-4 h-4" />
              번역 결과
            </h2>
            <button
              onClick={handleTranslate}
              disabled={
                translateLoading || !!domestic?.category_restricted
              }
              className="flex items-center gap-2 px-3 py-1.5 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-300 text-white rounded-lg text-xs font-medium transition-colors"
            >
              {translateLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  번역 중...
                </>
              ) : (
                <>
                  <Languages className="w-3.5 h-3.5" />
                  번역 미리보기
                </>
              )}
            </button>
          </div>

          {/* 에러 */}
          {translateError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-xs text-red-700 flex items-start gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                {translateError}
              </p>
            </div>
          )}

          {/* 성공 메시지 */}
          {translateMessage && !translateError && (
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-xs text-green-700 flex items-start gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                {translateMessage}
              </p>
            </div>
          )}

          {/* 언어 탭 */}
          <div className="flex rounded-lg border overflow-hidden">
            <button
              onClick={() => setActiveLang('en')}
              className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                activeLang === 'en'
                  ? 'bg-orange-500 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              English
            </button>
            <button
              onClick={() => setActiveLang('ja')}
              className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                activeLang === 'ja'
                  ? 'bg-orange-500 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              日本語
            </button>
          </div>

          {/* 번역 편집 패널 */}
          <div className="border rounded-lg p-4 bg-white min-h-[300px]">
            <LanguagePanel
              lang={activeLang}
              langData={globalData?.[activeLang] || null}
              onChange={(updated) => updateLangData(activeLang, updated)}
            />
          </div>

          {/* 글로벌 옵션 */}
          {globalData?.global_options &&
            globalData.global_options.length > 0 && (
              <Section title="글로벌 옵션" icon={Tag} defaultOpen={false}>
                <div className="space-y-3 text-sm">
                  {globalData.global_options.map((opt, i) => (
                    <div
                      key={i}
                      className="p-3 bg-gray-50 rounded-lg space-y-1"
                    >
                      <p className="font-medium text-gray-700">
                        {opt.original_name}
                      </p>
                      <p className="text-xs text-gray-500">
                        EN: {opt.name_en} → [{opt.values_en.join(', ')}]
                      </p>
                      <p className="text-xs text-gray-500">
                        JA: {opt.name_ja} → [{opt.values_ja.join(', ')}]
                      </p>
                    </div>
                  ))}
                </div>
              </Section>
            )}

          {/* 액션 버튼 */}
          {globalData && (
            <div className="flex gap-3">
              <button
                onClick={() => handleRegister(true)}
                disabled={registerLoading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 border-2 border-orange-500 text-orange-600 hover:bg-orange-50 disabled:border-gray-300 disabled:text-gray-400 rounded-lg text-sm font-medium transition-colors"
              >
                {registerLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                임시저장
              </button>
              <button
                onClick={() => handleRegister(false)}
                disabled={registerLoading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {registerLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                판매 등록
              </button>
            </div>
          )}

          {/* 등록 결과 */}
          {registerResult && (
            <div
              className={`p-4 rounded-lg flex items-start gap-2 text-sm ${
                registerResult.success
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-red-50 border border-red-200 text-red-700'
              }`}
            >
              {registerResult.success ? (
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
              )}
              {registerResult.message}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
