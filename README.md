# CSV Plotter (web)

Application web pour charger des CSV/Excel, les tracer (Plotly), les traiter
(lissage, débruitage, baseline, normalisation, outliers), extraire des métriques
et les agréger en **statistiques par population** (n, moyenne, SD, CV%…).

**Stack** : FastAPI (Python) + React 19 / TypeScript / Vite / Zustand / Plotly.js.
Multi-tenant : un `AppState` par session de navigateur, persisté en `<sid>.db` (SQLite).

> Une ancienne app **desktop PyQt5** vivait à la racine de ce dépôt. Elle a été
> archivée (tag git `legacy-desktop-2026-06-21`) et retirée de l'arbre — seule la
> web app sous `web/` est maintenue.

## Démarrage rapide (dev)

```powershell
# Prérequis (une fois)
cd web\frontend; npm install
cd ..\backend;  python -m venv venv_win; .\venv_win\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

# Lancer (backend 9099 + Vite 5174, ouvre le navigateur)
cd web
.\start-plotter.ps1
```

→ http://localhost:5174

## Les 3 environnements

| Env  | URL              | Port | Dossier        |
|------|------------------|------|----------------|
| dev  | `localhost:5174` | 9099 | `…\260324\web`     |
| beta | `…/plotter-exp/` | 9199 | `…\260324-exp\web` |
| prod | `…/plotter/`     | 9099 | `…\260324\web`     |

Promotion **dev → beta → prod** via `web/deploy/promote-*.ps1`. Détails complets,
nginx et services NSSM : **[web/deploy/DEPLOY.md](web/deploy/DEPLOY.md)**.

## Piloter depuis une LLM

Le backend monte un **serveur MCP** sur `/mcp` : une LLM peut charger des fichiers, tracer,
extraire et calculer les statistiques par population. Rien à installer côté client —
le panneau d'aide (`?`) de l'app affiche la commande :

```
claude mcp add --transport http plotter http://<serveur>/plotter/mcp
```

Les données entrent par le dossier partagé `SHARE_PATH` (le serveur ne voit pas le disque
des utilisateurs) et ressortent en pool `.db`, à rouvrir avec **Load**. Détails et pièges :
section « Piloter depuis une LLM » de [CLAUDE.md](CLAUDE.md).

## Structure

```
web/backend/    FastAPI : api/ (routers), core/ (traitement), models/ (schemas), main.py, mcp_server.py
web/frontend/   React/Vite : src/components, src/store (Zustand), src/api
web/deploy/     Scripts de déploiement (NSSM, nginx, promote)
tests/          Tests pytest du backend (voir ci-dessous)
docs/           Notes techniques ; docs/legacy/ = doc de l'app desktop archivée
```

## Tests

```powershell
# Backend — depuis la racine du dépôt (conftest.py met web/backend sur le sys.path)
python -m pytest

# Frontend — Vitest (store + utils/stats)
cd web\frontend; npm test
```

Le backend couvre `core/` (denoise, baseline, format de pool SQLite) ; les tests
wavelet sont skippés si PyWavelets n'est pas installé dans l'interpréteur courant.
Le frontend couvre le **store** et `utils/stats` — là où le calcul vit (populations,
moyenne/SD, restauration d'un pool). Le rendu Plotly, lui, se vérifie dans le
navigateur : cf. la note sur la fidélité des stats dans [CLAUDE.md](CLAUDE.md).

## Lint / format

```powershell
cd web\backend && ruff check . && black .   # config dans pyproject.toml (racine)
cd web\frontend && npm run lint              # ESLint
```

## Releases

Versioning **sémantique** (`vX.Y.Z`), source de vérité = `web/backend/main.py`
(`FastAPI(version=...)`). Pour publier :

1. Bump la version dans `web/backend/main.py`.
2. `git tag vX.Y.Z` sur le commit promu en prod.
3. Déployer via `web/deploy/promote-exp-to-prod.ps1`.

## Docs de référence

- **[CLAUDE.md](CLAUDE.md)** — architecture détaillée + conventions
- **[PITFALLS.md](PITFALLS.md)** — pièges connus et solutions
- **[web/deploy/DEPLOY.md](web/deploy/DEPLOY.md)** — déploiement nginx/NSSM
