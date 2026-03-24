"""
작가웹 글로벌 작품 등록 — aggregator API 직접 호출 방식

확정된 API (2026-03-25 네트워크 캡처):

임시저장: PUT https://artist-aggregator.idus.com/api/v1/global/product/{product_id}/draft
판매등록: PUT https://artist-aggregator.idus.com/api/v1/global/product/{product_id}

Request Payload:
{
  "publish_status": "WRITING" | "PUBLISHED",
  "name": "작품명",
  "language_code": "ja" | "en",
  "images": ["url1", ...],
  "keywords": ["kw1", ...],
  "descriptions": [{"value": "텍스트", "type": "TEXT", "label": "", "sort": 0}],
  "option_groups": [],
  "prohibited_nations": [],
  "clearance_documents": [],
  "request_push": [],
  "status": "DRAFT" | "SALE"
}

인증: Bearer 토큰 (Playwright 브라우저의 쿠키/세션에서 자동 처리)
"""
import asyncio
import logging
from typing import Optional
from playwright.async_api import Page
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..config import settings

logger = logging.getLogger(__name__)

AGGREGATOR_BASE = "https://artist-aggregator.idus.com"


class ProductWriter:
    """작가웹 글로벌 작품 등록 — API 직접 호출"""

    def __init__(self, page: Page):
        self.page = page

    async def register_language(
        self,
        product_uuid: str,
        language: str,
        data: LanguageData,
        domestic_images: list[str],
        domestic_id: int = 0,
        global_options: list[GlobalOption] = None,
        save_as_draft: bool = True,
    ) -> bool:
        """특정 언어로 글로벌 작품 등록 — aggregator API 직접 호출"""
        lang_label = "영어" if language == "en" else "일본어"
        lang_code = "en" if language == "en" else "ja"
        logger.info(f"{lang_label} 등록 시작 (API 직접 호출)")

        # descriptions 블록 변환
        descriptions = []
        blocks = data.description_blocks if hasattr(data, 'description_blocks') and data.description_blocks else []
        for i, block in enumerate(blocks):
            block_type = block.get("type", "TEXT")
            value = block.get("value", "")

            # IMAGE 블록: value가 배열이면 첫 URL
            if block_type == "IMAGE" and isinstance(value, list):
                value = value[0] if value else ""
            elif isinstance(value, list):
                value = ", ".join(str(v) for v in value)

            if block_type in ("TEXT", "SUBJECT", "IMAGE", "LINE", "BLANK"):
                descriptions.append({
                    "type": block_type,
                    "value": str(value),
                    "label": block.get("label", ""),
                    "sort": i,
                })

        # 설명이 비어있으면 HTML에서 간단 변환
        if not descriptions and data.description_html:
            descriptions.append({
                "type": "TEXT",
                "value": data.description_html,
                "label": "",
                "sort": 0,
            })

        # 키워드 정리
        keywords = [kw.strip().lstrip('#') for kw in (data.keywords or []) if kw.strip()]

        # 옵션 그룹
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

        # API payload
        payload = {
            "publish_status": "WRITING" if save_as_draft else "PUBLISHED",
            "name": (data.title or "")[:settings.title_max_length_global],
            "language_code": lang_code,
            "images": domestic_images or [],
            "keywords": keywords,
            "descriptions": descriptions,
            "option_groups": option_groups,
            "prohibited_nations": [],
            "clearance_documents": [],
            "request_push": [],
            "status": "DRAFT" if save_as_draft else "SALE",
        }

        logger.info(
            f"{lang_label} API 호출: "
            f"제목={payload['name'][:30]}..., "
            f"이미지={len(payload['images'])}장, "
            f"키워드={len(payload['keywords'])}개, "
            f"설명={len(payload['descriptions'])}블록, "
            f"옵션={len(payload['option_groups'])}개"
        )

        # Playwright 브라우저 내에서 fetch() 호출 (쿠키/인증 자동 포함)
        result = await self.page.evaluate("""
            async (args) => {
                const { uuid, payload, domesticId } = args;
                const base = 'https://artist-aggregator.idus.com';
                const headers = {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'platform': 'web',
                };

                try {
                    // STEP 1: migrate-product (글로벌 작품 생성/마이그레이션)
                    if (domesticId) {
                        const migrateResp = await fetch(
                            `${base}/api/v2/global/migrate-product/${domesticId}`,
                            { method: 'POST', headers, body: JSON.stringify(payload), credentials: 'include' }
                        );
                        const migrateStatus = migrateResp.status;
                        let migrateBody = null;
                        try { migrateBody = await migrateResp.json(); } catch(e) {}

                        // STEP 2: product-detail (실제 데이터 저장)
                        const detailResp = await fetch(
                            `${base}/api/v2/global/product-detail/${uuid}`,
                            { method: 'PUT', headers, body: JSON.stringify(payload), credentials: 'include' }
                        );
                        const detailStatus = detailResp.status;
                        let detailBody = null;
                        try { detailBody = await detailResp.json(); } catch(e) {}

                        return {
                            success: detailStatus >= 200 && detailStatus < 300,
                            migrateStatus: migrateStatus,
                            detailStatus: detailStatus,
                            response: JSON.stringify(detailBody || migrateBody).substring(0, 500),
                        };
                    } else {
                        // domesticId 없으면 product-detail만 호출
                        const resp = await fetch(
                            `${base}/api/v2/global/product-detail/${uuid}`,
                            { method: 'PUT', headers, body: JSON.stringify(payload), credentials: 'include' }
                        );
                        const status = resp.status;
                        let body = null;
                        try { body = await resp.json(); } catch(e) {}

                        return {
                            success: status >= 200 && status < 300,
                            status: status,
                            response: JSON.stringify(body).substring(0, 500),
                        };
                    }
                } catch (err) {
                    return { success: false, error: err.message || String(err) };
                }
            }
        """, {"uuid": product_uuid, "payload": payload, "domesticId": domestic_id})

        if result.get("success"):
            logger.info(f"{lang_label} API 저장 성공 (status={result.get('status')})")
            return True
        else:
            logger.error(
                f"{lang_label} API 저장 실패: "
                f"status={result.get('status')}, "
                f"error={result.get('error', '')}, "
                f"response={result.get('response', '')[:200]}"
            )
            return False

    async def register_global_product(
        self,
        global_data: GlobalProductData,
        product_id: str = "",
        save_as_draft: bool = True,
        target_languages: Optional[list[str]] = None,
        domestic_images: list[str] = None,
    ) -> dict:
        """글로벌 작품 등록 — 각 언어별 API 직접 호출"""
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

        # 글로벌 페이지로 이동 (인증 토큰 확보를 위해)
        try:
            url = f"https://artist.idus.com/product/{product_id}/global"
            await self.page.goto(url, timeout=30000)
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"글로벌 페이지 이동 오류 (계속): {e}")

        # 국내 작품 숫자 ID 가져오기 (migrate-product API에 필요)
        domestic_id = 0
        try:
            domestic_id = await self.page.evaluate("""
                () => {
                    const app = document.querySelector('#app');
                    if (!app || !app.__vue__ || !app.__vue__.$store) return 0;
                    return app.__vue__.$store.state.productForm?._item?.id || 0;
                }
            """)
            logger.info(f"국내 작품 ID: {domestic_id}")
        except Exception:
            pass

        for lang in target_languages:
            lang_data = global_data.ja if lang == "ja" else global_data.en
            if not lang_data:
                result["languages_failed"].append(lang)
                continue

            ok = await self.register_language(
                product_uuid=product_id,
                language=lang,
                data=lang_data,
                domestic_images=domestic_images or [],
                domestic_id=domestic_id,
                global_options=global_data.global_options,
                save_as_draft=save_as_draft,
            )
            if ok:
                result["languages_success"].append(lang)
            else:
                result["languages_failed"].append(lang)

        return result
