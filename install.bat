@echo off
chcp 65001 >nul
echo ========================================
echo   Metacog - LLM Awareness Engine
echo   インストーラー
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Pythonが見つかりません。
    echo Python 3.10以上をインストールしてください:
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Python環境を確認中...
python --version

echo.
echo [2/3] 依存パッケージをインストール中...
echo （初回は数分かかります）
echo.

pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] パッケージのインストールに失敗しました。
    pause
    exit /b 1
)

echo.
echo [3/3] ショートカットを作成中...

REM Create start.bat if not exists
if not exist "start.bat" (
    echo @echo off > start.bat
    echo cd /d "%%~dp0" >> start.bat
    echo python metacog.py >> start.bat
)

echo.
echo ========================================
echo   インストール完了！
echo ========================================
echo.
echo 起動方法:
echo   1. start.bat をダブルクリック
echo   2. または: python metacog.py
echo.
echo 注意: LM Studio を先に起動してください。
echo.
pause
