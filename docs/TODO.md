# ✅ TODO - 작업 체크리스트

> 최종 업데이트: 2024-12-30

---

## 📍 현재 단계: MVP 완료 ✅ → Python 3.11 설치 후 테스트 필요

---

## Phase 1: Backend 기본 구현 ✅ 완료

- [x] 프로젝트 구조 설계
- [x] FastAPI 서버 설정 (`main.py`)
- [x] Pydantic 모델 정의 (`models.py`)
- [x] Playwright 크롤러 (`scraper.py`)
  - [x] playwright-stealth 적용
  - [x] 상품 기본 정보 추출
  - [x] 옵션 버튼 클릭 로직
  - [x] 상세 이미지 URL 수집
- [x] ~~GPT-4o 번역기~~ → **Gemini 번역기** (`translator.py`)
  - [x] 텍스트 번역
  - [x] 이미지 OCR
  - [x] 옵션 번역
- [x] Railway Dockerfile
- [x] railway.toml 설정

---

## Phase 2: Frontend 기본 구현 ✅ 완료

### 2.1 프로젝트 초기화 ✅
- [x] Next.js 14 프로젝트 생성
- [x] Tailwind CSS 설정
- [x] Shadcn UI 컴포넌트 구축
- [x] TypeScript 타입 정의

### 2.2 레이아웃 및 공통 ✅
- [x] 루트 레이아웃 (`app/layout.tsx`)
- [x] 글로벌 스타일 (`globals.css`)
- [x] API 클라이언트 (`lib/api.ts`)
- [x] 유틸리티 함수 (`lib/utils.ts`)

### 2.3 UI 컴포넌트 ✅
- [x] Button, Input, Textarea, Card
- [x] Tabs (탭 네비게이션)
- [x] Toaster (알림)

### 2.4 비즈니스 컴포넌트 ✅
- [x] **UrlInputForm** - URL 입력 + 언어 선택
- [x] **LoadingState** - 진행률 표시 (4단계)
- [x] **SideBySideView** - 원본/번역 분할 뷰
- [x] **OptionTable** - 옵션 테이블
- [x] **ImageOcrResults** - 이미지 OCR 결과

### 2.5 기능 구현 ✅
- [x] 메인 페이지 상태 관리
- [x] API 연동 (scrape + translate)
- [x] 인라인 편집 기능
- [x] 클립보드 복사
- [x] JSON 다운로드

---

## Phase 2.5: Gemini API 적용 ✅ 완료

- [x] `translator.py` OpenAI → Gemini 변경
- [x] `main.py` 환경변수 변경 (OPENAI_API_KEY → GEMINI_API_KEY)
- [x] `requirements.txt` 업데이트 (google-generativeai)
- [x] 환경변수 예제 파일 업데이트
- [x] 설치 가이드 업데이트

---

## Phase 3: 테스트 및 배포 ⏳ 진행 중

### 사전 준비 (사용자 진행 필요)
- [ ] **Python 3.11 설치**
  - 다운로드: https://www.python.org/downloads/release/python-3119/
  - ⚠️ 설치 시 "Add Python to PATH" 체크 필수

### Backend 테스트
- [ ] `scripts\setup-backend.bat` 실행
- [ ] `.env` 파일에 Gemini API 키 설정
- [ ] `scripts\run-backend.bat` 실행
- [ ] http://localhost:8000/docs 접속 확인
- [ ] 실제 아이디어스 URL 크롤링 테스트
- [ ] Gemini 번역 품질 확인

### Frontend 테스트
- [ ] `scripts\setup-frontend.bat` 실행
- [ ] `scripts\run-frontend.bat` 실행
- [ ] http://localhost:3000 접속 확인
- [ ] API 연동 테스트
- [ ] UI 반응형 테스트

### E2E 통합 테스트
- [ ] URL 입력 → 크롤링 → 번역 → 결과 표시
- [ ] 영어 번역 테스트
- [ ] 일본어 번역 테스트
- [ ] 이미지 OCR 테스트
- [ ] 편집 기능 테스트
- [ ] 다운로드 기능 테스트

### 배포
- [ ] Backend → Railway 배포
- [ ] Frontend → Vercel 배포
- [ ] 환경 변수 설정
- [ ] 프로덕션 E2E 테스트

---

## Phase 4: 개선 (선택) 🔲 대기

- [ ] 다크 모드 지원
- [ ] 에러 핸들링 강화 (재시도 로직)
- [ ] Rate Limiting
- [ ] API 인증 (API Key)
- [ ] 번역 캐싱 (중복 요청 방지)
- [ ] 용어집(Glossary) 커스텀
- [ ] CSV 다운로드 추가
- [ ] 번역 히스토리 저장 (로컬 스토리지)

---

## 🎯 마일스톤

| 마일스톤 | 목표 | 상태 |
|----------|------|------|
| M1 | Backend MVP 완료 | ✅ 완료 |
| M2 | Frontend MVP 완료 | ✅ 완료 |
| M2.5 | Gemini API 적용 | ✅ 완료 |
| M3 | 통합 테스트 완료 | ⏳ Python 3.11 설치 후 진행 |
| M4 | 프로덕션 배포 | 🔲 대기 |

---

## 📝 메모

### 실행 방법 (Windows)

**간편 실행 (배치 스크립트)**
```
1. scripts\setup-backend.bat 더블클릭
2. backend\.env 파일에 GEMINI_API_KEY 설정
3. scripts\setup-frontend.bat 더블클릭
4. scripts\run-all.bat 더블클릭
```

**수동 실행**
```bash
# Backend
cd backend
py -3.11 -m pip install -r requirements.txt
py -3.11 -m playwright install chromium
# .env 파일에 GEMINI_API_KEY 설정
py -3.11 -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
# .env.local 파일에 NEXT_PUBLIC_API_URL 설정
npm run dev
```

### 환경 변수

| 파일 | 변수 | 설명 |
|------|------|------|
| `backend/.env` | `GEMINI_API_KEY` | Google Gemini API 키 |
| `frontend/.env.local` | `NEXT_PUBLIC_API_URL` | Backend API URL |

### 주의사항
- Python 3.14는 호환되지 않음 → **Python 3.11 또는 3.12 사용**
- 아이디어스 페이지 구조 변경 시 `scraper.py` 셀렉터 업데이트 필요
- Gemini API 무료 tier는 분당 요청 제한 있음
