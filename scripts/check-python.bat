@echo off
chcp 65001 > nul
echo ========================================
echo    Python 설치 상태 확인
echo ========================================
echo.

echo [py launcher 버전 목록]
py --list 2>nul
if errorlevel 1 (
    echo py launcher를 찾을 수 없습니다.
)

echo.
echo ----------------------------------------
echo.

echo [python 명령어]
python --version 2>nul
if errorlevel 1 (
    echo python 명령어를 찾을 수 없습니다.
)

echo.
echo ----------------------------------------
echo.

echo [py -3.11 확인]
py -3.11 --version 2>nul
if errorlevel 1 (
    echo Python 3.11이 설치되어 있지 않습니다.
    echo.
    echo ❌ Python 3.11을 설치해주세요:
    echo    https://www.python.org/downloads/release/python-3119/
)

echo.
echo ----------------------------------------
echo.

echo [py -3.12 확인]
py -3.12 --version 2>nul
if errorlevel 1 (
    echo Python 3.12가 설치되어 있지 않습니다.
)

echo.
pause

