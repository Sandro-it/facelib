@echo off
chcp 65001 >nul
echo ========================================
echo   FaceLib — Запуск
echo ========================================
echo.

if not exist "venv" (
    echo [ПОМИЛКА] Спочатку запустіть install.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo Запуск сервера...
echo Відкрийте браузер: http://127.0.0.1:7788
echo Для зупинки натисніть Ctrl+C
echo.
start "" http://127.0.0.1:7788
uvicorn app:app --host 127.0.0.1 --port 7788
