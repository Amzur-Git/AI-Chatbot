$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'

Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command', "cd '$backendDir'; if (-not (Test-Path .venv)) { python -m venv .venv }; .\.venv\Scripts\python.exe -m pip install --upgrade pip; .\.venv\Scripts\python.exe -m pip install -r requirements.txt; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)

Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command', "cd '$frontendDir'; if (-not (Test-Path node_modules)) { npm install }; npm run dev"
)
