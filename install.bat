@echo off
chcp 65001 >nul 2>&1

set "FACELIB_DIR=%~dp0"
set "FACELIB_DIR=%FACELIB_DIR:~0,-1%"

echo ========================================
echo   FaceLib - Installation
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Download Python 3.10+ from https://python.org
    echo Check "Add to PATH" during installation
    pause
    exit /b 1
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
set "SHORTCUT=%DESKTOP%\FaceLib.lnk"
set "VBS_PATH=%FACELIB_DIR%\start.vbs"
set "ICON_PATH=%FACELIB_DIR%\facelib.ico"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%VBS_PATH%\"'; $s.IconLocation = '%ICON_PATH%'; $s.Description = 'FaceLib'; $s.WorkingDirectory = '%FACELIB_DIR%'; $s.Save(); Write-Host 'Shortcut created'"

echo.
echo ========================================
echo   Done! FaceLib shortcut on your Desktop
echo   Double-click it to start
echo ========================================
pause
