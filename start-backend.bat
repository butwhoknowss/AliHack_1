@echo off
REM ============================================================
REM  Earth Trend Detective - start the FastAPI backend
REM  Double-click this file, keep the window open, then open
REM  frontend/index.html with Live Server.
REM ============================================================
title Earth Trend Detective - backend
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating Python virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [error] Python was not found. Install Python 3.12+ from python.org and tick "Add to PATH".
        pause
        exit /b 1
    )
    echo [setup] Installing packages - this takes a few minutes the first time ...
    ".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt
    if errorlevel 1 (
        echo [error] Package installation failed. See the messages above.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo [warning] Created .env from .env.example. Put your key in WEATHERAPI_KEY= for place search and current weather.
)

echo.
echo  Backend starting at http://127.0.0.1:8000   (API docs: http://127.0.0.1:8000/docs)
echo  KEEP THIS WINDOW OPEN. Now open frontend\index.html with Live Server.
echo  Press Ctrl+C to stop.
echo.

cd backend
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
pause
