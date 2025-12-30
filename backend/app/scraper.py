"""
아이디어스(Idus) 상품 크롤링 모듈
Playwright + Idus API 직접 호출 방식으로 안정적인 데이터 수집
"""
import asyncio
import json
import re
import os
from typing import Optional, Any
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from playwright_stealth import stealth_async
import httpx

from .models import ProductData, ProductOption, ImageText


class IdusScraper:
    """아이디어스 상품 페이지 크롤러 - API 기반 + DOM 폴백"""
    
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
            
            # Railway/Docker 환경 감지
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

    def _extract_product_uuid(self, url: str) -> Optional[str]:
        """URL에서 상품 UUID 추출"""
        # /v2/product/{uuid} 형식
        match = re.search(r'/v2/product/([a-f0-9-]{36})', url)
        if match:
            return match.group(1)
        # /w/product/{uuid} 형식
        match = re.search(r'/w/product/([a-f0-9-]{36})', url)
        if match:
            return match.group(1)
        return None
    
    async def scrape_product(self, url: str) -> ProductData:
        """상품 페이지 크롤링 - API 우선, DOM 폴백"""
        if not self._initialized:
            await self.initialize()
        
        product_uuid = self._extract_product_uuid(url)
        print(f"📄 크롤링 시작: {url}")
        print(f"📦 상품 UUID: {product_uuid}")
        
        page = await self._create_stealth_page()
        
        # 네트워크 응답 캡처를 위한 저장소
        api_responses: dict[str, Any] = {}
        image_urls_from_network: list[str] = []
        
        async def handle_response(response):
            try:
                url_str = response.url
                # Idus API 응답 캡처
                if '/api/aggregator/' in url_str or '/www-api/' in url_str:
                    if response.ok:
                        try:
                            data = await response.json()
                            api_responses[url_str] = data
                        except:
                            pass
                # 이미지 URL 캡처
                if response.request.resource_type == "image":
                    if url_str.startswith('http') and 'idus' in url_str.lower():
                        image_urls_from_network.append(url_str)
            except:
                pass
        
        page.on("response", handle_response)
        
        try:
            # 페이지 로드
            await page.goto(url, wait_until='networkidle', timeout=45000)
            await asyncio.sleep(2)
            
            # 동적 컨텐츠 로딩을 위한 스크롤
            await self._scroll_page(page)
            
            # 1. Nuxt.js 데이터에서 추출 시도
            nuxt_data = await self._extract_nuxt_data(page)
            
            # 2. API 응답에서 데이터 추출
            api_data = self._parse_api_responses(api_responses, product_uuid)
            
            # 3. DOM에서 추출 (폴백)
            dom_data = await self._extract_from_dom(page)
            
            # 데이터 병합 (우선순위: API > Nuxt > DOM)
            title = api_data.get('title') or nuxt_data.get('title') or dom_data.get('title') or "제목 없음"
            artist_name = api_data.get('artist_name') or nuxt_data.get('artist_name') or dom_data.get('artist_name') or "작가명 없음"
            price = api_data.get('price') or nuxt_data.get('price') or dom_data.get('price') or "가격 정보 없음"
            description = api_data.get('description') or nuxt_data.get('description') or dom_data.get('description') or "설명 없음"
            
            # 옵션 추출 (API > Nuxt > DOM > 인터랙티브)
            options = api_data.get('options') or nuxt_data.get('options') or []
            if not options:
                options = await self._extract_options_from_dom(page)
            if not options:
                options = await self._extract_options_interactive(page)
            
            # 이미지 추출
            detail_images = api_data.get('images') or nuxt_data.get('images') or []
            dom_images = await self._extract_images_from_dom(page)
            
            # 모든 이미지 소스 병합
            all_images = list(dict.fromkeys(
                detail_images + dom_images + image_urls_from_network
            ))
            
            # 이미지 필터링 (아이콘/로고 제외)
            filtered_images = []
            for img in all_images:
                if not img:
                    continue
                low = img.lower()
                if any(x in low for x in ['icon', 'sprite', 'logo', 'avatar', 'badge']):
                    continue
                if low.endswith('.svg'):
                    continue
                if img.startswith('http'):
                    filtered_images.append(img)
            
            # 중복 제거 및 제한
            filtered_images = list(dict.fromkeys(filtered_images))[:80]
            
            print(f"✅ 크롤링 완료: {title}")
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

    async def _scroll_page(self, page: Page):
        """페이지 스크롤로 동적 컨텐츠 로딩"""
        try:
            # 점진적 스크롤
            for _ in range(15):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
                await asyncio.sleep(0.3)
            
            # 맨 위로 복귀
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
        except:
            pass

    async def _extract_nuxt_data(self, page: Page) -> dict:
        """Nuxt.js 페이지의 __NUXT__ 데이터 추출"""
        result = {}
        
        try:
            # window.__NUXT__ 또는 window.__NUXT_DATA__ 추출
            nuxt_raw = await page.evaluate("""
                () => {
                    if (window.__NUXT__) return JSON.stringify(window.__NUXT__);
                    if (window.__NUXT_DATA__) return JSON.stringify(window.__NUXT_DATA__);
                    // Nuxt 3의 경우 다른 방식으로 저장될 수 있음
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        const t = s.textContent || '';
                        if (t.includes('__NUXT__') || t.includes('__NUXT_DATA__')) {
                            return t;
                        }
                    }
                    return null;
                }
            """)
            
            if not nuxt_raw:
                return result
            
            # JSON 파싱 시도
            try:
                data = json.loads(nuxt_raw)
            except:
                # __NUXT__= 형식에서 추출
                match = re.search(r'__NUXT__\s*=\s*(\{.+\})', nuxt_raw, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                    except:
                        return result
                else:
                    return result
            
            # 데이터에서 필요한 정보 추출
            result = self._extract_from_nuxt_structure(data)
            
        except Exception as e:
            print(f"Nuxt 데이터 추출 오류: {e}")
        
        return result

    def _extract_from_nuxt_structure(self, data: Any, depth: int = 0) -> dict:
        """Nuxt 데이터 구조에서 상품 정보 추출"""
        result = {}
        
        if depth > 10 or not data:
            return result
        
        if isinstance(data, dict):
            # 직접 키 매핑
            for key in ['title', 'name', 'productName', 'product_name']:
                if key in data and isinstance(data[key], str):
                    val = data[key].strip()
                    if 3 <= len(val) <= 200:
                        result['title'] = val
                        break
            
            for key in ['artistName', 'artist_name', 'sellerName', 'shopName', 'brandName']:
                if key in data and isinstance(data[key], str):
                    val = data[key].strip()
                    if 2 <= len(val) <= 100:
                        result['artist_name'] = val
                        break
            
            for key in ['price', 'salePrice', 'finalPrice', 'sellingPrice']:
                if key in data:
                    val = data[key]
                    if isinstance(val, (int, float)) and val > 0:
                        result['price'] = f"{int(val):,}원"
                        break
                    elif isinstance(val, str) and val.strip():
                        result['price'] = val.strip()
                        break
            
            for key in ['description', 'content', 'detail', 'introduction']:
                if key in data and isinstance(data[key], str):
                    val = data[key].strip()
                    if len(val) > 50:
                        result['description'] = val[:6000]
                        break
            
            # 옵션 추출
            for key in ['options', 'optionGroups', 'productOptions']:
                if key in data and isinstance(data[key], list):
                    opts = self._parse_options_from_list(data[key])
                    if opts:
                        result['options'] = opts
                        break
            
            # 이미지 추출
            for key in ['images', 'detailImages', 'productImages', 'imageUrls']:
                if key in data and isinstance(data[key], list):
                    imgs = [img for img in data[key] if isinstance(img, str) and img.startswith('http')]
                    if imgs:
                        result['images'] = imgs
                        break
            
            # 재귀 탐색
            for v in data.values():
                if not result.get('title') or not result.get('options'):
                    sub = self._extract_from_nuxt_structure(v, depth + 1)
                    for k, sv in sub.items():
                        if k not in result or not result[k]:
                            result[k] = sv
        
        elif isinstance(data, list):
            for item in data[:50]:
                sub = self._extract_from_nuxt_structure(item, depth + 1)
                for k, sv in sub.items():
                    if k not in result or not result[k]:
                        result[k] = sv
        
        return result

    def _parse_options_from_list(self, options_data: list) -> list[ProductOption]:
        """옵션 리스트 파싱"""
        options = []
        
        for opt in options_data[:20]:
            if not isinstance(opt, dict):
                continue
            
            name = (
                opt.get('name') or
                opt.get('optionName') or
                opt.get('groupName') or
                opt.get('title') or
                opt.get('label') or
                "옵션"
            )
            if isinstance(name, str):
                name = name.strip()
            else:
                name = "옵션"
            
            values = []
            values_data = (
                opt.get('values') or
                opt.get('optionValues') or
                opt.get('items') or
                opt.get('optionItems') or
                []
            )
            
            if isinstance(values_data, list):
                for v in values_data[:50]:
                    if isinstance(v, str):
                        values.append(v.strip())
                    elif isinstance(v, dict):
                        val = (
                            v.get('name') or
                            v.get('value') or
                            v.get('label') or
                            v.get('optionValue') or
                            ""
                        )
                        if isinstance(val, str) and val.strip():
                            values.append(val.strip())
            
            # 노이즈 제거
            values = [v for v in values if v and v not in ('선택', '선택하세요', '옵션 선택')]
            values = list(dict.fromkeys(values))
            
            if values:
                options.append(ProductOption(name=name, values=values))
        
        return options

    def _parse_api_responses(self, responses: dict, product_uuid: Optional[str]) -> dict:
        """캡처된 API 응답에서 데이터 추출"""
        result = {}
        
        for url, data in responses.items():
            if not isinstance(data, dict):
                continue
            
            # 데이터 구조 탐색
            payload = data.get('data') or data.get('result') or data
            
            if isinstance(payload, dict):
                # 제목
                for key in ['title', 'name', 'productName', 'product_name']:
                    if key in payload and isinstance(payload[key], str):
                        val = payload[key].strip()
                        if 3 <= len(val) <= 200 and not result.get('title'):
                            result['title'] = val
                
                # 작가명
                for key in ['artistName', 'artist_name', 'sellerName', 'shopName']:
                    if key in payload and isinstance(payload[key], str):
                        val = payload[key].strip()
                        if 2 <= len(val) <= 100 and not result.get('artist_name'):
                            result['artist_name'] = val
                
                # 가격
                for key in ['price', 'salePrice', 'finalPrice']:
                    if key in payload and not result.get('price'):
                        val = payload[key]
                        if isinstance(val, (int, float)) and val > 0:
                            result['price'] = f"{int(val):,}원"
                        elif isinstance(val, str):
                            result['price'] = val.strip()
                
                # 옵션
                for key in ['options', 'optionGroups', 'productOptions']:
                    if key in payload and isinstance(payload[key], list) and not result.get('options'):
                        opts = self._parse_options_from_list(payload[key])
                        if opts:
                            result['options'] = opts
                
                # 이미지
                for key in ['images', 'detailImages', 'productImages']:
                    if key in payload and isinstance(payload[key], list) and not result.get('images'):
                        imgs = []
                        for img in payload[key][:80]:
                            if isinstance(img, str) and img.startswith('http'):
                                imgs.append(img)
                            elif isinstance(img, dict):
                                img_url = img.get('url') or img.get('imageUrl') or img.get('src')
                                if isinstance(img_url, str) and img_url.startswith('http'):
                                    imgs.append(img_url)
                        if imgs:
                            result['images'] = imgs
        
        return result

    async def _extract_from_dom(self, page: Page) -> dict:
        """DOM에서 기본 정보 추출"""
        result = {}
        
        # 제목
        for sel in ['h1', '[class*="title"]', '[class*="product-name"]']:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text() or "").strip()
                    if 3 <= len(text) <= 200:
                        result['title'] = text
                        break
            except:
                continue
        
        # 작가명
        for sel in ['[class*="artist"]', '[class*="seller"]', '[class*="shop-name"]', 'a[href*="/artist/"]']:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text() or "").strip()
                    if 2 <= len(text) <= 100:
                        result['artist_name'] = text
                        break
            except:
                continue
        
        # 가격
        try:
            els = await page.query_selector_all('[class*="price"]')
            for el in els:
                text = (await el.inner_text() or "").strip()
                if re.search(r'[\d,]+\s*(원|₩)', text):
                    result['price'] = text
                    break
        except:
            pass
        
        # 설명 (긴 텍스트 블록 찾기)
        for sel in ['[class*="description"]', '[class*="detail"]', '[class*="content"]', 'article']:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text() or "").strip()
                    if len(text) > 100:
                        result['description'] = text[:6000]
                        break
            except:
                continue
        
        return result

    async def _extract_options_from_dom(self, page: Page) -> list[ProductOption]:
        """DOM에서 옵션 추출"""
        options = []
        
        # select 요소에서 옵션 추출
        try:
            selects = await page.query_selector_all('select')
            for idx, sel in enumerate(selects):
                opt_els = await sel.query_selector_all('option')
                values = []
                for opt in opt_els:
                    text = (await opt.inner_text() or "").strip()
                    if text and text not in ('선택', '선택하세요', '옵션 선택', '옵션을 선택해주세요'):
                        values.append(text)
                values = list(dict.fromkeys(values))
                if values:
                    options.append(ProductOption(name=f"옵션 {idx+1}", values=values))
        except:
            pass
        
        # role="listbox" 또는 role="option"에서 추출
        try:
            listboxes = await page.query_selector_all('[role="listbox"], [role="combobox"]')
            for idx, lb in enumerate(listboxes):
                opt_els = await lb.query_selector_all('[role="option"]')
                values = []
                for opt in opt_els:
                    text = (await opt.inner_text() or "").strip()
                    if text and len(text) <= 100:
                        values.append(text)
                values = list(dict.fromkeys(values))
                if values and len(values) >= 2:
                    options.append(ProductOption(name=f"옵션 {len(options)+1}", values=values))
        except:
            pass
        
        return options

    async def _extract_options_interactive(self, page: Page) -> list[ProductOption]:
        """인터랙티브 방식으로 옵션 추출 (버튼 클릭)"""
        options = []
        
        # 옵션 선택 트리거 찾기 및 클릭
        triggers = [
            'text=/옵션.*선택/i',
            'button:has-text("옵션")',
            'button:has-text("선택")',
            '[aria-haspopup="listbox"]',
            '[role="combobox"]',
        ]
        
        for trigger in triggers:
            try:
                el = await page.query_selector(trigger)
                if el:
                    # 클릭하여 옵션 패널 열기
                    await el.click()
                    await asyncio.sleep(0.8)
                    
                    # 열린 패널에서 옵션 수집
                    panel_options = await self._collect_options_from_panel(page)
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
        
        # 옵션 그룹 라벨 클릭 시도 (예: "1. 쿠키 선택")
        if not options:
            try:
                group_labels = await page.query_selector_all('text=/^\\s*\\d+\\./i')
                for gl in group_labels[:5]:
                    try:
                        group_text = (await gl.inner_text() or "").strip()
                        await gl.click()
                        await asyncio.sleep(0.6)
                        
                        panel_options = await self._collect_options_from_panel(page)
                        if panel_options:
                            # 그룹명 설정
                            group_name = re.sub(r'^\s*\d+\.?\s*', '', group_text).strip() or "옵션"
                            for opt in panel_options:
                                opt.name = group_name
                            options.extend(panel_options)
                        
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.3)
                    except:
                        continue
            except:
                pass
        
        # 중복 제거
        merged = {}
        for opt in options:
            merged.setdefault(opt.name, [])
            merged[opt.name].extend(opt.values)
        
        return [
            ProductOption(name=name, values=list(dict.fromkeys(vals)))
            for name, vals in merged.items()
            if vals
        ]

    async def _collect_options_from_panel(self, page: Page) -> list[ProductOption]:
        """열린 옵션 패널에서 옵션 값 수집"""
        options = []
        
        # 패널/다이얼로그/시트 찾기
        panel_selectors = [
            '[role="dialog"]',
            '[role="listbox"]',
            '[class*="modal"]',
            '[class*="sheet"]',
            '[class*="bottom"]',
            '[class*="dropdown"]',
            '[class*="popup"]',
        ]
        
        panel = None
        for sel in panel_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    # 실제로 보이는지 확인
                    box = await el.bounding_box()
                    if box and box['height'] > 50:
                        panel = el
                        break
            except:
                continue
        
        search_root = panel if panel else page
        
        # 옵션 아이템 수집
        option_selectors = [
            '[role="option"]',
            'li',
            'button',
            '[class*="option-item"]',
            '[class*="item"]',
        ]
        
        values = []
        for sel in option_selectors:
            try:
                items = await search_root.query_selector_all(sel)
                for item in items[:80]:
                    text = (await item.inner_text() or "").strip()
                    if not text:
                        continue
                    # 멀티라인이면 첫 줄만
                    if '\n' in text:
                        text = text.split('\n')[0].strip()
                    # 노이즈 필터링
                    if text in ('선택', '선택하세요', '옵션 선택', '장바구니', '구매하기', '선물하기'):
                        continue
                    if '옵션을 선택' in text:
                        continue
                    if len(text) > 100:
                        continue
                    values.append(text)
                
                values = list(dict.fromkeys(values))
                if len(values) >= 2:
                    break
            except:
                continue
        
        if values:
            options.append(ProductOption(name="옵션", values=values))
        
        return options

    async def _extract_images_from_dom(self, page: Page) -> list[str]:
        """DOM에서 이미지 URL 추출"""
        images = []
        
        try:
            # img 태그에서 추출
            img_els = await page.query_selector_all('img')
            for img in img_els:
                # src 속성들 확인
                for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                    try:
                        val = await img.get_attribute(attr)
                        if val and val.startswith('http'):
                            images.append(val)
                            break
                    except:
                        continue
                
                # srcset 처리
                try:
                    srcset = await img.get_attribute('srcset')
                    if srcset:
                        # 가장 큰 이미지 선택
                        parts = [p.strip().split()[0] for p in srcset.split(',') if p.strip()]
                        if parts:
                            images.append(parts[-1])
                except:
                    pass
            
            # source 태그 (picture 요소)
            source_els = await page.query_selector_all('source')
            for src in source_els:
                try:
                    srcset = await src.get_attribute('srcset')
                    if srcset:
                        parts = [p.strip().split()[0] for p in srcset.split(',') if p.strip()]
                        if parts:
                            images.append(parts[-1])
                except:
                    continue
            
            # background-image 스타일에서 추출
            try:
                bg_images = await page.evaluate("""
                    () => {
                        const urls = [];
                        const elements = document.querySelectorAll('[style*="background"]');
                        elements.forEach(el => {
                            const style = el.getAttribute('style') || '';
                            const matches = style.match(/url\\(['\"]?(https?:\\/\\/[^'\"\\)]+)['\"]?\\)/gi);
                            if (matches) {
                                matches.forEach(m => {
                                    const url = m.replace(/url\\(['\"]?|['\"]?\\)/gi, '');
                                    urls.push(url);
                                });
                            }
                        });
                        return urls;
                    }
                """)
                images.extend(bg_images or [])
            except:
                pass
            
        except Exception as e:
            print(f"DOM 이미지 추출 오류: {e}")
        
        # 중복 제거
        return list(dict.fromkeys(images))


# 테스트용 코드
if __name__ == "__main__":
    async def test():
        scraper = IdusScraper()
        await scraper.initialize()
        
        test_url = "https://www.idus.com/v2/product/87beb859-49b2-4c18-86b4-f300b31d6247"
        
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
