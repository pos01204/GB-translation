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
