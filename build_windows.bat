@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Koer start_windows.bat mindst een gang foerst.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt || exit /b 1
rem App-ikonet loeses ved runtime fra assetspp_icon.ico / app_icon.png
pyside6-deploy main.py --name "ElplanDWGEditorQt"
if errorlevel 1 pause
