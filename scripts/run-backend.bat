@echo off
chcp 65001 > nul
echo ========================================
echo    Backend 서버 시작
echo ========================================
echo.

:: Python 3.11 확인
py -3.11 --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3.11
    goto :run_server
)

:: Python 3.12 확인
py -3.12 --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3.12
    goto :run_server
)

:: Python 3.10 확인
py -3.10 --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3.10
    goto :run_server
)

echo ❌ 호환되는 Python 버전을 찾을 수 없습니다.
echo    Python 3.11을 설치해주세요.
pause
exit /b 1

:run_server
cd /d "%~dp0..\backend"

:: .env 파일 확인
if not exist ".env" (
    echo ⚠️  경고: .env 파일이 없습니다.
    echo    OPENAI_API_KEY가 설정되지 않으면 번역 기능이 작동하지 않습니다.
    echo.
)

echo 사용 Python: 
%PYTHON_CMD% --version
echo.
echo API 서버를 시작합니다...
echo.
echo   🌐 API URL: http://localhost:8000
echo   📚 API Docs: http://localhost:8000/docs
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo ----------------------------------------
echo.

%PYTHON_CMD% -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
