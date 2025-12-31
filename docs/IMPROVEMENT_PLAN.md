# 🚀 Idus Translator 실무 개선안

> **문서 버전**: v1.0  
> **작성일**: 2024년 12월  
> **목적**: 아이디어스 작품 번역 도구의 실무 활용성 극대화

---

## 📋 목차

1. [현황 분석](#1-현황-분석)
2. [핵심 문제점](#2-핵심-문제점)
3. [개선안 상세](#3-개선안-상세)
   - [3.1 번역 프롬프트 시스템](#31-번역-프롬프트-시스템)
   - [3.2 OCR 순서 정렬](#32-ocr-순서-정렬)
   - [3.3 결과물 구조화](#33-결과물-구조화)
   - [3.4 내보내기 기능](#34-내보내기-기능)
   - [3.5 UI/UX 개선](#35-uiux-개선)
4. [구현 로드맵](#4-구현-로드맵)
5. [기술 명세](#5-기술-명세)

---

## 1. 현황 분석

### 1.1 시스템 구성

```
┌─────────────────────────────────────────────────────────────┐
│                    Idus Translator                          │
├─────────────────────────────────────────────────────────────┤
│  Frontend (Next.js)                                         │
│  ├── URL 입력 → 크롤링 요청                                  │
│  ├── 번역 결과 표시 (탭 구조)                                │
│  └── JSON 다운로드                                          │
├─────────────────────────────────────────────────────────────┤
│  Backend (FastAPI + Playwright)                             │
│  ├── 크롤링: Playwright Stealth                             │
│  ├── 번역: Google Gemini API                                │
│  └── OCR: Gemini Vision                                     │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 현재 기능 수준

| 기능 | 현재 상태 | 실무 활용도 | 개선 필요도 |
|------|----------|------------|------------|
| 크롤링 (텍스트) | ✅ 기본 동작 | ⭐⭐⭐ | 중 |
| 크롤링 (이미지) | ✅ 대량 수집 | ⭐⭐⭐ | 중 |
| 크롤링 (옵션) | ⚠️ 불안정 | ⭐⭐ | 높음 |
| 번역 (텍스트) | ⚠️ 단순 번역 | ⭐⭐ | **매우 높음** |
| 번역 (옵션) | ✅ 기본 동작 | ⭐⭐⭐ | 중 |
| OCR | ⚠️ 순서 불일치 | ⭐ | **매우 높음** |
| 결과 내보내기 | ❌ JSON만 | ⭐ | **매우 높음** |
| 편집 기능 | ⚠️ 제한적 | ⭐⭐ | 높음 |

---

## 2. 핵심 문제점

### 2.1 번역 품질 문제

**현재 프롬프트:**
```python
prompt = f"""Translate this Korean text to {lang}. 
Output only the translation, nothing else.

Korean: {text}

{lang}:"""
```

**문제점:**
- ❌ 아이디어스 플랫폼 맥락 없음
- ❌ 핸드메이드 제품 특성 미반영
- ❌ 한국 시장 전용 콘텐츠 필터링 없음
- ❌ 출력 포맷 구조화 없음
- ❌ 브랜드명/작가명 처리 규칙 없음

### 2.2 OCR 순서 문제

**현재 방식:**
```python
# 이미지 URL을 수집 순서대로 처리
# → 페이지 내 실제 위치와 무관
```

**문제점:**
- ❌ 이미지가 페이지 순서와 다르게 수집됨
- ❌ 어떤 이미지의 텍스트인지 맥락 파악 어려움
- ❌ 결과 재정렬에 수동 작업 필요

### 2.3 결과물 활용 문제

**현재:**
- JSON 파일만 다운로드 가능
- 바로 복사/붙여넣기 불가능
- 마켓플레이스 등록 포맷과 불일치

**필요:**
- 즉시 사용 가능한 구조화된 텍스트
- 플랫폼별 맞춤 포맷
- 원클릭 복사 기능

---

## 3. 개선안 상세

### 3.1 번역 프롬프트 시스템

#### 3.1.1 프롬프트 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                   Prompt Template System                     │
├─────────────────────────────────────────────────────────────┤
│  Base Prompt (공통)                                          │
│  ├── 플랫폼 컨텍스트 (아이디어스 소개)                         │
│  ├── 핸드메이드 제품 특성                                     │
│  └── 공통 제외 항목 (배송, 할인 등)                            │
├─────────────────────────────────────────────────────────────┤
│  Language-Specific Prompt                                    │
│  ├── 일본어: Minne/Creema 스타일, 작家/作品 용어              │
│  └── 영어: 국제 마켓 스타일, artist/creation 용어             │
├─────────────────────────────────────────────────────────────┤
│  Section-Specific Prompt                                     │
│  ├── 제목: 간결하고 검색 최적화                               │
│  ├── 설명: 구조화된 포맷 출력                                 │
│  ├── 옵션: 짧고 명확하게                                      │
│  └── OCR: 원문 보존 + 자연스러운 번역                         │
└─────────────────────────────────────────────────────────────┘
```

#### 3.1.2 일본어 번역 프롬프트 (개선안)

```python
JAPANESE_TRANSLATION_PROMPT = """
あなたはアジア最大のハンドメイドマーケットプレイス「idus（アイディアス）」で商品を販売するオンラインセラーです。

以下のガイドラインに従って、韓国語のコンテンツを日本語に翻訳してください。

## 1. 文体とトーン
- 親しみやすく温かみのある文体で、購入者の心をつかむ
- 原文のトーンと雰囲気を維持
- 作家紹介セクションは [作家紹介] タイトルを使用
- 作家名が明確な場合: [XXXについて] 形式で記載
- 作家名が不明な場合: [作家紹介] セクションを省略

## 2. 除外コンテンツ（韓国市場専用）
以下は翻訳から除外してください：
- 韓国の祝日・季節イベント（추석, 설날 等）
- 価格情報（₩, 원）→「追加料金」に置換
- 配送情報: 배송기간, 무료배송, 배송비, 배송사, 택배사
- 返品・交換ポリシー
- 割引・プロモーション: 팔로우 쿠폰, 적립금, 타임딜 等
- 割引率(%)が記載されている場合 →「特別割引」に置換

## 3. 制作情報
- 制作所要時間（제작 소요 기간）✅ 含める
- 配送期間 ❌ 除外

## 4. プラットフォーム用語
- 販売者 → 作家
- 製品/商品 → ハンドメイド作品 / 作品（商品は使用しない）
- 区切り文字: 「&」→「・」

## 5. 固有名詞・ブランド名
- 韓国語の作家名 → 日本語カタカナに音訳
- 英語の作家名 → 英語のまま
- 韓国語ブランド名 → 日本語カタカナ（英語表記は不可）
  例: 이디엘 → イーディエル（NOT E.D.L）

## 6. 必須追加文
翻訳の最後に必ず以下を追加：
「もし作品の制作時間や詳細について知りたい場合は、アイディアス(idus)アプリのメッセージ機能を通じてご連絡ください。」

## 7. 最終チェック
- 韓国語が残っていないことを確認
- 絵文字・特殊文字は原文のまま維持
- Minne/Creemaの成功セラーのスタイルを参考に

---

翻訳対象テキスト:
{text}

---

日本語翻訳:
"""
```

#### 3.1.3 영어 번역 프롬프트 (개선안)

```python
ENGLISH_TRANSLATION_PROMPT = """
You are an online seller creating a product description for idus (아이디어스), the largest handmade online marketplace in Asia.

Translate the Korean content into English following this structured format:

## Output Format

[About the Artist]
{Artist introduction - only if identifiable from source}

[Item Description]
{Main product description}

[How to Use]
{Usage instructions - only if available in source}

[Item Details]
- Type: {product type}
- Color: {colors}
- Size: {dimensions}
- Materials: {materials}
- Components: {included items}

[Shipping Information]
International delivery time may vary depending on your location.
On average, delivery takes about 2 weeks after shipping.
For details, please contact via the message function on the idus app.

## Translation Guidelines

### Include:
- All product descriptions and features
- Material and craftsmanship details
- Care instructions
- Symbolic meanings and cultural context
- Emojis from original text

### Exclude (Korea-specific content):
- Korean holidays/events (추석, 설날, etc.)
- Prices in Won (₩, 원) → Replace with "additional charges"
- Shipping details: 배송기간, 무료배송, 배송비
- Discount promotions: 팔로우 쿠폰, 적립금, 타임딜
- Percentage discounts (%) → Replace with "Special Discount"

### Terminology:
- Sellers = "artists" (작가)
- Products = "handmade creations" or "items" (NOT "products")
- Use "・" as separator instead of "&"

### Proper Nouns:
- Korean artist names → Romanize phonetically
- English names → Keep as-is
- Korean brand names → Romanize (NOT translate)

---

Korean Text to Translate:
{text}

---

English Translation:
"""
```

#### 3.1.4 섹션별 특화 프롬프트

```python
# 제목 번역 (간결하게)
TITLE_PROMPT = """
Translate this product title to {language}.
Keep it concise and SEO-friendly.
Preserve brand names in original form or romanized.

Korean: {title}
{language}:
"""

# 옵션 번역 (짧게)
OPTION_PROMPT = """
Translate these product options to {language}.
Keep translations short and clear.
Output format: original → translation (one per line)

Options:
{options}

Translations:
"""

# OCR 텍스트 번역 (맥락 유지)
OCR_PROMPT = """
Translate this text extracted from a product image to {language}.
This is promotional/informational text from a handmade product listing.
Maintain the original formatting and emphasis.

Korean Text:
{text}

{language} Translation:
"""
```

---

### 3.2 OCR 순서 정렬

#### 3.2.1 이미지 순서 보장 알고리즘

```python
async def _extract_images_with_position(self, page: Page) -> list[dict]:
    """
    이미지를 페이지 내 Y좌표 순서대로 추출
    → 실제 페이지 스크롤 순서와 일치
    """
    return await page.evaluate("""
        () => {
            const images = [];
            const seen = new Set();
            
            // 모든 이미지 요소 수집
            const imgElements = document.querySelectorAll('img');
            
            imgElements.forEach((img, domIndex) => {
                const url = img.src || img.getAttribute('data-src') || 
                           img.getAttribute('data-original');
                
                if (!url || !url.includes('idus') || seen.has(url)) return;
                seen.add(url);
                
                const rect = img.getBoundingClientRect();
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                
                // 이미지 메타데이터 수집
                images.push({
                    url: url,
                    y_position: rect.top + scrollTop,  // 절대 Y좌표
                    x_position: rect.left,              // X좌표 (보조)
                    width: rect.width,
                    height: rect.height,
                    dom_index: domIndex,
                    alt: img.alt || '',
                    // 상위 섹션 정보
                    section: (() => {
                        const section = img.closest('section, article, [class*="detail"], [class*="content"]');
                        return section ? section.className : 'unknown';
                    })(),
                    // 이미지 유형 추정
                    type: (() => {
                        const parent = img.closest('[class*="main"], [class*="thumb"], [class*="detail"]');
                        if (!parent) return 'other';
                        const cls = parent.className.toLowerCase();
                        if (cls.includes('main') || cls.includes('thumb')) return 'thumbnail';
                        if (cls.includes('detail') || cls.includes('content')) return 'detail';
                        return 'other';
                    })()
                });
            });
            
            // Y좌표로 정렬 (같은 Y면 X좌표로)
            return images.sort((a, b) => {
                if (Math.abs(a.y_position - b.y_position) < 10) {
                    return a.x_position - b.x_position;
                }
                return a.y_position - b.y_position;
            });
        }
    """)
```

#### 3.2.2 개선된 ImageText 모델

```python
class ImageText(BaseModel):
    """이미지 내 텍스트 모델 (순서 정보 포함)"""
    image_url: str
    original_text: str
    translated_text: Optional[str] = None
    
    # 순서 및 위치 정보
    order_index: int = 0          # 페이지 내 순서 (0부터)
    y_position: float = 0         # Y좌표 (정렬용)
    
    # 메타데이터
    section: str = "unknown"      # 섹션 (thumbnail, detail, etc.)
    image_type: str = "other"     # 이미지 유형
    
    # 텍스트 분석
    text_category: str = "general"  # title, spec, notice, promotion, etc.
```

#### 3.2.3 텍스트 카테고리 자동 분류

```python
def _categorize_ocr_text(self, text: str) -> str:
    """OCR 텍스트 카테고리 자동 분류"""
    text_lower = text.lower()
    
    # 제목/헤더
    if any(k in text for k in ['POINT', 'INFO', 'ABOUT', '안내', '소개']):
        return 'header'
    
    # 스펙/상세정보
    if any(k in text for k in ['cm', 'mm', 'g', 'ml', '사이즈', '크기', '무게']):
        return 'specification'
    
    # 주의사항
    if any(k in text for k in ['주의', '유의', 'NOTE', 'CAUTION', '확인']):
        return 'notice'
    
    # 사용방법
    if any(k in text for k in ['사용', '방법', 'HOW', 'USE', '순서']):
        return 'how_to_use'
    
    # 프로모션
    if any(k in text for k in ['할인', 'SALE', '이벤트', '특가', '%']):
        return 'promotion'
    
    return 'description'
```

---

### 3.3 결과물 구조화

#### 3.3.1 번역 결과 포맷터

```python
class TranslationFormatter:
    """번역 결과를 다양한 포맷으로 변환"""
    
    @staticmethod
    def to_structured_text(data: TranslatedProduct) -> str:
        """실무자가 바로 쓸 수 있는 구조화된 텍스트"""
        
        lang = "English" if data.target_language == "en" else "日本語"
        
        output = []
        output.append("=" * 60)
        output.append(f"📦 상품명 / Product Title")
        output.append("=" * 60)
        output.append(f"[한국어] {data.original.title}")
        output.append(f"[{lang}] {data.translated_title}")
        output.append("")
        
        output.append("=" * 60)
        output.append(f"📝 상품 설명 / Description")
        output.append("=" * 60)
        output.append(data.translated_description)
        output.append("")
        
        if data.translated_options:
            output.append("=" * 60)
            output.append(f"🏷️ 옵션 / Options")
            output.append("=" * 60)
            for opt in data.translated_options:
                output.append(f"• {opt.name}: {' / '.join(opt.values)}")
            output.append("")
        
        if data.translated_image_texts:
            output.append("=" * 60)
            output.append(f"🖼️ 이미지 텍스트 / Image Text (순서대로)")
            output.append("=" * 60)
            
            # 순서대로 정렬
            sorted_texts = sorted(
                data.translated_image_texts, 
                key=lambda x: getattr(x, 'order_index', 0)
            )
            
            for idx, img_text in enumerate(sorted_texts, 1):
                output.append(f"\n[이미지 {idx}]")
                output.append(f"원문: {img_text.original_text}")
                output.append(f"번역: {img_text.translated_text or 'N/A'}")
        
        return "\n".join(output)
    
    @staticmethod
    def to_marketplace_format(data: TranslatedProduct, platform: str) -> str:
        """마켓플레이스별 맞춤 포맷"""
        
        if platform == "idus_global":
            return TranslationFormatter._format_idus_global(data)
        elif platform == "etsy":
            return TranslationFormatter._format_etsy(data)
        elif platform == "amazon":
            return TranslationFormatter._format_amazon(data)
        
        return TranslationFormatter.to_structured_text(data)
    
    @staticmethod
    def _format_idus_global(data: TranslatedProduct) -> str:
        """아이디어스 글로벌 등록용 포맷"""
        
        if data.target_language == "ja":
            sections = []
            sections.append(f"[作品紹介]\n{data.translated_description}")
            
            if data.translated_image_texts:
                sections.append("\n[詳細情報]")
                for img_text in sorted(data.translated_image_texts, 
                                      key=lambda x: getattr(x, 'order_index', 0)):
                    if img_text.translated_text:
                        sections.append(img_text.translated_text)
            
            sections.append("\nもし作品の制作時間や詳細について知りたい場合は、")
            sections.append("アイディアス(idus)アプリのメッセージ機能を通じてご連絡ください。")
            
            return "\n".join(sections)
        
        else:  # English
            sections = []
            sections.append(f"[Item Description]\n{data.translated_description}")
            
            if data.translated_options:
                sections.append("\n[Item Details]")
                for opt in data.translated_options:
                    sections.append(f"- {opt.name}: {', '.join(opt.values)}")
            
            sections.append("\n[Shipping Information]")
            sections.append("International delivery time may vary depending on your location.")
            sections.append("On average, delivery takes about 2 weeks after shipping.")
            sections.append("For details, please contact via the message function on the idus app.")
            
            return "\n".join(sections)
```

#### 3.3.2 복사용 텍스트 생성

```python
def generate_copy_ready_text(data: TranslatedProduct) -> dict:
    """각 영역별 복사 가능한 텍스트 생성"""
    
    return {
        "title": data.translated_title,
        "description": data.translated_description,
        "options": "\n".join([
            f"{opt.name}: {', '.join(opt.values)}"
            for opt in data.translated_options
        ]),
        "image_texts": "\n\n".join([
            f"[Image {i+1}]\n{t.translated_text or t.original_text}"
            for i, t in enumerate(
                sorted(data.translated_image_texts, 
                      key=lambda x: getattr(x, 'order_index', 0))
            )
        ]),
        "full": TranslationFormatter.to_structured_text(data)
    }
```

---

### 3.4 내보내기 기능

#### 3.4.1 지원 형식

| 형식 | 용도 | 설명 |
|------|------|------|
| **클립보드 복사** | 즉시 붙여넣기 | 구조화된 텍스트 |
| **TXT** | 텍스트 편집 | 유니코드 지원 |
| **JSON** | 개발/연동 | 전체 데이터 |
| **CSV** | 대량 등록 | 마켓플레이스 업로드용 |
| **Markdown** | 문서화 | 가독성 높은 포맷 |

#### 3.4.2 내보내기 컴포넌트

```tsx
// components/ExportOptions.tsx

interface ExportOptionsProps {
  data: TranslatedProduct;
  originalData: ProductData;
}

export function ExportOptions({ data, originalData }: ExportOptionsProps) {
  const exportFormats = [
    { 
      id: 'clipboard', 
      label: '📋 전체 복사', 
      description: '구조화된 텍스트를 클립보드에 복사',
      action: () => copyToClipboard(formatStructuredText(data))
    },
    { 
      id: 'title', 
      label: '📌 제목만 복사', 
      description: '번역된 제목만 복사',
      action: () => copyToClipboard(data.translated_title)
    },
    { 
      id: 'description', 
      label: '📝 설명만 복사', 
      description: '번역된 설명만 복사',
      action: () => copyToClipboard(data.translated_description)
    },
    { 
      id: 'txt', 
      label: '💾 TXT 다운로드', 
      description: '텍스트 파일로 저장',
      action: () => downloadTxt(data)
    },
    { 
      id: 'json', 
      label: '📦 JSON 다운로드', 
      description: '전체 데이터 (개발용)',
      action: () => downloadJson(data, originalData)
    },
    { 
      id: 'idus', 
      label: '🏪 아이디어스 형식', 
      description: '글로벌 등록용 포맷',
      action: () => copyToClipboard(formatIdusGlobal(data))
    },
  ];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">
          <Download className="w-4 h-4 mr-2" />
          내보내기
          <ChevronDown className="w-4 h-4 ml-2" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        {exportFormats.map((format) => (
          <DropdownMenuItem
            key={format.id}
            onClick={format.action}
            className="flex flex-col items-start py-3"
          >
            <span className="font-medium">{format.label}</span>
            <span className="text-xs text-muted-foreground">
              {format.description}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

---

### 3.5 UI/UX 개선

#### 3.5.1 새로운 레이아웃 구조

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 URL 입력                              [번역하기]         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📊 요약 카드                                         │   │
│  │ 상품명: XXX  |  작가: XXX  |  이미지: XX개  |  OCR: XX개│
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─── 빠른 액션 ─────────────────────────────────────────┐ │
│  │ [📋 전체복사] [📌 제목복사] [📝 설명복사] [💾 내보내기] │ │
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  ┌─────────────────────┬─────────────────────────────────┐ │
│  │                     │                                 │ │
│  │   원본 (한국어)      │       번역 결과                 │ │
│  │                     │                                 │ │
│  │   [제목]            │       [제목] ✏️                 │ │
│  │   상품명            │       Translated Title          │ │
│  │                     │                                 │ │
│  │   [설명]            │       [설명] ✏️                 │ │
│  │   원본 설명...      │       Translated description... │ │
│  │                     │                                 │ │
│  └─────────────────────┴─────────────────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 🖼️ 이미지 & OCR 매핑 뷰                                 ││
│  │ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐     ││
│  │ │ img 1 │ │ img 2 │ │ img 3 │ │ img 4 │ │ img 5 │ ... ││
│  │ └───────┘ └───────┘ └───────┘ └───────┘ └───────┘     ││
│  │                                                         ││
│  │ [선택된 이미지 상세]                                     ││
│  │ 원문: 한국어 텍스트...                                   ││
│  │ 번역: Translated text...                        [복사]  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### 3.5.2 이미지-OCR 매핑 컴포넌트

```tsx
// components/ImageOcrMapping.tsx

export function ImageOcrMapping({ 
  images, 
  ocrResults 
}: ImageOcrMappingProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  
  // OCR 결과를 이미지 URL로 매핑
  const ocrMap = useMemo(() => {
    const map = new Map<string, ImageText>();
    ocrResults.forEach(ocr => map.set(ocr.image_url, ocr));
    return map;
  }, [ocrResults]);

  return (
    <div className="space-y-4">
      {/* 썸네일 스트립 */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {images.map((url, idx) => {
          const hasOcr = ocrMap.has(url);
          return (
            <button
              key={url}
              onClick={() => setSelectedIndex(idx)}
              className={cn(
                "relative shrink-0 w-20 h-20 rounded border-2 overflow-hidden",
                selectedIndex === idx ? "border-primary" : "border-transparent",
                hasOcr && "ring-2 ring-green-500"
              )}
            >
              <img src={url} alt="" className="object-cover w-full h-full" />
              <span className="absolute top-1 left-1 bg-black/70 text-white text-xs px-1 rounded">
                {idx + 1}
              </span>
              {hasOcr && (
                <span className="absolute bottom-1 right-1 bg-green-500 text-white text-xs px-1 rounded">
                  OCR
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* 선택된 이미지 상세 */}
      <Card>
        <CardContent className="p-4">
          <div className="grid md:grid-cols-2 gap-4">
            {/* 이미지 */}
            <div>
              <img 
                src={images[selectedIndex]} 
                alt="" 
                className="w-full rounded"
              />
            </div>
            
            {/* OCR 결과 */}
            <div>
              {ocrMap.has(images[selectedIndex]) ? (
                <div className="space-y-4">
                  <div>
                    <Label>원문</Label>
                    <p className="text-sm bg-muted p-3 rounded">
                      {ocrMap.get(images[selectedIndex])!.original_text}
                    </p>
                  </div>
                  <div>
                    <Label>번역</Label>
                    <div className="relative">
                      <p className="text-sm bg-primary/10 p-3 rounded pr-10">
                        {ocrMap.get(images[selectedIndex])!.translated_text}
                      </p>
                      <Button 
                        size="icon" 
                        variant="ghost"
                        className="absolute top-2 right-2"
                        onClick={() => copyToClipboard(
                          ocrMap.get(images[selectedIndex])!.translated_text
                        )}
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  이 이미지에서 추출된 텍스트가 없습니다.
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## 4. 구현 로드맵

### Phase 1: 핵심 품질 개선 (1주차)

| 항목 | 설명 | 우선순위 | 예상 소요 |
|------|------|----------|----------|
| ✅ 번역 프롬프트 개선 | 공유된 프롬프트 적용 | P0 | 4시간 |
| ✅ OCR 순서 정렬 | Y좌표 기반 정렬 | P0 | 4시간 |
| ✅ 복사 기능 강화 | 원클릭 전체/부분 복사 | P0 | 2시간 |

### Phase 2: 사용성 개선 (2주차)

| 항목 | 설명 | 우선순위 | 예상 소요 |
|------|------|----------|----------|
| ✅ 내보내기 다양화 | TXT, CSV, 마켓플레이스 포맷 | P1 | 6시간 |
| ✅ 이미지-OCR 매핑 뷰 | 시각적 매핑 UI | P1 | 6시간 |
| ✅ 인라인 편집 | 번역 결과 직접 수정 | P1 | 4시간 |

### Phase 3: 고급 기능 (3주차)

| 항목 | 설명 | 우선순위 | 예상 소요 |
|------|------|----------|----------|
| 용어집 관리 | 자주 쓰는 용어 일관성 | P2 | 8시간 |
| 번역 히스토리 | 이전 결과 저장/불러오기 | P2 | 8시간 |
| 품질 검증 | 번역 품질 자동 체크 | P2 | 6시간 |

### Phase 4: 확장 (4주차+)

| 항목 | 설명 | 우선순위 | 예상 소요 |
|------|------|----------|----------|
| 다국어 확장 | 중국어, 태국어 등 | P3 | 16시간 |
| 배치 처리 | 다중 URL 일괄 번역 | P3 | 12시간 |
| API 제공 | 외부 연동용 API | P3 | 16시간 |

---

## 5. 기술 명세

### 5.1 백엔드 변경사항

```python
# backend/app/translator.py 수정 사항

class ProductTranslator:
    def __init__(self, api_key: Optional[str] = None):
        # ... 기존 코드 ...
        
        # 프롬프트 템플릿 로드
        self.prompts = {
            'ja': JAPANESE_TRANSLATION_PROMPT,
            'en': ENGLISH_TRANSLATION_PROMPT,
        }
    
    def _translate_text(self, text: str, target_language: TargetLanguage, 
                       context: str = "") -> str:
        """컨텍스트 기반 번역"""
        
        # 적절한 프롬프트 선택
        if context == "title":
            prompt = TITLE_PROMPT.format(language=lang, title=text)
        elif context == "ocr":
            prompt = OCR_PROMPT.format(language=lang, text=text)
        else:
            # 전체 설명은 상세 프롬프트 사용
            prompt = self.prompts[target_language.value].format(text=text)
        
        # ... API 호출 ...
```

### 5.2 프론트엔드 변경사항

```tsx
// frontend/app/page.tsx 수정 사항

export default function Home() {
  // ... 기존 상태 ...
  
  // 복사 기능
  const handleCopyAll = useCallback(() => {
    if (!translatedData) return;
    const text = formatStructuredText(translatedData);
    navigator.clipboard.writeText(text);
    toast({ title: '복사 완료', description: '전체 번역 결과가 복사되었습니다.' });
  }, [translatedData]);
  
  const handleCopyTitle = useCallback(() => {
    if (!translatedData) return;
    navigator.clipboard.writeText(translatedData.translated_title);
    toast({ title: '복사 완료', description: '제목이 복사되었습니다.' });
  }, [translatedData]);
  
  const handleCopyDescription = useCallback(() => {
    if (!translatedData) return;
    navigator.clipboard.writeText(translatedData.translated_description);
    toast({ title: '복사 완료', description: '설명이 복사되었습니다.' });
  }, [translatedData]);
  
  // ... 렌더링 ...
}
```

### 5.3 새로운 파일 구조

```
backend/
├── app/
│   ├── prompts/                    # 새로 추가
│   │   ├── __init__.py
│   │   ├── japanese.py             # 일본어 프롬프트
│   │   ├── english.py              # 영어 프롬프트
│   │   └── common.py               # 공통 프롬프트
│   ├── formatters/                 # 새로 추가
│   │   ├── __init__.py
│   │   └── export.py               # 내보내기 포맷터
│   ├── scraper.py
│   ├── translator.py
│   ├── models.py
│   └── main.py

frontend/
├── components/
│   ├── ExportOptions.tsx           # 새로 추가
│   ├── ImageOcrMapping.tsx         # 새로 추가
│   ├── QuickActions.tsx            # 새로 추가
│   ├── ...
├── lib/
│   ├── formatters.ts               # 새로 추가
│   └── ...
```

---

## 6. 구현 완료 내역

### Phase 1 완료 (2024-12-31)

| 항목 | 구현 내용 | 파일 |
|------|----------|------|
| ✅ 번역 프롬프트 | 일본어/영어 전문 프롬프트 적용 | `backend/app/prompts/` |
| ✅ OCR 순서 정렬 | Y좌표 기반 이미지 추출 및 정렬 | `backend/app/scraper.py` |
| ✅ 복사 기능 | 전체/부분 복사, 아이디어스 형식 | `frontend/lib/formatters.ts` |
| ✅ 다운로드 | TXT/JSON 다운로드 | `frontend/app/page.tsx` |

### Phase 2 완료 (2024-12-31)

| 항목 | 구현 내용 | 파일 |
|------|----------|------|
| ✅ 이미지-OCR 매핑 뷰 | 썸네일 스트립, 선택 뷰, OCR 요약 | `frontend/components/ImageOcrMapping.tsx` |
| ✅ 인라인 편집 | OCR 번역 결과 직접 수정 | `frontend/components/ImageOcrMapping.tsx` |
| ✅ 순서 표시 | OCR 순서 번호 표시 | `frontend/components/ImageOcrMapping.tsx` |

---

## 📌 다음 단계

### Phase 3: 고급 기능 (예정)

1. **용어집 관리** - 자주 쓰는 용어 일관성 유지
2. **번역 히스토리** - 이전 결과 저장/불러오기
3. **품질 검증** - 번역 품질 자동 체크

### Phase 4: 확장 (예정)

1. **다국어 확장** - 중국어, 태국어 등
2. **배치 처리** - 다중 URL 일괄 번역
3. **API 제공** - 외부 연동용 API

---

## 📊 작업 경과 요약

```
Phase 1 (핵심 품질 개선)
├── ✅ 번역 프롬프트 시스템 구현
│   ├── backend/app/prompts/__init__.py
│   ├── backend/app/prompts/japanese.py
│   └── backend/app/prompts/english.py
├── ✅ OCR 순서 정렬 구현
│   ├── backend/app/models.py (ImageText에 order_index, y_position 추가)
│   └── backend/app/scraper.py (Y좌표 기반 이미지 추출)
└── ✅ 복사 기능 강화
    ├── frontend/lib/formatters.ts (포맷터 유틸리티)
    ├── frontend/components/ui/dropdown-menu.tsx
    └── frontend/app/page.tsx (복사/다운로드 버튼)

Phase 2 (사용성 개선)
├── ✅ 이미지-OCR 매핑 뷰
│   └── frontend/components/ImageOcrMapping.tsx
├── ✅ 인라인 편집 기능
│   └── frontend/components/ImageOcrMapping.tsx (편집 모드)
└── ✅ OCR 탭 UI 개선
    └── frontend/app/page.tsx (매핑 뷰 적용)

Phase 3 (고급 기능) ✅ 완료
├── ✅ 번역 히스토리 기능
│   ├── frontend/lib/storage.ts (LocalStorage 관리)
│   └── frontend/components/TranslationHistory.tsx
├── ✅ 품질 검증 기능
│   ├── frontend/lib/quality-check.ts (검증 로직)
│   └── frontend/components/QualityCheck.tsx
├── ✅ 용어집 기본 구조
│   └── frontend/lib/storage.ts (용어집 CRUD)
└── ✅ UI 통합
    └── frontend/app/page.tsx (히스토리, 품질검증 통합)
```

---

## 📋 Phase 3 상세 구현 내역

### 3-1. 번역 히스토리 기능

**구현 파일:**
- `frontend/lib/storage.ts` - LocalStorage 기반 히스토리 관리
- `frontend/components/TranslationHistory.tsx` - 히스토리 UI 컴포넌트

**주요 기능:**
- 최근 20개 번역 결과 자동 저장
- 히스토리에서 이전 번역 결과 불러오기
- 개별/전체 삭제 기능
- 타임스탬프 표시 (방금 전, N분 전 등)
- 같은 URL 중복 제거 (최신 것만 유지)

**데이터 구조:**
```typescript
interface TranslationHistoryItem {
  id: string
  timestamp: number
  url: string
  productTitle: string
  targetLanguage: TargetLanguage
  originalData: ProductData
  translatedData: TranslatedProduct
}
```

### 3-2. 품질 검증 기능

**구현 파일:**
- `frontend/lib/quality-check.ts` - 품질 검증 로직
- `frontend/components/QualityCheck.tsx` - 품질 검증 UI

**검증 항목:**
1. **길이 비율 검증** - 원문 대비 번역문 길이 비교
   - 영어: 0.8~2.5배 정상
   - 일본어: 0.5~1.8배 정상
2. **숫자 누락 검증** - 원문의 숫자가 번역에 있는지 확인
3. **제목 길이 검증** - 마켓플레이스 권장 길이 체크
4. **한국어 잔존 검증** - 번역되지 않은 한글 감지
5. **옵션 일치 검증** - 원본과 번역 옵션 개수 비교

**점수 시스템:**
- A등급: 90점 이상 (문제 없음)
- B등급: 80~89점 (양호)
- C등급: 70~79점 (개선 권장)
- D등급: 60~69점 (확인 필요)
- F등급: 60점 미만 (문제 있음)

### 3-3. 용어집 기본 구조

**구현 파일:**
- `frontend/lib/storage.ts` - 용어집 CRUD 함수

**주요 기능:**
- 용어 추가/수정/삭제
- 카테고리별 분류 (소재/재료, 색상, 크기, 제작/공정, 배송/결제, 기타)
- 용어 검색 (한국어/영어/일본어)
- 기본 용어 초기화 (핸드메이드 관련 기본 용어 8개)

**데이터 구조:**
```typescript
interface GlossaryItem {
  id: string
  korean: string
  english: string
  japanese: string
  category: string
  notes?: string
  createdAt: number
  updatedAt: number
}
```

---

## 🎯 Phase 4 예정 작업

1. **다국어 확장** - 중국어, 태국어 등
2. **배치 처리** - 다중 URL 일괄 번역
3. **API 제공** - 외부 연동용 API
4. **용어집 UI** - 용어집 관리 화면 구현
5. **번역 비교** - 다른 언어 버전 비교 기능

---

## 📊 전체 진행 상황

| Phase | 상태 | 완료율 |
|-------|------|--------|
| Phase 1: 핵심 품질 개선 | ✅ 완료 | 100% |
| Phase 2: 사용성 개선 | ✅ 완료 | 100% |
| Phase 3: 고급 기능 | ✅ 완료 | 100% |
| Phase 4: 확장 | 📋 예정 | 0% |

다음 Phase 진행을 원하시면 말씀해주세요! 🚀
