@echo off
chcp 65001 > nul
echo ========================================
echo    Idus Translator Deploy Script
echo    Fix: Hierarchical Option Extraction
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
git commit -m "Fix: Support hierarchical options (2+ levels), sequential group extraction"

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
echo Option Extraction Improvements:
echo   1. Detect option count from "option select (0/N)" format
echo   2. Sequential option group processing (1st -> 2nd -> ...)
echo   3. Click group header to expand accordion
echo   4. Select first option to activate next group
echo   5. Fallback: simple panel / reviews extraction
echo.
echo [!] If API key is blocked:
echo     1. Go to https://aistudio.google.com/apikey
echo     2. Create new API key
echo     3. Update GEMINI_API_KEY in Railway environment
echo.
pause
