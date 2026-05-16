#!/usr/bin/env pwsh

Write-Host "Starting Tic Tac Toe Agent Backend..." -ForegroundColor Cyan

$BackendDir = Join-Path $PSScriptRoot "backend"

# Navigate to backend directory
Push-Location $BackendDir

# Create venv if it doesn't exist
$VenvPath = Join-Path $BackendDir ".venv"
if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "$VenvPath\Scripts\Activate.ps1"

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -q -r requirements.txt

# Display startup info
Write-Host ""
Write-Host "Starting Tic Tac Toe Agent Backend..." -ForegroundColor Green
Write-Host "Server:     http://127.0.0.1:8011" -ForegroundColor Green
Write-Host "API Docs:   http://127.0.0.1:8011/docs" -ForegroundColor Green
Write-Host "Frontend:   http://localhost:5173/tic-tac-toe" -ForegroundColor Green
Write-Host ""

# Start the server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload

Pop-Location
