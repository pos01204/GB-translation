"""
작가웹(artist.idus.com) 브라우저 세션 관리
Playwright 기반의 인증 및 네비게이션
"""
import asyncio
import re
import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from ..config import settings
from ..models.domestic import ProductSummary, ProductStatus, GlobalStatus

logger = logging.getLogger(__name__)


class ArtistWebSession:
    """작가웹 브라우저 세션

    Playwright를 사용하여 artist.idus.com에 로그인하고,
    작품 목록 조회 및 개별 작품 페이지 네비게이션을 수행합니다.

    Usage:
        session = ArtistWebSession()
        await session.initialize()
        await session.login("email@example.com", "password")
        products = await session.get_product_list("paused")
        await session.navigate_to_product("uuid-here")
        await session.close()
    """

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._authenticated = False
        self._initialized = False
        self._last_api_raw_sample: dict | None = None

    async def initialize(self):
        """Playwright 브라우저 초기화"""
        if self._initialized:
            return

        import os
        is_docker = os.path.exists('/.dockerenv') or os.getenv('RAILWAY_ENVIRONMENT')

        self.playwright = await async_playwright().start()

        launch_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
        ]

        if is_docker:
            launch_args.append('--single-process')
            logger.info("Docker 환경 감지됨")

        self.browser = await self.playwright.chromium.launch(
            headless=settings.browser_headless,
            args=launch_args,
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='ko-KR',
        )
        self.page = await self.context.new_page()
        self._initialized = True
        logger.info("작가웹 브라우저 세션 초기화 완료")

    async def login(self, email: str, password: str) -> bool:
        """
        작가웹 로그인

        절차:
        1. artist.idus.com 접속 → 로그인 페이지로 리다이렉트
        2. 이메일/비밀번호 입력
        3. 로그인 버튼 클릭
        4. 대시보드 로딩 확인
        """
        if not self.page:
            await self.initialize()

        try:
            await self.page.goto(
                f"{settings.artist_web_base_url}/login",
                timeout=settings.page_load_timeout,
            )
            await self.page.wait_for_load_state("networkidle")

            # 이메일 입력
            email_input = self.page.locator('input[type="email"], input[name="email"]')
            await email_input.wait_for(state="visible", timeout=10000)
            await email_input.fill(email)

            # 비밀번호 입력
            password_input = self.page.locator('input[type="password"], input[name="password"]')
            await password_input.fill(password)

            # 로그인 버튼 클릭
            login_button = self.page.locator(
                'button:has-text("로그인"), button[type="submit"]'
            ).first
            await login_button.click()

            # 로그인 성공 확인 (대시보드로 이동되는지)
            await self.page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=settings.artist_web_login_timeout,
            )
            self._authenticated = True
            logger.info("작가웹 로그인 성공")
            return True

        except Exception as e:
            logger.error(f"작가웹 로그인 실패: {e}")
            self._authenticated = False
            return False

    async def is_authenticated(self) -> bool:
        """인증 상태 확인"""
        if not self._authenticated or not self.page:
            return False
        current_url = self.page.url
        return "/login" not in current_url

    async def get_session_info(self) -> dict:
        """현재 세션 상태 정보 반환"""
        return {
            "initialized": self._initialized,
            "authenticated": self._authenticated,
            "current_url": self.page.url if self.page else None,
        }

    async def get_product_list(
        self,
        status: str = "selling",
    ) -> list[ProductSummary]:
        """
        작품 목록 조회

        전략 1: 브라우저 내 fetch()로 idus aggregator API 직접 호출
        전략 2: DOM 스크래핑 (링크 그룹핑 방식) - 폴백

        Args:
            status: "selling" | "paused" | "draft"

        Returns:
            ProductSummary 목록
        """
        if not await self.is_authenticated():
            raise Exception("로그인이 필요합니다")

        # ── 전략 1: 페이지 이동 후 SPA API 응답 캡처 ──
        url_map = {
            "selling": "/product/list",
            "paused": "/product/list/pause",
            "draft": "/product/list/draft",
        }
        target_url = f"{settings.artist_web_base_url}{url_map.get(status, '/product/list')}"

        try:
            all_products = []
            captured_responses = []

            async def on_api_response(response):
                """SPA가 호출하는 paging API 응답을 캡처"""
                try:
                    url = response.url
                    if response.status == 200 and "paging" in url and "idus" in url:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct:
                            body = await response.json()
                            captured_responses.append({"url": url, "body": body})
                            logger.info(f"[API 캡처] 응답 수신: {url}")
                except Exception:
                    pass

            self.page.on("response", on_api_response)

            try:
                # 페이지 이동 → SPA가 자동으로 API 호출
                logger.info(f"[API 캡처] 페이지 이동: {target_url}")
                await self.page.goto(target_url, timeout=settings.page_load_timeout)
                await self.page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(5)  # SPA 렌더링 + API 호출 대기
            finally:
                self.page.remove_listener("response", on_api_response)

            # 캡처된 응답 처리
            for resp_data in captured_responses:
                body = resp_data["body"]
                items = self._find_product_array(body)
                if not items:
                    continue

                page_products = self._parse_api_items(items, status)
                if page_products:
                    all_products.extend(page_products)
                    logger.info(f"[API 캡처] {len(page_products)}개 작품 추출 (URL: {resp_data['url']})")

                    # 페이지네이션 확인
                    has_next = self._check_has_next_page(body, 0, len(items))
                    if has_next:
                        # 스크롤로 다음 페이지 트리거
                        more_products = await self._load_remaining_pages(status)
                        all_products.extend(more_products)

            if all_products:
                logger.info(f"[API 캡처 성공] 총 {len(all_products)}개 작품 ({status})")
                return all_products
            else:
                logger.info(f"[API 캡처] 작품 0건 (캡처된 응답: {len(captured_responses)}건), DOM 스크래핑으로 전환")

        except Exception as e:
            logger.warning(f"API 캡처 실패: {e}")

        # ── 전략 2: DOM 스크래핑 (링크 그룹핑 방식) - 폴백 ──
        logger.info("DOM 스크래핑으로 전환...")

        url_map = {
            "selling": "/product/list",
            "paused": "/product/list/pause",
            "draft": "/product/list/draft",
        }
        target_url = f"{settings.artist_web_base_url}{url_map.get(status, '/product/list')}"

        try:
            await self.page.goto(target_url, timeout=settings.page_load_timeout)
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)  # SPA 렌더링 대기
        except Exception as e:
            logger.warning(f"DOM 스크래핑 페이지 로딩 실패: {e}")

        # 콘텐츠 로딩 대기
        try:
            await self.page.wait_for_selector(
                'a[href*="/product/"]', timeout=15000
            )
        except Exception:
            logger.warning("작품 링크 요소를 찾지 못함")

        # 무한스크롤 대응
        await self._scroll_to_load_all()

        # 링크를 UUID 별로 그룹핑하여 추출
        products_raw = await self.page.evaluate("""
            () => {
                const results = [];

                // 1단계: /product/UUID 링크를 UUID별로 그룹핑
                const allLinks = document.querySelectorAll('a[href*="/product/"]');
                const linksByProductId = {};

                for (const link of allLinks) {
                    const href = link.getAttribute('href') || '';
                    const match = href.match(/\\/product\\/([a-f0-9-]{36})/);
                    if (!match) continue;
                    const pid = match[1];
                    if (!linksByProductId[pid]) linksByProductId[pid] = [];
                    linksByProductId[pid].push(link);
                }

                // 2단계: 각 UUID에 대해 데이터 추출
                for (const [productId, links] of Object.entries(linksByProductId)) {

                    // 제목: 가장 짧은 의미있는 텍스트를 가진 링크에서 추출
                    let title = '';
                    let bestTitleLength = Infinity;
                    for (const link of links) {
                        // 링크 내 직접 텍스트 노드만 추출 (자식 요소 텍스트 제외)
                        const directText = Array.from(link.childNodes)
                            .filter(n => n.nodeType === Node.TEXT_NODE || (n.nodeType === Node.ELEMENT_NODE && !n.querySelector('img')))
                            .map(n => n.textContent.trim())
                            .join(' ')
                            .trim();

                        // 이미지만 있는 링크는 건너뜀
                        if (link.querySelector('img') && !directText) continue;

                        const text = directText || link.textContent.trim();
                        if (text && text.length > 3 && text.length < bestTitleLength
                            && !text.match(/^(남은수량|주문시|후기|판매수|찜|\\d)/)
                            && !text.match(/^\\d+[%원개건]/)
                        ) {
                            // 제목으로 적합한 텍스트: 카드 전체 텍스트가 아닌 제목 부분만
                            // 개행이 포함되면 첫 줄만 사용
                            const firstLine = text.split('\\n')[0].trim();
                            if (firstLine.length > 3) {
                                title = firstLine;
                                bestTitleLength = firstLine.length;
                            }
                        }
                    }

                    // 썸네일: img 태그가 있는 링크에서 추출
                    let thumbnailUrl = '';
                    for (const link of links) {
                        const img = link.querySelector('img');
                        if (img) {
                            thumbnailUrl = img.src || img.dataset?.src || '';
                            break;
                        }
                    }

                    // 카드 컨테이너 찾기: 모든 링크를 포함하는 공통 조상
                    let card = null;
                    if (links.length >= 2) {
                        let el = links[0];
                        for (let i = 0; i < 8; i++) {
                            el = el.parentElement;
                            if (!el || el.tagName === 'BODY') break;
                            if (el.contains(links[1])) {
                                card = el;
                                break;
                            }
                        }
                    }
                    if (!card) {
                        card = links[0].parentElement?.parentElement?.parentElement
                            || links[0].parentElement?.parentElement
                            || links[0].parentElement;
                    }

                    // 가격: 카드 내에서 "X,XXX원" 패턴 매칭
                    let priceText = '0';
                    if (card) {
                        const priceEl = card.querySelector('[class*="price"], [class*="Price"]');
                        if (priceEl) {
                            const match = priceEl.textContent.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                            priceText = match ? match[0] : '0';
                        } else {
                            const cardText = card.innerText || '';
                            const match = cardText.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                            priceText = match ? match[0] : '0';
                        }
                    }

                    // 글로벌 뱃지 확인
                    let hasGlobal = false;
                    if (card) {
                        hasGlobal = !!card.querySelector('[class*="global"], [class*="Global"]')
                            || (card.innerText || '').includes('글로벌');
                    }

                    results.push({
                        product_id: productId,
                        title: title,
                        price_text: priceText,
                        thumbnail_url: thumbnailUrl,
                        has_global: hasGlobal,
                    });
                }

                return results;
            }
        """)

        # 디버깅: 실패 시 페이지 정보 로깅
        if not products_raw:
            page_info = await self.page.evaluate("""
                () => ({
                    url: window.location.href,
                    title: document.title,
                    bodyLength: document.body.innerHTML.length,
                    linkCount: document.querySelectorAll('a').length,
                    productLinkCount: document.querySelectorAll('a[href*="/product/"]').length,
                    imgCount: document.querySelectorAll('img').length,
                    bodyPreview: document.body.innerText.substring(0, 1000),
                })
            """)
            logger.warning(f"DOM 스크래핑 결과 0건. 페이지 정보: {page_info}")

        # ProductSummary 변환
        result = []
        for p in products_raw:
            result.append(ProductSummary(
                product_id=p["product_id"],
                title=p.get("title", ""),
                price=self._parse_price(p.get("price_text", "0")),
                thumbnail_url=p.get("thumbnail_url") or None,
                status=ProductStatus(status),
                global_status=(
                    GlobalStatus.REGISTERED if p.get("has_global")
                    else GlobalStatus.NOT_REGISTERED
                ),
            ))

        logger.info(f"[DOM 스크래핑] {len(result)}개 작품 추출 ({status})")
        return result

    def _parse_api_items(
        self, items: list, status: str
    ) -> list[ProductSummary]:
        """API 응답의 작품 배열을 ProductSummary 리스트로 변환"""
        if not items:
            return []

        self._last_api_raw_sample = items[0] if items else None

        # 첫 아이템의 전체 구조를 로깅 (필드명 파악용)
        first_item = items[0] if items else {}
        if isinstance(first_item, dict):
            logger.info(f"[API 파싱] 첫 아이템 키: {list(first_item.keys())}")
            # 각 키의 값 타입과 샘플 출력
            for k, v in first_item.items():
                sample = str(v)[:100] if v is not None else "None"
                logger.info(f"  {k}: ({type(v).__name__}) {sample}")

        result = []
        for item in items:
            if not isinstance(item, dict):
                continue

            # UUID 형식의 ID 필드 탐색 (모든 문자열 필드에서)
            product_id = None
            uuid_pattern = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')

            # 명시적 키 우선
            for key in ("product_id", "productId", "uuid", "id"):
                val = item.get(key)
                if val and isinstance(val, str) and (len(val) >= 32 or uuid_pattern.match(val)):
                    product_id = val
                    break

            # 못 찾으면 모든 문자열 필드에서 UUID 탐색
            if not product_id:
                for key, val in item.items():
                    if isinstance(val, str) and uuid_pattern.match(val):
                        product_id = val
                        break

            if not product_id:
                continue

            # 제목: 다양한 키 + 최장 문자열 필드 폴백
            title = None
            for key in ("title", "name", "productName", "product_name",
                        "productTitle", "product_title", "displayName", "display_name"):
                val = item.get(key)
                if val and isinstance(val, str) and len(val) > 1:
                    title = val
                    break

            # 제목을 못 찾으면, 10자 이상의 문자열 필드 중 가장 긴 것
            if not title:
                best = ""
                for key, val in item.items():
                    if isinstance(val, str) and len(val) > len(best) and len(val) >= 5:
                        # UUID나 URL이 아닌 것만
                        if not uuid_pattern.match(val) and not val.startswith("http"):
                            best = val
                if best:
                    title = best

            # 가격: 다양한 키
            price = 0
            for key in ("price", "salePrice", "sale_price", "sellingPrice",
                        "selling_price", "originalPrice", "original_price",
                        "discountPrice", "discount_price"):
                val = item.get(key)
                if val:
                    if isinstance(val, (int, float)):
                        price = int(val)
                        break
                    elif isinstance(val, str):
                        price = self._parse_price(val)
                        if price > 0:
                            break

            # 썸네일: 다양한 키 + URL 패턴 탐색
            thumbnail = None
            for key in ("thumbnail_url", "thumbnailUrl", "image", "imageUrl",
                        "representative_image", "thumbnail", "img", "photo",
                        "photoUrl", "photo_url", "mainImage", "main_image",
                        "representativeImageUrl", "representative_image_url"):
                val = item.get(key)
                if val and isinstance(val, str) and ("http" in val or val.startswith("/")):
                    thumbnail = val
                    break

            # URL 필드 탐색 폴백
            if not thumbnail:
                for key, val in item.items():
                    if isinstance(val, str) and ("image" in key.lower() or "img" in key.lower() or "photo" in key.lower() or "thumb" in key.lower()):
                        if "http" in val or val.startswith("/"):
                            thumbnail = val
                            break

            # 글로벌 상태
            has_global = False
            for key in ("global_status", "globalStatus", "hasGlobal", "is_global",
                        "globalSaleStatus", "global_sale_status"):
                val = item.get(key)
                if val:
                    if isinstance(val, bool):
                        has_global = val
                    elif isinstance(val, str):
                        has_global = val.lower() not in ("", "none", "null", "false", "not_registered")
                    elif isinstance(val, (int, float)):
                        has_global = val > 0
                    if has_global:
                        break

            result.append(ProductSummary(
                product_id=str(product_id),
                title=str(title) if title else "",
                price=price,
                thumbnail_url=str(thumbnail) if thumbnail else None,
                status=ProductStatus(status),
                global_status=(
                    GlobalStatus.REGISTERED if has_global
                    else GlobalStatus.NOT_REGISTERED
                ),
            ))

        return result

    @staticmethod
    def _check_has_next_page(body: dict, current_page: int, items_count: int) -> bool:
        """API 응답에서 다음 페이지 존재 여부 확인"""
        if not isinstance(body, dict):
            return items_count >= 20  # 기본 페이지 사이즈 추정

        # 다양한 구조 대응
        def _find_pagination_info(obj):
            if not isinstance(obj, dict):
                return None
            # 직접 pagination 필드 확인
            for key in ("totalPages", "total_pages"):
                if key in obj:
                    total_pages = obj[key]
                    return current_page < (total_pages - 1)
            if "last" in obj and isinstance(obj["last"], bool):
                return not obj["last"]
            if "hasNext" in obj or "has_next" in obj:
                return bool(obj.get("hasNext") or obj.get("has_next"))
            # 중첩 탐색
            for val in obj.values():
                if isinstance(val, dict):
                    result = _find_pagination_info(val)
                    if result is not None:
                        return result
            return None

        has_next = _find_pagination_info(body)
        if has_next is not None:
            return has_next

        # pagination 정보 없으면 아이템 수로 추정 (20개 이상이면 다음 페이지 있을 수 있음)
        return items_count >= 20

    @staticmethod
    def _find_product_array(body) -> list | None:
        """중첩된 JSON 구조에서 작품 배열을 재귀적으로 탐색"""
        if isinstance(body, list) and len(body) > 0:
            return body
        if isinstance(body, dict):
            # 일반적인 키들 우선 탐색
            for key in ("data", "products", "items", "result", "list", "content", "rows"):
                if key in body:
                    found = ArtistWebSession._find_product_array(body[key])
                    if found:
                        return found
            # 나머지 값들 탐색
            for val in body.values():
                if isinstance(val, (list, dict)):
                    found = ArtistWebSession._find_product_array(val)
                    if found and len(found) >= 2:
                        return found
        return None

    async def _load_remaining_pages(self, status: str) -> list[ProductSummary]:
        """스크롤 또는 페이지 버튼으로 나머지 페이지 로드"""
        all_remaining = []
        max_scrolls = 30

        for i in range(max_scrolls):
            captured = []

            async def on_resp(response):
                try:
                    if response.status == 200 and "paging" in response.url and "idus" in response.url:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct:
                            body = await response.json()
                            captured.append(body)
                except Exception:
                    pass

            self.page.on("response", on_resp)
            try:
                # 스크롤 다운으로 다음 페이지 트리거
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
            finally:
                self.page.remove_listener("response", on_resp)

            if not captured:
                break  # 더 이상 API 호출 없음

            for body in captured:
                items = self._find_product_array(body)
                if items:
                    products = self._parse_api_items(items, status)
                    all_remaining.extend(products)
                    logger.info(f"[추가 페이지] {len(products)}개 추출 (누적: {len(all_remaining)})")

                    if not self._check_has_next_page(body, i + 1, len(items)):
                        return all_remaining

        return all_remaining

    async def _scroll_to_load_all(self):
        """무한스크롤 페이지에서 모든 작품을 로드"""
        prev_height = 0
        scroll_attempts = 0
        max_scrolls = 20

        while scroll_attempts < max_scrolls:
            current_height = await self.page.evaluate("document.body.scrollHeight")
            if current_height == prev_height:
                break
            prev_height = current_height
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            scroll_attempts += 1

        await self.page.evaluate("window.scrollTo(0, 0)")
        logger.debug(f"스크롤 완료: {scroll_attempts}회")

    async def get_page_debug_info(self) -> dict:
        """현재 페이지의 디버깅 정보 반환 (HTML 구조 분석용)"""
        if not self.page:
            return {"error": "페이지 없음"}

        return await self.page.evaluate("""
            () => {
                // 모든 product 링크 수집
                const productLinks = document.querySelectorAll('a[href*="/product/"]');
                const linkInfo = Array.from(productLinks).slice(0, 5).map(link => ({
                    href: link.getAttribute('href'),
                    text: link.textContent.trim().substring(0, 100),
                    hasImg: !!link.querySelector('img'),
                    parentClasses: link.parentElement?.className || '',
                    grandparentClasses: link.parentElement?.parentElement?.className || '',
                }));

                // 페이지의 주요 구조 요소
                const mainContent = document.querySelector('main, [role="main"], #root, #app, #__next');
                const firstLevelChildren = mainContent
                    ? Array.from(mainContent.children).slice(0, 10).map(c => ({
                        tag: c.tagName,
                        classes: c.className,
                        childCount: c.children.length,
                    }))
                    : [];

                return {
                    url: window.location.href,
                    title: document.title,
                    productLinkCount: productLinks.length,
                    sampleLinks: linkInfo,
                    structure: firstLevelChildren,
                    bodyTextPreview: document.body.innerText.substring(0, 2000),
                };
            }
        """)

    async def navigate_to_product(self, product_id: str) -> bool:
        """
        작품 수정 페이지로 이동

        Args:
            product_id: 작품 UUID

        Returns:
            이동 성공 여부
        """
        if not await self.is_authenticated():
            raise Exception("로그인이 필요합니다")

        url = f"{settings.artist_web_base_url}/product/{product_id}"

        try:
            await self.page.goto(url, timeout=settings.page_load_timeout)
            await self.page.wait_for_load_state("domcontentloaded")
            # SPA 렌더링 대기 — networkidle 대신 고정 대기
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"작품 페이지 로딩 중 타임아웃 (재시도): {e}")
            try:
                # 재시도: 이미 네비게이션 진행 중이므로 load만 대기
                await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
            except Exception as e2:
                logger.error(f"작품 페이지 로딩 재시도도 실패: {e2}")

        # 추가 SPA 렌더링 대기 — 주요 콘텐츠 요소 탐색
        try:
            await self.page.wait_for_selector(
                'input, textarea, [contenteditable], img[src*="idus"]',
                timeout=10000,
            )
        except Exception:
            logger.warning("작품 페이지 콘텐츠 요소 대기 타임아웃 (계속 진행)")

        # 페이지 로딩 확인
        success = "product" in self.page.url
        if success:
            logger.info(f"작품 페이지 이동 성공: {product_id}")
        else:
            logger.warning(f"작품 페이지 이동 실패: {product_id} → {self.page.url}")
        return success

    async def close(self):
        """세션 정리"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"세션 정리 중 오류: {e}")
        finally:
            self._authenticated = False
            self._initialized = False
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            logger.info("작가웹 세션 종료")

    @staticmethod
    def _parse_price(price_text: str) -> int:
        """가격 텍스트를 정수로 변환 ('10,000원' → 10000)"""
        digits = re.sub(r'[^\d]', '', price_text)
        return int(digits) if digits else 0
