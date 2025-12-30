'use client'

import { Loader2, Search, Languages, ImageIcon, CheckCircle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

type LoadingStep = 'scraping' | 'translating' | 'ocr' | 'complete'

interface LoadingStateProps {
  currentStep: LoadingStep
  message?: string
}

const steps = [
  { id: 'scraping', label: '크롤링 중', icon: Search, description: '상품 정보를 수집하고 있습니다...' },
  { id: 'translating', label: '번역 중', icon: Languages, description: '텍스트를 번역하고 있습니다...' },
  { id: 'ocr', label: 'OCR 처리', icon: ImageIcon, description: '이미지 내 텍스트를 추출 중입니다...' },
  { id: 'complete', label: '완료', icon: CheckCircle, description: '번역이 완료되었습니다!' },
]

export function LoadingState({ currentStep, message }: LoadingStateProps) {
  const currentIndex = steps.findIndex(s => s.id === currentStep)

  return (
    <Card className="overflow-hidden">
      <CardContent className="pt-8 pb-8">
        {/* 진행 단계 */}
        <div className="flex justify-between items-center mb-8 px-4">
          {steps.map((step, index) => {
            const Icon = step.icon
            const isActive = step.id === currentStep
            const isComplete = index < currentIndex
            const isPending = index > currentIndex

            return (
              <div key={step.id} className="flex flex-col items-center relative">
                {/* 연결선 */}
                {index < steps.length - 1 && (
                  <div
                    className={`absolute top-5 left-1/2 w-full h-0.5 ${
                      isComplete ? 'bg-primary' : 'bg-border'
                    }`}
                    style={{ transform: 'translateX(50%)' }}
                  />
                )}
                
                {/* 아이콘 원 */}
                <div
                  className={`
                    relative z-10 w-10 h-10 rounded-full flex items-center justify-center
                    transition-all duration-300
                    ${isActive ? 'bg-primary text-primary-foreground scale-110' : ''}
                    ${isComplete ? 'bg-primary text-primary-foreground' : ''}
                    ${isPending ? 'bg-muted text-muted-foreground' : ''}
                  `}
                >
                  {isActive ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : isComplete ? (
                    <CheckCircle className="w-5 h-5" />
                  ) : (
                    <Icon className="w-5 h-5" />
                  )}
                </div>
                
                {/* 라벨 */}
                <span
                  className={`
                    mt-2 text-xs font-medium
                    ${isActive ? 'text-primary' : ''}
                    ${isComplete ? 'text-primary' : ''}
                    ${isPending ? 'text-muted-foreground' : ''}
                  `}
                >
                  {step.label}
                </span>
              </div>
            )
          })}
        </div>

        {/* 현재 상태 메시지 */}
        <div className="text-center space-y-4">
          <div className="flex items-center justify-center gap-3">
            <Loader2 className="w-6 h-6 text-primary animate-spin" />
            <span className="text-lg font-medium">
              {steps.find(s => s.id === currentStep)?.description}
            </span>
          </div>
          
          {message && (
            <p className="text-sm text-muted-foreground animate-fade-in">
              {message}
            </p>
          )}

          {/* 팁 */}
          <div className="pt-4">
            <p className="text-xs text-muted-foreground">
              💡 이미지가 많은 상품은 OCR 처리에 시간이 더 소요될 수 있습니다.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

