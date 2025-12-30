# 📋 Idus 작품 번역 자동화 프로젝트 기획서

> **문서 버전**: v1.2  
> **최종 수정일**: 2024-12-30  
> **작성자**: AI Assistant  
> **상태**: 🟢 MVP 완료 + Gemini API 적용

---

## 📌 1. 프로젝트 개요

### 1.1 프로젝트 명
**Idus Product Translator** - 아이디어스 작품 글로벌 번역 자동화 웹 앱

### 1.2 프로젝트 배경
한국의 핸드메이드 플랫폼 '아이디어스(Idus)'의 제품 페이지를 글로벌 시장(영어/일본어권)으로 확장하기 위한 번역 업무 자동화 필요성

### 1.3 프로젝트 목표
| 목표 | 설명 | 상태 |
|------|------|------|
| **자동 크롤링** | URL 입력만으로 상품 정보 자동 수집 | ✅ 완료 |
| **이미지 OCR** | 상세 이미지 내 한국어 텍스트 추출 | ✅ 완료 |
| **다국어 번역** | 영어/일본어 자동 번역 | ✅ 완료 |
| **편집 UI** | 번역 결과 실시간 수정 가능 | ✅ 완료 |

### 1.4 주요 사용자
- 아이디어스 판매자 (작가)
- 글로벌 마케팅 담당자
- 상품 등록 운영팀

---

## 🛠 2. 기술 스택

### 2.1 Frontend ✅ 구현 완료
| 기술 | 버전 | 용도 |
|------|------|------|
| Next.js | 14.1.0 | App Router 기반 React 프레임워크 |
| Tailwind CSS | 3.4.x | 유틸리티 기반 CSS |
| Shadcn UI | 커스텀 | Radix 기반 컴포넌트 |
| TypeScript | 5.3.x | 타입 안정성 |
| Lucide React | 0.321.x | 아이콘 라이브러리 |

**배포**: Vercel

### 2.2 Backend ✅ 구현 완료
| 기술 | 버전 | 용도 |
|------|------|------|
| Python | 3.11 | 런타임 (⚠️ 3.14 호환 안됨) |
| FastAPI | 0.109.x | REST API 프레임워크 |
| Playwright | 1.41.x | 웹 크롤링 |
| playwright-stealth | 1.0.x | 봇 탐지 우회 |
| **Google Gemini** | 2.0 Flash | OCR 및 번역 (변경됨) |

**배포**: Railway (Docker)

### 2.3 AI 모델 (변경사항)
| 변경 전 | 변경 후 | 이유 |
|---------|---------|------|
| OpenAI GPT-4o | Google Gemini 2.0 Flash | 사용자 요청 |

---

## 🎯 3. 기능 요구사항 (Functional Requirements)

### 3.1 크롤링 기능

| ID | 기능 | 우선순위 | 상태 |
|----|------|----------|------|
| CR-01 | URL 입력 시 상품 페이지 접속 | P0 | ✅ 완료 |
| CR-02 | playwright-stealth 봇 탐지 우회 | P0 | ✅ 완료 |
| CR-03 | 상품명/작가명/가격 추출 | P0 | ✅ 완료 |
| CR-04 | 상품 설명 텍스트 추출 | P0 | ✅ 완료 |
| CR-05 | '옵션 선택' 버튼 자동 클릭 | P0 | ✅ 완료 |
| CR-06 | 숨겨진 옵션 텍스트 추출 | P0 | ✅ 완료 |
| CR-07 | 상세 이미지 URL 수집 | P0 | ✅ 완료 |
| CR-08 | 에러 핸들링 및 재시도 로직 | P1 | 🔲 미완료 |
| CR-09 | 크롤링 진행률 실시간 전송 | P2 | 🔲 미완료 |

### 3.2 OCR/번역 기능

| ID | 기능 | 우선순위 | 상태 |
|----|------|----------|------|
| TR-01 | Gemini Vision 이미지 OCR | P0 | ✅ 완료 |
| TR-02 | 한국어 → 영어 번역 | P0 | ✅ 완료 |
| TR-03 | 한국어 → 일본어 번역 | P0 | ✅ 완료 |
| TR-04 | 옵션값 번역 | P0 | ✅ 완료 |
| TR-05 | 이미지 내 텍스트 번역 | P0 | ✅ 완료 |
| TR-06 | 번역 품질 최적화 프롬프트 | P1 | ✅ 완료 |
| TR-07 | 번역 캐싱 (중복 요청 방지) | P2 | 🔲 미완료 |
| TR-08 | 용어집(Glossary) 지원 | P2 | 🔲 미완료 |

### 3.3 API 기능

| ID | 기능 | 우선순위 | 상태 |
|----|------|----------|------|
| API-01 | POST /api/scrape 엔드포인트 | P0 | ✅ 완료 |
| API-02 | POST /api/translate 엔드포인트 | P0 | ✅ 완료 |
| API-03 | POST /api/scrape-and-translate 통합 | P0 | ✅ 완료 |
| API-04 | GET /api/health 헬스체크 | P0 | ✅ 완료 |
| API-05 | CORS 설정 (Vercel 허용) | P0 | ✅ 완료 |
| API-06 | Rate Limiting | P1 | 🔲 미완료 |
| API-07 | API 인증 (API Key) | P1 | 🔲 미완료 |

### 3.4 Frontend UI 기능

| ID | 기능 | 우선순위 | 상태 |
|----|------|----------|------|
| UI-01 | URL 입력 폼 | P0 | ✅ 완료 |
| UI-02 | 언어 선택 (영어/일본어) | P0 | ✅ 완료 |
| UI-03 | 로딩/진행 상태 표시 | P0 | ✅ 완료 |
| UI-04 | 좌측(원본)/우측(번역) 분할 뷰 | P0 | ✅ 완료 |
| UI-05 | 번역 텍스트 인라인 편집 | P0 | ✅ 완료 |
| UI-06 | 이미지 OCR 결과 표시 | P0 | ✅ 완료 |
| UI-07 | 옵션 번역 결과 테이블 | P1 | ✅ 완료 |
| UI-08 | 번역 결과 복사 기능 | P1 | ✅ 완료 |
| UI-09 | 번역 결과 다운로드 (JSON) | P2 | ✅ 완료 |
| UI-10 | 다크 모드 | P2 | 🔲 미완료 |
| UI-11 | 반응형 모바일 UI | P2 | ✅ 완료 |

---

## 🏗 4. 시스템 아키텍처

### 4.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Vercel)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  URL Input  │  │  Language   │  │   Translation Editor    │  │
│  │    Form     │  │  Selector   │  │  (Side-by-Side View)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                         Next.js 14 + Tailwind + Shadcn          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ HTTPS (REST API)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (Railway)                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    FastAPI Server                        │    │
│  │  ┌───────────┐  ┌───────────────┐  ┌─────────────────┐  │    │
│  │  │  /scrape  │  │  /translate   │  │ /scrape-and-    │  │    │
│  │  │           │  │               │  │   translate     │  │    │
│  │  └─────┬─────┘  └───────┬───────┘  └────────┬────────┘  │    │
│  │        │                │                    │           │    │
│  │        ▼                ▼                    ▼           │    │
│  │  ┌───────────┐  ┌───────────────┐                        │    │
│  │  │  Scraper  │  │  Translator   │                        │    │
│  │  │(Playwright│  │  (Gemini)     │  ← 변경됨               │    │
│  │  │ +Stealth) │  │               │                        │    │
│  │  └─────┬─────┘  └───────┬───────┘                        │    │
│  └────────┼────────────────┼────────────────────────────────┘    │
│           │                │                                      │
└───────────┼────────────────┼──────────────────────────────────────┘
            │                │
            ▼                ▼
    ┌───────────────┐  ┌───────────────┐
    │   Idus.com    │  │  Google AI    │
    │  (크롤링 대상) │  │  (Gemini)     │  ← 변경됨
    └───────────────┘  └───────────────┘
```

### 4.2 데이터 흐름

```
1. 사용자가 아이디어스 URL 입력 + 언어 선택
           │
           ▼
2. Frontend → Backend API 호출 (POST /api/scrape)
           │
           ▼
3. Playwright가 페이지 크롤링
   - 봇 탐지 우회 (stealth)
   - 옵션 버튼 클릭
   - 데이터 추출
           │
           ▼
4. 크롤링 결과 반환 (ProductData)
           │
           ▼
5. Frontend → Backend API 호출 (POST /api/translate)
           │
           ▼
6. Gemini로 번역 수행
   - 텍스트 번역
   - 이미지 OCR + 번역
           │
           ▼
7. 번역 결과 반환 (TranslatedProduct)
           │
           ▼
8. Frontend에서 Side-by-Side 표시
   - 사용자 인라인 편집 가능
   - 클립보드 복사
   - JSON 다운로드
```

---

## 📁 5. 프로젝트 구조

### 5.1 현재 구조 ✅ 완료

```
작품 번역 자동화/
├── 📁 backend/                    # ✅ 완료
│   ├── 📁 app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI 엔트리포인트
│   │   ├── models.py             # Pydantic 모델
│   │   ├── scraper.py            # Playwright 크롤러
│   │   └── translator.py         # Gemini 번역기 (변경됨)
│   ├── Dockerfile                # Railway 배포용
│   ├── railway.toml              # Railway 설정
│   ├── requirements.txt          # Python 의존성 (Gemini 포함)
│   └── env.example               # 환경변수 예제
│
├── 📁 frontend/                   # ✅ 완료
│   ├── 📁 app/
│   │   ├── globals.css           # 전역 스타일 + CSS 변수
│   │   ├── layout.tsx            # 루트 레이아웃 (헤더/푸터)
│   │   └── page.tsx              # 메인 페이지 (상태 관리)
│   │
│   ├── 📁 components/
│   │   ├── 📁 ui/                # Shadcn 기반 UI 컴포넌트
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   ├── textarea.tsx
│   │   │   ├── tabs.tsx
│   │   │   └── toaster.tsx
│   │   ├── UrlInputForm.tsx      # URL 입력 + 언어 선택
│   │   ├── LoadingState.tsx      # 로딩 진행률 표시
│   │   ├── SideBySideView.tsx    # 원본/번역 분할 뷰
│   │   ├── OptionTable.tsx       # 옵션 테이블
│   │   └── ImageOcrResults.tsx   # 이미지 OCR 결과
│   │
│   ├── 📁 lib/
│   │   ├── api.ts                # Backend API 클라이언트
│   │   └── utils.ts              # 유틸리티 함수
│   │
│   ├── 📁 types/
│   │   └── index.ts              # TypeScript 타입 정의
│   │
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── env.example               # 환경변수 예제
│
├── 📁 scripts/                    # ✅ 완료
│   ├── setup-backend.bat         # Backend 설정 스크립트
│   ├── setup-frontend.bat        # Frontend 설정 스크립트
│   ├── run-backend.bat           # Backend 실행
│   ├── run-frontend.bat          # Frontend 실행
│   ├── run-all.bat               # 전체 실행
│   └── check-python.bat          # Python 버전 확인
│
├── 📁 docs/                       # 📋 문서
│   ├── PROJECT_SPEC.md           # 본 문서
│   ├── TODO.md                   # 작업 체크리스트
│   ├── CHANGELOG.md              # 변경 이력
│   └── SETUP_GUIDE.md            # 설치 가이드
│
├── .gitignore
└── README.md
```

---

## 📡 6. API 명세

### 6.1 Base URL
- **개발**: `http://localhost:8000`
- **프로덕션**: `https://your-app.railway.app`

### 6.2 Endpoints

#### `GET /api/health`
서버 상태 확인

**Response** `200 OK`
```json
{
  "status": "healthy",
  "version": "1.1.0"
}
```

---

#### `POST /api/scrape`
아이디어스 상품 페이지 크롤링

**Request Body**
```json
{
  "url": "https://www.idus.com/v2/product/12345678"
}
```

**Response** `200 OK`
```json
{
  "success": true,
  "message": "크롤링이 완료되었습니다.",
  "data": {
    "url": "https://www.idus.com/v2/product/12345678",
    "title": "수제 가죽 지갑",
    "artist_name": "가죽공방",
    "price": "45,000원",
    "description": "정성스럽게 만든 수제 가죽 지갑입니다...",
    "options": [
      {
        "name": "색상",
        "values": ["브라운", "블랙", "네이비"]
      }
    ],
    "detail_images": [
      "https://image.idus.com/image/...",
      "https://image.idus.com/image/..."
    ],
    "image_texts": []
  }
}
```

---

#### `POST /api/translate`
크롤링된 데이터 번역 (Gemini 사용)

**Request Body**
```json
{
  "product_data": { ... },
  "target_language": "en"  // "en" | "ja"
}
```

**Response** `200 OK`
```json
{
  "success": true,
  "message": "번역이 완료되었습니다.",
  "data": {
    "original": { ... },
    "translated_title": "Handmade Leather Wallet",
    "translated_description": "A carefully crafted handmade leather wallet...",
    "translated_options": [
      {
        "name": "Color",
        "values": ["Brown", "Black", "Navy"]
      }
    ],
    "translated_image_texts": [
      {
        "image_url": "https://...",
        "original_text": "배송 안내\n영업일 기준 3-5일...",
        "translated_text": "Shipping Info\n3-5 business days..."
      }
    ],
    "target_language": "en"
  }
}
```

---

## 📊 7. 진행 현황 요약

### 7.1 전체 진행률

```
Backend   ████████████████████████  100%
Frontend  ████████████████████████  100%
테스트     ░░░░░░░░░░░░░░░░░░░░░░░░    0%
───────────────────────────────────────
Total     ████████████████░░░░░░░░   80% (테스트 대기)
```

### 7.2 완료된 작업 ✅

| 카테고리 | 항목 | 완료일 |
|----------|------|--------|
| 설계 | 프로젝트 구조 설계 | 2024-12-30 |
| Backend | FastAPI main.py 구현 | 2024-12-30 |
| Backend | Pydantic 모델 정의 | 2024-12-30 |
| Backend | Playwright 크롤러 구현 | 2024-12-30 |
| Backend | Gemini 번역기 구현 | 2024-12-30 |
| Backend | Railway Dockerfile | 2024-12-30 |
| Frontend | Next.js 14 프로젝트 초기화 | 2024-12-30 |
| Frontend | Tailwind CSS + Shadcn UI | 2024-12-30 |
| Frontend | TypeScript 타입 정의 | 2024-12-30 |
| Frontend | API 클라이언트 구현 | 2024-12-30 |
| Frontend | URL 입력 폼 컴포넌트 | 2024-12-30 |
| Frontend | 언어 선택 UI (영어/일본어) | 2024-12-30 |
| Frontend | 로딩 상태 컴포넌트 | 2024-12-30 |
| Frontend | Side-by-Side 분할 뷰 | 2024-12-30 |
| Frontend | 인라인 편집 기능 | 2024-12-30 |
| Frontend | 이미지 OCR 결과 표시 | 2024-12-30 |
| Frontend | 옵션 테이블 컴포넌트 | 2024-12-30 |
| Frontend | 클립보드 복사 기능 | 2024-12-30 |
| Frontend | JSON 다운로드 기능 | 2024-12-30 |
| Frontend | 메인 페이지 통합 | 2024-12-30 |
| 설정 | 실행 스크립트 (BAT) | 2024-12-30 |
| 설정 | Gemini API 적용 | 2024-12-30 |
| 문서 | README.md 작성 | 2024-12-30 |
| 문서 | 프로젝트 기획서 작성 | 2024-12-30 |
| 문서 | 설치 가이드 작성 | 2024-12-30 |

### 7.3 미완료 작업 🔲

| 우선순위 | 카테고리 | 항목 | 상태 |
|----------|----------|------|------|
| **P0** | 테스트 | Python 3.11 설치 | ⏳ 사용자 진행 필요 |
| **P0** | 테스트 | Backend 로컬 실행 | ⏳ 대기 |
| **P0** | 테스트 | Frontend 로컬 실행 | ⏳ 대기 |
| **P0** | 테스트 | E2E 통합 테스트 | ⏳ 대기 |
| P1 | Backend | 에러 핸들링 강화 | 🔲 미완료 |
| P1 | Backend | Rate Limiting | 🔲 미완료 |
| P2 | Frontend | 다크 모드 | 🔲 미완료 |
| P2 | Backend | 번역 캐싱 | 🔲 미완료 |

---

## 🚀 8. 배포 계획

### 8.1 Backend (Railway)

**필요 환경 변수**
```
GEMINI_API_KEY=your-gemini-api-key
```

**배포 단계**
1. GitHub 레포지토리 생성
2. Railway 프로젝트 생성
3. GitHub 연동
4. 환경 변수 설정
5. 자동 배포 (Dockerfile 기반)

### 8.2 Frontend (Vercel)

**필요 환경 변수**
```
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

**배포 단계**
1. Vercel 프로젝트 생성
2. GitHub 연동 (frontend 폴더)
3. 환경 변수 설정
4. 자동 배포

---

## ⚠️ 9. 리스크 및 고려사항

### 9.1 기술적 리스크

| 리스크 | 영향도 | 대응 방안 |
|--------|--------|-----------|
| 아이디어스 페이지 구조 변경 | 높음 | 셀렉터 유지보수, 알림 시스템 |
| 봇 탐지 강화 | 중간 | stealth 옵션 업데이트, 요청 간격 조절 |
| Gemini API 제한 | 중간 | 캐싱, 요청 최적화, 유료 플랜 |
| Railway 콜드 스타트 | 낮음 | 헬스체크, 웜업 요청 |

### 9.2 비즈니스 고려사항

- 아이디어스 이용약관 확인 필요 (크롤링 정책)
- 대량 요청 시 IP 차단 가능성
- 이미지 저작권 관련 법적 검토

---

## 📎 10. 참고 자료

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Playwright Python](https://playwright.dev/python/)
- [playwright-stealth](https://github.com/nickolaj-jepsen/playwright_stealth)
- [Google Gemini API](https://ai.google.dev/docs)
- [Next.js 14 App Router](https://nextjs.org/docs/app)
- [Shadcn UI](https://ui.shadcn.com/)
- [Railway 배포 가이드](https://docs.railway.app/)

---

## 📝 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2024-12-30 | 최초 작성 (Backend 완료) | AI Assistant |
| v1.1 | 2024-12-30 | Frontend MVP 완료 | AI Assistant |
| v1.2 | 2024-12-30 | Gemini API 적용, 실행 스크립트 추가 | AI Assistant |

---

## 🔍 11. 현재 상태 진단 (v1.2)

### 11.1 구현 완료 항목

| 영역 | 구현 내용 | 상태 |
|------|-----------|------|
| **Backend API** | FastAPI 4개 엔드포인트 | ✅ 완료 |
| **크롤링** | Playwright + stealth | ✅ 완료 |
| **번역** | Google Gemini 2.0 Flash | ✅ 완료 |
| **Frontend 구조** | Next.js 14 App Router | ✅ 완료 |
| **UI 컴포넌트** | 6개 Shadcn 기반 | ✅ 완료 |
| **비즈니스 컴포넌트** | 5개 커스텀 컴포넌트 | ✅ 완료 |
| **상태 관리** | useState 기반 | ✅ 완료 |
| **API 연동** | lib/api.ts | ✅ 완료 |
| **실행 스크립트** | BAT 파일 6개 | ✅ 완료 |

### 11.2 다음 단계 (테스트)

1. **Python 3.11 설치** (사용자 진행 필요)
   - https://www.python.org/downloads/release/python-3119/

2. **Backend 설정 및 실행**
   ```cmd
   scripts\setup-backend.bat
   scripts\run-backend.bat
   ```

3. **Frontend 설정 및 실행**
   ```cmd
   scripts\setup-frontend.bat
   scripts\run-frontend.bat
   ```

4. **E2E 테스트**
   - http://localhost:3000 접속
   - 아이디어스 URL 입력
   - 번역 결과 확인

---

> 🎯 **현재 상태**: MVP 구현 완료, Python 3.11 설치 후 테스트 진행 필요
