"""
작가웹 글로벌 작품 등록 — Playwright route intercept 방식

핵심 원리:
1. 작품명만 textarea에 입력 (SPA의 v-model 반영)
2. Playwright route()로 migrate-product API 요청 인터셉트 등록
3. "임시저장" 버튼 클릭 → SPA가 API 호출
4. 인터셉트에서 원본 payload를 가로채 우리 데이터로 교체
5. 수정된 payload로 실제 API 전달

장점:
- CORS 문제 없음 (SPA 자체 호출, Bearer 토큰 자동 포함)
- 모달 UI 조작 완전 제거 (에디터/키워드/옵션 모달 불필요)
- 이미 작동 확인된 "작품명 + 임시저장" 플로우 활용
"""
import asyncio
import json
import logging
from typing import Optional
from playwright.async_api import Page, Route
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..config import settings

logger = logging.getLogger(__name__)


class ProductWriter:
    """작가웹 글로벌 작품 등록 — route intercept 방식"""

    def __init__(self, page: Page):
        self.page = page

    async def register_language(
        self,
        language: str,
        data: LanguageData,
        domestic_images: list[str] = None,
        global_options: list[GlobalOption] = None,
    ) -> tuple[bool, str]:
        """특정 언어로 글로벌 작품 등록

        Returns: (성공 여부, 메시지)
        """
        lang_label = "영어" if language == "en" else "일본어"
        lang_code = "en" if language == "en" else "ja"
        logger.info(f"{lang_label} 등록 시작")

        # 1. 언어 탭 선택
        tab = self.page.locator(
            f'.GlobalProductLanguageTab__item:has-text("{lang_label}")'
        ).first
        try:
            if await tab.count() > 0:
                await tab.click()
                await asyncio.sleep(3)
                logger.info(f"'{lang_label}' 탭 선택 완료")
            else:
                return False, f"'{lang_label}' 탭 없음"
        except Exception as e:
            return False, f"탭 선택 실패: {e}"

        # 2. 작품명 textarea 입력 (SPA v-model 반영)
        textarea = self.page.locator('textarea[name="globalProductName"]').first
        title = (data.title or "")[:settings.title_max_length_global]
        try:
            if await textarea.count() > 0:
                await textarea.fill(title)
                await textarea.dispatch_event("input")
                logger.info(f"작품명 입력: {title[:30]}...")
            else:
                return False, "작품명 textarea 없음"
        except Exception as e:
            return False, f"작품명 입력 실패: {e}"

        # 3. 우리 데이터로 교체할 payload 구성
        descriptions = self._build_descriptions(data)
        keywords = [kw.strip().lstrip('#') for kw in (data.keywords or []) if kw.strip()]
        option_groups = self._build_option_groups(global_options, language)
        images = domestic_images or []

        payload_override = {
            "name": title,
            "language_code": lang_code,
            "images": images,
            "keywords": keywords,
            "descriptions": descriptions,
            "option_groups": option_groups,
        }

        logger.info(
            f"{lang_label} payload: 이미지={len(images)}장, "
            f"키워드={len(keywords)}개, 설명={len(descriptions)}블록, "
            f"옵션={len(option_groups)}개"
        )

        # 4. route intercept 등록 — migrate-product API 요청을 가로채서 payload 교체
        intercept_result = {"intercepted": False, "status": None, "error": None}

        async def intercept_save(route: Route):
            """SPA의 저장 API 요청을 가로채서 payload를 우리 데이터로 교체"""
            request = route.request
            try:
                # 원본 payload 파싱
                original = json.loads(request.post_data) if request.post_data else {}

                # 우리 데이터로 교체 (원본의 다른 필드는 유지)
                modified = {**original, **payload_override}

                logger.info(
                    f"[intercept] 원본: img={len(original.get('images', []))}, "
                    f"kw={len(original.get('keywords', []))}, "
                    f"desc={len(original.get('descriptions', []))} → "
                    f"수정: img={len(modified.get('images', []))}, "
                    f"kw={len(modified.get('keywords', []))}, "
                    f"desc={len(modified.get('descriptions', []))}"
                )

                # 수정된 payload로 요청 계속 진행
                await route.continue_(post_data=json.dumps(modified))
                intercept_result["intercepted"] = True

            except Exception as e:
                logger.error(f"[intercept] payload 수정 실패: {e}")
                # 실패 시 원본 요청 그대로 진행
                await route.continue_()
                intercept_result["error"] = str(e)

        # route 등록
        # 디버그 테스트에서 검증된 동일한 패턴 사용
        route_pattern = "**/migrate-product/**"
        await self.page.route(route_pattern, intercept_save)
        logger.info(f"route intercept 등록: {route_pattern}")

        try:
            # 5. "임시저장" 버튼 클릭
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.5)

            save_btn = self.page.locator('button:has-text("임시저장")').first
            try:
                if await save_btn.count() > 0:
                    await save_btn.click()
                    logger.info("임시저장 버튼 클릭")
                else:
                    return False, "임시저장 버튼 없음"
            except Exception as e:
                return False, f"임시저장 클릭 실패: {e}"

            # 6. 결과 확인 (스낵바)
            await asyncio.sleep(3)
            msg = ""
            try:
                snack = self.page.locator('.v-snack__content').first
                if await snack.count() > 0:
                    msg = await snack.inner_text()
            except Exception:
                pass

            if "완료" in msg:
                logger.info(f"{lang_label} 임시저장 성공: {msg}")
                return True, msg
            elif msg:
                logger.error(f"{lang_label} 임시저장 실패: {msg}")
                return False, msg
            else:
                # 스낵바 없어도 intercept 성공했으면 OK
                if intercept_result["intercepted"]:
                    logger.info(f"{lang_label} 임시저장 완료 (intercept 성공, 스낵바 없음)")
                    return True, "intercept 성공"
                return False, "스낵바 없음"

        finally:
            # route 해제
            await self.page.unroute("**/migrate-product/**")

    def _build_descriptions(self, data: LanguageData) -> list[dict]:
        """LanguageData에서 descriptions 배열 구성"""
        descriptions = []
        blocks = getattr(data, 'description_blocks', None) or []

        for i, block in enumerate(blocks):
            block_type = block.get("type", "TEXT")
            value = block.get("value", "")

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

        # 블록이 없으면 HTML에서 간단 변환
        if not descriptions and data.description_html:
            descriptions.append({
                "type": "TEXT",
                "value": data.description_html[:2000],
                "label": "",
                "sort": 0,
            })

        return descriptions

    def _build_option_groups(
        self, options: list[GlobalOption] = None, language: str = "ja"
    ) -> list[dict]:
        """GlobalOption에서 option_groups 배열 구성"""
        if not options:
            return []
        groups = []
        for opt in options:
            name = opt.name_en if language == "en" else opt.name_ja
            values = opt.values_en if language == "en" else opt.values_ja
            if name and values:
                groups.append({
                    "name": name,
                    "type": opt.option_type or "Basic",
                    "values": [{"value": v, "price": 0} for v in values],
                })
        return groups

    async def register_global_product(
        self,
        global_data: GlobalProductData,
        product_id: str = "",
        save_as_draft: bool = True,
        target_languages: list[str] = None,
        domestic_images: list[str] = None,
    ) -> dict:
        """글로벌 작품 등록 — route intercept 방식"""
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

        # 글로벌 페이지 이동
        url = f"https://artist.idus.com/product/{product_id}/global"
        logger.info(f"글로벌 페이지 이동: {url}")
        try:
            await self.page.goto(url, timeout=30000)
            await self.page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            logger.warning(f"goto 오류 (계속): {e}")
        await asyncio.sleep(5)

        # textarea 대기
        try:
            await self.page.wait_for_selector(
                'textarea[name="globalProductName"]', timeout=10000
            )
        except Exception:
            logger.error("글로벌 폼 로딩 실패")
            result["languages_failed"] = target_languages
            return result

        logger.info("글로벌 탭 이동 완료")

        # 국내 이미지 (Vuex에서 가져오기)
        if not domestic_images:
            try:
                domestic_images = await self.page.evaluate("""
                    () => {
                        const app = document.querySelector('#app');
                        if (!app || !app.__vue__ || !app.__vue__.$store) return [];
                        return app.__vue__.$store.state.productForm?._item?.images || [];
                    }
                """)
                if domestic_images:
                    logger.info(f"Vuex에서 국내 이미지 {len(domestic_images)}장")
            except Exception:
                domestic_images = []

        # 각 언어별 등록
        for i, lang in enumerate(target_languages):
            # 이전 언어 실패 후 남은 모달/스낵바 정리
            if i > 0:
                for _ in range(3):
                    try:
                        if await self.page.locator('.v-dialog--active').count() > 0:
                            ok_btn = self.page.locator('.v-dialog--active button:has-text("확인")').first
                            if await ok_btn.count() > 0:
                                await ok_btn.click()
                            else:
                                await self.page.keyboard.press("Escape")
                            await asyncio.sleep(0.5)
                        else:
                            break
                    except Exception:
                        break
                await asyncio.sleep(1)
            lang_data = global_data.ja if lang == "ja" else global_data.en
            if not lang_data:
                result["languages_failed"].append(lang)
                continue

            ok, msg = await self.register_language(
                language=lang,
                data=lang_data,
                domestic_images=domestic_images,
                global_options=global_data.global_options,
            )
            if ok:
                result["languages_success"].append(lang)
            else:
                result["languages_failed"].append(lang)
                logger.error(f"{lang} 등록 실패: {msg}")

        return result
