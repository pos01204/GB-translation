"""
작가웹 국내 탭 데이터 추출 서비스

작가웹의 작품 수정 페이지(국내 탭)에서
제목, 가격, 이미지, 설명, 옵션, 키워드 등 전체 데이터를 추출합니다.
"""
import asyncio
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
        # SPA 콘텐츠 로딩 대기 — 이미지/폼 요소가 렌더링될 때까지
        await self._wait_for_content_ready()

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

    async def _wait_for_content_ready(self):
        """SPA 페이지의 콘텐츠가 완전히 렌더링될 때까지 대기"""
        # 1단계: 기본 폼 요소 대기
        try:
            await self.page.wait_for_selector(
                'input, textarea, [contenteditable]',
                timeout=15000,
            )
        except Exception:
            logger.warning("폼 요소 대기 타임아웃")

        # 2단계: 이미지 요소 대기 (idus 이미지)
        try:
            await self.page.wait_for_selector(
                'img[src*="idus"], img[src*="image."], img[data-src]',
                timeout=10000,
            )
        except Exception:
            logger.debug("이미지 요소 대기 타임아웃 (이미지 없는 작품일 수 있음)")

        # 3단계: 추가 렌더링 대기
        await asyncio.sleep(2)

        # 디버깅: 현재 페이지 상태 로깅
        try:
            page_state = await self.page.evaluate("""
                () => ({
                    url: window.location.href,
                    imgCount: document.querySelectorAll('img').length,
                    idusImgCount: document.querySelectorAll('img[src*="idus"], img[src*="image."]').length,
                    inputCount: document.querySelectorAll('input').length,
                    textareaCount: document.querySelectorAll('textarea').length,
                    formCount: document.querySelectorAll('form').length,
                })
            """)
            logger.info(f"페이지 콘텐츠 상태: {page_state}")
        except Exception:
            pass

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
                    await asyncio.sleep(1)  # 탭 전환 후 렌더링 대기
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
            # JavaScript로 이미지 추출 (더 넓은 범위의 셀렉터 사용)
            images_data = await self.page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();

                    // 1. idus 이미지 서버의 모든 img 태그
                    const imgSelectors = [
                        'img[src*="image.idus.com"]',
                        'img[src*="idus-file"]',
                        'img[src*="idus"]',
                        'img[src*="cloudfront"]',
                    ];

                    for (const selector of imgSelectors) {
                        const imgs = document.querySelectorAll(selector);
                        for (const img of imgs) {
                            const src = img.src || img.dataset?.src || img.getAttribute('data-src') || '';
                            if (!src || seen.has(src)) continue;
                            // 아이콘/로고/썸네일 필터링
                            if (src.includes('logo') || src.includes('icon')) continue;
                            // 너무 작은 이미지 제외 (아이콘일 가능성)
                            const w = img.naturalWidth || img.width || 0;
                            const h = img.naturalHeight || img.height || 0;
                            if (w > 0 && w < 50 && h > 0 && h < 50) continue;
                            seen.add(src);
                            results.push(src);
                        }
                    }

                    // 2. background-image에서 idus 이미지 추출
                    const allEls = document.querySelectorAll('[style*="background-image"]');
                    for (const el of allEls) {
                        const style = el.getAttribute('style') || '';
                        const match = style.match(/url\\(['"]?(https?:\\/\\/[^'"\\)]*idus[^'"\\)]*)/);
                        if (match && !seen.has(match[1])) {
                            seen.add(match[1]);
                            results.push(match[1]);
                        }
                    }

                    return results;
                }
            """)

            for i, src in enumerate(images_data[:9]):  # 최대 9장
                images.append(ProductImage(
                    url=src,
                    order=i,
                    is_representative=(i == 0),
                ))

            if not images:
                # 디버깅: 페이지의 모든 이미지 정보 로깅
                debug_info = await self.page.evaluate("""
                    () => {
                        const allImgs = document.querySelectorAll('img');
                        return Array.from(allImgs).slice(0, 20).map(img => ({
                            src: (img.src || '').substring(0, 120),
                            dataSrc: (img.dataset?.src || '').substring(0, 120),
                            width: img.width,
                            height: img.height,
                            alt: img.alt || '',
                        }));
                    }
                """)
                logger.warning(f"이미지 0건. 페이지 내 img 태그 샘플: {debug_info}")

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
            # JavaScript로 옵션 데이터 추출 — 여러 전략 시도
            options_data = await self.page.evaluate("""
                () => {
                    const result = [];

                    // 전략 1: 옵션 섹션 내 input 필드에서 추출
                    const optionSections = document.querySelectorAll(
                        '[class*="option"], [class*="Option"]'
                    );
                    for (const section of optionSections) {
                        const nameEl = section.querySelector(
                            'input[placeholder*="옵션명"], [class*="name"] input, input[placeholder*="옵션"]'
                        );
                        if (!nameEl) continue;
                        const name = nameEl.value;
                        if (!name) continue;

                        const values = [];
                        const valueEls = section.querySelectorAll(
                            '[class*="value"] input, [class*="item"] input, [class*="chip"], [class*="tag"]'
                        );
                        for (const valEl of valueEls) {
                            const val = valEl.value || valEl.textContent?.trim();
                            if (val && val !== name && val !== 'x' && val !== '×') {
                                values.push({
                                    value: val,
                                    additional_price: 0,
                                });
                            }
                        }

                        if (values.length > 0) {
                            result.push({ name, values, option_type: "basic" });
                        }
                    }

                    if (result.length > 0) return result;

                    // 전략 2: "옵션" 텍스트 라벨 근처의 input/select 요소
                    const labels = document.querySelectorAll('label, div, span, p');
                    for (const label of labels) {
                        const text = label.textContent?.trim();
                        if (!text || !text.includes('옵션') || text.length > 30) continue;

                        // 형제 또는 부모 컨테이너에서 input 탐색
                        const container = label.closest('[class*="option"], [class*="Option"], [class*="row"], [class*="group"]')
                            || label.parentElement;
                        if (!container) continue;

                        const inputs = container.querySelectorAll('input:not([type="hidden"]), select');
                        for (const input of inputs) {
                            const val = input.value;
                            if (val) {
                                result.push({
                                    name: text.replace(/[:\\s]*$/, ''),
                                    values: [{ value: val, additional_price: 0 }],
                                    option_type: "basic",
                                });
                                break;
                            }
                        }
                    }

                    // 전략 3: 페이지의 모든 input에서 옵션 관련 필드 탐색
                    if (result.length === 0) {
                        const allInputs = document.querySelectorAll('input');
                        for (const input of allInputs) {
                            const placeholder = input.placeholder || '';
                            const name = input.name || '';
                            if ((placeholder + name).toLowerCase().includes('option') ||
                                (placeholder + name).includes('옵션')) {
                                if (input.value) {
                                    result.push({
                                        name: placeholder || name || '옵션',
                                        values: [{ value: input.value, additional_price: 0 }],
                                        option_type: "basic",
                                    });
                                }
                            }
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

            if not options:
                # 디버깅: 옵션 관련 DOM 정보 로깅
                debug_info = await self.page.evaluate("""
                    () => {
                        const optionEls = document.querySelectorAll('[class*="option"], [class*="Option"]');
                        return {
                            optionElementCount: optionEls.length,
                            samples: Array.from(optionEls).slice(0, 5).map(el => ({
                                tag: el.tagName,
                                classes: el.className?.toString().substring(0, 100),
                                inputCount: el.querySelectorAll('input').length,
                                text: el.textContent?.trim().substring(0, 100),
                            })),
                        };
                    }
                """)
                logger.info(f"옵션 0건. DOM 옵션 요소 정보: {debug_info}")

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
