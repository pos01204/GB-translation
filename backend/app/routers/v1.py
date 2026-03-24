"""
v1 API 라우터 — 기존 크롤링/번역 API (하위 호환 유지)

기존 main.py의 엔드포인트를 라우터로 분리.
프론트엔드 v1 페이지가 그대로 동작합니다.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..models.v1 import (
    ScrapeRequest, ScrapeResponse,
    TranslateRequest, TranslateResponse,
    BatchTranslateRequest, BatchTranslateResponse, BatchItemResult,
    TargetLanguage,
)

router = APIRouter(tags=["V1 - Legacy"])

# 전역 인스턴스 참조 (main.py에서 주입)
_scraper = None
_translator = None
_initialize_fn = None


def configure(scraper, translator, initialize_fn):
    """main.py에서 전역 인스턴스를 주입받는다"""
    global _scraper, _translator, _initialize_fn
    _scraper = scraper
    _translator = translator
    _initialize_fn = initialize_fn


def update_refs(scraper, translator):
    """초기화 후 참조 업데이트"""
    global _scraper, _translator
    _scraper = scraper
    _translator = translator


# ──────────────── CORS Preflight ────────────────
def _cors_response():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.options("/api/scrape")
async def scrape_options():
    return _cors_response()


@router.options("/api/translate")
async def translate_options():
    return _cors_response()


@router.options("/api/scrape-and-translate")
async def scrape_and_translate_options():
    return _cors_response()


@router.options("/api/batch-translate")
async def batch_translate_options():
    return _cors_response()


# ──────────────── 크롤링 ────────────────

@router.post("/api/scrape", response_model=ScrapeResponse, summary="상품 크롤링")
async def scrape_product(request: ScrapeRequest):
    """아이디어스 상품 URL을 받아서 크롤링 수행"""
    if _initialize_fn:
        await _initialize_fn()

    if not _scraper:
        return ScrapeResponse(
            success=False,
            message="스크래퍼가 초기화되지 않았습니다.",
            data=None,
        )

    if "idus.com" not in request.url:
        return ScrapeResponse(
            success=False,
            message="유효한 아이디어스 URL이 아닙니다.",
            data=None,
        )

    try:
        product_data = await _scraper.scrape_product(request.url)
        return ScrapeResponse(
            success=True,
            message="크롤링이 완료되었습니다.",
            data=product_data,
        )
    except Exception as e:
        return ScrapeResponse(
            success=False,
            message=f"크롤링 중 오류 발생: {str(e)}",
            data=None,
        )


# ──────────────── 번역 ────────────────

@router.post("/api/translate", response_model=TranslateResponse, summary="상품 번역")
async def translate_product(request: TranslateRequest):
    """크롤링된 상품 데이터를 번역"""
    if _initialize_fn:
        await _initialize_fn()

    if not _translator:
        return TranslateResponse(
            success=False,
            message="번역기가 초기화되지 않았습니다.",
            data=None,
        )

    try:
        translated_data = await _translator.translate_product(
            product_data=request.product_data,
            target_language=request.target_language,
        )
        return TranslateResponse(
            success=True,
            message="번역이 완료되었습니다.",
            data=translated_data,
        )
    except Exception as e:
        return TranslateResponse(
            success=False,
            message=f"번역 중 오류 발생: {str(e)}",
            data=None,
        )


# ──────────────── 크롤링 + 번역 (Combined) ────────────────

@router.post(
    "/api/scrape-and-translate",
    response_model=TranslateResponse,
    summary="URL 크롤링 + 번역",
)
async def scrape_and_translate(url: str, target_language: str = "en"):
    """URL 크롤링부터 번역까지 한 번에 수행"""
    if _initialize_fn:
        await _initialize_fn()

    if not _scraper:
        return TranslateResponse(success=False, message="스크래퍼가 초기화되지 않았습니다.", data=None)
    if not _translator:
        return TranslateResponse(success=False, message="번역기가 초기화되지 않았습니다.", data=None)
    if "idus.com" not in url:
        return TranslateResponse(success=False, message="유효한 아이디어스 URL이 아닙니다.", data=None)

    try:
        product_data = await _scraper.scrape_product(url)
        lang = TargetLanguage.ENGLISH if target_language == "en" else TargetLanguage.JAPANESE
        translated_data = await _translator.translate_product(
            product_data=product_data,
            target_language=lang,
        )
        return TranslateResponse(
            success=True,
            message="크롤링 및 번역이 완료되었습니다.",
            data=translated_data,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return TranslateResponse(
            success=False,
            message=f"처리 중 오류 발생: {str(e)}",
            data=None,
        )


# ──────────────── 배치 처리 ────────────────

@router.post(
    "/api/batch-translate",
    response_model=BatchTranslateResponse,
    summary="배치 크롤링 + 번역",
)
async def batch_translate(request: BatchTranslateRequest):
    """여러 URL을 한 번에 크롤링 및 번역"""
    if _initialize_fn:
        await _initialize_fn()

    if not _scraper or not _translator:
        return BatchTranslateResponse(
            success=False,
            message="서비스가 초기화되지 않았습니다.",
            total_count=len(request.urls),
            success_count=0,
            failed_count=len(request.urls),
            results=[],
        )

    MAX_BATCH_SIZE = 10
    urls = request.urls[:MAX_BATCH_SIZE]
    results: list[BatchItemResult] = []
    success_count = 0
    failed_count = 0

    for idx, url in enumerate(urls):
        if "idus.com" not in url:
            results.append(BatchItemResult(
                url=url, success=False,
                message="유효한 아이디어스 URL이 아닙니다.",
                data=None, original_data=None,
            ))
            failed_count += 1
            continue

        try:
            product_data = await _scraper.scrape_product(url)
            translated_data = await _translator.translate_product(
                product_data=product_data,
                target_language=request.target_language,
            )
            results.append(BatchItemResult(
                url=url, success=True, message="처리 완료",
                data=translated_data, original_data=product_data,
            ))
            success_count += 1
        except Exception as e:
            results.append(BatchItemResult(
                url=url, success=False,
                message=f"처리 중 오류: {str(e)}",
                data=None, original_data=None,
            ))
            failed_count += 1

    return BatchTranslateResponse(
        success=success_count > 0,
        message=f"배치 처리 완료: {success_count}개 성공, {failed_count}개 실패",
        total_count=len(urls),
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )


# ──────────────── 디버그 ────────────────

@router.get("/api/debug/scrape", summary="디버그: 크롤링 결과 요약")
async def debug_scrape(url: str):
    """운영 진단용 디버그 엔드포인트"""
    if _initialize_fn:
        await _initialize_fn()

    if not _scraper:
        return {"success": False, "message": "스크래퍼가 초기화되지 않았습니다."}

    try:
        data = await _scraper.scrape_product(url)
        return {
            "success": True,
            "url": data.url,
            "title": data.title,
            "artist_name": data.artist_name,
            "options_count": len(data.options),
            "options_sample": [
                {"name": o.name, "values": o.values[:5]}
                for o in (data.options or [])[:3]
            ],
            "detail_images_count": len(data.detail_images),
            "detail_images_sample": (data.detail_images or [])[:10],
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
