# 🚀 배포 가이드

이 문서는 Idus Product Translator를 Vercel과 Railway에 배포하는 방법을 설명합니다.

## 📋 사전 준비

### 필요한 계정
- [GitHub](https://github.com) 계정
- [Vercel](https://vercel.com) 계정 (GitHub 연동)
- [Railway](https://railway.app) 계정 (GitHub 연동)
- [Google AI Studio](https://aistudio.google.com) 계정 (Gemini API 키)

### 레포지토리
- GitHub: https://github.com/pos01204/GB-translation

---

## 🔧 Step 1: GitHub에 코드 푸시

### 1.1 Git 초기화 및 연결

```bash
cd "작품 번역 자동화"

# Git 초기화
git init

# 원격 저장소 연결
git remote add origin https://github.com/pos01204/GB-translation.git

# 모든 파일 추가
git add .

# 커밋
git commit -m "Initial commit: Idus Product Translator MVP"

# 푸시
git push -u origin main
```

### 1.2 푸시할 파일 확인

```
GB-translation/
├── backend/           ✅ Railway 배포
├── frontend/          ✅ Vercel 배포
├── docs/              ✅ 문서
├── scripts/           ✅ 로컬 실행 스크립트
├── .gitignore         ✅ Git 제외 파일
└── README.md          ✅ 프로젝트 소개
```

---

## 🚂 Step 2: Railway Backend 배포

### 2.1 Railway 프로젝트 생성

1. [Railway](https://railway.app) 접속
2. **"New Project"** 클릭
3. **"Deploy from GitHub repo"** 선택
4. GitHub 계정 연동 (처음인 경우)
5. **`pos01204/GB-translation`** 레포지토리 선택

### 2.2 서비스 설정

1. 프로젝트 생성 후 **Settings** 탭 클릭
2. **Root Directory** 설정:
   ```
   backend
   ```
3. **Watch Paths** 설정 (선택):
   ```
   backend/**
   ```

### 2.3 환경 변수 설정

**Variables** 탭에서 추가:

| Variable | Value |
|----------|-------|
| `GEMINI_API_KEY` | `AIzaSyB4HcvCL8x_vUGH1he5p5wI3erIlom4s5Y` |
| `PORT` | `8000` (자동 설정됨) |

### 2.4 배포 확인

1. **Deployments** 탭에서 빌드 로그 확인
2. 배포 완료 후 **Settings** → **Domains**에서 URL 확인
3. 예: `https://gb-translation-production.up.railway.app`

### 2.5 헬스체크 테스트

```bash
curl https://your-railway-url.up.railway.app/api/health
```

응답:
```json
{"status": "healthy", "version": "1.1.0"}
```

---

## ▲ Step 3: Vercel Frontend 배포

### 3.1 Vercel 프로젝트 생성

1. [Vercel](https://vercel.com) 접속
2. **"Add New..."** → **"Project"** 클릭
3. **"Import Git Repository"** 선택
4. **`pos01204/GB-translation`** 선택

### 3.2 프로젝트 설정

| 설정 | 값 |
|------|-----|
| **Framework Preset** | Next.js |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` |
| **Output Directory** | `.next` |
| **Install Command** | `npm install` |

### 3.3 환경 변수 설정

**Environment Variables** 섹션에서 추가:

| Name | Value |
|------|-------|
| `NEXT_PUBLIC_API_URL` | `https://your-railway-url.up.railway.app` |

⚠️ **중요**: Railway 배포 URL을 정확히 입력하세요!

### 3.4 배포

1. **"Deploy"** 버튼 클릭
2. 빌드 로그 확인
3. 배포 완료 후 URL 확인
4. 예: `https://gb-translation.vercel.app`

---

## 🔗 Step 4: 연동 확인

### 4.1 CORS 설정 확인

Backend `main.py`에서 Vercel URL이 허용되어 있는지 확인:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",  # ✅ Vercel 허용
    ],
    ...
)
```

### 4.2 E2E 테스트

1. Vercel URL 접속 (예: `https://gb-translation.vercel.app`)
2. 아이디어스 상품 URL 입력
3. 언어 선택 (영어/일본어)
4. "크롤링 & 번역 시작" 클릭
5. 결과 확인

---

## 🔄 Step 5: 자동 배포 설정

### GitHub Push 시 자동 배포

Railway와 Vercel 모두 GitHub 연동 시 자동으로:
- `main` 브랜치에 푸시하면 자동 배포
- PR 생성 시 Preview 배포 (Vercel)

### 배포 트리거

| 이벤트 | Railway | Vercel |
|--------|---------|--------|
| Push to main | ✅ 자동 배포 | ✅ 자동 배포 |
| Pull Request | ❌ | ✅ Preview |
| Manual | ✅ Redeploy | ✅ Redeploy |

---

## 🐛 문제 해결

### Railway 빌드 실패

**증상**: Dockerfile 빌드 오류

**해결**:
1. Railway 대시보드에서 로그 확인
2. `backend/Dockerfile` 수정 후 재푸시

### Vercel 빌드 실패

**증상**: Next.js 빌드 오류

**해결**:
1. 로컬에서 `npm run build` 테스트
2. 에러 수정 후 재푸시

### CORS 오류

**증상**: Frontend에서 API 호출 시 CORS 에러

**해결**:
1. Backend `main.py`의 `allow_origins` 확인
2. Vercel 도메인 추가
3. Railway 재배포

### API 연결 실패

**증상**: Frontend에서 Backend 연결 안됨

**해결**:
1. Vercel 환경 변수 `NEXT_PUBLIC_API_URL` 확인
2. Railway URL이 정확한지 확인
3. Railway 서비스가 실행 중인지 확인

---

## 📊 배포 URL 요약

| 서비스 | URL | 용도 |
|--------|-----|------|
| **Frontend** | `https://gb-translation.vercel.app` | 사용자 UI |
| **Backend** | `https://gb-translation-xxx.up.railway.app` | API 서버 |
| **API Docs** | `https://gb-translation-xxx.up.railway.app/docs` | Swagger UI |

---

## 💰 비용 안내

### Railway
- **Free Tier**: 월 $5 크레딧 (약 500시간)
- **Hobby**: $5/월 (충분한 사용량)

### Vercel
- **Free Tier**: 개인 프로젝트 무료
- **Pro**: $20/월 (팀 사용 시)

### Gemini API
- **Free Tier**: 분당 60 요청
- **Pay-as-you-go**: 사용량 기반 과금

---

> 🎉 배포 완료! 이제 전 세계 어디서나 서비스에 접속할 수 있습니다.

