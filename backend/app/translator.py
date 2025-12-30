"""
Google Gemini 기반 번역 및 OCR 모듈
"""
import base64
import httpx
import os
import traceback
from typing import Optional
import google.generativeai as genai

from .models import (
    ProductData,
    ProductOption,
    ImageText,
    TranslatedProduct,
    TargetLanguage,
)


class ProductTranslator:
    """Google Gemini를 사용한 상품 번역기"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.model = None
        self.vision_model = None
        self._initialized = False
        self._model_name = None
        
        if api_key:
            self._initialize_models(api_key)
        else:
            print("⚠️ GEMINI_API_KEY가 설정되지 않았습니다")
    
    def _initialize_models(self, api_key: str):
        """Gemini 모델 초기화"""
        try:
            print(f"🔧 Gemini API 초기화 중... (키 길이: {len(api_key)})")
            genai.configure(api_key=api_key)
            
            # 사용 가능한 모델 목록 확인
            print("📋 사용 가능한 모델 확인 중...")
            available_models = []
            try:
                for model in genai.list_models():
                    if 'generateContent' in [m.name for m in model.supported_generation_methods]:
                        available_models.append(model.name)
                        print(f"   - {model.name}")
            except Exception as e:
                print(f"   모델 목록 조회 실패: {e}")
            
            # 모델 선택 (우선순위)
            model_candidates = [
                'gemini-pro',           # 가장 기본
                'gemini-1.0-pro',       # 1.0 버전
                'gemini-1.5-flash',     # 1.5 flash
                'gemini-1.5-pro',       # 1.5 pro
            ]
            
            self._model_name = None
            for candidate in model_candidates:
                try:
                    print(f"🔄 모델 시도: {candidate}")
                    test_model = genai.GenerativeModel(candidate)
                    # 간단한 테스트
                    test_response = test_model.generate_content("Hello")
                    if test_response:
                        self._model_name = candidate
                        self.model = test_model
                        self.vision_model = genai.GenerativeModel(candidate)
                        print(f"✅ 모델 선택됨: {candidate}")
                        break
                except Exception as e:
                    print(f"   ❌ {candidate} 실패: {e}")
                    continue
            
            if self._model_name:
                self._initialized = True
                print(f"✅ Gemini 모델 초기화 성공: {self._model_name}")
            else:
                print("❌ 사용 가능한 모델을 찾을 수 없습니다")
                self._initialized = False
            
        except Exception as e:
            print(f"❌ Gemini 모델 초기화 실패: {e}")
            traceback.print_exc()
            self._initialized = False
        
    def _get_language_name(self, lang: TargetLanguage) -> str:
        """언어 코드를 언어명으로 변환"""
        return {
            TargetLanguage.ENGLISH: "English",
            TargetLanguage.JAPANESE: "Japanese",
        }.get(lang, "English")
    
    async def translate_product(
        self,
        product_data: ProductData,
        target_language: TargetLanguage
    ) -> TranslatedProduct:
        """상품 데이터 전체 번역"""
        
        print(f"\n{'='*50}")
        print(f"🔄 번역 시작")
        print(f"   - 모델 초기화: {self._initialized}")
        print(f"   - 모델명: {self._model_name}")
        print(f"   - 대상 언어: {target_language.value}")
        print(f"{'='*50}")
        
        if not self._initialized or not self.model:
            print("❌ 모델이 초기화되지 않음 - 원본 반환")
            return TranslatedProduct(
                original=product_data,
                translated_title=product_data.title,
                translated_description=product_data.description,
                translated_options=product_data.options,
                translated_image_texts=[],
                target_language=target_language
            )
        
        # 1. 제목 번역
        print(f"\n📝 [1/4] 제목 번역")
        print(f"   원본: {product_data.title[:50]}...")
        translated_title = await self._translate_text_safe(
            product_data.title,
            target_language,
            "상품명"
        )
        print(f"   결과: {translated_title[:50]}...")
        
        # 2. 설명 번역
        print(f"\n📝 [2/4] 설명 번역")
        print(f"   원본 길이: {len(product_data.description)}자")
        translated_description = await self._translate_text_safe(
            product_data.description,
            target_language,
            "상품 설명"
        )
        print(f"   결과 길이: {len(translated_description)}자")
        
        # 3. 옵션 번역
        print(f"\n📝 [3/4] 옵션 번역: {len(product_data.options)}개 그룹")
        translated_options = await self._translate_options_safe(
            product_data.options,
            target_language
        )
        
        # 4. OCR
        print(f"\n📝 [4/4] 이미지 OCR: {len(product_data.detail_images)}개")
        translated_image_texts = await self._process_images_safe(
            product_data.detail_images,
            target_language
        )
        
        print(f"\n✅ 번역 완료!")
        print(f"{'='*50}\n")
        
        return TranslatedProduct(
            original=product_data,
            translated_title=translated_title,
            translated_description=translated_description,
            translated_options=translated_options,
            translated_image_texts=translated_image_texts,
            target_language=target_language
        )
    
    async def _translate_text_safe(
        self,
        text: str,
        target_language: TargetLanguage,
        context: str = ""
    ) -> str:
        """안전한 텍스트 번역 (에러 시 원문 반환)"""
        
        if not text or text.strip() == "":
            return text
        if text in ["제목 없음", "설명 없음", "가격 정보 없음", "작가명 없음"]:
            return text
        
        lang_name = self._get_language_name(target_language)
        
        prompt = f"""Translate the following Korean text to {lang_name}.

RULES:
- Output ONLY the translated text
- Do NOT add any explanations or notes
- Keep brand names unchanged
- For Japanese: use です/ます form

Context: {context}

Korean:
{text}

{lang_name}:"""

        try:
            print(f"      API 호출 중...")
            
            # generate_content_async 사용
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=4000,
                )
            )
            
            if response and response.text:
                result = response.text.strip()
                
                # 접두사 제거
                prefixes = ["Translation:", "English:", "Japanese:", "번역:", f"{lang_name}:"]
                for prefix in prefixes:
                    if result.startswith(prefix):
                        result = result[len(prefix):].strip()
                
                print(f"      ✅ 번역 성공")
                return result
            else:
                print(f"      ⚠️ 응답 없음")
                return text
                
        except Exception as e:
            print(f"      ❌ 번역 실패: {e}")
            traceback.print_exc()
            return text
    
    async def _translate_options_safe(
        self,
        options: list[ProductOption],
        target_language: TargetLanguage
    ) -> list[ProductOption]:
        """옵션 번역"""
        translated_options = []
        
        for i, option in enumerate(options):
            try:
                print(f"   옵션 {i+1}: {option.name}")
                
                translated_name = await self._translate_text_safe(
                    option.name,
                    target_language,
                    "옵션명"
                )
                
                translated_values = []
                for value in option.values:
                    translated_value = await self._translate_text_safe(
                        value,
                        target_language,
                        "옵션값"
                    )
                    translated_values.append(translated_value)
                
                translated_options.append(ProductOption(
                    name=translated_name,
                    values=translated_values
                ))
                
            except Exception as e:
                print(f"   ⚠️ 옵션 번역 실패: {e}")
                translated_options.append(option)
        
        return translated_options
    
    async def _process_images_safe(
        self,
        image_urls: list[str],
        target_language: TargetLanguage
    ) -> list[ImageText]:
        """이미지 OCR 및 번역"""
        results = []
        
        max_images = int(os.getenv("MAX_OCR_IMAGES", "15"))
        images_to_process = image_urls[:max_images]
        
        print(f"   처리할 이미지: {len(images_to_process)}개")
        
        for idx, url in enumerate(images_to_process):
            try:
                print(f"   [{idx+1}/{len(images_to_process)}] {url[:50]}...")
                
                ocr_result = await self._extract_text_from_image_safe(url)
                
                if ocr_result and len(ocr_result) > 10:
                    print(f"      ✅ 텍스트 발견: {len(ocr_result)}자")
                    
                    translated = await self._translate_text_safe(
                        ocr_result,
                        target_language,
                        "이미지 텍스트"
                    )
                    
                    results.append(ImageText(
                        image_url=url,
                        original_text=ocr_result,
                        translated_text=translated
                    ))
                else:
                    print(f"      ⬜ 텍스트 없음")
                    
            except Exception as e:
                print(f"      ❌ 오류: {e}")
                continue
        
        print(f"   OCR 결과: {len(results)}개 텍스트")
        return results
    
    async def _extract_text_from_image_safe(self, image_url: str) -> Optional[str]:
        """이미지에서 텍스트 추출"""
        
        if not self.vision_model:
            print(f"      ⚠️ Vision 모델 없음")
            return None
        
        try:
            # 이미지 다운로드
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(image_url)
                if response.status_code != 200:
                    print(f"      이미지 다운로드 실패: {response.status_code}")
                    return None
                image_data = response.content
            
            # MIME 타입
            content_type = response.headers.get("content-type", "").lower()
            if "png" in content_type:
                mime_type = "image/png"
            elif "webp" in content_type:
                mime_type = "image/webp"
            elif "gif" in content_type:
                mime_type = "image/gif"
            else:
                mime_type = "image/jpeg"
            
            # Base64 인코딩
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            prompt = """이 이미지에서 한국어 텍스트를 모두 추출해주세요.
텍스트가 없으면 "NO_TEXT"만 응답하세요.
설명 없이 텍스트만 출력하세요."""

            # Vision API 호출
            response = await self.vision_model.generate_content_async([
                prompt,
                {
                    "mime_type": mime_type,
                    "data": image_base64
                }
            ])
            
            if response and response.text:
                result = response.text.strip()
                if result == "NO_TEXT" or len(result) < 5:
                    return None
                return result
            
            return None
            
        except Exception as e:
            print(f"      OCR 오류: {e}")
            return None
    
    async def translate_single_text(
        self,
        text: str,
        target_language: TargetLanguage
    ) -> str:
        """단일 텍스트 번역"""
        return await self._translate_text_safe(text, target_language, "텍스트")
