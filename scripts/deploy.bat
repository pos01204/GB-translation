@echo off
chcp 65001 > nul
cd /d "%~dp0\.."

echo === Git Deploy ===
echo.
echo Adding files...
git add -A

echo.
echo Committing...
git commit -m "feat: Phase 1 improvements - prompts, OCR order, copy functions"

echo.
echo Pushing to origin...
git push origin main

echo.
echo === Deploy Complete ===
pause

