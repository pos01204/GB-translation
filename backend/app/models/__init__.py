"""
데이터 모델 패키지

v1: 기존 소비자 페이지 크롤링용 모델 (하위 호환성 유지)
domestic: 작가웹 국내 탭 기반 모델
global_product: 작가웹 글로벌 탭 등록 모델
"""
# v1 모델 재export (기존 import 호환성 유지)
from .v1 import (
    TargetLanguage,
    ScrapeRequest,
    ScrapeResponse,
    ProductData,
    ProductOption,
    ImageText,
    TranslateRequest,
    TranslateResponse,
    TranslatedProduct,
    HealthResponse,
    BatchTranslateRequest,
    BatchTranslateResponse,
    BatchItemResult,
)

# v2 모델
from .domestic import (
    GlobalStatus,
    ProductStatus,
    ProductImage,
    OptionValue,
    DomesticOption,
    ProductSummary,
    DomesticProduct,
)

from .global_product import (
    LanguageData,
    GlobalOption,
    GlobalProductData,
    RegistrationResult,
)

__all__ = [
    # v1
    "TargetLanguage", "ScrapeRequest", "ScrapeResponse",
    "ProductData", "ProductOption", "ImageText",
    "TranslateRequest", "TranslateResponse", "TranslatedProduct",
    "HealthResponse", "BatchTranslateRequest", "BatchTranslateResponse", "BatchItemResult",
    # v2 - domestic
    "GlobalStatus", "ProductStatus", "ProductImage", "OptionValue",
    "DomesticOption", "ProductSummary", "DomesticProduct",
    # v2 - global
    "LanguageData", "GlobalOption", "GlobalProductData", "RegistrationResult",
]
