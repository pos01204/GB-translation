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
from typing import Optional

from ..models.domestic import DomesticProduct, DomesticOption
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..config import settings

from ..prompts import (
    GB_TITLE_PROMPT_EN, GB_DESCRIPTION_PROMPT_EN,
    GB_KEYWORD_PROMPT_EN, GB_OPTION_PROMPT_EN,
    GB_TITLE_PROMPT_JA, GB_DESCRIPTION_PROMPT_JA,
    GB_KEYWORD_PROMPT_JA, GB_OPTION_PROMPT_JA,
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

        # 언어별 번역
        if "en" in target_languages:
            en_data = await self._translate_language(domestic, "en")
            logger.info("영어 번역 완료")

        if "ja" in target_languages:
            ja_data = await self._translate_language(domestic, "ja")
            logger.info("일본어 번역 완료")

        # 옵션 번역 (영어/일본어 공용이므로 한 번에 처리)
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
            # 불필요한 따옴표 제거
            result = result.strip().strip('"').strip("'")
            return result
        return title

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
