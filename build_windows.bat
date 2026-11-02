@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-build\Scripts\python.exe" (
    py -3.12 -m venv .venv-build
    if errorlevel 1 goto :failed
)
".venv-build\Scripts\python.exe" -m pip install --requirement requirements-build.txt
if errorlevel 1 goto :failed
".venv-build\Scripts\python.exe" build_windows.py
if errorlevel 1 goto :failed
echo Build completata in dist\ContaFlow\ContaFlow.exe
pause
exit /b 0
:failed
echo Build non riuscita. Controlla Python 3.12, connessione e messaggi sopra.
pause
exit /b 1
