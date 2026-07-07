@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/2] 최신 릴스 수집 중... (1~2분)
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python
"%PY%" -X utf8 update_seed.py
if errorlevel 1 goto fail
echo [2/2] GitHub에 푸시 중...
git add seed
git commit -m "chore: 릴스 시드 갱신"
git push
echo.
echo 완료! 몇 분 뒤 웹 버전에 반영됩니다.
pause
exit /b 0
:fail
echo 수집에 실패했습니다. 잠시 후 다시 시도해 주세요.
pause
exit /b 1
