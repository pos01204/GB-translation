@echo off
chcp 65001 > nul
echo ========================================
echo    Idus Translator Deploy Script
echo    Fix: Option Button Click Priority
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
git commit -m "Fix: Option extraction - click option button first, review fallback"

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
echo Option Extraction Priority:
echo   1. Click "option select" button (most accurate)
echo   2. Extract from reviews (fallback)
echo   3. Click "buy" button bottom sheet (fallback)
echo.
echo Image Area Filtering:
echo   - Tab structure based detection
echo   - Product info tab content only
echo   - Y-coordinate based sorting
echo   - Minimum size filter (150px)
echo.
pause
