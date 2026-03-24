"""
헬스체크 라우터
서버 상태 확인 및 기본 정보 제공
"""
import logging
from fastapi import APIRouter
from ..models.v1 import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

# 전역 세션 참조 (main.py에서 주입)
_artist_session = None


def configure(artist_session):
    global _artist_session
    _artist_session = artist_session


@router.get("/", summary="API 정보")
async def root():
    """루트 엔드포인트 — API 정보"""
    return {
        "name": "Idus Product Translator API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
    }


@router.get("/api/health", response_model=HealthResponse, summary="서버 상태 확인")
async def health_check():
    """
    서버 상태 확인 엔드포인트
    Railway 헬스체크용 — 항상 즉시 응답
    """
    return HealthResponse(
        status="healthy",
        version="2.0.0",
    )


@router.get("/api/debug/page", summary="현재 브라우저 페이지 디버깅 정보")
async def debug_page_info():
    """
    작가웹 브라우저 세션의 현재 페이지 DOM 구조를 반환합니다.
    디버깅 전용 — 작품 목록 스크래핑 문제 분석에 사용합니다.
    """
    if not _artist_session:
        return {"error": "세션 미초기화"}

    try:
        info = await _artist_session.get_page_debug_info()
        return {"success": True, "data": info}
    except Exception as e:
        logger.error(f"디버그 정보 수집 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/debug/api-response", summary="idus API 원본 응답 확인")
async def debug_api_response():
    """
    artist-aggregator.idus.com API를 직접 호출하고 원본 응답을 반환합니다.
    작품 데이터 필드명 파악용.
    """
    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화 또는 페이지 없음"}

    try:
        api_url = "https://artist-aggregator.idus.com/api/v1/product/public/sale/paging?page=0&sort=&query=&management_category_id=0"
        raw = await _artist_session.page.evaluate("""
            async (url) => {
                try {
                    const resp = await fetch(url, {
                        method: 'GET',
                        credentials: 'include',
                        headers: { 'Accept': 'application/json' },
                    });
                    if (!resp.ok) return { error: `HTTP ${resp.status}` };
                    const data = await resp.json();
                    // 첫 2개 아이템만 반환 (전체 응답이 너무 클 수 있음)
                    return { ok: true, raw_keys: Object.keys(data), data: data };
                } catch (e) {
                    return { error: e.message };
                }
            }
        """, api_url)
        return {"success": True, "api_response": raw}
    except Exception as e:
        logger.error(f"API 디버그 실패: {e}")
        return {"success": False, "error": str(e)}
