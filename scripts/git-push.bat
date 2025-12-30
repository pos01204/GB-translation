@echo off
chcp 65001 > nul
echo ========================================
echo    GitHub 레포지토리 푸시
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/5] Git 상태 확인...
git status
echo.

echo [2/5] 모든 파일 스테이징...
git add .
echo.

echo [3/5] 커밋 메시지 입력...
set /p COMMIT_MSG="커밋 메시지 (Enter 시 기본값): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Update: Idus Product Translator

git commit -m "%COMMIT_MSG%"
echo.

echo [4/5] 원격 저장소 확인...
git remote -v
echo.

echo [5/5] GitHub에 푸시...
git push -u origin main
if errorlevel 1 (
    echo.
    echo ⚠️ 푸시 실패. 아래 명령어로 강제 푸시를 시도하세요:
    echo    git push -u origin main --force
    echo.
)

echo.
echo ========================================
echo    ✅ 완료!
echo ========================================
echo.
echo GitHub 레포지토리:
echo   https://github.com/pos01204/GB-translation
echo.
pause

