@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
  set PY=py
) else (
  set PY=python
)

if not exist .venv\Scripts\python.exe (
  echo Opretter Python virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 goto :install_error
)

call .venv\Scripts\activate.bat

rem Start hurtigt og offline, hvis de nødvendige pakker allerede findes.
python -c "import PySide6, ezdxf, reportlab; import win32api, win32print" >nul 2>&1
if errorlevel 1 (
  echo Installerer/opdaterer manglende Python-afhaengigheder...
  python -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 goto :install_error
) else (
  echo Python-afhaengigheder er klar.
)

echo.
echo Starter Elplan DWG Editor...
echo.
python main.py
if errorlevel 1 goto :runtime_error

goto :eof

:runtime_error
echo.
echo ============================================================
echo Elplan stoppede med en Python/runtime-fejl.
echo Fejlteksten staar ovenfor og CMD-vinduet holdes nu aabent.
echo Tag evt. et screenshot af hele fejlteksten.
echo Logfil: %%APPDATA%%\ElplanDWGEditor\logs\elplan.log
echo ============================================================
echo.
pause
exit /b 1

:install_error
echo.
echo ============================================================
echo Kunne ikke installere/starte Elplan Qt.
echo Kontroller Python, internetforbindelse og fejlteksten ovenfor.
echo ============================================================
echo.
pause
exit /b 1
