$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "          Contract Review Platform" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check MySQL
Write-Host "[1/4] Checking MySQL..." -ForegroundColor Yellow
$mysqlOk = $false
try {
    $result = mysqladmin ping -u root -pzjj2005225 --silent 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] MySQL connected" -ForegroundColor Green
        $mysqlOk = $true
    } else {
        throw "ping failed"
    }
} catch {
    Write-Host "  [WARN] MySQL not reachable, continuing anyway..." -ForegroundColor DarkYellow
}
Write-Host ""

# 2. Python FastAPI
Write-Host "[2/4] Starting Python AI (port 8000)..." -ForegroundColor Yellow
$pythonJob = Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$ROOT\python-agent`" && .venv\Scripts\python.exe -m uvicorn server:app --port 8000 --reload" -WindowStyle Normal
Write-Host "  [OK] Python AI started" -ForegroundColor Green
Write-Host ""

# 3. Spring Boot
Write-Host "[3/4] Starting Java backend (port 8080)..." -ForegroundColor Yellow
$javaJob = Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$ROOT\java-backend`" && mvn spring-boot:run" -WindowStyle Normal
Write-Host "  [OK] Java started (first build may take a moment)" -ForegroundColor Green
Write-Host ""

# 4. Vue Frontend
Write-Host "[4/4] Starting Vue frontend (port 5173)..." -ForegroundColor Yellow
$vueJob = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$ROOT\vue-frontend`" && npm run dev" -WindowStyle Normal
Write-Host "  [OK] Vue started" -ForegroundColor Green
Write-Host ""

# Wait
Write-Host "Waiting for services to start (15s)..." -ForegroundColor DarkGray
Start-Sleep -Seconds 15

# Open browser
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  All services started!" -ForegroundColor Cyan
Write-Host "  Opening http://localhost:5173" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Start-Process "http://localhost:5173"
Write-Host ""
Write-Host "Close each cmd window to stop its service."
Write-Host "Press any key to exit this script..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
