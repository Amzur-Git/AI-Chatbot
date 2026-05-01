$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path node_modules)) {
    npm install
}

Write-Host "Starting frontend on http://localhost:5173"
npm run dev
