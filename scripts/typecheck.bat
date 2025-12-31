@echo off
chcp 65001 > nul
cd /d "%~dp0..\frontend"
call npx tsc --noEmit
echo.
echo TypeScript check completed with exit code: %ERRORLEVEL%
pause
