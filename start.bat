@echo off
chcp 65001 >nul
pushd "%~dp0"

echo ========================================
echo   Metacog - LLM Awareness Engine
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

echo Starting... Browser will open automatically.
echo.

python metacog.py

echo.
echo Finished.
popd
pause
