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

        await self.page.goto(target_url, timeout=settings.page_load_timeout)
        await self.page.wait_for_load_state("networkidle")

        # 작품 목록 추출 (JavaScript 실행)
        products_raw = await self.page.evaluate("""
            () => {
                const cards = document.querySelectorAll(
                    '[class*="product"], [class*="Product"], tr[class*="row"], [data-product-id]'
                );
                return Array.from(cards).map(card => {
                    const link = card.querySelector('a[href*="/product/"]');
                    const href = link ? link.getAttribute('href') : '';
                    const idMatch = href ? href.match(/\\/product\\/([a-f0-9-]+)/) : null;
                    const id = idMatch ? idMatch[1] : '';
                    const title = (
                        card.querySelector('[class*="title"], [class*="name"]')
                        || card.querySelector('td:nth-child(2)')
                    );
                    const titleText = title ? title.textContent.trim() : '';
                    const price = card.querySelector('[class*="price"]');
                    const priceText = price ? price.textContent.trim() : '';

                    // 글로벌 뱃지 확인
                    const globalBadge = card.querySelector(
                        '[class*="global"], [class*="Global"], .badge'
                    );
                    const hasGlobal = globalBadge
                        ? globalBadge.textContent.includes('글로벌') || globalBadge.textContent.includes('EN') || globalBadge.textContent.includes('JP')
                        : false;

                    return {
                        product_id: id,
                        title: titleText,
                        price_text: priceText,
                        has_global: hasGlobal,
                    };
                }).filter(p => p.product_id);
            }
        """)

        # ProductSummary로 변환
        result = []
        for p in products_raw:
            result.append(ProductSummary(
                product_id=p["product_id"],
                title=p.get("title", ""),
                price=self._parse_price(p.get("price_text", "0")),
                status=ProductStatus(status),
                global_status=(
                    GlobalStatus.REGISTERED if p.get("has_global")
                    else GlobalStatus.NOT_REGISTERED
                ),
            ))

        logger.info(f"작품 목록 조회 완료: {len(result)}개 ({status})")
        return result

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
