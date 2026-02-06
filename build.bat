@echo off
echo ========================================
echo  Metacog - Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous build
echo Cleaning previous build...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build
echo.
echo Building metacog.exe...
echo This may take several minutes...
echo.

pyinstaller metacog.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ========================================
    echo  Build FAILED!
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Build SUCCESS!
echo ========================================
echo.
echo Output: dist\metacog\metacog.exe
echo.
echo To run: double-click dist\metacog\metacog.exe
echo.
pause
