"""
작가웹 글로벌 탭 등록 데이터 모델
"""
from pydantic import BaseModel, Field
from typing import Optional


class LanguageData(BaseModel):
    """언어별 글로벌 등록 데이터"""
    title: str = Field(max_length=80)           # 글로벌 작품명
    description_html: str = ""                  # 작품 설명 (HTML)
    keywords: list[str] = []                    # 작품 키워드
    use_domestic_images: bool = True            # 국내 이미지 불러오기 사용
    custom_image_urls: list[str] = []           # 별도 이미지 URL


class GlobalOption(BaseModel):
    """글로벌 옵션 (일본어/영어 공용)"""
    original_name: str                          # 원본 한국어 옵션명
    name_en: str = ""
    name_ja: str = ""
    original_values: list[str] = []             # 원본 한국어 옵션값
    values_en: list[str] = []
    values_ja: list[str] = []
    option_type: str = "basic"                  # "basic" | "request"


class GlobalProductData(BaseModel):
    """글로벌 탭 입력 데이터 (번역 결과물)"""
    source_product_id: str                      # 원본 국내 작품 UUID
    en: Optional[LanguageData] = None
    ja: Optional[LanguageData] = None
    global_options: list[GlobalOption] = []


class RegistrationResult(BaseModel):
    """GB 등록 실행 결과"""
    product_id: str
    success: bool
    languages_registered: list[str] = []        # 성공한 언어 ["en", "ja"]
    languages_failed: list[str] = []            # 실패한 언어
    error_message: Optional[str] = None
    saved_as_draft: bool = False                # 임시저장 여부
