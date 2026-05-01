$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'

Write-Host '🚀 Starting Chatbot Application with Database Support'
Write-Host '=================================================='

# Check if PostgreSQL is available
Write-Host 'Checking PostgreSQL connection...'
try {
    $envFile = Join-Path $backendDir '.env'
    if (Test-Path $envFile) {
        $envContent = Get-Content $envFile
        $dbUrl = $envContent | Where-Object { $_ -match '^DATABASE_URL=' } | ForEach-Object { $_.Split('=', 2)[1] }
        if ($dbUrl -and $dbUrl -ne 'postgresql://localhost/chatbot_db') {
            Write-Host '✓ Database URL configured in .env'
        } else {
            Write-Host '⚠️  Database URL not configured. Please run setup_database.py first.'
            Write-Host '   See DATABASE_SETUP.md for instructions.'
        }
    }
} catch {
    Write-Host '⚠️  Could not check database configuration'
}

Write-Host 'Preparing backend and frontend...'

if (-not (Test-Path (Join-Path $backendDir '.venv'))) {
    Write-Host 'Creating Python virtual environment...'
    Push-Location $backendDir
    python -m venv .venv
    Pop-Location
}

Write-Host 'Installing Python dependencies...'
Push-Location $backendDir
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Pop-Location

Write-Host 'Installing Node.js dependencies...'
Push-Location $frontendDir
if (-not (Test-Path 'node_modules')) {
    npm install
}
Pop-Location

$backendCommand = "cd `"$backendDir`"; & `"$backendDir\.venv\Scripts\uvicorn.exe`" app.main:app --reload --host 0.0.0.0 --port 8000"
$frontendCommand = "cd `"$frontendDir`"; npm run dev"

Write-Host 'Starting backend and frontend servers...'
Write-Host 'Backend: http://localhost:8000'
Write-Host 'Frontend: http://localhost:5174'
Write-Host 'Login: http://localhost:5174/login'
Write-Host ''
Write-Host 'Press Ctrl+C to stop both servers'

$backendProcess = Start-Process -FilePath powershell.exe -ArgumentList '-NoProfile', '-NoExit', '-Command', $backendCommand -NoNewWindow -PassThru
$frontendProcess = Start-Process -FilePath powershell.exe -ArgumentList '-NoProfile', '-NoExit', '-Command', $frontendCommand -NoNewWindow -PassThru

Write-Host 'Backend process ID:' $backendProcess.Id
Write-Host 'Frontend process ID:' $frontendProcess.Id
Write-Host 'Waiting for the dev servers to stop...'

Wait-Process -Id $backendProcess.Id, $frontendProcess.Id
