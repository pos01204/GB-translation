"""
아이디어스(Idus) 상품 크롤링 모듈
Playwright + playwright-stealth를 사용하여 봇 탐지 우회
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
            
            # Railway/Docker 환경 감지
            is_docker = os.path.exists('/.dockerenv') or os.getenv('RAILWAY_ENVIRONMENT')
            
            # Chromium 브라우저 실행 (headless 모드)
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
            ]
            
            # Docker 환경에서는 single-process 추가
            if is_docker:
                launch_args.append('--single-process')
                print("🐳 Docker 환경 감지됨")
            
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=launch_args
            )
            
            # 브라우저 컨텍스트 생성
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='ko-KR',
            )
            
            self._initialized = True
            print("✅ Playwright 브라우저 초기화 완료")
            
        except Exception as e:
            print(f"❌ Playwright 초기화 실패: {e}")
            # 리소스 정리
            await self._cleanup()
            raise
        
    async def _cleanup(self):
        """리소스 정리 (내부용)"""
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
        # 초기화 확인
        if not self._initialized:
            await self.initialize()
            
        page = await self._create_stealth_page()
        
        try:
            # 페이지 로드
            print(f"📄 페이지 로딩 중: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # 추가 대기 (동적 콘텐츠 로딩)
            await asyncio.sleep(2)

            # 상세/옵션 영역은 스크롤 후 로딩되는 경우가 많음
            await self._prepare_dynamic_sections(page)

            # 0) Idus는 Next.js 기반이라 __NEXT_DATA__에 구조화된 데이터가 들어있는 경우가 많음
            #    먼저 여기서 최대한 추출하고, 부족한 부분은 DOM 스크래핑으로 보완
            next_data = await self._extract_from_next_data(page)
            
            # 기본 정보 추출
            title = await self._extract_title(page)
            artist_name = await self._extract_artist_name(page)
            price = await self._extract_price(page)
            description = await self._extract_description(page)
            
            # 옵션 추출 (버튼 클릭 후)
            options = await self._extract_options(page)
            
            # 상세 이미지 URL 추출
            detail_images = await self._extract_detail_images(page)

            # next_data로 보강 (next_data가 더 신뢰도 높은 경우가 많음)
            if next_data:
                title = self._pick_best_text(next_data.get("title"), title)
                artist_name = self._pick_best_text(next_data.get("artist_name"), artist_name)
                price = self._pick_best_text(next_data.get("price"), price)
                description = self._pick_best_description(next_data.get("description"), description)

                # 옵션/이미지는 next_data가 비어있지 않으면 우선 사용 (DOM은 누락/노이즈가 잦음)
                nd_options = next_data.get("options") or []
                if nd_options:
                    options = nd_options
                nd_images = next_data.get("detail_images") or []
                if nd_images:
                    detail_images = nd_images
            
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

    def _pick_best_text(self, candidate: Any, fallback: str) -> str:
        """candidate가 유효한 텍스트면 선택, 아니면 fallback."""
        if isinstance(candidate, str):
            c = candidate.strip()
            if c and c not in ("제목 없음", "설명 없음", "가격 정보 없음"):
                return c
        return fallback

    def _pick_best_description(self, candidate: Any, fallback: str) -> str:
        """설명은 길이가 긴 쪽을 우선 선택."""
        c = candidate.strip() if isinstance(candidate, str) else ""
        f = fallback.strip() if isinstance(fallback, str) else ""
        if c and (len(c) >= max(200, len(f) + 40)):
            return c[:6000]
        return fallback[:6000] if isinstance(fallback, str) else fallback

    async def _extract_from_next_data(self, page: Page) -> dict[str, Any]:
        """
        Idus Next.js 페이지의 script#__NEXT_DATA__에서 구조화 데이터 추출.
        - title / artist_name / price / description / options / detail_images 를 최대한 채움
        """
        try:
            raw = await page.eval_on_selector("script#__NEXT_DATA__", "el => el.textContent")
            if not raw:
                return {}
            data = json.loads(raw)
        except Exception:
            return {}

        # JSON 트리에서 (path, key, value) 형태로 모든 항목을 수집
        items: list[tuple[str, str, Any]] = []

        def walk(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    p = f"{path}.{k}" if path else k
                    items.append((path, k, v))
                    walk(v, p)
            elif isinstance(obj, list):
                for i, v in enumerate(obj[:2000]):  # 안전장치
                    walk(v, f"{path}[{i}]")

        walk(data)

        # ---- title 후보 ----
        title_keys = {"title", "name", "productName", "product_title"}
        title_candidates: list[str] = []
        for _, k, v in items:
            if k in title_keys and isinstance(v, str):
                s = v.strip()
                if 3 <= len(s) <= 120:
                    title_candidates.append(s)

        # ---- artist/shop 후보 ----
        artist_keys = {"artistName", "sellerName", "shopName", "brandName", "storeName", "makerName"}
        artist_candidates: list[str] = []
        for _, k, v in items:
            if k in artist_keys and isinstance(v, str):
                s = v.strip()
                if 2 <= len(s) <= 80:
                    artist_candidates.append(s)

        # ---- price 후보 ----
        price_keys = {"price", "salePrice", "sellingPrice", "discountPrice", "finalPrice"}
        price_candidates: list[str] = []
        for _, k, v in items:
            if k in price_keys:
                if isinstance(v, (int, float)):
                    if v > 0:
                        price_candidates.append(f"{int(v):,}원")
                elif isinstance(v, str):
                    s = v.strip()
                    if re.search(r"[\d,]+\s*(원|₩)", s) or s.isdigit():
                        price_candidates.append(s if "원" in s or "₩" in s else f"{s}원")

        # ---- description 후보 ----
        desc_key_hints = ("description", "content", "detail", "introduction", "story", "body", "text")
        desc_candidates: list[str] = []
        for path, k, v in items:
            if isinstance(v, str) and any(h in k.lower() for h in desc_key_hints):
                s = v.strip()
                # 너무 짧거나 UI 라벨은 제외
                if len(s) >= 120 and "이용약관" not in s and "개인정보" not in s:
                    desc_candidates.append(s)
            # Idus 상세는 POINT 01~ 형태가 많아서 이 패턴이 포함된 문자열도 후보
            if isinstance(v, str) and re.search(r"POINT\s*0?1", v, re.IGNORECASE):
                s = v.strip()
                if len(s) >= 200:
                    desc_candidates.append(s)

        # ---- images 후보 (detail images) ----
        img_candidates: list[str] = []
        for _, k, v in items:
            if isinstance(v, str) and ("http://" in v or "https://" in v):
                if re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", v, re.IGNORECASE):
                    # svg / icon 제외
                    if v.lower().endswith(".svg"):
                        continue
                    img_candidates.append(v)
        img_candidates = list(dict.fromkeys(img_candidates))

        # ---- options 후보 ----
        # 다양한 구조를 커버하기 위해:
        # 1) option/value 형태의 dict list
        # 2) labels + values 배열
        option_objs: list[dict[str, Any]] = []
        for path, k, v in items:
            if isinstance(v, list) and ("option" in k.lower() or "options" in k.lower()):
                # 리스트 내 dict가 있고, dict에 name/value/values 같은 키가 있으면 옵션 후보로
                for el in v[:200]:
                    if isinstance(el, dict):
                        lk = {kk.lower() for kk in el.keys()}
                        if "name" in lk and ("values" in lk or "value" in lk or "items" in lk):
                            option_objs.append(el)

        parsed_options: list[ProductOption] = []
        for obj in option_objs[:20]:
            try:
                name = (obj.get("name") or obj.get("title") or obj.get("label") or "").strip()
                vals_raw = obj.get("values") or obj.get("items") or obj.get("value") or []
                values: list[str] = []
                if isinstance(vals_raw, list):
                    for it in vals_raw[:200]:
                        if isinstance(it, str):
                            s = it.strip()
                            if s:
                                values.append(s)
                        elif isinstance(it, dict):
                            s = (it.get("name") or it.get("label") or it.get("value") or "").strip()
                            if s:
                                values.append(s)
                elif isinstance(vals_raw, str):
                    if vals_raw.strip():
                        values.append(vals_raw.strip())
                values = [v for v in values if v not in ("선택", "선택하세요", "옵션 선택")]
                values = list(dict.fromkeys(values))
                if not name:
                    name = "옵션"
                if values:
                    parsed_options.append(ProductOption(name=name, values=values))
            except:
                continue
        # 옵션 그룹명이 제대로 나오지 않는 경우가 많아서 중복 name을 합치기
        merged: dict[str, list[str]] = {}
        for opt in parsed_options:
            merged.setdefault(opt.name, [])
            merged[opt.name].extend(opt.values)
        merged_options: list[ProductOption] = []
        for name, vals in merged.items():
            uniq = list(dict.fromkeys([v for v in vals if v]))
            if uniq:
                merged_options.append(ProductOption(name=name, values=uniq))

        # 최종 선택 로직
        def pick_longest(arr: list[str], min_len: int = 1, max_len: int = 10000) -> str:
            best = ""
            for s in arr:
                s2 = (s or "").strip()
                if min_len <= len(s2) <= max_len and len(s2) > len(best):
                    best = s2
            return best

        title = pick_longest(title_candidates, min_len=3, max_len=140)
        artist_name = pick_longest(artist_candidates, min_len=2, max_len=80)
        price = pick_longest(price_candidates, min_len=2, max_len=40)
        description = pick_longest(desc_candidates, min_len=120, max_len=20000)[:6000]

        # 이미지: 너무 많은 경우엔 상위 N개만
        max_imgs = 40
        detail_images = img_candidates[:max_imgs]

        result: dict[str, Any] = {}
        if title:
            result["title"] = title
        if artist_name:
            result["artist_name"] = artist_name
        if price:
            result["price"] = price
        if description:
            result["description"] = description
        if merged_options:
            result["options"] = merged_options
        if detail_images:
            result["detail_images"] = detail_images
        return result

    async def _prepare_dynamic_sections(self, page: Page) -> None:
        """
        동적 로딩(상세 탭/지연 이미지/옵션 영역)을 준비하기 위한 공통 처리.
        - 상세 탭(작품정보 등) 클릭 시도
        - 페이지 하단 스크롤로 lazy-load 콘텐츠 로딩 유도
        """
        # 1) 탭 클릭 시도 (실패해도 무시)
        tab_text_candidates = ["작품정보", "상품정보", "상세정보", "정보", "작품 정보"]
        for t in tab_text_candidates:
            try:
                el = await page.query_selector(f'text="{t}"')
                if el:
                    await el.click()
                    await asyncio.sleep(0.5)
                    break
            except:
                continue

        # 2) 스크롤로 지연 로딩 유도
        try:
            await self._auto_scroll(page, max_steps=8, step_px=1200, pause_sec=0.4)
        except:
            pass

    async def _auto_scroll(self, page: Page, max_steps: int = 8, step_px: int = 1200, pause_sec: float = 0.4) -> None:
        """하단 스크롤 반복으로 lazy-load 콘텐츠 로딩을 유도."""
        for _ in range(max_steps):
            await page.evaluate(f"window.scrollBy(0, {step_px});")
            await asyncio.sleep(pause_sec)
        # 마지막에 상단으로 살짝 올려 sticky UI 상태 정리
        try:
            await page.evaluate("window.scrollBy(0, -400);")
        except:
            pass
    
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
        # 0) POINT 01 같은 상세 텍스트 블록을 우선적으로 찾기 (가장 정보가 풍부한 경우가 많음)
        try:
            point_el = await page.query_selector('text=/POINT\\s*0?1/i')
            if point_el:
                # 가까운 컨테이너(섹션/아티클/디브) 중 텍스트가 긴 블록을 선택
                rich_text = await point_el.evaluate(
                    """(el) => {
                        const candidates = [];
                        let cur = el;
                        for (let i=0;i<6 && cur;i++){
                          cur = cur.parentElement;
                          if (!cur) break;
                          const t = (cur.innerText || '').trim();
                          if (t && t.length > 200) candidates.push(t);
                        }
                        candidates.sort((a,b)=>b.length-a.length);
                        return candidates[0] || '';
                    }"""
                )
                if rich_text and len(rich_text.strip()) > 200:
                    return rich_text.strip()[:4000]
        except:
            pass

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
                        return text.strip()[:4000]  # 최대 4000자
            except:
                continue
                
        return "설명 없음"
    
    async def _extract_options(self, page: Page) -> list[ProductOption]:
        """
        옵션 추출 - '옵션 선택' 버튼 클릭하여 숨겨진 옵션 표시
        """
        options: list[ProductOption] = []

        # 0) 옵션 UI는 클릭해야 DOM에 리스트가 나타나는 경우가 많아서 여러 번 확장 시도
        await self._expand_option_ui(page)
        
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
        
        # 1) <select> 기반 옵션 우선 추출
        try:
            selects = await page.query_selector_all('select')
            for idx, sel in enumerate(selects):
                try:
                    opt_elements = await sel.query_selector_all('option')
                    values: list[str] = []
                    for opt in opt_elements:
                        v = (await opt.inner_text()) or ""
                        v = v.strip()
                        if v and v not in ("선택하세요", "선택", "옵션 선택"):
                            values.append(v)
                    values = list(dict.fromkeys(values))
                    if values:
                        options.append(ProductOption(name=f"옵션 {idx+1}", values=values))
                except:
                    continue
        except:
            pass

        # 2) 커스텀 드롭다운/리스트박스 기반 옵션 추출
        option_group_selectors = [
            '[role="listbox"]',
            '[role="combobox"]',
            '[class*="option"]',
            '[class*="Option"]',
            '[data-testid*="option"]',
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
                        value_elements = await group.query_selector_all(
                            '[role="option"], [class*="value"], [class*="option-text"], li, button, span'
                        )
                        for val_el in value_elements:
                            value = await val_el.inner_text()
                            if value and value.strip():
                                values.append(value.strip())
                    
                    if values:
                        # 너무 일반적인 텍스트(페이지 전체/버튼 라벨 등) 제거
                        values = [v for v in values if len(v) <= 120 and "아이디어스" not in v]
                        values = [v for v in values if v not in ("옵션 선택", "옵션", "선택")]
                        values = list(dict.fromkeys(values))
                        if not option_name or option_name == "옵션":
                            option_name = f"옵션 {len(options)+1}"
                        options.append(ProductOption(
                            name=option_name,
                            values=values
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

    async def _expand_option_ui(self, page: Page) -> None:
        """
        옵션 영역이 접혀있거나, 드롭다운을 눌러야 옵션이 DOM에 나타나는 케이스를 대비해
        '옵션 선택/선택' 관련 트리거들을 반복 클릭해 옵션 리스트를 최대한 노출시킵니다.
        """
        triggers = [
            'button:has-text("옵션 선택")',
            'button:has-text("옵션")',
            'button:has-text("선택")',
            '[role="combobox"]',
            '[aria-haspopup="listbox"]',
            # Idus 옵션 그룹(예: "1. 쿠키 선택")이 버튼/role로 렌더되는 케이스 대응
            '[class*="option"] [role="button"]',
            '[class*="Option"] [role="button"]',
        ]
        clicked = 0
        for _ in range(2):  # 2패스만 수행 (과도한 클릭 방지)
            for sel in triggers:
                try:
                    els = await page.query_selector_all(sel)
                    for el in els[:5]:  # 너무 많으면 상위 몇 개만
                        try:
                            # 화면 밖 요소는 스킵
                            box = await el.bounding_box()
                            if not box:
                                continue
                            await el.click()
                            clicked += 1
                            await asyncio.sleep(0.4)
                        except:
                            continue
                except:
                    continue
        if clicked:
            print(f"🔘 옵션 UI 확장 클릭 {clicked}회 수행")
    
    async def _extract_detail_images(self, page: Page) -> list[str]:
        """상세 이미지 URL 추출"""
        images = []

        # 상세 이미지는 스크롤해야 늦게 로딩되는 경우가 많음
        try:
            await self._auto_scroll(page, max_steps=10, step_px=1400, pause_sec=0.35)
        except:
            pass
        
        # 상세 이미지 영역 셀렉터
        detail_selectors = [
            '[class*="detail"] img',
            '[class*="description"] img',
            '[class*="content"] img',
            '[class*="product-info"] img',
            'article img',
            'img',
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
        # 중복 제거/상위 N개 제한
        images = list(dict.fromkeys(images))
        return images[:30]  # 최대 30개까지만


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
