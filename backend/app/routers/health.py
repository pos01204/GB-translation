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

                return {
                    url: window.location.href,
                    title: document.title,
                    inputCount: inputs.length,
                    inputs: inputs,
                    buttonCount: buttons.length,
                    buttons: buttons,
                    imageCount: images.length,
                    images: images,
                    tabs: tabs,
                };
            }
        """)

        return {"success": True, "data": dom_info}

    except Exception as e:
        logger.error(f"작품 페이지 디버그 실패: {e}")
        return {"success": False, "error": str(e)}
