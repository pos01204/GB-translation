@echo off
chcp 65001 > nul
echo ========================================
echo    Frontend 개발 서버 시작
echo ========================================
echo.

cd /d "%~dp0..\frontend"

echo 개발 서버를 시작합니다...
echo URL: http://localhost:3000
echo.

call npm run dev

