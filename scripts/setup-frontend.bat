@echo off
chcp 65001 > nul
echo ========================================
echo    Frontend 설정 스크립트
echo ========================================
echo.

cd /d "%~dp0..\frontend"

echo [1/2] Node.js 의존성 설치 중...
call npm install
if errorlevel 1 (
    echo 오류: npm install 실패
    pause
    exit /b 1
)

echo.
echo [2/2] 설정 완료!
echo.
echo ========================================
echo    Frontend 개발 서버 실행 방법:
echo    npm run dev
echo ========================================
echo.
pause

