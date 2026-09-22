@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo Failed to activate the ULTRON virtual environment.
  pause
  exit /b 1
)
python run.py
echo.
echo ULTRON stopped. Review the error above.
pause
