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

        전략 1: 네트워크 API 응답 가로채기 (SPA 백엔드 API)
        전략 2: DOM 스크래핑 폴백 (개선된 셀렉터)

        Args:
            status: "selling" | "paused" | "draft"

        Returns:
            ProductSummary 목록
        """
        if not await self.is_authenticated():
            raise Exception("로그인이 필요합니다")

        # 상태에 따른 URL
        url_map = {
            "selling": "/product/list",
            "paused": "/product/list/pause",
            "draft": "/product/list/draft",
        }
        target_url = f"{settings.artist_web_base_url}{url_map.get(status, '/product/list')}"

        # 전략 1: 네트워크 API 응답 가로채기
        api_products = []
        captured_responses = []

        async def capture_product_api(response):
            """작품 목록 API 응답을 캡처"""
            try:
                url = response.url
                # 작가웹이 내부적으로 호출하는 API 패턴 매칭
                if response.status == 200 and any(
                    pattern in url for pattern in [
                        "/api/product", "/product/list", "/products",
                        "/api/v1/product", "/api/v2/product",
                        "product", "artwork",
                    ]
                ):
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type:
                        body = await response.json()
                        captured_responses.append({"url": url, "body": body})
                        logger.debug(f"API 응답 캡처: {url}")
            except Exception:
                pass

        self.page.on("response", capture_product_api)

        try:
            await self.page.goto(target_url, timeout=settings.page_load_timeout)
            await self.page.wait_for_load_state("networkidle")
            # SPA 렌더링 대기
            await asyncio.sleep(2)

            # 캡처된 API 응답에서 작품 데이터 추출 시도
            api_products = self._extract_from_api_responses(captured_responses, status)
            if api_products:
                logger.info(f"[API 캡처] 작품 {len(api_products)}개 추출 ({status})")
                return api_products

        except Exception as e:
            logger.warning(f"API 캡처 방식 실패: {e}")
        finally:
            self.page.remove_listener("response", capture_product_api)

        # 전략 2: 개선된 DOM 스크래핑
        logger.info("DOM 스크래핑으로 전환...")

        # 페이지가 이미 로드되지 않았다면 다시 이동
        if "product" not in self.page.url:
            await self.page.goto(target_url, timeout=settings.page_load_timeout)
            await self.page.wait_for_load_state("networkidle")

        # 동적 콘텐츠 로딩 대기 - 다양한 셀렉터 시도
        await self._wait_for_product_elements()

        # 스크롤하여 모든 작품 로드 (무한스크롤 대응)
        await self._scroll_to_load_all()

        products_raw = await self.page.evaluate("""
            () => {
                const results = [];

                // 전략 A: 링크 기반 추출 — /product/UUID 패턴의 모든 링크 탐색
                const allLinks = document.querySelectorAll('a[href*="/product/"]');
                const seenIds = new Set();

                for (const link of allLinks) {
                    const href = link.getAttribute('href') || '';
                    const idMatch = href.match(/\\/product\\/([a-f0-9-]{36})/);
                    if (!idMatch) continue;

                    const productId = idMatch[1];
                    if (seenIds.has(productId)) continue;
                    seenIds.add(productId);

                    // 이 링크를 포함하는 가장 가까운 카드/컨테이너 찾기
                    const card = link.closest('[class*="card"], [class*="Card"], [class*="item"], [class*="Item"], [class*="product"], [class*="Product"], li, article, div[class]')
                        || link.parentElement?.parentElement || link.parentElement;

                    if (!card) continue;

                    // 제목 추출
                    const titleEl = card.querySelector('[class*="title"], [class*="name"], [class*="Title"], [class*="Name"], h3, h4, strong');
                    let title = titleEl ? titleEl.textContent.trim() : '';
                    if (!title) {
                        // 카드 내 텍스트에서 추출 시도
                        const texts = Array.from(card.querySelectorAll('span, p, div'))
                            .map(el => el.textContent.trim())
                            .filter(t => t.length > 5 && t.length < 100);
                        title = texts[0] || '';
                    }

                    // 가격 추출
                    const priceEl = card.querySelector('[class*="price"], [class*="Price"]');
                    let priceText = priceEl ? priceEl.textContent.trim() : '';
                    if (!priceText) {
                        // 원 단위 텍스트 검색
                        const allText = card.textContent;
                        const priceMatch = allText.match(/([\\d,]+)\\s*원/);
                        priceText = priceMatch ? priceMatch[0] : '0';
                    }

                    // 썸네일 추출
                    const imgEl = card.querySelector('img');
                    const thumbnailUrl = imgEl ? (imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '') : '';

                    // 글로벌 뱃지 확인
                    const cardText = card.textContent || '';
                    const hasGlobal = cardText.includes('글로벌')
                        || !!card.querySelector('[class*="global"], [class*="Global"]');

                    results.push({
                        product_id: productId,
                        title: title,
                        price_text: priceText,
                        thumbnail_url: thumbnailUrl,
                        has_global: hasGlobal,
                    });
                }

                // 전략 B: 결과가 없으면 더 넓은 범위로 재시도
                if (results.length === 0) {
                    // 페이지 내 UUID 패턴 모두 추출
                    const bodyHtml = document.body.innerHTML;
                    const uuidRegex = /([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/g;
                    const uuids = [...new Set(bodyHtml.match(uuidRegex) || [])];

                    for (const uuid of uuids) {
                        if (!seenIds.has(uuid)) {
                            results.push({
                                product_id: uuid,
                                title: '',
                                price_text: '0',
                                thumbnail_url: '',
                                has_global: false,
                            });
                        }
                    }
                }

                return results;
            }
        """)

        # 디버깅: DOM 스크래핑도 실패한 경우 페이지 정보 로깅
        if not products_raw:
            page_info = await self.page.evaluate("""
                () => ({
                    url: window.location.href,
                    title: document.title,
                    bodyLength: document.body.innerHTML.length,
                    linkCount: document.querySelectorAll('a').length,
                    imgCount: document.querySelectorAll('img').length,
                    bodyPreview: document.body.innerText.substring(0, 500),
                })
            """)
            logger.warning(f"DOM 스크래핑 결과 0건. 페이지 정보: {page_info}")

        # ProductSummary로 변환
        result = []
        for p in products_raw:
            result.append(ProductSummary(
                product_id=p["product_id"],
                title=p.get("title", ""),
                price=self._parse_price(p.get("price_text", "0")),
                thumbnail_url=p.get("thumbnail_url"),
                status=ProductStatus(status),
                global_status=(
                    GlobalStatus.REGISTERED if p.get("has_global")
                    else GlobalStatus.NOT_REGISTERED
                ),
            ))

        logger.info(f"[DOM 스크래핑] 작품 {len(result)}개 추출 ({status})")
        return result

    def _extract_from_api_responses(
        self, responses: list[dict], status: str
    ) -> list[ProductSummary]:
        """캡처된 API 응답에서 작품 목록을 추출"""
        for resp in responses:
            body = resp.get("body")
            if not body:
                continue

            # 다양한 API 응답 구조 처리
            items = None
            if isinstance(body, list):
                items = body
            elif isinstance(body, dict):
                # { data: [...] }, { products: [...] }, { items: [...] }, { result: [...] }
                for key in ("data", "products", "items", "result", "list", "content"):
                    if key in body and isinstance(body[key], list):
                        items = body[key]
                        break
                # 중첩 구조: { data: { list: [...] } }
                if not items and "data" in body and isinstance(body["data"], dict):
                    for key in ("list", "products", "items", "content"):
                        if key in body["data"] and isinstance(body["data"][key], list):
                            items = body["data"][key]
                            break

            if not items or len(items) == 0:
                continue

            # 작품 데이터인지 확인 (UUID 또는 product_id 필드 존재)
            result = []
            for item in items:
                if not isinstance(item, dict):
                    continue

                product_id = (
                    item.get("product_id")
                    or item.get("productId")
                    or item.get("uuid")
                    or item.get("id", "")
                )
                if not product_id or not isinstance(product_id, str):
                    continue

                # UUID 형식 검증 (loose)
                if len(str(product_id)) < 8:
                    continue

                title = (
                    item.get("title")
                    or item.get("name")
                    or item.get("productName")
                    or item.get("product_name", "")
                )
                price = item.get("price") or item.get("salePrice") or item.get("sale_price") or 0
                if isinstance(price, str):
                    price = self._parse_price(price)

                thumbnail = (
                    item.get("thumbnail_url")
                    or item.get("thumbnailUrl")
                    or item.get("image")
                    or item.get("imageUrl")
                    or item.get("representative_image")
                )

                has_global = bool(
                    item.get("global_status")
                    or item.get("globalStatus")
                    or item.get("hasGlobal")
                    or item.get("is_global")
                )

                result.append(ProductSummary(
                    product_id=str(product_id),
                    title=str(title),
                    price=int(price) if price else 0,
                    thumbnail_url=thumbnail,
                    status=ProductStatus(status),
                    global_status=(
                        GlobalStatus.REGISTERED if has_global
                        else GlobalStatus.NOT_REGISTERED
                    ),
                ))

            if result:
                logger.info(f"API 응답에서 {len(result)}개 작품 추출 (URL: {resp.get('url', '?')})")
                return result

        return []

    async def _wait_for_product_elements(self):
        """작품 목록 요소가 로딩될 때까지 대기"""
        selectors_to_try = [
            'a[href*="/product/"]',
            '[class*="product"]',
            '[class*="Product"]',
            '[class*="card"]',
            '[class*="Card"]',
            'img',
        ]
        for selector in selectors_to_try:
            try:
                await self.page.wait_for_selector(selector, timeout=5000)
                logger.debug(f"셀렉터 발견: {selector}")
                return
            except Exception:
                continue

        # 모든 셀렉터 실패 시 추가 대기
        logger.warning("작품 요소 셀렉터를 찾지 못함, 추가 대기 3초...")
        await asyncio.sleep(3)

    async def _scroll_to_load_all(self):
        """무한스크롤 페이지에서 모든 작품을 로드"""
        prev_height = 0
        scroll_attempts = 0
        max_scrolls = 20  # 최대 20회 스크롤

        while scroll_attempts < max_scrolls:
            current_height = await self.page.evaluate("document.body.scrollHeight")
            if current_height == prev_height:
                break

            prev_height = current_height
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            scroll_attempts += 1

        # 맨 위로 복귀
        await self.page.evaluate("window.scrollTo(0, 0)")
        logger.debug(f"스크롤 완료: {scroll_attempts}회")

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
        await self.page.goto(url, timeout=settings.page_load_timeout)
        await self.page.wait_for_load_state("networkidle")

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
