"""
v2 GB 등록 라우터
글로벌 탭 자동 입력 + 일괄 처리 API
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..models.global_product import GlobalProductData, RegistrationResult
from ..services.product_writer import ProductWriter
from ..services.batch_processor import BatchProcessor, BatchProgress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/register", tags=["V2 - Registration"])

# 전역 참조 (main.py에서 주입)
_artist_session = None
_gb_translator = None
_initialize_services = None


def configure(artist_session, gb_translator, initialize_fn=None):
    """main.py에서 의존성 주입"""
    global _artist_session, _gb_translator, _initialize_services
    _artist_session = artist_session
    if gb_translator is not None:
        _gb_translator = gb_translator
    if initialize_fn is not None:
        _initialize_services = initialize_fn


async def _ensure_translator():
    """번역기가 초기화되지 않았으면 초기화 실행"""
    global _gb_translator
    if _gb_translator is not None:
        return True
    if _initialize_services:
        logger.info("번역기 미초기화 — v1 서비스 초기화 실행...")
        await _initialize_services()
        return _gb_translator is not None
    return False


# ──────────────── Request/Response Models ────────────────

class RegisterSingleRequest(BaseModel):
    """단일 작품 GB 등록 요청"""
    product_id: str
    target_languages: list[str] = ["en", "ja"]
    save_as_draft: bool = True
    global_data: Optional[GlobalProductData] = None  # 미리보기 데이터 재사용 시


class RegisterSingleResponse(BaseModel):
    """단일 작품 GB 등록 응답"""
    success: bool
    message: str
    result: Optional[RegistrationResult] = None


class RegisterBatchRequest(BaseModel):
    """일괄 GB 등록 요청"""
    product_ids: list[str]
    target_languages: list[str] = ["en", "ja"]
    save_as_draft: bool = True


class RegisterBatchResponse(BaseModel):
    """일괄 GB 등록 응답"""
    success: bool
    message: str
    progress: Optional[dict] = None


# ──────────────── Endpoints ────────────────

@router.post(
    "/single",
    response_model=RegisterSingleResponse,
    summary="단일 작품 GB 등록",
)
async def register_single(request: RegisterSingleRequest):
    """
    단일 작품을 글로벌 탭에 등록합니다.

    1. global_data가 제공되면 바로 입력
    2. 제공되지 않으면 국내 데이터 추출 → 번역 → 입력
    3. save_as_draft=True면 임시저장, False면 판매 등록
    """
    if not _artist_session:
        raise HTTPException(status_code=503, detail="세션이 초기화되지 않았습니다")
    if not await _artist_session.is_authenticated():
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    try:
        global_data = request.global_data

        # global_data가 없으면 번역 파이프라인 실행
        if not global_data:
            translator_ready = await _ensure_translator()
            if not translator_ready:
                raise HTTPException(
                    status_code=503, detail="번역기가 초기화되지 않았습니다"
                )

            from ..services.product_reader import ProductReader

            # 작품 페이지로 이동
            navigated = await _artist_session.navigate_to_product(
                request.product_id
            )
            if not navigated:
                return RegisterSingleResponse(
                    success=False,
                    message=f"작품 페이지 이동 실패: {request.product_id}",
                )

            # 국내 데이터 추출
            reader = ProductReader(page=_artist_session.page)
            domestic_data = await reader.read_domestic_data(request.product_id)

            if domestic_data.category_restricted:
                return RegisterSingleResponse(
                    success=False,
                    message=f"글로벌 판매 제한 카테고리: {domestic_data.category_path}",
                )

            # 번역
            global_data = await _gb_translator.translate_for_gb(
                domestic=domestic_data,
                target_languages=request.target_languages,
            )

        # 글로벌 탭 자동 입력
        writer = ProductWriter(page=_artist_session.page)
        result = await writer.register_global_product(
            global_data=global_data,
            product_id=request.product_id,
            save_as_draft=request.save_as_draft,
        )

        success = len(result["languages_success"]) > 0
        registration_result = RegistrationResult(
            product_id=request.product_id,
            success=success,
            languages_registered=result["languages_success"],
            languages_failed=result["languages_failed"],
            saved_as_draft=request.save_as_draft,
        )

        return RegisterSingleResponse(
            success=success,
            message=(
                f"등록 완료: {result['languages_success']}"
                if success
                else f"등록 실패: {result['languages_failed']}"
            ),
            result=registration_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"단일 등록 실패: {e}")
        return RegisterSingleResponse(
            success=False,
            message=f"등록 중 오류 발생: {str(e)}",
        )


@router.post(
    "/batch",
    response_model=RegisterBatchResponse,
    summary="일괄 작품 GB 등록",
)
async def register_batch(request: RegisterBatchRequest):
    """
    여러 작품을 순차적으로 번역 + GB 등록합니다.

    - 최대 처리 개수: config.batch_max_size (기본 10)
    - 작품 간 대기: config.batch_item_delay (기본 3초)
    - 결과에 각 작품의 성공/실패 상태가 포함됩니다.
    """
    if not _artist_session:
        raise HTTPException(status_code=503, detail="세션이 초기화되지 않았습니다")
    translator_ready = await _ensure_translator()
    if not translator_ready:
        raise HTTPException(status_code=503, detail="번역기가 초기화되지 않았습니다")
    if not await _artist_session.is_authenticated():
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    if not request.product_ids:
        return RegisterBatchResponse(
            success=False,
            message="처리할 작품이 없습니다",
        )

    try:
        processor = BatchProcessor(
            artist_session=_artist_session,
            gb_translator=_gb_translator,
        )
        progress = await processor.process_batch(
            product_ids=request.product_ids,
            target_languages=request.target_languages,
            save_as_draft=request.save_as_draft,
        )

        return RegisterBatchResponse(
            success=progress.completed > 0,
            message=(
                f"일괄 처리 완료: {progress.completed}개 성공, "
                f"{progress.failed}개 실패 (총 {progress.total}개)"
            ),
            progress=progress.to_dict(),
        )

    except Exception as e:
        logger.error(f"일괄 등록 실패: {e}")
        return RegisterBatchResponse(
            success=False,
            message=f"일괄 처리 중 오류 발생: {str(e)}",
        )


@router.get(
    "/batch/status",
    summary="일괄 처리 상태 조회 (향후 WebSocket 전환 예정)",
)
async def batch_status():
    """
    현재 진행 중인 일괄 처리의 상태를 반환합니다.
    향후 WebSocket으로 실시간 상태 스트리밍 예정.
    """
    return {
        "message": "현재는 /batch 엔드포인트의 응답으로 최종 결과를 반환합니다. "
                   "향후 WebSocket 기반 실시간 진행률 제공 예정.",
    }
