"""
작가웹 국내 탭 기반 작품 데이터 모델
artist.idus.com에서 추출한 데이터 구조
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class GlobalStatus(str, Enum):
    """글로벌 등록 상태"""
    NOT_REGISTERED = "not_registered"   # 미등록
    REGISTERED = "registered"           # 등록 (판매중)
    PAUSED = "paused"                   # 일시중지
    DRAFT = "draft"                     # 임시저장


class ProductStatus(str, Enum):
    """국내 작품 상태"""
    SELLING = "selling"                 # 판매중
    PAUSED = "paused"                   # 일시중지
    DRAFT = "draft"                     # 임시저장


class ProductImage(BaseModel):
    """작품 이미지"""
    url: str
    order: int = 0                              # 순서 (0 = 대표 이미지)
    is_representative: bool = False


class OptionValue(BaseModel):
    """옵션 값"""
    value: str
    additional_price: int = 0                   # 추가 금액 (원)
    stock: Optional[int] = None                 # 재고


class DomesticOption(BaseModel):
    """국내 작품 옵션"""
    name: str                                   # 옵션명 (예: 색상)
    values: list[OptionValue]
    option_type: str = "basic"                  # "basic" | "request"


class ProductSummary(BaseModel):
    """작품 목록에 표시할 요약 정보"""
    product_id: str                             # UUID
    title: str
    price: int
    thumbnail_url: Optional[str] = None
    status: ProductStatus
    global_status: GlobalStatus = GlobalStatus.NOT_REGISTERED
    global_languages: list[str] = []            # 등록된 언어 ["en", "ja"]


class DomesticProduct(BaseModel):
    """작가웹 국내 탭 전체 데이터"""
    product_id: str
    product_url: str

    # 기본 정보
    title: str = Field(max_length=100)
    price: int
    quantity: int = 0
    is_made_to_order: bool = False

    # 카테고리
    category_path: str = ""                     # "디지털/폰 케이스 > 스마트톡 > 기타"
    category_restricted: bool = False           # 글로벌 판매 제한 카테고리 여부

    # 이미지
    product_images: list[ProductImage] = []
    detail_images: list[ProductImage] = []       # 작품 설명 내 상세 이미지 (OCR 대상)

    # 상세 설명 영역
    intro: Optional[str] = None                 # 작품 인트로 (100자)
    features: list[str] = []                    # 특장점 (최대 5개)
    process_steps: list[str] = []               # 제작과정 (최대 6개)
    description_html: str = ""                  # 작품 설명 (HTML)
    gift_wrapping: bool = False                 # 선물 포장 제공

    # 옵션
    options: list[DomesticOption] = []

    # 키워드
    keywords: list[str] = []

    # 상태
    status: ProductStatus = ProductStatus.SELLING
    global_status: GlobalStatus = GlobalStatus.NOT_REGISTERED
