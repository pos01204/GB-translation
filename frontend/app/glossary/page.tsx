'use client'

import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { GlossaryManager } from '@/components/GlossaryManager'

export default function GlossaryPage() {
  return (
    <div className="container mx-auto max-w-4xl px-4 py-8">
      {/* 헤더 */}
      <div className="flex items-center gap-4 mb-8">
        <Link href="/">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">용어집</h1>
          <p className="text-sm text-muted-foreground">
            자주 사용하는 용어를 관리하고 일관된 번역을 유지합니다
          </p>
        </div>
      </div>

      {/* 용어집 관리자 */}
      <GlossaryManager />
      
      {/* 사용 안내 */}
      <div className="mt-8 p-4 bg-muted/30 rounded-lg">
        <h3 className="font-medium mb-2">💡 사용 팁</h3>
        <ul className="text-sm text-muted-foreground space-y-1">
          <li>• 자주 사용하는 소재명, 기법명 등을 등록하세요</li>
          <li>• 카테고리별로 분류하여 관리할 수 있습니다</li>
          <li>• JSON 파일로 내보내기/가져오기가 가능합니다</li>
          <li>• 등록된 용어는 향후 번역 시 참고됩니다</li>
        </ul>
      </div>
    </div>
  )
}
