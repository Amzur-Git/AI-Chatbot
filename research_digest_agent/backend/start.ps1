# Research Digest Agent — Backend Startup
# Port: 8010 (separate from existing services)

Set-Location "$PSScriptRoot"

# Install deps if venv doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "[*] Installing dependencies..." -ForegroundColor Cyan
& .\.venv\Scripts\pip.exe install -r requirements.txt --quiet

Write-Host "[*] Starting Research Digest Agent on http://127.0.0.1:8010" -ForegroundColor Green
Write-Host "[*] Open frontend UI at http://127.0.0.1:3000" -ForegroundColor Yellow
Write-Host ""

& .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload
