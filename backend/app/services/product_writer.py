"""
작가웹 글로벌 작품 등록 — Python httpx 직접 API 호출

핵심: Bearer 토큰을 Playwright 브라우저에서 추출 → Python httpx로 서버→서버 API 호출.
- CORS 문제 없음 (브라우저가 아닌 서버에서 호출)
- 클라이언트 사이드 검증 우회 (SPA 경유 안 함)
- Bearer 토큰은 $axios 인터셉터 또는 localStorage에서 추출

확정된 API:
POST https://artist-aggregator.idus.com/api/v2/global/migrate-product/{domestic_id}
"""
import asyncio
import json
import logging
import httpx
from typing import Optional
from playwright.async_api import Page
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..config import settings

logger = logging.getLogger(__name__)

AGGREGATOR_BASE = "https://artist-aggregator.idus.com"


class ProductWriter:
    """작가웹 글로벌 작품 등록 — httpx 직접 API 호출"""

    def __init__(self, page: Page):
        self.page = page
        self._bearer_token: Optional[str] = None

    async def _extract_bearer_token(self) -> Optional[str]:
        """브라우저에서 Bearer 토큰 추출"""
        if self._bearer_token:
            return self._bearer_token

        token = await self.page.evaluate("""
            () => {
                // 1. $axios 인터셉터에서 추출
                const app = document.querySelector('#app');
                if (app && app.__vue__) {
                    const vm = app.__vue__;
                    const ax = vm.$axios || vm.$root?.$axios;
                    if (ax && ax.defaults && ax.defaults.headers) {
                        const auth = ax.defaults.headers.common?.Authorization
                            || ax.defaults.headers.Authorization;
                        if (auth) return auth.replace('Bearer ', '');
                    }
                    // interceptor에서 직접 추출
                    if (ax && ax.interceptors && ax.interceptors.request) {
                        for (const h of ax.interceptors.request.handlers || []) {
                            if (h && h.fulfilled) {
                                try {
                                    // 인터셉터 함수를 호출해서 토큰 추출 시도
                                    const config = { headers: {} };
                                    const result = h.fulfilled(config);
                                    if (result && result.headers && result.headers.Authorization) {
                                        return result.headers.Authorization.replace('Bearer ', '');
                                    }
                                } catch(e) {}
                            }
                        }
                    }
                }
                // 2. localStorage
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    const val = localStorage.getItem(key);
                    if (val && val.length > 20 && val.length < 2000) {
                        if (key.toLowerCase().includes('token') || key.toLowerCase().includes('auth')
                            || key.toLowerCase().includes('jwt') || key.toLowerCase().includes('access')) {
                            return val;
                        }
                    }
                }
                // 3. sessionStorage
                for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    const val = sessionStorage.getItem(key);
                    if (val && val.length > 20 && val.length < 2000) {
                        if (key.toLowerCase().includes('token') || key.toLowerCase().includes('auth')) {
                            return val;
                        }
                    }
                }
                // 4. cookie
                const cookies = document.cookie.split(';');
                for (const c of cookies) {
                    const [k, v] = c.trim().split('=');
                    if (k && v && v.length > 20) {
                        if (k.toLowerCase().includes('token') || k.toLowerCase().includes('auth')
                            || k.toLowerCase().includes('jwt')) {
                            return v;
                        }
                    }
                }
                return null;
            }
        """)

        if token:
            self._bearer_token = token
            logger.info(f"Bearer 토큰 추출 성공 (길이: {len(token)})")
        else:
            # 마지막 수단: 실제 API 호출을 캡처하여 토큰 추출
            token = await self._capture_token_from_request()
            if token:
                self._bearer_token = token
                logger.info(f"API 캡처로 토큰 추출 성공 (길이: {len(token)})")
            else:
                logger.error("Bearer 토큰 추출 실패")

        return self._bearer_token

    async def _capture_token_from_request(self) -> Optional[str]:
        """SPA의 실제 API 요청에서 Authorization 헤더 캡처"""
        token_holder = {"token": None}

        async def on_request(request):
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer ") and len(auth) > 20:
                token_holder["token"] = auth.replace("Bearer ", "")

        self.page.on("request", on_request)
        try:
            # SPA가 API를 호출하도록 페이지 새로고침
            await self.page.reload(timeout=15000)
            await asyncio.sleep(5)
        except Exception:
            pass
        finally:
            self.page.remove_listener("request", on_request)

        return token_holder["token"]

    async def _call_api(
        self,
        method: str,
        path: str,
        data: dict,
    ) -> tuple[bool, str, dict]:
        """aggregator API 직접 호출

        Returns: (성공, 메시지, 응답 데이터)
        """
        token = await self._extract_bearer_token()
        if not token:
            return False, "Bearer 토큰 추출 실패", {}

        url = f"{AGGREGATOR_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://artist.idus.com",
            "Referer": "https://artist.idus.com/",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if method == "POST":
                    resp = await client.post(url, json=data, headers=headers)
                elif method == "PUT":
                    resp = await client.put(url, json=data, headers=headers)
                else:
                    return False, f"미지원 메서드: {method}", {}

                body = {}
                try:
                    body = resp.json()
                except Exception:
                    body = {"raw": resp.text[:500]}

                if resp.status_code in (200, 201):
                    logger.info(f"API 성공: {method} {path} → {resp.status_code}")
                    return True, "성공", body
                else:
                    logger.error(f"API 실패: {method} {path} → {resp.status_code}: {resp.text[:300]}")
                    return False, f"HTTP {resp.status_code}: {resp.text[:200]}", body

        except Exception as e:
            logger.error(f"API 호출 실패: {e}")
            return False, str(e), {}

    def _build_payload(
        self,
        language: str,
        data: LanguageData,
        domestic_images: list[str] = None,
        global_options: list[GlobalOption] = None,
    ) -> dict:
        """API payload 구성"""
        lang_code = "en" if language == "en" else "ja"

        # descriptions (블록 배열)
        descriptions = []
        blocks = getattr(data, 'description_blocks', None) or []
        for i, block in enumerate(blocks):
            btype = block.get("type", "TEXT")
            value = block.get("value", "")
            if isinstance(value, list):
                value = value[0] if value else ""
            if btype in ("TEXT", "SUBJECT", "IMAGE", "LINE", "BLANK"):
                descriptions.append({
                    "type": btype,
                    "value": str(value),
                    "label": block.get("label", ""),
                })
        if not descriptions and data.description_html:
            descriptions.append({
                "type": "TEXT",
                "value": data.description_html[:2000],
                "label": "",
                "sort": 0,
            })

        # keywords
        keywords = [kw.strip().lstrip('#') for kw in (data.keywords or []) if kw.strip()]

        # option_groups
        option_groups = []
        if global_options:
            for opt in global_options:
                name = opt.name_en if language == "en" else opt.name_ja
                values = opt.values_en if language == "en" else opt.values_ja
                if name and values:
                    option_groups.append({
                        "name": name,
                        "type": opt.option_type or "Basic",
                        "values": [{"value": v, "price": 0} for v in values],
                    })

        return {
            "publish_status": "WRITING",
            "name": (data.title or "")[:settings.title_max_length_global],
            "language_code": lang_code,
            "images": domestic_images or [],
            "keywords": keywords,
            "descriptions": descriptions,
            "option_groups": [],  # TODO: 옵션 구조 확인 후 활성화
            "status": "DRAFT",
            "prohibited_nations": [],
            "clearance_documents": [],
            "request_push": [],
        }

    async def register_language(
        self,
        domestic_id: int,
        language: str,
        data: LanguageData,
        domestic_images: list[str] = None,
        global_options: list[GlobalOption] = None,
    ) -> tuple[bool, str]:
        """특정 언어로 글로벌 작품 등록 (API 직접 호출)"""
        lang_label = "영어" if language == "en" else "일본어"
        logger.info(f"{lang_label} 등록 시작 (API 직접 호출)")

        payload = self._build_payload(
            language=language,
            data=data,
            domestic_images=domestic_images,
            global_options=global_options,
        )

        # 디버그: 전체 payload 로깅 (첫 500자)
        import json as _json
        payload_str = _json.dumps(payload, ensure_ascii=False)
        logger.info(
            f"{lang_label} API 호출: 제목={payload['name'][:30]}..., "
            f"이미지={len(payload['images'])}장, "
            f"키워드={len(payload['keywords'])}개, "
            f"설명={len(payload['descriptions'])}블록, "
            f"옵션={len(payload['option_groups'])}개"
        )
        logger.info(f"{lang_label} payload 샘플: {payload_str[:500]}")

        ok, msg, body = await self._call_api(
            "POST",
            f"/api/v2/global/migrate-product/{domestic_id}",
            payload,
        )

        if ok:
            logger.info(f"{lang_label} 등록 성공")
        else:
            logger.error(f"{lang_label} 등록 실패: {msg}")

        return ok, msg

    async def register_global_product(
        self,
        global_data: GlobalProductData,
        product_id: str = "",
        save_as_draft: bool = True,
        target_languages: list[str] = None,
        domestic_images: list[str] = None,
    ) -> dict:
        """글로벌 작품 등록"""
        if target_languages is None:
            target_languages = []
            if global_data.ja:
                target_languages.append("ja")
            if global_data.en:
                target_languages.append("en")

        result = {"languages_success": [], "languages_failed": []}

        if not product_id:
            logger.error("product_id가 없습니다")
            result["languages_failed"] = target_languages
            return result

        # 글로벌 페이지로 이동 (토큰 추출을 위해)
        url = f"https://artist.idus.com/product/{product_id}/global"
        logger.info(f"글로벌 페이지 이동: {url}")
        try:
            await self.page.goto(url, timeout=30000)
            await self.page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            logger.warning(f"goto 오류 (계속): {e}")
        await asyncio.sleep(5)

        # domestic_id 가져오기 (Vuex에서)
        domestic_id = await self.page.evaluate("""
            () => {
                const app = document.querySelector('#app');
                if (!app || !app.__vue__ || !app.__vue__.$store) return 0;
                return app.__vue__.$store.state.productForm?._item?.id || 0;
            }
        """)

        if not domestic_id:
            logger.error("domestic_id를 가져올 수 없습니다")
            result["languages_failed"] = target_languages
            return result

        logger.info(f"국내 작품 ID: {domestic_id}")

        # 국내 이미지 (Vuex에서)
        if not domestic_images:
            domestic_images = await self.page.evaluate("""
                () => {
                    const app = document.querySelector('#app');
                    if (!app || !app.__vue__ || !app.__vue__.$store) return [];
                    return app.__vue__.$store.state.productForm?._item?.images || [];
                }
            """) or []
            if domestic_images:
                logger.info(f"Vuex에서 국내 이미지 {len(domestic_images)}장")

        # Bearer 토큰 추출
        token = await self._extract_bearer_token()
        if not token:
            logger.error("Bearer 토큰 추출 실패 — 등록 불가")
            result["languages_failed"] = target_languages
            return result

        # 각 언어별 등록
        for lang in target_languages:
            lang_data = global_data.ja if lang == "ja" else global_data.en
            if not lang_data:
                result["languages_failed"].append(lang)
                continue

            ok, msg = await self.register_language(
                domestic_id=domestic_id,
                language=lang,
                data=lang_data,
                domestic_images=domestic_images,
                global_options=global_data.global_options,
            )
            if ok:
                result["languages_success"].append(lang)
            else:
                result["languages_failed"].append(lang)

        return result
