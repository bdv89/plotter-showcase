# promote-dev-to-beta.ps1 — Pousse le code DEV (...\260324, testé en local sur :5174) vers la BETA (/plotter-exp/, 9199).
# À LANCER EN ADMINISTRATEUR (redémarre le service Windows CSVPlotter_Exp).
#
#   powershell -ExecutionPolicy Bypass -File .\promote-dev-to-beta.ps1
#   .\promote-dev-to-beta.ps1 -Force            # sans confirmation
#
# Ce que fait le script :
#   1. robocopy   ...\260324\web  ->  ...\260324-exp\web   (code source, hors artefacts régénérables)
#   2. rebuild    frontend beta avec base=/plotter-exp/ + VITE_API_URL=/plotter-exp/api
#   3. restart    service CSVPlotter_Exp (9199)  +  health check
#
# La prod (9099, ...\260324, /plotter/) n'est JAMAIS touchée.
# Les données beta (C:\ProgramData\Plotter_Exp) non plus : elles vivent hors de web\.

param(
    [string]$DevWeb  = '',          # défaut : ...\260324\web      (parent de ce dossier deploy)
    [string]$BetaWeb = '',          # défaut : ...\260324-exp\web  (déduit du chemin du script)
    [switch]$Force                  # ignore la confirmation
)

$ErrorActionPreference = 'Stop'

# --- Admin requis (Restart-Service) ---
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "Lance ce script en ADMINISTRATEUR." -ForegroundColor Red; exit 1 }

# --- Résolution des chemins ---
$deployDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $DevWeb)  { $DevWeb = (Resolve-Path (Join-Path $deployDir '..')).Path }         # ...\260324\web
if (-not $BetaWeb) {
    $devRoot = Split-Path $DevWeb -Parent                                                # ...\260324
    $BetaWeb = Join-Path "$devRoot-exp" 'web'                                            # ...\260324-exp\web
}

if (-not (Test-Path $BetaWeb)) {
    Write-Host "Copie beta introuvable : $BetaWeb" -ForegroundColor Red
    Write-Host "Fais d'abord l'install initiale de la beta (DEPLOY.md, section « Version expérimentale » §1-4)." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Promotion DEV -> BETA ===" -ForegroundColor Cyan
Write-Host "Source (dev)  : $DevWeb"  -ForegroundColor Yellow
Write-Host "Cible  (beta) : $BetaWeb" -ForegroundColor Yellow
Write-Host ""
if (-not $Force) {
    $ans = Read-Host "Écraser la beta avec le code dev, rebuild et relancer CSVPlotter_Exp ? (o/N)"
    if ($ans -notmatch '^[oOyY]') { Write-Host "Annulé." -ForegroundColor Yellow; exit 0 }
}

# --- 1. Copie code dev -> beta (mêmes exclusions que l'install/maj : artefacts régénérables) ---
# /MIR = miroir (supprime côté beta ce qui n'existe plus côté dev), hors dossiers exclus.
Write-Host "[1/3] Copie du code dev -> beta…" -ForegroundColor Cyan
& robocopy $DevWeb $BetaWeb /MIR /R:1 /W:1 /NP /XJ `
    /XD venv venv_win node_modules dist __pycache__ uploads logs .git .jj `
    /XF *.log
if ($LASTEXITCODE -ge 8) {          # robocopy : 0-7 = succès, >=8 = échec
    Write-Host "robocopy a échoué (code $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}

# --- 2. Rebuild du frontend beta pour le sous-chemin /plotter-exp/ ---
Write-Host "[2/3] Build frontend beta (base=/plotter-exp/)…" -ForegroundColor Cyan
Push-Location (Join-Path $BetaWeb 'frontend')
try {
    # Toujours (pas seulement si node_modules manque) : le dev peut avoir ajouté une dep
    # depuis la dernière promo → sinon `tsc -b` casse sur un module absent côté beta.
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install a échoué (code $LASTEXITCODE)." }
    $env:VITE_API_URL = '/plotter-exp/api'
    npm run build -- --base=/plotter-exp/
    if ($LASTEXITCODE -ne 0) { throw "npm run build a échoué (code $LASTEXITCODE)." }
} finally {
    Pop-Location
}

# --- 3. Redémarrage du backend beta + health check ---
Write-Host "[3/3] Redémarrage du service CSVPlotter_Exp…" -ForegroundColor Cyan
Restart-Service -Name 'CSVPlotter_Exp' -Force
Start-Sleep -Seconds 2
try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:9199/api/health' -TimeoutSec 5
    Write-Host ""
    Write-Host "Beta mise à jour. Santé : $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "Service relancé mais health check KO : $_" -ForegroundColor Red
    exit 1
}
Write-Host "Hard-refresh /plotter-exp/ dans le navigateur (Ctrl+Shift+R) pour charger les nouveaux assets." -ForegroundColor Yellow
