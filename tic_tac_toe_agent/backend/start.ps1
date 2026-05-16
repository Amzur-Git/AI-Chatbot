#!/usr/bin/env pwsh

Write-Host "🎮 Starting Tic Tac Toe Agent Backend..." -ForegroundColor Cyan

# Ensure we're in the backend directory
$BackendDir = $PSScriptRoot

# Activate virtual environment if it exists
$VenvPath = Join-Path $BackendDir ".venv"
if (Test-Path $VenvPath) {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & "$VenvPath\Scripts\Activate.ps1"
} else {
    Write-Host "Warning: Virtual environment not found at $VenvPath" -ForegroundColor Yellow
}

# Install/update dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -q -r (Join-Path $BackendDir "requirements.txt")

# Start the server
Write-Host "🚀 Starting Tic Tac Toe Agent on http://127.0.0.1:8011" -ForegroundColor Green
Write-Host "API Docs available at http://127.0.0.1:8011/docs" -ForegroundColor Green
Write-Host ""

cd $BackendDir
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload
