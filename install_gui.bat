@echo off
REM Install script for LomoKino GUI on Windows

echo Installing LomoKino GUI dependencies...

REM Check if venv exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements_gui.txt

echo.
echo Installation complete!
echo.
echo To run the GUI application:
echo   run_gui.bat
echo.
echo Or:
echo   venv\Scripts\activate.bat
echo   python lomokino_gui.py

pause
