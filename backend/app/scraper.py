"""
아이디어스(Idus) 상품 크롤링 모듈
HTML 전체에서 이미지 URL 추출 + 네트워크 캡처 + __NUXT__ 파싱
"""
import asyncio
import json
import re
import os
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext, Response
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
        
        def on_response(response: Response):
            try:
                resp_url = response.url
                # Idus 이미지 CDN URL 수집
                if 'image.idus.com' in resp_url:
                    network_images.add(resp_url)
                # 일반 이미지 리소스
                elif response.request.resource_type == "image":
                    if resp_url.startswith('http') and 'idus' in resp_url:
                        network_images.add(resp_url)
            except:
                pass
        
        page.on("response", on_response)
        
        try:
            # 페이지 로드 (networkidle 대신 domcontentloaded + 대기)
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            
            # HTML 전체 가져오기 (이미지 추출용)
            html_content = await page.content()
            
            # 1. 기본 정보 추출
            title = await self._get_title(page)
            artist_name = await self._get_artist(page)
            price = await self._get_price(page)
            description = await self._get_description(page)
            options = await self._get_options(page)
            
            # 2. 전체 스크롤하여 lazy-load 이미지 로드
            print("📜 이미지 로드를 위한 전체 스크롤...")
            await self._full_scroll(page)
            
            # 스크롤 후 HTML 다시 가져오기
            html_content = await page.content()
            
            # 3. HTML에서 모든 이미지 URL 추출 (정규식)
            html_images = self._extract_images_from_html(html_content)
            print(f"   HTML에서 추출: {len(html_images)}개")
            
            # 4. __NUXT__ 스크립트에서 이미지 URL 추출
            nuxt_images = self._extract_images_from_nuxt(html_content)
            print(f"   __NUXT__에서 추출: {len(nuxt_images)}개")
            
            # 5. DOM에서 이미지 URL 추출 (위치 정보 포함)
            dom_images = await self._extract_images_from_dom(page)
            dom_images_with_pos = await self._extract_images_with_position(page)
            print(f"   DOM에서 추출: {len(dom_images)}개 (위치 정보: {len(dom_images_with_pos)}개)")
            
            print(f"   네트워크에서 캡처: {len(network_images)}개")
            
            # 6. 모든 이미지 합치기
            all_images = set()
            all_images.update(html_images)
            all_images.update(nuxt_images)
            all_images.update(dom_images)
            all_images.update(network_images)
            
            # 7. 필터링 및 정리
            filtered_images = self._filter_images(list(all_images))
            
            # 8. 위치 기반 정렬 적용 (DOM에서 추출한 순서 우선)
            if dom_images_with_pos:
                filtered_images = self._sort_images_by_position(filtered_images, dom_images_with_pos)
            
            print(f"✅ 크롤링 완료: {title}")
            print(f"   - 작가: {artist_name}")
            print(f"   - 가격: {price}")
            print(f"   - 옵션: {len(options)}개")
            print(f"   - 최종 이미지: {len(filtered_images)}개")
            
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
        """작가명 추출 - 여러 방법 시도"""
        try:
            # 방법 1: artist 링크에서 추출
            result = await page.evaluate("""
                () => {
                    // artist 링크 찾기
                    const artistLinks = document.querySelectorAll('a[href*="/artist/"]');
                    for (const link of artistLinks) {
                        const text = (link.innerText || '').trim();
                        // 유효한 작가명인지 확인 (2~30자, 특수문자/UI텍스트 제외)
                        if (text.length >= 2 && text.length <= 30) {
                            if (!text.includes('바로가기') && !text.includes('작가') && 
                                !text.includes('홈') && !text.includes('샵')) {
                                return text;
                            }
                        }
                    }
                    
                    // 방법 2: 작가 관련 클래스에서 찾기
                    const selectors = [
                        '[class*="artist-name"]',
                        '[class*="artistName"]', 
                        '[class*="seller-name"]',
                        '[class*="shop-name"]',
                        '[class*="author"]'
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const text = (el.innerText || '').trim();
                            if (text.length >= 2 && text.length <= 30) {
                                return text;
                            }
                        }
                    }
                    
                    // 방법 3: meta 태그에서 찾기
                    const metaAuthor = document.querySelector('meta[name="author"]');
                    if (metaAuthor) {
                        const content = metaAuthor.getAttribute('content');
                        if (content && content.length >= 2) return content;
                    }
                    
                    return null;
                }
            """)
            if result:
                return result
        except Exception as e:
            print(f"작가명 추출 오류: {e}")
        return "작가명 없음"

    async def _get_price(self, page: Page) -> str:
        """가격 추출 - 여러 방법 시도"""
        try:
            result = await page.evaluate("""
                () => {
                    // 방법 1: 가격 관련 클래스에서 찾기 (할인가 우선)
                    const priceSelectors = [
                        '[class*="sale-price"]',
                        '[class*="salePrice"]',
                        '[class*="final-price"]',
                        '[class*="finalPrice"]',
                        '[class*="discount-price"]',
                        '[class*="price"]'
                    ];
                    
                    for (const sel of priceSelectors) {
                        const els = document.querySelectorAll(sel);
                        for (const el of els) {
                            const text = el.innerText || '';
                            // 숫자,원 패턴 매칭 (최소 3자리 이상)
                            const match = text.match(/([\\d,]{3,})\\s*원/);
                            if (match) {
                                return match[0];
                            }
                        }
                    }
                    
                    // 방법 2: 전체 페이지에서 첫 번째 가격 패턴 찾기
                    const allText = document.body.innerText || '';
                    const priceMatch = allText.match(/([\\d,]{4,})\\s*원/);
                    if (priceMatch) {
                        return priceMatch[0];
                    }
                    
                    return null;
                }
            """)
            if result:
                return result
        except Exception as e:
            print(f"가격 추출 오류: {e}")
        return "가격 정보 없음"

    async def _get_description(self, page: Page) -> str:
        # 작품정보 탭 클릭 시도
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
        """옵션 추출 - 옵션 버튼 클릭하여 실제 옵션 추출"""
        options: list[ProductOption] = []
        
        try:
            # 방법 1: "옵션을 선택해주세요" 버튼 클릭하여 옵션 패널 열기
            option_trigger = await page.query_selector('button:has-text("옵션을 선택해주세요")')
            if not option_trigger:
                option_trigger = await page.query_selector('button:has-text("옵션 선택")')
            if not option_trigger:
                option_trigger = await page.query_selector('[class*="option"] button')
            
            if option_trigger:
                print("   📌 옵션 버튼 클릭 시도...")
                await option_trigger.click()
                await asyncio.sleep(1)
                
                # 옵션 패널에서 옵션 그룹 찾기
                option_data = await page.evaluate("""
                    () => {
                        const result = [];
                        
                        // 바텀시트/다이얼로그에서 옵션 그룹 찾기
                        const panels = document.querySelectorAll('[role="dialog"], [class*="sheet"], [class*="modal"], [class*="option"]');
                        
                        for (const panel of panels) {
                            // 옵션 그룹 헤더 찾기 (1. 쿠키 선택, 2. 수량 등)
                            const groups = panel.querySelectorAll('[class*="group"], [class*="category"], h3, h4, [class*="title"]');
                            
                            // role="option" 또는 버튼 형태의 옵션 아이템 찾기
                            const items = panel.querySelectorAll('[role="option"], [role="radio"], [class*="option-item"], li button, li[class*="item"]');
                            
                            if (items.length > 0) {
                                const values = [];
                                items.forEach(item => {
                                    // 첫 번째 줄만 추출 (가격 등 부가정보 제외)
                                    let text = (item.innerText || '').trim().split('\\n')[0].trim();
                                    
                                    // 유효한 옵션값인지 확인
                                    if (text && text.length >= 2 && text.length <= 50) {
                                        // UI 텍스트/노이즈 제외
                                        const noise = ['선택', '확인', '취소', '닫기', '장바구니', '구매', '원', '₩', '품절'];
                                        let isNoise = noise.some(n => text.includes(n));
                                        if (!isNoise) {
                                            values.push(text);
                                        }
                                    }
                                });
                                
                                if (values.length > 0) {
                                    // 옵션 그룹 이름 찾기
                                    let groupName = '옵션';
                                    for (const g of groups) {
                                        const gText = (g.innerText || '').trim();
                                        // "1. 쿠키 선택" 형식에서 이름 추출
                                        const match = gText.match(/^\\d+\\.?\\s*(.+)/);
                                        if (match) {
                                            groupName = match[1].trim();
                                            break;
                                        } else if (gText.length >= 2 && gText.length <= 20) {
                                            groupName = gText;
                                            break;
                                        }
                                    }
                                    
                                    result.push({ name: groupName, values: values });
                                }
                            }
                        }
                        
                        return result;
                    }
                """)
                
                if option_data:
                    for opt in option_data:
                        if opt.get('values'):
                            # 중복 제거
                            unique_values = list(dict.fromkeys(opt['values']))
                            options.append(ProductOption(name=opt['name'], values=unique_values))
                
                # 패널 닫기
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
            
            # 방법 2: 옵션 버튼이 없는 경우, select 요소에서 추출
            if not options:
                select_options = await page.evaluate("""
                    () => {
                        const result = [];
                        document.querySelectorAll('select').forEach(sel => {
                            const name = sel.getAttribute('aria-label') || sel.getAttribute('name') || '옵션';
                            const values = [];
                            sel.querySelectorAll('option').forEach(opt => {
                                const text = (opt.innerText || '').trim();
                                if (text && text.length >= 2 && text.length <= 50 && 
                                    !text.includes('선택') && !text.includes('옵션을')) {
                                    values.push(text);
                                }
                            });
                            if (values.length > 0) {
                                result.push({ name, values });
                            }
                        });
                        return result;
                    }
                """)
                
                if select_options:
                    for opt in select_options:
                        if opt.get('values'):
                            options.append(ProductOption(name=opt['name'], values=opt['values']))
            
            print(f"   📌 옵션 추출 완료: {len(options)}개 그룹")
            
        except Exception as e:
            print(f"옵션 추출 오류: {e}")
        
        return options

    async def _full_scroll(self, page: Page):
        """페이지 전체를 천천히 스크롤"""
        try:
            total = await page.evaluate("document.body.scrollHeight")
            current = 0
            step = 400
            
            while current < total:
                await page.evaluate(f"window.scrollTo(0, {current})")
                await asyncio.sleep(0.3)
                current += step
                new_total = await page.evaluate("document.body.scrollHeight")
                if new_total > total:
                    total = new_total
            
            # 마지막에 맨 아래까지 확실히 스크롤
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)
            
        except Exception as e:
            print(f"스크롤 오류: {e}")

    def _extract_images_from_html(self, html: str) -> set[str]:
        """HTML 전체에서 정규식으로 이미지 URL 추출"""
        images = set()
        
        # 1. image.idus.com 패턴 (가장 중요)
        idus_pattern = r'https?://image\.idus\.com/image/files/[a-f0-9]+(?:_\d+)?\.(?:jpg|jpeg|png|webp|gif)'
        for match in re.findall(idus_pattern, html, re.IGNORECASE):
            images.add(match)
        
        # 2. 더 유연한 패턴 (확장자 없는 경우도 포함)
        idus_pattern2 = r'https?://image\.idus\.com/image/files/[a-f0-9_]+(?:\.[a-z]{3,4})?'
        for match in re.findall(idus_pattern2, html, re.IGNORECASE):
            if len(match) > 40:  # 충분히 긴 URL만
                images.add(match)
        
        # 3. cdn.idus.kr 패턴
        cdn_pattern = r'https?://cdn\.idus\.kr[^"\'\s\)>]+\.(?:jpg|jpeg|png|webp|gif)'
        for match in re.findall(cdn_pattern, html, re.IGNORECASE):
            images.add(match)
        
        # 4. 일반 이미지 URL (idus 도메인만)
        general_pattern = r'https?://[^"\'\s\)>]*idus[^"\'\s\)>]*\.(?:jpg|jpeg|png|webp|gif)'
        for match in re.findall(general_pattern, html, re.IGNORECASE):
            images.add(match)
        
        return images
    
    def _extract_images_from_nuxt(self, html: str) -> set[str]:
        """__NUXT__ 스크립트에서 이미지 URL 추출"""
        images = set()
        
        try:
            # __NUXT__ 또는 __NUXT_DATA__ 패턴 찾기
            patterns = [
                r'<script[^>]*>\s*window\.__NUXT__\s*=\s*(\{.+?\})\s*;?\s*</script>',
                r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.+?)</script>',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    data_str = match.group(1)
                    # 이미지 URL 추출 (JSON 파싱 없이 정규식으로)
                    url_pattern = r'https?://image\.idus\.com/image/files/[^"\'\s\\]+(?:\.(?:jpg|jpeg|png|webp|gif))?'
                    for url_match in re.findall(url_pattern, data_str, re.IGNORECASE):
                        # 이스케이프 문자 제거
                        clean_url = url_match.replace('\\/', '/').replace('\\"', '')
                        if len(clean_url) > 40:
                            images.add(clean_url)
        except Exception as e:
            print(f"NUXT 파싱 오류: {e}")
        
        return images

    async def _extract_images_from_dom(self, page: Page) -> list[str]:
        """DOM에서 이미지 URL 추출 (기본 - URL만)"""
        try:
            urls = await page.evaluate("""
                () => {
                    const urls = new Set();
                    
                    // img 태그
                    document.querySelectorAll('img').forEach(img => {
                        ['src', 'data-src', 'data-original', 'data-lazy-src'].forEach(attr => {
                            const url = img.getAttribute(attr);
                            if (url && url.includes('idus')) urls.add(url);
                        });
                        
                        // srcset
                        const srcset = img.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(part => {
                                const url = part.trim().split(' ')[0];
                                if (url && url.includes('idus')) urls.add(url);
                            });
                        }
                    });
                    
                    // source 태그
                    document.querySelectorAll('source').forEach(src => {
                        const srcset = src.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(part => {
                                const url = part.trim().split(' ')[0];
                                if (url && url.includes('idus')) urls.add(url);
                            });
                        }
                    });
                    
                    // background-image
                    document.querySelectorAll('*').forEach(el => {
                        try {
                            const bg = getComputedStyle(el).backgroundImage;
                            if (bg && bg !== 'none') {
                                const match = bg.match(/url\\(['"]?(https?:\\/\\/[^'"\\)]+)['"]?\\)/);
                                if (match && match[1].includes('idus')) {
                                    urls.add(match[1]);
                                }
                            }
                        } catch(e) {}
                    });
                    
                    return Array.from(urls);
                }
            """)
            return urls or []
        except Exception as e:
            print(f"DOM 이미지 추출 오류: {e}")
            return []

    async def _extract_images_with_position(self, page: Page) -> list[dict]:
        """DOM에서 이미지 URL과 Y좌표 추출 (페이지 순서 보장)"""
        try:
            images = await page.evaluate("""
                () => {
                    const images = [];
                    const seen = new Set();
                    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    
                    // 모든 img 요소 수집
                    document.querySelectorAll('img').forEach((img, domIndex) => {
                        // URL 추출 (여러 속성에서)
                        const url = img.src || img.getAttribute('data-src') || 
                                   img.getAttribute('data-original') || img.getAttribute('data-lazy-src');
                        
                        if (!url || !url.includes('idus') || seen.has(url)) return;
                        seen.add(url);
                        
                        // 위치 정보
                        const rect = img.getBoundingClientRect();
                        
                        images.push({
                            url: url,
                            y_position: rect.top + scrollTop,  // 절대 Y좌표
                            x_position: rect.left,
                            width: rect.width,
                            height: rect.height,
                            dom_index: domIndex
                        });
                    });
                    
                    // Y좌표로 정렬 (같은 Y면 X좌표로)
                    return images.sort((a, b) => {
                        // 10px 이내 차이는 같은 행으로 간주
                        if (Math.abs(a.y_position - b.y_position) < 10) {
                            return a.x_position - b.x_position;
                        }
                        return a.y_position - b.y_position;
                    });
                }
            """)
            return images or []
        except Exception as e:
            print(f"위치 기반 이미지 추출 오류: {e}")
            return []

    def _filter_images(self, images: list[str]) -> list[str]:
        """이미지 필터링 - 최소한의 제외만 적용"""
        
        # 명확히 제외할 패턴만
        exclude_patterns = [
            '/icon', '/sprite', '/logo', '/avatar', '/badge',
            '/emoji', '/button', '/arrow',
            'facebook.', 'twitter.', 'instagram.', 'kakao.', 'naver.',
            'google.com', 'apple.com',
            '/escrow', '/membership', '/banner-image',
            'data:image'
        ]
        
        result = []
        seen_urls = set()
        seen_file_ids = {}  # 같은 파일의 다른 크기 버전 처리
        
        for img in images:
            if not img or not isinstance(img, str):
                continue
            
            # 절대 URL이 아니면 건너뛰기
            if not img.startswith('http'):
                continue
            
            # 정확한 URL 중복 체크
            if img in seen_urls:
                continue
            seen_urls.add(img)
            
            low = img.lower()
            
            # SVG 제외
            if '.svg' in low:
                continue
            
            # 명백한 제외 패턴만 체크
            skip = False
            for pattern in exclude_patterns:
                if pattern in low:
                    skip = True
                    break
            if skip:
                continue
            
            # Idus 이미지 CDN URL인 경우
            if 'image.idus.com' in low:
                # 파일 ID 추출 (중복 크기 버전 처리)
                match = re.search(r'files/([a-f0-9]+)', low)
                if match:
                    file_id = match.group(1)
                    
                    # 크기 정보 추출
                    size_match = re.search(r'_(\d+)\.', low)
                    size = int(size_match.group(1)) if size_match else 0
                    
                    # 같은 파일 ID가 있으면 더 큰 크기로 교체
                    if file_id in seen_file_ids:
                        if size > seen_file_ids[file_id]['size']:
                            # 이전 URL 제거하고 새 URL 추가
                            old_url = seen_file_ids[file_id]['url']
                            if old_url in result:
                                result.remove(old_url)
                            seen_file_ids[file_id] = {'size': size, 'url': img}
                            result.append(img)
                    else:
                        seen_file_ids[file_id] = {'size': size, 'url': img}
                        result.append(img)
                else:
                    result.append(img)
            else:
                # Idus CDN이 아닌 다른 이미지
                result.append(img)
        
        print(f"📷 이미지 필터링: {len(images)}개 → {len(result)}개")
        return result[:200]  # 최대 200개
    
    def _sort_images_by_position(self, images: list[str], position_data: list[dict]) -> list[str]:
        """위치 정보를 기반으로 이미지 정렬 (페이지 순서 보장)"""
        
        # 위치 데이터를 URL -> 순서 맵으로 변환
        url_to_order = {}
        for idx, pos_info in enumerate(position_data):
            url = pos_info.get('url', '')
            if url:
                # URL 정규화 (쿼리 파라미터 제거 등)
                base_url = url.split('?')[0]
                url_to_order[base_url] = idx
                url_to_order[url] = idx
        
        # 이미지를 순서대로 정렬
        def get_order(url: str) -> int:
            base_url = url.split('?')[0]
            # 위치 정보가 있으면 해당 순서, 없으면 맨 뒤로
            if url in url_to_order:
                return url_to_order[url]
            if base_url in url_to_order:
                return url_to_order[base_url]
            return 99999
        
        sorted_images = sorted(images, key=get_order)
        
        print(f"📷 위치 기반 정렬: {len(sorted_images)}개 이미지 페이지 순서로 정렬됨")
        return sorted_images


if __name__ == "__main__":
    async def test():
        scraper = IdusScraper()
        await scraper.initialize()
        try:
            result = await scraper.scrape_product(
                "https://www.idus.com/v2/product/87beb859-49b2-4c18-86b4-f300b31d6247"
            )
            print(f"\n===== 결과 =====")
            print(f"제목: {result.title}")
            print(f"작가: {result.artist_name}")
            print(f"가격: {result.price}")
            print(f"옵션: {result.options}")
            print(f"이미지 수: {len(result.detail_images)}")
            print(f"\n상위 10개 이미지:")
            for i, img in enumerate(result.detail_images[:10]):
                print(f"  {i+1}. {img}")
        finally:
            await scraper.close()
    
    asyncio.run(test())
