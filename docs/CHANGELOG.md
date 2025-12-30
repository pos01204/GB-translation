# 📜 Changelog

이 프로젝트의 모든 주요 변경 사항을 문서화합니다.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따릅니다.

---

## [Unreleased]

### 🔜 예정
- 다크 모드 지원
- 에러 핸들링 강화 (재시도 로직)
- Rate Limiting 구현
- 번역 캐싱 시스템

---

## [0.3.0] - 2024-12-30

### 🔄 Changed (변경됨)

#### AI 모델 변경: OpenAI GPT-4o → Google Gemini
- **translator.py**: OpenAI SDK → google-generativeai SDK로 변경
- **모델**: gemini-2.0-flash-exp 사용 (빠르고 비용 효율적)
- **main.py**: 환경변수 `OPENAI_API_KEY` → `GEMINI_API_KEY`로 변경

#### 의존성 변경
- **requirements.txt**: `openai` 제거, `google-generativeai==0.8.3` 추가

#### 문서 업데이트
- **SETUP_GUIDE.md**: Gemini API 키 발급 방법 추가
- **env.example**: GEMINI_API_KEY 설정 안내

### 🎉 Added (추가됨)

#### 실행 스크립트 개선
- `check-python.bat` - Python 버전 확인 스크립트
- 모든 스크립트에 Python 버전 자동 감지 기능 추가
- Python 3.11/3.12 자동 선택 로직

---

## [0.2.0] - 2024-12-30

### 🎉 Added (추가됨)

#### Frontend MVP 완료
- **Next.js 14 App Router 프로젝트 구조**
  - `app/layout.tsx` - 루트 레이아웃 (헤더/푸터 포함)
  - `app/page.tsx` - 메인 페이지 (상태 관리 통합)
  - `app/globals.css` - Tailwind 기반 글로벌 스타일

- **Shadcn 기반 UI 컴포넌트**
  - `components/ui/button.tsx` - 다양한 variant 버튼
  - `components/ui/input.tsx` - 텍스트 입력
  - `components/ui/textarea.tsx` - 멀티라인 입력
  - `components/ui/card.tsx` - 카드 레이아웃
  - `components/ui/tabs.tsx` - 탭 네비게이션
  - `components/ui/toaster.tsx` - 토스트 알림

- **비즈니스 컴포넌트**
  - `UrlInputForm.tsx` - URL 입력 + 영어/일본어 선택 토글
  - `LoadingState.tsx` - 4단계 진행률 표시 (크롤링→번역→OCR→완료)
  - `SideBySideView.tsx` - 원본/번역 분할 뷰 + 인라인 편집
  - `OptionTable.tsx` - 옵션 원본/번역 테이블 + 편집
  - `ImageOcrResults.tsx` - 이미지 OCR 결과 아코디언

- **유틸리티**
  - `lib/api.ts` - Backend API 클라이언트 (타입 포함)
  - `lib/utils.ts` - 공통 유틸리티 함수
  - `types/index.ts` - TypeScript 타입 정의

- **기능**
  - URL 유효성 검사 (idus.com 도메인)
  - 크롤링 + 번역 순차 처리
  - 번역 결과 인라인 편집
  - 클립보드 복사 (제목, 설명, 옵션)
  - JSON 다운로드
  - 토스트 알림 (성공/에러)
  - 반응형 레이아웃

#### 실행 스크립트
- `scripts/setup-backend.bat` - Backend 의존성 설치
- `scripts/setup-frontend.bat` - Frontend 의존성 설치
- `scripts/run-backend.bat` - Backend 서버 실행
- `scripts/run-frontend.bat` - Frontend 서버 실행
- `scripts/run-all.bat` - 전체 동시 실행

---

## [0.1.0] - 2024-12-30

### 🎉 Added (추가됨)

#### Backend 핵심 구조
- FastAPI 서버 초기 설정 (`main.py`)
- Pydantic 데이터 모델 정의 (`models.py`)
  - `ScrapeRequest`, `ScrapeResponse`
  - `TranslateRequest`, `TranslateResponse`
  - `ProductData`, `TranslatedProduct`
  - `ProductOption`, `ImageText`

#### 크롤링 모듈
- Playwright 기반 크롤러 (`scraper.py`)
- playwright-stealth 봇 탐지 우회 적용
- 상품 정보 추출 (제목, 작가, 가격, 설명)
- '옵션 선택' 버튼 자동 클릭
- 숨겨진 옵션 텍스트 추출
- 상세 이미지 URL 수집

#### 번역 모듈 (초기 버전)
- GPT-4o 기반 번역기 (`translator.py`)
- 이미지 OCR (Vision API 활용)
- 한국어 → 영어 번역
- 한국어 → 일본어 번역
- 옵션값 번역 지원

#### API 엔드포인트
- `GET /api/health` - 헬스체크
- `POST /api/scrape` - 상품 크롤링
- `POST /api/translate` - 번역 수행
- `POST /api/scrape-and-translate` - 통합 처리

#### 배포 설정
- Railway용 Dockerfile
- railway.toml 설정 파일
- requirements.txt 의존성 정의

#### 문서
- README.md 프로젝트 소개
- PROJECT_SPEC.md 기획서
- TODO.md 작업 체크리스트
- CHANGELOG.md 변경 이력

---

## 버전 관리 규칙

- **Major (X.0.0)**: 호환되지 않는 API 변경
- **Minor (0.X.0)**: 하위 호환 기능 추가
- **Patch (0.0.X)**: 하위 호환 버그 수정

---

[Unreleased]: https://github.com/your-repo/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/your-repo/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/your-repo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/your-repo/releases/tag/v0.1.0
