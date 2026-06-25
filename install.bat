@echo off
chcp 65001 >nul
echo ========================================
echo   FaceLib — Встановлення
echo ========================================
echo.

:: Перевіряємо Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ПОМИЛКА] Python не знайдено!
    echo Скачайте Python 3.10+ з https://python.org
    echo Під час встановлення поставте галочку "Add to PATH"
    pause
    exit /b 1
)

echo [1/3] Python знайдено
python --version

:: Створюємо віртуальне середовище
echo.
echo [2/3] Створення віртуального середовища...
if not exist "venv" (
    python -m venv venv
)

:: Встановлюємо залежності
echo.
echo [3/3] Встановлення залежностей (може зайняти кілька хвилин)...
call venv\Scripts\activate.bat
pip install --upgrade pip -q
pip install fastapi uvicorn insightface onnxruntime pillow numpy -q

echo.
echo ========================================
echo   Встановлення завершено!
echo   Запустіть start.bat для старту
echo ========================================
pause
