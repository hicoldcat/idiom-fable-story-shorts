@echo off
chcp 65001 >nul
cd /d "%~dp0"
python scripts\build_zip.py
if errorlevel 1 py scripts\build_zip.py
echo.
pause
