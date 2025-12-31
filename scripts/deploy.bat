@echo off
chcp 65001 > nul
echo ========================================
echo    Idus Translator Deploy Script
echo    Phase 4: Batch Processing + Glossary
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
git commit -m "Phase 4: Add batch processing and glossary management features"

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
echo New Features:
echo   - Batch translation (up to 10 URLs)
echo   - Glossary management UI
echo   - JSON import/export
echo.
pause
