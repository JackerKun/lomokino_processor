@echo off
REM Run script for LomoKino GUI on Windows

REM Check if venv exists
if not exist "venv" (
    echo Virtual environment does not exist. Please run: install_gui.bat
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if PyQt6 is installed
python -c "import PyQt6" 2>nul
if errorlevel 1 (
    echo PyQt6 is not installed. Please run: install_gui.bat
    pause
    exit /b 1
)

REM Run the GUI
echo Starting LomoKino GUI...
python lomokino_gui.py

pause
