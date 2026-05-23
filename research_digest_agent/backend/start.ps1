# Research Digest Agent — Backend Startup
# Port: 8010 (separate from existing services)

Set-Location "$PSScriptRoot"

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $pyLauncher) {
    Write-Host "[!] Python launcher 'py' is not available. Install Python 3.12 and retry." -ForegroundColor Red
    exit 1
}

# LangChain/MCP dependency stack is reliable on Python 3.12 for this project.
$pythonVersion = & py -3.12 --version 2>$null
if (-not $pythonVersion) {
    Write-Host "[!] Python 3.12 was not found. Install Python 3.12 and retry." -ForegroundColor Red
    exit 1
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$venvPip = Join-Path $PSScriptRoot ".venv\Scripts\pip.exe"

$recreateVenv = $false
if (Test-Path $venvPython) {
    $minor = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($minor -ne "3.12") {
        Write-Host "[*] Recreating .venv with Python 3.12 (found Python $minor)." -ForegroundColor Yellow
        Remove-Item -Recurse -Force .venv
        $recreateVenv = $true
    }
} else {
    $recreateVenv = $true
}

if ($recreateVenv) {
    Write-Host "[*] Creating virtual environment with Python 3.12..." -ForegroundColor Cyan
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
}

Write-Host "[*] Installing dependencies..." -ForegroundColor Cyan
& $venvPip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Dependency installation failed. Backend cannot start." -ForegroundColor Red
    exit 1
}

Write-Host "[*] Starting Research Digest Agent on http://127.0.0.1:8010" -ForegroundColor Green
Write-Host "[*] Open frontend UI at http://127.0.0.1:3000" -ForegroundColor Yellow
Write-Host ""

& $venvPython -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload
