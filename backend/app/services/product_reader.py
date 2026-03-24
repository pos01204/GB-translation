"""
작가웹 국내 탭 데이터 추출 서비스

작가웹의 작품 수정 페이지(국내 탭)에서
제목, 가격, 이미지, 설명, 옵션, 키워드 등 전체 데이터를 추출합니다.

핵심: "작품 설명" 섹션의 "수정하기" 버튼을 클릭하여
상세 이미지, HTML 설명, 특장점 등 전체 콘텐츠를 노출시킨 뒤 추출합니다.
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

# 이미지 필터링용 패턴
_IMAGE_EXCLUDE_PATTERNS = re.compile(
    r'logo|icon|profile|avatar|10x10|favicon|placeholder|spinner',
    re.IGNORECASE,
)


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

        # 디버그: 모든 input/textarea 필드 덤프
        await self._dump_input_fields()

        # "작품 설명" 섹션의 "수정하기" 버튼 클릭 → 상세 에디터 노출
        await self._open_description_editor()

        # 각 필드 추출 (순차 — 페이지 상태 의존)
        title = await self._read_title()
        price = await self._read_price()
        quantity = await self._read_quantity(price)
        is_made_to_order = await self._read_made_to_order()
        category_path = await self._read_category()
        product_images = await self._read_product_images()
        detail_images = await self._read_detail_images()
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
            product_images=product_images,
            detail_images=detail_images,
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
            f"(제목={title[:20] if title else ''}..., "
            f"작품이미지={len(product_images)}, "
            f"상세이미지={len(detail_images)}, "
            f"옵션={len(options)})"
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

        # 3단계: Vue/Vuetify 앱 렌더링 대기
        try:
            await self.page.wait_for_selector(
                '.v-application--wrap, .v-application, [data-app]',
                timeout=5000,
            )
            logger.debug("Vuetify 앱 컨테이너 감지됨")
        except Exception:
            logger.debug("Vuetify 앱 컨테이너 미감지 (비-Vuetify 레이아웃일 수 있음)")

        # 4단계: 추가 렌더링 대기
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
                    vuetifyInputCount: document.querySelectorAll('.v-input, .v-text-field').length,
                    buttonCount: document.querySelectorAll('button').length,
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

    async def _dump_input_fields(self):
        """디버그: 페이지의 모든 input/textarea 필드 정보 덤프"""
        try:
            fields_info = await self.page.evaluate("""
                () => {
                    const results = [];
                    const inputs = document.querySelectorAll('input, textarea');
                    for (const el of inputs) {
                        // 가장 가까운 label 텍스트 찾기
                        let labelText = '';
                        // 1) for 속성 기반 label
                        if (el.id) {
                            const lbl = document.querySelector('label[for="' + el.id + '"]');
                            if (lbl) labelText = lbl.textContent.trim();
                        }
                        // 2) 부모 .v-input 내 label
                        if (!labelText) {
                            const vInput = el.closest('.v-input, .v-text-field');
                            if (vInput) {
                                const lbl = vInput.querySelector('label, .v-label');
                                if (lbl) labelText = lbl.textContent.trim();
                            }
                        }
                        // 3) 가장 가까운 부모의 label
                        if (!labelText) {
                            const parent = el.closest('.form-group, .field, [class*="field"]');
                            if (parent) {
                                const lbl = parent.querySelector('label');
                                if (lbl) labelText = lbl.textContent.trim();
                            }
                        }

                        results.push({
                            tag: el.tagName.toLowerCase(),
                            type: el.type || '',
                            name: el.name || '',
                            placeholder: (el.placeholder || '').substring(0, 80),
                            value: (el.value || '').substring(0, 50),
                            label: labelText.substring(0, 50),
                            classes: (el.className || '').toString().substring(0, 80),
                        });
                    }
                    return results;
                }
            """)
            logger.info(f"=== INPUT FIELD DUMP ({len(fields_info)} fields) ===")
            for i, f in enumerate(fields_info):
                logger.info(
                    f"  [{i}] <{f['tag']}> type={f['type']} name={f['name']} "
                    f"placeholder=\"{f['placeholder']}\" "
                    f"value=\"{f['value']}\" label=\"{f['label']}\""
                )
            logger.info("=== END INPUT FIELD DUMP ===")
        except Exception as e:
            logger.warning(f"Input 필드 덤프 실패: {e}")

    async def _open_description_editor(self):
        """'작품 설명' 섹션의 '수정하기' 버튼을 클릭하여 상세 에디터를 노출"""
        try:
            # 전략 1: "작품 설명" 텍스트 근처의 "수정하기" 버튼
            clicked = False

            # Playwright locator 기반 탐색 — 여러 셀렉터 시도
            selectors = [
                # "작품 설명" 섹션 내 "수정하기" 버튼
                'section:has-text("작품 설명") button:has-text("수정하기")',
                'div:has-text("작품 설명") button:has-text("수정하기")',
                # Vuetify card/expansion panel 내부
                '.v-card:has-text("작품 설명") button:has-text("수정하기")',
                '.v-expansion-panel:has-text("작품 설명") button:has-text("수정하기")',
            ]

            for sel in selectors:
                try:
                    btn = self.page.locator(sel).first
                    if await btn.count() > 0:
                        await btn.scroll_into_view_if_needed()
                        await btn.click()
                        clicked = True
                        logger.info(f"'수정하기' 버튼 클릭 성공 (selector: {sel})")
                        break
                except Exception:
                    continue

            # 전략 2: JS로 "수정하기" 버튼을 "작품 설명" 근처에서 탐색
            if not clicked:
                clicked = await self.page.evaluate("""
                    () => {
                        // 모든 버튼에서 "수정하기" 텍스트를 가진 것 찾기
                        const buttons = Array.from(document.querySelectorAll('button, .v-btn'));
                        const editButtons = buttons.filter(
                            b => b.textContent.trim().includes('수정하기')
                        );

                        // "작품 설명" 텍스트와 가장 가까운 "수정하기" 버튼 찾기
                        const descHeaders = Array.from(
                            document.querySelectorAll('h1, h2, h3, h4, h5, h6, .v-card__title, .v-subheader, span, div, p')
                        ).filter(el => {
                            const text = el.textContent.trim();
                            return text.includes('작품 설명') && text.length < 30;
                        });

                        for (const header of descHeaders) {
                            // header와 같은 섹션/카드에 있는 수정하기 버튼 찾기
                            const container = header.closest(
                                'section, .v-card, .v-expansion-panel, [class*="section"], [class*="description"]'
                            ) || header.parentElement?.parentElement;
                            if (!container) continue;

                            const btn = container.querySelector('button, .v-btn');
                            if (btn && btn.textContent.trim().includes('수정하기')) {
                                btn.click();
                                return true;
                            }
                        }

                        // Fallback: 가장 마지막 "수정하기" 버튼 (설명 섹션이 보통 아래쪽)
                        if (editButtons.length > 0) {
                            const lastBtn = editButtons[editButtons.length - 1];
                            lastBtn.click();
                            return true;
                        }

                        return false;
                    }
                """)
                if clicked:
                    logger.info("'수정하기' 버튼 클릭 성공 (JS fallback)")

            if not clicked:
                logger.warning(
                    "'작품 설명' 수정하기 버튼을 찾지 못함 — "
                    "에디터가 이미 열려있거나 페이지 구조가 다를 수 있음"
                )
                return

            # 에디터 로딩 대기
            await asyncio.sleep(2)

            # 에디터 콘텐츠 렌더링 대기 — 이미지, contenteditable 등
            editor_selectors = [
                '[contenteditable="true"]',
                '.ql-editor',
                '.ProseMirror',
                '.tiptap',
                '.v-textarea textarea',
                'textarea[rows]',
                'img[src*="idus"]',
            ]
            for sel in editor_selectors:
                try:
                    await self.page.wait_for_selector(sel, timeout=5000)
                    logger.info(f"수정하기 클릭 후 에디터 요소 감지: {sel}")
                    break
                except Exception:
                    continue

            # 추가 렌더링 안정화
            await asyncio.sleep(1)

        except Exception as e:
            logger.warning(f"작품 설명 수정하기 버튼 처리 중 오류: {e}")

    async def _read_title(self) -> str:
        """작품명 추출 — name="productName" textarea"""
        try:
            selectors = [
                'textarea[name="productName"]',
                'textarea[placeholder*="작품명"]',
                'input[name="productName"]',
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
        """가격 추출 — name="product_price" input"""
        try:
            price_input = self.page.locator(
                'input[name="product_price"]'
            ).first
            if await price_input.count() > 0:
                val = await price_input.input_value()
                return int(re.sub(r'[^\d]', '', val)) if val else 0
        except Exception as e:
            logger.warning(f"가격 추출 실패: {e}")
        return 0

    async def _read_quantity(self, price: int = 0) -> int:
        """수량 추출 — name="stock" input"""
        try:
            stock_input = self.page.locator('input[name="stock"]').first
            if await stock_input.count() > 0:
                val = await stock_input.input_value()
                qty = int(re.sub(r'[^\d]', '', val)) if val else 0
                if price > 0 and qty == price:
                    logger.warning(f"수량({qty})이 가격({price})과 동일 — 잘못된 추출 가능성")
                    return 0
                return qty
        except Exception as e:
            logger.warning(f"수량 추출 실패: {e}")
        return 0

    async def _read_made_to_order(self) -> bool:
        """주문 시 제작 여부 — name="product_custom_order_checkbox" """
        try:
            cb = self.page.locator('input[name="product_custom_order_checkbox"]').first
            if await cb.count() > 0:
                return await cb.is_checked()
        except Exception as e:
            logger.warning(f"주문제작 여부 추출 실패: {e}")
        return False

    async def _read_category(self) -> str:
        """카테고리 경로 추출 — name="productCategory" hidden input"""
        try:
            cat_input = self.page.locator('input[name="productCategory"]').first
            if await cat_input.count() > 0:
                val = await cat_input.input_value()
                if val:
                    return val.strip()
        except Exception as e:
            logger.warning(f"카테고리 추출 실패: {e}")
        return ""

    async def _read_product_images(self) -> list[ProductImage]:
        """작품 이미지 (대표 + 추가) 추출 — '작품 이미지' 업로드 섹션 스코프"""
        images = []
        try:
            images_data = await self.page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();

                    // "작품 이미지" 텍스트가 있는 섹션 컨테이너 찾기
                    let imageSection = null;
                    const headers = document.querySelectorAll(
                        'h1, h2, h3, h4, h5, h6, .v-card__title, .v-subheader, span, div, label, p'
                    );
                    for (const h of headers) {
                        const text = h.textContent.trim();
                        if (text.includes('작품 이미지') && text.length < 30) {
                            imageSection = h.closest(
                                'section, .v-card, [class*="section"], [class*="image-upload"], [class*="upload"]'
                            ) || h.parentElement?.parentElement?.parentElement;
                            break;
                        }
                    }

                    // 이미지 추출 함수
                    function extractFromContainer(container) {
                        if (!container) return;
                        const imgs = container.querySelectorAll('img');
                        for (const img of imgs) {
                            const src = img.src || img.dataset?.src || img.getAttribute('data-src') || '';
                            if (!src) continue;
                            if (seen.has(src)) continue;
                            // 필터: 로고, 아이콘 등 제외
                            const srcLower = src.toLowerCase();
                            if (srcLower.includes('logo') || srcLower.includes('icon')
                                || srcLower.includes('profile') || srcLower.includes('avatar')
                                || srcLower.includes('10x10') || srcLower.includes('favicon')
                                || srcLower.includes('placeholder') || srcLower.includes('spinner')) {
                                continue;
                            }
                            // 최소 크기 80px
                            const w = img.naturalWidth || img.width || 0;
                            const h = img.naturalHeight || img.height || 0;
                            if (w > 0 && w < 80 && h > 0 && h < 80) continue;
                            seen.add(src);
                            results.push(src);
                        }

                        // background-image
                        const bgEls = container.querySelectorAll('[style*="background-image"]');
                        for (const el of bgEls) {
                            const style = el.getAttribute('style') || '';
                            const match = style.match(/url\\(['"]?(https?:\\/\\/[^'"\\)]+)/);
                            if (match && !seen.has(match[1])) {
                                const srcLower = match[1].toLowerCase();
                                if (srcLower.includes('logo') || srcLower.includes('icon')
                                    || srcLower.includes('profile') || srcLower.includes('avatar')
                                    || srcLower.includes('10x10')) {
                                    continue;
                                }
                                seen.add(match[1]);
                                results.push(match[1]);
                            }
                        }
                    }

                    // 섹션이 찾아졌으면 그 안에서만 추출
                    if (imageSection) {
                        extractFromContainer(imageSection);
                    }

                    // 섹션을 못찾았거나 결과가 없으면 전체 범위에서 추출하되 필터링 강화
                    if (results.length === 0) {
                        const imgSelectors = [
                            'img[src*="image.idus.com"]',
                            'img[src*="idus-file"]',
                            'img[src*="idus"]',
                            'img[src*="cloudfront"]',
                        ];
                        for (const selector of imgSelectors) {
                            const imgs = document.querySelectorAll(selector);
                            for (const img of imgs) {
                                const src = img.src || img.dataset?.src || '';
                                if (!src || seen.has(src)) continue;
                                const srcLower = src.toLowerCase();
                                if (srcLower.includes('logo') || srcLower.includes('icon')
                                    || srcLower.includes('profile') || srcLower.includes('avatar')
                                    || srcLower.includes('10x10') || srcLower.includes('favicon')
                                    || srcLower.includes('placeholder') || srcLower.includes('spinner')) {
                                    continue;
                                }
                                const w = img.naturalWidth || img.width || 0;
                                const h = img.naturalHeight || img.height || 0;
                                if (w > 0 && w < 80 && h > 0 && h < 80) continue;
                                seen.add(src);
                                results.push(src);
                            }
                        }
                    }

                    // 고해상도 URL 우선: _720, _800, _1000 접미사가 있으면 상위로
                    results.sort((a, b) => {
                        const hiResPattern = /_(720|800|1000)/;
                        const aHi = hiResPattern.test(a) ? 0 : 1;
                        const bHi = hiResPattern.test(b) ? 0 : 1;
                        return aHi - bHi;
                    });

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
                logger.warning(f"작품 이미지 0건. 페이지 내 img 태그 샘플: {debug_info}")

        except Exception as e:
            logger.warning(f"작품 이미지 추출 실패: {e}")
        return images

    async def _read_detail_images(self) -> list[ProductImage]:
        """작품 설명 에디터 내 상세 이미지 추출 (OCR 대상)"""
        images = []
        try:
            images_data = await self.page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();

                    // 에디터 컨테이너 후보
                    const editorSelectors = [
                        '[contenteditable="true"]',
                        '.ql-editor',
                        '.ProseMirror',
                        '.tiptap',
                        '.v-textarea',
                    ];

                    let editorContainer = null;
                    for (const sel of editorSelectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            editorContainer = el;
                            break;
                        }
                    }

                    // "작품 설명" 섹션 컨테이너도 시도
                    if (!editorContainer) {
                        const headers = document.querySelectorAll(
                            'h1, h2, h3, h4, h5, h6, .v-card__title, .v-subheader, span, div, p'
                        );
                        for (const h of headers) {
                            const text = h.textContent.trim();
                            if (text.includes('작품 설명') && text.length < 30) {
                                editorContainer = h.closest(
                                    'section, .v-card, [class*="section"], [class*="description"]'
                                ) || h.parentElement?.parentElement;
                                break;
                            }
                        }
                    }

                    if (!editorContainer) return results;

                    const imgs = editorContainer.querySelectorAll('img');
                    for (const img of imgs) {
                        const src = img.src || img.dataset?.src || img.getAttribute('data-src') || '';
                        if (!src || seen.has(src)) continue;
                        const srcLower = src.toLowerCase();
                        if (srcLower.includes('logo') || srcLower.includes('icon')
                            || srcLower.includes('profile') || srcLower.includes('avatar')
                            || srcLower.includes('10x10') || srcLower.includes('favicon')
                            || srcLower.includes('placeholder') || srcLower.includes('spinner')) {
                            continue;
                        }
                        const w = img.naturalWidth || img.width || 0;
                        const h = img.naturalHeight || img.height || 0;
                        if (w > 0 && w < 80 && h > 0 && h < 80) continue;
                        seen.add(src);
                        results.push(src);
                    }

                    // 고해상도 URL 우선
                    results.sort((a, b) => {
                        const hiResPattern = /_(720|800|1000)/;
                        const aHi = hiResPattern.test(a) ? 0 : 1;
                        const bHi = hiResPattern.test(b) ? 0 : 1;
                        return aHi - bHi;
                    });

                    return results;
                }
            """)

            for i, src in enumerate(images_data):
                images.append(ProductImage(
                    url=src,
                    order=i,
                    is_representative=False,
                ))

            logger.info(f"상세 이미지 {len(images)}건 추출 (에디터 내)")

        except Exception as e:
            logger.warning(f"상세 이미지 추출 실패: {e}")
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
        """작품 설명 HTML 추출 — 수정하기 버튼 클릭 후 에디터에서 추출"""
        try:
            # 에디터 콘텐츠 영역 (수정하기 클릭 후 노출)
            selectors = [
                '[contenteditable="true"]',
                '.ql-editor',                      # Quill editor
                '.ProseMirror',                    # ProseMirror
                '.tiptap',                         # Tiptap
                '.v-textarea textarea',            # Vuetify textarea
                'section:has-text("작품 설명") [class*="content"]',
            ]
            for sel in selectors:
                el = self.page.locator(sel).first
                if await el.count() > 0:
                    html = await el.inner_html()
                    if html and len(html) > 10:
                        return html

            # Fallback: 100자 이상의 textarea (설명일 가능성)
            fallback_html = await self.page.evaluate("""
                () => {
                    const textareas = document.querySelectorAll('textarea');
                    for (const ta of textareas) {
                        if (ta.value && ta.value.length > 100) {
                            return ta.value;
                        }
                    }
                    // contenteditable div 중 긴 텍스트
                    const editables = document.querySelectorAll('[contenteditable]');
                    for (const el of editables) {
                        const html = el.innerHTML;
                        if (html && html.length > 100) {
                            return html;
                        }
                    }
                    return '';
                }
            """)
            if fallback_html:
                return fallback_html

        except Exception as e:
            logger.warning(f"작품 설명 추출 실패: {e}")
        return ""

    async def _read_options(self) -> list[DomesticOption]:
        """옵션 목록 추출 — Vue 인스턴스 데이터 직접 접근"""
        options = []
        try:
            # 전략 1: hidden input product_option의 Vue 바인딩 데이터를 직접 읽기
            # [object Object] 문자열이 아니라 Vue가 바인딩한 실제 JS 객체를 읽음
            options_data = await self.page.evaluate("""
                () => {
                    const result = [];

                    // 1. product_option hidden input에서 Vue 바인딩 데이터 접근
                    const optionInput = document.querySelector('input[name="product_option"]');
                    if (optionInput) {
                        // Vue 2/3 인스턴스에서 데이터 접근 시도
                        let vueData = null;

                        // Vue 2: __vue__ 속성
                        let el = optionInput;
                        for (let i = 0; i < 10; i++) {
                            if (el.__vue__) {
                                vueData = el.__vue__;
                                break;
                            }
                            el = el.parentElement;
                            if (!el) break;
                        }

                        // Vue 3: __vue_app__ / __vueParentComponent
                        if (!vueData) {
                            const app = document.querySelector('#app') || document.querySelector('[id*="app"]');
                            if (app && app.__vue_app__) {
                                // Vue 3 앱 인스턴스에서 탐색
                                try {
                                    const rootData = app.__vue_app__._instance?.proxy?.$data;
                                    if (rootData) vueData = rootData;
                                } catch(e) {}
                            }
                        }

                        // Vue 데이터에서 옵션 정보 추출
                        if (vueData) {
                            // $data 또는 직접 속성에서 옵션 관련 데이터 탐색
                            const data = vueData.$data || vueData;
                            const optionKeys = ['product_option', 'productOption', 'options', 'option', 'optionList', 'option_list'];
                            for (const key of optionKeys) {
                                const val = data[key];
                                if (val && typeof val === 'object') {
                                    // 배열이면 직접 사용
                                    if (Array.isArray(val)) {
                                        for (const opt of val) {
                                            if (opt && typeof opt === 'object') {
                                                const name = opt.name || opt.option_name || opt.optionName || opt.title || '';
                                                const values = opt.values || opt.option_values || opt.items || [];
                                                if (name) {
                                                    result.push({
                                                        name: String(name),
                                                        values: Array.isArray(values)
                                                            ? values.map(v => ({
                                                                value: String(typeof v === 'object' ? (v.value || v.name || v.label || JSON.stringify(v)) : v),
                                                                additional_price: typeof v === 'object' ? (v.additional_price || v.additionalPrice || v.price || 0) : 0,
                                                            }))
                                                            : [{value: String(values), additional_price: 0}],
                                                        option_type: opt.option_type || opt.type || 'basic',
                                                    });
                                                }
                                            }
                                        }
                                    }
                                    // 단일 객체이면 래핑
                                    else if (!Array.isArray(val) && val.name) {
                                        result.push({
                                            name: String(val.name),
                                            values: [{value: 'option', additional_price: 0}],
                                            option_type: 'basic',
                                        });
                                    }
                                    if (result.length > 0) break;
                                }
                            }
                        }
                    }

                    if (result.length > 0) return result;

                    // 2. DOM에서 옵션 UI 요소 탐색 (폴백)
                    const optionSections = document.querySelectorAll('[class*="option"], [class*="Option"]');
                    for (const section of optionSections) {
                        const nameEl = section.querySelector('input[placeholder*="옵션명"], input[placeholder*="옵션"]');
                        if (!nameEl || !nameEl.value) continue;

                        const values = [];
                        const chips = section.querySelectorAll('.v-chip');
                        for (const chip of chips) {
                            const text = chip.textContent?.trim().replace(/[×x✕✖]$/g, '').trim();
                            if (text && text.length > 0) {
                                values.push({ value: String(text), additional_price: 0 });
                            }
                        }
                        if (values.length > 0) {
                            result.push({ name: String(nameEl.value), values, option_type: 'basic' });
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
                            value=str(v["value"]),
                            additional_price=v.get("additional_price", 0),
                        )
                        for v in opt_data["values"]
                    ],
                    option_type=opt_data.get("option_type", "basic"),
                ))

            if not options:
                debug_info = await self.page.evaluate("""
                    () => {
                        const optionEls = document.querySelectorAll('[class*="option"], [class*="Option"]');
                        const chipEls = document.querySelectorAll('.v-chip');
                        return {
                            optionElementCount: optionEls.length,
                            chipCount: chipEls.length,
                            samples: Array.from(optionEls).slice(0, 5).map(el => ({
                                tag: el.tagName,
                                classes: el.className?.toString().substring(0, 100),
                                inputCount: el.querySelectorAll('input').length,
                                chipCount: el.querySelectorAll('.v-chip').length,
                                text: el.textContent?.trim().substring(0, 100),
                            })),
                            chipSamples: Array.from(chipEls).slice(0, 10).map(el => ({
                                text: el.textContent?.trim().substring(0, 80),
                            })),
                        };
                    }
                """)
                logger.info(f"옵션 0건. DOM 옵션 요소 정보: {debug_info}")

        except Exception as e:
            logger.warning(f"옵션 추출 실패: {e}")
        return options

    async def _read_keywords(self) -> list[str]:
        """키워드 추출 — name="product_keyword" hidden input"""
        try:
            # 전략 1: hidden input에서 직접 읽기 (가장 정확)
            kw_input = self.page.locator('input[name="product_keyword"]').first
            if await kw_input.count() > 0:
                val = await kw_input.input_value()
                if val:
                    # "#자개키링,#전통키링,..." 형식 → 파싱
                    keywords = [k.strip().lstrip('#') for k in val.split(',') if k.strip()]
                    if keywords:
                        logger.info(f"키워드 추출: {len(keywords)}개 (hidden input)")
                        return keywords

            # 전략 2: Vuetify chip 또는 태그 요소
            keywords_data = await self.page.evaluate("""
                () => {
                    const chipTags = document.querySelectorAll('.v-chip');
                    if (chipTags.length > 0) {
                        return Array.from(chipTags)
                            .map(t => t.textContent.trim().replace(/[×x✕✖]$/g, '').trim())
                            .filter(t => t && t.length > 1);
                    }

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
