"""
v2 번역 라우터
국내 작품 데이터를 GB 등록용으로 번역 (미리보기 + 실행)
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from ..models.domestic import DomesticProduct
from ..models.global_product import GlobalProductData
from ..services.product_reader import ProductReader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/translate", tags=["V2 - Translation"])

# 전역 참조 (main.py에서 주입)
_artist_session = None
_gb_translator = None


def configure(artist_session, gb_translator):
    """main.py에서 의존성 주입"""
    global _artist_session, _gb_translator
    _artist_session = artist_session
    _gb_translator = gb_translator


# ──────────────── Request/Response Models ────────────────

class TranslatePreviewRequest(BaseModel):
    """번역 미리보기 요청"""
    product_id: str
    target_languages: list[str] = ["en", "ja"]


class TranslatePreviewResponse(BaseModel):
    """번역 미리보기 응답"""
    success: bool
    message: str
    domestic_data: Optional[DomesticProduct] = None
    global_data: Optional[GlobalProductData] = None


class TranslateDirectRequest(BaseModel):
    """직접 데이터 번역 요청 (국내 데이터를 클라이언트에서 전달)"""
    domestic_data: DomesticProduct
    target_languages: list[str] = ["en", "ja"]


# ──────────────── Endpoints ────────────────

@router.post(
    "/preview",
    response_model=TranslatePreviewResponse,
    summary="GB 번역 미리보기",
)
async def translate_preview(request: TranslatePreviewRequest):
    """
    작품의 국내 데이터를 추출하고 GB 등록용으로 번역합니다.
    실제 등록은 하지 않고 번역 결과만 반환합니다.

    1. 작가웹에서 국내 데이터 추출
    2. Gemini를 통해 GB 번역 수행
    3. 번역 결과 반환 (확인/수정 가능)
    """
    if not _artist_session:
        raise HTTPException(status_code=503, detail="세션이 초기화되지 않았습니다")
    if not _gb_translator:
        raise HTTPException(status_code=503, detail="번역기가 초기화되지 않았습니다")
    if not await _artist_session.is_authenticated():
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    try:
        # 1. 작품 페이지로 이동
        navigated = await _artist_session.navigate_to_product(request.product_id)
        if not navigated:
            return TranslatePreviewResponse(
                success=False,
                message=f"작품 페이지 이동 실패: {request.product_id}",
            )

        # 2. 국내 데이터 추출
        reader = ProductReader(page=_artist_session.page)
        domestic_data = await reader.read_domestic_data(request.product_id)

        # 3. 글로벌 판매 제한 카테고리 확인
        if domestic_data.category_restricted:
            return TranslatePreviewResponse(
                success=False,
                message=(
                    f"글로벌 판매 제한 카테고리입니다: {domestic_data.category_path}. "
                    f"식품, 가구, 식물, 디퓨저류, 14k/18k/24k 액세서리는 글로벌 판매 불가합니다."
                ),
                domestic_data=domestic_data,
            )

        # 4. GB 번역 수행
        global_data = await _gb_translator.translate_for_gb(
            domestic=domestic_data,
            target_languages=request.target_languages,
        )

        return TranslatePreviewResponse(
            success=True,
            message="번역 미리보기가 준비되었습니다",
            domestic_data=domestic_data,
            global_data=global_data,
        )

    except Exception as e:
        logger.error(f"번역 미리보기 실패: {e}")
        return TranslatePreviewResponse(
            success=False,
            message=f"번역 중 오류 발생: {str(e)}",
        )


@router.post(
    "/direct",
    response_model=TranslatePreviewResponse,
    summary="직접 데이터 GB 번역",
)
async def translate_direct(request: TranslateDirectRequest):
    """
    클라이언트에서 전달한 국내 데이터를 GB 번역합니다.
    작가웹 세션 없이도 사용 가능합니다 (번역기만 필요).

    프론트엔드에서 이미 추출한 국내 데이터를 수정 후
    재번역할 때 유용합니다.
    """
    if not _gb_translator:
        raise HTTPException(status_code=503, detail="번역기가 초기화되지 않았습니다")

    if not _gb_translator.is_initialized:
        raise HTTPException(status_code=503, detail="Gemini API가 초기화되지 않았습니다")

    try:
        # 글로벌 판매 제한 카테고리 확인
        if request.domestic_data.category_restricted:
            return TranslatePreviewResponse(
                success=False,
                message=f"글로벌 판매 제한 카테고리: {request.domestic_data.category_path}",
                domestic_data=request.domestic_data,
            )

        # GB 번역 수행
        global_data = await _gb_translator.translate_for_gb(
            domestic=request.domestic_data,
            target_languages=request.target_languages,
        )

        return TranslatePreviewResponse(
            success=True,
            message="번역이 완료되었습니다",
            domestic_data=request.domestic_data,
            global_data=global_data,
        )

    except Exception as e:
        logger.error(f"직접 번역 실패: {e}")
        return TranslatePreviewResponse(
            success=False,
            message=f"번역 중 오류 발생: {str(e)}",
        )
