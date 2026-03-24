# GB 작품 연계 등록 자동화 - 최적화 설계안

> **문서 버전**: v1.0
> **작성일**: 2026-03-23
> **상태**: 설계 검토 단계

---

## 1. 현황 분석

### 1.1 현재 시스템 (AS-IS)

현재 프로젝트는 **소비자 페이지(idus.com)** 기반의 단방향 파이프라인으로 구성되어 있다.

```
[idus.com 상품 URL] → [Playwright 크롤링] → [Gemini 번역] → [결과 UI 표시]
```

주요 한계점:

- 소비자 페이지를 크롤링하므로 **작가웹(artist.idus.com)의 실제 등록 필드와 불일치**
- 번역 결과를 사용자가 수동으로 작가웹에 복사/붙여넣기해야 함
- 국내 작품의 원본 데이터(작품 인트로, 특장점, 제작과정 등)를 활용하지 못함
- 이미지는 URL만 수집할 뿐, 작가웹에 업로드하는 과정이 없음

### 1.2 작가웹 GB 등록 구조 (브라우저 탐색 기반)

artist.idus.com의 작품 수정 페이지는 아래와 같은 2단 탭 구조를 가진다.

```
작품 수정
├── [국내] 탭 (일시중지/판매중)
│   ├── 작품명* (30자)
│   ├── 가격* (원)
│   ├── d+ 추가할인
│   ├── 수량* (개)
│   ├── 카테고리 & 속성*
│   ├── 작품 이미지* (최대 9장, 첫 번째 = 대표 이미지)
│   ├── 영상 (0/1)
│   ├── 작품 인트로 (100자, 첫 번째 작품 이미지가 인트로에 사용)
│   ├── 특장점 (0/5)
│   ├── 제작과정 (0/6)
│   ├── 선물 포장
│   ├── 작품 설명* (이미지+텍스트 에디터)
│   ├── 작품 정보제공 고시*
│   ├── 옵션 (최대 10개)
│   ├── 배송출발일 설정
│   ├── 작품 키워드
│   └── 작품 후기 적립금 설정
│
└── [글로벌] 탭 (미등록/등록)
    ├── 글로벌 작품 등록 전 확인 안내
    ├── 배송 가능 국가 (45/45)
    ├── [일본어] 서브탭
    │   ├── 일본어 작품명* (80자)
    │   ├── 일본어 작품 이미지* (0/9, 국내 이미지 불러오기 가능)
    │   ├── 일본어 작품 설명* (이미지+텍스트 에디터)
    │   ├── 일본어 작품 키워드
    │   └── 일본어 카테고리 (국내 카테고리 기반 자동 매핑)
    │
    ├── [영어] 서브탭
    │   ├── 영어 작품명* (80자)
    │   ├── 영어 작품 이미지* (0/9, 국내 이미지 불러오기 가능)
    │   ├── 영어 작품 설명* (이미지+텍스트 에디터)
    │   ├── 영어 작품 키워드
    │   └── 영어 카테고리 (국내 카테고리 기반 자동 매핑, 영문 표시)
    │
    ├── 글로벌 옵션 (일본어/영어 공용)
    │   ├── 기본형 옵션
    │   └── 주문 요청사항 옵션
    │   └── ⚠️ 옵션 추가/삭제 시 일본어/영어 작품에 함께 반영
    │
    └── 가격/수량 → 국내 작품과 연동 (글로벌에서 변경 불가)
```

### 1.3 핵심 발견사항

| 항목 | 내용 |
|------|------|
| **이미지** | "국내 작품 이미지 불러오기"로 국내 이미지 재사용 가능. 별도 업로드도 가능 |
| **옵션** | 글로벌 옵션은 일본어/영어 간 공유됨. 옵션 추가/삭제 시 양쪽에 반영 |
| **가격/수량** | 국내 작품 정보 기준으로 연동. 글로벌에서 별도 변경 불가 |
| **카테고리** | 국내 카테고리 기반 자동 매핑. 영어는 영문 카테고리명으로 표시 |
| **작품 설명** | 이미지+텍스트 혼합 에디터. 글/글+이미지/이미지 모두 가능 |
| **작품명** | 글로벌은 80자 제한 (국내는 30자) |
| **판매 제한** | 식품, 가구, 식물, 디퓨저류, 14k/18k/24k 악세사리는 글로벌 판매 불가 |

---

## 2. 목표 시스템 (TO-BE)

### 2.1 새로운 파이프라인

```
[작가웹 국내 작품] → [국내 데이터 추출] → [Gemini 번역] → [작가웹 글로벌 탭 자동 입력] → [임시저장/판매]
```

### 2.2 핵심 변경 방향

| AS-IS | TO-BE |
|-------|-------|
| idus.com 소비자 페이지 크롤링 | artist.idus.com 작가웹 직접 연동 |
| URL 입력 → 번역 결과 표시만 | 국내 작품 선택 → 번역 → GB 탭에 자동 입력 |
| 결과를 수동 복사/붙여넣기 | 작가웹 폼에 직접 값 입력 (Playwright) |
| 이미지 URL만 수집 | "국내 이미지 불러오기" 기능 활용 |
| 텍스트 번역만 지원 | 작품명 + 설명 + 옵션 + 키워드 통합 번역 |

---

## 3. 시스템 아키텍처

### 3.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Vercel)                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ 작품 목록     │  │ 번역 미리보기 │  │ GB 등록 대시보드   │ │
│  │ (국내→글로벌) │  │ (편집 가능)   │  │ (진행상태/이력)    │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ 새 UI: 작가웹 세션 관리 / 작품 선택 / 일괄 처리 컨트롤  ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────┬───────────────────────────┘
                                   │ HTTPS (REST + WebSocket)
                                   ▼
┌──────────────────────────────────────────────────────────────┐
│                     BACKEND (Railway)                         │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    FastAPI Server                        │ │
│  │                                                          │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │ │
│  │  │ ArtistWeb   │  │ Translator   │  │ GB Registrar  │  │ │
│  │  │ Scraper     │  │ (Gemini)     │  │ (Form Filler) │  │ │
│  │  │             │  │              │  │               │  │ │
│  │  │ • 로그인     │  │ • 작품명번역 │  │ • 글로벌탭이동│  │ │
│  │  │ • 작품목록   │  │ • 설명번역   │  │ • 필드자동입력│  │ │
│  │  │ • 국내데이터 │  │ • 옵션번역   │  │ • 이미지불러오기│ │ │
│  │  │   추출      │  │ • 키워드번역 │  │ • 임시저장    │  │ │
│  │  └──────┬──────┘  └──────┬───────┘  └───────┬───────┘  │ │
│  └─────────┼───────────────┼──────────────────┼───────────┘ │
│            │               │                  │              │
└────────────┼───────────────┼──────────────────┼──────────────┘
             │               │                  │
             ▼               ▼                  ▼
     ┌──────────────┐ ┌────────────┐  ┌──────────────────┐
     │ artist.idus  │ │ Google AI  │  │ artist.idus.com  │
     │ .com (읽기)  │ │ (Gemini)   │  │ /product/global  │
     │              │ │            │  │ (쓰기)           │
     └──────────────┘ └────────────┘  └──────────────────┘
```

### 3.2 새로운 데이터 흐름

```
1. 사용자가 작가웹 로그인 정보 입력 (세션 생성)
              │
              ▼
2. Backend: Playwright로 artist.idus.com 로그인
              │
              ▼
3. 작품 목록 조회 (판매중/일시중지)
              │
              ▼
4. 사용자가 글로벌 등록할 작품 선택 (단건 or 일괄)
              │
              ▼
5. 국내 탭에서 데이터 추출:
   - 작품명, 가격, 수량
   - 작품 이미지 (URL + 순서)
   - 작품 설명 (HTML 콘텐츠)
   - 작품 인트로
   - 옵션 (이름 + 값 목록)
   - 카테고리 정보
   - 작품 키워드
              │
              ▼
6. Gemini로 번역 수행:
   - 작품명 → 영어/일본어 (80자 제한 준수)
   - 작품 설명 → 영어/일본어 (HTML 구조 유지)
   - 옵션명 + 옵션값 → 영어/일본어
   - 키워드 → 영어/일본어
              │
              ▼
7. 사용자가 번역 결과 미리보기 및 편집
              │
              ▼
8. 글로벌 탭 자동 입력:
   a. 글로벌 탭 클릭
   b. "국내 작품 이미지 불러오기" 또는 이미지 업로드
   c. 영어/일본어 탭별 필드 입력
   d. 글로벌 옵션 입력
   e. 임시저장 또는 판매 등록
              │
              ▼
9. 결과 리포트 (성공/실패/오류 내역)
```

---

## 4. 데이터 모델 재설계

### 4.1 국내 작품 데이터 (작가웹 기반)

```python
class DomesticProduct(BaseModel):
    """작가웹 국내 탭에서 추출한 작품 데이터"""
    product_id: str              # 작품 UUID (URL에서 추출)
    product_url: str             # artist.idus.com/product/{id}

    # 기본 정보
    title: str                   # 작품명 (30자)
    price: int                   # 가격 (원)
    quantity: int                # 수량
    is_made_to_order: bool       # 주문 시 제작 여부

    # 카테고리
    category_path: str           # "디지털/폰 케이스 > 스마트톡 > 기타 스마트톡"

    # 이미지
    product_images: list[ProductImage]  # 작품 이미지 (최대 9장)

    # 상세 설명
    intro: Optional[str]         # 작품 인트로 (100자)
    features: list[str]          # 특장점 (최대 5개)
    process_steps: list[str]     # 제작과정 (최대 6개)
    description_html: str        # 작품 설명 (HTML)

    # 옵션
    options: list[DomesticOption]

    # 키워드
    keywords: list[str]

    # 글로벌 상태
    global_status: GlobalStatus  # 미등록/등록/일시중지


class ProductImage(BaseModel):
    """작품 이미지"""
    url: str
    order: int                   # 순서 (0 = 대표 이미지)
    is_representative: bool      # 대표 이미지 여부


class DomesticOption(BaseModel):
    """국내 작품 옵션"""
    name: str                    # 옵션명
    values: list[OptionValue]
    option_type: str             # "basic" | "request" (기본형/주문요청사항)


class OptionValue(BaseModel):
    """옵션 값"""
    value: str
    additional_price: int = 0    # 추가 금액
    stock: int = 0               # 재고
```

### 4.2 글로벌 등록 데이터

```python
class GlobalProductData(BaseModel):
    """글로벌 탭에 입력할 데이터"""
    source_product_id: str       # 원본 국내 작품 ID

    # 영어 데이터
    en: Optional[LanguageData]

    # 일본어 데이터
    ja: Optional[LanguageData]

    # 공용 옵션 (일본어/영어 공유)
    global_options: list[GlobalOption]


class LanguageData(BaseModel):
    """언어별 등록 데이터"""
    title: str                   # 작품명 (80자 제한)
    description_html: str        # 작품 설명 (HTML)
    keywords: list[str]          # 작품 키워드
    use_domestic_images: bool    # 국내 이미지 불러오기 사용 여부
    custom_images: list[str]     # 별도 이미지 (사용 시)


class GlobalOption(BaseModel):
    """글로벌 옵션 (일본어/영어 공용)"""
    name_en: str
    name_ja: str
    values_en: list[str]
    values_ja: list[str]
    option_type: str             # "basic" | "request"
```

### 4.3 번역 요청/응답 모델 개선

```python
class GBTranslateRequest(BaseModel):
    """GB 등록용 번역 요청"""
    domestic_product: DomesticProduct
    target_languages: list[str]  # ["en", "ja"] 또는 ["en"] 등
    translation_options: TranslationOptions


class TranslationOptions(BaseModel):
    """번역 옵션"""
    use_domestic_images: bool = True   # 국내 이미지 재사용
    translate_keywords: bool = True     # 키워드 번역
    auto_register: bool = False         # 자동 등록 여부
    save_as_draft: bool = True          # 임시저장 모드


class GBTranslateResponse(BaseModel):
    """GB 등록용 번역 응답"""
    success: bool
    domestic_product: DomesticProduct
    global_data: GlobalProductData
    quality_warnings: list[str]        # 품질 경고 (예: 제한 카테고리)
```

---

## 5. 백엔드 모듈 재설계

### 5.1 디렉토리 구조 (TO-BE)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 엔트리포인트 (확장)
│   ├── config.py                  # 설정 관리 (NEW)
│   │
│   ├── models/                    # 모델 분리 (NEW)
│   │   ├── __init__.py
│   │   ├── domestic.py            # 국내 작품 모델
│   │   ├── global_product.py      # 글로벌 등록 모델
│   │   ├── translation.py         # 번역 요청/응답 모델
│   │   └── common.py              # 공통 모델 (응답, 에러 등)
│   │
│   ├── services/                  # 서비스 레이어 (NEW)
│   │   ├── __init__.py
│   │   ├── artist_web.py          # 작가웹 세션 관리 (로그인/인증)
│   │   ├── product_reader.py      # 국내 작품 데이터 읽기
│   │   ├── product_writer.py      # 글로벌 탭 데이터 쓰기
│   │   └── batch_processor.py     # 일괄 처리 오케스트레이터
│   │
│   ├── scraper/                   # 크롤러 분리 (REFACTOR)
│   │   ├── __init__.py
│   │   ├── base.py                # Playwright 기반 크롤러
│   │   ├── consumer_page.py       # 기존: idus.com 소비자 페이지
│   │   └── artist_page.py         # NEW: artist.idus.com 작가웹
│   │
│   ├── translator/                # 번역기 분리 (REFACTOR)
│   │   ├── __init__.py
│   │   ├── gemini_client.py       # Gemini API 클라이언트
│   │   ├── product_translator.py  # 작품 번역 로직
│   │   └── prompts/               # 프롬프트 템플릿
│   │       ├── __init__.py
│   │       ├── english.py
│   │       └── japanese.py
│   │
│   └── routers/                   # API 라우터 분리 (NEW)
│       ├── __init__.py
│       ├── health.py              # 헬스체크
│       ├── products.py            # 작품 목록/조회
│       ├── translation.py         # 번역 API
│       ├── registration.py        # GB 등록 API
│       └── session.py             # 세션 관리 API
│
├── Dockerfile
├── railway.toml
└── requirements.txt
```

### 5.2 핵심 모듈 설명

#### 5.2.1 artist_web.py - 작가웹 세션 관리

```python
class ArtistWebSession:
    """작가웹 브라우저 세션 관리"""

    async def login(self, email: str, password: str) -> bool:
        """작가웹 로그인"""

    async def is_authenticated(self) -> bool:
        """인증 상태 확인"""

    async def get_product_list(self, status: str = "selling") -> list[ProductSummary]:
        """작품 목록 조회 (판매중/일시중지)"""

    async def navigate_to_product(self, product_id: str) -> bool:
        """특정 작품 수정 페이지로 이동"""
```

#### 5.2.2 product_reader.py - 국내 작품 데이터 읽기

```python
class ProductReader:
    """작가웹 국내 탭에서 작품 데이터 추출"""

    async def read_domestic_data(self, product_id: str) -> DomesticProduct:
        """국내 탭의 모든 필드 데이터 추출"""

    async def read_product_images(self) -> list[ProductImage]:
        """작품 이미지 URL 및 순서 추출"""

    async def read_options(self) -> list[DomesticOption]:
        """옵션 데이터 추출"""

    async def read_description_html(self) -> str:
        """작품 설명 HTML 추출"""

    async def check_global_eligibility(self) -> tuple[bool, list[str]]:
        """글로벌 등록 가능 여부 확인 (카테고리 제한 등)"""
```

#### 5.2.3 product_writer.py - 글로벌 탭 자동 입력

```python
class ProductWriter:
    """작가웹 글로벌 탭에 번역 데이터 입력"""

    async def navigate_to_global_tab(self) -> bool:
        """글로벌 탭으로 이동"""

    async def import_domestic_images(self, language: str) -> bool:
        """'국내 작품 이미지 불러오기' 실행"""

    async def fill_language_tab(self, language: str, data: LanguageData) -> bool:
        """특정 언어 탭의 필드 자동 입력"""
        # - 작품명 입력
        # - 작품 설명 입력 (에디터에 HTML 삽입)
        # - 키워드 입력

    async def fill_global_options(self, options: list[GlobalOption]) -> bool:
        """글로벌 옵션 입력"""

    async def save_draft(self, language: str) -> bool:
        """임시저장"""

    async def publish(self, language: str) -> bool:
        """판매 등록"""
```

### 5.3 새로운 API 엔드포인트

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/session/login` | 작가웹 로그인 (세션 생성) |
| GET | `/api/v2/session/status` | 세션 상태 확인 |
| POST | `/api/v2/session/logout` | 세션 종료 |
| GET | `/api/v2/products` | 국내 작품 목록 조회 |
| GET | `/api/v2/products/{id}` | 국내 작품 상세 데이터 |
| GET | `/api/v2/products/{id}/global-status` | 글로벌 등록 상태 확인 |
| POST | `/api/v2/translate` | 작품 번역 (미리보기용) |
| POST | `/api/v2/register` | GB 등록 실행 (번역 + 입력 + 저장) |
| POST | `/api/v2/register/batch` | 일괄 GB 등록 |
| GET | `/api/v2/register/{id}/status` | 등록 진행 상태 (WebSocket 대안) |
| GET | `/api/health` | 헬스체크 (기존 유지) |

---

## 6. 프론트엔드 재설계

### 6.1 페이지 구조

```
frontend/
├── app/
│   ├── page.tsx                   # 랜딩/로그인 페이지
│   ├── dashboard/
│   │   └── page.tsx               # 작품 목록 대시보드
│   ├── product/
│   │   └── [id]/
│   │       └── page.tsx           # 작품 상세 + 번역 미리보기
│   ├── register/
│   │   └── page.tsx               # GB 등록 진행 화면
│   ├── batch/
│   │   └── page.tsx               # 일괄 처리 (기존 확장)
│   └── settings/
│       └── page.tsx               # 설정 (용어집, API 키 등)
```

### 6.2 사용자 플로우

```
[로그인] → [작품 목록] → [작품 선택] → [번역 미리보기] → [편집] → [GB 등록] → [결과]
   │                         │                                        │
   │                         ├── 단건 선택                             ├── 임시저장
   │                         └── 일괄 선택 (체크박스)                   └── 바로 판매
   │
   └── 작가웹 이메일/비밀번호 입력
```

### 6.3 주요 UI 컴포넌트

| 컴포넌트 | 역할 | 상태 |
|----------|------|------|
| `LoginForm` | 작가웹 로그인 | NEW |
| `ProductList` | 국내 작품 목록 (글로벌 상태 표시) | NEW |
| `ProductDetail` | 국내 원본 + 번역 미리보기 | REFACTOR |
| `TranslationEditor` | 번역 결과 편집 (영어/일본어 탭) | REFACTOR |
| `RegistrationProgress` | GB 등록 진행 상태 | NEW |
| `BatchSelector` | 일괄 처리 작품 선택 | REFACTOR |
| `GlobalStatusBadge` | 글로벌 등록 상태 뱃지 | NEW |

---

## 7. 번역 프롬프트 최적화

### 7.1 GB 등록에 특화된 번역 전략

기존 프롬프트는 일반 번역에 초점을 두고 있으나, GB 등록용으로는 아래 사항을 반영해야 한다.

| 필드 | 번역 전략 |
|------|-----------|
| **작품명** (80자) | 검색 최적화 고려, 핵심 키워드 포함, 감성적 표현 |
| **작품 설명** | HTML 구조 유지, 이미지 태그 보존, 배송/교환 정보는 글로벌 정책으로 대체 |
| **옵션명** | 간결하고 명확한 표현, 색상/사이즈 등 표준 용어 사용 |
| **옵션값** | 직역보다 해당 언어권에서 통용되는 표현 사용 |
| **키워드** | 현지 검색 트렌드 반영, SEO 최적화 |

### 7.2 작품 설명 HTML 처리

작품 설명은 이미지+텍스트 혼합 에디터이므로, HTML 구조를 유지하면서 텍스트만 번역해야 한다.

```
입력: <p>수제 가죽 지갑입니다.</p><img src="..."/><p>배송 안내: 3-5일</p>
출력: <p>Handmade leather wallet.</p><img src="..."/><p>Shipping: 3-5 days</p>
```

---

## 8. 구현 우선순위

### Phase 1: 핵심 인프라 (1-2주)

- [ ] 백엔드 디렉토리 구조 리팩토링
- [ ] 데이터 모델 재설계 (models/ 분리)
- [ ] 작가웹 세션 관리 (로그인/인증)
- [ ] 국내 작품 목록 조회 API

### Phase 2: 읽기 기능 (1-2주)

- [ ] 국내 탭 데이터 추출 (ProductReader)
- [ ] 글로벌 등록 가능 여부 검증
- [ ] 프론트엔드 로그인 + 작품 목록 UI

### Phase 3: 번역 최적화 (1주)

- [ ] GB 등록용 번역 프롬프트 업데이트
- [ ] HTML 구조 유지 번역 로직
- [ ] 옵션/키워드 전문 번역
- [ ] 번역 미리보기 UI

### Phase 4: 쓰기 기능 (1-2주)

- [ ] 글로벌 탭 자동 입력 (ProductWriter)
- [ ] 이미지 불러오기 자동화
- [ ] 임시저장/판매 등록
- [ ] 등록 결과 리포트

### Phase 5: 일괄 처리 + 안정화 (1주)

- [ ] 일괄 등록 처리
- [ ] 에러 핸들링 강화
- [ ] 진행 상태 실시간 표시 (WebSocket or SSE)
- [ ] E2E 테스트

---

## 9. 기술적 고려사항

### 9.1 세션 관리

작가웹 로그인 세션을 Playwright 브라우저 컨텍스트로 유지해야 한다. Railway 환경에서의 세션 지속성, 타임아웃 처리, 동시 접속 제한 등을 고려해야 한다.

### 9.2 작품 설명 에디터 자동화

작품 설명은 리치 텍스트 에디터(이미지+텍스트)로, 단순 텍스트 입력이 아닌 에디터 DOM 조작이 필요하다. "작품 설명 작성하기" 버튼을 클릭하면 별도 에디터가 열리는 구조이므로, 에디터 내부 API 또는 DOM 직접 조작 방식을 선택해야 한다.

### 9.3 이미지 처리

"국내 작품 이미지 불러오기" 기능을 활용하면 이미지 재업로드 없이 국내 이미지를 글로벌에 연결할 수 있다. 이 방식이 가장 효율적이며, 이미지 내 한국어 텍스트가 있는 경우에만 별도 이미지를 준비하면 된다.

### 9.4 Rate Limiting

작가웹에 과도한 요청을 보내지 않도록 요청 간격을 조절해야 한다. 특히 일괄 처리 시 작품 간 적절한 대기 시간을 설정해야 한다.

### 9.5 에러 복구

자동 입력 중 오류 발생 시 (네트워크 오류, 페이지 로딩 실패 등) 안전하게 롤백하거나 재시도할 수 있는 메커니즘이 필요하다. 임시저장을 중간 체크포인트로 활용할 수 있다.

---

## 10. 기존 코드 재활용 계획

| 기존 파일 | 재활용 방법 |
|-----------|-------------|
| `scraper.py` | `scraper/consumer_page.py`로 이동, 기존 기능 유지 |
| `translator.py` | `translator/gemini_client.py`로 분리, 프롬프트 로직은 `product_translator.py`로 |
| `models.py` | `models/` 디렉토리로 분리 확장 |
| `main.py` | 라우터 패턴으로 리팩토링, 기존 API는 `/api/v1/`으로 유지 |
| `prompts/` | 그대로 유지 + GB 등록용 프롬프트 추가 |
| 프론트엔드 컴포넌트들 | 대부분 재활용, 새 페이지에서 import |

---

> 이 설계안은 작가웹(artist.idus.com) 브라우저 탐색을 통해 실제 확인된 구조를 기반으로 작성되었습니다.
