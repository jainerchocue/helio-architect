@echo off
cd /d "%~dp0"
title FreeCAD Agent
echo Starting FreeCAD AI Agent...
"C:\Program Files\FreeCAD 1.1\bin\python.exe" -u "%~dp0fc_launcher.py"
