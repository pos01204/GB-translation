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
    
    # 시도할 모델 이름 목록 (다양한 형식)
    MODEL_CANDIDATES = [
        'models/gemini-1.5-flash',
        'models/gemini-1.5-pro', 
        'models/gemini-pro',
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-pro',
        'models/gemini-1.0-pro',
        'gemini-1.0-pro',
    ]
    
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
        """Gemini 모델 초기화 - 여러 모델 이름 형식 시도"""
        try:
            print(f"🔧 Gemini API 초기화 중... (키 길이: {len(api_key)})")
            genai.configure(api_key=api_key)
            
            # 각 모델 후보를 시도
            for model_name in self.MODEL_CANDIDATES:
                try:
                    print(f"🔄 모델 시도: {model_name}")
                    test_model = genai.GenerativeModel(model_name)
                    
                    # 간단한 테스트 호출
                    test_response = test_model.generate_content(
                        "Say 'OK'",
                        generation_config={"max_output_tokens": 10}
                    )
                    
                    if test_response and test_response.text:
                        self._model_name = model_name
                        self.model = test_model
                        self.vision_model = genai.GenerativeModel(model_name)
                        self._initialized = True
                        print(f"✅ 모델 선택 성공: {model_name}")
                        return
                        
                except Exception as e:
                    error_msg = str(e)
                    if "404" in error_msg:
                        print(f"   ⚠️ {model_name}: 모델 없음")
                    elif "API_KEY" in error_msg or "401" in error_msg or "403" in error_msg:
                        print(f"   ❌ API 키 오류: {e}")
                        break  # API 키 문제면 다른 모델도 안됨
                    else:
                        print(f"   ⚠️ {model_name}: {e}")
                    continue
            
            if not self._initialized:
                print("❌ 사용 가능한 모델을 찾을 수 없습니다")
                print("   API 키를 확인해주세요: https://aistudio.google.com/app/apikey")
            
        except Exception as e:
            print(f"❌ Gemini 초기화 실패: {e}")
            traceback.print_exc()
    
    def _get_language_name(self, lang: TargetLanguage) -> str:
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
        print(f"🔄 번역 시작 (모델: {self._model_name}, 초기화: {self._initialized})")
        print(f"{'='*50}")
        
        # 모델이 초기화되지 않았으면 원본 반환
        if not self._initialized or not self.model:
            print("⚠️ 모델 미초기화 - 원본 데이터 반환")
            return TranslatedProduct(
                original=product_data,
                translated_title=product_data.title,
                translated_description=product_data.description,
                translated_options=product_data.options,
                translated_image_texts=[],
                target_language=target_language
            )
        
        # 1. 제목 번역
        print(f"📝 제목 번역: {product_data.title[:30]}...")
        translated_title = self._translate_sync(
            product_data.title, target_language, "상품명"
        )
        
        # 2. 설명 번역
        print(f"📝 설명 번역: {len(product_data.description)}자")
        translated_description = self._translate_sync(
            product_data.description, target_language, "상품 설명"
        )
        
        # 3. 옵션 번역
        print(f"📝 옵션 번역: {len(product_data.options)}개")
        translated_options = self._translate_options_sync(
            product_data.options, target_language
        )
        
        # 4. OCR
        print(f"📝 OCR: {len(product_data.detail_images)}개 이미지")
        translated_image_texts = await self._process_images(
            product_data.detail_images, target_language
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
    
    def _translate_sync(self, text: str, target_language: TargetLanguage, context: str = "") -> str:
        """동기 방식 텍스트 번역"""
        if not text or not text.strip():
            return text
        if text in ["제목 없음", "설명 없음", "가격 정보 없음", "작가명 없음"]:
            return text
        
        lang = self._get_language_name(target_language)
        
        prompt = f"""Translate this Korean text to {lang}. Output only the translation, nothing else.

Korean: {text}

{lang}:"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": 4000}
            )
            
            if response and response.text:
                result = response.text.strip()
                # 접두사 제거
                for prefix in [f"{lang}:", "Translation:", "번역:"]:
                    if result.startswith(prefix):
                        result = result[len(prefix):].strip()
                print(f"   ✅ 번역 성공")
                return result
            
            return text
            
        except Exception as e:
            print(f"   ❌ 번역 실패: {e}")
            return text
    
    def _translate_options_sync(
        self, options: list[ProductOption], target_language: TargetLanguage
    ) -> list[ProductOption]:
        """옵션 번역"""
        result = []
        for opt in options:
            try:
                name = self._translate_sync(opt.name, target_language, "옵션명")
                values = [self._translate_sync(v, target_language, "옵션값") for v in opt.values]
                result.append(ProductOption(name=name, values=values))
            except:
                result.append(opt)
        return result
    
    async def _process_images(
        self, image_urls: list[str], target_language: TargetLanguage
    ) -> list[ImageText]:
        """이미지 OCR"""
        results = []
        max_images = int(os.getenv("MAX_OCR_IMAGES", "10"))
        
        for idx, url in enumerate(image_urls[:max_images]):
            try:
                print(f"   [{idx+1}] OCR: {url[:50]}...")
                ocr_text = await self._ocr_image(url)
                
                if ocr_text and len(ocr_text) > 10:
                    print(f"      ✅ 텍스트 발견: {len(ocr_text)}자")
                    translated = self._translate_sync(ocr_text, target_language, "이미지 텍스트")
                    results.append(ImageText(
                        image_url=url,
                        original_text=ocr_text,
                        translated_text=translated
                    ))
                else:
                    print(f"      ⬜ 텍스트 없음")
            except Exception as e:
                print(f"      ❌ 오류: {e}")
        
        return results
    
    async def _ocr_image(self, image_url: str) -> Optional[str]:
        """이미지 OCR"""
        if not self.vision_model:
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
            
            b64 = base64.b64encode(image_data).decode()
            
            response = self.vision_model.generate_content([
                "이 이미지에서 한국어 텍스트만 추출해주세요. 텍스트가 없으면 NO_TEXT만 응답하세요.",
                {"mime_type": mime, "data": b64}
            ])
            
            if response and response.text:
                text = response.text.strip()
                if text == "NO_TEXT" or len(text) < 5:
                    return None
                return text
            
            return None
            
        except Exception as e:
            print(f"      OCR 오류: {e}")
            return None
    
    async def translate_single_text(self, text: str, target_language: TargetLanguage) -> str:
        return self._translate_sync(text, target_language, "텍스트")
