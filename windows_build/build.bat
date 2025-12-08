@echo off
REM ═══════════════════════════════════════════════════════════════════════════════
REM VoxelMask Windows Build Script v1.1
REM ═══════════════════════════════════════════════════════════════════════════════
REM
REM This script builds VoxelMask into a standalone Windows executable.
REM Prerequisites: Python 3.8+ installed and added to PATH
REM
REM ═══════════════════════════════════════════════════════════════════════════════

echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo   VoxelMask v1.0 - Windows Build Script
echo ═══════════════════════════════════════════════════════════════════════════════
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
python --version

echo.
echo [2/4] Installing build dependencies...
echo ─────────────────────────────────────────────────────────────────────────────────

REM Upgrade pip first
pip install --upgrade pip

REM Install PyInstaller
pip install pyinstaller

REM ═══════════════════════════════════════════════════════════════════════════════
REM CORE DEPENDENCIES
REM ═══════════════════════════════════════════════════════════════════════════════
pip install streamlit
pip install pydicom
pip install numpy
pip install pillow
pip install pandas

REM ═══════════════════════════════════════════════════════════════════════════════
REM OPENCV - Use headless version (no GUI dependencies)
REM ═══════════════════════════════════════════════════════════════════════════════
pip install opencv-python-headless

REM ═══════════════════════════════════════════════════════════════════════════════
REM STREAMLIT COMPONENTS & EXTENSIONS
REM ═══════════════════════════════════════════════════════════════════════════════
pip install streamlit-drawable-canvas

REM ═══════════════════════════════════════════════════════════════════════════════
REM STREAMLIT INTERNAL DEPENDENCIES
REM ═══════════════════════════════════════════════════════════════════════════════
pip install altair
pip install pydeck
pip install watchdog
pip install toml
pip install validators
pip install gitpython
pip install rich
pip install tenacity
pip install cachetools
pip install pympler
pip install tzlocal
pip install click
pip install tornado
pip install protobuf

REM ═══════════════════════════════════════════════════════════════════════════════
REM PYDICOM OPTIONAL HANDLERS
REM ═══════════════════════════════════════════════════════════════════════════════
pip install pylibjpeg
pip install pylibjpeg-libjpeg
pip install python-gdcm

REM ═══════════════════════════════════════════════════════════════════════════════
REM ADDITIONAL UTILITIES
REM ═══════════════════════════════════════════════════════════════════════════════
pip install python-magic-bin
pip install packaging
pip install typing_extensions
pip install importlib-metadata

if errorlevel 1 (
    echo.
    echo WARNING: Some optional dependencies may have failed to install.
    echo Continuing with build...
)

echo.
echo [3/4] Building VoxelMask executable...
echo ─────────────────────────────────────────────────────────────────────────────────
echo This may take several minutes...
echo.

pyinstaller --noconfirm --clean VoxelMask.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo Check the output above for error messages.
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo   BUILD SUCCESSFUL!
echo ═══════════════════════════════════════════════════════════════════════════════
echo.
echo [4/4] Build complete!
echo.
echo Your standalone VoxelMask application is located at:
echo.
echo     dist\VoxelMask\VoxelMask.exe
echo.
echo ─────────────────────────────────────────────────────────────────────────────────
echo INSTRUCTIONS:
echo ─────────────────────────────────────────────────────────────────────────────────
echo.
echo 1. Navigate to: dist\VoxelMask\
echo 2. Double-click VoxelMask.exe to run
echo 3. A console window will open showing server status
echo 4. Your browser will automatically open to http://localhost:8501
echo 5. To stop: Close the console window or press Ctrl+C
echo.
echo DISTRIBUTION:
echo ─────────────────────────────────────────────────────────────────────────────────
echo.
echo To distribute VoxelMask:
echo 1. Copy the entire dist\VoxelMask\ folder
echo 2. Users only need to run VoxelMask.exe (no Python required!)
echo 3. Optionally, create a shortcut to VoxelMask.exe on the desktop
echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo.
pause
