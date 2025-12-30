"""
아이디어스(Idus) 상품 크롤링 모듈
Playwright + playwright-stealth를 사용하여 봇 탐지 우회
"""
import asyncio
import re
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from playwright_stealth import stealth_async

from .models import ProductData, ProductOption, ImageText


class IdusScraper:
    """아이디어스 상품 페이지 크롤러"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        
    async def initialize(self):
        """Playwright 브라우저 초기화"""
        self.playwright = await async_playwright().start()
        
        # Chromium 브라우저 실행 (headless 모드)
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--single-process',  # Railway 환경 호환성
            ]
        )
        
        # 브라우저 컨텍스트 생성 (모바일 에뮬레이션 대신 데스크톱)
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ko-KR',
        )
        
    async def close(self):
        """브라우저 리소스 정리"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def _create_stealth_page(self) -> Page:
        """Stealth 모드가 적용된 페이지 생성"""
        if not self.context:
            raise RuntimeError("브라우저가 초기화되지 않았습니다.")
            
        page = await self.context.new_page()
        
        # playwright-stealth 적용 (봇 탐지 우회)
        await stealth_async(page)
        
        return page
    
    async def scrape_product(self, url: str) -> ProductData:
        """
        상품 페이지 크롤링 메인 함수
        
        Args:
            url: 아이디어스 상품 URL
            
        Returns:
            ProductData: 크롤링된 상품 데이터
        """
        page = await self._create_stealth_page()
        
        try:
            # 페이지 로드
            print(f"📄 페이지 로딩 중: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # 추가 대기 (동적 콘텐츠 로딩)
            await asyncio.sleep(2)
            
            # 기본 정보 추출
            title = await self._extract_title(page)
            artist_name = await self._extract_artist_name(page)
            price = await self._extract_price(page)
            description = await self._extract_description(page)
            
            # 옵션 추출 (버튼 클릭 후)
            options = await self._extract_options(page)
            
            # 상세 이미지 URL 추출
            detail_images = await self._extract_detail_images(page)
            
            print(f"✅ 크롤링 완료: {title}")
            
            return ProductData(
                url=url,
                title=title,
                artist_name=artist_name,
                price=price,
                description=description,
                options=options,
                detail_images=detail_images,
                image_texts=[]  # OCR은 translator에서 처리
            )
            
        finally:
            await page.close()
    
    async def _extract_title(self, page: Page) -> str:
        """상품명 추출"""
        selectors = [
            'h1[class*="title"]',
            '[class*="product-title"]',
            '[class*="productName"]',
            'h1',
            '[data-testid="product-title"]',
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and len(text.strip()) > 0:
                        return text.strip()
            except:
                continue
                
        return "제목 없음"
    
    async def _extract_artist_name(self, page: Page) -> str:
        """작가명 추출"""
        selectors = [
            '[class*="artist"]',
            '[class*="seller"]',
            '[class*="shop-name"]',
            '[class*="brand"]',
            'a[href*="/artist/"]',
            'a[href*="/shop/"]',
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and len(text.strip()) > 0:
                        return text.strip()
            except:
                continue
                
        return "작가명 없음"
    
    async def _extract_price(self, page: Page) -> str:
        """가격 추출"""
        selectors = [
            '[class*="price"]',
            '[class*="cost"]',
            '[data-testid="price"]',
        ]
        
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    # 숫자와 원/₩이 포함된 텍스트 찾기
                    if text and re.search(r'[\d,]+\s*(원|₩)', text):
                        return text.strip()
            except:
                continue
                
        return "가격 정보 없음"
    
    async def _extract_description(self, page: Page) -> str:
        """상품 설명 추출"""
        selectors = [
            '[class*="description"]',
            '[class*="product-info"]',
            '[class*="detail-text"]',
            '[class*="content"]',
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and len(text.strip()) > 50:  # 최소 50자 이상
                        return text.strip()[:2000]  # 최대 2000자
            except:
                continue
                
        return "설명 없음"
    
    async def _extract_options(self, page: Page) -> list[ProductOption]:
        """
        옵션 추출 - '옵션 선택' 버튼 클릭하여 숨겨진 옵션 표시
        """
        options = []
        
        # 옵션 선택 버튼 클릭 시도
        option_button_selectors = [
            'button:has-text("옵션 선택")',
            'button:has-text("옵션")',
            '[class*="option"] button',
            '[class*="select-option"]',
            'button[class*="option"]',
        ]
        
        for selector in option_button_selectors:
            try:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    await asyncio.sleep(1)  # 옵션 로딩 대기
                    print("🔘 옵션 버튼 클릭 완료")
                    break
            except:
                continue
        
        # 옵션 그룹 찾기
        option_group_selectors = [
            '[class*="option-group"]',
            '[class*="option-item"]',
            '[class*="select-wrap"]',
            'select',
            '[role="listbox"]',
        ]
        
        for selector in option_group_selectors:
            try:
                groups = await page.query_selector_all(selector)
                
                for group in groups:
                    # 옵션 이름 추출
                    name_element = await group.query_selector('[class*="label"], [class*="title"], label')
                    option_name = "옵션"
                    if name_element:
                        option_name = (await name_element.inner_text()).strip()
                    
                    # 옵션 값들 추출
                    values = []
                    
                    # select 태그인 경우
                    if await group.evaluate('el => el.tagName') == 'SELECT':
                        option_elements = await group.query_selector_all('option')
                        for opt in option_elements:
                            value = await opt.inner_text()
                            if value and value.strip() and value.strip() != '선택하세요':
                                values.append(value.strip())
                    else:
                        # 일반 요소인 경우
                        value_elements = await group.query_selector_all('[class*="value"], [class*="option-text"], li, span')
                        for val_el in value_elements:
                            value = await val_el.inner_text()
                            if value and value.strip():
                                values.append(value.strip())
                    
                    if values:
                        options.append(ProductOption(
                            name=option_name,
                            values=list(set(values))  # 중복 제거
                        ))
                        
            except Exception as e:
                print(f"옵션 추출 중 오류: {e}")
                continue
        
        # 옵션 모달/드롭다운에서도 추출 시도
        try:
            # 모달이 열려있는 경우 옵션 값 추출
            modal_options = await page.query_selector_all('[class*="modal"] [class*="option"], [class*="dropdown"] [class*="item"]')
            
            if modal_options:
                modal_values = []
                for opt in modal_options:
                    text = await opt.inner_text()
                    if text and text.strip():
                        modal_values.append(text.strip())
                
                if modal_values and not any(o.name == "상품 옵션" for o in options):
                    options.append(ProductOption(
                        name="상품 옵션",
                        values=modal_values
                    ))
        except:
            pass
        
        return options
    
    async def _extract_detail_images(self, page: Page) -> list[str]:
        """상세 이미지 URL 추출"""
        images = []
        
        # 상세 이미지 영역 셀렉터
        detail_selectors = [
            '[class*="detail"] img',
            '[class*="description"] img',
            '[class*="content"] img',
            '[class*="product-info"] img',
            'article img',
        ]
        
        for selector in detail_selectors:
            try:
                img_elements = await page.query_selector_all(selector)
                
                for img in img_elements:
                    # src 또는 data-src 속성 추출
                    src = await img.get_attribute('src')
                    if not src:
                        src = await img.get_attribute('data-src')
                    if not src:
                        src = await img.get_attribute('data-lazy-src')
                    
                    if src:
                        # 유효한 이미지 URL인지 확인
                        if src.startswith('http') and not src.endswith('.svg'):
                            # 작은 아이콘 제외 (최소 크기 체크)
                            try:
                                width = await img.get_attribute('width')
                                height = await img.get_attribute('height')
                                if width and height:
                                    if int(width) < 100 or int(height) < 100:
                                        continue
                            except:
                                pass
                            
                            if src not in images:
                                images.append(src)
                                
            except Exception as e:
                print(f"이미지 추출 중 오류: {e}")
                continue
        
        print(f"📷 {len(images)}개의 상세 이미지 발견")
        return images[:20]  # 최대 20개까지만


# 테스트용 코드
if __name__ == "__main__":
    async def test():
        scraper = IdusScraper()
        await scraper.initialize()
        
        # 테스트 URL (실제 아이디어스 URL로 교체 필요)
        test_url = "https://www.idus.com/v2/product/example"
        
        try:
            result = await scraper.scrape_product(test_url)
            print(f"제목: {result.title}")
            print(f"작가: {result.artist_name}")
            print(f"가격: {result.price}")
            print(f"옵션: {result.options}")
            print(f"이미지 수: {len(result.detail_images)}")
        finally:
            await scraper.close()
    
    asyncio.run(test())

