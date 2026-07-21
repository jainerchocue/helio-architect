@echo off
cd /d "%~dp0"
echo Helio Architect - Status Check
echo ===============================
echo.
powershell -Command "
try {
    \$s = New-Object Net.Sockets.TcpClient; \$s.Connect('127.0.0.1',9876); \$s.Close();
    Write-Host 'FreeCAD Agent:  RUNNING (port 9876)' -ForegroundColor Green
} catch {
    Write-Host 'FreeCAD Agent:  STOPPED (port 9876)' -ForegroundColor Red
}
try {
    \$s = New-Object Net.Sockets.TcpClient; \$s.Connect('127.0.0.1',8501); \$s.Close();
    Write-Host 'Streamlit App:   RUNNING (port 8501)' -ForegroundColor Green
} catch {
    Write-Host 'Streamlit App:   STOPPED (port 8501)' -ForegroundColor Red
}
"
echo.
echo Open: http://localhost:8501
echo.
if "%~1"=="--check-only" exit /b 0
pause
