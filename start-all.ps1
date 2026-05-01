$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'

Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command', "cd '$backendDir'; if (-not (Test-Path .venv)) { python -m venv .venv }; .\.venv\Scripts\python.exe -m pip install --upgrade pip; .\.venv\Scripts\python.exe -m pip install -r requirements.txt; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
)

Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command', "cd '$frontendDir'; if (-not (Test-Path node_modules)) { npm install }; npm run dev"
)
