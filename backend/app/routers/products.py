"""
v2 작품 관리 라우터
작가웹 작품 목록 조회 및 국내 데이터 읽기
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from ..models.domestic import ProductSummary, DomesticProduct
from ..services.product_reader import ProductReader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/products", tags=["V2 - Products"])

# 전역 세션 참조 (main.py에서 주입)
_artist_session = None


def configure(artist_session):
    """main.py에서 작가웹 세션 인스턴스를 주입받는다"""
    global _artist_session
    _artist_session = artist_session


# ──────────────── Response Models ────────────────

class ProductListResponse(BaseModel):
    success: bool
    message: str
    products: list[ProductSummary] = []
    total_count: int = 0
    debug_info: Optional[dict] = None


class DomesticProductResponse(BaseModel):
    success: bool
    message: str
    data: Optional[DomesticProduct] = None


# ──────────────── Endpoints ────────────────

@router.get("/", response_model=ProductListResponse, summary="작품 목록 조회")
async def get_product_list(
    status: str = Query("selling", description="작품 상태: selling, paused, draft"),
):
    """
    작가웹에서 작품 목록을 조회합니다.

    - **status**: 작품 상태 필터 (selling/paused/draft)
    """
    if not _artist_session:
        raise HTTPException(status_code=503, detail="세션이 초기화되지 않았습니다")

    if not await _artist_session.is_authenticated():
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    try:
        products = await _artist_session.get_product_list(status=status)
        debug_info = _artist_session._last_api_raw_sample
        return ProductListResponse(
            success=True,
            message=f"{len(products)}개 작품을 조회했습니다",
            products=products,
            total_count=len(products),
            debug_info=debug_info,
        )
    except Exception as e:
        logger.error(f"작품 목록 조회 실패: {e}")
        return ProductListResponse(
            success=False,
            message=f"작품 목록 조회 중 오류: {str(e)}",
        )


@router.get(
    "/{product_id}/domestic",
    response_model=DomesticProductResponse,
    summary="국내 작품 데이터 조회",
)
async def get_domestic_product(product_id: str):
    """
    특정 작품의 국내 탭 데이터를 추출합니다.

    - **product_id**: 작품 UUID
    """
    if not _artist_session:
        raise HTTPException(status_code=503, detail="세션이 초기화되지 않았습니다")

    if not await _artist_session.is_authenticated():
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    try:
        # 작품 페이지로 이동
        navigated = await _artist_session.navigate_to_product(product_id)
        if not navigated:
            return DomesticProductResponse(
                success=False,
                message=f"작품 페이지 이동 실패: {product_id}",
            )

        # 국내 데이터 읽기
        reader = ProductReader(page=_artist_session.page)
        domestic_data = await reader.read_domestic_data(product_id)

        return DomesticProductResponse(
            success=True,
            message="국내 데이터 추출 완료",
            data=domestic_data,
        )
    except Exception as e:
        logger.error(f"국내 데이터 추출 실패: {e}")
        return DomesticProductResponse(
            success=False,
            message=f"국내 데이터 추출 중 오류: {str(e)}",
        )
