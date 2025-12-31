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
            
            # 2. "작품 정보 더보기" 버튼 클릭하여 상세 정보 펼치기
            print("📌 작품 정보 더보기 버튼 클릭 시도...")
            try:
                expand_button = await page.query_selector('button:has-text("작품 정보 더보기")')
                if expand_button:
                    await expand_button.click()
                    await asyncio.sleep(1)
                    print("   ✅ 상세 정보 펼침")
            except Exception as e:
                print(f"   상세 정보 펼치기 실패 (무시): {e}")
            
            # 3. 전체 스크롤하여 lazy-load 이미지 로드
            print("📜 이미지 로드를 위한 전체 스크롤...")
            await self._full_scroll(page)
            
            # 스크롤 후 HTML 다시 가져오기
            html_content = await page.content()
            
            # 4. 상세페이지 영역 내 이미지 추출 (위치 정보 포함, Y좌표 정렬)
            print("📷 상세페이지 이미지 추출 중...")
            detail_images_with_pos = await self._extract_images_with_position(page)
            
            # 5. 위치 기반 이미지가 있으면 해당 결과 사용 (최소 1개 이상)
            if len(detail_images_with_pos) >= 1:
                # 상세페이지 영역 이미지만 사용 (이미 Y좌표로 정렬됨)
                filtered_images = [img['url'] for img in detail_images_with_pos]
                filtered_images = self._filter_images(filtered_images)
                print(f"   ✅ 상세페이지 영역 이미지 사용: {len(filtered_images)}개")
            else:
                # 폴백: 전체 이미지에서 추출 (DOM 경로 필터링 포함)
                print("   ⚠️ 상세페이지 이미지 없음, 전체에서 추출 후 필터링...")
                
                all_images = set()
                all_images.update(network_images)
                
                # 폴백에서도 필터링 강화
                filtered_images = self._filter_images_strict(list(all_images), page)
                print(f"   네트워크에서 캡처 후 필터링: {len(network_images)}개 → {len(filtered_images)}개")
            
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
        """옵션 추출 - "옵션을 선택해주세요" 버튼 클릭 방식 우선"""
        options: list[ProductOption] = []
        
        try:
            # 방법 1: "옵션을 선택해주세요" 버튼 클릭하여 옵션 패널에서 추출 (가장 정확)
            print("   📌 옵션 선택 버튼 클릭하여 옵션 추출 시도...")
            
            # 다양한 선택자로 옵션 선택 버튼/영역 찾기
            option_selectors = [
                'button:has-text("옵션을 선택해주세요")',
                'button:has-text("옵션 선택")',
                'div:has-text("옵션을 선택해주세요")',
                '[class*="option-select"]',
                '[class*="optionSelect"]',
                '[class*="option"] button',
                '[class*="select-option"]',
            ]
            
            option_trigger = None
            for selector in option_selectors:
                try:
                    option_trigger = await page.query_selector(selector)
                    if option_trigger:
                        # 클릭 가능한지 확인
                        is_visible = await option_trigger.is_visible()
                        if is_visible:
                            print(f"      옵션 버튼 발견: {selector}")
                            break
                        else:
                            option_trigger = None
                except:
                    continue
            
            if option_trigger:
                await option_trigger.click()
                await asyncio.sleep(1.5)  # 옵션 패널 로드 대기
                
                # 옵션 패널에서 옵션 추출
                panel_options = await page.evaluate("""
                    () => {
                        const result = [];
                        const optionGroups = {};
                        
                        // 옵션 패널/바텀시트/드롭다운 찾기
                        const panels = document.querySelectorAll(
                            '[role="dialog"], [role="listbox"], [role="menu"], ' +
                            '[class*="bottom-sheet"], [class*="bottomSheet"], ' +
                            '[class*="option-panel"], [class*="optionPanel"], ' +
                            '[class*="option-list"], [class*="optionList"], ' +
                            '[class*="dropdown"], [class*="select-panel"], ' +
                            '[class*="modal"], [class*="drawer"]'
                        );
                        
                        for (const panel of panels) {
                            const rect = panel.getBoundingClientRect();
                            // 화면에 보이는 패널만 처리
                            if (rect.width < 50 || rect.height < 50) continue;
                            
                            const allText = panel.innerText || '';
                            const lines = allText.split('\\n');
                            
                            let currentGroup = null;
                            
                            for (const line of lines) {
                                const trimmed = line.trim();
                                if (!trimmed) continue;
                                
                                // "1. 쿠키 선택 (필수)" 또는 "쿠키 선택" 형식의 그룹 헤더
                                const groupMatch = trimmed.match(/^(?:(\\d+)\\.\\s*)?(.+?)(?:\\s*\\(필수\\))?\\s*$/);
                                if (groupMatch) {
                                    const potentialGroup = groupMatch[2].trim();
                                    // 그룹 이름으로 적합한지 확인
                                    if (potentialGroup.includes('선택') && 
                                        potentialGroup.length >= 2 && potentialGroup.length <= 30 &&
                                        !potentialGroup.includes('원') && !potentialGroup.includes('구매')) {
                                        currentGroup = potentialGroup;
                                        if (!optionGroups[currentGroup]) {
                                            optionGroups[currentGroup] = [];
                                        }
                                        continue;
                                    }
                                }
                                
                                // 옵션 값 수집
                                if (currentGroup && trimmed.length >= 2 && trimmed.length <= 80) {
                                    const noise = ['선택해주세요', '선택하세요', '확인', '취소', '닫기', 
                                                  '장바구니', '구매하기', '필수', '총 상품금액', 
                                                  '배송비', '수량', '품절', '옵션을'];
                                    const isNoise = noise.some(n => trimmed.includes(n));
                                    const isPriceOnly = /^[\\d,]+\\s*원?$/.test(trimmed);
                                    const isNumber = /^\\d+$/.test(trimmed);
                                    
                                    if (!isNoise && !isPriceOnly && !isNumber && !/^\\d+\\.\\s*[가-힣]/.test(trimmed)) {
                                        // 가격 정보 제거 (옵션값 뒤의 가격)
                                        let cleanValue = trimmed.replace(/\\s*[\\(\\[]?[\\+\\-]?[\\d,]+\\s*원[\\)\\]]?\\s*$/g, '').trim();
                                        if (cleanValue.length >= 2 && !optionGroups[currentGroup].includes(cleanValue)) {
                                            optionGroups[currentGroup].push(cleanValue);
                                        }
                                    }
                                }
                            }
                            
                            // role="option" 요소에서도 추출
                            const optionItems = panel.querySelectorAll('[role="option"], [class*="option-item"], [class*="optionItem"], li');
                            if (optionItems.length > 0 && Object.keys(optionGroups).length === 0) {
                                const values = [];
                                optionItems.forEach(item => {
                                    const text = (item.innerText || '').trim().split('\\n')[0].trim();
                                    if (text && text.length >= 2 && text.length <= 60) {
                                        const noise = ['선택해', '확인', '취소', '닫기', '품절'];
                                        if (!noise.some(n => text.includes(n))) {
                                            let cleanText = text.replace(/\\s*[\\(\\[]?[\\+\\-]?[\\d,]+\\s*원[\\)\\]]?\\s*$/g, '').trim();
                                            if (cleanText.length >= 2) {
                                                values.push(cleanText);
                                            }
                                        }
                                    }
                                });
                                if (values.length > 0) {
                                    optionGroups['옵션'] = values;
                                }
                            }
                        }
                        
                        for (const [name, values] of Object.entries(optionGroups)) {
                            if (values.length > 0) {
                                result.push({ name, values: [...new Set(values)] });
                            }
                        }
                        
                        return result;
                    }
                """)
                
                if panel_options:
                    for opt in panel_options:
                        if opt.get('values') and len(opt['values']) > 0:
                            options.append(ProductOption(name=opt['name'], values=opt['values']))
                            print(f"      ✅ 옵션 패널에서 추출: {opt['name']}: {opt['values']}")
                
                # 패널 닫기
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
            
            # 방법 2: 후기에서 옵션 정보 추출 (백업 - 후기가 있는 경우)
            if not options:
                print("   📌 후기에서 옵션 정보 추출 시도...")
                review_options = await page.evaluate("""
                    () => {
                        const optionGroups = {};
                        
                        // 전체 페이지 텍스트에서 옵션 패턴 찾기
                        const allText = document.body.innerText || '';
                        
                        // 패턴: "옵션명 선택: 옵션값"
                        // 예: "쿠키 선택: 세인트릴리 쿠키 (파랑술)"
                        const patterns = [
                            /([가-힣a-zA-Z]+\\s*선택)\\s*[：:]\\s*([가-힣a-zA-Z0-9\\s\\(\\)\\[\\]]+?)(?=\\s*\\*|\\s*[,\\n]|$)/g,
                            /구매작품\\s*[：:]\\s*([가-힣a-zA-Z]+\\s*선택)\\s*[：:]\\s*([가-힣a-zA-Z0-9\\s\\(\\)\\[\\]]+?)(?=\\s*\\*|\\s*[,\\n]|$)/g
                        ];
                        
                        for (const pattern of patterns) {
                            const matches = allText.matchAll(pattern);
                            for (const match of matches) {
                                let optName = match[1].trim();
                                let optValue = match[2].trim().replace(/\\s+/g, ' ');
                                
                                if (optName && optValue &&
                                    optName.length >= 2 && optName.length <= 30 && 
                                    optValue.length >= 2 && optValue.length <= 80) {
                                    
                                    if (!optionGroups[optName]) {
                                        optionGroups[optName] = new Set();
                                    }
                                    optionGroups[optName].add(optValue);
                                }
                            }
                        }
                        
                        const result = [];
                        for (const [name, values] of Object.entries(optionGroups)) {
                            if (values.size > 0) {
                                result.push({ name, values: Array.from(values) });
                            }
                        }
                        return result;
                    }
                """)
                
                if review_options:
                    for opt in review_options:
                        if opt.get('values') and len(opt['values']) > 0:
                            options.append(ProductOption(name=opt['name'], values=opt['values']))
                            print(f"      ✅ 후기에서 추출: {opt['name']}: {opt['values']}")
            
            # 방법 3: 구매하기 버튼 클릭 후 바텀시트에서 추출
            if not options:
                print("   📌 구매하기 버튼 클릭하여 바텀시트에서 옵션 추출 시도...")
                buy_button = await page.query_selector('button:has-text("구매하기")')
                
                if buy_button:
                    await buy_button.click()
                    await asyncio.sleep(2)
                    
                    sheet_options = await page.evaluate("""
                        () => {
                            const result = [];
                            const optionGroups = {};
                            
                            // 바텀시트/모달 찾기
                            const containers = document.querySelectorAll(
                                '[role="dialog"], [class*="bottom-sheet"], [class*="bottomSheet"], ' +
                                '[class*="modal"], [class*="drawer"], [class*="option-select"], ' +
                                '[class*="optionSelect"], [class*="purchase"]'
                            );
                            
                            for (const container of containers) {
                                const allText = container.innerText || '';
                                const lines = allText.split('\\n');
                                
                                let currentGroup = null;
                                
                                for (const line of lines) {
                                    const trimmed = line.trim();
                                    if (!trimmed) continue;
                                    
                                    // "1. 쿠키 선택 (필수)" 형식의 그룹 헤더
                                    const groupMatch = trimmed.match(/^(\\d+)\\.?\\s*(.+?)(?:\\s*\\(필수\\))?\\s*$/);
                                    if (groupMatch && !trimmed.includes('원') && trimmed.length <= 30) {
                                        currentGroup = groupMatch[2].trim();
                                        if (!optionGroups[currentGroup]) {
                                            optionGroups[currentGroup] = [];
                                        }
                                        continue;
                                    }
                                    
                                    // 옵션 값
                                    if (currentGroup && trimmed.length >= 2 && trimmed.length <= 60) {
                                        const noise = ['선택해주세요', '선택하세요', '확인', '취소', '닫기', 
                                                      '장바구니', '구매하기', '필수', '총 상품금액', 
                                                      '배송비', '수량', '품절'];
                                        const isNoise = noise.some(n => trimmed.includes(n));
                                        const isPriceOnly = /^[\\d,]+\\s*원?$/.test(trimmed);
                                        const isNumber = /^\\d+$/.test(trimmed);
                                        
                                        if (!isNoise && !isPriceOnly && !isNumber && !/^\\d+\\./.test(trimmed)) {
                                            let cleanValue = trimmed.replace(/\\s*[\\(\\[]?[\\+\\-]?[\\d,]+\\s*원[\\)\\]]?\\s*$/g, '').trim();
                                            if (cleanValue.length >= 2 && !optionGroups[currentGroup].includes(cleanValue)) {
                                                optionGroups[currentGroup].push(cleanValue);
                                            }
                                        }
                                    }
                                }
                            }
                            
                            for (const [name, values] of Object.entries(optionGroups)) {
                                if (values.length > 0) {
                                    result.push({ name, values: [...new Set(values)] });
                                }
                            }
                            
                            return result;
                        }
                    """)
                    
                    if sheet_options:
                        for opt in sheet_options:
                            if opt.get('values') and len(opt['values']) > 0:
                                options.append(ProductOption(name=opt['name'], values=opt['values']))
                                print(f"      ✅ 바텀시트에서 추출: {opt['name']}: {opt['values']}")
                    
                    # 바텀시트 닫기
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
            
            print(f"   📌 옵션 추출 완료: {len(options)}개 그룹")
            for opt in options:
                print(f"      - {opt.name}: {opt.values}")
            
        except Exception as e:
            print(f"옵션 추출 오류: {e}")
            import traceback
            traceback.print_exc()
        
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
        """상세페이지(작품정보 탭) 영역 내 이미지만 추출 - DOM 경로 기반 필터링 (개선버전)"""
        try:
            # 1단계: 작품정보 탭 클릭하여 해당 콘텐츠 활성화
            print("   📌 작품정보 탭 클릭 시도...")
            try:
                tab_clicked = await page.evaluate("""
                    () => {
                        const tabs = document.querySelectorAll('[role="tab"], button, a');
                        for (const tab of tabs) {
                            const text = (tab.innerText || tab.textContent || '').trim();
                            if (text.includes('작품정보') || text === '작품정보') {
                                tab.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                if tab_clicked:
                    await asyncio.sleep(0.5)
                    print("      ✅ 작품정보 탭 클릭됨")
            except:
                pass
            
            # 2단계: DOM 경로 기반 이미지 추출 (개선된 로직)
            images = await page.evaluate("""
                () => {
                    const images = [];
                    const seen = new Set();
                    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    
                    // ===== 제외할 부모 클래스/ID 패턴 =====
                    const excludePatterns = [
                        // 후기/리뷰 영역 (중요!)
                        'review', 'photo-review', 'photoReview', 'photo_review',
                        // 댓글 영역
                        'comment', 'qna',
                        // 추천/관련 상품 (가장 중요!)
                        'recommend', 'related', 'similar', 'other-product', 'otherProduct',
                        'also-like', 'alsoLike', 'you-may', 'youMay', 'more-product', 'moreProduct',
                        'products-you', 'productsYou', 'like-product', 'likeProduct',
                        // 작가/샵 다른 상품
                        'artist-product', 'artistProduct', 'shop-product', 'shopProduct',
                        'seller-product', 'sellerProduct', 'artist-other', 'artistOther',
                        'shop-other', 'shopOther', 'more-from', 'moreFrom',
                        // 헤더/푸터/네비게이션
                        'header', 'footer', 'nav-', '-nav', 'gnb', 'lnb',
                        // 배너/팝업
                        'banner', 'popup', 'modal', 'toast', 'alert', 'notice',
                        // 장바구니/구매 영역
                        'cart', 'purchase', 'buy-area', 'buyArea', 'order-',
                        // 썸네일 슬라이더 (상단 메인 이미지 - 이건 포함해도 됨)
                        // 'thumbnail', 'thumb-list', 
                        // 프로필/아바타
                        'profile', 'avatar', 'user-info', 'userInfo',
                        // 리스트/그리드 형태 상품 목록
                        'product-list', 'productList', 'item-list', 'itemList',
                        'product-grid', 'productGrid', 'item-grid', 'itemGrid',
                        'swiper-slide'  // 추천상품 슬라이더
                    ];
                    
                    // ===== 상세페이지 영역 경계 찾기 =====
                    let detailStartY = 0;
                    let detailEndY = Infinity;
                    
                    // "작품 정보 접기/더보기" 버튼으로 경계 찾기
                    const allButtons = document.querySelectorAll('button');
                    for (const btn of allButtons) {
                        const text = (btn.innerText || '').trim();
                        if (text.includes('작품 정보 접기')) {
                            const rect = btn.getBoundingClientRect();
                            detailEndY = rect.bottom + scrollTop + 100;  // 접기 버튼 아래 100px까지만
                            console.log('접기 버튼 발견, detailEndY:', detailEndY);
                            break;
                        }
                    }
                    
                    // "후기" 탭/섹션 헤더 위치로 경계 찾기 (더 정확한 방법)
                    const allElements = document.querySelectorAll('[role="tab"], h2, h3, [class*="section-title"]');
                    for (const el of allElements) {
                        const text = (el.innerText || el.textContent || '').trim();
                        if (/^후기/.test(text) && text.length < 20) {
                            const rect = el.getBoundingClientRect();
                            const y = rect.top + scrollTop;
                            if (y > 500 && y < detailEndY) {
                                detailEndY = y - 50;  // 후기 섹션 50px 전까지만
                                console.log('후기 섹션 발견, detailEndY:', detailEndY);
                                break;
                            }
                        }
                    }
                    
                    // 탭 헤더 위치로 상세정보 시작점 찾기
                    const tabLists = document.querySelectorAll('[role="tablist"]');
                    for (const tabList of tabLists) {
                        const rect = tabList.getBoundingClientRect();
                        detailStartY = rect.bottom + scrollTop;
                        console.log('탭 헤더 발견, detailStartY:', detailStartY);
                        break;
                    }
                    
                    console.log('상세페이지 영역:', detailStartY, '~', detailEndY);
                    
                    // ===== 이미지 수집 =====
                    document.querySelectorAll('img').forEach((img, domIndex) => {
                        // URL 추출 (여러 속성 시도)
                        const url = img.src || img.getAttribute('data-src') || 
                                   img.getAttribute('data-original') || img.getAttribute('data-lazy-src') ||
                                   img.dataset?.src || img.dataset?.original;
                        
                        if (!url || !url.includes('idus') || seen.has(url)) return;
                        
                        // URL 패턴으로 명백한 제외
                        const urlLower = url.toLowerCase();
                        if (urlLower.includes('/profile') || urlLower.includes('/avatar') ||
                            urlLower.includes('/icon') || urlLower.includes('/badge') ||
                            urlLower.includes('_50.') || urlLower.includes('_100.') ||
                            urlLower.includes('_150.') || urlLower.includes('_200.')) {
                            return;
                        }
                        
                        // 이미지 위치/크기 정보
                        const rect = img.getBoundingClientRect();
                        const imgY = rect.top + scrollTop;
                        const imgX = rect.left;
                        
                        // 크기 체크 (최소 100px - lazy loading 대응)
                        const width = rect.width || img.naturalWidth || parseInt(img.getAttribute('width')) || 0;
                        const height = rect.height || img.naturalHeight || parseInt(img.getAttribute('height')) || 0;
                        
                        // 아주 작은 이미지만 제외 (아이콘 등)
                        if (width > 0 && width < 100) return;
                        if (height > 0 && height < 100) return;
                        
                        // Y 위치 체크 (상세페이지 영역 내)
                        if (detailEndY < Infinity && imgY > detailEndY) {
                            console.log('Y 위치 초과로 제외:', imgY, '>', detailEndY, url.substring(0, 50));
                            return;
                        }
                        
                        // ===== DOM 경로 추적하여 제외 영역 체크 =====
                        let el = img.parentElement;
                        let inExcludedArea = false;
                        let excludeReason = '';
                        let depth = 0;
                        const maxDepth = 20;  // 더 깊이 탐색
                        
                        while (el && el !== document.body && depth < maxDepth) {
                            const classes = (el.className || '').toString().toLowerCase();
                            const id = (el.id || '').toLowerCase();
                            const combined = classes + ' ' + id;
                            
                            // 제외 패턴 체크
                            for (const pattern of excludePatterns) {
                                if (combined.includes(pattern.toLowerCase())) {
                                    inExcludedArea = true;
                                    excludeReason = pattern;
                                    break;
                                }
                            }
                            if (inExcludedArea) break;
                            
                            el = el.parentElement;
                            depth++;
                        }
                        
                        // 제외 영역에 있으면 건너뛰기
                        if (inExcludedArea) {
                            console.log('DOM 경로 제외:', excludeReason, url.substring(0, 50));
                            return;
                        }
                        
                        seen.add(url);
                        
                        images.push({
                            url: url,
                            y_position: imgY,
                            x_position: imgX,
                            width: width,
                            height: height,
                            dom_index: domIndex
                        });
                    });
                    
                    console.log('수집된 이미지:', images.length);
                    
                    // Y좌표로 정렬
                    return images.sort((a, b) => {
                        if (Math.abs(a.y_position - b.y_position) < 20) {
                            return a.x_position - b.x_position;
                        }
                        return a.y_position - b.y_position;
                    });
                }
            """)
            
            print(f"   📷 DOM 경로 기반 이미지 추출: {len(images)}개")
            if images:
                print(f"      Y 범위: {images[0].get('y_position', 0):.0f} ~ {images[-1].get('y_position', 0):.0f}")
            return images or []
        except Exception as e:
            print(f"위치 기반 이미지 추출 오류: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _filter_images(self, images: list[str]) -> list[str]:
        """이미지 필터링 - 상세페이지 이미지만 유지"""
        
        # 명확히 제외할 패턴
        exclude_patterns = [
            '/icon', '/sprite', '/logo', '/avatar', '/badge',
            '/emoji', '/button', '/arrow', '/profile',
            'facebook.', 'twitter.', 'instagram.', 'kakao.', 'naver.',
            'google.com', 'apple.com',
            '/escrow', '/membership', '/banner',
            '/thumbnail', '/thumb_', '_thumb',  # 썸네일 제외
            '/review/', '/comment/',  # 후기 이미지 제외
            '/artist/', '/shop/',  # 작가/샵 이미지 제외
            'data:image'
        ]
        
        # 크기 기반 제외 패턴 (작은 이미지)
        small_size_patterns = ['_50.', '_100.', '_150.', '_200.', '_250.']
        
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
            
            # 작은 크기 이미지 제외
            is_small = any(p in low for p in small_size_patterns)
            if is_small:
                continue
            
            # 명백한 제외 패턴 체크
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
                    size = int(size_match.group(1)) if size_match else 9999  # 크기 없으면 원본
                    
                    # 최소 크기 필터 (300px 이상만)
                    if size_match and size < 300:
                        continue
                    
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
                # Idus CDN이 아닌 다른 이미지는 제외 (상세페이지에는 idus 이미지만 있음)
                pass
        
        print(f"📷 이미지 필터링: {len(images)}개 → {len(result)}개")
        return result[:15]  # 최대 15개로 제한 (OCR 시간 단축)
    
    def _filter_images_strict(self, images: list[str], page: Page = None) -> list[str]:
        """엄격한 이미지 필터링 - 폴백 시 사용"""
        
        # 상세페이지 이미지로 추정되는 URL 패턴만 허용
        result = []
        seen_file_ids = set()
        
        for img in images:
            if not img or not isinstance(img, str):
                continue
            if not img.startswith('http'):
                continue
            
            low = img.lower()
            
            # Idus CDN만 허용
            if 'image.idus.com' not in low:
                continue
            
            # 파일 ID 추출
            match = re.search(r'files/([a-f0-9]+)', low)
            if not match:
                continue
            
            file_id = match.group(1)
            
            # 중복 파일 ID 제외
            if file_id in seen_file_ids:
                continue
            
            # 크기 정보 추출
            size_match = re.search(r'_(\d+)\.', low)
            if size_match:
                size = int(size_match.group(1))
                # 400px 이상만 (엄격한 필터)
                if size < 400:
                    continue
            
            # 명백한 제외 패턴
            exclude_patterns = [
                '/profile', '/avatar', '/icon', '/badge',
                '/thumb_', '/thumbnail', '_thumb',
                '/review', '/comment',
                '/artist/', '/shop/',
                '_50.', '_100.', '_150.', '_200.', '_250.', '_300.'
            ]
            
            skip = any(p in low for p in exclude_patterns)
            if skip:
                continue
            
            seen_file_ids.add(file_id)
            result.append(img)
        
        return result[:20]  # 엄격 필터는 20개로 더 제한
    
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
