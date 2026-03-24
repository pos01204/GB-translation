"""
작가웹 글로벌 탭 자동 입력 서비스

번역 결과(GlobalProductData)를 작가웹의 글로벌 탭 폼에
실제로 입력하는 핵심 모듈입니다.

확인된 DOM 구조 (2026-03-25 디버그):
- URL: /product/{uuid}/global
- 언어 탭: div.GlobalProductLanguageTab__item (--active / --inactive)
  - "일본어 ... 미등록" / "영어 미등록"
- 작품명: textarea[name="globalProductName"]
- 이미지: "등록 전 확인해 주세요." 드롭다운 내 이미지 업로드
- 설명: "작품 설명 작성하기" 버튼 → premiumDescription 에디터 모달
- 옵션: "옵션 편집" 버튼
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
            # product_id가 있으면 URL 직접 이동
            if product_id:
                url = f"https://artist.idus.com/product/{product_id}/global"
                logger.info(f"글로벌 페이지 이동: {url}")
                try:
                    await self.page.goto(url, timeout=30000)
                    await self.page.wait_for_load_state("domcontentloaded")
                except Exception as e:
                    logger.warning(f"goto 오류 (계속): {e}")
                await asyncio.sleep(3)  # SPA 렌더링 대기
            else:
                # product_id 없으면 탭 클릭으로 이동
                global_tab = self.page.locator(
                    '.BaseTabs__item:has-text("글로벌"), '
                    '.v-tab:has-text("글로벌")'
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
        """
        언어 서브탭 선택

        DOM: div.GlobalProductLanguageTab__item (--active / --inactive)
        텍스트: "일본어 ... 미등록" / "영어 미등록"
        """
        lang_text = "영어" if language == "en" else "일본어"
        try:
            # 확정된 셀렉터: GlobalProductLanguageTab__item 중 해당 언어 텍스트
            lang_tab = self.page.locator(
                f'.GlobalProductLanguageTab__item:has-text("{lang_text}")'
            ).first

            if await lang_tab.count() == 0:
                # 폴백: 모든 div에서 부분 매칭
                lang_tab = self.page.locator(
                    f'div:has-text("{lang_text}"):not(:has(div:has-text("{lang_text}")))'
                ).first

            if await lang_tab.count() == 0:
                logger.warning(f"'{lang_text}' 탭을 찾을 수 없습니다")
                return False

            await lang_tab.click()
            await asyncio.sleep(2)  # 탭 전환 + 폼 렌더링 대기
            logger.info(f"'{lang_text}' 탭 선택 완료")
            return True
        except Exception as e:
            logger.error(f"'{lang_text}' 탭 선택 실패: {e}")
            return False

    # ──────────────── 이미지 처리 ────────────────

    async def import_domestic_images(self) -> bool:
        """'국내 작품 이미지 불러오기' 실행"""
        try:
            # "등록 전 확인해 주세요." 패널 내부에 이미지 관련 기능이 있을 수 있음
            selectors = [
                'button:has-text("국내 작품 이미지 불러오기")',
                'text=국내 작품 이미지 불러오기',
                'button:has-text("이미지 불러오기")',
            ]
            for sel in selectors:
                btn = self.page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(2)
                    logger.info("국내 이미지 불러오기 완료")
                    return True

            logger.warning("국내 이미지 불러오기 버튼 없음 (건너뜀)")
            return False
        except Exception as e:
            logger.error(f"국내 이미지 불러오기 실패: {e}")
            return False

    # ──────────────── 필드 입력 ────────────────

    async def fill_title(self, title: str) -> bool:
        """작품명 입력 — textarea[name="globalProductName"]"""
        try:
            # 확정된 셀렉터
            title_input = self.page.locator(
                'textarea[name="globalProductName"]'
            ).first

            if await title_input.count() == 0:
                # 폴백: placeholder 기반
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
        """
        작품 설명 입력 — premiumDescription 블록 배열을 Vuex에 주입

        "작품 설명 작성하기" 버튼 클릭 → Vuex _detailUI.premiumDescription에 블록 배열 설정
        """
        try:
            # Vuex에 premiumDescription 블록 배열 직접 주입
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

    async def fill_description(self, description_html: str) -> bool:
        """작품 설명 입력 (HTML 방식 — 폴백용)"""
        try:
            # "작품 설명 작성하기" 버튼 클릭
            edit_btn = self.page.locator('button:has-text("작품 설명 작성하기")').first
            if await edit_btn.count() > 0:
                await edit_btn.click()
                await asyncio.sleep(1)

            # contenteditable 영역에 HTML 삽입
            editor = self.page.locator(
                '[contenteditable="true"], '
                '[class*="ql-editor"], '
                '[class*="ProseMirror"]'
            ).first
            if await editor.count() > 0:
                await editor.evaluate(
                    '(el, html) => { el.innerHTML = html; }',
                    description_html,
                )
                await editor.evaluate("""
                    (el) => {
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                """)
                logger.info("작품 설명 입력 완료 (contenteditable)")
                return True

            logger.warning("작품 설명 에디터를 찾을 수 없습니다")
            return False
        except Exception as e:
            logger.error(f"작품 설명 입력 실패: {e}")
            return False

    async def fill_keywords(self, keywords: list[str]) -> bool:
        """작품 키워드 입력 — 키워드 섹션 클릭 후 입력"""
        try:
            # 키워드 섹션의 '>' 화살표 또는 영역 클릭
            kw_section = self.page.locator(
                'text=작품 키워드'
            ).first
            if await kw_section.count() > 0:
                await kw_section.click()
                await asyncio.sleep(1)

            # 키워드 입력 필드 찾기
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
                await asyncio.sleep(300)

            logger.info(f"키워드 {len(keywords)}개 입력 완료")
            return True
        except Exception as e:
            logger.error(f"키워드 입력 실패: {e}")
            return False

    async def fill_global_options(
        self, options: list[GlobalOption], language: str,
    ) -> bool:
        """글로벌 옵션 입력 — "옵션 편집" 버튼 클릭 → 모달에서 입력"""
        try:
            edit_btn = self.page.locator('button:has-text("옵션 편집")').first
            if await edit_btn.count() == 0:
                logger.warning("옵션 편집 버튼을 찾을 수 없습니다")
                return False

            await edit_btn.click()
            await asyncio.sleep(1.5)

            # 모달 내에서 옵션 입력
            modal = self.page.locator('.v-dialog--active')
            if await modal.count() == 0:
                logger.warning("옵션 편집 모달이 열리지 않았습니다")
                return False

            for option in options:
                name = option.name_en if language == "en" else option.name_ja
                values = option.values_en if language == "en" else option.values_ja

                if not name or not values:
                    continue

                # 옵션명 입력
                name_input = modal.locator('input[name="productOptionName"]').first
                if await name_input.count() > 0:
                    await name_input.fill(name)

                # 옵션값 입력
                for val in values:
                    value_input = modal.locator('input[name="productOptionValue"]').last
                    if await value_input.count() > 0:
                        await value_input.fill(val)
                        await value_input.press('Enter')
                        await asyncio.sleep(300)

            # 저장/닫기
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
        """임시저장 — "일본어 임시저장" / "영어 임시저장" 버튼"""
        lang_text = "영어" if language == "en" else "일본어"
        try:
            draft_btn = self.page.locator(
                f'button:has-text("{lang_text} 임시저장")'
            ).first
            if await draft_btn.count() == 0:
                # 폴백: 일반 임시저장
                draft_btn = self.page.locator('button:has-text("임시저장")').first

            if await draft_btn.count() == 0:
                logger.warning("임시저장 버튼을 찾을 수 없습니다")
                return False

            await draft_btn.click()
            await asyncio.sleep(3)
            logger.info(f"{lang_text} 임시저장 완료")
            return True
        except Exception as e:
            logger.error(f"임시저장 실패: {e}")
            return False

    async def publish(self, language: str = "ja") -> bool:
        """판매 등록 — "일본어 작품 판매하기" / "영어 작품 판매하기" 버튼"""
        lang_text = "영어" if language == "en" else "일본어"
        try:
            publish_btn = self.page.locator(
                f'button:has-text("{lang_text} 작품 판매하기")'
            ).first
            if await publish_btn.count() == 0:
                publish_btn = self.page.locator('button:has-text("작품 판매하기")').first

            if await publish_btn.count() == 0:
                logger.warning("판매 등록 버튼을 찾을 수 없습니다")
                return False

            await publish_btn.click()
            await asyncio.sleep(3)
            logger.info(f"{lang_text} 판매 등록 완료")
            return True
        except Exception as e:
            logger.error(f"판매 등록 실패: {e}")
            return False

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

        # 2. 이미지 처리
        if use_domestic_images:
            await self.import_domestic_images()

        # 3. 작품명 입력
        await self.fill_title(data.title)

        # 4. 작품 설명 입력 (블록 배열 우선, HTML 폴백)
        if hasattr(data, 'description_blocks') and data.description_blocks:
            await self.fill_description_blocks(data.description_blocks)
        elif data.description_html:
            await self.fill_description(data.description_html)

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
    ) -> dict:
        """글로벌 탭 전체 등록 프로세스"""
        result = {
            "languages_success": [],
            "languages_failed": [],
        }

        # 글로벌 탭으로 이동 (URL 직접 이동)
        if not await self.navigate_to_global_tab(product_id):
            result["languages_failed"] = ["en", "ja"]
            return result

        # 일본어 등록 (기본 탭이므로 먼저)
        if global_data.ja:
            success = await self.fill_language_data(
                language="ja",
                data=global_data.ja,
                global_options=global_data.global_options,
            )
            if success:
                if save_as_draft:
                    await self.save_draft("ja")
                else:
                    await self.publish("ja")
                result["languages_success"].append("ja")
            else:
                result["languages_failed"].append("ja")

        # 영어 등록
        if global_data.en:
            success = await self.fill_language_data(
                language="en",
                data=global_data.en,
                global_options=global_data.global_options,
            )
            if success:
                if save_as_draft:
                    await self.save_draft("en")
                else:
                    await self.publish("en")
                result["languages_success"].append("en")
            else:
                result["languages_failed"].append("en")

        return result
