@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ========================================
echo   Git Commit and Push
echo ========================================

git add .
git status
echo.
echo Committing changes...
git commit -m "fix: Auto-detect available Gemini model (gemini-pro fallback)"
echo.
echo Pushing to remote...
git push

echo.
echo Done!
pause
