"""
FastAPI 메인 엔트리포인트
아이디어스 상품 크롤링/번역 + GB 등록 자동화 API

v1: 기존 소비자 페이지 크롤링 + 번역
v2: 작가웹 연동 기반 GB 등록 자동화
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .config import settings
from .services.artist_web import ArtistWebSession

# 라우터 임포트
from .routers import health, v1, session, products, translation, registration

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ──────────────── 전역 인스턴스 ────────────────

scraper: Any = None
translator: Any = None
gb_translator: Any = None
artist_session: Optional[ArtistWebSession] = None
is_initialized: bool = False


async def initialize_v1_services():
    """v1 서비스 초기화 (지연 초기화) + v2 GB 번역기 초기화"""
    global scraper, translator, gb_translator, is_initialized

    if is_initialized:
        return

    logger.info("=" * 60)
    logger.info("v1 서비스 초기화 시작")
    logger.info("=" * 60)

    # 지연 import (Railway 배포 환경 전용 의존성)
    from .scraper import IdusScraper as _IdusScraper
    from .translator import ProductTranslator as _ProductTranslator

    # Gemini API 키 확인
    gemini_api_key = os.getenv("GEMINI_API_KEY") or settings.gemini_api_key
    if not gemini_api_key:
        logger.warning("GEMINI_API_KEY 환경변수가 설정되지 않았습니다!")
    else:
        masked_key = gemini_api_key[:8] + "..." + gemini_api_key[-4:] if len(gemini_api_key) > 12 else "***"
        logger.info(f"Gemini API 키 확인됨: {masked_key}")

    # Translator 초기화
    logger.info("Translator 초기화...")
    translator = _ProductTranslator(api_key=gemini_api_key)
    if translator._initialized:
        logger.info(f"Translator 초기화 성공 (모델: {translator._model_name})")
    else:
        logger.warning("Translator 초기화 실패 — 번역 기능이 작동하지 않습니다")

    # Scraper 초기화
    logger.info("Scraper 초기화...")
    try:
        scraper = _IdusScraper()
        await scraper.initialize()
        logger.info("Playwright 브라우저 초기화 완료")
    except Exception as e:
        logger.error(f"Playwright 초기화 실패: {e}")
        scraper = None

    # GB 번역기 초기화 (v1 translator 래핑)
    if translator and translator._initialized:
        from .translator.gb_translator import GBProductTranslator
        gb_translator = GBProductTranslator(base_translator=translator)
        logger.info("GB 번역기 초기화 완료")

        # translation 라우터에 참조 업데이트
        translation.configure(artist_session, gb_translator)

    # v1 라우터에 참조 주입
    v1.update_refs(scraper, translator)

    is_initialized = True
    logger.info("=" * 60)
    logger.info("v1 서비스 초기화 완료")
    logger.info("=" * 60)


# ──────────────── Lifespan ────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 라이프사이클 관리"""
    global artist_session

    logger.info("서버 시작...")
    logger.info(f"PORT: {os.getenv('PORT', '8000')}")

    # v2 작가웹 세션 인스턴스 생성 (초기화는 로그인 시 수행)
    artist_session = ArtistWebSession()

    # 라우터에 의존성 주입
    v1.configure(scraper, translator, initialize_v1_services)
    health.configure(artist_session)
    session.configure(artist_session)
    products.configure(artist_session)
    translation.configure(artist_session, gb_translator)
    registration.configure(artist_session, gb_translator)

    yield

    # 종료 시 정리
    logger.info("서버 종료 — 리소스 정리 중...")
    try:
        if scraper:
            await scraper.close()
        if artist_session:
            await artist_session.close()
    except Exception as e:
        logger.warning(f"리소스 정리 중 오류: {e}")
    logger.info("리소스 정리 완료")


# ──────────────── FastAPI 앱 생성 ────────────────

app = FastAPI(
    title="Idus Product Translator & GB Registration API",
    description=(
        "아이디어스 상품 크롤링/번역 + GB 작품 연계 등록 자동화 API\n\n"
        "- **v1**: 소비자 페이지 URL 기반 크롤링 + 번역\n"
        "- **v2**: 작가웹 연동 기반 GB 등록 자동화"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ──────────────── 라우터 등록 ────────────────

app.include_router(health.router)          # /, /api/health
app.include_router(v1.router)              # /api/scrape, /api/translate, etc.
app.include_router(session.router)         # /api/v2/session/*
app.include_router(products.router)        # /api/v2/products/*
app.include_router(translation.router)     # /api/v2/translate/*
app.include_router(registration.router)    # /api/v2/register/*


# ──────────────── 개발용 실행 ────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
