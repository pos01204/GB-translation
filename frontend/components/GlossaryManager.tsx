'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { 
  Plus, Trash2, Edit3, Check, X, Search, 
  BookOpen, Filter, Download, Upload 
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { toast } from '@/components/ui/toaster'
import {
  getGlossary,
  saveGlossaryItem,
  updateGlossaryItem,
  deleteGlossaryItem,
  searchGlossary,
  GLOSSARY_CATEGORIES,
  initializeDefaultGlossary,
  type GlossaryItem,
} from '@/lib/storage'

interface GlossaryManagerProps {
  onClose?: () => void
}

export function GlossaryManager({ onClose }: GlossaryManagerProps) {
  const [glossary, setGlossary] = useState<GlossaryItem[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [isAdding, setIsAdding] = useState(false)
  
  // 새 항목 폼
  const [newItem, setNewItem] = useState({
    korean: '',
    english: '',
    japanese: '',
    category: GLOSSARY_CATEGORIES[0],
    notes: '',
  })

  // 편집 중인 항목
  const [editItem, setEditItem] = useState<Partial<GlossaryItem>>({})

  // 초기 로드
  useEffect(() => {
    initializeDefaultGlossary()
    setGlossary(getGlossary())
  }, [])

  // 필터링된 용어집
  const filteredGlossary = useMemo(() => {
    let result = glossary

    // 검색 필터
    if (searchQuery) {
      result = searchGlossary(searchQuery)
    }

    // 카테고리 필터
    if (selectedCategory) {
      result = result.filter(item => item.category === selectedCategory)
    }

    return result
  }, [glossary, searchQuery, selectedCategory])

  // 새 항목 추가
  const handleAdd = useCallback(() => {
    if (!newItem.korean || !newItem.english || !newItem.japanese) {
      toast({ 
        title: '입력 오류', 
        description: '한국어, 영어, 일본어를 모두 입력해주세요.',
        variant: 'destructive'
      })
      return
    }

    try {
      saveGlossaryItem(newItem)
      setGlossary(getGlossary())
      setNewItem({
        korean: '',
        english: '',
        japanese: '',
        category: GLOSSARY_CATEGORIES[0],
        notes: '',
      })
      setIsAdding(false)
      toast({ title: '추가 완료', description: '용어가 추가되었습니다.' })
    } catch (error) {
      toast({ 
        title: '추가 실패', 
        description: error instanceof Error ? error.message : '알 수 없는 오류',
        variant: 'destructive'
      })
    }
  }, [newItem])

  // 항목 수정
  const handleUpdate = useCallback(() => {
    if (!editingId || !editItem.korean || !editItem.english || !editItem.japanese) {
      return
    }

    updateGlossaryItem(editingId, editItem)
    setGlossary(getGlossary())
    setEditingId(null)
    setEditItem({})
    toast({ title: '수정 완료', description: '용어가 수정되었습니다.' })
  }, [editingId, editItem])

  // 항목 삭제
  const handleDelete = useCallback((id: string) => {
    if (window.confirm('이 용어를 삭제하시겠습니까?')) {
      deleteGlossaryItem(id)
      setGlossary(getGlossary())
      toast({ title: '삭제 완료', description: '용어가 삭제되었습니다.' })
    }
  }, [])

  // 편집 시작
  const startEdit = useCallback((item: GlossaryItem) => {
    setEditingId(item.id)
    setEditItem({
      korean: item.korean,
      english: item.english,
      japanese: item.japanese,
      category: item.category,
      notes: item.notes,
    })
  }, [])

  // 편집 취소
  const cancelEdit = useCallback(() => {
    setEditingId(null)
    setEditItem({})
  }, [])

  // JSON 내보내기
  const handleExport = useCallback(() => {
    const data = JSON.stringify(glossary, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `idus-glossary-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast({ title: '내보내기 완료', description: 'JSON 파일이 다운로드되었습니다.' })
  }, [glossary])

  // JSON 가져오기
  const handleImport = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const imported = JSON.parse(event.target?.result as string) as GlossaryItem[]
        let addedCount = 0
        
        imported.forEach(item => {
          try {
            saveGlossaryItem({
              korean: item.korean,
              english: item.english,
              japanese: item.japanese,
              category: item.category || GLOSSARY_CATEGORIES[5],
              notes: item.notes,
            })
            addedCount++
          } catch {
            // 중복 무시
          }
        })
        
        setGlossary(getGlossary())
        toast({ 
          title: '가져오기 완료', 
          description: `${addedCount}개 용어가 추가되었습니다.` 
        })
      } catch {
        toast({ 
          title: '가져오기 실패', 
          description: '올바른 JSON 파일이 아닙니다.',
          variant: 'destructive'
        })
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }, [])

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <BookOpen className="w-5 h-5" />
            용어집 관리
            <span className="text-sm font-normal text-muted-foreground">
              ({glossary.length}개)
            </span>
          </CardTitle>
          
          <div className="flex gap-2">
            {/* 내보내기/가져오기 */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  <Download className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleExport}>
                  <Download className="w-4 h-4 mr-2" />
                  JSON 내보내기
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <label className="cursor-pointer">
                    <Upload className="w-4 h-4 mr-2" />
                    JSON 가져오기
                    <input
                      type="file"
                      accept=".json"
                      className="hidden"
                      onChange={handleImport}
                    />
                  </label>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            
            {onClose && (
              <Button variant="ghost" size="sm" onClick={onClose}>
                <X className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
        
        {/* 검색 및 필터 */}
        <div className="flex gap-2 mt-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="용어 검색..."
              className="pl-9"
            />
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon">
                <Filter className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setSelectedCategory(null)}>
                전체
              </DropdownMenuItem>
              {GLOSSARY_CATEGORIES.map(cat => (
                <DropdownMenuItem 
                  key={cat} 
                  onClick={() => setSelectedCategory(cat)}
                >
                  {cat}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          
          <Button onClick={() => setIsAdding(true)} disabled={isAdding}>
            <Plus className="w-4 h-4 mr-1" />
            추가
          </Button>
        </div>
        
        {/* 선택된 카테고리 표시 */}
        {selectedCategory && (
          <div className="flex items-center gap-2 mt-2">
            <span className="text-sm text-muted-foreground">필터:</span>
            <span className="text-sm bg-primary/10 text-primary px-2 py-0.5 rounded">
              {selectedCategory}
            </span>
            <button 
              onClick={() => setSelectedCategory(null)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              ✕
            </button>
          </div>
        )}
      </CardHeader>
      
      <CardContent>
        {/* 새 항목 추가 폼 */}
        {isAdding && (
          <div className="mb-4 p-4 border rounded-lg bg-muted/30 space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">한국어</Label>
                <Input
                  value={newItem.korean}
                  onChange={(e) => setNewItem(prev => ({ ...prev, korean: e.target.value }))}
                  placeholder="한국어"
                />
              </div>
              <div>
                <Label className="text-xs">English</Label>
                <Input
                  value={newItem.english}
                  onChange={(e) => setNewItem(prev => ({ ...prev, english: e.target.value }))}
                  placeholder="English"
                />
              </div>
              <div>
                <Label className="text-xs">日本語</Label>
                <Input
                  value={newItem.japanese}
                  onChange={(e) => setNewItem(prev => ({ ...prev, japanese: e.target.value }))}
                  placeholder="日本語"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">카테고리</Label>
                <select
                  value={newItem.category}
                  onChange={(e) => setNewItem(prev => ({ ...prev, category: e.target.value }))}
                  className="w-full h-10 px-3 rounded-md border bg-background"
                >
                  {GLOSSARY_CATEGORIES.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label className="text-xs">메모 (선택)</Label>
                <Input
                  value={newItem.notes}
                  onChange={(e) => setNewItem(prev => ({ ...prev, notes: e.target.value }))}
                  placeholder="메모"
                />
              </div>
            </div>
            
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setIsAdding(false)}>
                취소
              </Button>
              <Button size="sm" onClick={handleAdd}>
                추가
              </Button>
            </div>
          </div>
        )}
        
        {/* 용어 목록 */}
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {filteredGlossary.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchQuery || selectedCategory 
                ? '검색 결과가 없습니다.' 
                : '등록된 용어가 없습니다.'}
            </div>
          ) : (
            filteredGlossary.map(item => (
              <div
                key={item.id}
                className={cn(
                  "p-3 border rounded-lg",
                  editingId === item.id && "bg-muted/50"
                )}
              >
                {editingId === item.id ? (
                  // 편집 모드
                  <div className="space-y-2">
                    <div className="grid grid-cols-3 gap-2">
                      <Input
                        value={editItem.korean || ''}
                        onChange={(e) => setEditItem(prev => ({ ...prev, korean: e.target.value }))}
                        placeholder="한국어"
                      />
                      <Input
                        value={editItem.english || ''}
                        onChange={(e) => setEditItem(prev => ({ ...prev, english: e.target.value }))}
                        placeholder="English"
                      />
                      <Input
                        value={editItem.japanese || ''}
                        onChange={(e) => setEditItem(prev => ({ ...prev, japanese: e.target.value }))}
                        placeholder="日本語"
                      />
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={cancelEdit}>
                        <X className="w-3 h-3 mr-1" />
                        취소
                      </Button>
                      <Button size="sm" onClick={handleUpdate}>
                        <Check className="w-3 h-3 mr-1" />
                        저장
                      </Button>
                    </div>
                  </div>
                ) : (
                  // 보기 모드
                  <div className="flex items-center gap-3">
                    <div className="flex-1 grid grid-cols-3 gap-2 text-sm">
                      <span className="font-medium">{item.korean}</span>
                      <span className="text-muted-foreground">{item.english}</span>
                      <span className="text-muted-foreground">{item.japanese}</span>
                    </div>
                    
                    <span className="text-xs bg-muted px-2 py-0.5 rounded shrink-0">
                      {item.category}
                    </span>
                    
                    <div className="flex gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => startEdit(item)}
                      >
                        <Edit3 className="w-3 h-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(item.id)}
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}
