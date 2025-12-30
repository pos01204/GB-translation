"""
Google Gemini 기반 번역 및 OCR 모듈
새로운 google-genai 라이브러리 사용
"""
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


class ProductTranslator:
    """Google Gemini를 사용한 상품 번역기"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.client = None
        self._initialized = False
        self._model_name = None
        
        if api_key:
            self._initialize_client(api_key)
        else:
            print("⚠️ GEMINI_API_KEY가 설정되지 않았습니다")
    
    def _initialize_client(self, api_key: str):
        """Gemini 클라이언트 초기화"""
        try:
            print(f"🔧 Gemini API 초기화 중... (키 길이: {len(api_key)})")
            
            # 새로운 방식: Client 생성
            self.client = genai.Client(api_key=api_key)
            
            # 사용 가능한 모델 목록 확인 및 테스트
            model_candidates = [
                "gemini-2.0-flash",
                "gemini-2.0-flash-exp", 
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-pro",
            ]
            
            for model_name in model_candidates:
                try:
                    print(f"🔄 모델 시도: {model_name}")
                    
                    # 테스트 호출
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
                    if "404" in error_str or "not found" in error_str.lower():
                        print(f"   ⚠️ {model_name}: 사용 불가")
                    else:
                        print(f"   ⚠️ {model_name}: {e}")
                    continue
            
            print("❌ 사용 가능한 모델을 찾을 수 없습니다")
            
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
        
        # 1. 제목 번역
        print(f"📝 제목 번역: {product_data.title[:30]}...")
        translated_title = self._translate_text(
            product_data.title, target_language, "상품명"
        )
        
        # 2. 설명 번역
        print(f"📝 설명 번역: {len(product_data.description)}자")
        translated_description = self._translate_text(
            product_data.description, target_language, "상품 설명"
        )
        
        # 3. 옵션 번역
        print(f"📝 옵션 번역: {len(product_data.options)}개")
        translated_options = self._translate_options(
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
    
    def _translate_text(self, text: str, target_language: TargetLanguage, context: str = "") -> str:
        """텍스트 번역"""
        if not text or not text.strip():
            return text
        if text in ["제목 없음", "설명 없음", "가격 정보 없음", "작가명 없음"]:
            return text
        
        lang = self._get_language_name(target_language)
        
        prompt = f"""Translate this Korean text to {lang}. Output only the translation, nothing else.

Korean: {text}

{lang}:"""

        try:
            response = self.client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4000,
                )
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
    
    def _translate_options(
        self, options: list[ProductOption], target_language: TargetLanguage
    ) -> list[ProductOption]:
        """옵션 번역"""
        result = []
        for opt in options:
            try:
                name = self._translate_text(opt.name, target_language, "옵션명")
                values = [self._translate_text(v, target_language, "옵션값") for v in opt.values]
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
                    translated = self._translate_text(ocr_text, target_language, "이미지 텍스트")
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
            
            # 새로운 방식: Part 객체 사용
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
            print(f"      OCR 오류: {e}")
            return None
    
    async def translate_single_text(self, text: str, target_language: TargetLanguage) -> str:
        return self._translate_text(text, target_language, "텍스트")
