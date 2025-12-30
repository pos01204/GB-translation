@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ========================================
echo   Git Commit and Push
echo ========================================

git add .
git commit -m "refactor: API-based Idus scraper with Nuxt.js support"
git push

echo.
echo Done!
pause

