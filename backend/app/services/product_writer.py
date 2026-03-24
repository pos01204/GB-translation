"""
작가웹 글로벌 탭 자동 입력 서비스

스크린샷 기반 확인된 모달 구조 (2026-03-25):

[이미지 모달 — 2단계]
1단계: '+' 사각형 클릭 → 바텀시트 ("국내 작품 이미지 불러오기" / "새로운 작품 이미지 등록하기")
2단계: "국내 작품 이미지 불러오기" 클릭 → 이미지 선택 모달
       "전체" 체크박스 → "X개 이미지 추가" 버튼

[키워드 모달]
트리거: 키워드 섹션 '>' 클릭
타이틀: "영어 작품 키워드" / "일본어 작품 키워드"
입력: input (placeholder "키워드를 영어로 입력해 주세요") + "추가" 버튼
저장: 우상단 "저장"

[옵션 모달]
트리거: "옵션 편집" 클릭
타이틀: "글로벌 옵션 (일본어/영어)"
구조: "기본형 옵션" 라디오(기본) → "추가" → 옵션명 input → "추가+" → 값 input
저장: 우상단 "적용"
"""
import asyncio
import logging
from typing import Optional
from playwright.async_api import Page
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..config import settings

logger = logging.getLogger(__name__)


class ProductWriter:
    """작가웹 글로벌 탭 데이터 입력기"""

    def __init__(self, page: Page):
        self.page = page

    # ──────────── 유틸 ────────────

    async def _safe_click(self, locator, timeout: float = 5, label: str = "") -> bool:
        """로케이터 클릭 — timeout 내에 요소가 없으면 False"""
        try:
            count = await asyncio.wait_for(locator.count(), timeout=timeout)
            if count > 0:
                await locator.click()
                return True
        except (asyncio.TimeoutError, Exception):
            pass
        if label:
            logger.warning(f"'{label}' 요소 없음 (건너뜀)")
        return False

    async def _close_any_modal(self):
        """열려있는 모달/패널 닫기"""
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except Exception:
            pass

    # ──────────── 탭 네비게이션 ────────────

    async def navigate_to_global_tab(self, product_id: str = "") -> bool:
        """글로벌 페이지 이동 (/product/{uuid}/global)"""
        try:
            if product_id:
                url = f"https://artist.idus.com/product/{product_id}/global"
                logger.info(f"글로벌 페이지 이동: {url}")
                try:
                    await self.page.goto(url, timeout=30000)
                    await self.page.wait_for_load_state("domcontentloaded")
                except Exception as e:
                    logger.warning(f"goto 오류 (계속): {e}")
                await asyncio.sleep(3)
            else:
                tab = self.page.locator('.v-tab:has-text("글로벌")').first
                if await self._safe_click(tab, label="글로벌 탭"):
                    await asyncio.sleep(2)
                else:
                    return False
            logger.info("글로벌 탭 이동 완료")
            return True
        except Exception as e:
            logger.error(f"글로벌 탭 이동 실패: {e}")
            return False

    async def select_language_tab(self, language: str) -> bool:
        """언어 서브탭 선택"""
        lang_text = "영어" if language == "en" else "일본어"
        tab = self.page.locator(
            f'.GlobalProductLanguageTab__item:has-text("{lang_text}")'
        ).first
        if await self._safe_click(tab, label=f"'{lang_text}' 탭"):
            await asyncio.sleep(2)
            logger.info(f"'{lang_text}' 탭 선택 완료")
            return True
        return False

    # ──────────── 이미지 (2단계 모달) ────────────

    async def import_domestic_images(self) -> bool:
        """국내 작품 이미지 불러오기 — '+' → 바텀시트 → 이미지 선택 → 추가"""
        try:
            # STEP 1: '+' 사각형 클릭 — 이미지 추가 영역
            # 스크린샷: 회색 사각형 안에 '+' 표시
            plus_btn = await self.page.evaluate("""
                () => {
                    // '+' 텍스트를 가진 요소 찾기
                    const allEls = document.querySelectorAll('div, button, label, span');
                    for (const el of allEls) {
                        const text = el.textContent?.trim();
                        // '+' 만 포함된 작은 요소 (이미지 추가 버튼)
                        if (text === '+' && el.offsetHeight > 30 && el.offsetHeight < 200) {
                            el.click();
                            return { clicked: true, tag: el.tagName, classes: el.className?.substring(0, 80) };
                        }
                    }
                    return { clicked: false };
                }
            """)

            if not plus_btn.get("clicked"):
                logger.warning(f"이미지 '+' 버튼 없음: {plus_btn}")
                return False

            logger.info(f"이미지 '+' 클릭: {plus_btn.get('tag')}.{plus_btn.get('classes', '')[:30]}")
            await asyncio.sleep(1.5)

            # STEP 2: 바텀시트에서 "국내 작품 이미지 불러오기" 클릭
            import_link = self.page.locator('text="국내 작품 이미지 불러오기"').first
            if not await self._safe_click(import_link, timeout=5, label="국내 작품 이미지 불러오기"):
                await self._close_any_modal()
                return False

            logger.info("'국내 작품 이미지 불러오기' 클릭")
            await asyncio.sleep(2)

            # STEP 3: "전체" 체크박스 클릭
            # 모달 내의 "전체" 텍스트 옆 체크박스
            select_all = self.page.locator('.v-dialog--active label:has-text("전체")').first
            if not await self._safe_click(select_all, timeout=5):
                # 폴백: 첫 번째 체크박스
                select_all = self.page.locator('.v-dialog--active input[type="checkbox"]').first
                await self._safe_click(select_all, label="전체 체크박스")

            logger.info("'전체' 선택")
            await asyncio.sleep(1)

            # STEP 4: "X개 이미지 추가" 버튼 클릭
            add_btn = self.page.locator('.v-dialog--active button:has-text("이미지 추가")').first
            if await self._safe_click(add_btn, timeout=5, label="이미지 추가 버튼"):
                logger.info("이미지 추가 완료")
            else:
                await self._close_any_modal()

            await asyncio.sleep(2)
            return True

        except Exception as e:
            logger.error(f"이미지 불러오기 실패: {e}")
            await self._close_any_modal()
            return False

    # ──────────── 작품명 ────────────

    async def fill_title(self, title: str) -> bool:
        """작품명 입력"""
        try:
            inp = self.page.locator('textarea[name="globalProductName"]').first
            if await inp.count() == 0:
                inp = self.page.locator('textarea[placeholder*="입력해 주세요"]').first
            if await inp.count() == 0:
                logger.warning("작품명 입력 필드 없음")
                return False

            truncated = title[:settings.title_max_length_global]
            await inp.click()
            await inp.fill("")
            await inp.type(truncated, delay=50)
            logger.info(f"작품명 입력: {truncated[:30]}...")
            return True
        except Exception as e:
            logger.error(f"작품명 입력 실패: {e}")
            return False

    # ──────────── 작품 설명 (Vuex 주입) ────────────

    async def fill_description_blocks(self, blocks: list[dict]) -> bool:
        """premiumDescription 블록 배열을 Vuex에 주입"""
        try:
            ok = await self.page.evaluate("""
                (blocks) => {
                    const app = document.querySelector('#app');
                    if (!app || !app.__vue__ || !app.__vue__.$store) return false;
                    const ui = app.__vue__.$store.state.globalProduct?._detailUI;
                    if (!ui) return false;
                    ui.premiumDescription = blocks;
                    return true;
                }
            """, blocks)
            if ok:
                logger.info(f"설명 블록 {len(blocks)}개 Vuex 주입 완료")
            else:
                logger.warning("Vuex 주입 실패")
            return bool(ok)
        except Exception as e:
            logger.error(f"설명 입력 실패: {e}")
            return False

    # ──────────── 키워드 (모달) ────────────

    async def fill_keywords(self, keywords: list[str]) -> bool:
        """키워드 모달 — 섹션 '>' 클릭 → input + "추가" → "저장" """
        try:
            # 키워드 섹션 클릭하여 모달 열기
            kw_trigger = self.page.locator(
                '[class*="contentItem"]:has-text("작품 키워드")'
            ).first
            if await kw_trigger.count() == 0:
                kw_trigger = self.page.locator('text="작품 키워드"').first
            # '>' 아이콘 또는 섹션 자체가 클릭 가능
            if not await self._safe_click(kw_trigger, timeout=5, label="키워드 섹션"):
                return False
            await asyncio.sleep(1.5)

            # 모달 내 키워드 입력 필드 찾기
            modal = self.page.locator('.v-dialog--active')
            if await modal.count() == 0:
                logger.warning("키워드 모달이 열리지 않음")
                return False

            kw_input = modal.locator('input[placeholder*="키워드"], input[placeholder*="입력"]').first
            if await kw_input.count() == 0:
                logger.warning("키워드 입력 필드 없음")
                await self._close_any_modal()
                return False

            # "추가" 버튼 찾기
            add_btn = modal.locator('button:has-text("추가")').first

            for keyword in keywords:
                kw = keyword.strip().lstrip('#')
                if not kw:
                    continue
                await kw_input.fill(kw)
                # "추가" 버튼 클릭 또는 Enter
                if await add_btn.count() > 0:
                    await add_btn.click()
                else:
                    await kw_input.press('Enter')
                await asyncio.sleep(0.3)

            logger.info(f"키워드 {len(keywords)}개 입력 완료")

            # "저장" 버튼 클릭
            save_btn = modal.locator('text="저장"').first
            if await self._safe_click(save_btn, timeout=3, label="키워드 저장"):
                await asyncio.sleep(1)
            else:
                await self._close_any_modal()

            return True

        except Exception as e:
            logger.error(f"키워드 입력 실패: {e}")
            await self._close_any_modal()
            return False

    # ──────────── 옵션 (모달) ────────────

    async def fill_global_options(
        self, options: list[GlobalOption], language: str,
    ) -> bool:
        """옵션 모달 — "옵션 편집" → "추가" → 옵션명 → "추가+" → 값 → "적용" """
        try:
            await self._close_any_modal()

            # "옵션 편집" 클릭
            edit_btn = self.page.locator('button:has-text("옵션 편집"), text="옵션 편집"').first
            if not await self._safe_click(edit_btn, timeout=5, label="옵션 편집"):
                return False
            await asyncio.sleep(1.5)

            modal = self.page.locator('.v-dialog--active')
            if await modal.count() == 0:
                logger.warning("옵션 편집 모달 미열림")
                return False

            for option in options:
                name = option.name_en if language == "en" else option.name_ja
                values = option.values_en if language == "en" else option.values_ja
                if not name or not values:
                    continue

                # "추가" 버튼 클릭 → 옵션 입력 폼 생성
                add_opt_btn = modal.locator('button:has-text("추가")').first
                if await self._safe_click(add_opt_btn, timeout=3, label="옵션 추가"):
                    await asyncio.sleep(1)

                # 옵션명 입력 (placeholder "영어를 입력해 주세요" 또는 유사)
                name_input = modal.locator(
                    'input[placeholder*="입력해 주세요"]'
                ).first
                if await name_input.count() > 0:
                    await name_input.fill(name)
                    logger.info(f"옵션명 입력: {name}")
                else:
                    logger.warning("옵션명 입력 필드 없음")

                # 옵션 값 입력: "추가+" 클릭 → 값 input에 입력
                for val in values:
                    # "추가+" 링크 클릭 (값 행 추가)
                    add_val = modal.locator('text="추가"').last
                    await self._safe_click(add_val, timeout=2)
                    await asyncio.sleep(0.5)

                    # 마지막 값 input에 입력
                    val_inputs = modal.locator(
                        'input[placeholder*="입력해 주세요"]'
                    )
                    val_count = await val_inputs.count()
                    if val_count > 1:
                        # 마지막 input이 새로 추가된 값 input
                        last_input = val_inputs.nth(val_count - 1)
                        await last_input.fill(val)
                        logger.info(f"옵션값 입력: {val}")

                await asyncio.sleep(0.3)

            # "적용" 클릭
            apply_btn = modal.locator('text="적용"').first
            if await self._safe_click(apply_btn, timeout=5, label="옵션 적용"):
                await asyncio.sleep(1)
            else:
                await self._close_any_modal()

            logger.info(f"옵션 {len(options)}개 입력 완료 ({language})")
            return True

        except Exception as e:
            logger.error(f"옵션 입력 실패: {e}")
            await self._close_any_modal()
            return False

    # ──────────── 저장/등록 ────────────

    async def save_draft(self, language: str = "ja") -> bool:
        """임시저장"""
        lang_text = "영어" if language == "en" else "일본어"
        await self._close_any_modal()

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
        await self._close_any_modal()

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
                    if text and len(text) < 500:
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
        global_options: Optional[list[GlobalOption]] = None,
    ) -> bool:
        """특정 언어 탭의 전체 데이터 입력"""
        lang_label = "영어" if language == "en" else "일본어"
        logger.info(f"{lang_label} 데이터 입력 시작")

        if not await self.select_language_tab(language):
            return False

        # 이미지 (필수 — 가장 먼저)
        await self.import_domestic_images()

        # 작품명
        await self.fill_title(data.title)

        # 설명 (Vuex 주입)
        if hasattr(data, 'description_blocks') and data.description_blocks:
            await self.fill_description_blocks(data.description_blocks)

        # 키워드
        if data.keywords:
            await self.fill_keywords(data.keywords)

        # 옵션
        if global_options:
            await self.fill_global_options(global_options, language)

        logger.info(f"{lang_label} 데이터 입력 완료")
        return True

    async def register_global_product(
        self, global_data: GlobalProductData,
        product_id: str = "", save_as_draft: bool = True,
        target_languages: Optional[list[str]] = None,
    ) -> dict:
        """글로벌 탭 전체 등록"""
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
