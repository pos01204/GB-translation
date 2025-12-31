"""
Pydantic 모델 정의
"""
from pydantic import BaseModel, HttpUrl
from typing import Optional
from enum import Enum


class TargetLanguage(str, Enum):
    """번역 대상 언어"""
    ENGLISH = "en"
    JAPANESE = "ja"


class ScrapeRequest(BaseModel):
    """크롤링 요청 모델"""
    url: str  # 아이디어스 상품 URL
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.idus.com/v2/product/12345678"
            }
        }


class ProductOption(BaseModel):
    """상품 옵션 모델"""
    name: str  # 옵션명 (예: 색상, 사이즈)
    values: list[str]  # 옵션 값들


class ImageText(BaseModel):
    """이미지 내 텍스트 모델 (순서 정보 포함)"""
    image_url: str
    original_text: str  # 추출된 원본 한국어 텍스트
    translated_text: Optional[str] = None  # 번역된 텍스트
    
    # 순서 및 위치 정보 (OCR 결과 정렬용)
    order_index: int = 0  # 페이지 내 순서 (0부터 시작)
    y_position: float = 0.0  # Y좌표 (정렬 기준)


class ProductData(BaseModel):
    """크롤링된 상품 데이터 모델"""
    url: str
    title: str  # 상품명
    artist_name: str  # 작가명
    price: str  # 가격
    description: str  # 상품 설명
    options: list[ProductOption]  # 옵션 목록
    detail_images: list[str]  # 상세 이미지 URL 목록
    image_texts: list[ImageText]  # 이미지 내 추출된 텍스트
    

class TranslateRequest(BaseModel):
    """번역 요청 모델"""
    product_data: ProductData
    target_language: TargetLanguage
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_data": {
                    "url": "https://www.idus.com/v2/product/12345678",
                    "title": "수제 가죽 지갑",
                    "artist_name": "가죽공방",
                    "price": "45,000원",
                    "description": "정성스럽게 만든 수제 가죽 지갑입니다.",
                    "options": [{"name": "색상", "values": ["브라운", "블랙"]}],
                    "detail_images": [],
                    "image_texts": []
                },
                "target_language": "en"
            }
        }


class TranslatedProduct(BaseModel):
    """번역된 상품 데이터 모델"""
    original: ProductData  # 원본 데이터
    translated_title: str
    translated_description: str
    translated_options: list[ProductOption]
    translated_image_texts: list[ImageText]
    target_language: TargetLanguage


class ScrapeResponse(BaseModel):
    """크롤링 응답 모델"""
    success: bool
    message: str
    data: Optional[ProductData] = None


class TranslateResponse(BaseModel):
    """번역 응답 모델"""
    success: bool
    message: str
    data: Optional[TranslatedProduct] = None


class HealthResponse(BaseModel):
    """헬스체크 응답 모델"""
    status: str
    version: str

