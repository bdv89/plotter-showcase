# start-lan.ps1 — Lance backend + frontend avec acces LAN
# Usage: .\start-lan.ps1
# Note: ouvrir les ports firewall manuellement (PowerShell admin) :
#   New-NetFirewallRule -DisplayName "CSVPlotter_Frontend" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5173
#   New-NetFirewallRule -DisplayName "CSVPlotter_Backend" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8099

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$venvActivate = Join-Path $backendDir "venv_win\Scripts\Activate.ps1"

# Ports
$backendPort = 8099
$frontendPort = 5173

# --- Detect LAN IP ---
$lanIP = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.InterfaceAlias -eq "Ethernet" -or $_.InterfaceAlias -eq "Wi-Fi" } |
    Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "=== CSV Plotter - LAN Mode ===" -ForegroundColor Cyan
Write-Host "LAN IP: $lanIP" -ForegroundColor Green
Write-Host "Frontend: http://${lanIP}:${frontendPort}" -ForegroundColor Green
Write-Host "Backend:  http://${lanIP}:${backendPort}" -ForegroundColor Green
Write-Host ""

# --- Start backend (hidden window) ---
Write-Host "Starting backend..." -ForegroundColor Yellow
$backendJob = Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-Command",
    "`$env:PYTHONUTF8='1'; `$env:PYTHONIOENCODING='utf-8'; Set-Location '$backendDir'; & '$venvActivate'; uvicorn main:app --reload --host 0.0.0.0 --port $backendPort"
) -PassThru

# --- Start frontend (hidden window) ---
Write-Host "Starting frontend..." -ForegroundColor Yellow
$frontendJob = Start-Process cmd -WindowStyle Hidden -ArgumentList @(
    "/c", "cd /d `"$frontendDir`" && npx vite --host 0.0.0.0"
) -PassThru

Write-Host ""
Write-Host "Both servers started." -ForegroundColor Green
Write-Host "Access from another PC: http://${lanIP}:${frontendPort}" -ForegroundColor Cyan
Write-Host "Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

try {
    while ($true) {
        if ($backendJob.HasExited -and $frontendJob.HasExited) { break }
        Start-Sleep -Seconds 2
    }
} finally {
    Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue
    Write-Host "Servers stopped." -ForegroundColor Green
}
