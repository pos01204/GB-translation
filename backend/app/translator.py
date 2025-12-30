"""
Google Gemini 기반 번역 및 OCR 모듈
이미지 내 텍스트 추출 및 다국어 번역 수행
"""
import base64
import httpx
import os
import asyncio
from typing import Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

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
        """
        Args:
            api_key: Google Gemini API 키
        """
        self.api_key = api_key
        self.model = None
        self.vision_model = None
        self._initialized = False
        
        if api_key:
            self._initialize_models(api_key)
        else:
            print("⚠️ GEMINI_API_KEY가 설정되지 않았습니다")
    
    def _initialize_models(self, api_key: str):
        """Gemini 모델 초기화"""
        try:
            genai.configure(api_key=api_key)
            
            # 안전 설정 (모든 콘텐츠 허용)
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            # gemini-1.5-flash 모델 사용
            model_name = 'gemini-1.5-flash'
            
            self.model = genai.GenerativeModel(
                model_name,
                safety_settings=safety_settings
            )
            self.vision_model = genai.GenerativeModel(
                model_name,
                safety_settings=safety_settings
            )
            
            self._initialized = True
            print(f"✅ Gemini 모델 초기화 성공: {model_name}")
            
        except Exception as e:
            print(f"❌ Gemini 모델 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
            self.model = None
            self.vision_model = None
            self._initialized = False
        
    def _get_language_name(self, lang: TargetLanguage) -> str:
        """언어 코드를 언어명으로 변환"""
        return {
            TargetLanguage.ENGLISH: "English",
            TargetLanguage.JAPANESE: "Japanese (日本語)",
        }.get(lang, "English")
    
    async def translate_product(
        self,
        product_data: ProductData,
        target_language: TargetLanguage
    ) -> TranslatedProduct:
        """상품 데이터 전체 번역"""
        
        print(f"🔄 번역 시작 - 모델 상태: initialized={self._initialized}, model={self.model is not None}")
        
        if not self._initialized or not self.model:
            print("❌ Gemini 모델이 초기화되지 않음 - 원본 데이터 반환")
            # 모델 없으면 원본 그대로 반환
            return TranslatedProduct(
                original=product_data,
                translated_title=product_data.title,
                translated_description=product_data.description,
                translated_options=product_data.options,
                translated_image_texts=[],
                target_language=target_language
            )
        
        lang_name = self._get_language_name(target_language)
        print(f"📝 번역 대상 언어: {lang_name}")
        
        # 1. 제목 번역
        print(f"📝 제목 번역 중: {product_data.title[:50]}...")
        translated_title = await self._translate_text(
            product_data.title,
            target_language,
            context="상품명"
        )
        print(f"   결과: {translated_title[:50]}...")
        
        # 2. 설명 번역
        print(f"📝 설명 번역 중: {product_data.description[:50]}...")
        translated_description = await self._translate_text(
            product_data.description,
            target_language,
            context="상품 설명"
        )
        print(f"   결과: {translated_description[:50]}...")
        
        # 3. 옵션 번역
        print(f"📝 옵션 번역 중: {len(product_data.options)}개 그룹")
        translated_options = await self._translate_options(
            product_data.options,
            target_language
        )
        
        # 4. 이미지 OCR 및 번역
        print(f"📝 이미지 OCR 시작: {len(product_data.detail_images)}개")
        translated_image_texts = await self._process_images(
            product_data.detail_images,
            target_language
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
    
    async def _translate_text(
        self,
        text: str,
        target_language: TargetLanguage,
        context: str = ""
    ) -> str:
        """텍스트 번역"""
        
        # 빈 텍스트나 기본값 처리
        if not text or text.strip() == "":
            return text
        if text in ["제목 없음", "설명 없음", "가격 정보 없음", "작가명 없음"]:
            return text
        
        lang_name = self._get_language_name(target_language)
        
        prompt = f"""Translate the following Korean text to {lang_name}.

IMPORTANT RULES:
- Output ONLY the translated text, nothing else
- Do not add explanations or notes
- Keep brand names and proper nouns in original form
- For Japanese: Use polite form (です/ます)
- Maintain formatting and line breaks

Context: {context}

Korean text:
{text}

{lang_name} translation:"""

        try:
            # 동기 API 사용 (더 안정적)
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=4000,
                )
            )
            
            if response and response.text:
                result = response.text.strip()
                # "Translation:" 등의 접두사 제거
                for prefix in ["Translation:", "English:", "Japanese:", "번역:"]:
                    if result.startswith(prefix):
                        result = result[len(prefix):].strip()
                return result
            else:
                print(f"⚠️ 번역 응답 없음 - 원문 반환")
                return text
                
        except Exception as e:
            print(f"❌ 번역 오류: {e}")
            import traceback
            traceback.print_exc()
            return text
    
    async def _translate_options(
        self,
        options: list[ProductOption],
        target_language: TargetLanguage
    ) -> list[ProductOption]:
        """옵션 목록 번역"""
        translated_options = []
        
        for option in options:
            try:
                # 옵션명 번역
                translated_name = await self._translate_text(
                    option.name,
                    target_language,
                    context="옵션 카테고리명"
                )
                
                # 옵션 값들 번역
                translated_values = []
                for value in option.values:
                    translated_value = await self._translate_text(
                        value,
                        target_language,
                        context="옵션 값"
                    )
                    translated_values.append(translated_value)
                
                translated_options.append(ProductOption(
                    name=translated_name,
                    values=translated_values
                ))
            except Exception as e:
                print(f"⚠️ 옵션 번역 오류: {e}")
                translated_options.append(option)
        
        return translated_options
    
    async def _process_images(
        self,
        image_urls: list[str],
        target_language: TargetLanguage
    ) -> list[ImageText]:
        """이미지 OCR 및 번역"""
        results = []
        
        max_images = int(os.getenv("MAX_OCR_IMAGES", "20"))
        images_to_process = image_urls[:max_images]
        
        print(f"🖼️ OCR 처리: {len(images_to_process)}개 이미지")
        
        for idx, url in enumerate(images_to_process):
            try:
                print(f"  [{idx+1}/{len(images_to_process)}] OCR: {url[:60]}...")
                
                ocr_result = await self._extract_text_from_image(url)
                
                if ocr_result and len(ocr_result) > 5:
                    print(f"    ✅ 텍스트 발견: {len(ocr_result)}자")
                    
                    translated = await self._translate_text(
                        ocr_result,
                        target_language,
                        context="이미지 내 텍스트"
                    )
                    
                    results.append(ImageText(
                        image_url=url,
                        original_text=ocr_result,
                        translated_text=translated
                    ))
                else:
                    print(f"    ⬜ 텍스트 없음")
                    
            except Exception as e:
                print(f"    ❌ 오류: {e}")
                continue
        
        print(f"🖼️ OCR 완료: {len(results)}개 텍스트 추출")
        return results
    
    async def _extract_text_from_image(self, image_url: str) -> Optional[str]:
        """이미지에서 텍스트 추출 (inline base64 방식)"""
        
        if not self.vision_model:
            return None
        
        try:
            # 이미지 다운로드
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(image_url)
                if response.status_code != 200:
                    print(f"    이미지 다운로드 실패: {response.status_code}")
                    return None
                image_data = response.content
            
            # MIME 타입 결정
            content_type = response.headers.get("content-type", "").lower()
            if "png" in content_type:
                mime_type = "image/png"
            elif "webp" in content_type:
                mime_type = "image/webp"
            elif "gif" in content_type:
                mime_type = "image/gif"
            else:
                mime_type = "image/jpeg"
            
            # Base64 인코딩 후 inline으로 전달 (upload_file보다 안정적)
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            prompt = """이 이미지에서 보이는 모든 한국어 텍스트를 추출해주세요.

규칙:
- 이미지에 있는 텍스트를 그대로 추출
- 제목, 설명, 포인트, 주의사항 등 모든 텍스트 포함
- 텍스트가 없는 순수 사진이면 "NO_TEXT" 만 응답
- 설명이나 해석 없이 텍스트만 출력"""

            # Gemini API에 inline image로 전달
            response = self.vision_model.generate_content([
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
            print(f"    OCR 오류: {e}")
            return None
    
    async def translate_single_text(
        self,
        text: str,
        target_language: TargetLanguage
    ) -> str:
        """단일 텍스트 번역"""
        return await self._translate_text(
            text,
            target_language,
            context="사용자 수정 텍스트"
        )
