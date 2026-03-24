"""
작가웹 국내 탭 데이터 추출 서비스

작가웹의 작품 수정 페이지(국내 탭)에서
제목, 가격, 이미지, 설명, 옵션, 키워드 등 전체 데이터를 추출합니다.
"""
import re
import logging
from typing import Optional
from playwright.async_api import Page
from ..models.domestic import (
    DomesticProduct, ProductImage, DomesticOption, OptionValue,
    ProductStatus, GlobalStatus,
)
from ..config import settings

logger = logging.getLogger(__name__)

# 글로벌 판매 제한 카테고리
RESTRICTED_CATEGORIES = [
    "식품", "가구", "식물", "디퓨저",
    "14k", "18k", "24k",
]


class ProductReader:
    """작가웹 국내 탭 데이터 추출기

    전제: 이미 /product/{product_id} 페이지에 위치한 상태에서 호출됩니다.
    ArtistWebSession.navigate_to_product() 호출 후 사용하세요.
    """

    def __init__(self, page: Page):
        self.page = page

    async def read_domestic_data(self, product_id: str) -> DomesticProduct:
        """
        국내 탭 전체 데이터 추출

        전제: 이미 /product/{product_id} 페이지에 위치
        국내 탭이 기본 선택 상태여야 함
        """
        # 국내 탭 활성화 확인
        await self._ensure_domestic_tab()

        # 각 필드 추출 (순차 — 페이지 상태 의존)
        title = await self._read_title()
        price = await self._read_price()
        quantity = await self._read_quantity()
        is_made_to_order = await self._read_made_to_order()
        category_path = await self._read_category()
        images = await self._read_images()
        intro = await self._read_intro()
        features = await self._read_features()
        process_steps = await self._read_process_steps()
        description_html = await self._read_description()
        options = await self._read_options()
        keywords = await self._read_keywords()
        gift_wrapping = await self._read_gift_wrapping()

        # 글로벌 판매 제한 카테고리 확인
        category_restricted = any(
            keyword in category_path for keyword in RESTRICTED_CATEGORIES
        )

        # 글로벌 상태 확인
        global_status = await self._read_global_status()

        product = DomesticProduct(
            product_id=product_id,
            product_url=self.page.url,
            title=title,
            price=price,
            quantity=quantity,
            is_made_to_order=is_made_to_order,
            category_path=category_path,
            category_restricted=category_restricted,
            product_images=images,
            intro=intro,
            features=features,
            process_steps=process_steps,
            description_html=description_html,
            options=options,
            keywords=keywords,
            gift_wrapping=gift_wrapping,
            global_status=global_status,
        )

        logger.info(
            f"국내 데이터 추출 완료: {product_id} "
            f"(제목={title[:20]}..., 이미지={len(images)}, 옵션={len(options)})"
        )
        return product

    # ──────────────────── Private Methods ────────────────────

    async def _ensure_domestic_tab(self):
        """국내 탭이 활성화되어 있는지 확인하고, 아니면 클릭"""
        try:
            domestic_tab = self.page.locator(
                'button:has-text("국내"), [role="tab"]:has-text("국내"), a:has-text("국내")'
            ).first
            if await domestic_tab.count() > 0:
                # 이미 활성화되어 있는지 확인
                is_active = await domestic_tab.get_attribute("aria-selected")
                data_state = await domestic_tab.get_attribute("data-state")
                if is_active != "true" and data_state != "active":
                    await domestic_tab.click()
                    await self.page.wait_for_timeout(settings.artist_web_navigation_delay)
                    logger.info("국내 탭 활성화")
        except Exception as e:
            logger.warning(f"국내 탭 전환 시도 중 오류 (무시): {e}")

    async def _read_title(self) -> str:
        """작품명 추출"""
        try:
            # 다양한 셀렉터 시도
            selectors = [
                'textarea[placeholder*="작품명"]',
                'input[placeholder*="작품명"]',
                'input[name*="title"]',
                'textarea[name*="title"]',
            ]
            for sel in selectors:
                el = self.page.locator(sel).first
                if await el.count() > 0:
                    value = await el.input_value()
                    if value:
                        return value.strip()
        except Exception as e:
            logger.warning(f"작품명 추출 실패: {e}")
        return ""

    async def _read_price(self) -> int:
        """가격 추출"""
        try:
            # 가격 관련 input 필드
            price_input = self.page.locator(
                'input[name*="price"], input[placeholder*="가격"]'
            ).first
            if await price_input.count() > 0:
                val = await price_input.input_value()
                return int(re.sub(r'[^\d]', '', val)) if val else 0
        except Exception as e:
            logger.warning(f"가격 추출 실패: {e}")
        return 0

    async def _read_quantity(self) -> int:
        """수량 추출"""
        try:
            # "수량" 라벨 인접 input
            quantity_section = self.page.locator(
                'label:has-text("수량"), div:has-text("수량")'
            ).first.locator('..')
            qty_input = quantity_section.locator('input').first
            if await qty_input.count() > 0:
                val = await qty_input.input_value()
                return int(re.sub(r'[^\d]', '', val)) if val else 0
        except Exception as e:
            logger.warning(f"수량 추출 실패: {e}")
        return 0

    async def _read_made_to_order(self) -> bool:
        """주문 시 제작 여부"""
        try:
            checkbox = self.page.locator(
                'input[type="checkbox"]'
            ).filter(has=self.page.locator('text=주문 시 제작'))
            if await checkbox.count() > 0:
                return await checkbox.is_checked()

            # 대안: 체크박스 라벨 탐색
            label = self.page.locator('label:has-text("주문 시 제작")')
            if await label.count() > 0:
                cb = label.locator('input[type="checkbox"]')
                if await cb.count() > 0:
                    return await cb.is_checked()
        except Exception as e:
            logger.warning(f"주문제작 여부 추출 실패: {e}")
        return False

    async def _read_category(self) -> str:
        """카테고리 경로 추출"""
        try:
            # 카테고리 영역에서 '>' 포함 텍스트 찾기
            category_el = self.page.locator(
                '[class*="category"], [class*="Category"]'
            ).filter(has_text=re.compile(r'>'))
            if await category_el.count() > 0:
                return (await category_el.first.inner_text()).strip()

            # 대안: 전체 페이지에서 카테고리 패턴 탐색
            all_text = await self.page.evaluate("""
                () => {
                    const els = document.querySelectorAll('p, span, div');
                    for (const el of els) {
                        const text = el.textContent.trim();
                        if (text.includes('>') && text.length < 100
                            && (text.includes('/') || text.includes('케이스')
                                || text.includes('액세서리'))) {
                            return text;
                        }
                    }
                    return '';
                }
            """)
            return all_text
        except Exception as e:
            logger.warning(f"카테고리 추출 실패: {e}")
        return ""

    async def _read_images(self) -> list[ProductImage]:
        """작품 이미지 URL 및 순서 추출"""
        images = []
        try:
            img_elements = self.page.locator(
                'img[src*="image.idus.com"], img[src*="idus-file"]'
            )
            count = await img_elements.count()
            for i in range(min(count, 9)):  # 최대 9장
                src = await img_elements.nth(i).get_attribute('src')
                if src and 'thumbnail' not in src.lower():
                    images.append(ProductImage(
                        url=src,
                        order=i,
                        is_representative=(i == 0),
                    ))
        except Exception as e:
            logger.warning(f"이미지 추출 실패: {e}")
        return images

    async def _read_intro(self) -> Optional[str]:
        """작품 인트로 추출"""
        try:
            intro_input = self.page.locator(
                'textarea[placeholder*="작품을 한 줄로"], textarea[placeholder*="인트로"]'
            ).first
            if await intro_input.count() > 0:
                val = await intro_input.input_value()
                return val.strip() if val else None
        except Exception as e:
            logger.warning(f"인트로 추출 실패: {e}")
        return None

    async def _read_features(self) -> list[str]:
        """특장점 추출"""
        features = []
        try:
            # 특장점 섹션 내 항목들
            feature_section = self.page.locator(
                'section:has-text("특장점"), div:has-text("특장점")'
            ).first
            if await feature_section.count() > 0:
                items = feature_section.locator(
                    '[class*="item"], [class*="feature"], li'
                )
                count = await items.count()
                for i in range(count):
                    text = (await items.nth(i).inner_text()).strip()
                    if text and text != "특장점":
                        features.append(text)
        except Exception as e:
            logger.warning(f"특장점 추출 실패: {e}")
        return features

    async def _read_process_steps(self) -> list[str]:
        """제작과정 추출"""
        steps = []
        try:
            process_section = self.page.locator(
                'section:has-text("제작과정"), div:has-text("제작과정")'
            ).first
            if await process_section.count() > 0:
                items = process_section.locator(
                    '[class*="item"], [class*="step"], li'
                )
                count = await items.count()
                for i in range(count):
                    text = (await items.nth(i).inner_text()).strip()
                    if text and text != "제작과정":
                        steps.append(text)
        except Exception as e:
            logger.warning(f"제작과정 추출 실패: {e}")
        return steps

    async def _read_description(self) -> str:
        """작품 설명 HTML 추출"""
        try:
            # 에디터 콘텐츠 영역
            selectors = [
                '[contenteditable="true"]',
                '[class*="editor"] [class*="content"]',
                '[class*="ql-editor"]',           # Quill editor
                '[class*="ProseMirror"]',          # ProseMirror
                '[class*="tiptap"]',               # Tiptap
                'section:has-text("작품 설명") [class*="content"]',
            ]
            for sel in selectors:
                el = self.page.locator(sel).first
                if await el.count() > 0:
                    html = await el.inner_html()
                    if html and len(html) > 10:
                        return html
        except Exception as e:
            logger.warning(f"작품 설명 추출 실패: {e}")
        return ""

    async def _read_options(self) -> list[DomesticOption]:
        """옵션 목록 추출"""
        options = []
        try:
            # JavaScript로 옵션 데이터 추출 (DOM 구조 의존도를 낮추기 위해)
            options_data = await self.page.evaluate("""
                () => {
                    const result = [];
                    // 옵션 그룹 찾기
                    const optionSections = document.querySelectorAll(
                        '[class*="option"], [class*="Option"]'
                    );
                    for (const section of optionSections) {
                        const nameEl = section.querySelector(
                            'input[placeholder*="옵션명"], [class*="name"] input'
                        );
                        if (!nameEl) continue;
                        const name = nameEl.value;
                        if (!name) continue;

                        // 옵션값 목록
                        const values = [];
                        const valueEls = section.querySelectorAll(
                            '[class*="value"] input, [class*="item"] input'
                        );
                        for (const valEl of valueEls) {
                            if (valEl.value) {
                                values.push({
                                    value: valEl.value,
                                    additional_price: 0,
                                });
                            }
                        }

                        if (values.length > 0) {
                            result.push({ name, values, option_type: "basic" });
                        }
                    }
                    return result;
                }
            """)

            for opt_data in options_data:
                options.append(DomesticOption(
                    name=opt_data["name"],
                    values=[
                        OptionValue(
                            value=v["value"],
                            additional_price=v.get("additional_price", 0),
                        )
                        for v in opt_data["values"]
                    ],
                    option_type=opt_data.get("option_type", "basic"),
                ))
        except Exception as e:
            logger.warning(f"옵션 추출 실패: {e}")
        return options

    async def _read_keywords(self) -> list[str]:
        """키워드 추출"""
        try:
            keywords_data = await self.page.evaluate("""
                () => {
                    // 키워드 태그 요소 또는 키워드 입력 필드
                    const tags = document.querySelectorAll(
                        '[class*="keyword"] [class*="tag"], [class*="keyword"] span, [class*="chip"]'
                    );
                    if (tags.length > 0) {
                        return Array.from(tags)
                            .map(t => t.textContent.trim())
                            .filter(t => t && t !== 'x' && t !== '×');
                    }

                    // 키워드 input 필드
                    const input = document.querySelector(
                        'input[placeholder*="키워드"], input[name*="keyword"]'
                    );
                    if (input && input.value) {
                        return input.value.split(',').map(k => k.trim()).filter(Boolean);
                    }

                    return [];
                }
            """)
            return keywords_data
        except Exception as e:
            logger.warning(f"키워드 추출 실패: {e}")
        return []

    async def _read_gift_wrapping(self) -> bool:
        """선물 포장 제공 여부"""
        try:
            checkbox = self.page.locator('label:has-text("선물 포장")').locator(
                'input[type="checkbox"]'
            )
            if await checkbox.count() > 0:
                return await checkbox.is_checked()
        except Exception as e:
            logger.warning(f"선물 포장 여부 추출 실패: {e}")
        return False

    async def _read_global_status(self) -> GlobalStatus:
        """글로벌 등록 상태 확인"""
        try:
            # 글로벌 탭 클릭해서 상태 확인 후 다시 국내 탭으로 복귀
            global_tab = self.page.locator(
                'button:has-text("글로벌"), [role="tab"]:has-text("글로벌"), a:has-text("글로벌")'
            ).first
            if await global_tab.count() > 0:
                # 글로벌 탭에 뱃지나 상태 표시가 있는지 확인
                badge = global_tab.locator('[class*="badge"], [class*="count"]')
                if await badge.count() > 0:
                    return GlobalStatus.REGISTERED

                # 글로벌 탭 텍스트에서 상태 추론
                tab_text = await global_tab.inner_text()
                if "등록" in tab_text or "판매" in tab_text:
                    return GlobalStatus.REGISTERED
        except Exception as e:
            logger.warning(f"글로벌 상태 확인 실패: {e}")

        return GlobalStatus.NOT_REGISTERED
