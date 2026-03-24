"""
작가웹 글로벌 탭 자동 입력 서비스

번역 결과(GlobalProductData)를 작가웹의 글로벌 탭 폼에
실제로 입력하는 핵심 모듈입니다.

흐름:
1. 글로벌 탭 이동
2. 언어 서브탭 선택 (영어/일본어)
3. 국내 이미지 불러오기
4. 작품명 입력
5. 작품 설명 입력 (HTML 에디터)
6. 키워드 입력
7. 옵션 입력
8. 임시저장 또는 판매 등록
"""
import asyncio
import logging
from typing import Optional
from playwright.async_api import Page
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..config import settings

logger = logging.getLogger(__name__)


class ProductWriter:
    """작가웹 글로벌 탭 데이터 입력기

    전제: ArtistWebSession으로 이미 로그인되어 있고,
    navigate_to_product()로 작품 페이지에 위치한 상태에서 사용합니다.
    """

    def __init__(self, page: Page):
        self.page = page

    # ──────────────── 탭 네비게이션 ────────────────

    async def navigate_to_global_tab(self) -> bool:
        """글로벌 탭으로 이동 (현재 /product/{id} 페이지에 위치해야 함)"""
        try:
            global_tab = self.page.locator(
                'button:has-text("글로벌"), [role="tab"]:has-text("글로벌"), a:has-text("글로벌")'
            ).first
            if await global_tab.count() == 0:
                logger.warning("글로벌 탭을 찾을 수 없습니다")
                return False

            await global_tab.click()
            await self.page.wait_for_timeout(settings.artist_web_navigation_delay)
            logger.info("글로벌 탭 이동 완료")
            return True
        except Exception as e:
            logger.error(f"글로벌 탭 이동 실패: {e}")
            return False

    async def select_language_tab(self, language: str) -> bool:
        """
        언어 서브탭 선택

        Args:
            language: "en" (영어) 또는 "ja" (일본어)
        """
        lang_text = "영어" if language == "en" else "일본어"
        try:
            lang_tab = self.page.locator(
                f'button:has-text("{lang_text}"), '
                f'[role="tab"]:has-text("{lang_text}"), '
                f'a:has-text("{lang_text}")'
            ).first
            if await lang_tab.count() == 0:
                logger.warning(f"'{lang_text}' 탭을 찾을 수 없습니다")
                return False

            await lang_tab.click()
            await self.page.wait_for_timeout(settings.artist_web_navigation_delay)
            logger.info(f"'{lang_text}' 탭 선택 완료")
            return True
        except Exception as e:
            logger.error(f"'{lang_text}' 탭 선택 실패: {e}")
            return False

    # ──────────────── 이미지 처리 ────────────────

    async def import_domestic_images(self) -> bool:
        """'국내 작품 이미지 불러오기' 실행"""
        try:
            # 여러 가능한 셀렉터 시도
            selectors = [
                'button:has-text("국내 작품 이미지 불러오기")',
                'text=국내 작품 이미지 불러오기',
                'button:has-text("이미지 불러오기")',
            ]
            for sel in selectors:
                btn = self.page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await self.page.wait_for_timeout(2000)  # 이미지 로딩 대기
                    logger.info("국내 이미지 불러오기 완료")
                    return True

            # 드롭다운 내부에 있을 수 있음
            dropdown = self.page.locator(
                'button:has-text("등록 전 확인"), [class*="dropdown"]'
            ).first
            if await dropdown.count() > 0:
                await dropdown.click()
                await self.page.wait_for_timeout(500)
                import_option = self.page.locator('text=국내 작품 이미지 불러오기').first
                if await import_option.count() > 0:
                    await import_option.click()
                    await self.page.wait_for_timeout(2000)
                    logger.info("드롭다운에서 국내 이미지 불러오기 완료")
                    return True

            logger.warning("국내 이미지 불러오기 버튼을 찾을 수 없습니다")
            return False
        except Exception as e:
            logger.error(f"국내 이미지 불러오기 실패: {e}")
            return False

    # ──────────────── 필드 입력 ────────────────

    async def fill_title(self, title: str) -> bool:
        """작품명 입력 (80자 제한)"""
        try:
            title_input = self.page.locator(
                'textarea[placeholder*="입력해 주세요"], '
                'input[placeholder*="입력해 주세요"], '
                'textarea[name*="title"], '
                'input[name*="title"]'
            ).first

            if await title_input.count() == 0:
                logger.warning("작품명 입력 필드를 찾을 수 없습니다")
                return False

            truncated = title[:settings.title_max_length_global]
            await title_input.click()
            await title_input.fill("")
            await title_input.type(truncated, delay=settings.artist_web_input_delay)
            logger.info(f"작품명 입력 완료: {truncated[:30]}...")
            return True
        except Exception as e:
            logger.error(f"작품명 입력 실패: {e}")
            return False

    async def fill_description(self, description_html: str) -> bool:
        """
        작품 설명 입력 (HTML 에디터)

        방법 1: contenteditable 요소에 직접 innerHTML 설정
        방법 2: 에디터 버튼 클릭 후 textarea에 입력
        """
        try:
            # "작품 설명 작성하기" 버튼이 있으면 먼저 클릭
            edit_btn = self.page.locator('button:has-text("작품 설명 작성하기")').first
            if await edit_btn.count() > 0:
                await edit_btn.click()
                await self.page.wait_for_timeout(1000)

            # 방법 1: contenteditable 영역
            editor = self.page.locator(
                '[contenteditable="true"], '
                '[class*="ql-editor"], '
                '[class*="ProseMirror"], '
                '[class*="tiptap"]'
            ).first
            if await editor.count() > 0:
                await editor.evaluate(
                    '(el, html) => { el.innerHTML = html; }',
                    description_html,
                )
                # 변경 이벤트 트리거 (프레임워크가 변경을 감지하도록)
                await editor.evaluate("""
                    (el) => {
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                """)
                logger.info("작품 설명 입력 완료 (contenteditable)")
                return True

            # 방법 2: textarea
            textarea = self.page.locator(
                'textarea[class*="description"], textarea[name*="description"]'
            ).first
            if await textarea.count() > 0:
                await textarea.fill(description_html)
                logger.info("작품 설명 입력 완료 (textarea)")
                return True

            logger.warning("작품 설명 에디터를 찾을 수 없습니다")
            return False
        except Exception as e:
            logger.error(f"작품 설명 입력 실패: {e}")
            return False

    async def fill_keywords(self, keywords: list[str]) -> bool:
        """작품 키워드 입력 (하나씩 Enter로 추가)"""
        try:
            keyword_input = self.page.locator(
                'input[placeholder*="키워드"], '
                'input[name*="keyword"], '
                'input[placeholder*="태그"]'
            ).first

            if await keyword_input.count() == 0:
                # 키워드 섹션 내부 탐색
                section = self.page.locator(
                    'section:has-text("키워드"), div:has-text("작품 키워드")'
                ).first
                if await section.count() > 0:
                    keyword_input = section.locator('input').first

            if await keyword_input.count() == 0:
                logger.warning("키워드 입력 필드를 찾을 수 없습니다")
                return False

            for keyword in keywords:
                await keyword_input.fill(keyword)
                await keyword_input.press('Enter')
                await self.page.wait_for_timeout(300)

            logger.info(f"키워드 {len(keywords)}개 입력 완료")
            return True
        except Exception as e:
            logger.error(f"키워드 입력 실패: {e}")
            return False

    async def fill_global_options(
        self, options: list[GlobalOption], language: str,
    ) -> bool:
        """
        글로벌 옵션 입력

        Args:
            options: 번역된 글로벌 옵션 목록
            language: "en" 또는 "ja" (해당 언어 값 사용)
        """
        try:
            # 옵션 편집 버튼 클릭
            edit_btn = self.page.locator(
                'button:has-text("옵션 편집"), button:has-text("옵션")'
            ).first
            if await edit_btn.count() == 0:
                logger.warning("옵션 편집 버튼을 찾을 수 없습니다")
                return False

            await edit_btn.click()
            await self.page.wait_for_timeout(1000)

            for option in options:
                # 옵션명
                name = option.name_en if language == "en" else option.name_ja
                values = option.values_en if language == "en" else option.values_ja

                if not name or not values:
                    continue

                # 추가 버튼 클릭
                add_btn = self.page.locator('button:has-text("추가")').first
                if await add_btn.count() > 0:
                    await add_btn.click()
                    await self.page.wait_for_timeout(500)

                # 옵션명 입력
                option_name_input = self.page.locator(
                    'input[placeholder*="옵션명"]'
                ).last
                if await option_name_input.count() > 0:
                    await option_name_input.fill(name)

                # 옵션값 입력 (하나씩)
                option_value_input = self.page.locator(
                    'input[placeholder*="옵션값"], input[placeholder*="추가"]'
                ).last
                if await option_value_input.count() > 0:
                    for val in values:
                        await option_value_input.fill(val)
                        await option_value_input.press('Enter')
                        await self.page.wait_for_timeout(200)

            # 적용 버튼 클릭
            apply_btn = self.page.locator(
                'button:has-text("적용"), button:has-text("확인")'
            ).first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                await self.page.wait_for_timeout(1000)

            logger.info(f"옵션 {len(options)}개 입력 완료 ({language})")
            return True
        except Exception as e:
            logger.error(f"옵션 입력 실패: {e}")
            return False

    # ──────────────── 저장/등록 ────────────────

    async def save_draft(self) -> bool:
        """임시저장"""
        try:
            draft_btn = self.page.locator(
                'button:has-text("임시저장")'
            ).first
            if await draft_btn.count() == 0:
                logger.warning("임시저장 버튼을 찾을 수 없습니다")
                return False

            await draft_btn.click()
            await self.page.wait_for_timeout(2000)
            logger.info("임시저장 완료")
            return True
        except Exception as e:
            logger.error(f"임시저장 실패: {e}")
            return False

    async def publish(self) -> bool:
        """판매 등록 — '작품 판매하기' 버튼 클릭"""
        try:
            publish_btn = self.page.locator(
                'button:has-text("작품 판매하기"), button:has-text("판매 등록")'
            ).first
            if await publish_btn.count() == 0:
                logger.warning("판매 등록 버튼을 찾을 수 없습니다")
                return False

            await publish_btn.click()
            await self.page.wait_for_timeout(3000)
            logger.info("판매 등록 완료")
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
        """
        특정 언어 탭의 전체 데이터 입력 (통합 메서드)

        Args:
            language: "en" 또는 "ja"
            data: 해당 언어의 등록 데이터
            global_options: 옵션 데이터 (양 언어 공용)
            use_domestic_images: 국내 이미지 불러오기 사용 여부
        """
        logger.info(f"{'영어' if language == 'en' else '일본어'} 데이터 입력 시작")

        # 1. 언어 탭 선택
        if not await self.select_language_tab(language):
            return False

        # 2. 이미지 처리
        if use_domestic_images:
            await self.import_domestic_images()

        # 3. 작품명 입력
        await self.fill_title(data.title)

        # 4. 작품 설명 입력
        if data.description_html:
            await self.fill_description(data.description_html)

        # 5. 키워드 입력
        if data.keywords:
            await self.fill_keywords(data.keywords)

        # 6. 옵션 입력
        if global_options:
            await self.fill_global_options(global_options, language)

        logger.info(f"{'영어' if language == 'en' else '일본어'} 데이터 입력 완료")
        return True

    async def register_global_product(
        self,
        global_data: GlobalProductData,
        save_as_draft: bool = True,
    ) -> dict:
        """
        글로벌 탭 전체 등록 프로세스 실행

        Args:
            global_data: 번역된 글로벌 등록 데이터
            save_as_draft: True면 임시저장, False면 판매 등록

        Returns:
            결과 dict (languages_success, languages_failed)
        """
        result = {
            "languages_success": [],
            "languages_failed": [],
        }

        # 글로벌 탭으로 이동
        if not await self.navigate_to_global_tab():
            result["languages_failed"] = ["en", "ja"]
            return result

        # 영어 등록
        if global_data.en:
            success = await self.fill_language_data(
                language="en",
                data=global_data.en,
                global_options=global_data.global_options,
            )
            if success:
                if save_as_draft:
                    await self.save_draft()
                else:
                    await self.publish()
                result["languages_success"].append("en")
            else:
                result["languages_failed"].append("en")

        # 일본어 등록
        if global_data.ja:
            success = await self.fill_language_data(
                language="ja",
                data=global_data.ja,
                global_options=global_data.global_options,
            )
            if success:
                if save_as_draft:
                    await self.save_draft()
                else:
                    await self.publish()
                result["languages_success"].append("ja")
            else:
                result["languages_failed"].append("ja")

        return result
