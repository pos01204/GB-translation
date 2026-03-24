"""
Phase 3 빌드 테스트
- registration 라우터 임포트 및 엔드포인트 확인
- ProductWriter 클래스 검증
- BatchProcessor/BatchItem/BatchProgress 검증
- main.py 라우터 등록 확인 (총 21+ 라우트)
- v1 하위 호환성 유지 확인
"""
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(__file__))

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
print("Phase 3 빌드 테스트")
print("=" * 60)

# ──────── 1. Config ────────
print("\n[1] Config")
try:
    from app.config import settings
    check("settings 로드", True)
    check("batch_max_size", settings.batch_max_size == 10)
    check("batch_item_delay", settings.batch_item_delay == 3.0)
except Exception as e:
    check("settings 로드", False, str(e))

# ──────── 2. Models ────────
print("\n[2] Models — global_product")
try:
    from app.models.global_product import (
        LanguageData, GlobalOption, GlobalProductData, RegistrationResult,
    )
    check("GlobalProductData import", True)

    # RegistrationResult 직렬화 테스트
    rr = RegistrationResult(
        product_id="test-123",
        success=True,
        languages_registered=["en", "ja"],
        languages_failed=[],
        saved_as_draft=True,
    )
    d = rr.model_dump()
    check("RegistrationResult 직렬화", d["product_id"] == "test-123" and d["success"])
except Exception as e:
    check("Models import", False, str(e))

# ──────── 3. Services ────────
print("\n[3] Services — ProductWriter")
try:
    from app.services.product_writer import ProductWriter
    check("ProductWriter import", True)
    # 메서드 존재 확인
    methods = [
        "navigate_to_global_tab", "select_language_tab",
        "import_domestic_images", "fill_title", "fill_description",
        "fill_keywords", "fill_global_options", "save_draft", "publish",
        "fill_language_data", "register_global_product",
    ]
    for m in methods:
        check(f"  .{m}()", hasattr(ProductWriter, m))
except Exception as e:
    check("ProductWriter import", False, str(e))

print("\n[4] Services — BatchProcessor")
try:
    from app.services.batch_processor import BatchProcessor, BatchItem, BatchProgress
    check("BatchProcessor import", True)

    # BatchProgress 테스트
    bp = BatchProgress(
        total=3,
        completed=2,
        failed=1,
        items=[
            BatchItem(product_id="a", status="completed"),
            BatchItem(product_id="b", status="completed"),
            BatchItem(product_id="c", status="failed", error_message="err"),
        ],
    )
    check("BatchProgress.is_done", bp.is_done)
    check("BatchProgress.success_rate", abs(bp.success_rate - 2 / 3) < 0.01)
    d = bp.to_dict()
    check("BatchProgress.to_dict()", d["total"] == 3 and d["is_done"])
    check("  items in dict", len(d["items"]) == 3)
except Exception as e:
    check("BatchProcessor import", False, str(e))

print("\n[5] Services — __init__ exports")
try:
    from app.services import (
        ArtistWebSession, ProductReader, ProductWriter,
        BatchProcessor, BatchItem, BatchProgress,
    )
    check("모든 서비스 export", True)
except Exception as e:
    check("서비스 export", False, str(e))

# ──────── 4. Routers ────────
print("\n[6] Routers — registration")
try:
    from app.routers.registration import router as reg_router, configure
    check("registration 라우터 import", True)

    paths = [r.path for r in reg_router.routes]
    check("/register/single 엔드포인트", "/api/v2/register/single" in paths, f"paths={paths}")
    check("/register/batch 엔드포인트", "/api/v2/register/batch" in paths, f"paths={paths}")
    check("/register/batch/status 엔드포인트", "/api/v2/register/batch/status" in paths, f"paths={paths}")
    check("configure 함수", callable(configure))
except Exception as e:
    check("registration 라우터", False, str(e))

# ──────── 5. Main App ────────
print("\n[7] Main App — 전체 라우트 검증")
try:
    from app.main import app
    all_routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            all_routes.append(route.path)

    print(f"    총 라우트 수: {len(all_routes)}")
    for r in sorted(all_routes):
        print(f"      {r}")

    # Phase 3 신규 라우트
    check("/api/v2/register/single", "/api/v2/register/single" in all_routes)
    check("/api/v2/register/batch", "/api/v2/register/batch" in all_routes)
    check("/api/v2/register/batch/status", "/api/v2/register/batch/status" in all_routes)

    # 기존 라우트 유지 확인
    check("/api/health (v1 호환)", "/api/health" in all_routes)
    check("/api/v2/session/login", "/api/v2/session/login" in all_routes)
    check("/api/v2/products/", "/api/v2/products/" in all_routes)
    check("/api/v2/translate/preview", "/api/v2/translate/preview" in all_routes)

    # 총 라우트 수 확인 (Phase 2: 18 + Phase 3: 3 = 21+)
    check(f"라우트 수 >= 21", len(all_routes) >= 21, f"실제: {len(all_routes)}")
except Exception as e:
    check("Main App 라우트", False, str(e))

# ──────── 6. v1 하위 호환 ────────
print("\n[8] v1 하위 호환성")
try:
    v1_paths = ["/api/scrape", "/api/translate", "/api/scrape-and-translate"]
    for p in v1_paths:
        check(f"v1 {p}", p in all_routes)
except Exception as e:
    check("v1 호환", False, str(e))

# ──────── 결과 ────────
print("\n" + "=" * 60)
total = passed + failed
print(f"결과: {passed}/{total} 통과 ({failed}개 실패)")
if failed > 0:
    print("❌ 실패한 테스트가 있습니다!")
    sys.exit(1)
else:
    print("✅ Phase 3 빌드 테스트 모두 통과!")
    sys.exit(0)
