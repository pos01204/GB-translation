"""
작가웹 글로벌 탭 자동 입력 서비스 — Vuex 직접 주입 방식

DOM 모달 상호작용 대신 Vuex 스토어에 데이터를 직접 주입합니다.
globalProduct._detailUI 구조:
{
  languageType: "ja" | "en",
  productName: string,
  images: string[],           ← 이미지 URL 배열
  keywords: string[],         ← 키워드 배열
  premiumDescription: dict[], ← 설명 블록 배열
  ...
}

유일한 DOM 상호작용: 언어 탭 선택 + 저장/판매 버튼 클릭
"""
import asyncio
import logging
import re
from typing import Optional
from playwright.async_api import Page
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..config import settings

logger = logging.getLogger(__name__)


class ProductWriter:
    """작가웹 글로벌 탭 — Vuex 직접 주입 방식"""

    def __init__(self, page: Page):
        self.page = page

    # ──────────── 유틸 ────────────

    async def _safe_click(self, locator, timeout: float = 5, label: str = "") -> bool:
        try:
            count = await asyncio.wait_for(locator.count(), timeout=timeout)
            if count > 0:
                await locator.click()
                return True
        except (asyncio.TimeoutError, Exception):
            pass
        if label:
            logger.warning(f"'{label}' 요소 없음")
        return False

    # ──────────── 글로벌 페이지 이동 ────────────

    async def navigate_to_global_tab(self, product_id: str = "") -> bool:
        """글로벌 페이지 이동"""
        try:
            if product_id:
                url = f"https://artist.idus.com/product/{product_id}/global"
                logger.info(f"글로벌 페이지 이동: {url}")
                try:
                    await self.page.goto(url, timeout=30000)
                    await self.page.wait_for_load_state("domcontentloaded")
                except Exception as e:
                    logger.warning(f"goto 오류 (계속): {e}")

                # 충분한 렌더링 대기 + 폼 요소 확인
                await asyncio.sleep(5)
                try:
                    await self.page.wait_for_selector(
                        'textarea[name="globalProductName"]', timeout=10000
                    )
                except Exception:
                    logger.warning("globalProductName 대기 timeout")
            else:
                tab = self.page.locator('.v-tab:has-text("글로벌")').first
                if await self._safe_click(tab, label="글로벌 탭"):
                    await asyncio.sleep(3)
                else:
                    return False

            logger.info("글로벌 탭 이동 완료")
            return True
        except Exception as e:
            logger.error(f"글로벌 탭 이동 실패: {e}")
            return False

    # ──────────── 언어 탭 선택 ────────────

    async def select_language_tab(self, language: str) -> bool:
        """언어 서브탭 선택 + Vuex languageType 확인"""
        lang_text = "영어" if language == "en" else "일본어"
        tab = self.page.locator(
            f'.GlobalProductLanguageTab__item:has-text("{lang_text}")'
        ).first
        if await self._safe_click(tab, label=f"'{lang_text}' 탭"):
            await asyncio.sleep(3)  # 탭 전환 + Vuex 상태 업데이트 대기
            logger.info(f"'{lang_text}' 탭 선택 완료")
            return True
        return False

    # ──────────── Vuex 일괄 주입 ────────────

    async def inject_all_data_via_vuex(
        self,
        language: str,
        title: str,
        images: list[str],
        keywords: list[str],
        description_blocks: list[dict],
    ) -> bool:
        """모든 폼 데이터를 Vuex _detailUI에 일괄 주입

        DOM 모달 상호작용 완전 제거 — Vuex 직접 조작만 사용
        """
        try:
            result = await self.page.evaluate("""
                (data) => {
                    const app = document.querySelector('#app');
                    if (!app || !app.__vue__ || !app.__vue__.$store) {
                        return { success: false, error: 'Vuex store not found' };
                    }
                    const store = app.__vue__.$store;
                    const ui = store.state.globalProduct?._detailUI;
                    if (!ui) {
                        return { success: false, error: '_detailUI not found' };
                    }

                    // 모든 데이터 일괄 주입
                    ui.productName = data.title || '';
                    ui.images = data.images || [];
                    ui.keywords = data.keywords || [];
                    ui.premiumDescription = data.blocks || [];

                    // textarea에도 값 반영 (Vue reactivity)
                    const textarea = document.querySelector('textarea[name="globalProductName"]');
                    if (textarea) {
                        textarea.value = data.title || '';
                        textarea.dispatchEvent(new Event('input', { bubbles: true }));
                    }

                    return {
                        success: true,
                        injected: {
                            title: (data.title || '').substring(0, 30),
                            imageCount: (data.images || []).length,
                            keywordCount: (data.keywords || []).length,
                            blockCount: (data.blocks || []).length,
                        }
                    };
                }
            """, {
                "title": title[:settings.title_max_length_global],
                "images": images,
                "keywords": keywords,
                "blocks": description_blocks,
            })

            if result.get("success"):
                info = result.get("injected", {})
                logger.info(
                    f"Vuex 일괄 주입 완료: "
                    f"제목={info.get('title', '')}..., "
                    f"이미지={info.get('imageCount', 0)}장, "
                    f"키워드={info.get('keywordCount', 0)}개, "
                    f"블록={info.get('blockCount', 0)}개"
                )
                return True
            else:
                logger.error(f"Vuex 주입 실패: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Vuex 주입 실패: {e}")
            return False

    # ──────────── 옵션 (모달 — 유일한 DOM 상호작용) ────────────

    async def fill_global_options(
        self, options: list[GlobalOption], language: str,
    ) -> bool:
        """글로벌 옵션 — "옵션 편집" 모달"""
        try:
            edit_btn = self.page.locator('button:has-text("옵션 편집")').first
            if not await self._safe_click(edit_btn, timeout=5, label="옵션 편집"):
                return False
            await asyncio.sleep(2)

            modal = self.page.locator('.v-dialog--active')
            if await modal.count() == 0:
                logger.warning("옵션 편집 모달 미열림")
                return False

            for option in options:
                name = option.name_en if language == "en" else option.name_ja
                values = option.values_en if language == "en" else option.values_ja
                if not name or not values:
                    continue

                # "추가" 버튼 클릭
                add_btn = modal.locator('button:has-text("추가")').first
                if await self._safe_click(add_btn, timeout=3):
                    await asyncio.sleep(1)

                # 옵션명 입력
                name_input = modal.locator('input[placeholder*="입력해 주세요"]').first
                if await name_input.count() > 0:
                    await name_input.fill(name)
                    logger.info(f"옵션명: {name}")

                # 옵션값 입력
                for i, val in enumerate(values):
                    # "추가+" 클릭 (첫 값은 이미 존재)
                    if i > 0:
                        add_val = modal.locator('text="추가"').last
                        await self._safe_click(add_val, timeout=2)
                        await asyncio.sleep(0.5)

                    # 마지막 값 input에 입력
                    val_inputs = modal.locator('input[placeholder*="입력해 주세요"]')
                    count = await val_inputs.count()
                    if count > 1:
                        await val_inputs.nth(count - 1).fill(val)

            # "적용" 클릭
            apply_btn = modal.locator('text="적용"').first
            if await self._safe_click(apply_btn, timeout=5):
                await asyncio.sleep(1)
                logger.info(f"옵션 {len(options)}개 적용 ({language})")
            else:
                await self.page.keyboard.press("Escape")

            return True

        except Exception as e:
            logger.error(f"옵션 입력 실패: {e}")
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
            return False

    # ──────────── 저장/등록 ────────────

    async def save_draft(self, language: str = "ja") -> bool:
        """임시저장"""
        lang_text = "영어" if language == "en" else "일본어"
        btn = self.page.locator(f'button:has-text("{lang_text} 임시저장")').first
        if not await self._safe_click(btn, timeout=5):
            btn = self.page.locator('button:has-text("임시저장")').first
            if not await self._safe_click(btn, timeout=3, label="임시저장"):
                return False
        await asyncio.sleep(3)
        return await self._check_save_result(lang_text, "임시저장")

    async def publish(self, language: str = "ja") -> bool:
        """판매 등록"""
        lang_text = "영어" if language == "en" else "일본어"
        btn = self.page.locator(f'button:has-text("{lang_text} 작품 판매하기")').first
        if not await self._safe_click(btn, timeout=5):
            btn = self.page.locator('button:has-text("작품 판매하기")').first
            if not await self._safe_click(btn, timeout=3, label="판매 등록"):
                return False
        await asyncio.sleep(3)
        return await self._check_save_result(lang_text, "판매 등록")

    async def _check_save_result(self, lang_text: str, action: str) -> bool:
        """저장 후 에러/성공 확인"""
        success = True
        try:
            # 에러 다이얼로그
            dlg = self.page.locator('.v-dialog--active').first
            try:
                if await asyncio.wait_for(dlg.count(), timeout=2) > 0:
                    text = await dlg.inner_text()
                    logger.error(f"[{action}] 다이얼로그: {text[:200]}")
                    success = False
                    ok = dlg.locator('button:has-text("확인")').first
                    await self._safe_click(ok)
            except asyncio.TimeoutError:
                pass

            # 에러 스낵바
            snack = self.page.locator('.v-snack__content').first
            try:
                if await asyncio.wait_for(snack.count(), timeout=1) > 0:
                    msg = await snack.inner_text()
                    if any(w in msg for w in ["확인", "입력", "오류", "실패"]):
                        logger.error(f"[{action}] 에러: {msg[:100]}")
                        success = False
                    else:
                        logger.info(f"[{action}] 성공: {msg[:100]}")
            except asyncio.TimeoutError:
                pass

            if success:
                logger.info(f"{lang_text} {action} 성공")
            else:
                logger.error(f"{lang_text} {action} 실패")
        except Exception as e:
            logger.warning(f"결과 확인 실패: {e}")
        return success

    # ──────────── 통합 ────────────

    async def fill_language_data(
        self, language: str, data: LanguageData,
        domestic_images: list[str] = None,
        global_options: Optional[list[GlobalOption]] = None,
    ) -> bool:
        """특정 언어 — Vuex 일괄 주입 + 옵션 모달"""
        lang_label = "영어" if language == "en" else "일본어"
        logger.info(f"{lang_label} 데이터 입력 시작")

        # 1. 언어 탭 선택
        if not await self.select_language_tab(language):
            return False

        # 2. Vuex 일괄 주입 (이미지 + 작품명 + 설명 + 키워드)
        images = domestic_images or []
        blocks = data.description_blocks if hasattr(data, 'description_blocks') and data.description_blocks else []
        keywords = [kw.strip().lstrip('#') for kw in (data.keywords or []) if kw.strip()]

        ok = await self.inject_all_data_via_vuex(
            language=language,
            title=data.title,
            images=images,
            keywords=keywords,
            description_blocks=blocks,
        )
        if not ok:
            logger.error(f"{lang_label} Vuex 주입 실패")
            return False

        # 3. 옵션 (유일한 DOM 상호작용)
        if global_options:
            await self.fill_global_options(global_options, language)

        logger.info(f"{lang_label} 데이터 입력 완료")
        return True

    async def register_global_product(
        self, global_data: GlobalProductData,
        product_id: str = "", save_as_draft: bool = True,
        target_languages: Optional[list[str]] = None,
        domestic_images: list[str] = None,
    ) -> dict:
        """글로벌 탭 전체 등록

        Args:
            domestic_images: 국내 작품 이미지 URL 목록 (글로벌에 복사)
        """
        if target_languages is None:
            target_languages = []
            if global_data.ja:
                target_languages.append("ja")
            if global_data.en:
                target_languages.append("en")

        result = {"languages_success": [], "languages_failed": []}

        if not await self.navigate_to_global_tab(product_id):
            result["languages_failed"] = target_languages
            return result

        for lang in target_languages:
            lang_data = global_data.ja if lang == "ja" else global_data.en
            if not lang_data:
                result["languages_failed"].append(lang)
                continue

            ok = await self.fill_language_data(
                language=lang, data=lang_data,
                domestic_images=domestic_images or [],
                global_options=global_data.global_options,
            )
            if ok:
                save_ok = (await self.save_draft(lang)) if save_as_draft else (await self.publish(lang))
                if save_ok:
                    result["languages_success"].append(lang)
                else:
                    result["languages_failed"].append(lang)
            else:
                result["languages_failed"].append(lang)

        return result
