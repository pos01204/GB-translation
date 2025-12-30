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
        image_urls_from_network: set[str] = set()
        
        def handle_response(response):
            try:
                url_lower = response.url.lower()
                # 이미지 리소스 또는 Idus CDN 이미지
                if response.request.resource_type == "image" or 'image.idus.com' in url_lower:
                    if response.url.startswith('http'):
                        image_urls_from_network.add(response.url)
            except:
                pass
        
        page.on("response", handle_response)
        
        try:
            # 페이지 로드
            await page.goto(url, wait_until='networkidle', timeout=45000)
            await asyncio.sleep(3)
            
            # 1. 상품명
            title = await self._extract_title_from_page(page)
            
            # 2. 작가명
            artist_name = await self._extract_artist_name(page)
            
            # 3. 가격
            price = await self._extract_price(page)
            
            # 4. 상품 설명
            description = await self._extract_description(page)
            
            # 5. 옵션
            options = await self._extract_options_complete(page)
            
            # 6. 이미지 - 충분히 스크롤하여 모든 이미지 로드
            await self._scroll_page_fully(page)
            dom_images = await self._extract_all_images(page)
            
            # 네트워크에서 수집한 이미지 추가
            all_images = list(dict.fromkeys(dom_images + list(image_urls_from_network)))
            
            # 이미지 필터링 (아이콘/로고만 제외, 나머지는 모두 포함)
            filtered_images = self._filter_images_simple(all_images)
            
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
            full_title = await page.title()
            if full_title:
                title = full_title.replace(" | 아이디어스", "").strip()
                if title and len(title) >= 3:
                    print(f"📌 타이틀에서 상품명 추출: {title}")
                    return title
        except:
            pass
        
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
            artist_link = await page.query_selector('a[href*="/artist/"]')
            if artist_link:
                text = (await artist_link.inner_text() or "").strip()
                if text and 2 <= len(text) <= 50 and "바로가기" not in text:
                    print(f"📌 작가명 추출: {text}")
                    return text
        except:
            pass
        
        try:
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
            price_text = await page.evaluate("""
                () => {
                    const selectors = ['[class*="price"]', '[class*="Price"]', '[class*="cost"]', '[class*="sale"]'];
                    for (const sel of selectors) {
                        const els = document.querySelectorAll(sel);
                        for (const el of els) {
                            const text = el.innerText || '';
                            const match = text.match(/[\\d,]+\\s*원|₩\\s*[\\d,]+/);
                            if (match) return match[0];
                        }
                    }
                    const body = document.body.innerText || '';
                    const allPrices = body.match(/[\\d,]{4,}\\s*원/g);
                    if (allPrices && allPrices.length > 0) return allPrices[0];
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
        descriptions = []
        
        try:
            tab_selectors = ['text="작품정보"', 'text="상품정보"', 'text="상세정보"']
            for sel in tab_selectors:
                tab = await page.query_selector(sel)
                if tab:
                    await tab.click()
                    await asyncio.sleep(1)
                    print("📌 상세 정보 탭 클릭")
                    break
        except:
            pass
        
        try:
            detail_text = await page.evaluate("""
                () => {
                    const texts = [];
                    const detailSelectors = ['article', '[class*="detail"]', '[class*="description"]', '[class*="content"]', '[class*="info"]', '[class*="story"]', 'main'];
                    const noisePatterns = ['로그인', '회원가입', '장바구니', '구매하기', '선물하기', '고객센터', '아이디어스 앱', '카카오', '네이버', '이용약관', '개인정보', '결제', '배송'];
                    
                    for (const selector of detailSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            const text = el.innerText || '';
                            if (text.length < 50) continue;
                            let isNoise = false;
                            for (const noise of noisePatterns) {
                                if (text.includes(noise) && text.length < 200) { isNoise = true; break; }
                            }
                            if (isNoise) continue;
                            if (text.includes('POINT') || text.includes('특징') || text.includes('소개') || text.includes('안내') || text.includes('사용') || text.includes('주의')) {
                                texts.unshift(text);
                            } else {
                                texts.push(text);
                            }
                        }
                    }
                    if (texts.length > 0) {
                        texts.sort((a, b) => b.length - a.length);
                        return texts[0];
                    }
                    return null;
                }
            """)
            if detail_text and len(detail_text) > 50:
                descriptions.append(detail_text)
                print(f"📌 상세 설명 추출: {len(detail_text)}자")
        except Exception as e:
            print(f"상세 설명 추출 오류: {e}")
        
        try:
            meta_desc = await page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[name="description"]');
                    if (meta) return meta.getAttribute('content');
                    const ogDesc = document.querySelector('meta[property="og:description"]');
                    if (ogDesc) return ogDesc.getAttribute('content');
                    return null;
                }
            """)
            if meta_desc and len(meta_desc) > 20:
                descriptions.append(meta_desc)
        except:
            pass
        
        if descriptions:
            descriptions.sort(key=len, reverse=True)
            return descriptions[0][:6000]
        return "설명 없음"

    async def _extract_options_complete(self, page: Page) -> list[ProductOption]:
        """옵션 추출"""
        options = []
        
        review_options = await self._extract_options_from_reviews(page)
        if review_options:
            options.extend(review_options)
            print(f"📌 후기에서 옵션 {len(review_options)}개 그룹 추출")
        
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
            review_texts = await page.evaluate("""
                () => {
                    const texts = [];
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
                if "구매작품" in text:
                    parts = text.split("구매작품")
                    for part in parts[1:]:
                        option_parts = part.split("*")
                        for opt_part in option_parts:
                            match = re.search(r':\s*([^:]+):\s*(.+?)(?:\s*\*|$)', opt_part)
                            if match:
                                opt_name = match.group(1).strip()
                                opt_value = match.group(2).strip()
                                if opt_name and opt_value:
                                    options_dict.setdefault(opt_name, set()).add(opt_value)
                            else:
                                simple_match = re.search(r':\s*([^:]+):\s*(.+)', opt_part)
                                if simple_match:
                                    opt_name = simple_match.group(1).strip()
                                    opt_value = simple_match.group(2).strip().split("*")[0].strip()
                                    if opt_name and opt_value:
                                        options_dict.setdefault(opt_name, set()).add(opt_value)
        except Exception as e:
            print(f"후기 옵션 추출 오류: {e}")
        
        return [ProductOption(name=name, values=list(values)) for name, values in options_dict.items() if values]

    async def _extract_options_interactive(self, page: Page) -> list[ProductOption]:
        """인터랙티브 방식으로 옵션 추출"""
        options = []
        triggers = ['button:has-text("옵션")', 'button:has-text("선택")', '[aria-haspopup="listbox"]', '[role="combobox"]']
        
        for trigger in triggers:
            try:
                el = await page.query_selector(trigger)
                if el:
                    box = await el.bounding_box()
                    if not box:
                        continue
                    await el.click()
                    await asyncio.sleep(0.8)
                    panel_options = await self._collect_real_options(page)
                    if panel_options:
                        options.extend(panel_options)
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
        """실제 옵션 값만 수집"""
        options = []
        noise_texts = {'아이디어스 앱 설치하기', '전송', '로그인', '회원가입', '고객센터', '관심', '내 정보', '도움이 돼요', '등록', '아이디어스 채팅 상담', '선택', '선택하세요', '옵션 선택', '장바구니', '구매하기', '선물하기', '옵션을 선택해주세요', '필수', '선택완료', '확인', '취소', '닫기'}
        
        try:
            panel_selectors = ['[role="dialog"]', '[role="listbox"]', '[class*="modal"]', '[class*="sheet"]', '[class*="bottom"]', '[class*="dropdown"]']
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
            
            items = await panel.query_selector_all('[role="option"], li, button')
            values = []
            for item in items[:50]:
                try:
                    text = (await item.inner_text() or "").strip()
                    if not text:
                        continue
                    if '\n' in text:
                        text = text.split('\n')[0].strip()
                    if text in noise_texts:
                        continue
                    if any(noise in text for noise in ['로그인', '회원가입', '설치하기', '고객센터']):
                        continue
                    if len(text) > 80 or len(text) < 2:
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

    async def _scroll_page_fully(self, page: Page):
        """페이지 전체를 천천히 스크롤하여 모든 이미지 로드"""
        try:
            # 먼저 전체 페이지 높이 확인
            total_height = await page.evaluate("document.body.scrollHeight")
            viewport_height = await page.evaluate("window.innerHeight")
            
            print(f"📜 스크롤 시작 (페이지 높이: {total_height}px)")
            
            # 400px씩 스크롤 (더 세밀하게)
            current = 0
            while current < total_height + viewport_height:
                await page.evaluate(f"window.scrollTo(0, {current})")
                await asyncio.sleep(0.3)
                current += 400
                
                # 동적 콘텐츠로 높이가 늘어났는지 확인
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height > total_height:
                    total_height = new_height
            
            # 끝에서 잠시 대기
            await asyncio.sleep(1)
            
            # 맨 위로
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
            
            print(f"📜 스크롤 완료")
        except Exception as e:
            print(f"스크롤 오류: {e}")

    async def _extract_all_images(self, page: Page) -> list[str]:
        """모든 이미지 URL 추출"""
        images = []
        
        try:
            all_urls = await page.evaluate("""
                () => {
                    const urls = new Set();
                    
                    // 1. img 태그
                    document.querySelectorAll('img').forEach(img => {
                        if (img.src && img.src.startsWith('http')) urls.add(img.src);
                        const dataSrc = img.getAttribute('data-src');
                        if (dataSrc && dataSrc.startsWith('http')) urls.add(dataSrc);
                        const dataOriginal = img.getAttribute('data-original');
                        if (dataOriginal && dataOriginal.startsWith('http')) urls.add(dataOriginal);
                        
                        // srcset
                        const srcset = img.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(part => {
                                const url = part.trim().split(' ')[0];
                                if (url && url.startsWith('http')) urls.add(url);
                            });
                        }
                    });
                    
                    // 2. source 태그
                    document.querySelectorAll('source').forEach(source => {
                        const srcset = source.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(part => {
                                const url = part.trim().split(' ')[0];
                                if (url && url.startsWith('http')) urls.add(url);
                            });
                        }
                    });
                    
                    // 3. background-image
                    document.querySelectorAll('*').forEach(el => {
                        try {
                            const style = getComputedStyle(el);
                            const bg = style.backgroundImage;
                            if (bg && bg !== 'none') {
                                const match = bg.match(/url\\(['"]?(https?:\\/\\/[^'"\\)]+)['"]?\\)/);
                                if (match && match[1]) urls.add(match[1]);
                            }
                        } catch(e) {}
                    });
                    
                    return Array.from(urls);
                }
            """)
            
            images = all_urls or []
            print(f"📷 DOM에서 {len(images)}개 이미지 수집")
            
        except Exception as e:
            print(f"이미지 추출 오류: {e}")
        
        return images

    def _filter_images_simple(self, images: list[str]) -> list[str]:
        """
        이미지 필터링 (단순화)
        - 명확한 제외 패턴만 제외
        - 중복 제거는 정확한 URL 기준으로만
        """
        result = []
        
        # 명확하게 제외할 패턴 (아이콘, 로고, UI 요소만)
        exclude_patterns = [
            'icon', 'sprite', 'logo', 'avatar', 'badge', 'emoji',
            'button', 'arrow', 'check', 'close', 'menu', 'search',
            'facebook', 'twitter', 'instagram', 'kakao', 'naver',
            'google', 'apple', 'play', 'app-store', 'qr',
            'escrow', 'membership',
            'loading', 'placeholder', 'blank',
            '/ad/', '/ads/', '/banner/',
        ]
        
        # Idus CDN에서 같은 이미지의 다른 크기 버전 통합
        # 예: files/abc123_720.jpg와 files/abc123_100.jpg는 같은 이미지
        seen_file_ids: dict[str, str] = {}  # file_id -> best_url
        other_images = []  # Idus CDN이 아닌 이미지
        
        for img in images:
            if not img or not img.startswith('http'):
                continue
            
            low = img.lower()
            
            # SVG 제외
            if low.endswith('.svg'):
                continue
            
            # 명확한 제외 패턴
            if any(pattern in low for pattern in exclude_patterns):
                continue
            
            # Idus CDN 이미지인 경우: 같은 파일 ID의 가장 큰 버전만 유지
            if 'image.idus.com' in low:
                # files/UUID_SIZE.ext 패턴에서 UUID 추출
                match = re.search(r'files/([a-f0-9]{20,})(?:_(\d+))?\.', low)
                if match:
                    file_id = match.group(1)
                    size = int(match.group(2)) if match.group(2) else 0
                    
                    if file_id in seen_file_ids:
                        # 기존 URL의 크기와 비교
                        existing_match = re.search(r'_(\d+)\.', seen_file_ids[file_id].lower())
                        existing_size = int(existing_match.group(1)) if existing_match else 0
                        
                        # 더 큰 크기면 교체
                        if size > existing_size:
                            seen_file_ids[file_id] = img
                    else:
                        seen_file_ids[file_id] = img
                else:
                    # UUID 패턴이 아닌 경우 그냥 추가
                    other_images.append(img)
            else:
                # Idus CDN이 아닌 이미지는 그대로 추가
                other_images.append(img)
        
        # 결과 합치기: Idus CDN 이미지 + 기타 이미지
        result = list(seen_file_ids.values()) + other_images
        
        # 최종 중복 제거 (정확한 URL 기준)
        result = list(dict.fromkeys(result))
        
        print(f"📷 필터링 결과: Idus CDN {len(seen_file_ids)}개, 기타 {len(other_images)}개, 총 {len(result)}개")
        
        return result[:100]


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
