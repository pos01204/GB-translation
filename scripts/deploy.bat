@echo off
chcp 65001 > nul
echo ========================================
echo    Idus Translator Deploy Script
echo    Fix: DOM Path Based Image Filtering
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
git commit -m "Fix: DOM path based image filtering - exclude recommend/review areas"

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
echo Image Filtering Improvements:
echo   1. DOM path based exclusion:
echo      - recommend, related, similar
echo      - review, comment
echo      - artist-product, shop-product
echo   2. Click "product info" tab first
echo   3. Find "fold/more info" button position
echo   4. Find "review(N)" section position
echo   5. Minimum size filter (280x200px)
echo.
pause
