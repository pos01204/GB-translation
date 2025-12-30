@echo off
chcp 65001 > nul
echo ========================================
echo    Idus Translator 전체 실행
echo ========================================
echo.

:: Python 확인
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo ❌ Python을 찾을 수 없습니다.
        echo    https://www.python.org/downloads/ 에서 설치해주세요.
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

:: Node.js 확인
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Node.js/npm을 찾을 수 없습니다.
    echo    https://nodejs.org/ 에서 설치해주세요.
    pause
    exit /b 1
)

echo Backend와 Frontend를 동시에 실행합니다.
echo.

:: Backend 실행 (새 창에서)
start "Backend Server" cmd /k "cd /d %~dp0..\backend && %PYTHON_CMD% -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: 3초 대기 (Backend 시작 대기)
echo Backend 시작 대기 중...
timeout /t 3 /nobreak > nul

:: Frontend 실행 (새 창에서)
start "Frontend Dev Server" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo.
echo ========================================
echo    ✅ 서버가 시작되었습니다!
echo ========================================
echo.
echo   🎨 Frontend: http://localhost:3000
echo   🔧 Backend:  http://localhost:8000
echo   📚 API Docs: http://localhost:8000/docs
echo.
echo 각 창에서 Ctrl+C로 서버를 종료할 수 있습니다.
echo.
pause
