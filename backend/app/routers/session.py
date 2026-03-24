"""
v2 세션 관리 라우터
작가웹(artist.idus.com) 브라우저 세션의 인증 및 상태 관리
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/session", tags=["V2 - Session"])

# 전역 세션 참조 (main.py에서 주입)
_artist_session = None


def configure(artist_session):
    """main.py에서 작가웹 세션 인스턴스를 주입받는다"""
    global _artist_session
    _artist_session = artist_session


# ──────────────── Request/Response Models ────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str


class SessionStatusResponse(BaseModel):
    initialized: bool
    authenticated: bool
    current_url: Optional[str] = None


# ──────────────── Endpoints ────────────────

@router.post("/login", response_model=LoginResponse, summary="작가웹 로그인")
async def login(request: LoginRequest):
    """
    작가웹에 로그인합니다.

    - **email**: 작가웹 계정 이메일
    - **password**: 비밀번호
    """
    if not _artist_session:
        raise HTTPException(status_code=503, detail="세션 서비스가 초기화되지 않았습니다")

    try:
        # 브라우저 초기화 (필요시)
        if not _artist_session._initialized:
            await _artist_session.initialize()

        success = await _artist_session.login(request.email, request.password)

        if success:
            return LoginResponse(success=True, message="로그인 성공")
        else:
            return LoginResponse(success=False, message="로그인 실패: 이메일 또는 비밀번호를 확인해주세요")

    except Exception as e:
        logger.error(f"로그인 처리 중 오류: {e}")
        return LoginResponse(success=False, message=f"로그인 처리 중 오류: {str(e)}")


@router.get("/status", response_model=SessionStatusResponse, summary="세션 상태 확인")
async def get_session_status():
    """현재 작가웹 세션의 인증 상태를 확인합니다."""
    if not _artist_session:
        return SessionStatusResponse(initialized=False, authenticated=False)

    info = await _artist_session.get_session_info()
    return SessionStatusResponse(**info)


@router.post("/logout", response_model=LoginResponse, summary="세션 종료")
async def logout():
    """작가웹 세션을 종료합니다."""
    if not _artist_session:
        return LoginResponse(success=True, message="활성 세션이 없습니다")

    try:
        await _artist_session.close()
        return LoginResponse(success=True, message="세션이 종료되었습니다")
    except Exception as e:
        logger.error(f"세션 종료 중 오류: {e}")
        return LoginResponse(success=False, message=f"세션 종료 중 오류: {str(e)}")
