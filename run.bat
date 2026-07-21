@echo off
cd /d "%~dp0"
title Helio Architect
cls

echo ============================================
echo    Helio Architect - AI Architecture Agent
echo ============================================
echo.

:: Matar procesos zombies del puerto 9876
echo [0/2] Cleaning previous sessions...
powershell -Command "Get-Process -Name 'python' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*fc_launcher*' } | Stop-Process -Force -ErrorAction SilentlyContinue"
powershell -Command "Get-Process -Name 'FreeCAD' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"
timeout /t 2 /nobreak >nul

if not exist "C:\Program Files\FreeCAD 1.1\bin\python.exe" (
    echo [ERROR] FreeCAD 1.1 no encontrado
    pause
    exit /b 1
)
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] No se encuentra venv\Scripts\python.exe
    pause
    exit /b 1
)

echo [1/2] Starting FreeCAD Agent...
start "FreeCAD Agent" "C:\Program Files\FreeCAD 1.1\bin\python.exe" -u "%~dp0fc_launcher.py"

echo [2/2] Starting Streamlit...
start "Streamlit" "%~dp0venv\Scripts\python.exe" -m streamlit run "%~dp0web_app.py" --server.port 8501

echo.
echo Both servers starting in separate windows.
echo Open http://localhost:8501 in your browser.
echo Close the windows to stop.
echo.
pause
