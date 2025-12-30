'use client'

import { useState } from 'react'
import { ImageIcon, Edit3, Check, X, Copy, CheckCheck, ChevronDown, ChevronUp } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { copyToClipboard } from '@/lib/utils'
import type { ImageText } from '@/lib/api'

interface ImageOcrResultsProps {
  imageTexts: ImageText[]
  onEditTranslation?: (index: number, newText: string) => void
}

export function ImageOcrResults({ imageTexts, onEditTranslation }: ImageOcrResultsProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(0)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editedText, setEditedText] = useState('')
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  if (!imageTexts.length) {
    return null
  }

  const handleEdit = (index: number, currentText: string) => {
    setEditingIndex(index)
    setEditedText(currentText)
  }

  const handleSave = () => {
    if (editingIndex !== null) {
      onEditTranslation?.(editingIndex, editedText)
    }
    setEditingIndex(null)
    setEditedText('')
  }

  const handleCancel = () => {
    setEditingIndex(null)
    setEditedText('')
  }

  const handleCopy = async (text: string, index: number) => {
    const success = await copyToClipboard(text)
    if (success) {
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
    }
  }

  const toggleExpand = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index)
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <ImageIcon className="w-4 h-4 text-primary" />
          이미지 OCR 결과
          <span className="text-xs font-normal text-muted-foreground">
            ({imageTexts.length}개 이미지)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {imageTexts.map((item, index) => {
          const isExpanded = expandedIndex === index
          const isEditing = editingIndex === index

          return (
            <div
              key={index}
              className="border rounded-lg overflow-hidden transition-all duration-200"
            >
              {/* 헤더 (클릭하여 확장/축소) */}
              <button
                onClick={() => toggleExpand(index)}
                className="w-full px-4 py-3 flex items-center justify-between bg-muted/50 hover:bg-muted transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded bg-muted flex items-center justify-center overflow-hidden">
                    <img
                      src={item.image_url}
                      alt={`이미지 ${index + 1}`}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none'
                      }}
                    />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium">이미지 {index + 1}</p>
                    <p className="text-xs text-muted-foreground truncate max-w-[300px]">
                      {item.original_text.slice(0, 50)}...
                    </p>
                  </div>
                </div>
                {isExpanded ? (
                  <ChevronUp className="w-5 h-5 text-muted-foreground" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-muted-foreground" />
                )}
              </button>

              {/* 확장된 내용 */}
              {isExpanded && (
                <div className="p-4 space-y-4 animate-fade-in">
                  {/* 이미지 미리보기 */}
                  <div className="rounded-lg overflow-hidden bg-muted max-h-[200px] flex items-center justify-center">
                    <img
                      src={item.image_url}
                      alt={`상세 이미지 ${index + 1}`}
                      className="max-h-[200px] object-contain"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = '/placeholder-image.png'
                      }}
                    />
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {/* 원본 텍스트 */}
                    <div className="space-y-2">
                      <label className="text-xs font-medium text-muted-foreground flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                        추출된 원본 텍스트
                      </label>
                      <div className="p-3 bg-muted rounded-lg max-h-[200px] overflow-y-auto">
                        <p className="text-sm whitespace-pre-wrap">{item.original_text}</p>
                      </div>
                    </div>

                    {/* 번역된 텍스트 */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-medium text-muted-foreground flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-primary" />
                          번역 결과
                        </label>
                        {!isEditing && (
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2"
                              onClick={() => item.translated_text && handleCopy(item.translated_text, index)}
                            >
                              {copiedIndex === index ? (
                                <CheckCheck className="w-3 h-3 text-green-500" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2"
                              onClick={() => handleEdit(index, item.translated_text || '')}
                            >
                              <Edit3 className="w-3 h-3" />
                            </Button>
                          </div>
                        )}
                      </div>

                      {isEditing ? (
                        <div className="space-y-2">
                          <Textarea
                            value={editedText}
                            onChange={(e) => setEditedText(e.target.value)}
                            className="min-h-[150px] border-primary"
                            autoFocus
                          />
                          <div className="flex gap-2 justify-end">
                            <Button variant="ghost" size="sm" onClick={handleCancel}>
                              <X className="w-4 h-4 mr-1" /> 취소
                            </Button>
                            <Button size="sm" onClick={handleSave}>
                              <Check className="w-4 h-4 mr-1" /> 저장
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div 
                          className="p-3 bg-primary/5 border border-primary/20 rounded-lg max-h-[200px] overflow-y-auto cursor-pointer hover:bg-primary/10 transition-colors"
                          onClick={() => handleEdit(index, item.translated_text || '')}
                        >
                          <p className="text-sm whitespace-pre-wrap">
                            {item.translated_text || '번역 결과 없음'}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

