# publish-showcase.ps1 — Publie une version taguee sur la vitrine publique (github.com/bdv89/plotter-showcase).
#
#   .\tools\publish-showcase.ps1 -Tag v0.3.0            # controle anti-fuite puis publication
#   .\tools\publish-showcase.ps1 -Tag v0.3.0 -DryRun    # controle seulement
#
# Le depot prive (origin) et la vitrine partagent le MEME historique : tout ce qui est commite
# dans le prive devient public a la publication suivante. Ce script refuse donc de publier si
# l'historique jusqu'au tag contient une information interne :
#   - chaines : email professionnel, chemins D:\restart, IP internes du LAN (10.108.*), nom du proxy interne
#     (en majuscules : nom du reverse-proxy interne ; "Materia Nova" en casse normale est autorise) ;
#   - fichiers : instructions d'assistants IA (CLAUDE*.md, AGENTS.md, .claude/), pools et
#     donnees (*.db, *.dpool, *.xls*, *.csv hors examples/demo-data), fichiers _tmp_*.
# En cas d'alerte : retirer l'information du depot (et si elle est deja dans l'historique,
# reecrire l historique avec git filter-repo, cf. web/deploy/DEPLOY.md) avant de republier.

param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$showcaseUrl = 'https://github.com/bdv89/plotter-showcase.git'

& git -C $repo rev-parse --verify --quiet "refs/tags/$Tag" | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Tag $Tag introuvable." -ForegroundColor Red; exit 1 }

$contentPatterns = @(
    '(?i)@materianova\.be',
    '(?i)\b[a-z]:[\\/]+restart[\\/]',
    '\b10\.108\.\d+\.\d+',
    '\bMATERIA\b'
)
$filePatterns = @(
    '(^|/)CLAUDE[^/]*\.md$', '(^|/)AGENTS\.md$', '(^|/)\.claude/',
    '\.(db|dpool|xlsx?)$', '(^|/)_tmp_'
)
$allowedCsv = '^(examples/demo-data/[^/]+|test_denoising)\.csv$|^examples/demo-data/'

Write-Host "Controle anti-fuite de l'historique jusqu'a $Tag..." -ForegroundColor Cyan
$problems = @()

# Contenu de tous les commits (diffs, messages, auteurs).
$log = & git -C $repo log -p --format='commit %H%nauthor %an <%ae>%ncommitter %cn <%ce>%n%B' $Tag
foreach ($p in $contentPatterns) {
    $hits = $log | Select-String -CaseSensitive -Pattern $p | Select-Object -First 3
    foreach ($h in $hits) { $problems += "contenu [$p] : $($h.Line.Trim())" }
}

# Noms de fichiers ayant existe dans l'historique.
$names = & git -C $repo log --name-only --format= $Tag | Where-Object { $_ } | Sort-Object -Unique
foreach ($n in $names) {
    foreach ($p in $filePatterns) { if ($n -match $p) { $problems += "fichier : $n" } }
    if ($n -match '\.csv$' -and $n -notmatch $allowedCsv) { $problems += "fichier de donnees : $n" }
}

if ($problems) {
    Write-Host "PUBLICATION REFUSEE : $($problems.Count) alerte(s)" -ForegroundColor Red
    $problems | Select-Object -Unique | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host "Aucune information interne detectee." -ForegroundColor Green
if ($DryRun) { exit 0 }

if (-not (& git -C $repo remote | Select-String -SimpleMatch -Pattern 'showcase')) {
    & git -C $repo remote add showcase $showcaseUrl
}
& git -C $repo push showcase "$Tag^{commit}:refs/heads/main"
if ($LASTEXITCODE -ne 0) { Write-Host "Push de main vers la vitrine refuse." -ForegroundColor Red; exit 1 }
& git -C $repo push showcase "refs/tags/$Tag"
if ($LASTEXITCODE -ne 0) { Write-Host "Push du tag vers la vitrine refuse." -ForegroundColor Red; exit 1 }
Write-Host "Vitrine publiee : $Tag -> $showcaseUrl" -ForegroundColor Green
