@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" exit /b 1
venv\Scripts\python.exe -m pip install -r requirements_gui.txt "pyinstaller>=6.10,<7"
if errorlevel 1 exit /b 1
set QT_QPA_PLATFORM=offscreen
venv\Scripts\python.exe -m unittest discover -s tests -v
if errorlevel 1 exit /b 1
venv\Scripts\python.exe -m PyInstaller --noconfirm lomokino_gui.spec
if errorlevel 1 exit /b 1
echo Built dist\LomoKinoGUI\LomoKinoGUI.exe - distribute the entire folder.
