@echo off
title AutoReach - Bulk Resume & Cold Email Dispatcher
color 0B
echo =====================================================================
echo           AUTOREACH - 1-CLICK RESUME & COLD EMAIL DISPATCHER        
echo =====================================================================
echo.
echo [1/3] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.9+ from https://www.python.org
    pause
    exit /b
)

echo [2/3] Checking dependencies...
python -c "import fastapi, uvicorn, openpyxl, pandas" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing required packages...
    python -m pip install -r requirements.txt
)

echo [3/3] Starting AutoReach Server...
echo.
echo Application will automatically open in your default web browser!
echo URL: http://localhost:8000
echo.
echo Press CTRL+C anytime in this window to stop the server.
echo =====================================================================
echo.

python app.py
pause
