$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path .venv)) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "Starting backend on http://localhost:8000"
& .\.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000
