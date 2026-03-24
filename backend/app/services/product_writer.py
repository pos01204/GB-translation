"""
작가웹 글로벌 탭 자동 입력 서비스

확인된 DOM 구조 (2026-03-25 디버그):
- URL: /product/{uuid}/global
- 언어 탭: div.GlobalProductLanguageTab__item (--active / --inactive)
- 작품명: textarea[name="globalProductName"]
- 이미지: '+' 버튼 → 토스트 모달 → "국내 작품 이미지 불러오기" → "전체" → "이미지 추가"
- 설명: premiumDescription Vuex 주입
- 옵션: "옵션 편집" 모달
- 저장: "일본어 임시저장" / "일본어 작품 판매하기"
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

    # ──────────────── 탭 네비게이션 ────────────────

    async def navigate_to_global_tab(self, product_id: str = "") -> bool:
        """글로벌 페이지로 이동 (/product/{uuid}/global URL 직접 이동)"""
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
                global_tab = self.page.locator(
                    '.BaseTabs__item:has-text("글로벌"), .v-tab:has-text("글로벌")'
                ).first
                if await global_tab.count() > 0:
                    await global_tab.click()
                    await asyncio.sleep(2)
                else:
                    logger.warning("글로벌 탭을 찾을 수 없습니다")
                    return False

            logger.info("글로벌 탭 이동 완료")
            return True
        except Exception as e:
            logger.error(f"글로벌 탭 이동 실패: {e}")
            return False

    async def select_language_tab(self, language: str) -> bool:
        """언어 서브탭 선택 — div.GlobalProductLanguageTab__item"""
        lang_text = "영어" if language == "en" else "일본어"
        try:
            lang_tab = self.page.locator(
                f'.GlobalProductLanguageTab__item:has-text("{lang_text}")'
            ).first

            if await lang_tab.count() == 0:
                logger.warning(f"'{lang_text}' 탭을 찾을 수 없습니다")
                return False

            await lang_tab.click()
            await asyncio.sleep(2)
            logger.info(f"'{lang_text}' 탭 선택 완료")
            return True
        except Exception as e:
            logger.error(f"'{lang_text}' 탭 선택 실패: {e}")
            return False

    # ──────────────── 이미지 처리 ────────────────

    async def import_domestic_images(self) -> bool:
        """국내 작품 이미지 불러오기 — 스크린샷 기반 정확한 플로우

        1. '+' 버튼 클릭 → 토스트 모달
        2. "국내 작품 이미지 불러오기" 클릭 → 이미지 선택 모달
        3. "전체" 체크박스 선택
        4. "이미지 추가" 버튼 클릭
        """
        try:
            # STEP 1: 이미지 추가 영역 클릭
            # 스크린샷: 회색 빈 사각형 안에 '+' 표시 — div 또는 label 클릭
            plus_selectors = [
                '[class*="ImageUpload"] [class*="add"]',
                '[class*="imageUpload"] [class*="add"]',
                '[class*="image-upload"] [class*="add"]',
                '[class*="ImageAdd"]',
                '[class*="imageAdd"]',
                'label[for*="image"]',
                '[class*="upload"] [class*="plus"]',
            ]
            plus_clicked = False
            for sel in plus_selectors:
                btn = self.page.locator(sel).first
                try:
                    if await asyncio.wait_for(btn.count(), timeout=2) > 0:
                        await btn.click()
                        plus_clicked = True
                        logger.info(f"이미지 추가 영역 클릭 (셀렉터: {sel})")
                        break
                except (asyncio.TimeoutError, Exception):
                    continue

            # 폴백: JS로 이미지 추가 영역 찾기
            if not plus_clicked:
                try:
                    clicked = await self.page.evaluate("""
                        () => {
                            // 이미지 섹션 내의 추가 버튼/영역 찾기
                            const candidates = document.querySelectorAll(
                                '[class*="image"] [class*="add"], ' +
                                '[class*="Image"] [class*="Add"], ' +
                                '[class*="upload"], [class*="Upload"]'
                            );
                            for (const el of candidates) {
                                const text = el.textContent?.trim();
                                if (text === '+' || text === '' || el.querySelector('svg, i')) {
                                    el.click();
                                    return true;
                                }
                            }
                            // 더 넓은 탐색: "작품 이미지" 근처의 클릭 가능 영역
                            const imageSection = document.querySelector('[class*="작품 이미지"], [class*="image"]');
                            if (imageSection) {
                                const addBtn = imageSection.querySelector('[class*="add"], [class*="plus"], button');
                                if (addBtn) { addBtn.click(); return true; }
                            }
                            return false;
                        }
                    """)
                    if clicked:
                        plus_clicked = True
                        logger.info("이미지 추가 영역 클릭 (JS 폴백)")
                except Exception:
                    pass

            if not plus_clicked:
                logger.warning("이미지 추가 영역을 찾을 수 없습니다 — 디버그 필요")
                # 디버그: 이미지 관련 요소 덤프
                try:
                    debug = await self.page.evaluate("""
                        () => {
                            const els = document.querySelectorAll('[class*="image"], [class*="Image"], [class*="upload"], [class*="Upload"]');
                            return Array.from(els).slice(0, 10).map(el => ({
                                tag: el.tagName,
                                classes: (el.className || '').substring(0, 100),
                                text: el.textContent?.trim().substring(0, 30),
                                children: el.children.length,
                            }));
                        }
                    """)
                    logger.info(f"이미지 관련 요소: {debug}")
                except Exception:
                    pass
                return False

            await asyncio.sleep(1.5)

            # STEP 2: 토스트/모달에서 "국내 작품 이미지 불러오기" 클릭
            import_btn = self.page.locator('text=국내 작품 이미지 불러오기').first
            try:
                if await asyncio.wait_for(import_btn.count(), timeout=5) > 0:
                    await import_btn.click()
                    logger.info("'국내 작품 이미지 불러오기' 클릭")
                else:
                    logger.warning("'국내 작품 이미지 불러오기' 메뉴 없음")
                    await self.page.keyboard.press("Escape")
                    return False
            except asyncio.TimeoutError:
                logger.warning("'국내 작품 이미지 불러오기' 메뉴 대기 timeout")
                await self.page.keyboard.press("Escape")
                return False

            await asyncio.sleep(2)

            # STEP 3: "전체" 체크박스 선택
            select_all = self.page.locator(
                '.v-dialog--active text=전체, '
                '.v-dialog--active input[type="checkbox"]'
            ).first
            try:
                if await asyncio.wait_for(select_all.count(), timeout=5) > 0:
                    await select_all.click()
                    logger.info("'전체' 선택")
                else:
                    logger.warning("'전체' 체크박스 없음")
            except asyncio.TimeoutError:
                logger.warning("'전체' 체크박스 대기 timeout")

            await asyncio.sleep(1)

            # STEP 4: "X개 이미지 추가" 버튼 클릭
            add_btn = self.page.locator(
                '.v-dialog--active button:has-text("이미지 추가")'
            ).first
            try:
                if await asyncio.wait_for(add_btn.count(), timeout=5) > 0:
                    await add_btn.click()
                    logger.info("이미지 추가 완료")
                else:
                    # 폴백: 모달 내 확인/적용 버튼
                    ok_btn = self.page.locator(
                        '.v-dialog--active button:has-text("확인"), '
                        '.v-dialog--active button:has-text("적용")'
                    ).first
                    if await asyncio.wait_for(ok_btn.count(), timeout=3) > 0:
                        await ok_btn.click()
                    else:
                        await self.page.keyboard.press("Escape")
            except asyncio.TimeoutError:
                await self.page.keyboard.press("Escape")

            await asyncio.sleep(2)
            return True

        except Exception as e:
            logger.error(f"국내 이미지 불러오기 실패: {e}")
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
            return False

    # ──────────────── 필드 입력 ────────────────

    async def fill_title(self, title: str) -> bool:
        """작품명 입력 — textarea[name="globalProductName"]"""
        try:
            title_input = self.page.locator(
                'textarea[name="globalProductName"]'
            ).first

            if await title_input.count() == 0:
                title_input = self.page.locator(
                    'textarea[placeholder*="입력해 주세요"]'
                ).first

            if await title_input.count() == 0:
                logger.warning("작품명 입력 필드를 찾을 수 없습니다")
                return False

            truncated = title[:settings.title_max_length_global]
            await title_input.click()
            await title_input.fill("")
            await title_input.type(truncated, delay=50)
            logger.info(f"작품명 입력 완료: {truncated[:30]}...")
            return True
        except Exception as e:
            logger.error(f"작품명 입력 실패: {e}")
            return False

    async def fill_description_blocks(self, blocks: list[dict]) -> bool:
        """작품 설명 — premiumDescription 블록 배열을 Vuex에 주입"""
        try:
            success = await self.page.evaluate("""
                (blocks) => {
                    const app = document.querySelector('#app');
                    if (!app || !app.__vue__ || !app.__vue__.$store) return false;
                    const store = app.__vue__.$store;
                    const ui = store.state.globalProduct?._detailUI;
                    if (!ui) return false;
                    ui.premiumDescription = blocks;
                    return true;
                }
            """, blocks)

            if success:
                logger.info(f"작품 설명 블록 {len(blocks)}개 Vuex 주입 완료")
            else:
                logger.warning("Vuex 주입 실패 — _detailUI 없음")
            return bool(success)
        except Exception as e:
            logger.error(f"작품 설명 입력 실패: {e}")
            return False

    async def fill_keywords(self, keywords: list[str]) -> bool:
        """작품 키워드 — 키워드 섹션 클릭 → 입력 → 닫기"""
        try:
            # 키워드 섹션 클릭 (모달/패널 열기)
            kw_section = self.page.locator(
                '[class*="contentItem"]:has-text("작품 키워드")'
            ).first
            if await kw_section.count() == 0:
                kw_section = self.page.locator('text="작품 키워드"').first
            if await kw_section.count() > 0:
                await kw_section.click()
                await asyncio.sleep(1.5)

            # 키워드 입력 필드
            keyword_input = self.page.locator(
                'input[placeholder*="키워드"], '
                'input[name*="keyword"], '
                'input[placeholder*="태그"]'
            ).first

            if await keyword_input.count() == 0:
                logger.warning("키워드 입력 필드를 찾을 수 없습니다")
                return False

            for keyword in keywords:
                kw = keyword.strip().lstrip('#')
                if not kw:
                    continue
                await keyword_input.fill(kw)
                await keyword_input.press('Enter')
                await asyncio.sleep(0.3)

            logger.info(f"키워드 {len(keywords)}개 입력 완료")

            # 패널 닫기
            save_btn = self.page.locator(
                '.v-dialog--active button:has-text("저장"), '
                '.v-dialog--active button:has-text("확인")'
            ).first
            try:
                if await asyncio.wait_for(save_btn.count(), timeout=2) > 0:
                    await save_btn.click()
                    await asyncio.sleep(1)
                else:
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
            except asyncio.TimeoutError:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)

            return True
        except Exception as e:
            logger.error(f"키워드 입력 실패: {e}")
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
            return False

    async def fill_global_options(
        self, options: list[GlobalOption], language: str,
    ) -> bool:
        """글로벌 옵션 — "옵션 편집" 모달"""
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

            edit_btn = self.page.locator('button:has-text("옵션 편집")').first
            try:
                if await asyncio.wait_for(edit_btn.count(), timeout=5) == 0:
                    logger.warning("옵션 편집 버튼 없음 (건너뜀)")
                    return False
            except asyncio.TimeoutError:
                logger.warning("옵션 편집 버튼 대기 timeout (건너뜀)")
                return False

            await edit_btn.click()
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

                name_input = modal.locator('input[name="productOptionName"]').first
                if await name_input.count() > 0:
                    await name_input.fill(name)

                for val in values:
                    value_input = modal.locator('input[name="productOptionValue"]').last
                    if await value_input.count() > 0:
                        await value_input.fill(val)
                        await value_input.press('Enter')
                        await asyncio.sleep(0.3)

            save_btn = modal.locator('button:has-text("저장"), button:has-text("적용")').first
            if await save_btn.count() > 0:
                await save_btn.click()
                await asyncio.sleep(1)
            else:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)

            logger.info(f"옵션 {len(options)}개 입력 완료 ({language})")
            return True
        except Exception as e:
            logger.error(f"옵션 입력 실패: {e}")
            return False

    # ──────────────── 저장/등록 ────────────────

    async def save_draft(self, language: str = "ja") -> bool:
        """임시저장"""
        lang_text = "영어" if language == "en" else "일본어"
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

            btn = self.page.locator(f'button:has-text("{lang_text} 임시저장")').first
            try:
                if await asyncio.wait_for(btn.count(), timeout=5) == 0:
                    btn = self.page.locator('button:has-text("임시저장")').first
            except asyncio.TimeoutError:
                btn = self.page.locator('button:has-text("임시저장")').first

            try:
                if await asyncio.wait_for(btn.count(), timeout=3) == 0:
                    logger.warning("임시저장 버튼 없음")
                    return False
            except asyncio.TimeoutError:
                logger.warning("임시저장 버튼 대기 timeout")
                return False

            await btn.click()
            await asyncio.sleep(3)

            # 저장 후 에러 확인
            await self._check_save_result(lang_text, "임시저장")
            return True
        except Exception as e:
            logger.error(f"임시저장 실패: {e}")
            return False

    async def publish(self, language: str = "ja") -> bool:
        """판매 등록"""
        lang_text = "영어" if language == "en" else "일본어"
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

            btn = self.page.locator(f'button:has-text("{lang_text} 작품 판매하기")').first
            try:
                if await asyncio.wait_for(btn.count(), timeout=5) == 0:
                    btn = self.page.locator('button:has-text("작품 판매하기")').first
            except asyncio.TimeoutError:
                btn = self.page.locator('button:has-text("작품 판매하기")').first

            try:
                if await asyncio.wait_for(btn.count(), timeout=3) == 0:
                    logger.warning("판매 등록 버튼 없음")
                    return False
            except asyncio.TimeoutError:
                logger.warning("판매 등록 버튼 대기 timeout")
                return False

            await btn.click()
            await asyncio.sleep(3)

            # 저장 후 에러 확인
            await self._check_save_result(lang_text, "판매 등록")
            return True
        except Exception as e:
            logger.error(f"판매 등록 실패: {e}")
            return False

    async def _check_save_result(self, lang_text: str, action: str) -> bool:
        """저장/등록 후 에러 모달 또는 성공 상태 확인. 실패 시 False 반환."""
        success = True
        try:
            # 에러 다이얼로그 확인
            error_dialog = self.page.locator('.v-dialog--active').first
            try:
                if await asyncio.wait_for(error_dialog.count(), timeout=2) > 0:
                    error_text = await error_dialog.inner_text()
                    if error_text and len(error_text) < 500:
                        logger.error(f"[{action}] 에러 다이얼로그: {error_text[:200]}")
                        success = False
                    ok_btn = error_dialog.locator('button:has-text("확인")').first
                    if await ok_btn.count() > 0:
                        await ok_btn.click()
                        await asyncio.sleep(0.5)
            except asyncio.TimeoutError:
                pass

            # 스낵바/토스트 확인
            snackbar = self.page.locator('.v-snack__content').first
            try:
                if await asyncio.wait_for(snackbar.count(), timeout=1) > 0:
                    msg = await snackbar.inner_text()
                    if "확인" in msg or "입력" in msg or "오류" in msg or "실패" in msg:
                        logger.error(f"[{action}] 에러 스낵바: {msg[:100]}")
                        success = False
                    else:
                        logger.info(f"[{action}] 스낵바: {msg[:100]}")
            except asyncio.TimeoutError:
                pass

            if success:
                logger.info(f"{lang_text} {action} 성공")
            else:
                logger.error(f"{lang_text} {action} 실패 — 필수 입력 정보 확인 필요")
        except Exception as e:
            logger.warning(f"저장 결과 확인 실패 (무시): {e}")

        return success

    # ──────────────── 통합 메서드 ────────────────

    async def fill_language_data(
        self,
        language: str,
        data: LanguageData,
        global_options: Optional[list[GlobalOption]] = None,
        use_domestic_images: bool = True,
    ) -> bool:
        """특정 언어 탭의 전체 데이터 입력"""
        lang_label = "영어" if language == "en" else "일본어"
        logger.info(f"{lang_label} 데이터 입력 시작")

        # 1. 언어 탭 선택
        if not await self.select_language_tab(language):
            return False

        # 2. 이미지 처리 (가장 먼저 — 필수 필드)
        if use_domestic_images:
            await self.import_domestic_images()

        # 3. 작품명 입력
        await self.fill_title(data.title)

        # 4. 작품 설명 (블록 배열 우선)
        if hasattr(data, 'description_blocks') and data.description_blocks:
            await self.fill_description_blocks(data.description_blocks)

        # 5. 키워드 입력
        if data.keywords:
            await self.fill_keywords(data.keywords)

        # 6. 옵션 입력
        if global_options:
            await self.fill_global_options(global_options, language)

        logger.info(f"{lang_label} 데이터 입력 완료")
        return True

    async def register_global_product(
        self,
        global_data: GlobalProductData,
        product_id: str = "",
        save_as_draft: bool = True,
        target_languages: Optional[list[str]] = None,
    ) -> dict:
        """글로벌 탭 전체 등록 프로세스

        Args:
            target_languages: 등록할 언어 목록 (기본: ["ja", "en"])
        """
        if target_languages is None:
            target_languages = []
            if global_data.ja:
                target_languages.append("ja")
            if global_data.en:
                target_languages.append("en")

        result = {
            "languages_success": [],
            "languages_failed": [],
        }

        # 글로벌 탭으로 이동
        if not await self.navigate_to_global_tab(product_id):
            result["languages_failed"] = target_languages
            return result

        # 요청된 언어만 등록
        for lang in target_languages:
            lang_data = global_data.ja if lang == "ja" else global_data.en
            if not lang_data:
                result["languages_failed"].append(lang)
                continue

            success = await self.fill_language_data(
                language=lang,
                data=lang_data,
                global_options=global_data.global_options,
            )
            if success:
                if save_as_draft:
                    await self.save_draft(lang)
                else:
                    await self.publish(lang)
                result["languages_success"].append(lang)
            else:
                result["languages_failed"].append(lang)

        return result
