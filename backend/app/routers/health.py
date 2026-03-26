"""
헬스체크 라우터
서버 상태 확인 및 기본 정보 제공
"""
import logging
from fastapi import APIRouter
from ..models.v1 import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

# 전역 세션 참조 (main.py에서 주입)
_artist_session = None


def configure(artist_session):
    global _artist_session
    _artist_session = artist_session


@router.get("/", summary="API 정보")
async def root():
    """루트 엔드포인트 — API 정보"""
    return {
        "name": "Idus Product Translator API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
    }


@router.get("/api/health", response_model=HealthResponse, summary="서버 상태 확인")
async def health_check():
    """
    서버 상태 확인 엔드포인트
    Railway 헬스체크용 — 항상 즉시 응답
    """
    return HealthResponse(
        status="healthy",
        version="2.0.0",
    )


@router.get("/api/debug/page", summary="현재 브라우저 페이지 디버깅 정보")
async def debug_page_info():
    """
    작가웹 브라우저 세션의 현재 페이지 DOM 구조를 반환합니다.
    디버깅 전용 — 작품 목록 스크래핑 문제 분석에 사용합니다.
    """
    if not _artist_session:
        return {"error": "세션 미초기화"}

    try:
        info = await _artist_session.get_page_debug_info()
        return {"success": True, "data": info}
    except Exception as e:
        logger.error(f"디버그 정보 수집 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/debug/capture", summary="작품 목록 API 응답 캡처")
async def debug_capture():
    """
    product list 페이지로 이동하여 SPA가 호출하는 API 응답을 캡처합니다.
    실제 API 필드명을 확인하는 데 사용합니다.
    """
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화 또는 페이지 없음"}

    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요 — 먼저 /api/v2/session/login으로 로그인하세요"}

    try:
        page = _artist_session.page
        captured = []

        async def on_response(response):
            try:
                url = response.url
                if response.status == 200 and "paging" in url and "idus" in url:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        body = await response.json()
                        captured.append({"url": url, "body": body})
            except Exception:
                pass

        page.on("response", on_response)

        try:
            # product list 페이지로 이동 (SPA가 자동으로 API 호출)
            await page.goto(
                "https://artist.idus.com/product/list",
                timeout=30000,
            )
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(5)  # SPA 렌더링 + API 호출 대기
        finally:
            page.remove_listener("response", on_response)

        if not captured:
            return {
                "success": False,
                "error": "API 응답 캡처 실패 — paging 패턴 응답 없음",
                "current_url": page.url,
            }

        # 첫 번째 캡처된 응답 분석
        first = captured[0]
        body = first["body"]

        # 배열 찾기
        items = _artist_session._find_product_array(body)

        result = {
            "success": True,
            "captured_url": first["url"],
            "response_top_keys": list(body.keys()) if isinstance(body, dict) else str(type(body)),
            "total_captured_responses": len(captured),
        }

        if isinstance(body, dict):
            # 전체 구조 탐색 (값은 타입만)
            structure = {}
            for k, v in body.items():
                if isinstance(v, list):
                    structure[k] = f"list[{len(v)}]"
                elif isinstance(v, dict):
                    structure[k] = f"dict({list(v.keys())[:5]})"
                else:
                    structure[k] = f"{type(v).__name__}: {str(v)[:80]}"
            result["response_structure"] = structure

        if items and len(items) > 0:
            result["items_count"] = len(items)
            # 첫 아이템 전체 키-값 (값은 80자까지)
            first_item = items[0]
            result["first_item_keys"] = list(first_item.keys()) if isinstance(first_item, dict) else None
            if isinstance(first_item, dict):
                result["first_item_detail"] = {
                    k: {"type": type(v).__name__, "value": str(v)[:200]}
                    for k, v in first_item.items()
                }
            # 두 번째 아이템 (비교용)
            if len(items) > 1 and isinstance(items[1], dict):
                result["second_item_sample"] = {
                    k: str(v)[:100] for k, v in items[1].items()
                }
        else:
            result["items"] = None
            result["raw_body_preview"] = str(body)[:2000]

        return result

    except Exception as e:
        logger.error(f"캡처 디버그 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/debug/product-page", summary="작품 상세 페이지 DOM 구조")
async def debug_product_page(product_id: str = ""):
    """
    특정 작품 페이지로 이동하여 DOM 구조(input, button, 이미지)를 반환합니다.
    """
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}
    if not product_id:
        return {"error": "product_id 파라미터 필요 (예: ?product_id=uuid)"}

    try:
        page = _artist_session.page
        url = f"https://artist.idus.com/product/{product_id}"
        await page.goto(url, timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)

        dom_info = await page.evaluate("""
            () => {
                // 모든 input/textarea 필드
                const inputs = Array.from(document.querySelectorAll('input, textarea')).map(el => ({
                    tag: el.tagName,
                    type: el.type || '',
                    name: el.name || '',
                    placeholder: el.placeholder || '',
                    value: (el.value || '').substring(0, 80),
                    label: (() => {
                        const l = el.closest('.v-input, .v-text-field, label, .form-group');
                        return l ? l.textContent.trim().substring(0, 60) : '';
                    })(),
                }));

                // 모든 버튼 텍스트
                const buttons = Array.from(document.querySelectorAll('button, a.v-btn')).map(el => ({
                    text: el.textContent.trim().substring(0, 50),
                    classes: (el.className || '').substring(0, 80),
                })).filter(b => b.text);

                // 모든 이미지
                const images = Array.from(document.querySelectorAll('img')).slice(0, 30).map(img => ({
                    src: (img.src || '').substring(0, 150),
                    width: img.width,
                    height: img.height,
                    alt: img.alt || '',
                }));

                // v-tab 요소
                const tabs = Array.from(document.querySelectorAll('[role="tab"], .v-tab')).map(t => ({
                    text: t.textContent.trim(),
                    active: t.classList.contains('v-tab--active') || t.getAttribute('aria-selected') === 'true',
                }));

                // 배경 이미지 URL 수집
                const bgImages = [];
                const allEls = document.querySelectorAll('*');
                for (const el of allEls) {
                    const style = window.getComputedStyle(el);
                    const bg = style.backgroundImage;
                    if (bg && bg !== 'none' && bg.includes('url(')) {
                        const match = bg.match(/url\(['"]?(https?:\/\/[^'")\s]+)/);
                        if (match) {
                            bgImages.push({
                                url: match[1].substring(0, 200),
                                size: `${el.offsetWidth}x${el.offsetHeight}`,
                                tag: el.tagName,
                                classes: (el.className || '').toString().substring(0, 80),
                            });
                        }
                    }
                }

                // Vue 인스턴스 데이터 탐색
                let vueData = null;
                const appEl = document.querySelector('#app') || document.querySelector('[id*="app"]') || document.querySelector('.v-application');
                if (appEl) {
                    // Vue 2
                    let el = appEl;
                    for (let i = 0; i < 15; i++) {
                        if (el.__vue__) {
                            const d = el.__vue__.$data || el.__vue__;
                            vueData = {};
                            for (const [k, v] of Object.entries(d)) {
                                if (typeof v === 'function') continue;
                                try {
                                    vueData[k] = JSON.stringify(v)?.substring(0, 300);
                                } catch(e) {
                                    vueData[k] = String(v).substring(0, 100);
                                }
                            }
                            break;
                        }
                        if (el.firstElementChild) el = el.firstElementChild;
                        else break;
                    }
                }

                // product_option hidden input의 원본 JS 값 접근 시도
                let optionRaw = null;
                const optInput = document.querySelector('input[name="product_option"]');
                if (optInput) {
                    // Vue binding에서 실제 값 접근
                    let parent = optInput;
                    for (let i = 0; i < 10; i++) {
                        parent = parent.parentElement;
                        if (!parent) break;
                        if (parent.__vue__) {
                            const vm = parent.__vue__;
                            const data = vm.$data || vm;
                            // 옵션 관련 키 탐색
                            for (const key of Object.keys(data)) {
                                if (key.toLowerCase().includes('option')) {
                                    try {
                                        optionRaw = { key, value: JSON.stringify(data[key])?.substring(0, 500) };
                                    } catch(e) {
                                        optionRaw = { key, value: String(data[key]).substring(0, 200) };
                                    }
                                    break;
                                }
                            }
                            if (optionRaw) break;
                        }
                    }
                }

                return {
                    url: window.location.href,
                    title: document.title,
                    inputCount: inputs.length,
                    inputs: inputs,
                    buttonCount: buttons.length,
                    buttons: buttons,
                    imageCount: images.length,
                    images: images,
                    bgImageCount: bgImages.length,
                    bgImages: bgImages.slice(0, 20),
                    tabs: tabs,
                    vueDataKeys: vueData ? Object.keys(vueData) : null,
                    vueDataSample: vueData,
                    optionRawFromVue: optionRaw,
                };
            }
        """)

        return {"success": True, "data": dom_info}

    except Exception as e:
        logger.error(f"작품 페이지 디버그 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/debug/deep-extract", summary="Vue 컴포넌트 깊이 탐색")
async def debug_deep_extract(product_id: str = ""):
    """제품 이미지와 옵션 데이터를 Vue 컴포넌트 트리에서 깊이 탐색합니다."""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}
    if not product_id:
        return {"error": "product_id 필요"}

    try:
        page = _artist_session.page

        # 이미 해당 작품 페이지에 있는지 확인, 아니면 이동
        if product_id not in page.url:
            await page.goto(
                f"https://artist.idus.com/product/{product_id}",
                timeout=30000,
            )
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

        result = await page.evaluate("""
            () => {
                const output = {};

                // 1. 모든 Vue 컴포넌트 순회하며 이미지/옵션 데이터 탐색
                const vueComponents = [];
                function findVueInstances(el, depth) {
                    if (depth > 20 || !el) return;
                    if (el.__vue__) {
                        const vm = el.__vue__;
                        const data = vm.$data || {};
                        const props = vm.$props || {};
                        const keys = [...Object.keys(data), ...Object.keys(props)];
                        vueComponents.push({
                            depth,
                            tag: el.tagName,
                            dataKeys: keys.slice(0, 30),
                        });

                        // 이미지 관련 데이터 탐색
                        for (const key of keys) {
                            const val = data[key] || props[key];
                            if (!val) continue;
                            const lk = key.toLowerCase();
                            if (lk.includes('image') || lk.includes('photo') || lk.includes('img')) {
                                try {
                                    output['vue_image_' + key] = JSON.stringify(val).substring(0, 500);
                                } catch(e) {
                                    output['vue_image_' + key] = String(val).substring(0, 200);
                                }
                            }
                            if (lk.includes('option')) {
                                try {
                                    output['vue_option_' + key] = JSON.stringify(val).substring(0, 1000);
                                } catch(e) {
                                    output['vue_option_' + key] = String(val).substring(0, 300);
                                }
                            }
                            if (lk.includes('description') || lk.includes('premium')) {
                                try {
                                    output['vue_desc_' + key] = JSON.stringify(val).substring(0, 1000);
                                } catch(e) {
                                    output['vue_desc_' + key] = String(val).substring(0, 300);
                                }
                            }
                        }
                    }
                    for (const child of (el.children || [])) {
                        findVueInstances(child, depth + 1);
                    }
                }
                findVueInstances(document.body, 0);
                output.vueComponentCount = vueComponents.length;
                output.vueComponentSample = vueComponents.slice(0, 10);

                // 2. v-img 요소 탐색
                const vImgs = document.querySelectorAll('.v-image, .v-img, [class*="v-image"]');
                output.vImgCount = vImgs.length;
                output.vImgs = Array.from(vImgs).slice(0, 15).map(el => {
                    const bgDiv = el.querySelector('.v-image__image');
                    let bgUrl = '';
                    if (bgDiv) {
                        const style = bgDiv.getAttribute('style') || '';
                        const match = style.match(/url\\(['"]?(https?:\\/\\/[^'"\\)]+)/);
                        if (match) bgUrl = match[1];
                    }
                    return {
                        classes: (el.className || '').substring(0, 80),
                        size: el.offsetWidth + 'x' + el.offsetHeight,
                        bgUrl: bgUrl.substring(0, 200),
                        lazySrc: el.getAttribute('lazy-src') || '',
                        src: el.getAttribute('src') || '',
                    };
                });

                // 3. data-src, data-image 속성 탐색
                const dataSrcEls = document.querySelectorAll('[data-src], [data-image], [data-original]');
                output.dataSrcCount = dataSrcEls.length;
                output.dataSrcs = Array.from(dataSrcEls).slice(0, 10).map(el => ({
                    tag: el.tagName,
                    dataSrc: (el.getAttribute('data-src') || '').substring(0, 150),
                    dataImage: (el.getAttribute('data-image') || '').substring(0, 150),
                }));

                // 4. Vuex/Pinia 스토어 탐색
                const app = document.querySelector('#app');
                if (app && app.__vue__) {
                    const vm = app.__vue__;
                    if (vm.$store) {
                        const state = vm.$store.state;
                        output.vuexKeys = Object.keys(state).slice(0, 20);
                        for (const key of Object.keys(state)) {
                            const lk = key.toLowerCase();
                            if (lk.includes('product') || lk.includes('image') || lk.includes('option')) {
                                try {
                                    output['vuex_' + key] = JSON.stringify(state[key]).substring(0, 1000);
                                } catch(e) {
                                    output['vuex_' + key] = String(state[key]).substring(0, 300);
                                }
                            }
                        }
                    }
                }

                return output;
            }
        """)

        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"Deep extract 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/debug/vuex-product", summary="Vuex 스토어 제품 데이터")
async def debug_vuex_product():
    """현재 페이지의 Vuex 스토어에서 제품 데이터를 읽습니다. 네비게이션 없음."""

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}

    try:
        page = _artist_session.page

        result = await page.evaluate("""
            () => {
                const output = { currentUrl: window.location.href };
                const app = document.querySelector('#app');
                if (!app || !app.__vue__ || !app.__vue__.$store) {
                    return { ...output, error: 'Vuex store not found' };
                }
                const store = app.__vue__.$store;
                const state = store.state;

                output.vuexModules = Object.keys(state);

                // 모든 제품 관련 Vuex 모듈 덤프
                const moduleNames = ['productForm', 'product', 'globalProduct', 'productPreview'];
                for (const mod of moduleNames) {
                    if (!state[mod]) continue;
                    const modData = state[mod];
                    output[mod + '_keys'] = Object.keys(modData);

                    // 각 키의 값을 최대한 추출
                    for (const key of Object.keys(modData)) {
                        const val = modData[key];
                        if (val === null || val === undefined) continue;
                        const fullKey = mod + '.' + key;
                        try {
                            const json = JSON.stringify(val);
                            // 2000자까지만 (너무 큰 데이터 방지)
                            output[fullKey] = json.length > 2000
                                ? json.substring(0, 2000) + '...(truncated)'
                                : json;
                        } catch(e) {
                            output[fullKey] = String(val).substring(0, 500);
                        }
                    }
                }

                return output;
            }
        """)

        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"Vuex 디버그 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/debug/global-editor", summary="글로벌 탭 DOM 전체 덤프")
async def debug_global_editor(product_id: str = ""):
    """글로벌 페이지(/global)로 직접 이동 → 모든 버튼/탭/input 덤프"""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    try:
        page = _artist_session.page

        # 1. /global URL로 직접 이동
        if product_id:
            url = f"https://artist.idus.com/product/{product_id}/global"
        else:
            # 현재 URL에서 product_id 추출
            current = page.url
            import re
            m = re.search(r'/product/([a-f0-9-]{36})', current)
            if m:
                url = f"https://artist.idus.com/product/{m.group(1)}/global"
            else:
                return {"error": "product_id를 찾을 수 없습니다"}

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            logger.warning(f"글로벌 페이지 이동 오류 (계속): {e}")
        await asyncio.sleep(3)

        # 2. 전체 DOM 덤프: 버튼, 탭, input, textarea
        dom_info = await page.evaluate("""
            () => {
                const result = { url: window.location.href };

                // 모든 버튼
                result.buttons = Array.from(document.querySelectorAll('button')).map(b => ({
                    text: b.textContent?.trim().substring(0, 80),
                    tag: b.tagName,
                    classes: (b.className || '').substring(0, 100),
                    disabled: b.disabled,
                    visible: b.offsetHeight > 0,
                })).filter(b => b.visible && b.text);

                // 모든 탭 (role="tab" 또는 탭 관련 클래스)
                result.tabs = Array.from(document.querySelectorAll('[role="tab"], [class*="tab"], [class*="Tab"]')).map(t => ({
                    text: t.textContent?.trim().substring(0, 80),
                    tag: t.tagName,
                    classes: (t.className || '').substring(0, 100),
                    active: t.getAttribute('aria-selected') === 'true' || t.classList.contains('v-tab--active'),
                })).filter(t => t.text);

                // 모든 input/textarea
                result.inputs = Array.from(document.querySelectorAll('input, textarea')).map(i => ({
                    tag: i.tagName,
                    type: i.type || 'textarea',
                    name: i.name,
                    placeholder: i.placeholder?.substring(0, 80),
                    value: i.value?.substring(0, 80),
                    visible: i.offsetHeight > 0,
                })).filter(i => i.visible || i.name);

                // 링크 (a 태그 중 탭 관련)
                result.links = Array.from(document.querySelectorAll('a')).map(a => ({
                    text: a.textContent?.trim().substring(0, 80),
                    href: a.href?.substring(0, 100),
                    classes: (a.className || '').substring(0, 100),
                })).filter(a => a.text && (a.text.includes('일본어') || a.text.includes('영어') || a.text.includes('글로벌') || a.text.includes('저장') || a.text.includes('판매')));

                return result;
            }
        """)

        return {"success": True, "data": dom_info}

    except Exception as e:
        logger.error(f"글로벌 에디터 디버그 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/debug/option-modal", summary="옵션 모달 DOM 디버그")
async def debug_option_modal():
    """옵션 항목 클릭 → 모달 열기 → 모달 내 input 구조 확인"""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}

    try:
        page = _artist_session.page
        result = {"currentUrl": page.url}

        # 1단계: 옵션 섹션에서 클릭 가능한 요소 찾기
        option_elements = await page.evaluate("""
            () => {
                const results = [];
                // 모든 텍스트에서 "디자인" 찾기
                const allEls = document.querySelectorAll('*');
                for (const el of allEls) {
                    if (el.children.length > 3) continue;  // 리프 노드에 가까운 것만
                    const text = el.textContent?.trim();
                    if (text === '디자인' || text === '= 디자인') {
                        results.push({
                            tag: el.tagName,
                            text: text,
                            classes: (el.className || '').toString().substring(0, 100),
                            clickable: el.tagName === 'BUTTON' || el.tagName === 'A' || el.style?.cursor === 'pointer' || el.onclick !== null,
                            parentTag: el.parentElement?.tagName,
                            parentClasses: (el.parentElement?.className || '').toString().substring(0, 100),
                        });
                    }
                }
                return results;
            }
        """)
        result["optionElements"] = option_elements

        # 2단계: "디자인" 텍스트 클릭 시도
        clicked = False
        try:
            el = page.locator('text="디자인"').first
            if await el.count() > 0:
                await el.click()
                await asyncio.sleep(1.5)
                clicked = True
        except Exception as e:
            result["clickError"] = str(e)

        result["clicked"] = clicked

        # 3단계: 모달/다이얼로그 확인
        if clicked:
            modal_info = await page.evaluate("""
                () => {
                    // 활성 다이얼로그 찾기
                    const dialogs = document.querySelectorAll(
                        '.v-dialog, .v-dialog--active, [role="dialog"], .v-overlay--active .v-card'
                    );
                    const activeDialogs = Array.from(dialogs).filter(d =>
                        d.offsetParent !== null || d.style.display !== 'none'
                    );

                    if (activeDialogs.length === 0) {
                        return { found: false, dialogCount: dialogs.length };
                    }

                    const modal = activeDialogs[activeDialogs.length - 1];
                    const inputs = Array.from(modal.querySelectorAll('input')).map(inp => ({
                        type: inp.type,
                        name: inp.name || '',
                        value: inp.value || '',
                        placeholder: inp.placeholder || '',
                        label: (() => {
                            const c = inp.closest('.v-input, .v-text-field, [class*="field"]');
                            const l = c?.querySelector('label, .v-label');
                            return l?.textContent?.trim() || '';
                        })(),
                    }));

                    return {
                        found: true,
                        dialogCount: activeDialogs.length,
                        modalTag: modal.tagName,
                        modalClasses: (modal.className || '').substring(0, 100),
                        modalText: modal.textContent.substring(0, 300),
                        inputCount: inputs.length,
                        inputs: inputs,
                    };
                }
            """)
            result["modal"] = modal_info

            # 모달 닫기
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except Exception:
                pass

        return {"success": True, "data": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/debug/global-elements", summary="글로벌 페이지 이미지/키워드/옵션 요소 탐색")
async def debug_global_elements():
    """글로벌 페이지에서 이미지 추가 버튼, 키워드 섹션, 옵션 편집 버튼의 DOM을 덤프"""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    try:
        page = _artist_session.page

        # 글로벌 페이지인지 확인, 아니면 이동
        if "/global" not in page.url:
            import re
            m = re.search(r'/product/([a-f0-9-]{36})', page.url)
            if m:
                url = f"https://artist.idus.com/product/{m.group(1)}/global"
                try:
                    await page.goto(url, timeout=30000)
                    await page.wait_for_load_state("domcontentloaded")
                except Exception:
                    pass
                await asyncio.sleep(5)

        # 충분히 대기 — 메인 컨텐츠 영역 스크롤
        try:
            await page.wait_for_selector('textarea[name="globalProductName"]', timeout=10000)
        except Exception:
            pass

        # Vuetify의 메인 스크롤 컨테이너 찾아서 스크롤
        await page.evaluate("""
            () => {
                // 메인 컨텐츠 스크롤 (body가 아닌 내부 컨테이너)
                const main = document.querySelector('.v-main__wrap, .v-main, main, [class*="content"]');
                if (main) {
                    main.scrollTop = main.scrollHeight;
                }
                window.scrollTo(0, document.body.scrollHeight);
            }
        """)
        await asyncio.sleep(3)
        await page.evaluate("""
            () => {
                const main = document.querySelector('.v-main__wrap, .v-main, main');
                if (main) main.scrollTop = 0;
                window.scrollTo(0, 0);
            }
        """)
        await asyncio.sleep(1)

        result = await page.evaluate("""
            () => {
                const output = { url: window.location.href };

                // 1. 이미지 영역: '+' 요소 탐색
                output.imageSection = [];
                // 이미지 관련 텍스트 "작품 이미지" 근처 요소
                const allEls = document.querySelectorAll('*');
                for (const el of allEls) {
                    const text = el.textContent?.trim();
                    // '+' 만 가진 요소 (작은 요소)
                    if (text === '+' && el.children.length <= 2 && el.offsetHeight > 0) {
                        output.imageSection.push({
                            found: '+',
                            tag: el.tagName,
                            classes: (el.className || '').substring(0, 120),
                            parent: el.parentElement?.tagName + '.' + (el.parentElement?.className || '').substring(0, 80),
                            size: el.offsetWidth + 'x' + el.offsetHeight,
                            clickable: el.tagName === 'BUTTON' || el.tagName === 'A' || el.tagName === 'LABEL' || el.getAttribute('role') === 'button',
                        });
                    }
                }

                // 2. 키워드 섹션
                output.keywordSection = [];
                const kwEls = document.querySelectorAll('[class*="contentItem"], [class*="ContentItem"]');
                for (const el of kwEls) {
                    output.keywordSection.push({
                        tag: el.tagName,
                        classes: (el.className || '').substring(0, 120),
                        text: el.textContent?.trim().substring(0, 60),
                        visible: el.offsetHeight > 0,
                    });
                }
                // 키워드 텍스트를 직접 찾기
                const kwTextEls = document.querySelectorAll('*');
                for (const el of kwTextEls) {
                    if (el.textContent?.trim() === '작품 키워드' && el.children.length === 0) {
                        output.keywordSection.push({
                            exactMatch: true,
                            tag: el.tagName,
                            classes: (el.className || '').substring(0, 120),
                            parent: el.parentElement?.tagName + '.' + (el.parentElement?.className || '').substring(0, 80),
                        });
                    }
                }

                // 3. 옵션 편집
                output.optionSection = [];
                const optBtns = document.querySelectorAll('button, a, [role="button"]');
                for (const el of optBtns) {
                    const text = el.textContent?.trim();
                    if (text && (text.includes('옵션') || text.includes('키워드'))) {
                        output.optionSection.push({
                            tag: el.tagName,
                            text: text.substring(0, 60),
                            classes: (el.className || '').substring(0, 120),
                            visible: el.offsetHeight > 0,
                        });
                    }
                }

                // 4. 페이지 내 모든 가시적 텍스트 (섹션 헤딩)
                output.visibleHeadings = [];
                const headings = document.querySelectorAll('h1, h2, h3, h4, .subtitle-1, .subtitle-2, .body-1, .body-2, [class*="title"], [class*="Title"]');
                for (const el of headings) {
                    if (el.offsetHeight > 0 && el.textContent?.trim().length < 60) {
                        output.visibleHeadings.push({
                            tag: el.tagName,
                            text: el.textContent?.trim(),
                            classes: (el.className || '').substring(0, 80),
                        });
                    }
                }

                // 5. 페이지 전체 innerText (첫 3000자)
                output.fullPageText = document.body.innerText?.substring(0, 3000) || '';

                // 6. 메인 컨텐츠 영역 HTML 구조 (클래스만)
                const mainContent = document.querySelector('.v-main__wrap, .v-main, main');
                if (mainContent) {
                    output.mainContentChildren = Array.from(mainContent.querySelectorAll('*'))
                        .filter(el => el.offsetHeight > 0)
                        .slice(0, 50)
                        .map(el => ({
                            tag: el.tagName,
                            classes: (el.className || '').substring(0, 80),
                            text: el.textContent?.trim().substring(0, 40),
                            depth: 0, // simplified
                        }));
                }

                // 7. 페이지 전체 텍스트에서 "이미지" "키워드" 포함 부분 추출
                output.textWithImage = [];
                output.textWithKeyword = [];
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                while (walker.nextNode()) {
                    const text = walker.currentNode.textContent.trim();
                    if (!text) continue;
                    const parent = walker.currentNode.parentElement;
                    if (!parent || parent.offsetHeight === 0) continue;
                    if (text.includes('이미지') && text.length < 100) {
                        output.textWithImage.push({
                            text: text,
                            parentTag: parent.tagName,
                            parentClasses: (parent.className || '').substring(0, 100),
                            grandparentClasses: (parent.parentElement?.className || '').substring(0, 100),
                        });
                    }
                    if (text.includes('키워드') && text.length < 100) {
                        output.textWithKeyword.push({
                            text: text,
                            parentTag: parent.tagName,
                            parentClasses: (parent.className || '').substring(0, 100),
                            grandparentClasses: (parent.parentElement?.className || '').substring(0, 100),
                        });
                    }
                }

                return output;
            }
        """)

        return {"success": True, "data": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/debug/test-option-reader", summary="ProductReader 옵션 코드 직접 테스트")
async def debug_test_option_reader():
    """ProductReader._read_options_from_modal()과 동일한 코드를 실행하여 결과 확인"""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    page = _artist_session.page
    result = {"currentUrl": page.url, "steps": []}

    try:
        # 1단계: JS evaluate로 옵션 버튼 텍스트 목록 추출
        option_names = await page.evaluate("""
            () => {
                const names = [];
                const selectors = [
                    '[class*="ProductFormOptionSection"] button',
                    '[class*="optionItem"] button',
                    '[class*="OptionItem"] button',
                ];
                for (const sel of selectors) {
                    const btns = document.querySelectorAll(sel);
                    for (const btn of btns) {
                        const text = btn.textContent?.trim();
                        if (text && text.length > 0 && text.length < 30
                            && !names.includes(text)) {
                            names.push(text);
                        }
                    }
                    if (names.length > 0) break;
                }
                return names;
            }
        """)
        result["steps"].append({"step": "find_names", "option_names": option_names})

        if not option_names:
            result["steps"].append({"step": "no_options", "message": "옵션 없음"})
            return {"success": True, "data": result}

        # 2단계: 각 옵션 클릭 + 모달 읽기
        for opt_name in option_names:
            step_data = {"option_name": opt_name}

            el = page.locator(f'text="{opt_name}"').first
            el_count = await el.count()
            step_data["locator_count"] = el_count

            if el_count == 0:
                step_data["error"] = "locator not found"
                result["steps"].append(step_data)
                continue

            await el.click()
            await asyncio.sleep(1.5)
            step_data["clicked"] = True

            # 모달 읽기
            modal_data = await page.evaluate("""
                () => {
                    const modal = document.querySelector('.v-dialog--active');
                    if (!modal) return { error: 'no_modal' };

                    const nameInput = modal.querySelector('input[name="productOptionName"]');
                    const optionName = nameInput ? nameInput.value.trim() : '';

                    const valueInputs = Array.from(
                        modal.querySelectorAll('input[name="productOptionValue"]')
                    );
                    const priceInputs = Array.from(
                        modal.querySelectorAll('input[name="optionPrice"]')
                    );

                    const values = [];
                    for (let i = 0; i < valueInputs.length; i++) {
                        const val = valueInputs[i].value.trim();
                        if (!val) continue;
                        const price = priceInputs[i]
                            ? parseInt(priceInputs[i].value.replace(/[^0-9]/g, ''), 10) || 0
                            : 0;
                        values.push({ value: val, additional_price: price });
                    }

                    return { name: optionName, values: values };
                }
            """)
            step_data["modal_data"] = modal_data

            # 모달 닫기
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

            result["steps"].append(step_data)

        return {"success": True, "data": result}

    except Exception as e:
        result["error"] = str(e)
        return {"success": False, "data": result}


@router.get("/api/debug/vuex-actions", summary="Vuex mutations/actions 목록")
async def debug_vuex_actions():
    """globalProduct 모듈의 mutations와 actions 목록을 덤프합니다."""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    try:
        page = _artist_session.page

        # 글로벌 페이지로 이동
        if "/global" not in page.url:
            import re
            m = re.search(r'/product/([a-f0-9-]{36})', page.url)
            if m:
                try:
                    await page.goto(f"https://artist.idus.com/product/{m.group(1)}/global", timeout=30000)
                    await page.wait_for_load_state("domcontentloaded")
                except Exception:
                    pass
                await asyncio.sleep(5)

        result = await page.evaluate("""
            () => {
                const app = document.querySelector('#app');
                if (!app || !app.__vue__ || !app.__vue__.$store) return { error: 'no store' };
                const store = app.__vue__.$store;

                // 전체 mutations 키
                const allMutations = Object.keys(store._mutations || {});
                // 전체 actions 키
                const allActions = Object.keys(store._actions || {});

                // globalProduct 관련만 필터
                const gpMutations = allMutations.filter(k => k.toLowerCase().includes('global') || k.toLowerCase().includes('product'));
                const gpActions = allActions.filter(k => k.toLowerCase().includes('global') || k.toLowerCase().includes('product'));

                // 전체 목록도 (save/update/create 관련)
                const saveMutations = allMutations.filter(k =>
                    k.toLowerCase().includes('save') ||
                    k.toLowerCase().includes('update') ||
                    k.toLowerCase().includes('create') ||
                    k.toLowerCase().includes('set') ||
                    k.toLowerCase().includes('draft')
                );
                const saveActions = allActions.filter(k =>
                    k.toLowerCase().includes('save') ||
                    k.toLowerCase().includes('update') ||
                    k.toLowerCase().includes('create') ||
                    k.toLowerCase().includes('draft') ||
                    k.toLowerCase().includes('publish')
                );

                return {
                    totalMutations: allMutations.length,
                    totalActions: allActions.length,
                    gpMutations: gpMutations,
                    gpActions: gpActions,
                    saveMutations: saveMutations,
                    saveActions: saveActions,
                    // 전체 목록 (첫 100개)
                    allMutations: allMutations.slice(0, 100),
                    allActions: allActions.slice(0, 100),
                };
            }
        """)

        return {"success": True, "data": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/debug/full-register-test", summary="글로벌 등록 전체 시뮬레이션 + API 캡처")
async def debug_full_register_test():
    """Playwright로 UI 조작하여 실제 저장하고, 모든 네트워크 요청을 캡처합니다."""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    page = _artist_session.page
    captured = []
    steps = []

    try:
        # 네트워크 요청 캡처 시작
        async def on_req(request):
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                url = request.url
                if "kinesis" not in url:  # AWS 로깅 제외
                    try:
                        captured.append({
                            "url": url,
                            "method": request.method,
                            "body": (request.post_data or "")[:3000],
                        })
                    except Exception:
                        captured.append({"url": url, "method": request.method})

        async def on_resp(response):
            url = response.url
            if response.request.method in ("POST", "PUT", "PATCH") and "kinesis" not in url:
                try:
                    status = response.status
                    for c in captured:
                        if c["url"] == url and "status" not in c:
                            c["status"] = status
                            try:
                                body = await response.text()
                                c["response"] = body[:1000]
                            except Exception:
                                pass
                            break
                except Exception:
                    pass

        page.on("request", on_req)
        page.on("response", on_resp)

        try:
            # STEP 1: 글로벌 페이지로 이동
            import re
            m = re.search(r'/product/([a-f0-9-]{36})', page.url)
            pid = m.group(1) if m else ""
            if not pid:
                return {"error": "product_id 없음"}

            if "/global" not in page.url:
                await page.goto(f"https://artist.idus.com/product/{pid}/global", timeout=30000)
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(5)
            steps.append({"step": "글로벌 이동", "url": page.url})

            # STEP 2: 작품명 입력
            textarea = page.locator('textarea[name="globalProductName"]').first
            if await textarea.count() > 0:
                await textarea.fill("テスト作品名")
                steps.append({"step": "작품명 입력", "ok": True})
            else:
                steps.append({"step": "작품명 입력", "ok": False, "error": "textarea 없음"})

            # STEP 3: 이미지 '+' 클릭 시도 — 페이지의 모든 요소에서 '+' 찾기
            plus_result = await page.evaluate("""
                () => {
                    // 방법 1: 텍스트가 '+' 인 요소
                    const allEls = document.querySelectorAll('*');
                    for (const el of allEls) {
                        if (el.children.length > 3) continue;
                        const text = el.textContent?.trim();
                        if (text === '+' && el.offsetHeight > 20 && el.offsetWidth > 20) {
                            el.click();
                            return { clicked: true, method: 'text+', tag: el.tagName, classes: (el.className||'').substring(0,80) };
                        }
                    }
                    // 방법 2: SVG나 icon 클래스
                    const addBtns = document.querySelectorAll('[class*="add"], [class*="Add"], [class*="plus"], [class*="Plus"]');
                    for (const el of addBtns) {
                        if (el.offsetHeight > 20 && el.closest('[class*="image"], [class*="Image"]')) {
                            el.click();
                            return { clicked: true, method: 'class', tag: el.tagName, classes: (el.className||'').substring(0,80) };
                        }
                    }
                    // 방법 3: 이미지 업로드 영역 자체 (빈 사각형)
                    const uploadAreas = document.querySelectorAll('[class*="upload"], [class*="Upload"], [class*="dropzone"]');
                    for (const el of uploadAreas) {
                        if (el.offsetHeight > 40) {
                            el.click();
                            return { clicked: true, method: 'upload-area', tag: el.tagName, classes: (el.className||'').substring(0,80) };
                        }
                    }
                    return { clicked: false };
                }
            """)
            steps.append({"step": "이미지 + 클릭", "result": plus_result})

            if plus_result.get("clicked"):
                await asyncio.sleep(1.5)

                # "국내 작품 이미지 불러오기" 클릭
                import_btn = page.locator('text="국내 작품 이미지 불러오기"').first
                if await import_btn.count() > 0:
                    await import_btn.click()
                    await asyncio.sleep(2)
                    steps.append({"step": "국내 이미지 불러오기 클릭", "ok": True})

                    # "전체" 체크박스
                    select_all = page.locator('.v-dialog--active label:has-text("전체")').first
                    if await select_all.count() > 0:
                        await select_all.click()
                        await asyncio.sleep(1)
                        steps.append({"step": "전체 선택", "ok": True})

                        # "이미지 추가" 버튼
                        add_btn = page.locator('.v-dialog--active button:has-text("이미지 추가")').first
                        if await add_btn.count() > 0:
                            await add_btn.click()
                            await asyncio.sleep(2)
                            steps.append({"step": "이미지 추가", "ok": True})
                        else:
                            steps.append({"step": "이미지 추가", "ok": False, "error": "버튼 없음"})
                    else:
                        steps.append({"step": "전체 선택", "ok": False})
                        await page.keyboard.press("Escape")
                else:
                    steps.append({"step": "국내 이미지 불러오기 클릭", "ok": False})
                    await page.keyboard.press("Escape")

            # STEP 4: 설명 — "작품 설명 작성하기" 클릭 후 에디터에서 입력
            desc_btn = page.locator('button:has-text("작품 설명 작성하기")').first
            if await desc_btn.count() > 0:
                await desc_btn.click()
                await asyncio.sleep(2)
                steps.append({"step": "설명 에디터 열기", "ok": True})

                # 에디터 모달에서 "본문" 버튼 클릭 후 텍스트 입력
                # (에디터 DOM을 덤프하여 구조 확인)
                editor_dump = await page.evaluate("""
                    () => {
                        const dialog = document.querySelector('.v-dialog--active');
                        if (!dialog) return { found: false };
                        // 모든 버튼
                        const btns = Array.from(dialog.querySelectorAll('button')).map(b => ({
                            text: b.textContent?.trim().substring(0, 40),
                            classes: (b.className||'').substring(0, 80),
                            visible: b.offsetHeight > 0,
                        })).filter(b => b.visible);
                        // 모든 input/textarea/contenteditable
                        const inputs = Array.from(dialog.querySelectorAll('input, textarea, [contenteditable="true"]')).map(i => ({
                            tag: i.tagName,
                            type: i.type,
                            placeholder: i.placeholder?.substring(0, 40),
                            classes: (i.className||'').substring(0, 80),
                        }));
                        return { found: true, buttons: btns, inputs: inputs, text: dialog.innerText?.substring(0, 500) };
                    }
                """)
                steps.append({"step": "에디터 DOM 덤프", "data": editor_dump})

                # 에디터 닫기
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            else:
                steps.append({"step": "설명 에디터 열기", "ok": False, "error": "버튼 없음"})

            # STEP 5: "임시저장" 클릭
            save_btn = page.locator('button:has-text("임시저장")').first
            if await save_btn.count() > 0:
                await save_btn.click()
                await asyncio.sleep(3)
                steps.append({"step": "임시저장 클릭", "ok": True})
            else:
                steps.append({"step": "임시저장 클릭", "ok": False})

            # 스낵바 확인
            snack = page.locator('.v-snack__content').first
            try:
                if await asyncio.wait_for(snack.count(), timeout=2) > 0:
                    msg = await snack.inner_text()
                    steps.append({"step": "스낵바", "message": msg})
            except asyncio.TimeoutError:
                pass

        finally:
            page.remove_listener("request", on_req)
            page.remove_listener("response", on_resp)

        return {
            "success": True,
            "steps": steps,
            "captured_requests": captured,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "steps": steps, "captured_requests": captured}


@router.get("/api/debug/intercept-save", summary="임시저장 API 인터셉트")
async def debug_intercept_save():
    """글로벌 페이지에서 임시저장 클릭 시 호출되는 API를 캡처합니다."""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    page = _artist_session.page
    captured_requests = []

    try:
        # 글로벌 페이지로 이동
        if "/global" not in page.url:
            import re
            m = re.search(r'/product/([a-f0-9-]{36})', page.url)
            if m:
                gurl = f"https://artist.idus.com/product/{m.group(1)}/global"
                try:
                    await page.goto(gurl, timeout=30000)
                    await page.wait_for_load_state("domcontentloaded")
                except Exception:
                    pass
                await asyncio.sleep(5)
            else:
                return {"error": f"product_id를 찾을 수 없습니다: {page.url}"}

        # 모든 POST/PUT/PATCH 요청 캡처
        async def on_request(request):
            if request.method in ("POST", "PUT", "PATCH") and "idus" in request.url:
                try:
                    body = request.post_data
                    captured_requests.append({
                        "url": request.url,
                        "method": request.method,
                        "headers": dict(request.headers),
                        "body_preview": body[:2000] if body else None,
                        "body_length": len(body) if body else 0,
                    })
                except Exception:
                    captured_requests.append({
                        "url": request.url,
                        "method": request.method,
                    })

        page.on("request", on_request)

        try:
            # 작품명을 임시로 입력 (필수 필드)
            textarea = page.locator('textarea[name="globalProductName"]').first
            if await textarea.count() > 0:
                current = await textarea.input_value()
                if not current:
                    await textarea.fill("테스트 작품명")
                    await asyncio.sleep(0.5)

            # "임시저장" 버튼 클릭
            save_btn = page.locator('button:has-text("임시저장")').first
            if await save_btn.count() > 0:
                await save_btn.click()
                await asyncio.sleep(3)  # API 호출 대기
            else:
                return {"error": "임시저장 버튼 없음"}

        finally:
            page.remove_listener("request", on_request)

        return {
            "success": True,
            "captured_count": len(captured_requests),
            "requests": captured_requests,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/debug/api-test", summary="3가지 API 호출 방안 동시 테스트")
async def debug_api_test():
    """CORS 해결을 위해 3가지 방안을 한 번에 테스트합니다."""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    page = _artist_session.page

    try:
        import re
        m = re.search(r'/product/([a-f0-9-]{36})', page.url)
        pid = m.group(1) if m else ""
        if not pid:
            return {"error": "product_id 없음"}

        if "/global" not in page.url:
            try:
                await page.goto(f"https://artist.idus.com/product/{pid}/global", timeout=30000)
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            await asyncio.sleep(5)

        result = await page.evaluate("""
            async (uuid) => {
                const output = {};
                const app = document.querySelector('#app');
                if (!app || !app.__vue__) return { error: 'Vue app not found' };
                const vm = app.__vue__;
                const store = vm.$store;

                // ═══ 방안 1: $axios 인스턴스 탐색 ═══
                const ax = {};
                ax.vm_axios = !!vm.$axios;
                ax.root_axios = !!vm.$root?.$axios;
                ax.nuxt_axios = !!window.$nuxt?.$axios;
                ax.window_axios = !!window.axios;
                const axiosInst = vm.$axios || vm.$root?.$axios || window.$nuxt?.$axios || window.axios;
                if (axiosInst) {
                    ax.found = true;
                    try {
                        const r = await axiosInst.get('/api/v1/commission');
                        ax.testOk = true;
                        ax.testStatus = r.status;
                    } catch (e) { ax.testOk = false; ax.testErr = e.message?.substring(0, 100); }
                } else { ax.found = false; }
                output.axios = ax;

                // ═══ 방안 2: 같은 도메인 fetch ═══
                const sf = {};
                try {
                    const r = await fetch('/api/v1/commission', { credentials: 'include' });
                    sf.status = r.status;
                    sf.ok = r.ok;
                } catch (e) { sf.error = e.message; }
                output.sameOriginFetch = sf;

                // ═══ 방안 3: Vuex dispatch ═══
                const vx = {};
                if (!store) { vx.error = 'no store'; }
                else {
                    // 3-1: selectGlobalProductDetail
                    try {
                        await store.dispatch('globalProduct/selectGlobalProductDetail', { productUuid: uuid });
                        vx.selectDetail = 'ok';
                        await new Promise(r => setTimeout(r, 2000));
                    } catch (e) { vx.selectDetail = (e.message || String(e)).substring(0, 200); }

                    // 3-2: 상태 확인
                    const d = store.state.globalProduct?._detail || {};
                    const ui = store.state.globalProduct?._detailUI || {};
                    vx.detailId = d.id;
                    vx.detailUuid = d.uuid;
                    vx.uiLang = ui.languageType;
                    vx.uiKeys = Object.keys(ui).join(',');

                    // 3-3: setDetailUI + insertDraft
                    try {
                        store.commit('globalProduct/setDetailUI', {
                            ...ui,
                            productName: 'テスト',
                            images: ['https://image.idus.com/image/files/6c105d356fcf444ebfd4e9c88265a4ac.jpg',
                                     'https://image.idus.com/image/files/ddb60123067b4b3ba0d33ab589fad709.jpg',
                                     'https://image.idus.com/image/files/69fcfba020d4451f9890c7808e1bc6e0.jpg',
                                     'https://image.idus.com/image/files/e0184c029db149ffa761efefabfaa0d6.jpg'],
                            keywords: ['test'],
                            premiumDescription: [{ type: 'TEXT', value: 'テスト', label: '', uuid: 'test1' }],
                        });
                        vx.setUI = 'ok';
                    } catch (e) { vx.setUI = e.message; }

                    try {
                        await store.dispatch('globalProduct/insertGlobalProductDraft');
                        vx.insertDraft = 'ok';
                    } catch (e) { vx.insertDraft = (e.message || String(e)).substring(0, 300); }
                }
                output.vuex = vx;

                return output;
            }
        """, pid)

        return {"success": True, "pid": pid, "data": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/debug/axios-save-test", summary="$axios로 실제 임시저장 테스트")
async def debug_axios_save_test():
    """$axios 인스턴스로 글로벌 작품 임시저장을 시도합니다."""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    page = _artist_session.page

    try:
        import re
        m = re.search(r'/product/([a-f0-9-]{36})', page.url)
        pid = m.group(1) if m else ""
        if not pid:
            return {"error": "product_id 없음"}

        if "/global" not in page.url:
            try:
                await page.goto(f"https://artist.idus.com/product/{pid}/global", timeout=30000)
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            await asyncio.sleep(5)

        result = await page.evaluate("""
            async (uuid) => {
                const output = {};
                const vm = document.querySelector('#app')?.__vue__;
                if (!vm) return { error: 'Vue not found' };

                const axios = vm.$axios || vm.$root?.$axios || window.$nuxt?.$axios;
                if (!axios) return { error: '$axios not found' };

                const store = vm.$store;
                const detail = store?.state?.globalProduct?._detail || {};
                const form = store?.state?.productForm?._item || {};

                output.detailId = detail.id;
                output.formId = form.id;
                output.formUuid = form.uuid;

                // $axios의 baseURL 확인
                output.axiosBaseURL = axios.defaults?.baseURL || 'none';

                // $axios로 가능한 API 경로들 탐색
                const testUrls = [
                    { label: 'aggregator-draft', method: 'put', url: `https://artist-aggregator.idus.com/api/v1/global/product/${detail.id || 0}/draft` },
                    { label: 'aggregator-v2-draft', method: 'put', url: `https://artist-aggregator.idus.com/api/v2/global/product-detail/${uuid}` },
                    { label: 'relative-draft', method: 'put', url: `/api/v1/global/product/${detail.id || 0}/draft` },
                    { label: 'relative-v2', method: 'put', url: `/api/v2/global/product-detail/${uuid}` },
                ];

                const payload = {
                    publish_status: 'WRITING',
                    name: 'テスト作品名',
                    language_code: 'ja',
                    images: [
                        'https://image.idus.com/image/files/6c105d356fcf444ebfd4e9c88265a4ac.jpg',
                        'https://image.idus.com/image/files/ddb60123067b4b3ba0d33ab589fad709.jpg',
                        'https://image.idus.com/image/files/69fcfba020d4451f9890c7808e1bc6e0.jpg',
                        'https://image.idus.com/image/files/e0184c029db149ffa761efefabfaa0d6.jpg',
                    ],
                    keywords: ['テスト'],
                    descriptions: [
                        { type: 'TEXT', value: 'テスト説明文です。', label: '', sort: 0 }
                    ],
                    option_groups: [],
                    prohibited_nations: [],
                    clearance_documents: [],
                    status: 'DRAFT',
                };

                output.tests = [];
                for (const t of testUrls) {
                    try {
                        const resp = await axios({ method: t.method, url: t.url, data: payload });
                        output.tests.push({
                            label: t.label, url: t.url,
                            status: resp.status, ok: true,
                            data: JSON.stringify(resp.data)?.substring(0, 300),
                        });
                    } catch (e) {
                        const errResp = e.response;
                        output.tests.push({
                            label: t.label, url: t.url,
                            status: errResp?.status || null,
                            ok: false,
                            error: (errResp?.data ? JSON.stringify(errResp.data).substring(0, 300) : (e.message || '').substring(0, 200)),
                        });
                    }
                }

                return output;
            }
        """, pid)

        return {"success": True, "pid": pid, "data": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/debug/token-and-direct-api", summary="토큰 추출 + httpx 직접 호출")
async def debug_token_and_direct_api():
    """브라우저 쿠키에서 토큰 추출 -> Python httpx로 aggregator API 직접 호출"""
    import asyncio
    import httpx

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    page = _artist_session.page

    try:
        import re
        m = re.search(r'/product/([a-f0-9-]{36})', page.url)
        pid = m.group(1) if m else ""

        token_info = await page.evaluate("""
            () => {
                const r = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const k = localStorage.key(i);
                    const v = localStorage.getItem(k);
                    if (k.match(/token|auth|jwt|session|access/i))
                        r['ls_' + k] = v?.substring(0, 150);
                }
                r.cookies = document.cookie.substring(0, 500);
                const vm = document.querySelector('#app')?.__vue__;
                const ax = vm?.$axios || vm?.$root?.$axios;
                if (ax?.defaults?.headers?.common)
                    r.axiosHeaders = JSON.stringify(ax.defaults.headers.common).substring(0, 300);
                return r;
            }
        """)

        cookies = await page.context.cookies()
        cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        idus_cookies = [{"name": c["name"], "domain": c["domain"],
                         "value": c["value"][:40]} for c in cookies if "idus" in c.get("domain", "")]

        detail_id = await page.evaluate(
            "() => document.querySelector('#app')?.__vue__?.$store?.state?.globalProduct?._detail?.id || 0"
        )

        base = "https://artist-aggregator.idus.com"
        api_tests = []
        headers = {
            "Cookie": cookie_header,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Origin": "https://artist.idus.com",
            "Referer": "https://artist.idus.com/",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            for label, url in [
                ("commission", f"{base}/api/v1/commission"),
                ("global-detail", f"{base}/api/v1/global/product/{detail_id}"),
            ]:
                try:
                    r = await client.get(url, headers=headers)
                    api_tests.append({"label": label, "status": r.status_code, "body": r.text[:200]})
                except Exception as e:
                    api_tests.append({"label": label, "error": str(e)[:100]})

            if detail_id:
                payload = {
                    "publish_status": "WRITING", "name": "test", "language_code": "ja",
                    "images": ["https://image.idus.com/image/files/6c105d356fcf444ebfd4e9c88265a4ac.jpg",
                               "https://image.idus.com/image/files/ddb60123067b4b3ba0d33ab589fad709.jpg",
                               "https://image.idus.com/image/files/69fcfba020d4451f9890c7808e1bc6e0.jpg",
                               "https://image.idus.com/image/files/e0184c029db149ffa761efefabfaa0d6.jpg"],
                    "keywords": ["test"],
                    "descriptions": [{"type": "TEXT", "value": "test desc", "label": "", "sort": 0}],
                    "option_groups": [], "prohibited_nations": [],
                    "clearance_documents": [], "status": "DRAFT",
                }
                for label, method, url in [
                    ("draft-put", "PUT", f"{base}/api/v1/global/product/{detail_id}/draft"),
                    ("draft-post", "POST", f"{base}/api/v1/global/product/{detail_id}/draft"),
                ]:
                    try:
                        r = await client.request(method, url, headers={**headers, "Content-Type": "application/json"}, json=payload)
                        api_tests.append({"label": label, "status": r.status_code, "body": r.text[:300]})
                    except Exception as e:
                        api_tests.append({"label": label, "error": str(e)[:100]})

        return {"success": True, "pid": pid, "detailId": detail_id, "tokenInfo": token_info,
                "idusCookies": idus_cookies, "totalCookies": len(cookies), "apiTests": api_tests}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/debug/vuex-commit-save-test", summary="Vuex commit + 임시저장 버튼 조합 테스트")
async def debug_vuex_commit_save_test():
    """Vuex setDetailUI commit으로 이미지+설명+키워드 설정 후 임시저장 버튼 클릭.
    캡처된 API 요청의 payload에 이미지/설명이 포함되는지 확인."""
    import asyncio

    if not _artist_session or not _artist_session.page:
        return {"error": "세션 미초기화"}
    if not await _artist_session.is_authenticated():
        return {"error": "로그인 필요"}

    page = _artist_session.page
    captured = []
    steps = []

    try:
        async def on_req(request):
            if request.method in ("POST", "PUT", "PATCH"):
                url = request.url
                if "kinesis" not in url and "sentry" not in url and "channel" not in url and "facebook" not in url and "cognito" not in url:
                    captured.append({"url": url, "method": request.method, "body": (request.post_data or "")[:2000]})

        page.on("request", on_req)

        try:
            import re
            m = re.search(r'/product/([a-f0-9-]{36})', page.url)
            pid = m.group(1) if m else ""
            if not pid:
                return {"error": "product_id 없음"}

            # STEP 1: 글로벌 페이지 이동
            if "/global" not in page.url:
                try:
                    await page.goto(f"https://artist.idus.com/product/{pid}/global", timeout=30000)
                    await page.wait_for_load_state("domcontentloaded")
                except Exception:
                    pass
                await asyncio.sleep(5)
            steps.append({"step": "글로벌 이동", "url": page.url})

            # STEP 2: 작품명 textarea 입력
            textarea = page.locator('textarea[name="globalProductName"]').first
            if await textarea.count() > 0:
                await textarea.fill("テスト作品名_Vuex検証")
                await textarea.dispatch_event("input")
                steps.append({"step": "작품명 입력", "ok": True})
            else:
                steps.append({"step": "작품명 입력", "ok": False})

            # STEP 3: Vuex setDetailUI commit (이미지 + 설명 + 키워드)
            vuex_result = await page.evaluate("""
                () => {
                    const app = document.querySelector('#app');
                    if (!app || !app.__vue__ || !app.__vue__.$store) return { error: 'no store' };
                    const store = app.__vue__.$store;
                    const ui = store.state.globalProduct?._detailUI || {};

                    const newUI = {
                        ...ui,
                        productName: 'テスト作品名_Vuex検証',
                        images: [
                            'https://image.idus.com/image/files/6c105d356fcf444ebfd4e9c88265a4ac.jpg',
                            'https://image.idus.com/image/files/ddb60123067b4b3ba0d33ab589fad709.jpg',
                            'https://image.idus.com/image/files/69fcfba020d4451f9890c7808e1bc6e0.jpg',
                            'https://image.idus.com/image/files/e0184c029db149ffa761efefabfaa0d6.jpg',
                        ],
                        keywords: ['テスト1', 'テスト2', 'テスト3'],
                        premiumDescription: [
                            { type: 'TEXT', value: 'テスト説明文です。これはVuex commit経由の検証です。', label: '', uuid: 'test_txt_1' },
                            { type: 'IMAGE', value: ['https://image.idus.com/image/files/6c105d356fcf444ebfd4e9c88265a4ac.jpg'], label: '', uuid: 'test_img_1' },
                            { type: 'TEXT', value: '二番目のテスト段落です。', label: '', uuid: 'test_txt_2' },
                        ],
                    };
                    store.commit('globalProduct/setDetailUI', newUI);

                    // 확인
                    const updated = store.state.globalProduct?._detailUI || {};
                    return {
                        ok: true,
                        name: updated.productName,
                        imgCount: updated.images?.length || 0,
                        kwCount: updated.keywords?.length || 0,
                        descCount: updated.premiumDescription?.length || 0,
                    };
                }
            """)
            steps.append({"step": "Vuex commit", "result": vuex_result})

            # STEP 4: 임시저장 버튼 클릭
            await asyncio.sleep(1)
            save_btn = page.locator('button:has-text("임시저장")').first
            if await save_btn.count() > 0:
                await save_btn.click()
                await asyncio.sleep(3)
                steps.append({"step": "임시저장 클릭", "ok": True})
            else:
                steps.append({"step": "임시저장 클릭", "ok": False})

            # STEP 5: 스낵바 확인
            try:
                snack = page.locator('.v-snack__content').first
                if await snack.count() > 0:
                    msg = await snack.inner_text()
                    steps.append({"step": "스낵바", "message": msg})
            except Exception:
                pass

        finally:
            page.remove_listener("request", on_req)

        # 캡처된 요청에서 migrate-product 찾아 payload 분석
        api_payload_analysis = None
        for c in captured:
            if "migrate-product" in c.get("url", "") or "global" in c.get("url", ""):
                body = c.get("body", "")
                import json
                try:
                    parsed = json.loads(body)
                    api_payload_analysis = {
                        "url": c["url"],
                        "method": c["method"],
                        "has_images": bool(parsed.get("images")),
                        "image_count": len(parsed.get("images", [])),
                        "has_keywords": bool(parsed.get("keywords")),
                        "keyword_count": len(parsed.get("keywords", [])),
                        "has_descriptions": bool(parsed.get("descriptions")),
                        "desc_count": len(parsed.get("descriptions", [])),
                        "name": parsed.get("name", "")[:50],
                        "language_code": parsed.get("language_code", ""),
                    }
                except Exception:
                    api_payload_analysis = {"url": c["url"], "raw_body": body[:500]}
                break

        return {
            "success": True,
            "steps": steps,
            "captured_count": len(captured),
            "api_payload": api_payload_analysis,
            "all_captured_urls": [c["url"] for c in captured],
        }

    except Exception as e:
        return {"success": False, "error": str(e), "steps": steps}
