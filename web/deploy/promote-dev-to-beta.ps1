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
Write-Host "[1/4] Copie du code dev -> beta…" -ForegroundColor Cyan
& robocopy $DevWeb $BetaWeb /MIR /R:1 /W:1 /NP /XJ `
    /XD venv venv_win node_modules dist __pycache__ uploads logs .git .jj `
    /XF *.log
if ($LASTEXITCODE -ge 8) {          # robocopy : 0-7 = succès, >=8 = échec
    Write-Host "robocopy a échoué (code $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}

# --- 2-3. Service ARRETE : sync des dependances backend + rebuild du frontend ---
# Le venv est EXCLU du robocopy : sans ce pip install, requirements.txt est promu mais
# jamais applique, et une nouvelle dependance (ex. le serveur MCP) empeche main.py de
# s'importer — le service ne redemarre plus DU TOUT.
# Le service est arrete AVANT pip : tant qu'il tourne, venv_win\Scripts\uvicorn.exe est
# verrouille et toute montee de version d'uvicorn echoue en WinError 32 (vecu le 15/09).
# Il est relance quoi qu'il arrive (finally), meme si pip ou le build echoue.
$venvPy = Join-Path $BetaWeb 'backend\venv_win\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host "venv introuvable : $venvPy" -ForegroundColor Red
    exit 1
}
Write-Host "Arret du service CSVPlotter_Exp (libere les binaires du venv)..." -ForegroundColor Cyan
Stop-Service -Name 'CSVPlotter_Exp' -Force
try {
    Write-Host "[2/4] Sync des dependances backend (venv_win)..." -ForegroundColor Cyan
    # PAS de --quiet : il masque le message d'erreur de pip. Vecu le 15/09 — l'echec
    # (uvicorn.exe verrouille) n'a rien affiche et le script s'est arrete sans rien dire.
    & $venvPy -m pip install --disable-pip-version-check -r (Join-Path $BetaWeb 'backend\requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "pip install a echoue (code $LASTEXITCODE)." }

    # --- 3. Rebuild du frontend beta pour le sous-chemin /plotter-exp/ ---
    Write-Host "[3/4] Build frontend beta (base=/plotter-exp/)…" -ForegroundColor Cyan
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
} finally {
    # --- 4. Démarrage du backend beta (toujours) + health check ---
    Write-Host "[4/4] Démarrage du service CSVPlotter_Exp…" -ForegroundColor Cyan
    Start-Service -Name 'CSVPlotter_Exp'
}
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
