"""
일괄 처리 서비스

여러 작품을 순차적으로 번역 + GB 등록합니다.
진행 상황을 콜백으로 보고합니다.
"""
import asyncio
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass, field

from ..models.domestic import ProductSummary, DomesticProduct
from ..models.global_product import GlobalProductData, RegistrationResult
from ..services.product_reader import ProductReader
from ..services.product_writer import ProductWriter
from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class BatchItem:
    """일괄 처리 개별 항목"""
    product_id: str
    status: str = "pending"         # pending, translating, registering, completed, failed
    domestic_data: Optional[DomesticProduct] = None
    global_data: Optional[GlobalProductData] = None
    result: Optional[RegistrationResult] = None
    error_message: Optional[str] = None


@dataclass
class BatchProgress:
    """일괄 처리 진행 상황"""
    total: int = 0
    completed: int = 0
    failed: int = 0
    current_item: Optional[str] = None
    current_status: str = ""
    items: list[BatchItem] = field(default_factory=list)

    @property
    def is_done(self) -> bool:
        return self.completed + self.failed >= self.total

    @property
    def success_rate(self) -> float:
        return self.completed / self.total if self.total > 0 else 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "current_item": self.current_item,
            "current_status": self.current_status,
            "is_done": self.is_done,
            "items": [
                {
                    "product_id": item.product_id,
                    "status": item.status,
                    "error_message": item.error_message,
                }
                for item in self.items
            ],
        }


class BatchProcessor:
    """일괄 처리 프로세서

    Usage:
        processor = BatchProcessor(
            artist_session=session,
            gb_translator=translator,
        )
        progress = await processor.process_batch(
            product_ids=["uuid1", "uuid2"],
            target_languages=["en", "ja"],
            save_as_draft=True,
        )
    """

    def __init__(self, artist_session, gb_translator):
        self.session = artist_session
        self.translator = gb_translator
        self._progress: Optional[BatchProgress] = None
        self._is_running = False

    @property
    def progress(self) -> Optional[BatchProgress]:
        return self._progress

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def process_batch(
        self,
        product_ids: list[str],
        target_languages: list[str] = None,
        save_as_draft: bool = True,
        on_progress: Optional[Callable] = None,
    ) -> BatchProgress:
        """
        여러 작품을 순차적으로 번역 + GB 등록

        Args:
            product_ids: 작품 UUID 목록
            target_languages: 번역 대상 언어 ["en", "ja"]
            save_as_draft: True면 임시저장, False면 바로 판매 등록
            on_progress: 진행 상황 콜백 (BatchProgress)

        Returns:
            최종 BatchProgress
        """
        if target_languages is None:
            target_languages = ["en", "ja"]

        # 최대 처리 개수 제한
        product_ids = product_ids[:settings.batch_max_size]

        self._progress = BatchProgress(
            total=len(product_ids),
            items=[BatchItem(product_id=pid) for pid in product_ids],
        )
        self._is_running = True

        logger.info(f"일괄 처리 시작: {len(product_ids)}개 작품")

        try:
            for idx, item in enumerate(self._progress.items):
                self._progress.current_item = item.product_id
                self._progress.current_status = "처리 중"

                try:
                    await self._process_single(
                        item=item,
                        target_languages=target_languages,
                        save_as_draft=save_as_draft,
                    )
                    self._progress.completed += 1
                except Exception as e:
                    item.status = "failed"
                    item.error_message = str(e)
                    self._progress.failed += 1
                    logger.error(f"작품 처리 실패 [{item.product_id}]: {e}")

                # 콜백 호출
                if on_progress:
                    on_progress(self._progress)

                # 작품 간 대기 (마지막 아이템은 대기 불필요)
                if idx < len(self._progress.items) - 1:
                    await asyncio.sleep(settings.batch_item_delay)

        finally:
            self._is_running = False
            self._progress.current_item = None
            self._progress.current_status = "완료"

        logger.info(
            f"일괄 처리 완료: {self._progress.completed}개 성공, "
            f"{self._progress.failed}개 실패"
        )
        return self._progress

    async def _process_single(
        self,
        item: BatchItem,
        target_languages: list[str],
        save_as_draft: bool,
    ):
        """개별 작품 처리 (번역 + 등록)"""

        # 1. 작품 페이지로 이동
        item.status = "navigating"
        navigated = await self.session.navigate_to_product(item.product_id)
        if not navigated:
            raise Exception(f"작품 페이지 이동 실패: {item.product_id}")

        # 2. 국내 데이터 추출
        item.status = "reading"
        reader = ProductReader(page=self.session.page)
        domestic_data = await reader.read_domestic_data(item.product_id)
        item.domestic_data = domestic_data

        # 3. 글로벌 판매 제한 확인
        if domestic_data.category_restricted:
            raise Exception(f"글로벌 판매 제한 카테고리: {domestic_data.category_path}")

        # 4. 번역
        item.status = "translating"
        global_data = await self.translator.translate_for_gb(
            domestic=domestic_data,
            target_languages=target_languages,
        )
        item.global_data = global_data

        # 5. 글로벌 탭 입력
        item.status = "registering"
        writer = ProductWriter(page=self.session.page)
        result = await writer.register_global_product(
            global_data=global_data,
            save_as_draft=save_as_draft,
        )

        # 6. 결과 기록
        success = len(result["languages_success"]) > 0
        item.result = RegistrationResult(
            product_id=item.product_id,
            success=success,
            languages_registered=result["languages_success"],
            languages_failed=result["languages_failed"],
            saved_as_draft=save_as_draft,
        )
        item.status = "completed" if success else "failed"

        if not success:
            raise Exception(
                f"등록 실패 — 실패 언어: {result['languages_failed']}"
            )
