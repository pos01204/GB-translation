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

        # lazy-load 이미지 누락을 줄이기 위해 네트워크로 로딩된 image 요청 URL도 수집
        network_image_urls: list[str] = []

        def _on_response(resp):
            try:
                req = resp.request
                if getattr(req, "resource_type", None) == "image":
                    u = resp.url
                    if u and u.startswith("http"):
                        network_image_urls.append(u)
            except Exception:
                pass

        try:
            page.on("response", _on_response)
        except Exception:
            pass
        
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

            # 옵션이 비면 인터랙티브 방식으로 재시도 (next_data 유무와 무관하게)
            if not options:
                try:
                    options = await self._extract_options_interactive(page)
                except Exception as e:
                    print(f"⚠️ 인터랙티브 옵션 추출 실패: {e}")
            
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
                # next_data에서 옵션을 못 찾았으면(혹은 빈 값이면) 인터랙티브 방식으로 한 번 더 시도
                if not options:
                    try:
                        options = await self._extract_options_interactive(page)
                    except Exception as e:
                        print(f"⚠️ 인터랙티브 옵션 추출 실패: {e}")
                # 이미지가 너무 적으면(누락 가능성 높음) 확장 수집
                if detail_images and len(detail_images) < 8:
                    try:
                        detail_images = list(dict.fromkeys(detail_images + (await self._extract_detail_images(page))))
                    except:
                        pass

            # 네트워크/HTML 기반으로 이미지 후보 추가 수집 (하단 lazy-load 누락 완화)
            try:
                html_imgs = await self._extract_image_urls_from_html(page)
            except Exception:
                html_imgs = []

            if network_image_urls:
                # fragment 제거로 중복 완화
                network_image_urls = [u.split("#")[0] for u in network_image_urls]

            detail_images = list(dict.fromkeys(detail_images + html_imgs + network_image_urls))
            detail_images = detail_images[:80]
            
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
            try:
                page.remove_listener("response", _on_response)
            except Exception:
                pass

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
        # Idus CDN은 확장자가 없거나 query로만 타입이 붙는 케이스가 있어 완화해서 수집
        img_candidates: list[str] = []
        for path, k, v in items:
            if isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")):
                low = v.lower()
                if low.endswith(".svg"):
                    continue
                # 1) 확장자 기반
                if re.search(r"\.(jpg|jpeg|png|webp|gif)(\?|$)", v, re.IGNORECASE):
                    img_candidates.append(v)
                    continue
                # 2) 키/경로 기반 (imageUrl, thumbnailUrl, etc)
                k_low = k.lower()
                p_low = path.lower()
                if any(x in k_low for x in ["image", "img", "thumbnail", "thumb", "photo", "banner"]) or any(
                    x in p_low for x in ["image", "img", "thumbnail", "detail", "description", "content"]
                ):
                    # 아이콘/스프라이트는 제외
                    if any(x in low for x in ["sprite", "icon", "logo"]):
                        continue
                    img_candidates.append(v)

        img_candidates = list(dict.fromkeys(img_candidates))

        # ---- options 후보 ----
        # 다양한 구조를 커버하기 위해:
        # 1) option/value 형태의 dict list
        # 2) labels + values 배열
        # 3) groupName/optionItems/variants 형태
        option_objs: list[dict[str, Any]] = []
        for path, k, v in items:
            if isinstance(v, list) and ("option" in k.lower() or "options" in k.lower()):
                # 리스트 내 dict가 있고, dict에 name/value/values 같은 키가 있으면 옵션 후보로
                for el in v[:200]:
                    if isinstance(el, dict):
                        lk = {kk.lower() for kk in el.keys()}
                        if "name" in lk and ("values" in lk or "value" in lk or "items" in lk):
                            option_objs.append(el)
                        # Idus에서 자주 보이는 형태: optionName + optionValues
                        if ("optionname" in lk or "label" in lk or "title" in lk) and (
                            "optionvalues" in lk or "values" in lk or "items" in lk
                        ):
                            option_objs.append(el)
                        # groupName + optionItems/variants 형태
                        if ("groupname" in lk or "optiongroupname" in lk) and (
                            "optionitems" in lk or "variants" in lk or "items" in lk or "values" in lk
                        ):
                            option_objs.append(el)

        # dict 단독으로도 option group이 들어오는 케이스가 있어 추가로 탐색
        for path, k, v in items:
            if isinstance(v, dict) and ("option" in k.lower() or "options" in k.lower()):
                lk = {kk.lower() for kk in v.keys()}
                if ("name" in lk or "optionname" in lk or "label" in lk or "title" in lk) and (
                    "values" in lk or "items" in lk or "optionvalues" in lk
                ):
                    option_objs.append(v)
                if ("groupname" in lk or "optiongroupname" in lk) and (
                    "optionitems" in lk or "variants" in lk or "items" in lk or "values" in lk or "optionvalues" in lk
                ):
                    option_objs.append(v)

        parsed_options: list[ProductOption] = []
        for obj in option_objs[:20]:
            try:
                name = (
                    obj.get("name")
                    or obj.get("optionName")
                    or obj.get("groupName")
                    or obj.get("optionGroupName")
                    or obj.get("title")
                    or obj.get("label")
                    or ""
                ).strip()
                vals_raw = (
                    obj.get("values")
                    or obj.get("optionValues")
                    or obj.get("optionItems")
                    or obj.get("variants")
                    or obj.get("items")
                    or obj.get("value")
                    or []
                )
                values: list[str] = []
                if isinstance(vals_raw, list):
                    for it in vals_raw[:200]:
                        if isinstance(it, str):
                            s = it.strip()
                            if s:
                                values.append(s)
                        elif isinstance(it, dict):
                            s = (
                                it.get("name")
                                or it.get("label")
                                or it.get("value")
                                or it.get("optionValue")
                                or it.get("displayName")
                                or it.get("optionName")
                                or ""
                            ).strip()
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

        # 옵션이 여전히 비어있으면, next_data 전체에서 "옵션" 관련 문자열을 약하게 수집(최후의 안전장치)
        if not parsed_options:
            loose_values: list[str] = []
            for path, k, v in items:
                if isinstance(v, str) and ("option" in k.lower() or "option" in path.lower() or "옵션" in v):
                    s = v.strip()
                    if 2 <= len(s) <= 80 and s not in ("옵션", "옵션 선택", "옵션을 선택해주세요.", "선택", "선택하세요"):
                        loose_values.append(s)
            loose_values = list(dict.fromkeys(loose_values))
            # 너무 일반적인 텍스트는 제외
            loose_values = [v for v in loose_values if "옵션을 선택" not in v]
            if loose_values:
                parsed_options.append(ProductOption(name="옵션", values=loose_values[:50]))
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
        max_imgs = 80
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

    async def _extract_options_interactive(self, page: Page) -> list[ProductOption]:
        """
        DOM에서 옵션이 비어있는 경우를 대비해, 실제로 옵션 UI를 열어서(role=listbox/option)
        화면에 표시되는 값을 수집하는 방식.
        """
        results: list[ProductOption] = []

        # 0) Idus에서 자주 보이는 트리거: "옵션을 선택해주세요" 영역을 먼저 클릭 시도
        try:
            hint = await page.query_selector('text=/옵션을\\s*선택해주세요/i')
            if hint:
                clickable = await hint.evaluate_handle(
                    """(el) => el.closest('button,[role="button"],[role="combobox"],div')"""
                )
                try:
                    try:
                        await clickable.scroll_into_view_if_needed()
                    except:
                        pass
                    await clickable.click()
                    await asyncio.sleep(0.6)
                except:
                    pass
        except:
            pass

        # 0.5) 옵션 그룹 라벨(예: "1. 쿠키 선택")이 페이지에 있으면 직접 클릭해 리스트를 띄우는 경로를 우선 시도
        try:
            group_labels = await page.query_selector_all("text=/^\\s*\\d+\\./")
            for gl in group_labels[:5]:
                try:
                    await gl.scroll_into_view_if_needed()
                except:
                    pass
                try:
                    await gl.click()
                    await asyncio.sleep(0.6)
                except:
                    continue

                # dialog/listbox가 뜨면 role=option을 수집하고 종료
                try:
                    await page.wait_for_selector('[role="option"], [role="listbox"], [role="dialog"]', timeout=2000)
                except:
                    pass
                # 실제 option 텍스트 수집 (dialog 우선)
                scope = None
                for scope_sel in ['[role="dialog"]', '[class*="modal"]', '[class*="sheet"]', '[class*="bottom"]']:
                    try:
                        el = await page.query_selector(scope_sel)
                        if el:
                            scope = el
                            break
                    except:
                        continue
                search_root = scope if scope else page
                option_els = await search_root.query_selector_all('[role="option"], li[role="option"], li, button')
                values: list[str] = []
                for opt in option_els[:120]:
                    try:
                        t = ((await opt.inner_text()) or "").strip()
                        if not t:
                            continue
                        if t in ("선택", "선택하세요", "옵션 선택", "장바구니", "구매하기", "선물하기"):
                            continue
                        if "옵션을 선택해주세요" in t:
                            continue
                        if "\n" in t:
                            t = t.split("\n")[0].strip()
                        if 1 <= len(t) <= 120:
                            values.append(t)
                    except:
                        continue
                values = list(dict.fromkeys(values))
                try:
                    await page.keyboard.press("Escape")
                except:
                    pass

                if values:
                    # "1. 쿠키 선택" -> "쿠키 선택"
                    group_name = ((await gl.inner_text()) or "").strip()
                    group_name = re.sub(r"^\\s*\\d+\\.", "", group_name).strip() or "옵션"
                    results.append(ProductOption(name=group_name, values=values))
                    # 직접 경로로 성공했으면 추가 탐색은 생략
                    return results
        except:
            pass

        # 구매 영역 근처의 트리거를 최대한 포괄
        trigger_selectors = [
            '[aria-haspopup="listbox"]',
            '[role="combobox"]',
            'button:has-text("옵션")',
            'button:has-text("선택")',
        ]

        triggers: list[Any] = []
        for sel in trigger_selectors:
            try:
                els = await page.query_selector_all(sel)
                triggers.extend(els)
            except:
                continue

        # 중복 트리거 제거 (bounding box + text 조합)
        uniq: list[Any] = []
        seen: set[str] = set()
        for el in triggers:
            try:
                txt = ((await el.inner_text()) or "").strip()
                box = await el.bounding_box()
                key = f"{txt}|{int(box['x']) if box else -1}|{int(box['y']) if box else -1}"
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(el)
            except:
                continue

        # 상위 몇 개만 시도 (너무 많으면 오탐)
        uniq = uniq[:8]

        for idx, trig in enumerate(uniq):
            try:
                # 옵션 그룹명 추정: 트리거 주변 텍스트에서 "1." 같은 라인을 우선
                group_name = await trig.evaluate(
                    """(el) => {
                      const container = el.closest('section, article, div') || el.parentElement;
                      const t = (container?.innerText || '').trim();
                      const lines = t.split('\\n').map(s=>s.trim()).filter(Boolean);
                      // "1. 쿠키 선택" 형태 우선
                      const hit = lines.find(l => /^\\d+\\./.test(l) && l.length <= 50);
                      if (hit) return hit.replace(/^\\d+\\./, '').trim();
                      // 그 외에는 첫 줄 후보
                      return (lines[0] || '').slice(0, 50);
                    }"""
                )
                group_name = (group_name or "").strip() or f"옵션 {idx+1}"

                # 클릭해서 옵션 노출
                await trig.click()
                await asyncio.sleep(0.5)

                # 옵션 항목 후보들 수집: dialog/bottom-sheet 내부로 범위를 좁혀 노이즈를 줄임
                scope = None
                for scope_sel in ['[role="dialog"]', '[class*="modal"]', '[class*="sheet"]', '[class*="bottom"]']:
                    try:
                        el = await page.query_selector(scope_sel)
                        if el:
                            scope = el
                            break
                    except:
                        continue

                search_root = scope if scope else page
                option_els = []
                for opt_sel in ['[role="option"]', 'li[role="option"]', '[class*="dropdown"] li', 'li', 'button', '[class*="item"]']:
                    try:
                        option_els = await search_root.query_selector_all(opt_sel)
                        if option_els and len(option_els) >= 2:
                            break
                    except:
                        continue

                values: list[str] = []
                for opt in option_els[:60]:
                    try:
                        t = ((await opt.inner_text()) or "").strip()
                        if not t:
                            continue
                        # UI/푸터/버튼 텍스트 등 노이즈 제거
                        if t in ("선택", "선택하세요", "옵션 선택", "장바구니", "구매하기", "선물하기"):
                            continue
                        if "옵션을 선택해주세요" in t:
                            continue
                        if len(t) > 120:
                            continue
                        # 너무 많은 줄이 섞이면 첫 줄만
                        if "\n" in t:
                            t = t.split("\n")[0].strip()
                        values.append(t)
                    except:
                        continue

                values = list(dict.fromkeys(values))

                # 그룹명만 잡히고 실제 값이 안 잡히는 케이스(“쿠키 선택”만 나옴)를 위해:
                # 그룹 후보를 눌러 한 번 더 값을 수집
                if values and len(values) <= 3:
                    group_like = [
                        v for v in values
                        if any(k in v for k in ["선택", "옵션"]) or re.match(r"^\d+\.", v)
                    ]
                    if group_like:
                        try:
                            group_el = await search_root.query_selector(f'text="{group_like[0]}"')
                            if group_el:
                                await group_el.click()
                                await asyncio.sleep(0.5)
                                option_els2 = await search_root.query_selector_all('[role="option"], li, button')
                                values2: list[str] = []
                                for opt2 in option_els2[:80]:
                                    try:
                                        tt = ((await opt2.inner_text()) or "").strip()
                                        if not tt or len(tt) > 120:
                                            continue
                                        if tt in ("선택", "선택하세요", "옵션 선택", "장바구니", "구매하기", "선물하기"):
                                            continue
                                        if "옵션을 선택해주세요" in tt:
                                            continue
                                        if "\n" in tt:
                                            tt = tt.split("\n")[0].strip()
                                        values2.append(tt)
                                    except:
                                        continue
                                values2 = list(dict.fromkeys(values2))
                                if len(values2) > len(values):
                                    values = values2
                        except:
                            pass

                # 닫기 (ESC)
                try:
                    await page.keyboard.press("Escape")
                except:
                    pass
                await asyncio.sleep(0.2)

                if values:
                    results.append(ProductOption(name=group_name, values=values))
            except:
                # 트리거 하나 실패해도 계속
                try:
                    await page.keyboard.press("Escape")
                except:
                    pass
                continue

        # 중복/빈값 정리
        merged: dict[str, list[str]] = {}
        for opt in results:
            merged.setdefault(opt.name, [])
            merged[opt.name].extend(opt.values)
        out: list[ProductOption] = []
        for name, vals in merged.items():
            uniq_vals = list(dict.fromkeys([v for v in vals if v and v not in ("선택", "선택하세요")]))
            if uniq_vals:
                out.append(ProductOption(name=name, values=uniq_vals))
        return out

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
        # NOTE: Idus 상세 이미지는 "뷰포트에 들어와야" 로딩되는 케이스가 많아서
        #       scrollTo(bottom) 점프 방식은 오히려 누락을 만들 수 있음.
        #       진행형(프로그레시브) 스크롤로 중간 구간도 실제로 통과시킵니다.
        try:
            await self._progressive_scroll_to_bottom(page, max_steps=35, pause_sec=0.45)
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

    async def _auto_scroll_to_bottom(self, page: Page, max_loops: int = 30, pause_sec: float = 0.35) -> None:
        """
        scrollHeight가 더 이상 늘지 않을 때까지 적응형으로 스크롤.
        하단 이미지/상세가 viewport에 들어와야 로딩되는 구조를 최대한 커버.
        """
        stable = 0
        last_h = 0
        for _ in range(max_loops):
            h = await page.evaluate("document.body.scrollHeight")
            if h == last_h:
                stable += 1
            else:
                stable = 0
                last_h = h

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(pause_sec)

            if stable >= 3:
                break

        # 상단으로 살짝 복귀
        try:
            await page.evaluate("window.scrollBy(0, -600);")
        except:
            pass

    async def _progressive_scroll_to_bottom(self, page: Page, max_steps: int = 35, pause_sec: float = 0.45) -> None:
        """
        진행형 스크롤: viewport 단위로 내려가며 lazy-load 트리거를 최대한 살림.
        - 중간 구간을 실제로 통과시키지 않으면 로딩되지 않는 이미지들이 많음
        """
        stable = 0
        last_h = 0
        for _ in range(max_steps):
            metrics = await page.evaluate(
                """() => ({
                  y: window.scrollY,
                  vh: window.innerHeight,
                  h: document.body.scrollHeight
                })"""
            )
            h = int(metrics.get("h", 0) or 0)
            vh = int(metrics.get("vh", 900) or 900)
            y = int(metrics.get("y", 0) or 0)

            if h == last_h:
                stable += 1
            else:
                stable = 0
                last_h = h

            # 거의 끝이면 종료
            if y + vh >= h - 80:
                break

            step = int(vh * 0.9)
            await page.evaluate("(s) => window.scrollBy(0, s)", step)
            await asyncio.sleep(pause_sec)

            # 높이 변화가 없고 충분히 내려왔으면 종료
            if stable >= 5 and y + vh >= h * 0.8:
                break

        # 마지막에 살짝 위로 (sticky UI 영향 완화)
        try:
            await page.evaluate("window.scrollBy(0, -500);")
        except:
            pass

    async def _extract_image_urls_from_html(self, page: Page) -> list[str]:
        """page.content()에서 직접 이미지 URL을 정규식으로 추출 (DOM/네트워크 누락 폴백)."""
        html = await page.content()
        if not html:
            return []
        urls = re.findall(
            r"https?://[^\\\"'\\s>]+\\.(?:jpg|jpeg|png|webp)(?:\\?[^\\\"'\\s>]*)?",
            html,
            flags=re.IGNORECASE,
        )
        # 확장자 없는 CDN URL도 잡기 (idus 이미지 도메인/경로 기반)
        urls += re.findall(
            r"https?://[^\\\"'\\s>]+(?:image|img)[^\\\"'\\s>]+(?:\\?[^\\\"'\\s>]*)?",
            html,
            flags=re.IGNORECASE,
        )
        urls = [
            u for u in urls
            if "icon" not in u.lower()
            and "sprite" not in u.lower()
            and not u.lower().endswith(".svg")
        ]
        return list(dict.fromkeys(urls))
    
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
            # 점프 스크롤은 중간 구간 lazy-load를 놓칠 수 있어 진행형 스크롤을 사용
            await self._progressive_scroll_to_bottom(page, max_steps=45, pause_sec=0.4)
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
            'source',
        ]
        
        for selector in detail_selectors:
            try:
                img_elements = await page.query_selector_all(selector)
                
                for img in img_elements:
                    # src 계열 추출 (lazy-load / srcset 포함)
                    src = await img.get_attribute('src')
                    if not src:
                        src = await img.get_attribute('data-src')
                    if not src:
                        src = await img.get_attribute('data-lazy-src')
                    if not src:
                        src = await img.get_attribute('data-original')
                    if not src:
                        src = await img.get_attribute('data-url')

                    # srcset / data-srcset 처리
                    srcset = await img.get_attribute('srcset')
                    if not srcset:
                        srcset = await img.get_attribute('data-srcset')
                    if srcset:
                        # srcset: "url1 320w, url2 640w" -> 가장 큰 것 선택
                        try:
                            parts = [p.strip() for p in srcset.split(",") if p.strip()]
                            # width 기준 정렬
                            scored = []
                            for p in parts:
                                seg = p.split()
                                u = seg[0]
                                w = 0
                                if len(seg) >= 2 and seg[1].endswith("w"):
                                    try:
                                        w = int(seg[1].replace("w", ""))
                                    except:
                                        w = 0
                                scored.append((w, u))
                            scored.sort(key=lambda x: x[0], reverse=True)
                            if scored:
                                src = scored[0][1]
                        except:
                            pass

                    # background-image(url(...)) 처리
                    if not src:
                        try:
                            style = await img.get_attribute('style') or ""
                            m = re.search(r'url\\([\"\\\']?(.*?)[\"\\\']?\\)', style)
                            if m:
                                src = m.group(1)
                        except:
                            pass
                    
                    if src:
                        # 유효한 이미지 URL인지 확인
                        if src.startswith('http') and not src.endswith('.svg'):
                            # 너무 작은 썸네일/아이콘 URL 패턴 제외 (경험칙)
                            low = src.lower()
                            if any(x in low for x in ["sprite", "icon", "logo"]):
                                continue
                            
                            if src not in images:
                                images.append(src)
                                
            except Exception as e:
                print(f"이미지 추출 중 오류: {e}")
                continue
        
        print(f"📷 {len(images)}개의 상세 이미지 발견")
        # 중복 제거/상위 N개 제한
        images = list(dict.fromkeys(images))
        return images[:60]  # 최대 60개까지만


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
