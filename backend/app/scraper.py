"""
아이디어스(Idus) 상품 크롤링 모듈
모든 상세 이미지 수집 - 필터링 최소화
"""
import asyncio
import re
import os
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from playwright_stealth import stealth_async

from .models import ProductData, ProductOption


class IdusScraper:
    """아이디어스 상품 페이지 크롤러"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        self._initialized = False
        
    async def initialize(self):
        if self._initialized:
            return
            
        print("🔧 Playwright 브라우저 초기화 중...")
        
        try:
            self.playwright = await async_playwright().start()
            
            is_docker = os.path.exists('/.dockerenv') or os.getenv('RAILWAY_ENVIRONMENT')
            
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
            ]
            
            if is_docker:
                launch_args.append('--single-process')
                print("🐳 Docker 환경 감지됨")
            
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=launch_args
            )
            
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='ko-KR',
            )
            
            self._initialized = True
            print("✅ Playwright 브라우저 초기화 완료")
            
        except Exception as e:
            print(f"❌ Playwright 초기화 실패: {e}")
            raise
        
    async def close(self):
        print("🔧 Playwright 브라우저 종료 중...")
        if self.context:
            try: await self.context.close()
            except: pass
        if self.browser:
            try: await self.browser.close()
            except: pass
        if self.playwright:
            try: await self.playwright.stop()
            except: pass
        self._initialized = False
        print("✅ Playwright 브라우저 종료 완료")
    
    async def scrape_product(self, url: str) -> ProductData:
        if not self._initialized:
            await self.initialize()
        
        print(f"📄 크롤링 시작: {url}")
        
        page = await self.context.new_page()
        await stealth_async(page)
        
        # 네트워크에서 이미지 URL 수집
        network_images: set[str] = set()
        
        def on_response(response):
            try:
                resp_url = response.url
                # 이미지 응답 또는 Idus 이미지 CDN
                if response.request.resource_type == "image":
                    if resp_url.startswith('http'):
                        network_images.add(resp_url)
                elif 'image.idus.com' in resp_url and resp_url.startswith('http'):
                    network_images.add(resp_url)
            except:
                pass
        
        page.on("response", on_response)
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)
            
            # 1. 기본 정보 추출
            title = await self._get_title(page)
            artist_name = await self._get_artist(page)
            price = await self._get_price(page)
            description = await self._get_description(page)
            options = await self._get_options(page)
            
            # 2. 이미지 수집 - 스크롤하면서 모든 이미지 로드
            print("📜 페이지 스크롤 시작...")
            await self._scroll_entire_page(page)
            print("📜 페이지 스크롤 완료")
            
            # 3. DOM에서 모든 이미지 URL 수집
            dom_images = await self._collect_all_image_urls(page)
            
            # 4. 모든 이미지 합치기 (네트워크 + DOM)
            all_images = list(network_images) + dom_images
            
            # 5. 최소한의 필터링만 적용 (아이콘/로고만 제외)
            filtered = self._minimal_filter(all_images)
            
            print(f"✅ 크롤링 완료: {title}")
            print(f"   - 작가: {artist_name}")
            print(f"   - 가격: {price}")
            print(f"   - 옵션: {len(options)}개")
            print(f"   - 이미지: {len(filtered)}개 (네트워크: {len(network_images)}, DOM: {len(dom_images)})")
            
            return ProductData(
                url=url,
                title=title,
                artist_name=artist_name,
                price=price,
                description=description,
                options=options,
                detail_images=filtered,
                image_texts=[]
            )
            
        finally:
            await page.close()

    async def _get_title(self, page: Page) -> str:
        try:
            title = await page.title()
            if title:
                clean = title.replace(" | 아이디어스", "").strip()
                if clean and len(clean) >= 3:
                    return clean
        except: pass
        return "제목 없음"

    async def _get_artist(self, page: Page) -> str:
        try:
            link = await page.query_selector('a[href*="/artist/"]')
            if link:
                text = (await link.inner_text() or "").strip()
                if 2 <= len(text) <= 50:
                    return text
        except: pass
        return "작가명 없음"

    async def _get_price(self, page: Page) -> str:
        try:
            result = await page.evaluate("""
                () => {
                    const els = document.querySelectorAll('[class*="price"], [class*="Price"]');
                    for (const el of els) {
                        const m = (el.innerText || '').match(/[\\d,]+\\s*원/);
                        if (m) return m[0];
                    }
                    return null;
                }
            """)
            if result: return result
        except: pass
        return "가격 정보 없음"

    async def _get_description(self, page: Page) -> str:
        # 탭 클릭 시도
        try:
            for sel in ['text="작품정보"', 'text="상품정보"', 'text="상세정보"']:
                tab = await page.query_selector(sel)
                if tab:
                    await tab.click()
                    await asyncio.sleep(1)
                    break
        except: pass
        
        try:
            text = await page.evaluate("""
                () => {
                    const selectors = ['article', '[class*="detail"]', '[class*="description"]', '[class*="content"]', 'main'];
                    let longest = '';
                    for (const sel of selectors) {
                        document.querySelectorAll(sel).forEach(el => {
                            const t = el.innerText || '';
                            if (t.length > longest.length && t.length > 100) {
                                // 노이즈 필터
                                if (!t.includes('로그인') && !t.includes('장바구니')) {
                                    longest = t;
                                }
                            }
                        });
                    }
                    return longest || null;
                }
            """)
            if text:
                return text[:6000]
        except: pass
        return "설명 없음"

    async def _get_options(self, page: Page) -> list[ProductOption]:
        options_dict: dict[str, set[str]] = {}
        
        try:
            # 후기에서 옵션 추출
            texts = await page.evaluate("""
                () => {
                    const result = [];
                    document.querySelectorAll('a, span, div, p').forEach(el => {
                        const t = el.innerText || '';
                        if (t.includes('구매작품') && t.includes(':')) result.push(t);
                    });
                    return result;
                }
            """)
            
            for text in texts:
                for part in text.split("구매작품")[1:]:
                    for opt in part.split("*"):
                        match = re.search(r':\s*([^:]+):\s*([^*]+)', opt)
                        if match:
                            name = match.group(1).strip()
                            value = match.group(2).strip()
                            if name and value:
                                options_dict.setdefault(name, set()).add(value)
        except: pass
        
        return [ProductOption(name=n, values=list(v)) for n, v in options_dict.items() if v]

    async def _scroll_entire_page(self, page: Page):
        """페이지 전체를 천천히 스크롤하여 모든 lazy-load 이미지 로드"""
        try:
            # 총 페이지 높이
            total = await page.evaluate("document.body.scrollHeight")
            current = 0
            step = 300  # 300px씩 스크롤
            
            while current < total:
                await page.evaluate(f"window.scrollTo(0, {current})")
                await asyncio.sleep(0.25)  # 이미지 로드 대기
                current += step
                
                # 동적 콘텐츠로 높이가 늘어났는지 확인
                new_total = await page.evaluate("document.body.scrollHeight")
                if new_total > total:
                    total = new_total
            
            # 맨 아래에서 잠시 대기 (마지막 이미지 로드)
            await asyncio.sleep(1.5)
            
            # 맨 위로 돌아가기
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"스크롤 오류: {e}")

    async def _collect_all_image_urls(self, page: Page) -> list[str]:
        """DOM에서 모든 이미지 URL 수집"""
        try:
            urls = await page.evaluate("""
                () => {
                    const urls = [];
                    
                    // 1. img 태그
                    document.querySelectorAll('img').forEach(img => {
                        if (img.src && img.src.startsWith('http')) urls.push(img.src);
                        
                        // data-* 속성
                        ['data-src', 'data-original', 'data-lazy-src', 'data-url'].forEach(attr => {
                            const val = img.getAttribute(attr);
                            if (val && val.startsWith('http')) urls.push(val);
                        });
                        
                        // srcset
                        const srcset = img.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(part => {
                                const url = part.trim().split(' ')[0];
                                if (url && url.startsWith('http')) urls.push(url);
                            });
                        }
                    });
                    
                    // 2. source 태그
                    document.querySelectorAll('source').forEach(src => {
                        const srcset = src.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(part => {
                                const url = part.trim().split(' ')[0];
                                if (url && url.startsWith('http')) urls.push(url);
                            });
                        }
                    });
                    
                    // 3. background-image
                    document.querySelectorAll('*').forEach(el => {
                        try {
                            const bg = getComputedStyle(el).backgroundImage;
                            if (bg && bg !== 'none') {
                                const match = bg.match(/url\\(['"]?(https?:\\/\\/[^'"\\)]+)['"]?\\)/);
                                if (match) urls.push(match[1]);
                            }
                        } catch(e) {}
                    });
                    
                    // 4. a 태그의 href (이미지 링크)
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.getAttribute('href');
                        if (href && /\\.(jpg|jpeg|png|webp|gif)(\\?|$)/i.test(href)) {
                            if (href.startsWith('http')) urls.push(href);
                        }
                    });
                    
                    return urls;
                }
            """)
            return urls or []
        except Exception as e:
            print(f"이미지 수집 오류: {e}")
            return []

    def _minimal_filter(self, images: list[str]) -> list[str]:
        """
        최소한의 필터링 - 명백한 아이콘/로고만 제외
        중복 제거는 정확한 URL 기준으로만
        """
        # 확실히 제외할 패턴만 (매우 보수적)
        exclude = [
            '/icon', '/sprite', '/logo', '/avatar', '/badge', '/emoji',
            '/button', '/arrow', '/check/', '/close/', '/menu/', '/search/',
            'facebook.', 'twitter.', 'instagram.', 'kakao.', 'naver.',
            'google.com', 'apple.com', 'play.google',
            '/qr', '/escrow', '/membership',
            'data:image',  # base64 인라인 이미지
        ]
        
        result = []
        seen = set()  # 정확한 URL 중복 제거
        
        for img in images:
            if not img or not img.startswith('http'):
                continue
            
            # 정확한 URL 중복 체크
            if img in seen:
                continue
            seen.add(img)
            
            low = img.lower()
            
            # SVG 제외
            if '.svg' in low:
                continue
            
            # 명백한 제외 패턴만 체크
            skip = False
            for pattern in exclude:
                if pattern in low:
                    skip = True
                    break
            if skip:
                continue
            
            # 이미지 확장자 또는 Idus CDN이면 포함
            is_image = any(ext in low for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif'])
            is_idus = 'idus.com' in low
            
            if is_image or is_idus:
                result.append(img)
        
        print(f"📷 필터링: {len(images)}개 → {len(result)}개")
        return result[:150]  # 최대 150개


if __name__ == "__main__":
    async def test():
        scraper = IdusScraper()
        await scraper.initialize()
        try:
            result = await scraper.scrape_product(
                "https://www.idus.com/v2/product/87beb859-49b2-4c18-86b4-f300b31d6247"
            )
            print(f"\n제목: {result.title}")
            print(f"이미지: {len(result.detail_images)}개")
            for i, img in enumerate(result.detail_images[:10]):
                print(f"  {i+1}. {img[:80]}...")
        finally:
            await scraper.close()
    
    asyncio.run(test())
