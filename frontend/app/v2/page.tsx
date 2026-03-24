'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  loginArtistWeb,
  getSessionStatus,
  getProductList,
  registerBatch,
  getErrorMessage,
  type SessionStatus,
  type ProductSummary,
} from '@/lib/api-v2'
import {
  LogIn,
  Loader2,
  Search,
  CheckCircle2,
  XCircle,
  Globe,
  Package,
  RefreshCw,
  Eye,
  ChevronRight,
} from 'lucide-react'

// ──────────── LoginForm ────────────
function LoginForm({
  onSuccess,
}: {
  onSuccess: () => void
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const result = await loginArtistWeb(email, password)
      if (result.success) {
        onSuccess()
      } else {
        setError(result.message || '로그인에 실패했습니다.')
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-md p-8 bg-white rounded-xl shadow-sm border">
        <div className="text-center mb-6">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center mb-4">
            <Globe className="w-7 h-7 text-white" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">작가웹 로그인</h2>
          <p className="text-sm text-gray-500 mt-1">
            artist.idus.com 계정으로 로그인하세요
          </p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              이메일
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="artist@example.com"
              required
              disabled={loading}
              className="w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none disabled:opacity-50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              비밀번호
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
              className="w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none disabled:opacity-50"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <XCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="w-full py-2.5 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                로그인 중...
              </>
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                로그인
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

// ──────────── GlobalStatusBadge ────────────
function GlobalStatusBadge({ status }: { status: string }) {
  if (status === 'registered' || status === 'selling') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200">
        <CheckCircle2 className="w-3 h-3" />
        등록됨
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-50 text-gray-500 border border-gray-200">
      미등록
    </span>
  )
}

// ──────────── Helpers ────────────
/**
 * 작가웹에서 가져온 title 텍스트에서 가격/수량/후기 등
 * 불필요하게 이어 붙은 부분을 잘라낸다.
 */
function cleanProductTitle(raw: string): string {
  if (!raw) return '(제목 없음)'
  // 가격 패턴(숫자+원) 이후를 모두 제거
  let cleaned = raw.replace(/\s*\d{1,3}(,\d{3})*원[\s\S]*$/, '')
  // 퍼센트 할인 패턴 이후 제거 (예: "19% ...")
  cleaned = cleaned.replace(/\s*\d+%\s*[\s\S]*$/, '')
  // "남은수량", "주문시", "후기", "판" 등이 나오면 그 이전까지만
  cleaned = cleaned.replace(/\s*(남은수량|주문시|후기|판매|리뷰|품절)[\s\S]*$/, '')
  // 양쪽 공백 정리
  cleaned = cleaned.trim()
  return cleaned || raw.trim()
}

// ──────────── ProductCard ────────────
function ProductCard({
  product,
  selected,
  onToggle,
  onClick,
}: {
  product: ProductSummary
  selected: boolean
  onToggle: () => void
  onClick: () => void
}) {
  const [imgError, setImgError] = useState(false)
  const displayTitle = cleanProductTitle(product.title)

  return (
    <div
      onClick={onClick}
      className={`group flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all duration-150 ${
        selected
          ? 'border-orange-300 bg-orange-50/50 shadow-sm'
          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50 hover:shadow-sm'
      }`}
    >
      {/* 체크박스 */}
      <input
        type="checkbox"
        checked={selected}
        onChange={(e) => {
          e.stopPropagation()
          onToggle()
        }}
        onClick={(e) => e.stopPropagation()}
        className="w-4 h-4 rounded border-gray-300 text-orange-500 focus:ring-orange-500 shrink-0"
      />

      {/* 썸네일 */}
      <div className="w-16 h-16 rounded-xl bg-gray-100 overflow-hidden shrink-0 border border-gray-200">
        {product.thumbnail_url && !imgError ? (
          <img
            src={product.thumbnail_url}
            alt={displayTitle}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
            <Package className="w-6 h-6 text-gray-300" />
          </div>
        )}
      </div>

      {/* 작품 정보 */}
      <div className="flex-1 min-w-0">
        <p
          className="text-sm font-medium text-gray-900 line-clamp-2 leading-snug"
          title={product.title}
        >
          {displayTitle}
        </p>
        <div className="flex items-center gap-2 mt-1.5">
          {product.price > 0 && (
            <span className="text-sm font-semibold text-gray-800">
              {product.price.toLocaleString()}
              <span className="text-xs font-normal text-gray-500">원</span>
            </span>
          )}
          <GlobalStatusBadge status={product.global_status} />
        </div>
      </div>

      {/* 상세 보기 버튼 */}
      <div
        className="p-2 rounded-lg text-gray-300 group-hover:text-gray-500 group-hover:bg-gray-100 transition-colors shrink-0"
      >
        <ChevronRight className="w-4 h-4" />
      </div>
    </div>
  )
}

// ──────────── Main Dashboard ────────────
export default function V2DashboardPage() {
  const router = useRouter()
  const [session, setSession] = useState<SessionStatus | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)
  const [products, setProducts] = useState<ProductSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<'selling' | 'paused'>('selling')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchResult, setBatchResult] = useState<string | null>(null)

  // 세션 확인
  useEffect(() => {
    getSessionStatus()
      .then((s) => {
        setSession(s)
        if (s.authenticated) loadProducts()
      })
      .catch(() => setSession({ authenticated: false }))
      .finally(() => setCheckingSession(false))
  }, [])

  const loadProducts = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getProductList(statusFilter)
      setProducts(result.products || [])
    } catch (err) {
      console.error('작품 목록 로드 실패:', err)
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    if (session?.authenticated) loadProducts()
  }, [statusFilter, session?.authenticated, loadProducts])

  const handleLoginSuccess = () => {
    setSession({ authenticated: true })
    loadProducts()
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredProducts.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredProducts.map((p) => p.product_id)))
    }
  }

  const handleBatchRegister = async () => {
    if (selectedIds.size === 0) return
    setBatchLoading(true)
    setBatchResult(null)
    try {
      const result = await registerBatch(Array.from(selectedIds))
      setBatchResult(result.message)
    } catch (err) {
      setBatchResult(`오류: ${getErrorMessage(err)}`)
    } finally {
      setBatchLoading(false)
    }
  }

  // 검색 필터링
  const filteredProducts = products.filter((p) =>
    searchQuery ? p.title.toLowerCase().includes(searchQuery.toLowerCase()) : true
  )

  // 로딩 중
  if (checkingSession) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
      </div>
    )
  }

  // 미인증
  if (!session?.authenticated) {
    return <LoginForm onSuccess={handleLoginSuccess} />
  }

  // 인증 후 대시보드
  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">내 작품</h1>
          <p className="text-sm text-gray-500 mt-1">
            글로벌 탭에 등록할 작품을 선택하세요
          </p>
        </div>
        <button
          onClick={loadProducts}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          새로고침
        </button>
      </div>

      {/* 필터바 */}
      <div className="flex items-center gap-3 mb-4">
        {/* 상태 탭 */}
        <div className="flex rounded-lg border overflow-hidden">
          <button
            onClick={() => setStatusFilter('selling')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              statusFilter === 'selling'
                ? 'bg-orange-500 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            판매중
          </button>
          <button
            onClick={() => setStatusFilter('paused')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              statusFilter === 'paused'
                ? 'bg-orange-500 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            일시중지
          </button>
        </div>

        {/* 검색 */}
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="작품명 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
          />
        </div>
      </div>

      {/* 전체 선택 / 선택 정보 */}
      <div className="flex items-center justify-between mb-3">
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={
              filteredProducts.length > 0 &&
              selectedIds.size === filteredProducts.length
            }
            onChange={toggleSelectAll}
            className="w-4 h-4 rounded border-gray-300 text-orange-500 focus:ring-orange-500"
          />
          전체 선택 ({filteredProducts.length}개)
        </label>
        {selectedIds.size > 0 && (
          <span className="text-sm text-orange-600 font-medium">
            {selectedIds.size}개 선택됨
          </span>
        )}
      </div>

      {/* 작품 목록 */}
      <div className="space-y-2 mb-6">
        {loading ? (
          <div className="text-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-orange-500 mx-auto mb-2" />
            <p className="text-sm text-gray-500">작품 목록 불러오는 중...</p>
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Package className="w-10 h-10 mx-auto mb-2 text-gray-300" />
            <p className="text-sm">
              {searchQuery
                ? '검색 결과가 없습니다.'
                : '등록된 작품이 없습니다.'}
            </p>
          </div>
        ) : (
          filteredProducts.map((product) => (
            <ProductCard
              key={product.product_id}
              product={product}
              selected={selectedIds.has(product.product_id)}
              onToggle={() => toggleSelect(product.product_id)}
              onClick={() =>
                router.push(`/v2/product/${product.product_id}`)
              }
            />
          ))
        )}
      </div>

      {/* 일괄 처리 바 */}
      {selectedIds.size > 0 && (
        <div className="sticky bottom-4 p-4 bg-white border rounded-xl shadow-lg flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900">
              {selectedIds.size}개 작품 선택됨
            </p>
            <p className="text-xs text-gray-500">
              번역 후 글로벌 탭에 임시저장됩니다
            </p>
          </div>
          <button
            onClick={handleBatchRegister}
            disabled={batchLoading}
            className="flex items-center gap-2 px-5 py-2.5 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {batchLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                처리 중...
              </>
            ) : (
              <>
                <Globe className="w-4 h-4" />
                일괄 GB 등록
              </>
            )}
          </button>
        </div>
      )}

      {/* 일괄 처리 결과 */}
      {batchResult && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
          {batchResult}
        </div>
      )}
    </div>
  )
}
