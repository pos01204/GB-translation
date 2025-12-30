@echo off
chcp 65001 > nul
cd /d "%~dp0\.."

echo === Git Deploy ===
git add -A
git commit -m "fix: scraper rewrite - extract images from HTML NUXT network"
git push origin main

echo === Done ===
pause

