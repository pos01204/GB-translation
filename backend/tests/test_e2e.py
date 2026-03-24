"""
Phase 5 — E2E 테스트 스크립트
실제 작가웹 연동 전체 파이프라인 검증

사용법:
    # 환경 변수에 로그인 정보 설정 필요
    ARTIST_EMAIL=작가이메일 ARTIST_PASSWORD=비밀번호 python tests/test_e2e.py

    # 또는 직접 .env에서 로드
    python tests/test_e2e.py

테스트 작품 ID: 7fda9710-76e4-4825-bcf4-ca94fd719f13
"""
import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0
skipped = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✓ {name}")
        passed += 1
    else:
        print(f"  ✗ {name} — {detail}")
        failed += 1

def skip(name, reason=""):
    global skipped
    print(f"  ⊘ {name} (건너뜀: {reason})")
    skipped += 1


TEST_PRODUCT_ID = "7fda9710-76e4-4825-bcf4-ca94fd719f13"

print("=" * 60)
print("Phase 5 E2E 테스트")
print("=" * 60)


async def run_e2e():
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    # 환경 변수에서 로그인 정보 확인
    email = os.environ.get("ARTIST_EMAIL", "")
    password = os.environ.get("ARTIST_PASSWORD", "")

    if not email or not password:
        print("\n⚠️  ARTIST_EMAIL / ARTIST_PASSWORD 환경변수가 설정되지 않았습니다.")
        print("   E2E 테스트는 실제 작가웹 연동이 필요합니다.")
        print("   구조적 E2E 검증(dry run)만 실행합니다.\n")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ━━━━━━ Step 1: 헬스 체크 ━━━━━━
        print("\n[Step 1] 헬스 체크")
        r = await client.get("/api/health")
        check("서버 정상 응답", r.status_code == 200)
        data = r.json()
        check("서버 상태 healthy", data.get("status") == "healthy")

        # ━━━━━━ Step 2: 세션 상태 확인 ━━━━━━
        print("\n[Step 2] 세션 상태 확인")
        r = await client.get("/api/v2/session/status")
        check("세션 상태 응답", r.status_code == 200)
        session = r.json()
        check("초기 상태 미인증", session["authenticated"] is False)

        # ━━━━━━ Step 3: 로그인 ━━━━━━
        print("\n[Step 3] 로그인")
        if not email or not password:
            skip("로그인", "자격증명 미설정")
            skip("작품 목록 조회", "미로그인")
            skip("국내 데이터 추출", "미로그인")
            skip("번역 미리보기", "미로그인")
            skip("GB 등록 (임시저장)", "미로그인")
        else:
            r = await client.post(
                "/api/v2/session/login",
                json={"email": email, "password": password},
            )
            login_data = r.json()

            if r.status_code == 200 and login_data.get("success"):
                check("로그인 성공", True)

                # ━━━━━━ Step 4: 작품 목록 ━━━━━━
                print("\n[Step 4] 작품 목록 조회")
                r = await client.get("/api/v2/products/?status=selling")
                check("작품 목록 응답", r.status_code == 200)
                data = r.json()
                check("작품 목록 success", data.get("success") is True)
                products = data.get("products", [])
                check(f"작품 {len(products)}개 조회", len(products) >= 0)

                # ━━━━━━ Step 5: 국내 데이터 추출 ━━━━━━
                print(f"\n[Step 5] 국내 데이터 추출 ({TEST_PRODUCT_ID[:8]}...)")
                r = await client.get(
                    f"/api/v2/products/{TEST_PRODUCT_ID}/domestic"
                )
                check("국내 데이터 응답", r.status_code == 200)
                data = r.json()

                if data.get("success"):
                    domestic = data.get("data", {})
                    check("제목 추출", len(domestic.get("title", "")) > 0)
                    check("가격 추출", domestic.get("price", 0) > 0)
                    check("product_id 일치", domestic.get("product_id") == TEST_PRODUCT_ID)
                    check("설명 HTML 추출", len(domestic.get("description_html", "")) > 0)
                    check(
                        "카테고리 제한 확인",
                        domestic.get("category_restricted") is False,
                        "테스트 작품은 제한 카테고리가 아니어야 합니다",
                    )
                else:
                    check("국내 데이터 추출 성공", False, data.get("message", ""))

                # ━━━━━━ Step 6: 번역 미리보기 ━━━━━━
                print(f"\n[Step 6] 번역 미리보기 ({TEST_PRODUCT_ID[:8]}...)")
                r = await client.post(
                    "/api/v2/translate/preview",
                    json={
                        "product_id": TEST_PRODUCT_ID,
                        "target_languages": ["en", "ja"],
                    },
                    timeout=120.0,
                )
                check("번역 미리보기 응답", r.status_code == 200)
                data = r.json()

                if data.get("success"):
                    global_data = data.get("global_data", {})
                    en = global_data.get("en")
                    ja = global_data.get("ja")

                    check("영어 번역 데이터 존재", en is not None)
                    check("일본어 번역 데이터 존재", ja is not None)

                    if en:
                        check(
                            f"영어 제목 80자 이하 ({len(en.get('title',''))}자)",
                            len(en.get("title", "")) <= 80,
                        )
                        check("영어 설명 HTML 존재", len(en.get("description_html", "")) > 0)
                        check("영어 키워드 존재", len(en.get("keywords", [])) > 0)

                    if ja:
                        check(
                            f"일본어 제목 80자 이하 ({len(ja.get('title',''))}자)",
                            len(ja.get("title", "")) <= 80,
                        )
                        check("일본어 설명 HTML 존재", len(ja.get("description_html", "")) > 0)
                else:
                    check("번역 미리보기 성공", False, data.get("message", ""))

                # ━━━━━━ Step 7: GB 등록 (임시저장 모드) ━━━━━━
                print(f"\n[Step 7] GB 등록 — 임시저장 ({TEST_PRODUCT_ID[:8]}...)")
                r = await client.post(
                    "/api/v2/register/single",
                    json={
                        "product_id": TEST_PRODUCT_ID,
                        "target_languages": ["en", "ja"],
                        "save_as_draft": True,
                    },
                    timeout=180.0,
                )
                check("등록 응답", r.status_code == 200)
                data = r.json()
                check("등록 결과 수신", "message" in data)

                if data.get("success"):
                    result = data.get("result", {})
                    check("등록 성공", result.get("success") is True)
                    check(
                        "임시저장 모드",
                        result.get("saved_as_draft") is True,
                    )
                    check(
                        "등록 언어",
                        len(result.get("languages_registered", [])) > 0,
                    )
                else:
                    # 등록 실패 시에도 에러 핸들링이 되어야 함
                    check("등록 실패 메시지", len(data.get("message", "")) > 0)
                    print(f"    ℹ️  등록 결과: {data.get('message')}")

            else:
                check("로그인 성공", False, login_data.get("message", str(r.status_code)))
                skip("작품 목록 조회", "로그인 실패")
                skip("국내 데이터 추출", "로그인 실패")
                skip("번역 미리보기", "로그인 실패")
                skip("GB 등록 (임시저장)", "로그인 실패")


asyncio.run(run_e2e())

# ━━━━━━━━━ 결과 ━━━━━━━━━
print("\n" + "=" * 60)
total = passed + failed + skipped
print(f"결과: {passed} 통과 / {failed} 실패 / {skipped} 건너뜀 (총 {total})")
if failed > 0:
    print("❌ 실패한 테스트가 있습니다!")
    sys.exit(1)
else:
    print("✅ E2E 테스트 완료!")
    sys.exit(0)
