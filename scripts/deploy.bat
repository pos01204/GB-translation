@echo off
chcp 65001 > nul
echo ========================================
echo    Idus Translator Deploy Script
echo    Fix: Tab Panel Based Image Extraction
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/4] Checking Git status...
git status

echo.
echo [2/4] Adding all changes...
git add -A

echo.
echo [3/4] Creating commit...
git commit -m "Fix: Tab panel based image extraction, improved API key error handling"

echo.
echo [4/4] Pushing to remote...
git push origin main

echo.
echo ========================================
echo    Deploy completed!
echo ========================================
echo.
echo Frontend (Vercel): https://gb-translation.vercel.app
echo Backend (Railway): Auto-deploy triggered
echo.
echo Image Extraction Improvements:
echo   1. Tab panel based: role="tabpanel" from product info tab
echo   2. Fallback: class-based detail content area
echo   3. Fallback: container with most images
echo   4. Clear API key leaked error message
echo.
echo [!] If API key is blocked:
echo     1. Go to https://aistudio.google.com/apikey
echo     2. Create new API key
echo     3. Update GEMINI_API_KEY in Railway environment
echo.
pause
