cd "c:\AI trining\backend"
Write-Host "Starting backend server on http://127.0.0.1:8000"
Write-Host "Press Ctrl+C to stop"
Write-Host ""
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
