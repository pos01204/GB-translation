@echo off
chcp 65001 > nul
echo ========================================
echo    GitHub 레포지토리 초기화
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/4] Git 초기화...
git init
echo.

echo [2/4] 원격 저장소 연결...
git remote add origin https://github.com/pos01204/GB-translation.git 2>nul
if errorlevel 1 (
    echo 이미 원격 저장소가 연결되어 있습니다.
    git remote set-url origin https://github.com/pos01204/GB-translation.git
)
echo.

echo [3/4] 브랜치 설정...
git branch -M main
echo.

echo [4/4] 원격 저장소 확인...
git remote -v
echo.

echo ========================================
echo    ✅ Git 초기화 완료!
echo ========================================
echo.
echo 다음 단계:
echo   1. scripts\git-push.bat 실행하여 코드 푸시
echo   2. Railway에서 Backend 배포
echo   3. Vercel에서 Frontend 배포
echo.
pause

