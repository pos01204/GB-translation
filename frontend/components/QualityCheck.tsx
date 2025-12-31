'use client'

import { useMemo, useState } from 'react'
import { AlertCircle, AlertTriangle, Info, CheckCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  checkTranslationQuality,
  getGradeColor,
  getIssueColor,
  type QualityCheckResult,
  type QualityIssue,
} from '@/lib/quality-check'
import type { TranslatedProduct } from '@/lib/api'

interface QualityCheckProps {
  data: TranslatedProduct
}

function IssueIcon({ type }: { type: QualityIssue['type'] }) {
  const className = cn('w-4 h-4', getIssueColor(type))
  
  switch (type) {
    case 'error':
      return <AlertCircle className={className} />
    case 'warning':
      return <AlertTriangle className={className} />
    case 'info':
      return <Info className={className} />
    default:
      return <Info className={className} />
  }
}

export function QualityCheck({ data }: QualityCheckProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  
  const result = useMemo<QualityCheckResult>(() => {
    return checkTranslationQuality(data)
  }, [data])

  const hasIssues = result.issues.length > 0
  const errorCount = result.issues.filter(i => i.type === 'error').length
  const warningCount = result.issues.filter(i => i.type === 'warning').length

  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* 등급 배지 */}
            <div className={cn(
              'w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg',
              getGradeColor(result.grade)
            )}>
              {result.grade}
            </div>
            
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                번역 품질 검증
                <span className="text-sm font-normal text-muted-foreground">
                  {result.score}점
                </span>
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {result.summary}
              </p>
            </div>
          </div>
          
          {hasIssues && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="gap-1"
            >
              {errorCount > 0 && (
                <span className="flex items-center gap-1 text-red-500">
                  <AlertCircle className="w-3 h-3" />
                  {errorCount}
                </span>
              )}
              {warningCount > 0 && (
                <span className="flex items-center gap-1 text-yellow-500 ml-1">
                  <AlertTriangle className="w-3 h-3" />
                  {warningCount}
                </span>
              )}
              {isExpanded ? (
                <ChevronUp className="w-4 h-4 ml-1" />
              ) : (
                <ChevronDown className="w-4 h-4 ml-1" />
              )}
            </Button>
          )}
          
          {!hasIssues && (
            <div className="flex items-center gap-1 text-green-600">
              <CheckCircle className="w-5 h-5" />
              <span className="text-sm">문제 없음</span>
            </div>
          )}
        </div>
      </CardHeader>
      
      {isExpanded && hasIssues && (
        <CardContent className="pt-2">
          <div className="space-y-2">
            {result.issues.map((issue, idx) => (
              <div
                key={idx}
                className={cn(
                  'p-3 rounded-lg border',
                  issue.type === 'error' && 'bg-red-50 border-red-200',
                  issue.type === 'warning' && 'bg-yellow-50 border-yellow-200',
                  issue.type === 'info' && 'bg-blue-50 border-blue-200'
                )}
              >
                <div className="flex items-start gap-2">
                  <IssueIcon type={issue.type} />
                  <div className="flex-1">
                    <p className="text-sm font-medium">{issue.message}</p>
                    {issue.suggestion && (
                      <p className="text-xs text-muted-foreground mt-1">
                        💡 {issue.suggestion}
                      </p>
                    )}
                    <span className="text-xs text-muted-foreground mt-1 inline-block bg-muted px-1.5 py-0.5 rounded">
                      {issue.field}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      )}
    </Card>
  )
}
