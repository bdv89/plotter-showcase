# promote-exp-to-prod.ps1 — Pousse la version BETA (/plotter-exp/, 9199) vers la PROD (/plotter/, 9099).
# À LANCER EN ADMINISTRATEUR (redémarre le service Windows CSVPlotter).
#
#   powershell -ExecutionPolicy Bypass -File .\promote-exp-to-prod.ps1
#   .\promote-exp-to-prod.ps1 -Force            # sans confirmation
#
# Ce que fait le script :
#   1. robocopy   ...\260324-exp\web  ->  ...\260324\web   (code source, hors artefacts régénérables)
#   2. rebuild    frontend prod avec base=/plotter/ + VITE_API_URL=/plotter/api
#   3. restart    service CSVPlotter (9099)  +  health check
#
# La beta (9199, ...\260324-exp) et ses données (C:\ProgramData\Plotter_Exp) ne sont PAS touchées.
# Les données prod (C:\ProgramData\Plotter) non plus : elles vivent hors de web\.

param(
    [string]$ExpWeb  = '',          # défaut : ...\260324-exp\web (déduit du chemin du script)
    [string]$ProdWeb = '',          # défaut : ...\260324\web      (parent de ce dossier deploy)
    [switch]$Force                  # ignore la confirmation
)

$ErrorActionPreference = 'Stop'

# --- Admin requis (Restart-Service) ---
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "Lance ce script en ADMINISTRATEUR." -ForegroundColor Red; exit 1 }

# --- Résolution des chemins ---
$deployDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ProdWeb) { $ProdWeb = (Resolve-Path (Join-Path $deployDir '..')).Path }     # ...\260324\web
if (-not $ExpWeb)  {
    $prodRoot = Split-Path $ProdWeb -Parent                                            # ...\260324
    $ExpWeb   = Join-Path "$prodRoot-exp" 'web'                                        # ...\260324-exp\web
}

if (-not (Test-Path (Join-Path $ExpWeb 'backend\main.py'))) {
    Write-Host "Copie beta introuvable : $ExpWeb" -ForegroundColor Red
    Write-Host "Vérifie le chemin (-ExpWeb) ou que la beta est bien déployée." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Promotion BETA -> PROD ===" -ForegroundColor Cyan
Write-Host "Source (beta) : $ExpWeb"  -ForegroundColor Yellow
Write-Host "Cible  (prod) : $ProdWeb" -ForegroundColor Yellow
Write-Host ""
if (-not $Force) {
    $ans = Read-Host "Écraser la prod avec le code de la beta, rebuild et relancer CSVPlotter ? (o/N)"
    if ($ans -notmatch '^[oOyY]') { Write-Host "Annulé." -ForegroundColor Yellow; exit 0 }
}

# --- 1. Copie code beta -> prod (mêmes exclusions que l'install/maj : artefacts régénérables) ---
# /MIR = miroir (supprime côté prod ce qui n'existe plus côté beta), hors dossiers exclus.
# On exclut ce script lui-même : sinon /MIR le supprimerait si la beta ne l'a pas encore.
Write-Host "[1/3] Copie du code beta -> prod…" -ForegroundColor Cyan
& robocopy $ExpWeb $ProdWeb /MIR /R:1 /W:1 /NP /XJ `
    /XD venv venv_win node_modules dist __pycache__ uploads logs .git .jj `
    /XF *.log promote-exp-to-prod.ps1
if ($LASTEXITCODE -ge 8) {          # robocopy : 0-7 = succès, >=8 = échec
    Write-Host "robocopy a échoué (code $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}

# --- 2. Rebuild du frontend prod pour le sous-chemin /plotter/ ---
Write-Host "[2/3] Build frontend prod (base=/plotter/)…" -ForegroundColor Cyan
Push-Location (Join-Path $ProdWeb 'frontend')
try {
    if (-not (Test-Path 'node_modules')) { npm install }
    $env:VITE_API_URL = '/plotter/api'
    npm run build -- --base=/plotter/
    if ($LASTEXITCODE -ne 0) { throw "npm run build a échoué (code $LASTEXITCODE)." }
} finally {
    Pop-Location
}

# --- 3. Redémarrage du backend prod + health check ---
Write-Host "[3/3] Redémarrage du service CSVPlotter…" -ForegroundColor Cyan
Restart-Service -Name 'CSVPlotter' -Force
Start-Sleep -Seconds 2
try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:9099/api/health' -TimeoutSec 5
    Write-Host ""
    Write-Host "Prod promue. Santé : $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "Service relancé mais health check KO : $_" -ForegroundColor Red
    exit 1
}
Write-Host "Hard-refresh /plotter/ dans le navigateur (Ctrl+Shift+R) pour charger les nouveaux assets." -ForegroundColor Yellow
