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
Write-Host "[1/4] Copie du code beta -> prod…" -ForegroundColor Cyan
& robocopy $ExpWeb $ProdWeb /MIR /R:1 /W:1 /NP /XJ `
    /XD venv venv_win node_modules dist __pycache__ uploads logs .git .jj `
    /XF *.log promote-exp-to-prod.ps1
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
$venvPy = Join-Path $ProdWeb 'backend\venv_win\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host "venv introuvable : $venvPy" -ForegroundColor Red
    exit 1
}
Write-Host "Arret du service CSVPlotter (libere les binaires du venv)..." -ForegroundColor Cyan
Stop-Service -Name 'CSVPlotter' -Force
try {
    Write-Host "[2/4] Sync des dependances backend (venv_win)..." -ForegroundColor Cyan
    # PAS de --quiet : il masque le message d'erreur de pip. Vecu le 15/09 — l'echec
    # (uvicorn.exe verrouille) n'a rien affiche et le script s'est arrete sans rien dire.
    & $venvPy -m pip install --disable-pip-version-check -r (Join-Path $ProdWeb 'backend\requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "pip install a echoue (code $LASTEXITCODE)." }

    # --- 3. Rebuild du frontend prod pour le sous-chemin /plotter/ ---
    Write-Host "[3/4] Build frontend prod (base=/plotter/)…" -ForegroundColor Cyan
    Push-Location (Join-Path $ProdWeb 'frontend')
    try {
        # Inconditionnel (comme cote beta) : une dep ajoutee depuis la derniere promo ne serait
        # jamais installee si on ne le lance que quand node_modules manque -> `tsc -b` casse.
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install a échoué (code $LASTEXITCODE)." }
        $env:VITE_API_URL = '/plotter/api'
        npm run build -- --base=/plotter/
        if ($LASTEXITCODE -ne 0) { throw "npm run build a échoué (code $LASTEXITCODE)." }
    } finally {
        Pop-Location
    }
} finally {
    # --- 4. Démarrage du backend prod (toujours) + health check ---
    Write-Host "[4/4] Démarrage du service CSVPlotter…" -ForegroundColor Cyan
    Start-Service -Name 'CSVPlotter'
}
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
