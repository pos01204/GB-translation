"""
Google Gemini 기반 번역 및 OCR 모듈
새로운 google-genai 라이브러리 사용 + Rate Limiting
전문 프롬프트 템플릿 시스템 적용
"""
import asyncio
import base64
import httpx
import os
import traceback
from typing import Optional

# 새로운 google-genai 라이브러리
from google import genai
from google.genai import types

from .models import (
    ProductData,
    ProductOption,
    ImageText,
    TranslatedProduct,
    TargetLanguage,
)

# 전문 번역 프롬프트 템플릿
from .prompts import (
    JAPANESE_PROMPT,
    JAPANESE_TITLE_PROMPT,
    JAPANESE_OPTION_PROMPT,
    ENGLISH_PROMPT,
    ENGLISH_TITLE_PROMPT,
    ENGLISH_OPTION_PROMPT,
)


class ProductTranslator:
    """Google Gemini를 사용한 상품 번역기 (Rate Limiting 적용)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.client = None
        self._initialized = False
        self._model_name = None
        
        # Rate Limiting 설정
        self._request_delay = 6.5  # 초 (분당 10회 = 6초 간격, 여유분 추가)
        self._last_request_time = 0
        self._max_retries = 3
        
        if api_key:
            self._initialize_client(api_key)
        else:
            print("⚠️ GEMINI_API_KEY가 설정되지 않았습니다")
    
    def _initialize_client(self, api_key: str):
        """Gemini 클라이언트 초기화"""
        try:
            print(f"🔧 Gemini API 초기화 중... (키 길이: {len(api_key)})")
            
            self.client = genai.Client(api_key=api_key)
            
            # 모델 우선순위 (최신 모델 우선)
            model_candidates = [
                "gemini-2.5-flash-preview-05-20",  # 최신 권장
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-2.0-flash-exp", 
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-pro",
            ]
            
            api_key_leaked = False
            
            for model_name in model_candidates:
                try:
                    print(f"🔄 모델 시도: {model_name}")
                    
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents="Say OK"
                    )
                    
                    if response and response.text:
                        self._model_name = model_name
                        self._initialized = True
                        print(f"✅ 모델 선택 성공: {model_name}")
                        return
                        
                except Exception as e:
                    error_str = str(e)
                    if "leaked" in error_str.lower() or "PERMISSION_DENIED" in error_str:
                        print(f"   ⛔ API 키 차단됨! 새 API 키가 필요합니다.")
                        api_key_leaked = True
                        break  # 더 이상 시도하지 않음
                    elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        print(f"   ⚠️ {model_name}: Quota 초과 - 다음 모델 시도")
                    elif "404" in error_str or "not found" in error_str.lower():
                        print(f"   ⚠️ {model_name}: 사용 불가")
                    else:
                        print(f"   ⚠️ {model_name}: {str(e)[:100]}")
                    continue
            
            if api_key_leaked:
                print("="*60)
                print("⛔ API 키가 유출로 보고되어 차단되었습니다!")
                print("   새 API 키를 생성하세요: https://aistudio.google.com/apikey")
                print("   Railway 환경 변수 GEMINI_API_KEY를 업데이트하세요.")
                print("="*60)
            else:
                print("❌ 사용 가능한 모델을 찾을 수 없습니다")
            
        except Exception as e:
            print(f"❌ Gemini 초기화 실패: {e}")
            traceback.print_exc()
    
    async def _wait_for_rate_limit(self):
        """Rate Limit을 위한 대기"""
        import time
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        
        if elapsed < self._request_delay:
            wait_time = self._request_delay - elapsed
            print(f"   ⏳ Rate Limit 대기: {wait_time:.1f}초")
            await asyncio.sleep(wait_time)
        
        self._last_request_time = time.time()
    
    def _prioritize_high_res_images(self, images: list[str]) -> list[str]:
        """고해상도 이미지를 우선 정렬 (OCR 품질 향상)"""
        import re
        
        high_res = []  # _720, _800, _1000 등
        normal = []
        
        for img in images:
            low = img.lower()
            # 고해상도 패턴 확인
            if re.search(r'_([5-9]\d{2}|[1-9]\d{3})\.', low):  # _500 이상
                high_res.append(img)
            elif re.search(r'/([5-9]\d{2}|[1-9]\d{3})/', low):  # /500/ 이상
                high_res.append(img)
            else:
                normal.append(img)
        
        # 고해상도 이미지 먼저, 그 다음 일반 이미지
        return high_res + normal
    
    def _get_language_name(self, lang: TargetLanguage) -> str:
        return {
            TargetLanguage.ENGLISH: "English",
            TargetLanguage.JAPANESE: "Japanese",
        }.get(lang, "English")
    
    def _get_prompt(self, text: str, target_language: TargetLanguage, context: str = "") -> str:
        """컨텍스트에 맞는 프롬프트 선택"""
        
        if target_language == TargetLanguage.JAPANESE:
            if context == "title":
                return JAPANESE_TITLE_PROMPT.format(text=text)
            elif context == "option":
                return JAPANESE_OPTION_PROMPT.format(text=text)
            else:
                return JAPANESE_PROMPT.format(text=text)
        else:  # English
            if context == "title":
                return ENGLISH_TITLE_PROMPT.format(text=text)
            elif context == "option":
                return ENGLISH_OPTION_PROMPT.format(text=text)
            else:
                return ENGLISH_PROMPT.format(text=text)
    
    async def translate_product(
        self,
        product_data: ProductData,
        target_language: TargetLanguage
    ) -> TranslatedProduct:
        """상품 데이터 전체 번역"""
        
        print(f"\n{'='*50}")
        print(f"🔄 번역 시작 (모델: {self._model_name}, 초기화: {self._initialized})")
        print(f"{'='*50}")
        
        if not self._initialized or not self.client:
            print("⚠️ 모델 미초기화 - 원본 데이터 반환")
            return TranslatedProduct(
                original=product_data,
                translated_title=product_data.title,
                translated_description=product_data.description,
                translated_options=product_data.options,
                translated_image_texts=[],
                target_language=target_language
            )
        
        # 1. 제목 번역 (간결한 프롬프트 사용)
        print(f"📝 제목 번역: {product_data.title[:30]}...")
        translated_title = await self._translate_text_with_retry(
            product_data.title, target_language, "title"
        )
        
        # 2. 설명 번역 (전문 프롬프트 사용)
        print(f"📝 설명 번역: {len(product_data.description)}자")
        translated_description = await self._translate_text_with_retry(
            product_data.description, target_language, "description"
        )
        
        # 3. 옵션 번역
        print(f"📝 옵션 번역: {len(product_data.options)}개")
        translated_options = await self._translate_options(
            product_data.options, target_language
        )
        
        # 4. OCR (고해상도 이미지 우선, Rate Limit 고려)
        max_ocr = int(os.getenv("MAX_OCR_IMAGES", "10"))  # 기본값 10개 (Rate Limit 대응)
        
        # 고해상도 이미지 우선 정렬 (_720, _800 등)
        sorted_images = self._prioritize_high_res_images(product_data.detail_images)
        
        print(f"📝 OCR: {len(sorted_images)}개 이미지 중 최대 {max_ocr}개 처리")
        translated_image_texts = await self._process_images(
            sorted_images[:max_ocr], target_language
        )
        
        print(f"✅ 번역 완료!")
        
        return TranslatedProduct(
            original=product_data,
            translated_title=translated_title,
            translated_description=translated_description,
            translated_options=translated_options,
            translated_image_texts=translated_image_texts,
            target_language=target_language
        )
    
    async def _translate_text_with_retry(
        self, text: str, target_language: TargetLanguage, context: str = ""
    ) -> str:
        """Rate Limit과 재시도를 포함한 번역"""
        if not text or not text.strip():
            return text
        if text in ["제목 없음", "설명 없음", "가격 정보 없음", "작가명 없음"]:
            return text
        
        for attempt in range(self._max_retries):
            try:
                await self._wait_for_rate_limit()
                return self._translate_text(text, target_language, context)
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    # 429 에러: 더 오래 대기
                    wait_time = (attempt + 1) * 12  # 12초, 24초, 36초
                    print(f"   ⏳ Rate Limit 초과, {wait_time}초 대기 후 재시도...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"   ❌ 번역 실패: {e}")
                    return text
        
        return text
    
    def _translate_text(self, text: str, target_language: TargetLanguage, context: str = "") -> str:
        """텍스트 번역 (전문 프롬프트 사용)"""
        
        # 컨텍스트에 맞는 프롬프트 선택
        prompt = self._get_prompt(text, target_language, context)
        
        # 설명 번역은 더 긴 출력 허용
        max_tokens = 8000 if context == "description" else 4000
        
        response = self.client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,  # 약간 높여서 자연스러운 표현 유도
                max_output_tokens=max_tokens,
            )
        )
        
        if response and response.text:
            result = response.text.strip()
            
            # 불필요한 프리픽스 제거
            lang = self._get_language_name(target_language)
            prefixes_to_remove = [
                f"{lang}:", f"{lang} Translation:", "Translation:", 
                "번역:", "Japanese:", "English:",
                "Japanese Translation:", "English Translation:"
            ]
            for prefix in prefixes_to_remove:
                if result.startswith(prefix):
                    result = result[len(prefix):].strip()
            
            print(f"   ✅ 번역 성공 ({context})")
            return result
        
        return text
    
    async def _translate_options(
        self, options: list[ProductOption], target_language: TargetLanguage
    ) -> list[ProductOption]:
        """옵션 번역 (간결한 프롬프트 사용)"""
        result = []
        for opt in options:
            try:
                # 옵션명 번역
                name = await self._translate_text_with_retry(opt.name, target_language, "option")
                
                # 옵션값들 번역
                values = []
                for v in opt.values:
                    translated_v = await self._translate_text_with_retry(v, target_language, "option")
                    values.append(translated_v)
                    
                result.append(ProductOption(name=name, values=values))
            except Exception as e:
                print(f"   ❌ 옵션 번역 실패: {e}")
                result.append(opt)
        return result
    
    async def _process_images(
        self, image_urls: list[str], target_language: TargetLanguage
    ) -> list[ImageText]:
        """이미지 OCR (Rate Limit 적용, 순서 정보 포함)"""
        results = []
        
        for idx, url in enumerate(image_urls):
            try:
                print(f"   [{idx+1}/{len(image_urls)}] OCR: {url[:50]}...")
                
                # Rate Limit 대기
                await self._wait_for_rate_limit()
                
                # OCR with retry
                ocr_text = await self._ocr_image_with_retry(url)
                
                if ocr_text and len(ocr_text) > 10:
                    print(f"      ✅ 텍스트 발견: {len(ocr_text)}자")
                    
                    # 번역 (OCR 텍스트는 일반 번역 프롬프트 사용)
                    translated = await self._translate_text_with_retry(
                        ocr_text, target_language, "ocr"
                    )
                    
                    # 순서 정보 포함하여 저장
                    results.append(ImageText(
                        image_url=url,
                        original_text=ocr_text,
                        translated_text=translated,
                        order_index=idx,  # 페이지 순서 (이미 정렬된 상태)
                        y_position=float(idx * 100)  # 상대적 위치 (정렬용)
                    ))
                else:
                    print(f"      ⬜ 텍스트 없음")
                    
            except Exception as e:
                print(f"      ❌ OCR 오류: {e}")
        
        # 순서대로 정렬된 결과 반환
        results.sort(key=lambda x: x.order_index)
        print(f"   📊 OCR 결과: {len(results)}개 (순서 정렬됨)")
        
        return results
    
    async def _ocr_image_with_retry(self, image_url: str) -> Optional[str]:
        """재시도 로직이 포함된 OCR"""
        for attempt in range(self._max_retries):
            try:
                return await self._ocr_image(image_url)
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    wait_time = (attempt + 1) * 12
                    print(f"      ⏳ Rate Limit, {wait_time}초 대기...")
                    await asyncio.sleep(wait_time)
                else:
                    raise e
        return None
    
    async def _ocr_image(self, image_url: str) -> Optional[str]:
        """이미지 OCR"""
        if not self.client or not self._model_name:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(image_url)
                if resp.status_code != 200:
                    return None
                image_data = resp.content
            
            # MIME 타입
            ct = resp.headers.get("content-type", "").lower()
            mime = "image/jpeg"
            if "png" in ct: mime = "image/png"
            elif "webp" in ct: mime = "image/webp"
            elif "gif" in ct: mime = "image/gif"
            
            image_part = types.Part.from_bytes(
                data=image_data,
                mime_type=mime
            )
            
            response = self.client.models.generate_content(
                model=self._model_name,
                contents=[
                    "이 이미지에서 한국어 텍스트만 추출해주세요. 텍스트가 없으면 NO_TEXT만 응답하세요.",
                    image_part
                ]
            )
            
            if response and response.text:
                text = response.text.strip()
                if text == "NO_TEXT" or len(text) < 5:
                    return None
                return text
            
            return None
            
        except Exception as e:
            raise e
    
    async def translate_single_text(self, text: str, target_language: TargetLanguage) -> str:
        """단일 텍스트 번역 (외부 API용)"""
        return await self._translate_text_with_retry(text, target_language, "description")
