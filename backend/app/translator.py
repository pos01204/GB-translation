"""
Google Gemini 기반 번역 및 OCR 모듈
이미지 내 텍스트 추출 및 다국어 번역 수행
"""
import base64
import httpx
import os
import tempfile
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
        """
        Args:
            api_key: Google Gemini API 키
        """
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)
            # Gemini 2.0 Flash 모델 사용 (빠르고 비용 효율적)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            # Vision 기능이 필요한 경우 동일 모델 사용
            self.vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        else:
            self.model = None
            self.vision_model = None
        
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
        """
        상품 데이터 전체 번역
        
        Args:
            product_data: 크롤링된 상품 데이터
            target_language: 번역 대상 언어
            
        Returns:
            TranslatedProduct: 번역된 상품 데이터
        """
        if not self.model:
            raise RuntimeError("Gemini API 키가 설정되지 않았습니다.")
        
        lang_name = self._get_language_name(target_language)
        
        # 1. 텍스트 번역 (제목, 설명)
        translated_title = await self._translate_text(
            product_data.title,
            target_language,
            context="상품명"
        )
        
        translated_description = await self._translate_text(
            product_data.description,
            target_language,
            context="상품 설명"
        )
        
        # 2. 옵션 번역
        translated_options = await self._translate_options(
            product_data.options,
            target_language
        )
        
        # 3. 이미지 OCR 및 번역
        translated_image_texts = await self._process_images(
            product_data.detail_images,
            target_language
        )
        
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
        """
        텍스트 번역
        
        Args:
            text: 번역할 텍스트
            target_language: 대상 언어
            context: 문맥 정보 (예: "상품명", "설명")
        """
        if not text or text in ["제목 없음", "설명 없음", "가격 정보 없음"]:
            return text
            
        lang_name = self._get_language_name(target_language)
        
        prompt = f"""You are a professional translator specializing in e-commerce product translations.
Translate the following Korean text to {lang_name}.

Guidelines:
- Maintain the original tone and style
- Keep product-specific terminology accurate
- Preserve any measurements, sizes, or specifications
- Do not translate brand names or proper nouns
- For Japanese: Use polite form (です/ます)
- Keep the translation natural and fluent
- Only output the translated text, nothing else

Context: This is a {context} for a handmade product on an e-commerce platform.

Korean text to translate:
{text}"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=2000,
                )
            )
            
            return response.text.strip()
            
        except Exception as e:
            print(f"번역 오류: {e}")
            return text  # 오류 시 원문 반환
    
    async def _translate_options(
        self,
        options: list[ProductOption],
        target_language: TargetLanguage
    ) -> list[ProductOption]:
        """옵션 목록 번역"""
        translated_options = []
        
        for option in options:
            # 옵션명 번역
            translated_name = await self._translate_text(
                option.name,
                target_language,
                context="옵션 카테고리명"
            )
            
            # 옵션 값들 일괄 번역
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
        
        return translated_options
    
    async def _process_images(
        self,
        image_urls: list[str],
        target_language: TargetLanguage
    ) -> list[ImageText]:
        """
        이미지 OCR 및 번역
        Gemini Vision을 사용하여 이미지 내 텍스트 추출 후 번역
        """
        results = []
        lang_name = self._get_language_name(target_language)
        
        max_images = int(os.getenv("MAX_OCR_IMAGES", "20"))
        for url in image_urls[:max_images]:  # 기본 최대 20개 이미지만 처리
            try:
                # 이미지에서 텍스트 추출
                ocr_result = await self._extract_text_from_image(url)
                
                if ocr_result and ocr_result.strip():
                    # 추출된 텍스트 번역
                    translated = await self._translate_text(
                        ocr_result,
                        target_language,
                        context="상품 상세 이미지 내 텍스트"
                    )
                    
                    results.append(ImageText(
                        image_url=url,
                        original_text=ocr_result,
                        translated_text=translated
                    ))
                    
            except Exception as e:
                print(f"이미지 처리 오류 ({url}): {e}")
                continue
        
        return results
    
    async def _extract_text_from_image(self, image_url: str) -> Optional[str]:
        """
        Gemini Vision을 사용하여 이미지에서 텍스트 추출
        
        Args:
            image_url: 이미지 URL
            
        Returns:
            추출된 텍스트 또는 None
        """
        prompt = """You are an OCR specialist. Extract ALL Korean text visible in this product detail image.

Guidelines:
- Extract text exactly as it appears
- Include headings, descriptions, specifications, care instructions
- Preserve line breaks for readability
- If there's no text in the image, respond with "NO_TEXT"
- Do not describe the image, only extract the text

이 이미지에서 모든 한국어 텍스트를 추출해주세요."""

        try:
            if not self.vision_model:
                return None

            # 이미지 URL에서 이미지 데이터 가져오기
            async with httpx.AsyncClient(follow_redirects=True) as client:
                img_resp = await client.get(image_url, timeout=30.0)
                if img_resp.status_code != 200:
                    print(f"이미지 다운로드 실패({img_resp.status_code}): {image_url}")
                    return None
                image_data = img_resp.content

            # 이미지 MIME 타입 추정
            content_type = (img_resp.headers.get("content-type") or "").lower()
            if "png" in content_type:
                mime_type = "image/png"
                suffix = ".png"
            elif "gif" in content_type:
                mime_type = "image/gif"
                suffix = ".gif"
            elif "webp" in content_type:
                mime_type = "image/webp"
                suffix = ".webp"
            else:
                mime_type = "image/jpeg"
                suffix = ".jpg"

            # Gemini 이미지 파트 전달은 라이브러리 버전에 따라 포맷 차이가 있어
            # 가장 안정적인 방식인 "임시 파일 저장 -> genai.upload_file"로 처리합니다.
            uploaded = None
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                    f.write(image_data)
                    tmp_path = f.name

                uploaded = genai.upload_file(tmp_path, mime_type=mime_type)

                resp = await self.vision_model.generate_content_async(
                    [prompt, uploaded],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=2000,
                    ),
                )
                result = (resp.text or "").strip()
            finally:
                # 임시 파일 삭제
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
            
            # 텍스트가 없는 경우
            if result == "NO_TEXT" or len(result) < 5:
                return None
                
            return result
            
        except Exception as e:
            print(f"OCR 오류: {e}")
            return None
    
    async def translate_single_text(
        self,
        text: str,
        target_language: TargetLanguage
    ) -> str:
        """
        단일 텍스트 번역 (UI에서 개별 수정 시 사용)
        """
        return await self._translate_text(
            text,
            target_language,
            context="사용자 수정 텍스트"
        )


# 테스트용 코드
if __name__ == "__main__":
    import asyncio
    import os
    
    async def test():
        api_key = os.getenv("GEMINI_API_KEY")
        translator = ProductTranslator(api_key=api_key)
        
        # 테스트 데이터
        test_data = ProductData(
            url="https://example.com",
            title="수제 가죽 지갑",
            artist_name="가죽공방",
            price="45,000원",
            description="정성스럽게 만든 수제 가죽 지갑입니다. 이탈리아 베지터블 가죽을 사용했습니다.",
            options=[
                ProductOption(name="색상", values=["브라운", "블랙", "네이비"]),
                ProductOption(name="각인", values=["각인 없음", "이니셜 각인"])
            ],
            detail_images=[],
            image_texts=[]
        )
        
        result = await translator.translate_product(
            test_data,
            TargetLanguage.ENGLISH
        )
        
        print(f"원본 제목: {result.original.title}")
        print(f"번역 제목: {result.translated_title}")
        print(f"번역 설명: {result.translated_description}")
        print(f"번역 옵션: {result.translated_options}")
    
    asyncio.run(test())
