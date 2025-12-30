"""
아이디어스(Idus) 상품 크롤링 모듈
Playwright + 정확한 셀렉터 기반 데이터 추출
"""
import asyncio
import json
import re
import os
from typing import Optional, Any
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from playwright_stealth import stealth_async

from .models import ProductData, ProductOption, ImageText


class IdusScraper:
    """아이디어스 상품 페이지 크롤러"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        self._initialized = False
        
    async def initialize(self):
        """Playwright 브라우저 초기화"""
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
            await self._cleanup()
            raise
        
    async def _cleanup(self):
        """리소스 정리"""
        if self.context:
            try:
                await self.context.close()
            except:
                pass
            self.context = None
            
        if self.browser:
            try:
                await self.browser.close()
            except:
                pass
            self.browser = None
            
        if self.playwright:
            try:
                await self.playwright.stop()
            except:
                pass
            self.playwright = None
            
        self._initialized = False
        
    async def close(self):
        """브라우저 리소스 정리"""
        print("🔧 Playwright 브라우저 종료 중...")
        await self._cleanup()
        print("✅ Playwright 브라우저 종료 완료")
            
    async def _create_stealth_page(self) -> Page:
        """Stealth 모드가 적용된 페이지 생성"""
        if not self.context:
            raise RuntimeError("브라우저가 초기화되지 않았습니다.")
            
        page = await self.context.new_page()
        await stealth_async(page)
        return page
    
    async def scrape_product(self, url: str) -> ProductData:
        """상품 페이지 크롤링"""
        if not self._initialized:
            await self.initialize()
        
        print(f"📄 크롤링 시작: {url}")
        
        page = await self._create_stealth_page()
        
        # 이미지 URL 수집을 위한 네트워크 응답 캡처
        image_urls_from_network: list[str] = []
        
        def handle_response(response):
            try:
                if response.request.resource_type == "image":
                    img_url = response.url
                    if img_url.startswith('http') and 'idus' in img_url.lower():
                        image_urls_from_network.append(img_url)
            except:
                pass
        
        page.on("response", handle_response)
        
        try:
            # 페이지 로드
            await page.goto(url, wait_until='networkidle', timeout=45000)
            await asyncio.sleep(3)
            
            # 1. 상품명: 페이지 타이틀에서 추출 (가장 정확함)
            title = await self._extract_title_from_page(page)
            
            # 2. 작가명 추출
            artist_name = await self._extract_artist_name(page)
            
            # 3. 가격 추출
            price = await self._extract_price(page)
            
            # 4. 상품 설명 추출
            description = await self._extract_description(page)
            
            # 5. 옵션 추출 (후기에서 + 인터랙티브)
            options = await self._extract_options_complete(page)
            
            # 6. 이미지 추출
            await self._scroll_for_images(page)
            detail_images = await self._extract_product_images(page)
            
            # 네트워크에서 수집한 이미지 추가
            all_images = list(dict.fromkeys(detail_images + image_urls_from_network))
            
            # 이미지 필터링
            filtered_images = self._filter_product_images(all_images)
            
            print(f"✅ 크롤링 완료: {title}")
            print(f"   - 작가: {artist_name}")
            print(f"   - 가격: {price}")
            print(f"   - 옵션: {len(options)}개 그룹")
            print(f"   - 이미지: {len(filtered_images)}개")
            
            return ProductData(
                url=url,
                title=title,
                artist_name=artist_name,
                price=price,
                description=description,
                options=options,
                detail_images=filtered_images,
                image_texts=[]
            )
            
        finally:
            try:
                page.remove_listener("response", handle_response)
            except:
                pass
            await page.close()

    async def _extract_title_from_page(self, page: Page) -> str:
        """페이지 타이틀에서 상품명 추출"""
        try:
            # 방법 1: 페이지 타이틀에서 추출 (가장 정확)
            full_title = await page.title()
            if full_title:
                # " | 아이디어스" 제거
                title = full_title.replace(" | 아이디어스", "").strip()
                if title and len(title) >= 3:
                    print(f"📌 타이틀에서 상품명 추출: {title}")
                    return title
        except:
            pass
        
        # 방법 2: meta og:title에서 추출
        try:
            og_title = await page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[property="og:title"]');
                    return meta ? meta.getAttribute('content') : null;
                }
            """)
            if og_title:
                title = og_title.replace(" | 아이디어스", "").strip()
                if title and len(title) >= 3:
                    return title
        except:
            pass
        
        # 방법 3: h1 태그에서 추출
        try:
            h1 = await page.query_selector('h1')
            if h1:
                text = (await h1.inner_text() or "").strip()
                if text and len(text) >= 3:
                    return text
        except:
            pass
        
        return "제목 없음"

    async def _extract_artist_name(self, page: Page) -> str:
        """작가명 추출"""
        try:
            # 방법 1: href에 /artist/ 포함된 링크에서 추출
            artist_link = await page.query_selector('a[href*="/artist/"]')
            if artist_link:
                text = (await artist_link.inner_text() or "").strip()
                # 너무 긴 텍스트나 UI 텍스트 제외
                if text and 2 <= len(text) <= 50 and "바로가기" not in text:
                    print(f"📌 작가명 추출: {text}")
                    return text
        except:
            pass
        
        try:
            # 방법 2: class에 artist/seller/shop 포함된 요소에서 추출
            for sel in ['[class*="artist"]', '[class*="seller"]', '[class*="shop-name"]']:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text() or "").strip()
                    if text and 2 <= len(text) <= 50:
                        return text
        except:
            pass
        
        return "작가명 없음"

    async def _extract_price(self, page: Page) -> str:
        """가격 추출"""
        try:
            # 방법 1: 가격 패턴이 있는 텍스트 찾기
            price_text = await page.evaluate("""
                () => {
                    // 가격 관련 클래스를 가진 요소들에서 찾기
                    const selectors = [
                        '[class*="price"]',
                        '[class*="Price"]',
                        '[class*="cost"]',
                        '[class*="sale"]'
                    ];
                    
                    for (const sel of selectors) {
                        const els = document.querySelectorAll(sel);
                        for (const el of els) {
                            const text = el.innerText || '';
                            // 숫자,원 또는 숫자₩ 패턴 매칭
                            const match = text.match(/[\\d,]+\\s*원|₩\\s*[\\d,]+/);
                            if (match) {
                                return match[0];
                            }
                        }
                    }
                    
                    // 전체 페이지에서 가격 패턴 찾기
                    const body = document.body.innerText || '';
                    const allPrices = body.match(/[\\d,]{4,}\\s*원/g);
                    if (allPrices && allPrices.length > 0) {
                        return allPrices[0];
                    }
                    
                    return null;
                }
            """)
            
            if price_text:
                return price_text.strip()
        except:
            pass
        
        return "가격 정보 없음"

    async def _extract_description(self, page: Page) -> str:
        """상품 설명 추출"""
        try:
            # meta description에서 추출
            meta_desc = await page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[name="description"]');
                    if (meta) {
                        return meta.getAttribute('content');
                    }
                    const ogDesc = document.querySelector('meta[property="og:description"]');
                    if (ogDesc) {
                        return ogDesc.getAttribute('content');
                    }
                    return null;
                }
            """)
            
            if meta_desc and len(meta_desc) > 20:
                return meta_desc.strip()[:4000]
        except:
            pass
        
        try:
            # description 클래스 요소에서 추출
            for sel in ['[class*="description"]', '[class*="detail"]', '[class*="content"]']:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text() or "").strip()
                    # UI 텍스트가 아닌 실제 설명인지 확인
                    if len(text) > 100 and "로그인" not in text and "회원가입" not in text:
                        return text[:4000]
        except:
            pass
        
        return "설명 없음"

    async def _extract_options_complete(self, page: Page) -> list[ProductOption]:
        """옵션 추출 - 후기 + 인터랙티브 방식 결합"""
        options = []
        
        # 방법 1: 후기에서 "구매작품 :" 패턴으로 옵션 추출
        review_options = await self._extract_options_from_reviews(page)
        if review_options:
            options.extend(review_options)
            print(f"📌 후기에서 옵션 {len(review_options)}개 그룹 추출")
        
        # 방법 2: 인터랙티브 방식 (버튼 클릭)
        if not options:
            interactive_options = await self._extract_options_interactive(page)
            if interactive_options:
                options.extend(interactive_options)
                print(f"📌 인터랙티브 방식으로 옵션 {len(interactive_options)}개 그룹 추출")
        
        return options

    async def _extract_options_from_reviews(self, page: Page) -> list[ProductOption]:
        """후기에서 옵션 정보 추출"""
        options_dict: dict[str, set[str]] = {}
        
        try:
            # 후기 텍스트에서 "구매작품 :" 패턴 찾기
            review_texts = await page.evaluate("""
                () => {
                    const texts = [];
                    // 모든 링크/텍스트에서 "구매작품" 패턴 찾기
                    const elements = document.querySelectorAll('a, span, div, p');
                    for (const el of elements) {
                        const text = el.innerText || '';
                        if (text.includes('구매작품') && text.includes(':')) {
                            texts.push(text);
                        }
                    }
                    return texts;
                }
            """)
            
            for text in review_texts:
                # "구매작품 : 옵션명: 옵션값" 패턴 파싱
                # 예: "구매작품 : 쿠키 선택: 용감한 쿠키 (노랑술) * 쿠키 선택: 세인트릴리 쿠키 (파랑술)"
                if "구매작품" in text:
                    # "구매작품 :" 이후 부분 추출
                    parts = text.split("구매작품")
                    for part in parts[1:]:
                        # ": 옵션명: 옵션값" 형식 파싱
                        # 여러 옵션이 "*"로 구분될 수 있음
                        option_parts = part.split("*")
                        for opt_part in option_parts:
                            # "옵션명: 옵션값" 파싱
                            match = re.search(r':\s*([^:]+):\s*(.+?)(?:\s*\*|$)', opt_part)
                            if match:
                                opt_name = match.group(1).strip()
                                opt_value = match.group(2).strip()
                                if opt_name and opt_value:
                                    options_dict.setdefault(opt_name, set()).add(opt_value)
                            else:
                                # 단순 "옵션명: 옵션값" 형식
                                simple_match = re.search(r':\s*([^:]+):\s*(.+)', opt_part)
                                if simple_match:
                                    opt_name = simple_match.group(1).strip()
                                    opt_value = simple_match.group(2).strip()
                                    # 다음 "*" 전까지만
                                    opt_value = opt_value.split("*")[0].strip()
                                    if opt_name and opt_value:
                                        options_dict.setdefault(opt_name, set()).add(opt_value)
        except Exception as e:
            print(f"후기 옵션 추출 오류: {e}")
        
        # dict를 ProductOption 리스트로 변환
        return [
            ProductOption(name=name, values=list(values))
            for name, values in options_dict.items()
            if values
        ]

    async def _extract_options_interactive(self, page: Page) -> list[ProductOption]:
        """인터랙티브 방식으로 옵션 추출"""
        options = []
        
        # 옵션 선택 트리거 클릭 시도
        triggers = [
            'button:has-text("옵션")',
            'button:has-text("선택")',
            '[aria-haspopup="listbox"]',
            '[role="combobox"]',
        ]
        
        for trigger in triggers:
            try:
                el = await page.query_selector(trigger)
                if el:
                    # 요소가 화면에 보이는지 확인
                    box = await el.bounding_box()
                    if not box:
                        continue
                    
                    await el.click()
                    await asyncio.sleep(0.8)
                    
                    # 옵션 패널에서 값 수집
                    panel_options = await self._collect_real_options(page)
                    if panel_options:
                        options.extend(panel_options)
                    
                    # 패널 닫기
                    try:
                        await page.keyboard.press("Escape")
                    except:
                        pass
                    await asyncio.sleep(0.3)
                    
                    if options:
                        break
            except:
                continue
        
        return options

    async def _collect_real_options(self, page: Page) -> list[ProductOption]:
        """실제 옵션 값만 수집 (UI 노이즈 제외)"""
        options = []
        
        # UI 노이즈 텍스트 목록
        noise_texts = {
            '아이디어스 앱 설치하기', '전송', '로그인', '회원가입', '고객센터',
            '관심', '내 정보', '도움이 돼요', '등록', '아이디어스 채팅 상담',
            '선택', '선택하세요', '옵션 선택', '장바구니', '구매하기', '선물하기',
            '옵션을 선택해주세요', '필수', '선택완료', '확인', '취소', '닫기'
        }
        
        try:
            # 다이얼로그/시트/드롭다운 찾기
            panel_selectors = [
                '[role="dialog"]',
                '[role="listbox"]',
                '[class*="modal"]',
                '[class*="sheet"]',
                '[class*="bottom"]',
                '[class*="dropdown"]',
            ]
            
            panel = None
            for sel in panel_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        box = await el.bounding_box()
                        if box and box['height'] > 100:
                            panel = el
                            break
                except:
                    continue
            
            if not panel:
                return options
            
            # 옵션 아이템 수집
            items = await panel.query_selector_all('[role="option"], li, button')
            
            values = []
            for item in items[:50]:
                try:
                    text = (await item.inner_text() or "").strip()
                    if not text:
                        continue
                    
                    # 멀티라인이면 첫 줄만
                    if '\n' in text:
                        text = text.split('\n')[0].strip()
                    
                    # 노이즈 필터링
                    if text in noise_texts:
                        continue
                    if any(noise in text for noise in ['로그인', '회원가입', '설치하기', '고객센터']):
                        continue
                    if len(text) > 80:
                        continue
                    if len(text) < 2:
                        continue
                    
                    values.append(text)
                except:
                    continue
            
            values = list(dict.fromkeys(values))
            
            if values and len(values) >= 2:
                options.append(ProductOption(name="옵션", values=values))
        
        except Exception as e:
            print(f"옵션 수집 오류: {e}")
        
        return options

    async def _scroll_for_images(self, page: Page):
        """이미지 로딩을 위한 스크롤"""
        try:
            for _ in range(20):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
                await asyncio.sleep(0.25)
            
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
        except:
            pass

    async def _extract_product_images(self, page: Page) -> list[str]:
        """상품 이미지 URL 추출"""
        images = []
        
        try:
            # JavaScript로 모든 이미지 URL 추출
            all_images = await page.evaluate("""
                () => {
                    const urls = new Set();
                    
                    // img 태그에서 추출
                    document.querySelectorAll('img').forEach(img => {
                        // src
                        if (img.src && img.src.startsWith('http')) {
                            urls.add(img.src);
                        }
                        // data-src (lazy loading)
                        const dataSrc = img.getAttribute('data-src');
                        if (dataSrc && dataSrc.startsWith('http')) {
                            urls.add(dataSrc);
                        }
                        // srcset
                        const srcset = img.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(part => {
                                const url = part.trim().split(' ')[0];
                                if (url && url.startsWith('http')) {
                                    urls.add(url);
                                }
                            });
                        }
                    });
                    
                    // source 태그에서 추출
                    document.querySelectorAll('source').forEach(src => {
                        const srcset = src.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(part => {
                                const url = part.trim().split(' ')[0];
                                if (url && url.startsWith('http')) {
                                    urls.add(url);
                                }
                            });
                        }
                    });
                    
                    // background-image에서 추출
                    document.querySelectorAll('[style*="background"]').forEach(el => {
                        const style = el.getAttribute('style') || '';
                        const matches = style.match(/url\\(['\"]?(https?:\\/\\/[^'\"\\)]+)['\"]?\\)/gi);
                        if (matches) {
                            matches.forEach(m => {
                                const url = m.replace(/url\\(['\"]?|['\"]?\\)/gi, '');
                                urls.add(url);
                            });
                        }
                    });
                    
                    return Array.from(urls);
                }
            """)
            
            images = all_images or []
            
        except Exception as e:
            print(f"이미지 추출 오류: {e}")
        
        return images

    def _filter_product_images(self, images: list[str]) -> list[str]:
        """상품 관련 이미지만 필터링"""
        filtered = []
        
        # 제외할 패턴
        exclude_patterns = [
            'icon', 'sprite', 'logo', 'avatar', 'badge', 'emoji',
            'button', 'arrow', 'check', 'close', 'menu', 'search',
            'facebook', 'twitter', 'instagram', 'kakao', 'naver',
            'google', 'apple', 'play', 'app-store',
            'banner-image', 'escrow', 'membership'
        ]
        
        for img in images:
            if not img or not img.startswith('http'):
                continue
            
            low = img.lower()
            
            # SVG 제외
            if low.endswith('.svg'):
                continue
            
            # 아이콘/로고 등 제외
            if any(pattern in low for pattern in exclude_patterns):
                continue
            
            # Idus 상품 이미지 CDN 패턴 확인
            if 'idus' in low or 'image.idus.com' in low:
                # 너무 작은 썸네일 제외 (100px 이하)
                if '_100.' in low or '/100.' in low:
                    continue
                filtered.append(img)
            elif any(ext in low for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                filtered.append(img)
        
        # 중복 제거 및 제한
        filtered = list(dict.fromkeys(filtered))
        return filtered[:80]


# 테스트용 코드
if __name__ == "__main__":
    async def test():
        scraper = IdusScraper()
        await scraper.initialize()
        
        test_url = "https://www.idus.com/v2/product/87beb859-49b2-4c18-86b4-f300b31d6247"
        
        try:
            result = await scraper.scrape_product(test_url)
            print(f"\n===== 결과 =====")
            print(f"제목: {result.title}")
            print(f"작가: {result.artist_name}")
            print(f"가격: {result.price}")
            print(f"옵션: {result.options}")
            print(f"이미지 수: {len(result.detail_images)}")
        finally:
            await scraper.close()
    
    asyncio.run(test())
