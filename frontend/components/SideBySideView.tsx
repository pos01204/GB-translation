'use client'

import { useState } from 'react'
import { Edit3, Check, X, Copy, CheckCheck } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { copyToClipboard } from '@/lib/utils'

interface SideBySideViewProps {
  originalTitle: string
  originalContent: string
  translatedTitle: string
  translatedContent: string
  onEditTitle?: (newTitle: string) => void
  onEditContent?: (newContent: string) => void
  label?: {
    original: string
    translated: string
  }
}

export function SideBySideView({
  originalTitle,
  originalContent,
  translatedTitle,
  translatedContent,
  onEditTitle,
  onEditContent,
  label = { original: '원본 (한국어)', translated: '번역본' }
}: SideBySideViewProps) {
  const [editingTitle, setEditingTitle] = useState(false)
  const [editingContent, setEditingContent] = useState(false)
  const [editedTitle, setEditedTitle] = useState(translatedTitle)
  const [editedContent, setEditedContent] = useState(translatedContent)
  const [copiedTitle, setCopiedTitle] = useState(false)
  const [copiedContent, setCopiedContent] = useState(false)

  const handleSaveTitle = () => {
    onEditTitle?.(editedTitle)
    setEditingTitle(false)
  }

  const handleSaveContent = () => {
    onEditContent?.(editedContent)
    setEditingContent(false)
  }

  const handleCancelTitle = () => {
    setEditedTitle(translatedTitle)
    setEditingTitle(false)
  }

  const handleCancelContent = () => {
    setEditedContent(translatedContent)
    setEditingContent(false)
  }

  const handleCopy = async (text: string, type: 'title' | 'content') => {
    const success = await copyToClipboard(text)
    if (success) {
      if (type === 'title') {
        setCopiedTitle(true)
        setTimeout(() => setCopiedTitle(false), 2000)
      } else {
        setCopiedContent(true)
        setTimeout(() => setCopiedContent(false), 2000)
      }
    }
  }

  return (
    <div className="split-view">
      {/* 원본 (한국어) */}
      <Card className="h-fit">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <CardTitle className="text-base">{label.original}</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 원본 제목 */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">상품명</label>
            <div className="p-3 bg-muted rounded-lg">
              <p className="font-semibold">{originalTitle}</p>
            </div>
          </div>
          
          {/* 원본 설명 */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">상품 설명</label>
            <div className="p-3 bg-muted rounded-lg max-h-[300px] overflow-y-auto">
              <p className="text-sm whitespace-pre-wrap">{originalContent}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 번역본 */}
      <Card className="h-fit border-primary/30">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-primary" />
              <CardTitle className="text-base">{label.translated}</CardTitle>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 번역 제목 */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-muted-foreground">상품명</label>
              <div className="flex items-center gap-1">
                {!editingTitle && (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2"
                      onClick={() => handleCopy(editedTitle, 'title')}
                    >
                      {copiedTitle ? <CheckCheck className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2"
                      onClick={() => setEditingTitle(true)}
                    >
                      <Edit3 className="w-3 h-3" />
                    </Button>
                  </>
                )}
              </div>
            </div>
            
            {editingTitle ? (
              <div className="space-y-2">
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="w-full p-3 rounded-lg border border-primary bg-background font-semibold focus:ring-2 focus:ring-primary focus:outline-none"
                  autoFocus
                />
                <div className="flex gap-2 justify-end">
                  <Button variant="ghost" size="sm" onClick={handleCancelTitle}>
                    <X className="w-4 h-4 mr-1" /> 취소
                  </Button>
                  <Button size="sm" onClick={handleSaveTitle}>
                    <Check className="w-4 h-4 mr-1" /> 저장
                  </Button>
                </div>
              </div>
            ) : (
              <div 
                className="p-3 bg-primary/5 border border-primary/20 rounded-lg cursor-pointer hover:bg-primary/10 transition-colors"
                onClick={() => setEditingTitle(true)}
              >
                <p className="font-semibold">{editedTitle}</p>
              </div>
            )}
          </div>
          
          {/* 번역 설명 */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-muted-foreground">상품 설명</label>
              <div className="flex items-center gap-1">
                {!editingContent && (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2"
                      onClick={() => handleCopy(editedContent, 'content')}
                    >
                      {copiedContent ? <CheckCheck className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2"
                      onClick={() => setEditingContent(true)}
                    >
                      <Edit3 className="w-3 h-3" />
                    </Button>
                  </>
                )}
              </div>
            </div>
            
            {editingContent ? (
              <div className="space-y-2">
                <Textarea
                  value={editedContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  className="min-h-[200px] border-primary"
                  autoFocus
                />
                <div className="flex gap-2 justify-end">
                  <Button variant="ghost" size="sm" onClick={handleCancelContent}>
                    <X className="w-4 h-4 mr-1" /> 취소
                  </Button>
                  <Button size="sm" onClick={handleSaveContent}>
                    <Check className="w-4 h-4 mr-1" /> 저장
                  </Button>
                </div>
              </div>
            ) : (
              <div 
                className="p-3 bg-primary/5 border border-primary/20 rounded-lg max-h-[300px] overflow-y-auto cursor-pointer hover:bg-primary/10 transition-colors"
                onClick={() => setEditingContent(true)}
              >
                <p className="text-sm whitespace-pre-wrap">{editedContent}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

