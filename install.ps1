$ErrorActionPreference = "Stop"
$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

$host.UI.RawUI.WindowTitle = "FaceLib - Installation"
$host.UI.RawUI.BackgroundColor = "DarkBlue"
$host.UI.RawUI.ForegroundColor = "White"
Clear-Host

Write-Host ""
Write-Host "  +========================================+" -ForegroundColor Cyan
Write-Host "  |       FaceLib - Installation           |" -ForegroundColor Cyan
Write-Host "  +========================================+" -ForegroundColor Cyan
Write-Host ""

# Step 1 - Python
Write-Host "  [1/4] Checking Python..." -ForegroundColor Yellow
try {
    $pyver = python --version 2>&1
    Write-Host "  OK: $pyver" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found!" -ForegroundColor Red
    Write-Host "  Download Python 3.10+ from https://python.org" -ForegroundColor White
    Write-Host "  Check 'Add to PATH' during installation" -ForegroundColor White
    Write-Host ""
    Write-Host "  Press Enter to exit..." -ForegroundColor Gray
    Read-Host
    exit 1
}

# Step 2 - Virtual environment
Write-Host ""
Write-Host "  [2/4] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "$DIR\.venv") {
    Remove-Item "$DIR\.venv" -Recurse -Force | Out-Null
}
python -m venv "$DIR\.venv" | Out-Null
Write-Host "  OK: Done" -ForegroundColor Green

# Step 3 - Dependencies
Write-Host ""
Write-Host "  [3/4] Installing dependencies..." -ForegroundColor Yellow
Write-Host "  (this may take 5-10 minutes)" -ForegroundColor Gray
Write-Host ""

$packages = @("fastapi", "uvicorn", "insightface", "onnxruntime", "pillow", "numpy", "python-multipart")
$i = 0
foreach ($pkg in $packages) {
    $i++
    $pct = [int]($i / $packages.Count * 100)
    Write-Progress -Activity "Installing packages" -Status "$pkg ($i/$($packages.Count))" -PercentComplete $pct
    & "$DIR\.venv\Scripts\python.exe" -m pip install $pkg -q 2>&1 | Out-Null
}
Write-Progress -Activity "Installing packages" -Completed
Write-Host "  OK: All packages installed" -ForegroundColor Green

# Step 4 - Shortcut
Write-Host ""
Write-Host "  [4/4] Creating desktop shortcut..." -ForegroundColor Yellow
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = "$desktop\FaceLib.lnk"
$vbs = "$DIR\start.vbs"
$icon = "$DIR\facelib.ico"

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($shortcut)
$s.TargetPath = "wscript.exe"
$s.Arguments = "`"$vbs`""
$s.IconLocation = $icon
$s.Description = "FaceLib"
$s.WorkingDirectory = $DIR
$s.Save()
Write-Host "  OK: Shortcut created on Desktop" -ForegroundColor Green

Write-Host ""
Write-Host "  +========================================+" -ForegroundColor Green
Write-Host "  |      Installation complete!            |" -ForegroundColor Green
Write-Host "  |  Double-click FaceLib on your Desktop  |" -ForegroundColor Green
Write-Host "  +========================================+" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Enter to exit..." -ForegroundColor Gray
Read-Host
