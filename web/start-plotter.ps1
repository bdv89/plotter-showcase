# start-plotter.ps1 — Lance Plotter accessible sur le LAN (backend + frontend)
# Usage :  .\start-plotter.ps1            (ports par défaut)
#          .\start-plotter.ps1 -BackendPort 9099 -FrontendPort 5174
# Ouvre 2 fenêtres PowerShell (logs backend / frontend). Ctrl+C dans chacune pour stopper.
#
# Pare-feu (une seule fois, PowerShell admin) — ouvrir les ports entrants :
#   New-NetFirewallRule -DisplayName "Plotter_Frontend" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5174
#   New-NetFirewallRule -DisplayName "Plotter_Backend"  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9099

param(
    [int]$BackendPort = 9099,
    [int]$FrontendPort = 5174
)

$root        = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir  = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'

if (-not (Test-Path (Join-Path $backendDir 'venv_win\Scripts\uvicorn.exe'))) {
    Write-Host "venv backend introuvable. Crée-le d'abord :" -ForegroundColor Red
    Write-Host "  cd backend; python -m venv venv_win; .\venv_win\Scripts\Activate.ps1; pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    Write-Host "Dépendances frontend manquantes. Lance d'abord : cd frontend; npm install" -ForegroundColor Red
    exit 1
}

# --- Détecte l'IP LAN (IPv4 Ethernet/Wi-Fi, hors loopback/APIPA) ---
$lanIP = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.InterfaceAlias -match 'Ethernet|Wi-Fi' -and
        $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'
    } | Select-Object -First 1).IPAddress
if (-not $lanIP) { $lanIP = 'localhost' }

$apiUrl = "http://${lanIP}:${BackendPort}/api"

Write-Host ""
Write-Host "=== Plotter (LAN) ===" -ForegroundColor Cyan
Write-Host "IP LAN   : $lanIP" -ForegroundColor Green
Write-Host "Backend  : http://${lanIP}:${BackendPort}" -ForegroundColor Green
Write-Host "Frontend : http://${lanIP}:${FrontendPort}   <- à ouvrir depuis les autres PC" -ForegroundColor Green
Write-Host ""

# Backend sur 0.0.0.0 — PYTHONUTF8 évite le crash des prints emoji (console Windows)
Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "`$env:PYTHONUTF8='1'; `$env:PYTHONIOENCODING='utf-8'; Set-Location '$backendDir'; & '.\venv_win\Scripts\uvicorn.exe' main:app --reload --host 0.0.0.0 --port $BackendPort"
)

# Frontend sur 0.0.0.0 — VITE_API_URL pointe vers le backend par l'IP LAN
Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "`$env:VITE_API_URL='$apiUrl'; Set-Location '$frontendDir'; npm run dev -- --host 0.0.0.0 --port $FrontendPort"
)

Start-Sleep -Seconds 3
Start-Process "http://localhost:${FrontendPort}/"
