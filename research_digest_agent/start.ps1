# Research Digest Agent — Run Backend + Next.js Frontend
# Run from the research_digest_agent/ root

Write-Host "=== Research Digest Agent ===" -ForegroundColor Cyan
Write-Host ""

# Start backend in a separate window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned; Set-Location '$PSScriptRoot\backend'; .\start.ps1"

# Start frontend in a separate window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned; Set-Location '$PSScriptRoot\frontend-next'; .\start.ps1"

# Wait a moment then open browser
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:3000"

Write-Host "[*] Backend starting on http://127.0.0.1:8010" -ForegroundColor Green
Write-Host "[*] Frontend starting on http://127.0.0.1:3000" -ForegroundColor Green
Write-Host "[*] Browser opened. If it fails, refresh in a few seconds." -ForegroundColor Yellow
