@echo off
chcp 65001 > nul
echo ========================================
echo    Idus Translator Deploy Script
echo    Fix: Image Filtering + OCR Optimization
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
git commit -m "Fix: Improved image filtering, reduced OCR limit to 10 for faster processing"

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
echo Improvements:
echo   1. DOM path based image exclusion (recommend, review, etc.)
echo   2. Y-position based detail area detection
echo   3. Max 15 images from scraper (was 30+)
echo   4. Max 10 images for OCR (was 15)
echo   5. Strict fallback filtering (400px+ only)
echo.
pause
