# 🚀 설치 및 실행 가이드

## 📋 사전 요구사항

| 요구사항 | 버전 | 비고 |
|----------|------|------|
| **Python** | 3.11 또는 3.12 | ⚠️ 3.14는 호환 안됨 |
| **Node.js** | 18+ | Frontend용 |
| **Google Gemini API Key** | - | 번역/OCR 사용 |

### ⚠️ Python 버전 주의사항

**Python 3.14는 사용할 수 없습니다!**

- Python 3.14는 아직 알파/베타 버전으로, `pydantic-core` 등 일부 패키지가 호환되지 않습니다.
- **Python 3.11** 또는 **Python 3.12**를 사용해주세요.

**Python 3.11 다운로드:**
- https://www.python.org/downloads/release/python-3119/
- Windows: "Windows installer (64-bit)" 다운로드

---

## 🔑 Gemini API 키 발급

이 프로젝트는 **Google Gemini API**를 사용합니다.

### API 키 발급 방법

1. [Google AI Studio](https://aistudio.google.com/apikey) 접속
2. Google 계정으로 로그인
3. "Create API Key" 클릭
4. 프로젝트 선택 또는 새 프로젝트 생성
5. 생성된 API 키 복사

### 무료 사용량
- Gemini API는 무료 tier가 있어 테스트에 충분합니다
- 분당 요청 제한이 있으니 대량 사용 시 유료 플랜 고려

---

## ⚡ 빠른 시작 (Windows)

### 방법 1: 배치 스크립트 사용

1. **Backend 설정**
   ```
   scripts\setup-backend.bat 더블클릭
   ```

2. **Frontend 설정**
   ```
   scripts\setup-frontend.bat 더블클릭
   ```

3. **전체 실행**
   ```
   scripts\run-all.bat 더블클릭
   ```

### 방법 2: 수동 설정

아래 단계별 가이드를 따라주세요.

---

## 🔧 Step 1: Python 3.11 설치 (필수)

### 1.1 현재 Python 버전 확인
```cmd
python --version
```

### 1.2 Python 3.11이 없다면 설치

1. https://www.python.org/downloads/release/python-3119/ 접속
2. **Windows installer (64-bit)** 다운로드
3. 설치 시 **⚠️ "Add Python to PATH" 체크박스 반드시 선택!**
4. 설치 완료

### 1.3 여러 Python 버전이 있는 경우

Windows에서는 `py` launcher로 특정 버전 사용:
```cmd
py -3.11 --version
py -3.11 -m pip install package_name
```

---

## 🔧 Step 2: Backend 설정

### 2.1 디렉토리 이동
```cmd
cd backend
```

### 2.2 가상환경 생성 (권장)
```cmd
py -3.11 -m venv venv
.\venv\Scripts\activate
```

### 2.3 의존성 설치
```cmd
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.4 Playwright 브라우저 설치
```cmd
playwright install chromium
```

### 2.5 환경 변수 설정 ⭐ 중요
```cmd
copy env.example .env
notepad .env
```

`.env` 파일 내용 (Gemini API 키 입력):
```
GEMINI_API_KEY=AIzaSyB4HcvCL8x_vUGH1he5p5wI3erIlom4s5Y
```

### 2.6 서버 실행
```cmd
uvicorn app.main:app --reload --port 8000
```

✅ 성공 시 출력:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
🚀 서버 시작 - 리소스 초기화 중...
✅ Gemini API 키 확인됨
✅ Playwright 브라우저 초기화 완료
```

### 2.7 API 테스트
브라우저에서 열기: http://localhost:8000/docs

---

## 🎨 Step 3: Frontend 설정

### 3.1 새 터미널 열기 & 디렉토리 이동
```cmd
cd frontend
```

### 3.2 의존성 설치
```cmd
npm install
```

### 3.3 환경 변수 설정
```cmd
copy env.example .env.local
```

`.env.local` 파일 내용:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3.4 개발 서버 실행
```cmd
npm run dev
```

✅ 성공 시 출력:
```
▲ Next.js 14.1.0
- Local:        http://localhost:3000
```

### 3.5 브라우저에서 확인
http://localhost:3000 접속

---

## 🧪 Step 4: 기능 테스트

### 테스트 시나리오

1. **URL 입력**
   - 아이디어스 상품 URL 입력
   - 예: `https://www.idus.com/v2/product/xxxxx`

2. **언어 선택**
   - 🇺🇸 English 또는 🇯🇵 日本語 선택

3. **번역 실행**
   - "크롤링 & 번역 시작" 버튼 클릭
   - 진행률 확인 (크롤링 → 번역 → OCR → 완료)

4. **결과 확인**
   - 원본/번역 비교 뷰
   - 옵션 테이블
   - 이미지 OCR 결과

5. **편집 & 다운로드**
   - 텍스트 클릭하여 편집
   - 복사 버튼으로 클립보드 복사
   - JSON 다운로드 버튼

---

## 🐛 문제 해결

### ❌ Python 3.14 pydantic-core 오류

**증상:**
```
error: metadata-generation-failed
× Encountered error while generating package metadata.
╰─> pydantic-core
```

**원인:** Python 3.14는 너무 최신 버전으로 패키지 호환 안됨

**해결:**
1. Python 3.11 설치: https://www.python.org/downloads/release/python-3119/
2. `py -3.11 -m pip install -r requirements.txt` 사용

---

### ❌ pip이 인식되지 않음

**해결:**
```cmd
python -m pip install package_name
```
또는
```cmd
py -3.11 -m pip install package_name
```

---

### ❌ Playwright 설치 오류

**해결:**
```cmd
# 관리자 권한으로 실행
playwright install chromium --with-deps
```

---

### ❌ npm 설치 오류

**해결:**
```cmd
npm cache clean --force
rd /s /q node_modules
npm install
```

---

### ❌ Gemini API 오류

**증상:**
```
번역 오류: API key not valid
```

**해결:**
1. `.env` 파일에 올바른 API 키가 있는지 확인
2. API 키에 공백이나 따옴표가 없는지 확인
3. Google AI Studio에서 키가 활성화되어 있는지 확인

---

### ❌ CORS 오류

Backend `main.py`의 CORS 설정 확인:
- `allow_origins`에 Frontend URL 포함 여부

---

## 📁 최종 폴더 구조

```
작품 번역 자동화/
├── backend/
│   ├── .env              ← Gemini API 키 설정
│   ├── venv/             ← 가상환경 (선택)
│   └── ...
├── frontend/
│   ├── .env.local        ← Backend URL 설정
│   ├── node_modules/
│   └── ...
├── scripts/
│   ├── setup-backend.bat
│   ├── setup-frontend.bat
│   ├── run-backend.bat
│   ├── run-frontend.bat
│   └── run-all.bat
└── docs/
    └── SETUP_GUIDE.md
```

---

## 🔑 환경 변수 요약

| 파일 | 변수 | 값 |
|------|------|-----|
| `backend/.env` | `GEMINI_API_KEY` | Google Gemini API 키 |
| `frontend/.env.local` | `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |

---

## 🌐 접속 URL

| 서비스 | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API 문서 (Swagger) | http://localhost:8000/docs |

---

## 🤖 AI 모델 정보

이 프로젝트는 **Google Gemini 2.0 Flash**를 사용합니다.

| 기능 | 모델 |
|------|------|
| 텍스트 번역 | gemini-2.0-flash-exp |
| 이미지 OCR | gemini-2.0-flash-exp |

**장점:**
- 빠른 응답 속도
- 비용 효율적
- 이미지 분석 지원

---

> 🎉 설정 완료 후 http://localhost:3000 에서 서비스를 이용할 수 있습니다!
