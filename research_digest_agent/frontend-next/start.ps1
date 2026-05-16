Set-Location "$PSScriptRoot"

if (-not (Test-Path "node_modules")) {
    Write-Host "[*] Installing frontend dependencies..." -ForegroundColor Cyan
    npm install
}

Write-Host "[*] Starting Research Digest frontend on http://127.0.0.1:3000" -ForegroundColor Green
npm run dev
