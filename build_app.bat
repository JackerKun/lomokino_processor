@echo off
REM Build script for creating standalone application on Windows

echo Building LomoKino GUI application...

REM Check if venv exists
if not exist "venv" (
    echo Virtual environment does not exist. Please run: install_gui.bat
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install PyInstaller if not present
echo Installing PyInstaller...
pip install pyinstaller

REM Clean previous builds
echo Cleaning old build files...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build application
echo Building application...
pyinstaller --onefile --windowed --name LomoKinoGUI lomokino_gui.py

REM Check if build was successful
if exist "dist\LomoKinoGUI.exe" (
    echo.
    echo Build successful!
    echo Application location: dist\LomoKinoGUI.exe
    echo.
    echo You can run the application by double-clicking: dist\LomoKinoGUI.exe
) else (
    echo.
    echo Build failed
    exit /b 1
)

pause
