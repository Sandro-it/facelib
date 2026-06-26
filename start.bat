@echo off

if not exist ".venv" (
    echo [ERROR] Run install.bat first
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo Server starting at http://127.0.0.1:7788
echo Press Ctrl+C to stop
echo.
uvicorn app:app --host 127.0.0.1 --port 7788
pause
