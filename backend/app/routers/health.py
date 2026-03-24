"""
헬스체크 라우터
서버 상태 확인 및 기본 정보 제공
"""
from fastapi import APIRouter
from ..models.v1 import HealthResponse

router = APIRouter(tags=["Health"])


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
