"""
FastAPI 메인 엔트리포인트
아이디어스 상품 크롤링 및 번역 API
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .models import (
    ScrapeRequest,
    ScrapeResponse,
    TranslateRequest,
    TranslateResponse,
    HealthResponse,
)
from .scraper import IdusScraper
from .translator import ProductTranslator

# 환경 변수 로드
load_dotenv()

# 전역 인스턴스
scraper: IdusScraper | None = None
translator: ProductTranslator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 라이프사이클 관리 - 시작/종료 시 리소스 관리"""
    global scraper, translator
    
    # 시작 시 초기화
    print("🚀 서버 시작 - 리소스 초기화 중...")
    
    # Gemini API 키 확인
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("⚠️ 경고: GEMINI_API_KEY가 설정되지 않았습니다.")
    else:
        print("✅ Gemini API 키 확인됨")
    
    scraper = IdusScraper()
    translator = ProductTranslator(api_key=gemini_api_key)
    
    await scraper.initialize()
    print("✅ Playwright 브라우저 초기화 완료")
    
    yield
    
    # 종료 시 정리
    print("🛑 서버 종료 - 리소스 정리 중...")
    if scraper:
        await scraper.close()
    print("✅ 리소스 정리 완료")


# FastAPI 앱 생성
app = FastAPI(
    title="Idus Product Translator API",
    description="아이디어스 상품 크롤링 및 다국어 번역 API (Powered by Google Gemini)",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS 설정 (프론트엔드 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # 로컬 개발
        "https://*.vercel.app",   # Vercel 배포
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    서버 상태 확인 엔드포인트
    """
    return HealthResponse(
        status="healthy",
        version="1.1.0"
    )


@app.post("/api/scrape", response_model=ScrapeResponse, tags=["Scraping"])
async def scrape_product(request: ScrapeRequest):
    """
    아이디어스 상품 URL을 받아서 크롤링 수행
    
    - **url**: 아이디어스 상품 페이지 URL
    
    상품명, 작가명, 가격, 설명, 옵션, 상세 이미지 등을 수집합니다.
    """
    global scraper
    
    if not scraper:
        raise HTTPException(status_code=500, detail="스크래퍼가 초기화되지 않았습니다.")
    
    # URL 유효성 검사
    if "idus.com" not in request.url:
        raise HTTPException(
            status_code=400, 
            detail="유효한 아이디어스 URL이 아닙니다."
        )
    
    try:
        product_data = await scraper.scrape_product(request.url)
        
        return ScrapeResponse(
            success=True,
            message="크롤링이 완료되었습니다.",
            data=product_data
        )
        
    except Exception as e:
        return ScrapeResponse(
            success=False,
            message=f"크롤링 중 오류 발생: {str(e)}",
            data=None
        )


@app.post("/api/translate", response_model=TranslateResponse, tags=["Translation"])
async def translate_product(request: TranslateRequest):
    """
    크롤링된 상품 데이터를 번역
    
    - **product_data**: 크롤링된 상품 데이터
    - **target_language**: 번역 대상 언어 (en: 영어, ja: 일본어)
    
    Google Gemini를 사용하여 상품 정보와 이미지 내 텍스트를 번역합니다.
    """
    global translator
    
    if not translator:
        raise HTTPException(status_code=500, detail="번역기가 초기화되지 않았습니다.")
    
    try:
        translated_data = await translator.translate_product(
            product_data=request.product_data,
            target_language=request.target_language
        )
        
        return TranslateResponse(
            success=True,
            message="번역이 완료되었습니다.",
            data=translated_data
        )
        
    except Exception as e:
        return TranslateResponse(
            success=False,
            message=f"번역 중 오류 발생: {str(e)}",
            data=None
        )


@app.post("/api/scrape-and-translate", response_model=TranslateResponse, tags=["Combined"])
async def scrape_and_translate(url: str, target_language: str = "en"):
    """
    URL 크롤링부터 번역까지 한 번에 수행
    
    - **url**: 아이디어스 상품 페이지 URL
    - **target_language**: 번역 대상 언어 (en/ja)
    """
    global scraper, translator
    
    if not scraper or not translator:
        raise HTTPException(status_code=500, detail="서비스가 초기화되지 않았습니다.")
    
    # URL 유효성 검사
    if "idus.com" not in url:
        raise HTTPException(
            status_code=400, 
            detail="유효한 아이디어스 URL이 아닙니다."
        )
    
    try:
        # 1. 크롤링
        product_data = await scraper.scrape_product(url)
        
        # 2. 번역
        from .models import TargetLanguage
        lang = TargetLanguage.ENGLISH if target_language == "en" else TargetLanguage.JAPANESE
        
        translated_data = await translator.translate_product(
            product_data=product_data,
            target_language=lang
        )
        
        return TranslateResponse(
            success=True,
            message="크롤링 및 번역이 완료되었습니다.",
            data=translated_data
        )
        
    except Exception as e:
        return TranslateResponse(
            success=False,
            message=f"처리 중 오류 발생: {str(e)}",
            data=None
        )


# 개발용 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
