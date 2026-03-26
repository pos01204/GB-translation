"""
작가웹 글로벌 작품 등록 — Playwright UI 조작 + 임시저장 버튼 방식

확정된 플로우 (2026-03-26 디버그 결과):
1. 글로벌 페이지 이동 (/product/{uuid}/global)
2. 언어 탭 선택 (GlobalProductLanguageTab__item)
3. 작품명: textarea[name="globalProductName"].fill() + input 이벤트
4. 이미지: migrate-product API가 국내 이미지를 자동 복사 (별도 작업 불필요)
5. 설명: "작품 설명 작성하기" 또는 "수정하기" 버튼 → 에디터 모달에서 블록 입력
6. 키워드: "작품 키워드" 섹션 클릭 → 모달에서 입력
7. 옵션: "옵션 편집" 버튼 → 모달
8. "임시저장" 버튼 클릭 → SPA 내부 저장 로직 (migrate-product API 자동 호출)
"""
import asyncio
import logging
from typing import Optional
from playwright.async_api import Page
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..config import settings

logger = logging.getLogger(__name__)


class ProductWriter:
    """작가웹 글로벌 작품 등록 — UI 조작 방식"""

    def __init__(self, page: Page):
        self.page = page

    # ──────────── 유틸 ────────────

    async def _click(self, locator, timeout: float = 5, label: str = "") -> bool:
        """안전 클릭 — timeout 내에 요소가 없으면 False"""
        try:
            if await locator.count() > 0:
                await locator.click(timeout=timeout * 1000)
                return True
        except Exception as e:
            if label:
                logger.warning(f"'{label}' 클릭 실패: {e}")
        return False

    async def _wait_snackbar(self) -> str:
        """스낵바 메시지 읽기"""
        try:
            snack = self.page.locator('.v-snack__content').first
            await asyncio.sleep(2)
            if await snack.count() > 0:
                return await snack.inner_text()
        except Exception:
            pass
        return ""

    # ──────────── 페이지 이동 ────────────

    async def navigate_to_global(self, product_id: str) -> bool:
        """글로벌 페이지로 이동"""
        url = f"https://artist.idus.com/product/{product_id}/global"
        logger.info(f"글로벌 페이지 이동: {url}")
        try:
            await self.page.goto(url, timeout=30000)
            await self.page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            logger.warning(f"goto 오류 (계속): {e}")
        await asyncio.sleep(5)

        # textarea 존재 확인
        try:
            await self.page.wait_for_selector(
                'textarea[name="globalProductName"]', timeout=10000
            )
        except Exception:
            logger.warning("globalProductName textarea 대기 실패")
            return False

        logger.info("글로벌 탭 이동 완료")
        return True

    async def select_language(self, language: str) -> bool:
        """언어 탭 선택"""
        lang_text = "영어" if language == "en" else "일본어"
        tab = self.page.locator(
            f'.GlobalProductLanguageTab__item:has-text("{lang_text}")'
        ).first
        if await self._click(tab, label=f"'{lang_text}' 탭"):
            await asyncio.sleep(3)
            logger.info(f"'{lang_text}' 탭 선택 완료")
            return True
        return False

    # ──────────── 작품명 ────────────

    async def fill_title(self, title: str) -> bool:
        """작품명 입력 — textarea + input 이벤트"""
        textarea = self.page.locator('textarea[name="globalProductName"]').first
        if await textarea.count() == 0:
            logger.warning("작품명 textarea 없음")
            return False
        truncated = title[:settings.title_max_length_global]
        await textarea.fill(truncated)
        await textarea.dispatch_event("input")
        logger.info(f"작품명 입력: {truncated[:30]}...")
        return True

    # ──────────── 설명 에디터 ────────────

    async def fill_description(self, blocks: list[dict]) -> bool:
        """작품 설명 — 에디터 모달 열고 블록 입력

        에디터 모달 구조:
        - 툴바: 이미지/GIF, 타이틀, 본문, 인용구, 구분선, 여백 버튼
        - 각 블록 추가 후 텍스트 입력

        현재 접근: Vuex commit으로 premiumDescription 설정 후 에디터를 열지 않고 저장
        → 이전 테스트에서 설명 1블록만 전달됨 (Vuex가 부분 반영)
        → 에디터 UI를 통해 직접 입력 필요
        """
        if not blocks:
            return False

        # 1단계: "작품 설명 작성하기" 또는 "수정하기" 버튼 찾기
        await self.page.evaluate("window.scrollTo(0, 500)")
        await asyncio.sleep(1)

        desc_btn = None
        for text in ["작품 설명 작성하기", "수정하기"]:
            btn = self.page.locator(f'button:has-text("{text}")').first
            if await btn.count() > 0:
                desc_btn = btn
                break

        if not desc_btn:
            logger.warning("설명 에디터 버튼 없음")
            return False

        await desc_btn.click()
        await asyncio.sleep(2)

        # 2단계: 에디터 모달에서 블록 입력
        modal = self.page.locator('.v-dialog--active').first
        if await modal.count() == 0:
            logger.warning("설명 에디터 모달 미열림")
            return False

        # 에디터 내 블록 입력 — 각 블록 타입에 맞는 버튼 클릭 + 텍스트 입력
        text_blocks = [b for b in blocks if b.get("type") in ("TEXT", "SUBJECT")]
        entered = 0

        for block in text_blocks[:10]:  # 최대 10블록
            block_type = block.get("type", "TEXT")
            value = block.get("value", "")
            if isinstance(value, list):
                value = " ".join(str(v) for v in value)
            if not value:
                continue

            # "본문" 버튼 클릭 (TEXT) 또는 "타이틀" 버튼 클릭 (SUBJECT)
            toolbar_text = "타이틀" if block_type == "SUBJECT" else "본문"
            toolbar_btn = modal.locator(f'button:has-text("{toolbar_text}"), [role="button"]:has-text("{toolbar_text}")').first
            if await toolbar_btn.count() > 0:
                await toolbar_btn.click()
                await asyncio.sleep(0.5)

                # 마지막 입력 가능 요소에 텍스트 입력
                editable = modal.locator('[contenteditable="true"], textarea').last
                if await editable.count() > 0:
                    await editable.fill(value)
                    await asyncio.sleep(0.3)
                    entered += 1
            else:
                # 툴바 버튼 못 찾으면 직접 텍스트 입력 시도
                editable = modal.locator('[contenteditable="true"], textarea').last
                if await editable.count() > 0:
                    await editable.click()
                    await self.page.keyboard.type(value[:500], delay=10)
                    await self.page.keyboard.press("Enter")
                    await asyncio.sleep(0.3)
                    entered += 1

        # 3단계: 에디터 저장
        save_btn = modal.locator('button:has-text("저장"), text="저장"').first
        if await self._click(save_btn, label="에디터 저장"):
            await asyncio.sleep(1)
        else:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

        logger.info(f"설명 입력 완료: {entered}블록")
        return entered > 0

    # ──────────── 키워드 ────────────

    async def fill_keywords(self, keywords: list[str]) -> bool:
        """키워드 — 키워드 섹션 클릭 → 모달에서 입력"""
        if not keywords:
            return False

        # 키워드 섹션 찾기 + 클릭
        await self.page.evaluate("window.scrollTo(0, 700)")
        await asyncio.sleep(1)

        kw_section = self.page.locator('div:has-text("작품 키워드")').last
        if await self._click(kw_section, label="키워드 섹션"):
            await asyncio.sleep(1.5)
        else:
            return False

        # 모달 내 입력 필드
        modal = self.page.locator('.v-dialog--active').first
        if await modal.count() == 0:
            logger.warning("키워드 모달 미열림")
            return False

        # 키워드 입력 + "추가" 버튼
        kw_input = modal.locator('input[type="text"]').first
        add_btn = modal.locator('button:has-text("추가")').first

        entered = 0
        for kw in keywords[:10]:  # 최대 10개
            cleaned = kw.strip().lstrip('#')
            if not cleaned:
                continue
            if await kw_input.count() > 0:
                await kw_input.fill(cleaned)
                if await add_btn.count() > 0:
                    await add_btn.click()
                else:
                    await kw_input.press("Enter")
                await asyncio.sleep(0.3)
                entered += 1

        # 모달 저장
        save_btn = modal.locator('text="저장"').first
        if await self._click(save_btn, label="키워드 저장"):
            await asyncio.sleep(1)
        else:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

        logger.info(f"키워드 {entered}개 입력 완료")
        return entered > 0

    # ──────────── 옵션 ────────────

    async def fill_options(self, options: list[GlobalOption], language: str) -> bool:
        """글로벌 옵션 — "옵션 편집" 모달"""
        if not options:
            return True  # 옵션 없으면 성공

        await self.page.evaluate("window.scrollTo(0, 900)")
        await asyncio.sleep(1)

        edit_btn = self.page.locator('button:has-text("옵션 편집")').first
        if not await self._click(edit_btn, label="옵션 편집"):
            return False
        await asyncio.sleep(2)

        modal = self.page.locator('.v-dialog--active').first
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
            if await self._click(add_btn, timeout=3):
                await asyncio.sleep(1)

            # 옵션명 입력
            name_inputs = modal.locator('input[type="text"]')
            count = await name_inputs.count()
            if count > 0:
                await name_inputs.first.fill(name)

            # 옵션값 입력
            for val in values:
                val_inputs = modal.locator('input[type="text"]')
                cnt = await val_inputs.count()
                if cnt > 1:
                    await val_inputs.nth(cnt - 1).fill(val)
                    await val_inputs.nth(cnt - 1).press("Enter")
                    await asyncio.sleep(0.3)

        # 적용
        apply_btn = modal.locator('text="적용"').first
        if await self._click(apply_btn, label="옵션 적용"):
            await asyncio.sleep(1)
        else:
            await self.page.keyboard.press("Escape")

        logger.info(f"옵션 {len(options)}개 입력 ({language})")
        return True

    # ──────────── 저장 ────────────

    async def save_draft(self) -> tuple[bool, str]:
        """임시저장 버튼 클릭 + 결과 확인"""
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.5)
        btn = self.page.locator('button:has-text("임시저장")').first
        if not await self._click(btn, label="임시저장"):
            return False, "임시저장 버튼 없음"
        msg = await self._wait_snackbar()
        success = "완료" in msg if msg else False
        if success:
            logger.info(f"임시저장 성공: {msg}")
        else:
            logger.error(f"임시저장 실패: {msg or '스낵바 없음'}")
        return success, msg

    async def publish(self) -> tuple[bool, str]:
        """판매 등록"""
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.5)
        btn = self.page.locator('button:has-text("작품 판매하기")').first
        if not await self._click(btn, label="판매 등록"):
            return False, "판매 등록 버튼 없음"
        msg = await self._wait_snackbar()
        success = "완료" in msg if msg else False
        return success, msg

    # ──────────── 통합 ────────────

    async def register_language(
        self,
        language: str,
        data: LanguageData,
        global_options: list[GlobalOption] = None,
    ) -> bool:
        """특정 언어 등록 — 전체 UI 조작 플로우"""
        lang_label = "영어" if language == "en" else "일본어"
        logger.info(f"{lang_label} 등록 시작")

        # 1. 언어 탭 선택
        if not await self.select_language(language):
            return False

        # 2. 작품명
        await self.fill_title(data.title)

        # 3. 설명 (에디터 모달)
        blocks = data.description_blocks if hasattr(data, 'description_blocks') and data.description_blocks else []
        if blocks:
            await self.fill_description(blocks)

        # 4. 키워드 (모달)
        if data.keywords:
            await self.fill_keywords(data.keywords)

        # 5. 옵션 (모달)
        if global_options:
            await self.fill_options(global_options, language)

        # 6. 임시저장
        success, msg = await self.save_draft()

        logger.info(f"{lang_label} 등록 {'성공' if success else '실패'}: {msg}")
        return success

    async def register_global_product(
        self,
        global_data: GlobalProductData,
        product_id: str = "",
        save_as_draft: bool = True,
        target_languages: list[str] = None,
        domestic_images: list[str] = None,
    ) -> dict:
        """글로벌 작품 등록 — 전체 프로세스"""
        if target_languages is None:
            target_languages = []
            if global_data.ja:
                target_languages.append("ja")
            if global_data.en:
                target_languages.append("en")

        result = {"languages_success": [], "languages_failed": []}

        if not product_id:
            logger.error("product_id가 없습니다")
            result["languages_failed"] = target_languages
            return result

        # 글로벌 페이지 이동
        if not await self.navigate_to_global(product_id):
            result["languages_failed"] = target_languages
            return result

        for lang in target_languages:
            lang_data = global_data.ja if lang == "ja" else global_data.en
            if not lang_data:
                result["languages_failed"].append(lang)
                continue

            ok = await self.register_language(
                language=lang,
                data=lang_data,
                global_options=global_data.global_options,
            )
            if ok:
                result["languages_success"].append(lang)
            else:
                result["languages_failed"].append(lang)

        return result
