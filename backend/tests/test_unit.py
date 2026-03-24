"""
Phase 5 — 단위 테스트
모델 생성/검증/직렬화, config 기본값, 유틸리티 로직 검증
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✓ {name}")
        passed += 1
    else:
        print(f"  ✗ {name} — {detail}")
        failed += 1


print("=" * 60)
print("Phase 5 단위 테스트")
print("=" * 60)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Config
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n[1] Config 기본값 검증")
from app.config import Settings

# .env를 무시하고 순수 기본값 검증
s = Settings(_env_file=None)
check("port 기본값", s.port == 8000)
check("debug 기본값", s.debug is False)
check("browser_headless 기본값", s.browser_headless is True)
check("browser_timeout 기본값", s.browser_timeout == 30000)
check("page_load_timeout 기본값", s.page_load_timeout == 60000)
check("artist_web_base_url", s.artist_web_base_url == "https://artist.idus.com")
check("translation_rate_limit_delay", s.translation_rate_limit_delay == 6.5)
check("translation_max_retries", s.translation_max_retries == 3)
check("title_max_length_global", s.title_max_length_global == 80)
check("batch_max_size", s.batch_max_size == 10)
check("batch_item_delay", s.batch_item_delay == 3.0)
check("cors_origins 기본값", s.cors_origins == ["*"])
check("gemini_api_key 기본값 None", s.gemini_api_key is None)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Domestic Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n[2] Domestic 모델 생성 + 직렬화")
from app.models.domestic import (
    DomesticProduct, ProductSummary, ProductImage,
    OptionValue, DomesticOption, GlobalStatus, ProductStatus,
)

# ProductImage
img = ProductImage(url="https://img.idus.com/test.jpg", order=0, is_representative=True)
check("ProductImage 생성", img.url == "https://img.idus.com/test.jpg")
d = img.model_dump()
check("ProductImage 직렬화", d["is_representative"] is True)

# OptionValue
ov = OptionValue(value="빨강", additional_price=1000, stock=5)
check("OptionValue 생성", ov.value == "빨강" and ov.additional_price == 1000)

# DomesticOption
do = DomesticOption(name="색상", values=[ov], option_type="basic")
check("DomesticOption 생성", do.name == "색상" and len(do.values) == 1)

# ProductSummary
ps = ProductSummary(
    product_id="uuid-1234", title="테스트 작품", price=25000,
    status=ProductStatus.SELLING,
    global_status=GlobalStatus.NOT_REGISTERED,
)
d = ps.model_dump()
check("ProductSummary 직렬화", d["product_id"] == "uuid-1234")
check("ProductSummary status enum", d["status"] == "selling")
check("ProductSummary global_languages 기본값", d["global_languages"] == [])

# DomesticProduct — 전체 필드
dp = DomesticProduct(
    product_id="7fda9710-76e4-4825-bcf4-ca94fd719f13",
    product_url="https://artist.idus.com/product/7fda9710",
    title="핸드메이드 폰케이스",
    price=35000,
    quantity=100,
    category_path="디지털/폰 케이스 > 스마트톡 > 기타",
    category_restricted=False,
    product_images=[img],
    intro="감성 가득한 핸드메이드",
    features=["수공예", "천연 소재"],
    description_html="<p>아름다운 작품입니다</p>",
    options=[do],
    keywords=["핸드메이드", "폰케이스"],
    gift_wrapping=True,
)
d = dp.model_dump()
check("DomesticProduct 전체 직렬화", d["product_id"] == "7fda9710-76e4-4825-bcf4-ca94fd719f13")
check("DomesticProduct images", len(d["product_images"]) == 1)
check("DomesticProduct options", len(d["options"]) == 1)
check("DomesticProduct keywords", d["keywords"] == ["핸드메이드", "폰케이스"])

# 역직렬화 (roundtrip)
dp2 = DomesticProduct.model_validate(d)
check("DomesticProduct 역직렬화", dp2.title == dp.title)
check("DomesticProduct roundtrip options", dp2.options[0].name == "색상")

# 카테고리 제한 플래그
dp_restricted = DomesticProduct(
    product_id="restricted-1", product_url="https://test",
    title="식품 테스트", price=10000,
    category_path="식품 > 과자", category_restricted=True,
)
check("category_restricted 플래그", dp_restricted.category_restricted is True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Global Product Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n[3] Global 모델 생성 + 검증")
from app.models.global_product import (
    LanguageData, GlobalOption, GlobalProductData, RegistrationResult,
)

# LanguageData — 80자 이내
ld = LanguageData(
    title="Handmade Phone Case - Premium Quality",
    description_html="<p>Beautiful handmade product</p>",
    keywords=["handmade", "phone case"],
)
check("LanguageData 생성", ld.title.startswith("Handmade"))
check("LanguageData use_domestic_images 기본값", ld.use_domestic_images is True)

# LanguageData — 80자 제한 검증
try:
    over80 = LanguageData(title="A" * 81, description_html="")
    check("LanguageData 80자 초과 → 에러", False, "에러가 발생해야 함")
except Exception:
    check("LanguageData 80자 초과 → 에러", True)

exactly80 = LanguageData(title="B" * 80, description_html="")
check("LanguageData 정확히 80자", len(exactly80.title) == 80)

# GlobalOption
go = GlobalOption(
    original_name="색상",
    name_en="Color", name_ja="カラー",
    original_values=["빨강", "파랑"],
    values_en=["Red", "Blue"],
    values_ja=["赤", "青"],
)
check("GlobalOption 생성", go.name_en == "Color" and go.name_ja == "カラー")
d = go.model_dump()
check("GlobalOption 직렬화", d["values_en"] == ["Red", "Blue"])

# GlobalProductData
gpd = GlobalProductData(
    source_product_id="uuid-test",
    en=ld,
    ja=LanguageData(
        title="ハンドメイドフォンケース",
        description_html="<p>美しい作品</p>",
        keywords=["ハンドメイド"],
    ),
    global_options=[go],
)
d = gpd.model_dump()
check("GlobalProductData 직렬화", d["source_product_id"] == "uuid-test")
check("GlobalProductData en/ja 존재", d["en"] is not None and d["ja"] is not None)
check("GlobalProductData global_options", len(d["global_options"]) == 1)

# GlobalProductData roundtrip
gpd2 = GlobalProductData.model_validate(d)
check("GlobalProductData roundtrip", gpd2.en.title == gpd.en.title)

# RegistrationResult
rr = RegistrationResult(
    product_id="uuid-test",
    success=True,
    languages_registered=["en", "ja"],
    saved_as_draft=True,
)
d = rr.model_dump()
check("RegistrationResult 직렬화", d["success"] is True)
check("RegistrationResult languages", d["languages_registered"] == ["en", "ja"])
check("RegistrationResult draft", d["saved_as_draft"] is True)
check("RegistrationResult error_message 기본값", d["error_message"] is None)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. V1 Models 하위 호환
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n[4] v1 모델 하위 호환")
from app.models import (
    ProductData, TranslatedProduct, ScrapeRequest, TargetLanguage,
)
check("v1 ProductData import", ProductData is not None)
check("v1 TranslatedProduct import", TranslatedProduct is not None)
check("v1 ScrapeRequest import", ScrapeRequest is not None)
check("v1 TargetLanguage import", TargetLanguage is not None)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. Prompts 존재 확인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n[5] GB 프롬프트 모듈")
from app.prompts import (
    GB_TITLE_PROMPT_EN, GB_DESCRIPTION_PROMPT_EN,
    GB_KEYWORD_PROMPT_EN, GB_OPTION_PROMPT_EN,
    GB_TITLE_PROMPT_JA, GB_DESCRIPTION_PROMPT_JA,
    GB_KEYWORD_PROMPT_JA, GB_OPTION_PROMPT_JA,
)
check("GB_TITLE_PROMPT_EN", "{text}" in GB_TITLE_PROMPT_EN)
check("GB_DESCRIPTION_PROMPT_EN", "{text}" in GB_DESCRIPTION_PROMPT_EN)
check("GB_KEYWORD_PROMPT_EN", "{text}" in GB_KEYWORD_PROMPT_EN)
check("GB_OPTION_PROMPT_EN", "{text}" in GB_OPTION_PROMPT_EN)
check("GB_TITLE_PROMPT_JA", "{text}" in GB_TITLE_PROMPT_JA)
check("GB_DESCRIPTION_PROMPT_JA", "{text}" in GB_DESCRIPTION_PROMPT_JA)
check("GB_KEYWORD_PROMPT_JA", "{text}" in GB_KEYWORD_PROMPT_JA)
check("GB_OPTION_PROMPT_JA", "{text}" in GB_OPTION_PROMPT_JA)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. GBProductTranslator 구조 확인 (초기화 없이)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n[6] GBProductTranslator 구조")
from app.translator.gb_translator import GBProductTranslator
check("GBProductTranslator import", True)
methods = [
    "translate_for_gb", "_translate_language", "_translate_title",
    "_translate_description", "_translate_keywords", "_translate_options",
    "_call_gemini",
]
for m in methods:
    check(f"  .{m}()", hasattr(GBProductTranslator, m))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. Services 구조 확인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n[7] Services 모듈 구조")
from app.services import (
    ArtistWebSession, ProductReader, ProductWriter,
    BatchProcessor, BatchItem, BatchProgress,
)
check("ArtistWebSession", hasattr(ArtistWebSession, "login"))
check("ProductReader", hasattr(ProductReader, "read_domestic_data"))
check("ProductWriter", hasattr(ProductWriter, "register_global_product"))
check("BatchProcessor", hasattr(BatchProcessor, "process_batch"))

# BatchItem defaults
bi = BatchItem(product_id="test")
check("BatchItem 기본 status", bi.status == "pending")
check("BatchItem error_message", bi.error_message is None)

# BatchProgress calculations
bp = BatchProgress(
    total=5, completed=3, failed=1,
    items=[
        BatchItem(product_id="a", status="completed"),
        BatchItem(product_id="b", status="completed"),
        BatchItem(product_id="c", status="completed"),
        BatchItem(product_id="d", status="failed", error_message="err"),
        BatchItem(product_id="e", status="pending"),
    ],
)
check("BatchProgress.is_done", bp.is_done is False)  # 5 != 3+1
bp2 = BatchProgress(total=4, completed=3, failed=1, items=[])
check("BatchProgress.is_done (4==3+1)", bp2.is_done is True)
check("BatchProgress.success_rate", abs(bp2.success_rate - 0.75) < 0.01)

# ━━━━━━━━━ 결과 ━━━━━━━━━
print("\n" + "=" * 60)
total = passed + failed
print(f"결과: {passed}/{total} 통과 ({failed}개 실패)")
if failed > 0:
    print("❌ 실패한 테스트가 있습니다!")
    sys.exit(1)
else:
    print("✅ 단위 테스트 모두 통과!")
    sys.exit(0)
