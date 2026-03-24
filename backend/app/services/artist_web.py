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

        전략 1: 네트워크 API 응답 가로채기 (idus.com 도메인 한정)
        전략 2: DOM 스크래핑 (링크 그룹핑 방식)

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

        # ── 전략 1: 네트워크 API 응답 가로채기 ──
        captured_responses = []

        async def capture_api(response):
            """idus.com 도메인의 JSON 응답만 캡처"""
            try:
                url = response.url
                # idus.com 도메인 API만 캡처 (자체 백엔드 제외)
                if response.status == 200 and "idus.com" in url:
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type:
                        body = await response.json()
                        captured_responses.append({"url": url, "body": body})
                        logger.info(f"[API 캡처] URL: {url}, type: {type(body).__name__}")
            except Exception:
                pass

        self.page.on("response", capture_api)

        try:
            await self.page.goto(target_url, timeout=settings.page_load_timeout)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            # 캡처된 응답에서 작품 데이터 추출
            api_products = self._extract_from_api_responses(captured_responses, status)
            if api_products:
                logger.info(f"[API 캡처 성공] {len(api_products)}개 작품 ({status})")
                return api_products
            else:
                logger.info(f"[API 캡처] 작품 데이터 없음. 캡처된 응답 {len(captured_responses)}건")
                for r in captured_responses[:5]:
                    logger.info(f"  - {r['url']}")

        except Exception as e:
            logger.warning(f"API 캡처 실패: {e}")
        finally:
            self.page.remove_listener("response", capture_api)

        # ── 전략 2: DOM 스크래핑 (링크 그룹핑 방식) ──
        logger.info("DOM 스크래핑으로 전환...")

        if "product" not in self.page.url:
            await self.page.goto(target_url, timeout=settings.page_load_timeout)
            await self.page.wait_for_load_state("networkidle")

        # 콘텐츠 로딩 대기
        try:
            await self.page.wait_for_selector(
                'a[href*="/product/"]', timeout=10000
            )
        except Exception:
            logger.warning("작품 링크 요소를 찾지 못함")

        # 무한스크롤 대응
        await self._scroll_to_load_all()

        # 핵심 변경: 링크를 UUID 별로 그룹핑하여 추출
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

                    // 제목: 텍스트가 있는 링크에서 추출 (이미지만 있는 링크 제외)
                    let title = '';
                    for (const link of links) {
                        const text = link.textContent.trim();
                        // 통계 라벨이 아닌, 의미 있는 텍스트
                        if (text && text.length > 3
                            && !text.match(/^(남은수량|주문시|후기|판매수|찜|\\d)/)
                            && !text.match(/^\\d+[%원개건]/)
                        ) {
                            title = text;
                            break;
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
                        // 두 링크의 공통 조상 탐색
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
                        // 링크 1개인 경우, 3단계 상위 탐색
                        card = links[0].parentElement?.parentElement?.parentElement
                            || links[0].parentElement?.parentElement
                            || links[0].parentElement;
                    }

                    // 가격: 카드 내에서 "X,XXX원" 패턴 매칭
                    let priceText = '0';
                    if (card) {
                        // 가격 요소를 직접 찾기
                        const priceEl = card.querySelector('[class*="price"], [class*="Price"]');
                        if (priceEl) {
                            const match = priceEl.textContent.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                            priceText = match ? match[0] : '0';
                        } else {
                            // 카드 텍스트에서 첫 번째 가격 패턴 매칭
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

    def _extract_from_api_responses(
        self, responses: list[dict], status: str
    ) -> list[ProductSummary]:
        """캡처된 API 응답에서 작품 목록을 추출"""
        for resp in responses:
            body = resp.get("body")
            if not body:
                continue

            # 다양한 API 응답 구조에서 배열 추출
            items = self._find_product_array(body)
            if not items or len(items) < 2:
                continue

            # 작품 데이터인지 확인
            result = []
            for item in items:
                if not isinstance(item, dict):
                    continue

                # UUID 형식의 ID 필드 탐색
                product_id = None
                for key in ("product_id", "productId", "uuid", "id"):
                    val = item.get(key)
                    if val and isinstance(val, str) and len(val) >= 32:
                        product_id = val
                        break

                if not product_id:
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
                    or item.get("thumbnail")
                    or item.get("img")
                )

                has_global = bool(
                    item.get("global_status")
                    or item.get("globalStatus")
                    or item.get("hasGlobal")
                    or item.get("is_global")
                )

                result.append(ProductSummary(
                    product_id=str(product_id),
                    title=str(title) if title else "",
                    price=int(price) if price else 0,
                    thumbnail_url=str(thumbnail) if thumbnail else None,
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
