"""
아이디어스(Idus) 상품 크롤링 모듈
Playwright + 정확한 셀렉터 기반 데이터 추출
개선: 상세 이미지 수집 강화 (텍스트 포함 이미지 우선)
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
                # 이미지 리소스 타입이거나 이미지 확장자 URL
                if response.request.resource_type == "image":
                    img_url = response.url
                    if img_url.startswith('http'):
                        image_urls_from_network.add(img_url)
                # URL 패턴으로도 이미지 수집 (idus CDN)
                elif 'image.idus.com' in response.url:
                    image_urls_from_network.add(response.url)
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
            
            # 6. 이미지 추출 (개선된 방식)
            await self._full_scroll_for_images(page)
            dom_images = await self._extract_all_images_comprehensive(page)
            
            # 네트워크에서 수집한 이미지 추가
            network_images = list(image_urls_from_network)
            all_images = list(dict.fromkeys(dom_images + network_images))
            
            # 이미지 필터링 및 정렬 (상세 이미지 우선)
            filtered_images = self._filter_and_prioritize_images(all_images)
            
            print(f"✅ 크롤링 완료: {title}")
            print(f"   - 작가: {artist_name}")
            print(f"   - 가격: {price}")
            print(f"   - 옵션: {len(options)}개 그룹")
            print(f"   - 이미지: {len(filtered_images)}개 (DOM: {len(dom_images)}, 네트워크: {len(network_images)})")
            
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
        """상품 설명 추출 - 상세 페이지의 POINT 등 텍스트 포함"""
        descriptions = []
        
        # 1. 상세 정보 탭 클릭 시도
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
        
        # 2. 상세 설명 영역에서 텍스트 추출 (POINT 01, 02 등)
        try:
            detail_text = await page.evaluate("""
                () => {
                    const texts = [];
                    
                    // 상세 설명 영역 셀렉터들
                    const detailSelectors = [
                        'article',
                        '[class*="detail"]',
                        '[class*="description"]',
                        '[class*="content"]',
                        '[class*="info"]',
                        '[class*="story"]',
                        'main'
                    ];
                    
                    // UI 노이즈 필터
                    const noisePatterns = [
                        '로그인', '회원가입', '장바구니', '구매하기', '선물하기',
                        '고객센터', '아이디어스 앱', '카카오', '네이버',
                        '이용약관', '개인정보', '결제', '배송'
                    ];
                    
                    for (const selector of detailSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            // 텍스트 노드만 추출 (자식 요소의 중복 제외)
                            const text = el.innerText || '';
                            
                            // 충분히 긴 텍스트만 (설명일 가능성)
                            if (text.length < 50) continue;
                            
                            // UI 노이즈 필터링
                            let isNoise = false;
                            for (const noise of noisePatterns) {
                                if (text.includes(noise) && text.length < 200) {
                                    isNoise = true;
                                    break;
                                }
                            }
                            if (isNoise) continue;
                            
                            // POINT, 특징, 설명 등 키워드 포함 시 우선
                            if (text.includes('POINT') || 
                                text.includes('특징') || 
                                text.includes('소개') ||
                                text.includes('안내') ||
                                text.includes('사용') ||
                                text.includes('주의')) {
                                texts.unshift(text);  // 앞에 추가
                            } else {
                                texts.push(text);
                            }
                        }
                    }
                    
                    // 가장 긴 텍스트 반환 (상세 설명일 가능성 높음)
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
        
        # 3. meta description (폴백)
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
        
        # 가장 긴 설명 반환
        if descriptions:
            descriptions.sort(key=len, reverse=True)
            return descriptions[0][:6000]  # 최대 6000자
        
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

    async def _full_scroll_for_images(self, page: Page):
        """
        이미지 로딩을 위한 전체 스크롤 (개선됨)
        - 더 느리게, 더 많이 스크롤하여 모든 lazy-load 이미지 로드
        """
        try:
            # 전체 페이지 높이 확인
            total_height = await page.evaluate("document.body.scrollHeight")
            viewport_height = await page.evaluate("window.innerHeight")
            
            # 스크롤 단계 계산 (300px씩)
            scroll_step = 300
            current_position = 0
            
            print(f"📜 이미지 로딩을 위한 스크롤 시작 (페이지 높이: {total_height}px)")
            
            # 천천히 페이지 끝까지 스크롤
            while current_position < total_height:
                await page.evaluate(f"window.scrollTo(0, {current_position})")
                await asyncio.sleep(0.4)  # 각 스크롤 후 0.4초 대기 (이미지 로드 시간)
                current_position += scroll_step
                
                # 동적 콘텐츠로 페이지 높이가 늘어났는지 확인
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height > total_height:
                    total_height = new_height
            
            # 페이지 끝에서 잠시 대기 (마지막 이미지 로드)
            await asyncio.sleep(1)
            
            # 다시 위로 스크롤하면서 한번 더 확인
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
            
            print(f"📜 스크롤 완료")
            
        except Exception as e:
            print(f"스크롤 오류: {e}")

    async def _extract_all_images_comprehensive(self, page: Page) -> list[str]:
        """
        모든 이미지 URL 종합 추출 (개선됨)
        - img src, data-src, srcset
        - picture source
        - background-image
        - 모든 크기의 이미지 수집
        """
        images = []
        
        try:
            # JavaScript로 모든 가능한 이미지 URL 추출
            all_image_urls = await page.evaluate("""
                () => {
                    const urls = new Set();
                    
                    // 1. img 태그에서 추출
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
                        
                        // data-original (일부 lazy load 라이브러리)
                        const dataOriginal = img.getAttribute('data-original');
                        if (dataOriginal && dataOriginal.startsWith('http')) {
                            urls.add(dataOriginal);
                        }
                        
                        // srcset에서 모든 이미지 추출
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
                    
                    // 2. picture > source 태그에서 추출
                    document.querySelectorAll('source').forEach(source => {
                        const srcset = source.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(part => {
                                const url = part.trim().split(' ')[0];
                                if (url && url.startsWith('http')) {
                                    urls.add(url);
                                }
                            });
                        }
                    });
                    
                    // 3. background-image에서 추출
                    document.querySelectorAll('*').forEach(el => {
                        const style = getComputedStyle(el);
                        const bgImage = style.backgroundImage;
                        if (bgImage && bgImage !== 'none') {
                            const match = bgImage.match(/url\\(['"]?(https?:\\/\\/[^'"\\)]+)['"]?\\)/);
                            if (match && match[1]) {
                                urls.add(match[1]);
                            }
                        }
                    });
                    
                    // 4. 인라인 스타일의 background-image
                    document.querySelectorAll('[style*="background"]').forEach(el => {
                        const style = el.getAttribute('style') || '';
                        const matches = style.match(/url\\(['"]?(https?:\\/\\/[^'"\\)]+)['"]?\\)/g);
                        if (matches) {
                            matches.forEach(match => {
                                const url = match.replace(/url\\(['"]?/, '').replace(/['"]?\\)/, '');
                                if (url.startsWith('http')) {
                                    urls.add(url);
                                }
                            });
                        }
                    });
                    
                    return Array.from(urls);
                }
            """)
            
            images = all_image_urls or []
            print(f"📷 DOM에서 {len(images)}개 이미지 URL 수집")
            
        except Exception as e:
            print(f"이미지 추출 오류: {e}")
        
        return images

    def _filter_and_prioritize_images(self, images: list[str]) -> list[str]:
        """
        상품 관련 이미지 필터링 및 우선순위 정렬
        - OCR 대상이 될 상세 이미지(텍스트 포함) 우선
        - 큰 해상도 이미지 우선
        """
        high_priority = []  # 큰 해상도 이미지 (OCR 가치 높음)
        normal_priority = []  # 일반 상품 이미지
        
        # 제외할 패턴 (아이콘, 로고, 작은 이미지 등)
        exclude_patterns = [
            'icon', 'sprite', 'logo', 'avatar', 'badge', 'emoji',
            'button', 'arrow', 'check', 'close', 'menu', 'search',
            'facebook', 'twitter', 'instagram', 'kakao', 'naver',
            'google', 'apple', 'play', 'app-store', 'qr',
            'banner-image', 'escrow', 'membership', 'profile',
            'loading', 'placeholder', 'default', 'blank',
            '/ad/', '/ads/', '/banner/', '/event/',
        ]
        
        # 작은 썸네일 크기 패턴 (제외)
        small_size_patterns = [
            '_50.', '_60.', '_70.', '_80.', '_90.', '_100.',
            '_120.', '_150.', '_180.',
            '/50/', '/60/', '/70/', '/80/', '/90/', '/100/',
            '/120/', '/150/', '/180/',
            '50x', '60x', '70x', '80x', '90x', '100x',
        ]
        
        # 큰 해상도 패턴 (우선)
        large_size_patterns = [
            '_720.', '_800.', '_1000.', '_1200.', '_1500.', '_1920.',
            '/720/', '/800/', '/1000/', '/1200/', '/1500/', '/1920/',
        ]
        
        seen_base_urls = set()  # 중복 제거용
        
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
            
            # 작은 썸네일 제외
            if any(pattern in low for pattern in small_size_patterns):
                continue
            
            # Idus CDN 이미지 확인
            is_idus = 'idus' in low or 'image.idus.com' in low
            
            # 이미지 확장자 확인
            is_image = any(ext in low for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif'])
            
            if not (is_idus or is_image):
                continue
            
            # 기본 URL 추출 (크기 변형 무시)
            # 예: xxx_720.jpg와 xxx_100.jpg는 같은 이미지
            base_url = re.sub(r'_\d+\.', '_X.', img)
            base_url = re.sub(r'/\d+/', '/X/', base_url)
            
            if base_url in seen_base_urls:
                continue
            seen_base_urls.add(base_url)
            
            # 큰 해상도 이미지는 우선순위 높음
            if any(pattern in low for pattern in large_size_patterns):
                high_priority.append(img)
            else:
                normal_priority.append(img)
        
        # 우선순위별로 결합
        result = high_priority + normal_priority
        result = list(dict.fromkeys(result))  # 최종 중복 제거
        
        print(f"📷 필터링 결과: 고해상도 {len(high_priority)}개, 일반 {len(normal_priority)}개")
        
        return result[:100]  # 최대 100개


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
