@echo off
chcp 65001 > nul
cd /d "%~dp0\.."

echo === Git Deploy ===
echo.
echo Adding files...
git add -A

echo.
echo Committing...
git commit -m "fix: improve option extraction and remove final tab"

echo.
echo Pushing to origin...
git push origin main

echo.
echo === Deploy Complete ===
pause

