'use client'

import { useState } from 'react'
import { Edit3, Check, X, Copy, CheckCheck } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { copyToClipboard } from '@/lib/utils'
import type { ProductOption } from '@/lib/api'

interface OptionTableProps {
  originalOptions: ProductOption[]
  translatedOptions: ProductOption[]
  onEditOption?: (index: number, newOption: ProductOption) => void
}

export function OptionTable({ 
  originalOptions, 
  translatedOptions,
  onEditOption 
}: OptionTableProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editedOption, setEditedOption] = useState<ProductOption | null>(null)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  if (!originalOptions.length && !translatedOptions.length) {
    return null
  }

  const handleEdit = (index: number) => {
    setEditingIndex(index)
    setEditedOption({ ...translatedOptions[index] })
  }

  const handleSave = () => {
    if (editingIndex !== null && editedOption) {
      onEditOption?.(editingIndex, editedOption)
    }
    setEditingIndex(null)
    setEditedOption(null)
  }

  const handleCancel = () => {
    setEditingIndex(null)
    setEditedOption(null)
  }

  const handleCopy = async (option: ProductOption, index: number) => {
    const text = `${option.name}: ${option.values.join(', ')}`
    const success = await copyToClipboard(text)
    if (success) {
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500" />
          상품 옵션
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground w-[45%]">
                  원본 (한국어)
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground w-[45%]">
                  번역
                </th>
                <th className="px-4 py-3 text-center font-medium text-muted-foreground w-[10%]">
                  작업
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {originalOptions.map((original, index) => {
                const translated = translatedOptions[index]
                const isEditing = editingIndex === index

                return (
                  <tr key={index} className="hover:bg-muted/50 transition-colors">
                    {/* 원본 */}
                    <td className="px-4 py-3">
                      <div className="space-y-1">
                        <p className="font-medium text-foreground">{original.name}</p>
                        <div className="flex flex-wrap gap-1">
                          {original.values.map((value, vIndex) => (
                            <span
                              key={vIndex}
                              className="px-2 py-0.5 bg-muted rounded text-xs"
                            >
                              {value}
                            </span>
                          ))}
                        </div>
                      </div>
                    </td>

                    {/* 번역 */}
                    <td className="px-4 py-3">
                      {isEditing && editedOption ? (
                        <div className="space-y-2">
                          <input
                            type="text"
                            value={editedOption.name}
                            onChange={(e) => setEditedOption({ 
                              ...editedOption, 
                              name: e.target.value 
                            })}
                            className="w-full px-2 py-1 rounded border text-sm font-medium"
                            placeholder="옵션명"
                          />
                          <input
                            type="text"
                            value={editedOption.values.join(', ')}
                            onChange={(e) => setEditedOption({ 
                              ...editedOption, 
                              values: e.target.value.split(',').map(v => v.trim()) 
                            })}
                            className="w-full px-2 py-1 rounded border text-sm"
                            placeholder="값들 (쉼표로 구분)"
                          />
                        </div>
                      ) : (
                        <div className="space-y-1">
                          <p className="font-medium text-primary">{translated?.name}</p>
                          <div className="flex flex-wrap gap-1">
                            {translated?.values.map((value, vIndex) => (
                              <span
                                key={vIndex}
                                className="px-2 py-0.5 bg-primary/10 text-primary rounded text-xs"
                              >
                                {value}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </td>

                    {/* 작업 버튼 */}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        {isEditing ? (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0"
                              onClick={handleCancel}
                            >
                              <X className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-primary"
                              onClick={handleSave}
                            >
                              <Check className="w-4 h-4" />
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0"
                              onClick={() => translated && handleCopy(translated, index)}
                            >
                              {copiedIndex === index ? (
                                <CheckCheck className="w-4 h-4 text-green-500" />
                              ) : (
                                <Copy className="w-4 h-4" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0"
                              onClick={() => handleEdit(index)}
                            >
                              <Edit3 className="w-4 h-4" />
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

