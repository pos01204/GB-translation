"""
GB 등록용 번역 서비스

기존 gemini_client.py의 ProductTranslator를 래핑하여
GB 등록에 특화된 번역 로직을 제공합니다.

주요 차이점:
- GB 전용 프롬프트 사용 (HTML 구조 보존, 글로벌 마켓 톤)
- DomesticProduct → GlobalProductData 변환
- 영어/일본어 동시 번역 지원
- 옵션 번역 (양 언어 병렬)
"""
import asyncio
import logging
import os
from typing import Optional

import httpx

from ..models.domestic import DomesticProduct, DomesticOption
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption, ImageText
from ..config import settings

from ..prompts import (
    GB_TITLE_PROMPT_EN, GB_DESCRIPTION_PROMPT_EN,
    GB_KEYWORD_PROMPT_EN, GB_OPTION_PROMPT_EN,
    GB_DESCRIPTION_REBUILD_PROMPT_EN,
    GB_TITLE_PROMPT_JA, GB_DESCRIPTION_PROMPT_JA,
    GB_KEYWORD_PROMPT_JA, GB_OPTION_PROMPT_JA,
    GB_DESCRIPTION_REBUILD_PROMPT_JA,
)

logger = logging.getLogger(__name__)


class GBProductTranslator:
    """GB 등록 전용 번역기

    기존 ProductTranslator의 Gemini 클라이언트를 재활용하면서
    GB 등록에 최적화된 프롬프트와 후처리 로직을 적용합니다.

    Usage:
        from app.translator import ProductTranslator
        base = ProductTranslator(api_key="...")
        gb = GBProductTranslator(base)
        result = await gb.translate_for_gb(domestic_product, ["en", "ja"])
    """

    def __init__(self, base_translator):
        """
        Args:
            base_translator: 기존 ProductTranslator 인스턴스
                             (Gemini 클라이언트, rate limiter 포함)
        """
        self.translator = base_translator

    @property
    def is_initialized(self) -> bool:
        return self.translator and self.translator._initialized

    async def translate_for_gb(
        self,
        domestic: DomesticProduct,
        target_languages: list[str],
    ) -> GlobalProductData:
        """
        국내 작품 데이터를 글로벌 등록용으로 번역

        Args:
            domestic: 국내 작품 데이터
            target_languages: ["en", "ja"] 등

        Returns:
            GlobalProductData: 번역된 글로벌 등록 데이터
        """
        logger.info(
            f"GB 번역 시작: {domestic.product_id} "
            f"(언어={target_languages}, 제목={domestic.title[:20]}...)"
        )

        en_data = None
        ja_data = None
        global_options: list[GlobalOption] = []

        do_en = "en" in target_languages
        do_ja = "ja" in target_languages

        # ── GB 최적화 파이프라인 ──
        # 1. OCR (1회) → 텍스트 수집
        # 2. 제목+키워드 (EN/JA 각 1회)
        # 3. AI 상세 설명 재구성 (EN/JA 각 1회) — KR 데이터 + OCR 텍스트 기반
        # 4. 옵션 번역

        en_title, en_desc, en_keywords = "", "", []
        ja_title, ja_desc, ja_keywords = "", "", []

        # 1. 이미지 OCR — 텍스트 수집 (1회, 이미지 생성 없음)
        ocr_texts: list[str] = []
        if domestic.detail_images:
            ocr_results = await self._ocr_all_images(domestic.detail_images)
            ocr_texts = [r["original_text"] for r in ocr_results]
            logger.info(f"이미지 OCR 완료: {len(ocr_texts)}개 텍스트 수집")

        # 2. 제목+키워드
        if do_en:
            en_title, en_keywords = await self._translate_title_and_keywords(
                domestic.title, domestic.keywords, "en",
            )
            logger.info("EN 제목+키워드 완료")

        if do_ja:
            ja_title, ja_keywords = await self._translate_title_and_keywords(
                domestic.title, domestic.keywords, "ja",
            )
            logger.info("JA 제목+키워드 완료")

        # 3. AI 상세 설명 재구성 (KR 텍스트 + OCR 텍스트 → 새 GB 설명)
        if do_en:
            en_desc = await self._build_gb_description(
                domestic, ocr_texts, "en",
            )
            logger.info("EN 설명 재구성 완료")

        if do_ja:
            ja_desc = await self._build_gb_description(
                domestic, ocr_texts, "ja",
            )
            logger.info("JA 설명 재구성 완료")

        # 4. LanguageData 조립
        if do_en:
            en_data = LanguageData(
                title=en_title[:settings.title_max_length_global],
                description_html=en_desc,
                keywords=en_keywords,
                use_domestic_images=True,
            )
        if do_ja:
            ja_data = LanguageData(
                title=ja_title[:settings.title_max_length_global],
                description_html=ja_desc,
                keywords=ja_keywords,
                use_domestic_images=True,
            )

        # 5. 옵션 번역
        if domestic.options:
            global_options = await self._translate_options(
                domestic.options, target_languages,
            )
            logger.info(f"옵션 번역 완료: {len(global_options)}개")

        result = GlobalProductData(
            source_product_id=domestic.product_id,
            en=en_data,
            ja=ja_data,
            global_options=global_options,
        )

        logger.info(f"GB 번역 완료: {domestic.product_id}")
        return result

    # ──────────────── Private: 언어별 번역 ────────────────

    async def _translate_language(
        self,
        domestic: DomesticProduct,
        language: str,
    ) -> LanguageData:
        """특정 언어로 전체 필드 번역"""

        # 1. 작품명 번역 (80자 제한)
        title = await self._translate_title(domestic.title, language)
        if len(title) > settings.title_max_length_global:
            title = title[:settings.title_max_length_global]

        # 2. 작품 설명 번역 (HTML 구조 유지)
        description_html = await self._translate_description(
            domestic.description_html, language,
        )

        # 3. 키워드 번역
        keywords = await self._translate_keywords(domestic.keywords, language)

        return LanguageData(
            title=title,
            description_html=description_html,
            keywords=keywords,
            use_domestic_images=True,
        )

    async def _translate_title_and_keywords(
        self,
        title: str,
        keywords: list[str],
        language: str,
    ) -> tuple[str, list[str]]:
        """제목과 키워드를 1회 API 호출로 동시 번역 (6.5초 절약)"""
        if not title and not keywords:
            return title or "", keywords or []

        title_prompt = (
            GB_TITLE_PROMPT_EN if language == "en"
            else GB_TITLE_PROMPT_JA
        )
        keyword_prompt = (
            GB_KEYWORD_PROMPT_EN if language == "en"
            else GB_KEYWORD_PROMPT_JA
        )

        combined_prompt = (
            f"다음 두 가지를 번역해주세요. 반드시 ---구분선--- 으로 구분하여 응답하세요.\n\n"
            f"[파트1: 제목 번역]\n"
            f"{title_prompt.format(text=title)}\n\n"
            f"---구분선---\n\n"
            f"[파트2: 키워드 번역]\n"
            f"{keyword_prompt.format(text=chr(10).join(keywords))}"
        )

        result = await self._call_gemini(combined_prompt, max_tokens=4000)

        if result and "---" in result:
            parts = result.split("---")
            # 구분선 전후로 분리
            title_part = parts[0].strip().strip('"').strip("'").strip()
            keyword_part = parts[-1].strip() if len(parts) > 1 else ""

            # 제목: 첫 줄 or 전체 (짧은 텍스트)
            translated_title = title_part.split("\n")[0].strip().strip('"').strip("'")
            if not translated_title:
                translated_title = title

            # 키워드: 줄바꿈 구분
            translated_keywords = [
                kw.strip() for kw in keyword_part.split("\n")
                if kw.strip()
            ] if keyword_part else keywords

            if translated_keywords and len(translated_keywords) <= len(keywords) * 2:
                return translated_title, translated_keywords
            return translated_title, keywords

        # 합쳐서 번역 실패 시 개별 호출 폴백
        logger.warning(f"합친 번역 실패, 개별 호출로 폴백 ({language})")
        translated_title = await self._translate_title(title, language)
        translated_keywords = await self._translate_keywords(keywords, language)
        return translated_title, translated_keywords

    async def _translate_title(self, title: str, language: str) -> str:
        """작품명 번역 — GB 전용 프롬프트 사용"""
        if not title or not title.strip():
            return title

        prompt_template = (
            GB_TITLE_PROMPT_EN if language == "en"
            else GB_TITLE_PROMPT_JA
        )
        prompt = prompt_template.format(text=title)

        result = await self._call_gemini(prompt)
        if result:
            result = result.strip().strip('"').strip("'")
            return result
        return title

    async def _build_gb_description(
        self,
        domestic: DomesticProduct,
        ocr_texts: list[str],
        language: str,
    ) -> str:
        """KR 데이터 전체를 기반으로 GB 최적화 상세 설명을 AI로 재구성

        이미지는 포함하지 않음 (텍스트 중심, SEO 최적화)
        """
        # 모든 KR 텍스트를 수집
        parts = []
        parts.append(f"제목: {domestic.title}")
        parts.append(f"카테고리: {domestic.category_path}")
        if domestic.keywords:
            parts.append(f"키워드: {', '.join(domestic.keywords)}")
        if domestic.intro:
            parts.append(f"한줄소개: {domestic.intro}")
        if domestic.features:
            parts.append(f"특장점: {' / '.join(domestic.features)}")
        if domestic.description_html:
            # HTML 태그 제거하여 순수 텍스트만
            import re
            clean_text = re.sub(r'<[^>]+>', ' ', domestic.description_html)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            if clean_text:
                parts.append(f"설명: {clean_text[:500]}")
        if domestic.options:
            for opt in domestic.options:
                vals = [v.value for v in opt.values]
                parts.append(f"옵션 [{opt.name}]: {', '.join(vals)}")
        for i, text in enumerate(ocr_texts[:10]):
            parts.append(f"이미지텍스트{i+1}: {text[:200]}")

        combined = "\n".join(parts)

        prompt_template = (
            GB_DESCRIPTION_REBUILD_PROMPT_EN if language == "en"
            else GB_DESCRIPTION_REBUILD_PROMPT_JA
        )
        prompt = prompt_template.format(text=combined)

        result = await self._call_gemini(prompt, max_tokens=8000)
        if result:
            return result
        return f"<p>{domestic.title}</p>"

    async def _translate_description(self, html: str, language: str) -> str:
        """작품 설명 HTML 번역 — HTML 태그 보존"""
        if not html or html.strip() == "":
            return ""

        prompt_template = (
            GB_DESCRIPTION_PROMPT_EN if language == "en"
            else GB_DESCRIPTION_PROMPT_JA
        )
        prompt = prompt_template.format(text=html)

        result = await self._call_gemini(prompt, max_tokens=8000)
        return result if result else html

    async def _translate_keywords(
        self,
        keywords: list[str],
        language: str,
    ) -> list[str]:
        """키워드 목록 번역"""
        if not keywords:
            return []

        prompt_template = (
            GB_KEYWORD_PROMPT_EN if language == "en"
            else GB_KEYWORD_PROMPT_JA
        )
        text = "\n".join(keywords)
        prompt = prompt_template.format(text=text)

        result = await self._call_gemini(prompt)
        if result:
            translated = [
                kw.strip() for kw in result.strip().split("\n")
                if kw.strip()
            ]
            # 키워드 수가 원본과 크게 다르면 원본 반환
            if translated and len(translated) <= len(keywords) * 2:
                return translated
        return keywords

    # ──────────────── Private: 옵션 번역 ────────────────

    async def _translate_options(
        self,
        options: list[DomesticOption],
        languages: list[str],
    ) -> list[GlobalOption]:
        """옵션 번역 (영어/일본어 동시)"""
        result = []

        for option in options:
            original_values = [v.value for v in option.values]

            global_opt = GlobalOption(
                original_name=option.name,
                original_values=original_values,
                option_type=option.option_type,
            )

            # 옵션명 번역
            if "en" in languages:
                global_opt.name_en = await self._translate_single_text(
                    option.name, "en",
                )
            if "ja" in languages:
                global_opt.name_ja = await self._translate_single_text(
                    option.name, "ja",
                )

            # 옵션값 번역 (배치)
            if "en" in languages:
                global_opt.values_en = await self._translate_option_values(
                    original_values, "en",
                )
            if "ja" in languages:
                global_opt.values_ja = await self._translate_option_values(
                    original_values, "ja",
                )

            result.append(global_opt)

        return result

    async def _translate_single_text(self, text: str, language: str) -> str:
        """단일 텍스트(옵션명 등) 간단 번역"""
        if not text or not text.strip():
            return text

        prompt_template = (
            GB_TITLE_PROMPT_EN if language == "en"
            else GB_TITLE_PROMPT_JA
        )
        prompt = prompt_template.format(text=text)
        result = await self._call_gemini(prompt)
        if result:
            return result.strip().strip('"').strip("'")
        return text

    async def _translate_option_values(
        self,
        values: list[str],
        language: str,
    ) -> list[str]:
        """옵션값 목록 배치 번역"""
        if not values:
            return []

        prompt_template = (
            GB_OPTION_PROMPT_EN if language == "en"
            else GB_OPTION_PROMPT_JA
        )
        text = "\n".join(values)
        prompt = prompt_template.format(text=text)

        result = await self._call_gemini(prompt)
        if result:
            translated = [v.strip() for v in result.strip().split("\n") if v.strip()]
            # 개수가 일치하는지 확인
            if len(translated) == len(values):
                return translated
            # 근사 매칭 허용 (±1)
            if abs(len(translated) - len(values)) <= 1:
                return translated[:len(values)]
        return values

    # ──────────────── Private: 이미지 OCR + 번역 + 생성 ────────────────

    @staticmethod
    def _get_high_res_url(url: str) -> str:
        """이미지 URL을 고해상도(_1000)로 변환"""
        if not url:
            return url
        # 이미 접미사가 있으면 교체, 없으면 추가
        import re
        base = re.sub(r'_\d+\.(jpg|jpeg|png|webp|gif)$', r'.\1', url)
        # 확장자 앞에 _1000 삽입
        return re.sub(r'\.(jpg|jpeg|png|webp|gif)$', r'_1000.\1', base)

    async def _download_image(self, url: str) -> tuple[Optional[bytes], str]:
        """이미지 다운로드 + MIME 타입 반환"""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None, ""
                ct = resp.headers.get("content-type", "").lower()
                mime = "image/jpeg"
                if "png" in ct:
                    mime = "image/png"
                elif "webp" in ct:
                    mime = "image/webp"
                elif "gif" in ct:
                    mime = "image/gif"
                return resp.content, mime
        except Exception as e:
            logger.warning(f"이미지 다운로드 실패: {e}")
            return None, ""

    async def _ocr_all_images(
        self, images: list,
    ) -> list[dict]:
        """모든 이미지에서 한국어 텍스트를 1회만 추출 (언어 무관)

        Returns:
            [{"image_url": str, "original_text": str, "order_index": int,
              "image_data": bytes, "mime": str}, ...]
        """
        MAX_OCR_IMAGES = int(os.getenv("MAX_OCR_IMAGES", "10"))
        results = []

        target_images = images[:MAX_OCR_IMAGES]
        logger.info(f"이미지 OCR 시작: {len(target_images)}개 처리")

        for idx, img in enumerate(target_images):
            raw_url = img.url
            high_res_url = self._get_high_res_url(raw_url)

            try:
                await self.translator._wait_for_rate_limit()

                # 고해상도 이미지 다운로드
                image_data, mime = await self._download_image(high_res_url)
                if not image_data:
                    # 고해상도 실패 시 원본 URL 시도
                    image_data, mime = await self._download_image(raw_url)
                if not image_data:
                    continue

                from google.genai import types

                image_part = types.Part.from_bytes(
                    data=image_data, mime_type=mime,
                )

                # 개선된 OCR 프롬프트
                response = self.translator.client.models.generate_content(
                    model=self.translator._model_name,
                    contents=[
                        "이 이미지를 분석하세요.\n"
                        "1. 이미지에 포함된 모든 한국어 텍스트를 추출하세요.\n"
                        "2. 영어 텍스트도 있다면 함께 추출하세요.\n"
                        "3. 텍스트가 전혀 없으면 NO_TEXT만 응답하세요.\n\n"
                        "추출된 텍스트만 줄바꿈으로 구분하여 응답하세요. "
                        "설명이나 부가 정보는 필요 없습니다.",
                        image_part,
                    ],
                )

                if response and response.text:
                    text = response.text.strip()
                    if text != "NO_TEXT" and len(text) >= 3:
                        logger.info(f"  [{idx+1}] OCR 텍스트: {text[:50]}...")
                        results.append({
                            "image_url": raw_url,
                            "original_text": text,
                            "order_index": idx,
                            "image_data": image_data,
                            "mime": mime,
                        })
                    else:
                        logger.debug(f"  [{idx+1}] 텍스트 없음")
                else:
                    logger.debug(f"  [{idx+1}] OCR 응답 없음")

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    logger.warning(f"  [{idx+1}] Rate limit, 12초 대기 후 스킵")
                    await asyncio.sleep(12)
                else:
                    logger.warning(f"  [{idx+1}] OCR 오류: {e}")

        logger.info(f"OCR 완료: {len(results)}/{len(target_images)}개 텍스트 발견")
        return results

    # (이미지 생성 메서드 제거됨 — GB는 텍스트 중심 상세 설명 사용)

    # ──────────────── Private: Gemini API 호출 ────────────────

    async def _call_gemini(
        self,
        prompt: str,
        max_tokens: int = 4000,
    ) -> Optional[str]:
        """
        Gemini API 호출 (rate limiting + retry 포함)

        기존 ProductTranslator의 클라이언트를 직접 사용합니다.
        """
        if not self.translator._initialized:
            logger.error("Gemini 클라이언트가 초기화되지 않았습니다")
            return None

        for attempt in range(settings.translation_max_retries):
            try:
                await self.translator._wait_for_rate_limit()

                from google.genai import types

                response = self.translator.client.models.generate_content(
                    model=self.translator._model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=max_tokens,
                    ),
                )

                if response and response.text:
                    return response.text.strip()

                logger.warning(f"Gemini 응답 비어있음 (attempt {attempt + 1})")
                return None

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    wait_time = (attempt + 1) * 12
                    logger.warning(
                        f"Rate limit 초과, {wait_time}초 대기 후 재시도 "
                        f"(attempt {attempt + 1}/{settings.translation_max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Gemini API 호출 실패: {e}")
                    return None

        logger.error(f"Gemini API 호출 최대 재시도 초과")
        return None
