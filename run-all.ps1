# ═══════════════════════════════════════════════════════════════
# He thong quan ly ke toan noi bo — Master Startup Script (Windows)
# ═══════════════════════════════════════════════════════════════
# Khoi dong Backend (FastAPI - Port 8000) va Frontend (Vite/React - Port 5173)
# 
# Cach su dung:
#   .\run-all.ps1
# ═══════════════════════════════════════════════════════════════

$root = $PSScriptRoot

Write-Host ""
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   He thong Quan ly Ke toan - Khoi tao Full BE & FE   " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Backend (ketoan-backend) ─────────────────────────────
$beDir = Join-Path $root "ketoan-backend"
$beEnv = Join-Path $beDir ".env"
$beEnvExample = Join-Path $beDir ".env.example"
$beVenv = Join-Path $beDir "venv"
$bePy = Join-Path $beVenv "Scripts\python.exe"

Write-Host "[1/2] Kiem tra & Cau hinh Backend (ketoan-backend)..." -ForegroundColor Yellow

if (-not (Test-Path $beEnv) -and (Test-Path $beEnvExample)) {
    Copy-Item $beEnvExample $beEnv
    Write-Host "      + Da tao file .env tu .env.example" -ForegroundColor Green
}

if (-not (Test-Path $bePy)) {
    Write-Host "      + Dang tao virtual environment (venv)..." -ForegroundColor Yellow
    python -m venv $beVenv
    if (Test-Path $bePy) {
        Write-Host "      + Dang cai dat thu vien Python tu requirements.txt..." -ForegroundColor Yellow
        & $bePy -m pip install -r (Join-Path $beDir "requirements.txt")
    } else {
        Write-Host "      [!] Khong tim thay Python de tao venv. Hay kiem tra cai dat Python!" -ForegroundColor Red
    }
}

# Thu Alembic Migration & Seed data
if (Test-Path $bePy) {
    Write-Host "      + Dang kiem tra Database Migration & Seed Data..." -ForegroundColor Yellow
    try {
        Push-Location $beDir
        & $bePy -m alembic upgrade head 2>$null
        & $bePy -m scripts.seed_initial_data 2>$null
    } catch {
        Write-Host "      [i] Luu y: Khong the migrate DB tu dong (co the PostgreSQL chua khoi chay)." -ForegroundColor DarkYellow
    } finally {
        Pop-Location
    }
}

Write-Host "      => Khoi dong Backend tai http://localhost:8000" -ForegroundColor Green
Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "cd '$beDir'; if (Test-Path '$bePy') { & '$bePy' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 } else { python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 }" `
    -WorkingDirectory $beDir

Start-Sleep -Seconds 2

# ── 2. Frontend (ketoan-frontend) ────────────────────────────
$feDir = Join-Path $root "ketoan-frontend"
$feEnv = Join-Path $feDir ".env"
$feEnvExample = Join-Path $feDir ".env.example"

Write-Host "[2/2] Kiem tra & Cau hinh Frontend (ketoan-frontend)..." -ForegroundColor Yellow

if (-not (Test-Path $feEnv) -and (Test-Path $feEnvExample)) {
    Copy-Item $feEnvExample $feEnv
    Write-Host "      + Da tao file .env tu .env.example" -ForegroundColor Green
}

if (-not (Test-Path (Join-Path $feDir "node_modules"))) {
    Write-Host "      + Dang cai dat dependencies (npm install)..." -ForegroundColor Yellow
    Start-Process "cmd.exe" -ArgumentList "/c", "npm install" -WorkingDirectory $feDir -Wait -NoNewWindow
}

Write-Host "      => Khoi dong Frontend tai http://localhost:5173" -ForegroundColor Green
Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "cd '$feDir'; npm run dev" `
    -WorkingDirectory $feDir

Write-Host ""
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   Khoi dong hoan tat!" -ForegroundColor Green
Write-Host "   * Backend Swagger API: http://localhost:8000/docs" -ForegroundColor White
Write-Host "   * Frontend UI:          http://localhost:5173" -ForegroundColor White
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""
