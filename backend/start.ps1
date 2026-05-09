param(
    [switch]$Reload,
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path .venv)) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

$uvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--host', $BindHost, '--port', "$Port")
if ($Reload) {
    $uvicornArgs += '--reload'
}

Write-Host "Starting backend on http://$BindHost`:$Port"
if ($Reload) {
    Write-Host 'Reload mode enabled.'
}

& .\.venv\Scripts\python.exe @uvicornArgs
