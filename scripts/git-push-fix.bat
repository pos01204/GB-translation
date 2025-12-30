@echo off
chcp 65001 > nul
cd /d "C:\Users\김지훈\Desktop\[Global Business셀] 김지훈\AI 자동화\작품 번역 자동화"

echo === Git Push ===
git add -A
git commit -m "fix: google-genai new library migration"
git push origin main

echo.
echo === Done ===
pause

