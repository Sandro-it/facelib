@echo off
chcp 65001 >nul 2>&1

set "FACELIB_DIR=%~dp0"
set "FACELIB_DIR=%FACELIB_DIR:~0,-1%"

echo ========================================
echo   FaceLib - Installation
echo ========================================
echo.

:: Перевіряємо Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Downloading Python 3.11...
    echo     Please wait...
    echo.
    :: Скачуємо Python installer
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
    if errorlevel 1 (
        echo [ERROR] Failed to download Python.
        echo Please download manually from https://python.org
        pause
        exit /b 1
    )
    echo [*] Installing Python...
    :: Встановлюємо тихо з Add to PATH
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    if errorlevel 1 (
        echo [ERROR] Python installation failed.
        pause
        exit /b 1
    )
    del "%TEMP%\python_installer.exe"
    :: Оновлюємо PATH для поточної сесії
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    echo [OK] Python installed successfully
    echo.
)

echo [1/4] Python found:
python --version

echo.
echo [2/4] Creating virtual environment...
if not exist "%FACELIB_DIR%\.venv" (
    python -m venv "%FACELIB_DIR%\.venv"
)

echo.
echo [3/4] Installing dependencies (may take a few minutes)...
call "%FACELIB_DIR%\.venv\Scripts\activate.bat"
python -m pip install --upgrade pip -q 2>nul
pip install fastapi uvicorn insightface onnxruntime pillow numpy python-multipart -q

echo.
echo [4/4] Creating desktop shortcut...
set "DESKTOP=%USERPROFILE%\Desktop"
set "VBS_PATH=%FACELIB_DIR%\start.vbs"
set "ICON_PATH=%FACELIB_DIR%\facelib.ico"
set "SHORTCUT=%DESKTOP%\FaceLib.lnk"

:: Створюємо ярлик через VBS скрипт
set "TMPVBS=%TEMP%\make_shortcut.vbs"
echo Set ws = CreateObject("WScript.Shell") > "%TMPVBS%"
echo Set s = ws.CreateShortcut("%SHORTCUT%") >> "%TMPVBS%"
echo s.TargetPath = "wscript.exe" >> "%TMPVBS%"
echo s.Arguments = Chr(34) ^& "%VBS_PATH%" ^& Chr(34) >> "%TMPVBS%"
echo s.IconLocation = "%ICON_PATH%" >> "%TMPVBS%"
echo s.Description = "FaceLib" >> "%TMPVBS%"
echo s.WorkingDirectory = "%FACELIB_DIR%" >> "%TMPVBS%"
echo s.Save >> "%TMPVBS%"
cscript //nologo "%TMPVBS%"
del "%TMPVBS%"
echo Shortcut created

echo.
echo ========================================
echo   Done! FaceLib shortcut on your Desktop
echo   Double-click it to start
echo ========================================
timeout /t 3 /nobreak >nul
