"""
작가웹 국내 탭 데이터 추출 서비스

Vuex 스토어($store.state.productForm._item)에서 직접 데이터를 읽습니다.
DOM 셀렉터 의존을 제거하고, JS 객체를 JSON으로 직접 직렬화하여
[object Object] 문제를 완전 해결합니다.
"""
import asyncio
import logging
from typing import Optional
from playwright.async_api import Page
from ..models.domestic import (
    DomesticProduct, ProductImage, DomesticOption, OptionValue,
    ProductStatus, GlobalStatus,
)

logger = logging.getLogger(__name__)

# 글로벌 판매 제한 카테고리
RESTRICTED_CATEGORIES = [
    "식품", "가구", "식물", "디퓨저",
    "14k", "18k", "24k",
]


class ProductReader:
    """작가웹 국내 탭 데이터 추출기 — Vuex 스토어 기반

    전제: 이미 /product/{product_id} 페이지에 위치한 상태에서 호출됩니다.
    ArtistWebSession.navigate_to_product() 호출 후 사용하세요.
    """

    def __init__(self, page: Page):
        self.page = page

    async def read_domestic_data(self, product_id: str) -> DomesticProduct:
        """Vuex 스토어에서 전체 제품 데이터를 한 번에 추출"""
        # SPA 렌더링 대기
        await asyncio.sleep(2)

        # Vuex 스토어에서 데이터 추출
        vuex_data = await self._read_vuex_store()

        if vuex_data and vuex_data.get("success"):
            logger.info(f"[Vuex] 데이터 추출 성공: {product_id}")
            product = self._build_product_from_vuex(product_id, vuex_data)

            # 국내 옵션이 비어있으면 DOM 모달에서 추출 시도
            if not product.options:
                logger.info("[Vuex] 옵션 비어있음 — DOM 모달에서 추출 시도")
                dom_options = await self._read_options_from_modal()
                if dom_options:
                    product.options = dom_options
                    logger.info(f"[DOM 모달] 옵션 {len(dom_options)}개 추출")

            return product

        # Vuex 실패 시 DOM 폴백
        logger.warning(f"[Vuex] 데이터 추출 실패, DOM 폴백: {vuex_data}")
        return await self._read_from_dom(product_id)

    async def _read_vuex_store(self) -> Optional[dict]:
        """Vuex 스토어에서 productForm._item 데이터 추출"""
        try:
            return await self.page.evaluate("""
                () => {
                    const app = document.querySelector('#app');
                    if (!app || !app.__vue__ || !app.__vue__.$store) {
                        return { success: false, error: 'Vuex store not found' };
                    }

                    const store = app.__vue__.$store;
                    const state = store.state;
                    const form = state.productForm?._item;

                    if (!form) {
                        return { success: false, error: 'productForm._item not found' };
                    }

                    // 이미지: string[] (URL 배열)
                    const images = form.images || [];

                    // 옵션: form.options (국내) 또는 globalProduct의 productOptionGroups (글로벌)
                    const options = [];

                    // 국내 옵션 (form.options)
                    const domesticOpts = form.options || form.productOptionGroups || [];
                    if (Array.isArray(domesticOpts) && domesticOpts.length > 0) {
                        for (const group of domesticOpts) {
                            if (!group) continue;
                            const name = group.name || group.title || '';
                            const vals = group.productOptions || group.values || group.items || [];
                            const values = [];
                            for (const opt of (Array.isArray(vals) ? vals : [])) {
                                if (!opt) continue;
                                const v = typeof opt.value === 'string' ? opt.value
                                    : (Array.isArray(opt.value) ? (opt.value.find(x => x.lang === 'ko')?.value || opt.value[0]?.value || '') : String(opt.value || ''));
                                values.push({ value: v, additional_price: opt.price || 0 });
                            }
                            if (name || values.length > 0) {
                                options.push({ name: String(name), values, option_type: group.optionType || 'basic' });
                            }
                        }
                    }

                    // 글로벌 옵션 (globalProduct._detail.productOptionGroups) — 국내 없으면 참조
                    const globalOpts = state.globalProduct?._detail?.productOptionGroups || [];
                    if (options.length === 0 && Array.isArray(globalOpts) && globalOpts.length > 0) {
                        for (const group of globalOpts) {
                            if (!group) continue;
                            // 그룹명: value는 [{lang, value}] 다국어 배열
                            const nameArr = group.value || [];
                            const name = Array.isArray(nameArr)
                                ? (nameArr.find(x => x.lang === 'ko')?.value || nameArr.find(x => x.lang === 'ja')?.value || nameArr[0]?.value || '')
                                : String(nameArr);
                            const vals = group.productOptions || [];
                            const values = [];
                            for (const opt of (Array.isArray(vals) ? vals : [])) {
                                const vArr = opt.value || [];
                                const v = Array.isArray(vArr)
                                    ? (vArr.find(x => x.lang === 'ko')?.value || vArr.find(x => x.lang === 'ja')?.value || vArr[0]?.value || '')
                                    : String(vArr);
                                values.push({ value: v, additional_price: opt.price || 0 });
                            }
                            if (name || values.length > 0) {
                                options.push({ name: String(name), values, option_type: group.optionType || 'basic' });
                            }
                        }
                    }

                    // premiumDescription: [{uuid, type, label, value}, ...]
                    // value는 TEXT/SUBJECT일 때 문자열, IMAGE/SPLIT_IMAGE일 때 URL 배열
                    const premDesc = form.premiumDescription || [];
                    let descriptionHtml = '';
                    const detailImageUrls = [];
                    if (Array.isArray(premDesc)) {
                        const htmlParts = [];
                        for (const section of premDesc) {
                            if (!section) continue;
                            const type = section.type || '';
                            const rawValue = section.value;
                            const label = section.label || '';

                            if (type === 'TEXT' || type === 'SUBJECT') {
                                const text = typeof rawValue === 'string' ? rawValue : '';
                                if (text) htmlParts.push(type === 'SUBJECT' ? '<h3>' + text + '</h3>' : '<p>' + text + '</p>');
                            } else if (type === 'IMAGE' || type === 'SPLIT_IMAGE') {
                                // value가 배열(URL[]) 또는 문자열일 수 있음
                                const urls = Array.isArray(rawValue)
                                    ? rawValue
                                    : (typeof rawValue === 'string' ? rawValue.split(',').map(u => u.trim()) : []);
                                for (const url of urls) {
                                    if (typeof url === 'string' && url.startsWith('http')) {
                                        detailImageUrls.push(url);
                                        htmlParts.push('<img src="' + url + '" />');
                                    }
                                }
                            } else if (type === 'LINE') {
                                htmlParts.push('<hr />');
                            }
                            // BLANK은 무시
                        }
                        descriptionHtml = htmlParts.join('\\n');
                    }

                    // 키워드: Vuex에 없으면 hidden input에서 읽기
                    let keywords = form.keywords || [];
                    if (typeof keywords === 'string') {
                        keywords = keywords.split(',').map(k => k.trim().replace(/^#/, '')).filter(Boolean);
                    } else if (Array.isArray(keywords) && keywords.length > 0) {
                        keywords = keywords.map(k => {
                            if (typeof k === 'object') return k.name || k.keyword || k.value || String(k);
                            return String(k).replace(/^#/, '');
                        }).filter(Boolean);
                    }
                    // Vuex에 키워드 없으면 hidden input에서
                    if (!keywords || keywords.length === 0) {
                        const kwInput = document.querySelector('input[name="product_keyword"]');
                        if (kwInput && kwInput.value) {
                            keywords = kwInput.value.split(',').map(k => k.trim().replace(/^#/, '')).filter(Boolean);
                        }
                    }

                    // 카테고리
                    const category = form.managementCategoryName || form.categoryName || '';
                    // hidden input에서 카테고리 읽기 (폴백)
                    let categoryFromInput = '';
                    const catInput = document.querySelector('input[name="productCategory"]');
                    if (catInput) categoryFromInput = catInput.value || '';

                    // 글로벌 상태 확인
                    const globalDetail = state.globalProduct?._detail || {};
                    const hasGlobal = globalDetail.onSale || globalDetail.uuid || false;

                    return {
                        success: true,
                        title: form.productName || form.name || '',
                        price: form.originPrice || form.price || 0,
                        salePrice: form.salePrice || 0,
                        useDiscount: form.useDiscount || false,
                        quantity: form.itemCount || 0,
                        isCustomOrder: form.orderAfterMaking || false,
                        category: categoryFromInput || category,
                        images: images,
                        options: options,
                        descriptionHtml: descriptionHtml,
                        detailImageUrls: detailImageUrls,
                        premiumDescriptionRaw: premDesc.map(s => ({
                            type: s?.type || '',
                            label: s?.label || '',
                            value: Array.isArray(s?.value) ? JSON.stringify(s.value) : String(s?.value || '').substring(0, 500),
                        })),
                        keywords: keywords,
                        giftWrapping: (form.attributeIds || []).length > 0,
                        hasGlobal: !!hasGlobal,
                        globalJaTitle: globalDetail.productName || '',
                    };
                }
            """)
        except Exception as e:
            logger.error(f"Vuex 스토어 읽기 실패: {e}")
            return None

    def _build_product_from_vuex(
        self, product_id: str, data: dict
    ) -> DomesticProduct:
        """Vuex 데이터를 DomesticProduct 모델로 변환"""
        # 대표 이미지 + 추가 이미지
        product_images = []
        for i, url in enumerate(data.get("images", [])):
            if isinstance(url, str) and url.startswith("http"):
                product_images.append(ProductImage(
                    url=url,
                    order=i,
                    is_representative=(i == 0),
                ))

        # 설명 내 이미지 (OCR 대상)
        detail_images = []
        for i, url in enumerate(data.get("detailImageUrls", [])):
            if isinstance(url, str) and url.startswith("http"):
                detail_images.append(ProductImage(
                    url=url,
                    order=i,
                    is_representative=False,
                ))

        # 옵션
        options = []
        for opt_data in data.get("options", []):
            if not isinstance(opt_data, dict):
                continue
            options.append(DomesticOption(
                name=opt_data.get("name", ""),
                values=[
                    OptionValue(
                        value=v.get("value", ""),
                        additional_price=v.get("additional_price", 0),
                    )
                    for v in opt_data.get("values", [])
                    if isinstance(v, dict)
                ],
                option_type=opt_data.get("option_type", "basic"),
            ))

        # 카테고리
        category_path = data.get("category", "")
        category_restricted = any(
            kw in category_path for kw in RESTRICTED_CATEGORIES
        )

        # 글로벌 상태
        global_status = (
            GlobalStatus.REGISTERED if data.get("hasGlobal")
            else GlobalStatus.NOT_REGISTERED
        )

        product = DomesticProduct(
            product_id=product_id,
            product_url=self.page.url,
            title=data.get("title", ""),
            price=data.get("price", 0),
            quantity=data.get("quantity", 0),
            is_made_to_order=data.get("isCustomOrder", False),
            category_path=category_path,
            category_restricted=category_restricted,
            product_images=product_images,
            detail_images=detail_images,
            description_html=data.get("descriptionHtml", ""),
            options=options,
            keywords=data.get("keywords", []),
            gift_wrapping=data.get("giftWrapping", False),
            global_status=global_status,
        )

        logger.info(
            f"[Vuex] 제품 변환 완료: {product_id} "
            f"(제목={product.title[:30]}, 이미지={len(product_images)}, "
            f"설명이미지={len(detail_images)}, 옵션={len(options)}, "
            f"키워드={len(product.keywords)})"
        )
        return product

    async def _read_options_from_modal(self) -> list[DomesticOption]:
        """옵션 버튼을 클릭 → 모달에서 name 속성으로 옵션명/값/추가금액 읽기

        디버그 엔드포인트(/api/debug/option-modal)와 동일한 로직 사용.
        """
        options = []
        try:
            # DOM 렌더링 대기
            await asyncio.sleep(2)

            # Playwright 로케이터로 옵션 버튼 찾기 (자동 대기)
            option_buttons = self.page.locator(
                '[class*="optionItem"] button, [class*="OptionItem"] button'
            )
            count = await option_buttons.count()
            logger.info(f"[옵션 모달] optionItem 버튼 {count}개 발견")

            if count == 0:
                # 폴백: 모든 BaseButton 중 option 부모를 가진 것
                option_buttons = self.page.locator(
                    '.BaseButton'
                )
                all_count = await option_buttons.count()
                # option 관련 부모를 가진 버튼만 필터링
                valid_indices = []
                for i in range(all_count):
                    btn = option_buttons.nth(i)
                    parent_class = await btn.evaluate(
                        "el => el.closest('[class*=\"option\"], [class*=\"Option\"]')?.className || ''"
                    )
                    if parent_class:
                        valid_indices.append(i)
                count = len(valid_indices)
                logger.info(f"[옵션 모달] BaseButton 폴백: {count}개")

            for i in range(count):
                try:
                    btn = option_buttons.nth(i)
                    btn_text = (await btn.inner_text()).strip()
                    if not btn_text or len(btn_text) > 30:
                        continue

                    logger.info(f"[옵션 모달] 버튼 클릭: '{btn_text}'")
                    await btn.click()
                    await asyncio.sleep(1.5)

                    # 모달에서 데이터 읽기 (확정된 name 속성)
                    modal_data = await self.page.evaluate("""
                        () => {
                            const modal = document.querySelector('.v-dialog--active');
                            if (!modal) return null;

                            const nameInput = modal.querySelector('input[name="productOptionName"]');
                            const optionName = nameInput ? nameInput.value.trim() : '';

                            const valueInputs = Array.from(modal.querySelectorAll('input[name="productOptionValue"]'));
                            const priceInputs = Array.from(modal.querySelectorAll('input[name="optionPrice"]'));

                            const values = [];
                            for (let i = 0; i < valueInputs.length; i++) {
                                const val = valueInputs[i].value.trim();
                                if (!val) continue;
                                const price = priceInputs[i]
                                    ? parseInt(priceInputs[i].value.replace(/[^0-9]/g, ''), 10) || 0
                                    : 0;
                                values.push({ value: val, additional_price: price });
                            }

                            return { name: optionName, values: values };
                        }
                    """)

                    if modal_data and modal_data.get("name"):
                        opt_values = [
                            OptionValue(
                                value=v.get("value", ""),
                                additional_price=v.get("additional_price", 0),
                            )
                            for v in modal_data.get("values", [])
                            if v.get("value")
                        ]
                        options.append(DomesticOption(
                            name=modal_data["name"],
                            values=opt_values,
                            option_type="basic",
                        ))
                        logger.info(
                            f"[옵션 모달] 추출 성공: {modal_data['name']} "
                            f"({len(opt_values)}개 값)"
                        )
                    else:
                        logger.warning(f"[옵션 모달] 모달 데이터 없음: {modal_data}")

                    # 모달 닫기 (ESC)
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(f"[옵션 모달] 옵션 처리 실패: {e}")
                    try:
                        await self.page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass

        except Exception as e:
            logger.warning(f"[옵션 모달] 전체 실패: {e}")

        return options

    async def _read_from_dom(self, product_id: str) -> DomesticProduct:
        """DOM 폴백 — Vuex 실패 시 기본 input에서 읽기"""
        logger.info("[DOM 폴백] 기본 input 필드에서 데이터 추출")

        title = ""
        price = 0
        category = ""
        keywords = []

        try:
            # 제목
            el = self.page.locator('textarea[name="productName"]').first
            if await el.count() > 0:
                title = (await el.input_value()).strip()

            # 가격
            el = self.page.locator('input[name="product_price"]').first
            if await el.count() > 0:
                val = await el.input_value()
                import re
                price = int(re.sub(r'[^\d]', '', val)) if val else 0

            # 카테고리
            el = self.page.locator('input[name="productCategory"]').first
            if await el.count() > 0:
                category = (await el.input_value()).strip()

            # 키워드
            el = self.page.locator('input[name="product_keyword"]').first
            if await el.count() > 0:
                val = await el.input_value()
                if val:
                    keywords = [k.strip().lstrip('#') for k in val.split(',') if k.strip()]

        except Exception as e:
            logger.warning(f"[DOM 폴백] 추출 오류: {e}")

        return DomesticProduct(
            product_id=product_id,
            product_url=self.page.url,
            title=title,
            price=price,
            category_path=category,
            category_restricted=any(kw in category for kw in RESTRICTED_CATEGORIES),
            keywords=keywords,
        )
