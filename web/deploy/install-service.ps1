# install-service.ps1 — Installe le backend Plotter en service Windows via NSSM.
# À LANCER EN ADMINISTRATEUR.
#
#   powershell -ExecutionPolicy Bypass -File .\install-service.ps1
#   .\install-service.ps1 -Port 9099 -DataDir C:\ProgramData\Plotter
#
# Désinstaller :
#   nssm stop   CSVPlotter
#   nssm remove CSVPlotter confirm
#
# Prérequis : NSSM installé (https://nssm.cc). Indique son chemin avec -NssmPath
# s'il n'est pas dans le PATH. Le venv backend doit exister (venv_win).

param(
    [string]$ServiceName = 'CSVPlotter',   # = task_name attendu par le services dashboard
    [int]   $Port        = 9099,
    [string]$NssmPath    = 'nssm',
    [string]$DataDir     = 'C:\ProgramData\Plotter',
    [string]$SharePath   = ''                       # optionnel : share réseau pour les pools
)

$ErrorActionPreference = 'Stop'

# --- Admin requis ---
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "Lance ce script en ADMINISTRATEUR." -ForegroundColor Red; exit 1 }

# --- Chemins ---
$deployDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Resolve-Path (Join-Path $deployDir '..\backend')
$uvicorn    = Join-Path $backendDir 'venv_win\Scripts\uvicorn.exe'
$logDir     = Join-Path $DataDir 'logs'
$uploadDir  = Join-Path $DataDir 'uploads'
$sessionDir = Join-Path $uploadDir 'sessions'

if (-not (Test-Path $uvicorn)) {
    Write-Host "uvicorn introuvable : $uvicorn" -ForegroundColor Red
    Write-Host "Crée le venv : cd backend; python -m venv venv_win; .\venv_win\Scripts\Activate.ps1; pip install -r requirements.txt"
    exit 1
}
if (-not (Get-Command $NssmPath -ErrorAction SilentlyContinue)) {
    Write-Host "NSSM introuvable ('$NssmPath'). Installe-le ou passe -NssmPath C:\path\nssm.exe" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $logDir, $uploadDir, $sessionDir | Out-Null

# --- (Ré)installation propre ---
& $NssmPath stop   $ServiceName 2>$null
& $NssmPath remove $ServiceName confirm 2>$null

Write-Host "Installation du service '$ServiceName'…" -ForegroundColor Cyan
# 1 worker (défaut), PAS de --reload, bind localhost (nginx fait le front).
& $NssmPath install $ServiceName "$uvicorn" "main:app --host 127.0.0.1 --port $Port"
& $NssmPath set $ServiceName AppDirectory "$backendDir"

# Variables d'environnement (chemins Windows + UTF-8 anti-crash prints emoji)
$envLines = @(
    'PYTHONUTF8=1'
    'PYTHONIOENCODING=utf-8'
    "UPLOAD_DIR=$uploadDir"
    "SESSIONS_DIR=$sessionDir"
)
if ($SharePath) { $envLines += "SHARE_PATH=$SharePath" }
& $NssmPath set $ServiceName AppEnvironmentExtra ($envLines -join "`r`n")

# Logs + rotation
& $NssmPath set $ServiceName AppStdout (Join-Path $logDir 'backend.out.log')
& $NssmPath set $ServiceName AppStderr (Join-Path $logDir 'backend.err.log')
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateOnline 1
& $NssmPath set $ServiceName AppRotateBytes 10485760     # 10 Mo

# Démarrage auto au boot ; restart-on-crash = défaut NSSM
& $NssmPath set $ServiceName Start SERVICE_AUTO_START

& $NssmPath start $ServiceName
Start-Sleep -Seconds 2
& $NssmPath status $ServiceName

Write-Host ""
Write-Host "Backend : http://127.0.0.1:$Port  (santé : /api/health)" -ForegroundColor Green
Write-Host "Données : $DataDir   Logs : $logDir" -ForegroundColor Green
Write-Host "nginx : sert dist/ sous /plotter/ + proxy /plotter/api → 127.0.0.1:$Port (voir services-plotter.conf + DEPLOY.md)" -ForegroundColor Yellow
