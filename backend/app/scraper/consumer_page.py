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

from ..models.v1 import ProductData, ProductOption


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
        """옵션 추출 - 계층형 옵션 구조 지원 (2단 이상 옵션)"""
        options: list[ProductOption] = []
        
        try:
            print("   📌 계층형 옵션 추출 시작...")
            
            # 1단계: 옵션 영역 찾기 및 클릭
            option_area_selectors = [
                'text="옵션을 선택해주세요"',
                'text="옵션 선택"',
                '[class*="option-select"]',
                '[class*="optionSelect"]',
                'button:has-text("옵션")',
            ]
            
            option_area = None
            for selector in option_area_selectors:
                try:
                    option_area = await page.query_selector(selector)
                    if option_area and await option_area.is_visible():
                        print(f"      옵션 영역 발견: {selector}")
                        break
                    option_area = None
                except:
                    continue
            
            if not option_area:
                print("      ⚠️ 옵션 영역을 찾을 수 없음, 후기에서 추출 시도...")
                return await self._get_options_from_reviews(page)
            
            # 2단계: 옵션 영역 클릭하여 옵션 패널 열기
            await option_area.click()
            await asyncio.sleep(1)
            
            # 3단계: 옵션 그룹 개수 파악 (옵션 선택 (0/2) 형태)
            option_info = await page.evaluate("""
                () => {
                    // "옵션 선택 (0/2)" 또는 "옵션 선택(0/2)" 형태에서 총 옵션 그룹 수 추출
                    const allText = document.body.innerText || '';
                    const match = allText.match(/옵션\\s*선택\\s*\\(?\\s*(\\d+)\\s*\\/\\s*(\\d+)\\s*\\)?/);
                    if (match) {
                        return { current: parseInt(match[1]), total: parseInt(match[2]) };
                    }
                    return null;
                }
            """)
            
            total_groups = option_info['total'] if option_info else 1
            print(f"      옵션 그룹 수: {total_groups}개")
            
            # 4단계: 각 옵션 그룹을 순차적으로 클릭하여 옵션값 추출
            for group_idx in range(1, total_groups + 1):
                print(f"      📍 {group_idx}번 옵션 그룹 처리 중...")
                
                # 옵션 그룹 헤더 찾기 ("1. 핫케이크 높이" 형태)
                js_find_group = """
                    (groupIdx) => {
                        const result = { name: null, values: [], headerElement: null };
                        
                        // 옵션 그룹 헤더 찾기 (아코디언/드롭다운 형태)
                        const allElements = document.querySelectorAll('*');
                        let foundHeader = null;
                        let groupName = null;
                        
                        for (const el of allElements) {
                            const text = (el.innerText || el.textContent || '').trim();
                            
                            // "1. 핫케이크 높이" 또는 "1. 기타 옵션" 형태
                            const headerMatch = text.match(new RegExp('^' + groupIdx + '\\\\.\\\\s*(.+?)(?:\\\\s|$)'));
                            if (headerMatch && text.length < 50) {
                                // 클릭 가능한 요소인지 확인
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 50 && rect.height > 20) {
                                    groupName = headerMatch[1].trim();
                                    foundHeader = el;
                                    break;
                                }
                            }
                        }
                        
                        if (groupName) {
                            result.name = groupName;
                            
                            // 해당 그룹의 옵션값 찾기
                            // 헤더 다음에 오는 옵션 리스트 탐색
                            if (foundHeader) {
                                let sibling = foundHeader.nextElementSibling;
                                let parent = foundHeader.parentElement;
                                
                                // 같은 부모 내에서 옵션값 찾기
                                const searchContainer = parent || document.body;
                                const options = searchContainer.querySelectorAll(
                                    '[role="option"], [class*="option-item"], [class*="optionItem"], ' +
                                    'li, [class*="select-item"], [class*="selectItem"]'
                                );
                                
                                options.forEach(opt => {
                                    const optText = (opt.innerText || '').trim().split('\\n')[0].trim();
                                    
                                    // 유효한 옵션값인지 확인
                                    if (optText && optText.length >= 1 && optText.length <= 60) {
                                        const noise = ['선택해주세요', '선택하세요', '확인', '취소', 
                                                      '닫기', '장바구니', '구매하기', '필수', '옵션'];
                                        const isNoise = noise.some(n => optText.includes(n));
                                        const isGroupHeader = /^\\d+\\./.test(optText);
                                        const isPriceOnly = /^[\\d,]+\\s*원?$/.test(optText);
                                        
                                        if (!isNoise && !isGroupHeader && !isPriceOnly) {
                                            // 가격 정보 제거
                                            let cleanValue = optText.replace(/\\s*\\(?[\\+\\-]?[\\d,]+\\s*원\\)?\\s*$/g, '').trim();
                                            if (cleanValue.length >= 1 && !result.values.includes(cleanValue)) {
                                                result.values.push(cleanValue);
                                            }
                                        }
                                    }
                                });
                            }
                        }
                        
                        return result;
                    }
                """
                group_data = await page.evaluate(js_find_group, group_idx)
                
                # 그룹 헤더를 직접 클릭하여 옵션 펼치기
                if group_data and group_data.get('name'):
                    group_name = group_data['name']
                    
                    # 그룹 헤더 클릭 (아코디언 펼치기)
                    try:
                        header_selector = f'text="{group_idx}. {group_name}"'
                        header_el = await page.query_selector(header_selector)
                        if header_el:
                            await header_el.click()
                            await asyncio.sleep(0.5)
                    except:
                        pass
                    
                    # 펼쳐진 후 옵션값 다시 추출
                    # group_name을 안전하게 이스케이프
                    safe_group_name = group_name.replace('\\', '\\\\').replace('"', '\\"') if group_name else ''
                    
                    js_code = """
                        (args) => {
                            const values = [];
                            const groupIdx = args.groupIdx;
                            const groupName = args.groupName;
                            
                            // 화면에 보이는 모든 텍스트에서 옵션값 패턴 찾기
                            // 특히 아코디언/드롭다운이 펼쳐진 상태에서
                            
                            // 방법 1: role="option" 또는 li 요소
                            const optionElements = document.querySelectorAll(
                                '[role="option"], [role="listitem"], ' +
                                '[class*="option-item"], [class*="optionItem"], ' +
                                '[class*="select-item"], [class*="selectItem"], ' +
                                '[class*="dropdown-item"], [class*="dropdownItem"]'
                            );
                            
                            optionElements.forEach(el => {
                                const rect = el.getBoundingClientRect();
                                // 화면에 보이는 요소만
                                if (rect.width > 0 && rect.height > 0) {
                                    const text = (el.innerText || '').trim().split('\\n')[0].trim();
                                    
                                    if (text && text.length >= 1 && text.length <= 60) {
                                        const noise = ['선택해', '확인', '취소', '닫기', '필수', '옵션 선택'];
                                        const isNoise = noise.some(n => text.includes(n));
                                        const isGroupHeader = /^\\d+\\./.test(text);
                                        const isPriceOnly = /^[\\d,]+\\s*원?$/.test(text);
                                        
                                        if (!isNoise && !isGroupHeader && !isPriceOnly) {
                                            let cleanValue = text.replace(/\\s*\\(?[\\+\\-]?[\\d,]+\\s*원\\)?\\s*$/g, '').trim();
                                            if (cleanValue.length >= 1 && !values.includes(cleanValue)) {
                                                values.push(cleanValue);
                                            }
                                        }
                                    }
                                }
                            });
                            
                            // 방법 2: 그룹 헤더 아래의 텍스트 라인들
                            if (values.length === 0) {
                                const allText = document.body.innerText || '';
                                const lines = allText.split('\\n');
                                let inGroup = false;
                                
                                for (let i = 0; i < lines.length; i++) {
                                    const line = lines[i].trim();
                                    
                                    // 현재 그룹 헤더 발견
                                    if (line.startsWith(groupIdx + '.') || line.includes(groupName)) {
                                        inGroup = true;
                                        continue;
                                    }
                                    
                                    // 다음 그룹 헤더 발견 시 종료
                                    if (inGroup && /^\\d+\\./.test(line)) {
                                        break;
                                    }
                                    
                                    // 옵션값 수집
                                    if (inGroup && line.length >= 1 && line.length <= 60) {
                                        const noise = ['선택해', '확인', '취소', '닫기', '필수', '옵션'];
                                        const isNoise = noise.some(n => line.includes(n));
                                        const isPriceOnly = /^[\\d,]+\\s*원?$/.test(line);
                                        
                                        if (!isNoise && !isPriceOnly && !/^\\d+\\./.test(line)) {
                                            let cleanValue = line.replace(/\\s*\\(?[\\+\\-]?[\\d,]+\\s*원\\)?\\s*$/g, '').trim();
                                            if (cleanValue.length >= 1 && !values.includes(cleanValue)) {
                                                values.push(cleanValue);
                                            }
                                        }
                                    }
                                }
                            }
                            
                            return values;
                        }
                    """
                    expanded_values = await page.evaluate(js_code, {'groupIdx': group_idx, 'groupName': safe_group_name})
                    
                    final_values = expanded_values if expanded_values else group_data.get('values', [])
                    
                    if final_values:
                        options.append(ProductOption(name=group_name, values=final_values))
                        print(f"         ✅ {group_name}: {final_values}")
                        
                        # 다음 옵션 그룹 활성화를 위해 첫 번째 옵션 선택
                        if group_idx < total_groups and len(final_values) > 0:
                            try:
                                first_option = final_values[0]
                                option_selector = f'text="{first_option}"'
                                option_el = await page.query_selector(option_selector)
                                if option_el and await option_el.is_visible():
                                    await option_el.click()
                                    await asyncio.sleep(0.5)
                                    print(f"         → 다음 그룹 활성화를 위해 '{first_option}' 선택")
                            except:
                                pass
            
            # 5단계: 결과가 없으면 대체 방법 시도
            if not options:
                print("      ⚠️ 계층형 옵션 추출 실패, 단순 패널 추출 시도...")
                options = await self._get_options_simple(page)
            
            # 6단계: 여전히 없으면 후기에서 추출
            if not options:
                print("      ⚠️ 패널 추출 실패, 후기에서 추출 시도...")
                options = await self._get_options_from_reviews(page)
            
            # 패널 닫기
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            
            print(f"   📌 옵션 추출 완료: {len(options)}개 그룹")
            for opt in options:
                print(f"      - {opt.name}: {opt.values}")
            
        except Exception as e:
            print(f"옵션 추출 오류: {e}")
            import traceback
            traceback.print_exc()
        
        return options
    
    async def _get_options_simple(self, page: Page) -> list[ProductOption]:
        """단순 옵션 패널에서 추출 (계층형이 아닌 경우)"""
        options = []
        try:
            panel_options = await page.evaluate("""
                () => {
                    const result = [];
                    const optionGroups = {};
                    
                    // 옵션 패널 찾기
                    const panels = document.querySelectorAll(
                        '[role="dialog"], [role="listbox"], ' +
                        '[class*="bottom-sheet"], [class*="bottomSheet"], ' +
                        '[class*="option-panel"], [class*="optionPanel"], ' +
                        '[class*="modal"], [class*="drawer"]'
                    );
                    
                    for (const panel of panels) {
                        const rect = panel.getBoundingClientRect();
                        if (rect.width < 50 || rect.height < 50) continue;
                        
                        const allText = panel.innerText || '';
                        const lines = allText.split('\\n');
                        
                        let currentGroup = null;
                        
                        for (const line of lines) {
                            const trimmed = line.trim();
                            if (!trimmed) continue;
                            
                            // 그룹 헤더 패턴: "1. 옵션명" 또는 "옵션명"
                            const groupMatch = trimmed.match(/^(?:(\\d+)\\.\\s*)?(.+?)$/);
                            if (groupMatch && trimmed.length <= 30 && !trimmed.includes('원')) {
                                const potentialGroup = groupMatch[2].trim();
                                if (potentialGroup.length >= 2 && 
                                    !['선택해주세요', '확인', '취소', '닫기'].some(n => potentialGroup.includes(n))) {
                                    currentGroup = potentialGroup;
                                    if (!optionGroups[currentGroup]) {
                                        optionGroups[currentGroup] = [];
                                    }
                                    continue;
                                }
                            }
                            
                            // 옵션값
                            if (currentGroup && trimmed.length >= 1 && trimmed.length <= 60) {
                                const noise = ['선택해', '확인', '취소', '닫기', '장바구니', '구매하기', '필수'];
                                const isNoise = noise.some(n => trimmed.includes(n));
                                const isPriceOnly = /^[\\d,]+\\s*원?$/.test(trimmed);
                                
                                if (!isNoise && !isPriceOnly && !/^\\d+\\./.test(trimmed)) {
                                    let cleanValue = trimmed.replace(/\\s*\\(?[\\+\\-]?[\\d,]+\\s*원\\)?\\s*$/g, '').trim();
                                    if (cleanValue.length >= 1 && !optionGroups[currentGroup].includes(cleanValue)) {
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
            
            if panel_options:
                for opt in panel_options:
                    if opt.get('values') and len(opt['values']) > 0:
                        options.append(ProductOption(name=opt['name'], values=opt['values']))
                        
        except Exception as e:
            print(f"단순 옵션 추출 오류: {e}")
        
        return options
    
    async def _get_options_from_reviews(self, page: Page) -> list[ProductOption]:
        """후기에서 옵션 정보 추출"""
        options = []
        try:
            review_options = await page.evaluate("""
                () => {
                    const optionGroups = {};
                    const allText = document.body.innerText || '';
                    
                    // 패턴: "옵션명: 옵션값" 또는 "옵션명 선택: 옵션값"
                    const patterns = [
                        /([가-힣a-zA-Z]+(?:\\s*선택)?)\\s*[：:]\\s*([가-힣a-zA-Z0-9\\s\\(\\)\\[\\]]+?)(?=\\s*\\*|\\s*[,\\n]|$)/g
                    ];
                    
                    for (const pattern of patterns) {
                        const matches = allText.matchAll(pattern);
                        for (const match of matches) {
                            let optName = match[1].trim();
                            let optValue = match[2].trim().replace(/\\s+/g, ' ');
                            
                            // 유효성 검사
                            if (optName && optValue &&
                                optName.length >= 2 && optName.length <= 30 && 
                                optValue.length >= 1 && optValue.length <= 80 &&
                                !['구매', '배송', '결제', '가격'].some(n => optName.includes(n))) {
                                
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
                        
        except Exception as e:
            print(f"후기 옵션 추출 오류: {e}")
        
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
        """상세페이지(작품정보 탭) 영역 내 이미지만 추출 - 탭 패널 기반 (가장 정확)"""
        try:
            # 1단계: 작품정보 탭 클릭하여 해당 콘텐츠 활성화
            print("   📌 작품정보 탭 클릭 시도...")
            try:
                tab_clicked = await page.evaluate("""
                    () => {
                        // 방법 1: role="tab" 요소 중 작품정보 찾기
                        const tabs = document.querySelectorAll('[role="tab"]');
                        for (const tab of tabs) {
                            const text = (tab.innerText || tab.textContent || '').trim();
                            if (text.includes('작품정보') || text === '작품정보') {
                                tab.click();
                                return { clicked: true, method: 'role=tab' };
                            }
                        }
                        
                        // 방법 2: 버튼/링크 중 작품정보 찾기
                        const buttons = document.querySelectorAll('button, a');
                        for (const btn of buttons) {
                            const text = (btn.innerText || btn.textContent || '').trim();
                            if (text === '작품정보' || text === '상품정보') {
                                btn.click();
                                return { clicked: true, method: 'button/link' };
                            }
                        }
                        
                        return { clicked: false };
                    }
                """)
                if tab_clicked and tab_clicked.get('clicked'):
                    await asyncio.sleep(1)  # 탭 콘텐츠 로드 대기
                    print(f"      ✅ 작품정보 탭 클릭됨 (방법: {tab_clicked.get('method')})")
            except Exception as e:
                print(f"      ⚠️ 탭 클릭 실패: {e}")
            
            # 2단계: 탭 패널 기반 이미지 추출 (가장 정확한 방법)
            images = await page.evaluate("""
                () => {
                    const images = [];
                    const seen = new Set();
                    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    
                    // ===== 제외 패턴 =====
                    const excludePatterns = [
                        'review', 'photo-review', 'recommend', 'related', 'similar',
                        'comment', 'qna', 'artist-product', 'shop-product',
                        'profile', 'avatar', 'banner', 'popup', 'swiper'
                    ];
                    
                    // ===== 방법 1: 활성화된 탭 패널에서 이미지 찾기 =====
                    let targetContainer = null;
                    
                    // [role="tabpanel"] 중 활성화된 것 찾기
                    const tabPanels = document.querySelectorAll('[role="tabpanel"]');
                    console.log('탭 패널 수:', tabPanels.length);
                    
                    for (const panel of tabPanels) {
                        // 활성화된 패널 확인 (여러 방법으로)
                        const isHidden = panel.hidden || 
                                        panel.getAttribute('aria-hidden') === 'true' ||
                                        getComputedStyle(panel).display === 'none' ||
                                        getComputedStyle(panel).visibility === 'hidden' ||
                                        panel.offsetHeight === 0;
                        
                        if (!isHidden) {
                            const text = panel.innerText || '';
                            const imgs = panel.querySelectorAll('img[src*="idus"]');
                            console.log('활성 패널 발견, 텍스트 길이:', text.length, '이미지 수:', imgs.length);
                            
                            // 충분한 콘텐츠가 있는 패널
                            if (text.length > 50 || imgs.length > 0) {
                                targetContainer = panel;
                                console.log('✅ 타겟 컨테이너로 선택됨');
                                break;
                            }
                        }
                    }
                    
                    // 방법 2: 클래스명으로 상세 콘텐츠 영역 찾기
                    if (!targetContainer) {
                        const detailSelectors = [
                            '[class*="detail-content"]', '[class*="detailContent"]',
                            '[class*="product-detail"]', '[class*="productDetail"]',
                            '[class*="description-area"]', '[class*="descriptionArea"]',
                            '[class*="product-info"]', '[class*="productInfo"]',
                            '[data-tab="product-info"]', '[data-tab="작품정보"]',
                            'article[class*="detail"]', 'section[class*="detail"]'
                        ];
                        
                        for (const sel of detailSelectors) {
                            const els = document.querySelectorAll(sel);
                            for (const el of els) {
                                const rect = el.getBoundingClientRect();
                                const imgs = el.querySelectorAll('img[src*="idus"]');
                                console.log('셀렉터', sel, '- 높이:', rect.height, '이미지:', imgs.length);
                                
                                if (rect.height > 100 && imgs.length > 0) {
                                    targetContainer = el;
                                    console.log('✅ 상세 콘텐츠 영역 발견:', sel);
                                    break;
                                }
                            }
                            if (targetContainer) break;
                        }
                    }
                    
                    // 방법 3: 이미지가 가장 많은 컨테이너 찾기
                    if (!targetContainer) {
                        const containers = document.querySelectorAll('article, section, div[class*="content"]');
                        let maxImgCount = 0;
                        
                        for (const container of containers) {
                            const classes = (container.className || '').toLowerCase();
                            // 추천/리뷰 영역 제외
                            if (excludePatterns.some(p => classes.includes(p))) continue;
                            
                            const imgs = container.querySelectorAll('img[src*="idus"]');
                            const rect = container.getBoundingClientRect();
                            
                            // 충분한 크기의 컨테이너에서 이미지가 많은 것
                            if (imgs.length > maxImgCount && imgs.length >= 2 && rect.height > 300) {
                                maxImgCount = imgs.length;
                                targetContainer = container;
                            }
                        }
                        if (targetContainer) {
                            console.log('✅ 이미지 많은 컨테이너 발견, 이미지 수:', maxImgCount);
                        }
                    }
                    
                    // ===== 이미지 수집 =====
                    const collectImages = (container) => {
                        const imgElements = container ? 
                            container.querySelectorAll('img') : 
                            document.querySelectorAll('img');
                        
                        console.log('이미지 요소 수:', imgElements.length);
                        
                        imgElements.forEach((img, domIndex) => {
                            // URL 추출 (여러 속성 시도)
                            const url = img.src || img.getAttribute('data-src') || 
                                       img.getAttribute('data-original') || img.getAttribute('data-lazy-src') ||
                                       img.dataset?.src || img.dataset?.original;
                            
                            if (!url) return;
                            if (!url.includes('idus')) return;
                            if (seen.has(url)) return;
                            
                            // URL 패턴으로 명백한 제외
                            const urlLower = url.toLowerCase();
                            if (urlLower.includes('/profile') || urlLower.includes('/avatar') ||
                                urlLower.includes('/icon') || urlLower.includes('/badge') ||
                                urlLower.includes('_50.') || urlLower.includes('_100.') ||
                                urlLower.includes('_150.') || urlLower.includes('_200.') ||
                                urlLower.includes('/thumb_') || urlLower.includes('/review/')) {
                                return;
                            }
                            
                            // 이미지 위치/크기 정보
                            const rect = img.getBoundingClientRect();
                            const imgY = rect.top + scrollTop;
                            const imgX = rect.left;
                            
                            // 크기 정보 (자연 크기 또는 렌더링 크기)
                            const width = img.naturalWidth || rect.width || parseInt(img.getAttribute('width')) || 0;
                            const height = img.naturalHeight || rect.height || parseInt(img.getAttribute('height')) || 0;
                            
                            // 아주 작은 이미지만 제외 (아이콘 등)
                            if (width > 0 && width < 80) return;
                            if (height > 0 && height < 80) return;
                            
                            // 부모 요소 제외 영역 체크
                            let parent = img.parentElement;
                            let inExcluded = false;
                            let depth = 0;
                            
                            while (parent && parent !== container && depth < 8) {
                                const classes = (parent.className || '').toString().toLowerCase();
                                for (const pattern of excludePatterns) {
                                    if (classes.includes(pattern)) {
                                        inExcluded = true;
                                        break;
                                    }
                                }
                                if (inExcluded) break;
                                parent = parent.parentElement;
                                depth++;
                            }
                            
                            if (inExcluded) return;
                            
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
                    };
                    
                    // 타겟 컨테이너에서 이미지 수집
                    if (targetContainer) {
                        console.log('타겟 컨테이너에서 이미지 추출 중...');
                        collectImages(targetContainer);
                    } else {
                        console.log('⚠️ 타겟 컨테이너 없음, 전체에서 필터링 추출');
                        // 전체에서 추출하되 엄격한 필터링
                        collectImages(null);
                    }
                    
                    console.log('최종 수집된 이미지:', images.length);
                    
                    // Y좌표로 정렬
                    return images.sort((a, b) => {
                        if (Math.abs(a.y_position - b.y_position) < 20) {
                            return a.x_position - b.x_position;
                        }
                        return a.y_position - b.y_position;
                    });
                }
            """)
            
            print(f"   📷 탭 패널 기반 이미지 추출: {len(images)}개")
            if images:
                print(f"      Y 범위: {images[0].get('y_position', 0):.0f} ~ {images[-1].get('y_position', 0):.0f}")
            return images or []
        except Exception as e:
            print(f"이미지 추출 오류: {e}")
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
