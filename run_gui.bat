@echo off
setlocal
cd /d "%~dp0"
if exist ".venv312\Scripts\python.exe" (
    ".venv312\Scripts\python.exe" main.py
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    py -3.12 main.py
)
if errorlevel 1 pause
endlocal
