"""
Phase 5 — 통합 테스트
FastAPI TestClient를 사용한 API 엔드포인트 검증
(Playwright/Gemini 없이 구조 + 에러 핸들링 테스트)
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
print("Phase 5 통합 테스트 (API 엔드포인트)")
print("=" * 60)

from httpx import ASGITransport, AsyncClient
from app.main import app
import asyncio


async def run_tests():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. Health endpoints
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[1] Health endpoints")

        r = await client.get("/")
        check("GET / 상태코드 200", r.status_code == 200)
        data = r.json()
        check("GET / version 필드", "version" in data)

        r = await client.get("/api/health")
        check("GET /api/health 200", r.status_code == 200)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. v2 Session endpoints (세션 미초기화 상태)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[2] v2 Session endpoints")

        r = await client.get("/api/v2/session/status")
        check("GET /session/status 200", r.status_code == 200)
        data = r.json()
        check("session/status authenticated=false", data["authenticated"] is False)

        r = await client.post(
            "/api/v2/session/login",
            json={"email": "test@test.com", "password": "wrong"},
        )
        # 503 because artist_session isn't initialized with a browser
        check("POST /session/login 세션미초기화 503", r.status_code == 503)

        r = await client.post("/api/v2/session/logout")
        check("POST /session/logout 200", r.status_code == 200)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. v2 Products endpoints (미인증 상태)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[3] v2 Products endpoints (미인증)")

        r = await client.get("/api/v2/products/?status=selling")
        # artist_session exists but not authenticated → 401
        # Or 503 if not initialized. Either is acceptable.
        check(
            "GET /products 미인증 → 4xx/5xx",
            r.status_code in (401, 503),
            f"got {r.status_code}",
        )

        r = await client.get("/api/v2/products/test-uuid/domestic")
        check(
            "GET /products/:id/domestic 미인증",
            r.status_code in (401, 503),
            f"got {r.status_code}",
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4. v2 Translation endpoints (미인증)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[4] v2 Translation endpoints (미인증)")

        r = await client.post(
            "/api/v2/translate/preview",
            json={"product_id": "test-uuid", "target_languages": ["en"]},
        )
        check(
            "POST /translate/preview 미인증 → 4xx/5xx",
            r.status_code in (401, 503),
            f"got {r.status_code}",
        )

        # /translate/direct는 세션 없이도 번역기만 있으면 가능하지만
        # gb_translator 미초기화 → 503
        r = await client.post(
            "/api/v2/translate/direct",
            json={
                "domestic_data": {
                    "product_id": "test",
                    "product_url": "https://test",
                    "title": "테스트",
                    "price": 10000,
                },
                "target_languages": ["en"],
            },
        )
        check(
            "POST /translate/direct 번역기미초기화 → 503",
            r.status_code == 503,
            f"got {r.status_code}",
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 5. v2 Registration endpoints (미인증)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[5] v2 Registration endpoints (미인증)")

        r = await client.post(
            "/api/v2/register/single",
            json={"product_id": "test-uuid"},
        )
        check(
            "POST /register/single 미인증 → 4xx/5xx",
            r.status_code in (401, 503),
            f"got {r.status_code}",
        )

        r = await client.post(
            "/api/v2/register/batch",
            json={"product_ids": ["a", "b"]},
        )
        check(
            "POST /register/batch 미인증 → 4xx/5xx",
            r.status_code in (401, 503),
            f"got {r.status_code}",
        )

        r = await client.get("/api/v2/register/batch/status")
        check(
            "GET /register/batch/status 200",
            r.status_code == 200,
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 6. v1 하위호환 (모든 엔드포인트 존재)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[6] v1 하위호환 엔드포인트")

        # v1 POST endpoints without body → 422 (validation error), which means route exists
        r = await client.post("/api/scrape", json={})
        check("POST /api/scrape 라우트 존재", r.status_code in (200, 422, 500), f"got {r.status_code}")

        r = await client.post("/api/translate", json={})
        check("POST /api/translate 라우트 존재", r.status_code in (200, 422, 500), f"got {r.status_code}")

        r = await client.post("/api/scrape-and-translate")
        check("POST /api/scrape-and-translate 라우트 존재", r.status_code in (200, 422, 500), f"got {r.status_code}")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 7. 잘못된 요청 검증
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[7] 잘못된 요청 (validation)")

        # 빈 email/password
        r = await client.post(
            "/api/v2/session/login",
            json={},
        )
        check(
            "POST /session/login body 없음 → 422 또는 503",
            r.status_code in (422, 503),
            f"got {r.status_code}",
        )

        # 빈 product_ids
        r = await client.post(
            "/api/v2/register/batch",
            json={"product_ids": []},
        )
        # Should be 503 (not authenticated) or handled gracefully
        check(
            "POST /register/batch 빈 목록 → 에러 핸들링",
            r.status_code in (200, 401, 503),
            f"got {r.status_code}",
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 8. OpenAPI 문서
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[8] OpenAPI 문서 생성")

        r = await client.get("/openapi.json")
        check("GET /openapi.json 200", r.status_code == 200)
        schema = r.json()
        paths = list(schema.get("paths", {}).keys())
        check("OpenAPI paths 포함", len(paths) >= 10, f"paths={len(paths)}")

        # v2 태그 확인
        tags = set()
        for p_info in schema.get("paths", {}).values():
            for method_info in p_info.values():
                for tag in method_info.get("tags", []):
                    tags.add(tag)
        check("V2 - Session 태그", "V2 - Session" in tags, f"tags={tags}")
        check("V2 - Products 태그", "V2 - Products" in tags, f"tags={tags}")
        check("V2 - Translation 태그", "V2 - Translation" in tags, f"tags={tags}")
        check("V2 - Registration 태그", "V2 - Registration" in tags, f"tags={tags}")


asyncio.run(run_tests())

# ━━━━━━━━━ 결과 ━━━━━━━━━
print("\n" + "=" * 60)
total = passed + failed
print(f"결과: {passed}/{total} 통과 ({failed}개 실패)")
if failed > 0:
    print("❌ 실패한 테스트가 있습니다!")
    sys.exit(1)
else:
    print("✅ 통합 테스트 모두 통과!")
    sys.exit(0)
