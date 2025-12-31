"""
FastAPI 메인 엔트리포인트
아이디어스 상품 크롤링 및 번역 API
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .models import (
    ScrapeRequest,
    ScrapeResponse,
    TranslateRequest,
    TranslateResponse,
    HealthResponse,
    BatchTranslateRequest,
    BatchTranslateResponse,
    BatchItemResult,
    TargetLanguage,
)
from .scraper import IdusScraper
from .translator import ProductTranslator

# 환경 변수 로드
load_dotenv()

# 전역 인스턴스
scraper: IdusScraper | None = None
translator: ProductTranslator | None = None
is_initialized: bool = False


async def initialize_services():
    """서비스 초기화 (지연 초기화)"""
    global scraper, translator, is_initialized
    
    if is_initialized:
        return
    
    print("\n" + "="*60)
    print("🔧 서비스 초기화 시작")
    print("="*60)
    
    # Gemini API 키 확인
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY 환경변수가 설정되지 않았습니다!")
        print("   Railway 대시보드에서 환경변수를 설정해주세요.")
    else:
        # API 키 일부만 표시 (보안)
        masked_key = gemini_api_key[:8] + "..." + gemini_api_key[-4:] if len(gemini_api_key) > 12 else "***"
        print(f"✅ Gemini API 키 확인됨: {masked_key}")
    
    # Translator 초기화
    print("\n📌 Translator 초기화...")
    translator = ProductTranslator(api_key=gemini_api_key)
    if translator._initialized:
        print(f"✅ Translator 초기화 성공 (모델: {translator._model_name})")
    else:
        print("❌ Translator 초기화 실패 - 번역 기능이 작동하지 않습니다")
    
    # Scraper 초기화
    print("\n📌 Scraper 초기화...")
    try:
        scraper = IdusScraper()
        await scraper.initialize()
        print("✅ Playwright 브라우저 초기화 완료")
    except Exception as e:
        print(f"❌ Playwright 초기화 실패: {e}")
        scraper = None
    
    is_initialized = True
    print("\n" + "="*60)
    print("✅ 서비스 초기화 완료")
    print("="*60 + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 라이프사이클 관리 - 시작/종료 시 리소스 관리"""
    global scraper
    
    # 시작 시 - 헬스체크용 최소 초기화만 수행
    print("🚀 서버 시작...")
    print(f"📍 PORT: {os.getenv('PORT', '8000')}")
    
    yield
    
    # 종료 시 정리
    print("🛑 서버 종료 - 리소스 정리 중...")
    if scraper:
        try:
            await scraper.close()
        except Exception as e:
            print(f"⚠️ 리소스 정리 중 오류: {e}")
    print("✅ 리소스 정리 완료")


# FastAPI 앱 생성
app = FastAPI(
    title="Idus Product Translator API",
    description="아이디어스 상품 크롤링 및 다국어 번역 API (Powered by Google Gemini)",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS 설정 - 모든 오리진 허용 (프로덕션에서는 제한 권장)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 오리진 허용
    allow_credentials=False,  # credentials와 * 는 함께 사용 불가
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """루트 엔드포인트 - API 정보"""
    return {
        "name": "Idus Product Translator API",
        "version": "1.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    서버 상태 확인 엔드포인트
    Railway 헬스체크용 - 항상 즉시 응답
    """
    return HealthResponse(
        status="healthy",
        version="1.1.0"
    )


@app.options("/api/scrape")
async def scrape_options():
    """CORS preflight 요청 처리"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.post("/api/scrape", response_model=ScrapeResponse, tags=["Scraping"])
async def scrape_product(request: ScrapeRequest):
    """
    아이디어스 상품 URL을 받아서 크롤링 수행
    
    - **url**: 아이디어스 상품 페이지 URL
    
    상품명, 작가명, 가격, 설명, 옵션, 상세 이미지 등을 수집합니다.
    """
    global scraper
    
    # 지연 초기화
    await initialize_services()
    
    if not scraper:
        return ScrapeResponse(
            success=False,
            message="스크래퍼가 초기화되지 않았습니다. 서버 로그를 확인해주세요.",
            data=None
        )
    
    # URL 유효성 검사
    if "idus.com" not in request.url:
        return ScrapeResponse(
            success=False,
            message="유효한 아이디어스 URL이 아닙니다.",
            data=None
        )
    
    try:
        product_data = await scraper.scrape_product(request.url)
        
        return ScrapeResponse(
            success=True,
            message="크롤링이 완료되었습니다.",
            data=product_data
        )
        
    except Exception as e:
        print(f"❌ 크롤링 오류: {e}")
        return ScrapeResponse(
            success=False,
            message=f"크롤링 중 오류 발생: {str(e)}",
            data=None
        )


@app.get("/api/debug/scrape", tags=["Debug"])
async def debug_scrape(url: str):
    """
    운영 진단용 디버그 엔드포인트.
    - 옵션/이미지 개수, 일부 샘플 URL을 반환합니다.
    """
    global scraper
    await initialize_services()
    if not scraper:
        return {"success": False, "message": "스크래퍼가 초기화되지 않았습니다."}
    try:
        data = await scraper.scrape_product(url)
        return {
            "success": True,
            "url": data.url,
            "title": data.title,
            "artist_name": data.artist_name,
            "options_count": len(data.options),
            "options_sample": [{"name": o.name, "values": o.values[:5]} for o in (data.options or [])[:3]],
            "detail_images_count": len(data.detail_images),
            "detail_images_sample": (data.detail_images or [])[:10],
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.options("/api/translate")
async def translate_options():
    """CORS preflight 요청 처리"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
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
    
    # 지연 초기화
    await initialize_services()
    
    if not translator:
        return TranslateResponse(
            success=False,
            message="번역기가 초기화되지 않았습니다.",
            data=None
        )
    
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
        print(f"❌ 번역 오류: {e}")
        return TranslateResponse(
            success=False,
            message=f"번역 중 오류 발생: {str(e)}",
            data=None
        )


@app.options("/api/scrape-and-translate")
async def scrape_and_translate_options():
    """CORS preflight 요청 처리"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.post("/api/scrape-and-translate", response_model=TranslateResponse, tags=["Combined"])
async def scrape_and_translate(url: str, target_language: str = "en"):
    """
    URL 크롤링부터 번역까지 한 번에 수행
    
    - **url**: 아이디어스 상품 페이지 URL
    - **target_language**: 번역 대상 언어 (en/ja)
    """
    global scraper, translator
    
    # 지연 초기화
    await initialize_services()
    
    if not scraper:
        return TranslateResponse(
            success=False,
            message="스크래퍼가 초기화되지 않았습니다. 서버 로그를 확인해주세요.",
            data=None
        )
    
    if not translator:
        return TranslateResponse(
            success=False,
            message="번역기가 초기화되지 않았습니다.",
            data=None
        )
    
    # URL 유효성 검사
    if "idus.com" not in url:
        return TranslateResponse(
            success=False,
            message="유효한 아이디어스 URL이 아닙니다.",
            data=None
        )
    
    try:
        # 1. 크롤링
        print(f"📥 크롤링 시작: {url}")
        product_data = await scraper.scrape_product(url)
        print(f"✅ 크롤링 완료: {product_data.title}")
        
        # 2. 번역
        lang = TargetLanguage.ENGLISH if target_language == "en" else TargetLanguage.JAPANESE
        
        print(f"🌐 번역 시작: {lang.value}")
        translated_data = await translator.translate_product(
            product_data=product_data,
            target_language=lang
        )
        print("✅ 번역 완료")
        
        return TranslateResponse(
            success=True,
            message="크롤링 및 번역이 완료되었습니다.",
            data=translated_data
        )
        
    except Exception as e:
        print(f"❌ 처리 오류: {e}")
        import traceback
        traceback.print_exc()
        return TranslateResponse(
            success=False,
            message=f"처리 중 오류 발생: {str(e)}",
            data=None
        )


# ============ 배치 처리 API ============

@app.options("/api/batch-translate")
async def batch_translate_options():
    """CORS preflight 요청 처리"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.post("/api/batch-translate", response_model=BatchTranslateResponse, tags=["Batch"])
async def batch_translate(request: BatchTranslateRequest):
    """
    여러 URL을 한 번에 크롤링 및 번역
    
    - **urls**: 아이디어스 상품 URL 목록 (최대 10개)
    - **target_language**: 번역 대상 언어 (en/ja)
    
    각 URL을 순차적으로 처리하며, 개별 결과를 반환합니다.
    """
    global scraper, translator
    
    # 지연 초기화
    await initialize_services()
    
    if not scraper:
        return BatchTranslateResponse(
            success=False,
            message="스크래퍼가 초기화되지 않았습니다.",
            total_count=len(request.urls),
            success_count=0,
            failed_count=len(request.urls),
            results=[]
        )
    
    if not translator:
        return BatchTranslateResponse(
            success=False,
            message="번역기가 초기화되지 않았습니다.",
            total_count=len(request.urls),
            success_count=0,
            failed_count=len(request.urls),
            results=[]
        )
    
    # URL 개수 제한
    MAX_BATCH_SIZE = 10
    urls = request.urls[:MAX_BATCH_SIZE]
    
    results: list[BatchItemResult] = []
    success_count = 0
    failed_count = 0
    
    print(f"\n{'='*60}")
    print(f"📦 배치 처리 시작: {len(urls)}개 URL")
    print(f"🌐 대상 언어: {request.target_language.value}")
    print(f"{'='*60}\n")
    
    for idx, url in enumerate(urls):
        print(f"\n[{idx + 1}/{len(urls)}] 처리 중: {url[:50]}...")
        
        # URL 유효성 검사
        if "idus.com" not in url:
            print(f"   ❌ 유효하지 않은 URL")
            results.append(BatchItemResult(
                url=url,
                success=False,
                message="유효한 아이디어스 URL이 아닙니다.",
                data=None,
                original_data=None
            ))
            failed_count += 1
            continue
        
        try:
            # 1. 크롤링
            print(f"   📥 크롤링...")
            product_data = await scraper.scrape_product(url)
            print(f"   ✅ 크롤링 완료: {product_data.title[:30]}...")
            
            # 2. 번역
            print(f"   🌐 번역...")
            translated_data = await translator.translate_product(
                product_data=product_data,
                target_language=request.target_language
            )
            print(f"   ✅ 번역 완료")
            
            results.append(BatchItemResult(
                url=url,
                success=True,
                message="처리 완료",
                data=translated_data,
                original_data=product_data
            ))
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")
            results.append(BatchItemResult(
                url=url,
                success=False,
                message=f"처리 중 오류: {str(e)}",
                data=None,
                original_data=None
            ))
            failed_count += 1
    
    print(f"\n{'='*60}")
    print(f"📦 배치 처리 완료")
    print(f"   ✅ 성공: {success_count}개")
    print(f"   ❌ 실패: {failed_count}개")
    print(f"{'='*60}\n")
    
    return BatchTranslateResponse(
        success=success_count > 0,
        message=f"배치 처리 완료: {success_count}개 성공, {failed_count}개 실패",
        total_count=len(urls),
        success_count=success_count,
        failed_count=failed_count,
        results=results
    )


# 개발용 실행
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
