"""
작가웹(artist.idus.com) 브라우저 세션 관리
Playwright 기반의 인증 및 네비게이션
"""
import asyncio
import re
import logging
import time
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
        self._product_list_cache: dict = {}  # {status: (timestamp, products)}
        self._saved_email: Optional[str] = None
        self._saved_password: Optional[str] = None

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
            logger.info(f"로그인 시도: {settings.artist_web_base_url}/login")
            await self.page.goto(
                f"{settings.artist_web_base_url}/login",
                timeout=settings.page_load_timeout,
            )
            # networkidle 대신 domcontentloaded 사용 (더 빠름)
            await self.page.wait_for_load_state("domcontentloaded")
            logger.info(f"로그인 페이지 로드 완료: {self.page.url}")

            # 이메일 입력
            email_input = self.page.locator('input[type="email"], input[name="email"]')
            await email_input.wait_for(state="visible", timeout=15000)
            await email_input.fill(email)
            logger.info("이메일 입력 완료")

            # 비밀번호 입력
            password_input = self.page.locator('input[type="password"], input[name="password"]')
            await password_input.wait_for(state="visible", timeout=5000)
            await password_input.fill(password)
            logger.info("비밀번호 입력 완료")

            # 로그인 버튼 클릭
            login_button = self.page.locator(
                'button:has-text("로그인"), button[type="submit"]'
            ).first
            await login_button.wait_for(state="visible", timeout=5000)
            await login_button.click()
            logger.info("로그인 버튼 클릭 완료")

            # 로그인 성공 확인 (URL 변경 대기 — 30초)
            await self.page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=30000,
            )
            logger.info(f"로그인 후 URL: {self.page.url}")
            self._authenticated = True
            # 자동 재로그인용 인증 정보 저장 (컨테이너 재시작 대비)
            self._saved_email = email
            self._saved_password = password
            logger.info("작가웹 로그인 성공")
            return True

        except Exception as e:
            logger.error(f"작가웹 로그인 실패: {e}")
            self._authenticated = False
            return False

    async def is_authenticated(self) -> bool:
        """인증 상태 확인 + 자동 재로그인 (컨테이너 재시작 대비)"""
        if self._authenticated and self.page is not None:
            return True

        # 저장된 인증 정보가 있으면 자동 재로그인 시도
        if self._saved_email and self._saved_password:
            logger.info("세션 만료 감지 — 저장된 인증 정보로 자동 재로그인 시도")
            try:
                # 브라우저가 없으면 재초기화
                if not self.page or not self._initialized:
                    self._initialized = False  # 재초기화 허용
                    await self.initialize()
                return await self.login(self._saved_email, self._saved_password)
            except Exception as e:
                logger.error(f"자동 재로그인 실패: {e}")
                return False

        return False

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

        # ── 캐시 확인 ──
        CACHE_TTL = 300  # 5분

        cache_key = status
        if cache_key in self._product_list_cache:
            cached_time, cached_products = self._product_list_cache[cache_key]
            if time.time() - cached_time < CACHE_TTL:
                logger.info(f"[캐시 히트] {len(cached_products)}개 작품 ({status})")
                return cached_products

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
                self._product_list_cache[cache_key] = (time.time(), all_products)
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
        self._product_list_cache[cache_key] = (time.time(), result)
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

            # ── 확정된 idus API 필드 매핑 ──
            # product_uuid: UUID 문자열
            product_id = (
                item.get("product_uuid")
                or item.get("uuid")
                or item.get("product_id")
                or item.get("productId")
            )
            if not product_id:
                # 폴백: id가 있으면 문자열로
                raw_id = item.get("id")
                if raw_id:
                    product_id = str(raw_id)
            if not product_id:
                continue

            # name: 작품 제목
            title = (
                item.get("name")
                or item.get("title")
                or item.get("productName")
                or ""
            )

            # original_price: 원래 가격 (sales_price는 할인가)
            price = item.get("original_price") or item.get("sales_price") or item.get("price") or 0
            if isinstance(price, str):
                price = self._parse_price(price)

            # main_image: 대표 이미지 URL
            thumbnail = (
                item.get("main_image")
                or item.get("thumbnail_url")
                or item.get("image")
                or item.get("imageUrl")
            )

            # 글로벌 등록 상태: global_meta.status 또는 badges 배열
            has_global = False
            # 1) global_meta 객체 확인
            global_meta = item.get("global_meta")
            if isinstance(global_meta, dict):
                gm_status = global_meta.get("status", "")
                has_global = gm_status.upper() in ("SALE", "PAUSE", "DRAFT")
            # 2) badges 배열에 "GLOBAL" 포함 여부
            if not has_global:
                badges = item.get("badges", [])
                if isinstance(badges, list):
                    has_global = "GLOBAL" in badges

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

        return result

    @staticmethod
    def _check_has_next_page(body: dict, current_page: int, items_count: int) -> bool:
        """API 응답에서 다음 페이지 존재 여부 확인"""
        if not isinstance(body, dict):
            return items_count >= 20  # 기본 페이지 사이즈 추정

        # idus 응답 구조: paging_cursor, total_products 확인
        total_products = body.get("total_products", 0)
        if total_products and isinstance(total_products, int):
            loaded = (current_page + 1) * max(items_count, 20)
            if loaded >= total_products:
                return False
            return True

        paging_cursor = body.get("paging_cursor")
        if paging_cursor is not None:
            # 커서가 있으면 다음 페이지 존재
            return bool(paging_cursor)

        # 다양한 구조 대응
        def _find_pagination_info(obj):
            if not isinstance(obj, dict):
                return None
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
            # idus API 확정 키 + 일반적인 키들
            for key in ("paging_products", "data", "products", "items", "result", "list", "content", "rows"):
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
        """스크롤로 나머지 페이지 로드 — expect_response로 API 응답 대기"""
        all_remaining = []
        empty_count = 0  # 연속 빈 응답 카운터

        for i in range(30):
            try:
                # 스크롤 후 paging API 응답을 명시적으로 대기 (최대 5초)
                async with self.page.expect_response(
                    lambda r: "paging" in r.url and r.status == 200,
                    timeout=5000
                ) as response_info:
                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

                response = await response_info.value
                body = await response.json()
                items = self._find_product_array(body)

                if items:
                    products = self._parse_api_items(items, status)
                    all_remaining.extend(products)
                    empty_count = 0
                    logger.info(f"[추가 페이지] {len(products)}개 추출 (누적: {len(all_remaining)})")

                    if not self._check_has_next_page(body, i + 1, len(items)):
                        break
                else:
                    empty_count += 1

            except Exception:
                empty_count += 1

            if empty_count >= 2:
                logger.info(f"[추가 페이지] 2회 연속 빈 응답 → 페이지네이션 종료 (누적: {len(all_remaining)})")
                break

            await asyncio.sleep(1)

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

        # 이미 해당 작품 페이지에 있으면 네비게이션 스킵
        if product_id in (self.page.url or ""):
            logger.info(f"이미 작품 페이지에 위치: {product_id}")
            # 이미 있어도 Vuex 데이터 로딩 대기
            await self._wait_for_vuex_product_data(product_id)
            return True

        # 전체 URL로 네비게이션 (상대 경로 X)
        full_url = f"{settings.artist_web_base_url}/product/{product_id}"
        logger.info(f"작품 페이지 이동: {full_url}")

        try:
            await self.page.goto(full_url, timeout=settings.page_load_timeout)
            await self.page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            logger.warning(f"page.goto 실패 (계속 진행): {e}")

        # Vuex 데이터 로딩 대기 (이미지 포함)
        await self._wait_for_vuex_product_data(product_id)

        success = "product" in self.page.url
        if success:
            logger.info(f"작품 페이지 이동 성공: {product_id}")
        else:
            logger.warning(f"작품 페이지 이동 실패: {product_id} → {self.page.url}")
        return success

    async def _wait_for_vuex_product_data(self, product_id: str):
        """Vuex productForm._item에 이미지 데이터가 로딩될 때까지 대기"""
        for attempt in range(20):  # 최대 20초 대기
            try:
                status = await self.page.evaluate("""
                    () => {
                        const app = document.querySelector('#app');
                        if (!app || !app.__vue__ || !app.__vue__.$store) return { ready: false, reason: 'no_store' };
                        const item = app.__vue__.$store.state.productForm?._item;
                        if (!item || !item.id || item.id === 0) return { ready: false, reason: 'no_item' };
                        const hasImages = Array.isArray(item.images) && item.images.length > 0;
                        return {
                            ready: hasImages,
                            reason: hasImages ? 'ok' : 'no_images',
                            id: item.id,
                            imageCount: Array.isArray(item.images) ? item.images.length : 0,
                            name: (item.productName || '').substring(0, 30),
                        };
                    }
                """)

                if status and status.get("ready"):
                    logger.info(
                        f"[Vuex 대기] 완료 — 시도 {attempt + 1}, "
                        f"이미지 {status.get('imageCount')}개, "
                        f"제목: {status.get('name')}"
                    )
                    return

                if attempt % 5 == 4:
                    logger.info(f"[Vuex 대기] 진행 중... 시도 {attempt + 1}, 상태: {status}")

            except Exception as e:
                if attempt == 0:
                    logger.warning(f"[Vuex 대기] evaluate 오류: {e}")

            await asyncio.sleep(1)

        logger.warning(f"[Vuex 대기] 20초 타임아웃 — 이미지 없이 계속 진행")

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
