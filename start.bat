@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Metacog - LLM Awareness Engine
echo ========================================
echo.
echo 起動中... ブラウザが自動で開きます。
echo 終了するには、UIの「終了」ボタンを押すか、
echo このウィンドウを閉じてください。
echo.

python metacog.py

if errorlevel 1 (
    echo.
    echo [ERROR] 起動に失敗しました。
    echo install.bat を実行してください。
    pause
)
