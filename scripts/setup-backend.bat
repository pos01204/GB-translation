@echo off
chcp 65001 > nul
echo ========================================
echo    Backend 설정 스크립트
echo ========================================
echo.

:: Python 버전 확인
echo [0/4] Python 설치 확인 중...
echo.

:: py launcher로 설치된 Python 버전 확인
echo 설치된 Python 버전:
py --list 2>nul
if errorlevel 1 (
    echo py launcher를 찾을 수 없습니다.
)
echo.

:: Python 3.11 확인
py -3.11 --version >nul 2>nul
if %errorlevel% equ 0 (
    echo ✅ Python 3.11 발견!
    set PYTHON_CMD=py -3.11
    set PIP_CMD=py -3.11 -m pip
    goto :start_install
)

:: Python 3.12 확인
py -3.12 --version >nul 2>nul
if %errorlevel% equ 0 (
    echo ✅ Python 3.12 발견!
    set PYTHON_CMD=py -3.12
    set PIP_CMD=py -3.12 -m pip
    goto :start_install
)

:: Python 3.10 확인
py -3.10 --version >nul 2>nul
if %errorlevel% equ 0 (
    echo ✅ Python 3.10 발견!
    set PYTHON_CMD=py -3.10
    set PIP_CMD=py -3.10 -m pip
    goto :start_install
)

:: 호환되는 Python 없음
echo.
echo ========================================
echo ❌ 호환되는 Python 버전을 찾을 수 없습니다!
echo ========================================
echo.
echo 현재 설치된 Python: 3.14.2 (호환 안됨)
echo.
echo Python 3.11을 설치해주세요:
echo.
echo   1. 아래 링크에서 다운로드:
echo      https://www.python.org/downloads/release/python-3119/
echo.
echo   2. "Windows installer (64-bit)" 클릭
echo.
echo   3. 설치 시 반드시 체크:
echo      [v] Add Python 3.11 to PATH
echo.
echo   4. 설치 완료 후 이 스크립트 다시 실행
echo.
echo ========================================
echo.

:: 브라우저로 다운로드 페이지 열기
set /p OPEN_BROWSER="Python 다운로드 페이지를 열까요? (Y/N): "
if /i "%OPEN_BROWSER%"=="Y" (
    start https://www.python.org/downloads/release/python-3119/
)

pause
exit /b 1

:start_install
echo.
echo 사용할 Python: 
%PYTHON_CMD% --version
echo.

cd /d "%~dp0..\backend"

echo [1/4] pip 업그레이드 중...
%PIP_CMD% install --upgrade pip
if errorlevel 1 (
    echo ⚠️ pip 업그레이드 실패 (계속 진행)
)
echo.

echo [2/4] Python 의존성 설치 중...
%PIP_CMD% install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ❌ 오류: pip install 실패
    echo.
    pause
    exit /b 1
)

echo.
echo [3/4] Playwright Chromium 설치 중...
%PYTHON_CMD% -m playwright install chromium
if errorlevel 1 (
    echo.
    echo ❌ 오류: Playwright 설치 실패
    echo.
    pause
    exit /b 1
)

echo.
echo [4/4] 환경 변수 파일 확인...
if not exist ".env" (
    if exist "env.example" (
        copy env.example .env > nul
        echo ✅ .env 파일이 생성되었습니다.
        echo.
        echo ⚠️  중요: .env 파일을 열어서 OPENAI_API_KEY를 설정해주세요!
        echo     notepad backend\.env
    )
) else (
    echo ✅ .env 파일이 이미 존재합니다.
)

echo.
echo ========================================
echo    ✅ Backend 설정 완료!
echo ========================================
echo.
echo 다음 단계:
echo   1. backend\.env 파일에서 OPENAI_API_KEY 설정
echo   2. scripts\run-backend.bat 실행
echo.
echo 서버 실행 명령어:
echo   %PYTHON_CMD% -m uvicorn app.main:app --reload --port 8000
echo.
pause
