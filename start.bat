@echo off
chcp 65001 >nul
echo ========================================
echo   FaceLib — Запуск (режим діагностики)
echo ========================================
echo.
echo Сервер запускається...
echo Адреса: http://127.0.0.1:7788
echo Для зупинки натисніть Ctrl+C
echo.
echo Логи сервера:
echo ----------------------------------------

if not exist ".venv" (
    echo [ПОМИЛКА] Спочатку запустіть install.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
uvicorn app:app --host 127.0.0.1 --port 7788
pause
