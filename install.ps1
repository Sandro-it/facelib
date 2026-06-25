# FaceLib Installer
$ErrorActionPreference = "Stop"
$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

# Налаштування вікна
$host.UI.RawUI.WindowTitle = "FaceLib — Встановлення"
$host.UI.RawUI.BackgroundColor = "DarkBlue"
$host.UI.RawUI.ForegroundColor = "White"
Clear-Host

function Write-Header {
    Write-Host ""
    Write-Host "  ╔════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║        FaceLib — Встановлення          ║" -ForegroundColor Cyan
    Write-Host "  ╚════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param($num, $total, $text)
    Write-Host "  [$num/$total] $text" -ForegroundColor Yellow
}

function Write-OK {
    param($text)
    Write-Host "  ✓ $text" -ForegroundColor Green
}

function Write-Fail {
    param($text)
    Write-Host "  ✗ $text" -ForegroundColor Red
}

Write-Header

# Крок 1 — Python
Write-Step 1 4 "Перевірка Python..."
try {
    $pyver = python --version 2>&1
    Write-OK "Python знайдено: $pyver"
} catch {
    Write-Fail "Python не знайдено!"
    Write-Host ""
    Write-Host "  Скачайте Python 3.10+ з https://python.org" -ForegroundColor White
    Write-Host "  Під час встановлення поставте галочку 'Add to PATH'" -ForegroundColor White
    Write-Host ""
    Write-Host "  Натисніть Enter для виходу..." -ForegroundColor Gray
    Read-Host
    exit 1
}

# Крок 2 — Віртуальне середовище
Write-Host ""
Write-Step 2 4 "Створення віртуального середовища..."
if (-not (Test-Path "$DIR\.venv")) {
    python -m venv "$DIR\.venv" | Out-Null
}
Write-OK "Готово"

# Крок 3 — Залежності
Write-Host ""
Write-Step 3 4 "Встановлення залежностей..."
Write-Host "  (може зайняти 5-10 хвилин — завантажується InsightFace)" -ForegroundColor Gray
Write-Host ""

$packages = @("fastapi", "uvicorn", "insightface", "onnxruntime", "pillow", "numpy", "python-multipart")
$i = 0
foreach ($pkg in $packages) {
    $i++
    $pct = [int]($i / $packages.Count * 100)
    Write-Progress -Activity "Встановлення пакетів" -Status "$pkg ($i/$($packages.Count))" -PercentComplete $pct
    & "$DIR\.venv\Scripts\pip.exe" install $pkg -q 2>&1 | Out-Null
}
Write-Progress -Activity "Встановлення пакетів" -Completed
Write-OK "Всі пакети встановлено"

# Крок 4 — Ярлик
Write-Host ""
Write-Step 4 4 "Створення ярлика на робочому столі..."
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = "$desktop\FaceLib.lnk"
$vbs = "$DIR\start.vbs"
$icon = "$DIR\facelib.ico"

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($shortcut)
$s.TargetPath = "wscript.exe"
$s.Arguments = "`"$vbs`""
$s.IconLocation = $icon
$s.Description = "FaceLib — розпізнавання облич"
$s.WorkingDirectory = $DIR
$s.Save()
Write-OK "Ярлик FaceLib створено на робочому столі"

# Готово
Write-Host ""
Write-Host "  ╔════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║         Встановлення завершено!        ║" -ForegroundColor Green
Write-Host "  ║   Двічі клікніть FaceLib на десктопі  ║" -ForegroundColor Green
Write-Host "  ╚════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Натисніть Enter для виходу..." -ForegroundColor Gray
Read-Host
