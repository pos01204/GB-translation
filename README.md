# 🎨 Idus 작품 번역 자동화 (Idus Product Translator)

아이디어스(Idus) 핸드메이드 플랫폼의 제품 페이지를 영어/일본어로 자동 번역하는 웹 애플리케이션입니다.

[![Deploy Frontend](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/pos01204/GB-translation&root-directory=frontend)
[![Deploy Backend](https://railway.app/button.svg)](https://railway.app/template/GB-translation)

## 🚀 주요 기능

- **URL 기반 크롤링**: 아이디어스 상품 URL 입력 시 자동으로 상품 정보 수집
- **봇 탐지 우회**: playwright-stealth를 활용한 안정적인 크롤링
- **옵션 자동 추출**: '옵션 선택' 버튼 클릭하여 숨겨진 옵션까지 수집
- **이미지 OCR**: Google Gemini를 활용한 상세 이미지 내 텍스트 추출
- **다국어 번역**: 한국어 → 영어/일본어 자동 번역
- **실시간 편집**: 번역 결과 직접 수정 가능한 에디터 UI

## 🛠 기술 스택

### Frontend
- Next.js 14 (App Router)
- Tailwind CSS
- Shadcn UI
- TypeScript
- **배포**: Vercel

### Backend
- Python 3.11 + FastAPI
- Playwright + playwright-stealth
- Google Gemini 2.0 Flash API
- **배포**: Railway (Docker)

## 📦 프로젝트 구조

```
├── backend/                 # FastAPI Backend
│   ├── app/
│   │   ├── main.py          # API 엔트리포인트
│   │   ├── scraper.py       # Playwright 크롤링
│   │   ├── translator.py    # Gemini 번역/OCR
│   │   └── models.py        # Pydantic 모델
│   ├── Dockerfile           # Railway 배포용
│   ├── railway.toml
│   └── requirements.txt
│
├── frontend/                # Next.js Frontend
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── vercel.json          # Vercel 배포 설정
│   └── package.json
│
├── docs/                    # 문서
│   ├── PROJECT_SPEC.md
│   ├── SETUP_GUIDE.md
│   └── CHANGELOG.md
│
└── scripts/                 # 실행 스크립트 (Windows)
```

## 🌐 배포

### Backend (Railway)

1. [Railway](https://railway.app) 접속 및 로그인
2. "New Project" → "Deploy from GitHub repo"
3. `pos01204/GB-translation` 선택
4. Root Directory: `backend` 설정
5. 환경 변수 추가:
   ```
   GEMINI_API_KEY=your-gemini-api-key
   ```
6. Deploy!

### Frontend (Vercel)

1. [Vercel](https://vercel.com) 접속 및 로그인
2. "New Project" → GitHub 연동
3. `pos01204/GB-translation` 선택
4. Root Directory: `frontend` 설정
5. 환경 변수 추가:
   ```
   NEXT_PUBLIC_API_URL=https://your-railway-backend.up.railway.app
   ```
6. Deploy!

## 🏃‍♂️ 로컬 실행 방법

### 사전 요구사항
- Python 3.11 (⚠️ 3.14는 호환 안됨)
- Node.js 18+
- Google Gemini API Key

### Backend

```bash
cd backend
pip install -r requirements.txt
playwright install chromium

# .env 파일 생성
echo "GEMINI_API_KEY=your-api-key" > .env

# 서버 실행
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# .env.local 파일 생성
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# 개발 서버 실행
npm run dev
```

### Windows 사용자 (간편 실행)

```
scripts\setup-backend.bat    # Backend 설정
scripts\setup-frontend.bat   # Frontend 설정
scripts\run-all.bat          # 전체 실행
```

## 🔑 환경 변수

### Backend (.env)
| 변수 | 설명 | 필수 |
|------|------|------|
| `GEMINI_API_KEY` | Google Gemini API 키 | ✅ |

### Frontend (.env.local)
| 변수 | 설명 | 필수 |
|------|------|------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | ✅ |

## 📝 API 엔드포인트

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | 서버 상태 확인 |
| POST | `/api/scrape` | URL로 상품 정보 크롤링 |
| POST | `/api/translate` | 크롤링된 데이터 번역 |
| POST | `/api/scrape-and-translate` | 크롤링 + 번역 통합 |

## 📚 문서

- [설치 가이드](docs/SETUP_GUIDE.md)
- [프로젝트 기획서](docs/PROJECT_SPEC.md)
- [변경 이력](docs/CHANGELOG.md)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

Made with ❤️ for Global Business
