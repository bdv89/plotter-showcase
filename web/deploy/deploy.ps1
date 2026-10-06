# deploy.ps1 — Deploie la BETA ou la PROD a partir de git. A LANCER EN ADMINISTRATEUR.
#
#   .\deploy.ps1 -Target beta                    # beta = copie de travail git (...\260324-exp)
#   .\deploy.ps1 -Target prod -Tag v0.3.0        # prod = version taguee (...\260324)
#   ajouter -Force pour ne pas demander de confirmation
#
# Deux dossiers, deux services, un seul depot git (origin) :
#
#   | Cible | Dossier      | Code deploye                                  | Service        | Port | URL           |
#   |-------|--------------|-----------------------------------------------|----------------|------|---------------|
#   | beta  | ...\260324-exp | ce qui est dans la copie de travail (on y code) | CSVPlotter_Exp | 9199 | /plotter-exp/ |
#   | prod  | ...\260324   | un TAG git, checkout en lecture seule        | CSVPlotter     | 9099 | /plotter/     |
#
# Etapes (identiques pour les deux, sauf le checkout du tag en prod) :
#   1. prod seulement : refuse si le dossier prod a des modifications suivies, puis
#      git fetch + checkout --detach du tag (on ne code JAMAIS dans le dossier prod)
#   2. service ARRETE, puis pip install (venv_win) — sinon uvicorn.exe est verrouille (vecu le 15/09)
#   3. npm install + build avec le bon sous-chemin (check-build.mjs valide base et URL d'API)
#   4. service relance QUOI QU'IL ARRIVE, health check, et controle de la version servie
#
# Remplace promote-dev-to-beta.ps1 et promote-exp-to-prod.ps1 (copies robocopy entre dossiers).

param(
    [Parameter(Mandatory = $true)][ValidateSet('beta', 'prod')][string]$Target,
    [string]$Tag = '',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "Lance ce script en ADMINISTRATEUR." -ForegroundColor Red; exit 1 }

# Les deux dossiers sont freres : ...\260324 (prod) et ...\260324-exp (beta), quel que soit
# celui d'ou le script est lance.
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$parent   = Split-Path $repoRoot -Parent
$cfg = @{
    beta = @{ Root = Join-Path $parent '260324-exp'; Service = 'CSVPlotter_Exp'; Port = 9199; Base = '/plotter-exp/' }
    prod = @{ Root = Join-Path $parent '260324';     Service = 'CSVPlotter';     Port = 9099; Base = '/plotter/' }
}[$Target]
$root = $cfg.Root
$web  = Join-Path $root 'web'

if (-not (Test-Path (Join-Path $root '.git'))) {
    Write-Host "$root n'est pas un depot git (voir DEPLOY.md, « Mise en place »)." -ForegroundColor Red
    exit 1
}
if ($Target -eq 'prod' -and -not $Tag) {
    Write-Host "La prod se deploie depuis un tag : -Tag vX.Y.Z" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Deploiement $($Target.ToUpper()) ===" -ForegroundColor Cyan
Write-Host "Dossier : $root"
Write-Host "Service : $($cfg.Service) (port $($cfg.Port), $($cfg.Base))"
if ($Tag) { Write-Host "Version : $Tag" }
if (-not $Force) {
    $ans = Read-Host "Continuer ? (o/N)"
    if ($ans -notmatch '^[oOyY]') { Write-Host "Annule." -ForegroundColor Yellow; exit 0 }
}

# --- 1. prod : checkout du tag ---
if ($Target -eq 'prod') {
    Write-Host "[1/4] git fetch + checkout $Tag..." -ForegroundColor Cyan
    $dirty = & git -C $root status --porcelain --untracked-files=no
    if ($dirty) {
        Write-Host "Le dossier prod a des modifications suivies : on ne code pas dans la prod." -ForegroundColor Red
        Write-Host ($dirty -join "`n")
        exit 1
    }
    & git -C $root fetch --tags --force origin
    if ($LASTEXITCODE -ne 0) { Write-Host "git fetch a echoue." -ForegroundColor Red; exit 1 }
    & git -C $root rev-parse --verify --quiet "refs/tags/$Tag" | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "Tag $Tag introuvable sur origin (git push origin $Tag ?)." -ForegroundColor Red; exit 1 }
    & git -C $root checkout --detach $Tag
    if ($LASTEXITCODE -ne 0) { Write-Host "git checkout a echoue." -ForegroundColor Red; exit 1 }
} else {
    Write-Host "[1/4] beta : code de la copie de travail ($(& git -C $root describe --tags --always --dirty))" -ForegroundColor Cyan
}

# --- 2-3. service arrete : dependances + build ---
$venvPy = Join-Path $web 'backend\venv_win\Scripts\python.exe'
if (-not (Test-Path $venvPy)) { Write-Host "venv introuvable : $venvPy" -ForegroundColor Red; exit 1 }

Write-Host "Arret du service $($cfg.Service)..." -ForegroundColor Cyan
Stop-Service -Name $cfg.Service -Force
try {
    Write-Host "[2/4] pip install (venv_win)..." -ForegroundColor Cyan
    # PAS de --quiet : il masque le message d'erreur de pip (vecu le 15/09).
    & $venvPy -m pip install --disable-pip-version-check -r (Join-Path $web 'backend\requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "pip install a echoue (code $LASTEXITCODE)." }

    Write-Host "[3/4] build frontend (base=$($cfg.Base))..." -ForegroundColor Cyan
    Push-Location (Join-Path $web 'frontend')
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install a echoue (code $LASTEXITCODE)." }
        $env:VITE_API_URL = "$($cfg.Base)api"
        npm run build -- "--base=$($cfg.Base)"
        if ($LASTEXITCODE -ne 0) { throw "npm run build a echoue (code $LASTEXITCODE)." }
    } finally {
        Pop-Location
    }
} finally {
    Write-Host "[4/4] Demarrage du service $($cfg.Service)..." -ForegroundColor Cyan
    Start-Service -Name $cfg.Service
}

Start-Sleep -Seconds 3
try {
    $health  = Invoke-RestMethod -Uri "http://127.0.0.1:$($cfg.Port)/api/health" -TimeoutSec 10
    $version = (Invoke-RestMethod -Uri "http://127.0.0.1:$($cfg.Port)/openapi.json" -TimeoutSec 10).info.version
} catch {
    Write-Host "Service relance mais health check KO : $_" -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "$($Target.ToUpper()) deployee : version $version, sante $($health.status), SHARE_PATH='$($health.share_path)'" -ForegroundColor Green
if ($Tag -and "v$version" -ne $Tag) {
    Write-Host "ATTENTION : le tag $Tag ne correspond pas a la version servie ($version)." -ForegroundColor Yellow
}
if (-not $health.share_path) {
    Write-Host "SHARE_PATH vide : Watch et le MCP ne peuvent pas lire de fichiers (DEPLOY.md, variables)." -ForegroundColor Yellow
}
Write-Host "Ctrl+Shift+R sur $($cfg.Base) pour charger les nouveaux fichiers." -ForegroundColor Yellow
