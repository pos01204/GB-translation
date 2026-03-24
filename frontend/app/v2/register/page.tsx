'use client'

import { useState } from 'react'
import {
  registerBatch,
  getErrorMessage,
  type BatchProgress,
} from '@/lib/api-v2'
import {
  Globe,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Play,
  Package,
} from 'lucide-react'

// 상태별 아이콘 + 색상
function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="w-4 h-4 text-green-500" />
    case 'failed':
      return <XCircle className="w-4 h-4 text-red-500" />
    case 'navigating':
    case 'reading':
    case 'translating':
    case 'registering':
      return <Loader2 className="w-4 h-4 text-orange-500 animate-spin" />
    default:
      return <AlertCircle className="w-4 h-4 text-gray-300" />
  }
}

function StatusLabel({ status }: { status: string }) {
  const labels: Record<string, string> = {
    pending: '대기',
    navigating: '페이지 이동',
    reading: '데이터 추출',
    translating: '번역 중',
    registering: '등록 중',
    completed: '완료',
    failed: '실패',
  }
  return (
    <span className="text-xs text-gray-600">
      {labels[status] || status}
    </span>
  )
}

export default function RegisterPage() {
  const [productIdsInput, setProductIdsInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<BatchProgress | null>(null)
  const [error, setError] = useState('')

  const handleBatchRegister = async () => {
    const ids = productIdsInput
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)

    if (ids.length === 0) {
      setError('작품 ID를 입력하세요.')
      return
    }

    setLoading(true)
    setError('')
    setProgress(null)

    try {
      const result = await registerBatch(ids)
      if (result.progress) {
        setProgress(result.progress)
      }
      if (!result.success) {
        setError(result.message)
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const successRate = progress
    ? Math.round(progress.success_rate * 100)
    : 0

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* 헤더 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Globe className="w-6 h-6 text-orange-500" />
          GB 등록
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          작품 ID를 입력하여 일괄 글로벌 등록을 실행합니다.
          대시보드에서 작품을 선택해 등록할 수도 있습니다.
        </p>
      </div>

      {/* 입력 */}
      <div className="border rounded-lg p-4 mb-6 bg-white">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          작품 ID 목록 (줄바꿈으로 구분)
        </label>
        <textarea
          value={productIdsInput}
          onChange={(e) => setProductIdsInput(e.target.value)}
          placeholder={`7fda9710-76e4-4825-bcf4-ca94fd719f13\nabc12345-...\n...`}
          rows={5}
          disabled={loading}
          className="w-full px-3 py-2 border rounded-lg text-sm font-mono focus:ring-2 focus:ring-orange-500 outline-none resize-y disabled:opacity-50"
        />
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-gray-400">
            {productIdsInput
              .split('\n')
              .filter((l) => l.trim()).length}
            개 입력됨
          </span>
          <button
            onClick={handleBatchRegister}
            disabled={loading || !productIdsInput.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                처리 중...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                일괄 등록 시작
              </>
            )}
          </button>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
          <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {/* 결과 */}
      {progress && (
        <div className="border rounded-lg overflow-hidden bg-white">
          {/* 요약 바 */}
          <div className="p-4 border-b bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">
                처리 결과
              </span>
              <span className="text-sm text-gray-600">
                {progress.completed + progress.failed} / {progress.total}
              </span>
            </div>
            {/* 프로그레스 바 */}
            <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${
                    ((progress.completed + progress.failed) /
                      Math.max(progress.total, 1)) *
                    100
                  }%`,
                  background:
                    progress.failed > 0
                      ? 'linear-gradient(90deg, #22c55e, #22c55e ' +
                        successRate +
                        '%, #ef4444 ' +
                        successRate +
                        '%)'
                      : '#22c55e',
                }}
              />
            </div>
            <div className="flex gap-4 mt-2 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-green-500" />
                성공: {progress.completed}
              </span>
              <span className="flex items-center gap-1">
                <XCircle className="w-3 h-3 text-red-500" />
                실패: {progress.failed}
              </span>
              <span>성공률: {successRate}%</span>
            </div>
          </div>

          {/* 개별 항목 */}
          <div className="divide-y">
            {progress.items.map((item, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-4 py-3"
              >
                <StatusIcon status={item.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-mono text-gray-700 truncate">
                    {item.product_id}
                  </p>
                  {item.error_message && (
                    <p className="text-xs text-red-500 mt-0.5">
                      {item.error_message}
                    </p>
                  )}
                </div>
                <StatusLabel status={item.status} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 빈 상태 */}
      {!progress && !loading && (
        <div className="text-center py-12 text-gray-400">
          <Package className="w-12 h-12 mx-auto mb-3 text-gray-200" />
          <p className="text-sm">아직 처리 결과가 없습니다.</p>
          <p className="text-xs mt-1">
            위에서 작품 ID를 입력하고 등록을 시작하세요.
          </p>
        </div>
      )}
    </div>
  )
}
