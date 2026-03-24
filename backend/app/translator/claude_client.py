"""
Claude API 기반 번역 클라이언트
Gemini 대체용 — rate limit 병목 제거
"""
import base64
import asyncio
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class ClaudeTranslator:
    """Claude API를 사용한 번역 엔진

    Anthropic Messages API를 사용합니다.
    Gemini 대비: rate limit 완화 (분당 50회+), 번역 품질 향상
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("anthropic 패키지가 필요합니다: pip install anthropic")
        self.model = model
        self._last_request_time = 0.0
        self._request_delay = 1.0  # Claude는 1초면 충분
        logger.info(f"Claude 번역기 초기화: 모델={model}")

    async def translate(self, prompt: str, max_tokens: int = 4000) -> str:
        """텍스트 번역 — Claude Messages API 호출"""
        await self._wait_for_rate_limit()

        try:
            # anthropic은 동기 라이브러리이므로 asyncio.to_thread 사용
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=max_tokens,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.content[0].text
            return result.strip()
        except Exception as e:
            logger.error(f"Claude 번역 실패: {e}")
            raise

    async def ocr_image(self, image_url: str, prompt: str) -> str:
        """이미지 OCR — Claude Vision API"""
        await self._wait_for_rate_limit()

        try:
            # 이미지 다운로드
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                image_bytes = resp.content

            # MIME 타입 추정
            content_type = resp.headers.get("content-type", "image/jpeg")
            if "png" in content_type:
                media_type = "image/png"
            elif "webp" in content_type:
                media_type = "image/webp"
            elif "gif" in content_type:
                media_type = "image/gif"
            else:
                media_type = "image/jpeg"

            image_b64 = base64.b64encode(image_bytes).decode()

            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Claude OCR 실패 ({image_url}): {e}")
            raise

    async def _wait_for_rate_limit(self):
        """요청 간격 유지 (Claude는 1초면 충분)"""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._request_delay:
            wait = self._request_delay - elapsed
            logger.debug(f"Rate limit 대기: {wait:.1f}초")
            await asyncio.sleep(wait)
        self._last_request_time = time.time()
