@echo off
cd /d "%~dp0"
echo ========================================
echo          ULTRON INSTALLER
echo ========================================
python -m venv .venv
if errorlevel 1 goto err
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto err
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto err
".venv\Scripts\python.exe" -m py_compile run.py server\app.py core\*.py computer\*.py monitoring\*.py security\*.py automation\*.py
if errorlevel 1 goto err
echo.
echo ULTRON installation completed successfully.
echo You can now run start.bat
echo.
pause
exit /b 0
:err
echo.
echo ULTRON installation failed. Read the error above.
pause
exit /b 1
