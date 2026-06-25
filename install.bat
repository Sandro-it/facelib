@echo off
chcp 65001 >nul
echo ========================================
echo   FaceLib — Встановлення
echo ========================================
echo.

set "FACELIB_DIR=%~dp0"
set "FACELIB_DIR=%FACELIB_DIR:~0,-1%"

:: Перевіряємо Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ПОМИЛКА] Python не знайдено!
    echo Скачайте Python 3.10+ з https://python.org
    echo Під час встановлення поставте галочку "Add to PATH"
    pause
    exit /b 1
)

echo [1/4] Python знайдено
python --version

:: Створюємо віртуальне середовище
echo.
echo [2/4] Створення віртуального середовища...
if not exist "%FACELIB_DIR%\.venv" (
    python -m venv "%FACELIB_DIR%\.venv"
)

:: Встановлюємо залежності
echo.
echo [3/4] Встановлення залежностей (може зайняти кілька хвилин)...
call "%FACELIB_DIR%\.venv\Scripts\activate.bat"
pip install --upgrade pip -q
pip install fastapi uvicorn insightface onnxruntime pillow numpy python-multipart -q

:: Створюємо ярлик на робочому столі
echo.
echo [4/4] Створення ярлика на робочому столі...
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\FaceLib.lnk"
set "VBS_PATH=%FACELIB_DIR%\start.vbs"
set "ICON_PATH=%FACELIB_DIR%\facelib.ico"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\""%VBS_PATH%\"\"'; $s.IconLocation = '%ICON_PATH%'; $s.Description = 'FaceLib — розпізнавання облич'; $s.WorkingDirectory = '%FACELIB_DIR%'; $s.Save()"

echo.
echo ========================================
echo   Встановлення завершено!
echo   Ярлик FaceLib створено на робочому столі
echo   Двічі клікніть на нього щоб запустити
echo ========================================
pause
