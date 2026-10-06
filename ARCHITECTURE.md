# Architecture (LLM‑ready)

But : fournir une vue d'ensemble courte et reliée au code pour aider humains et
LLMs à comprendre le projet **web** (FastAPI + React) sans complexité inutile.

> L'**architecture détaillée** (slices d'état, endpoints, format de pool, pièges)
> vit dans **[README.md](README.md)**, **[PITFALLS.md](PITFALLS.md)** et les docstrings du code. Ce fichier
> ne fait que pointer dessus — pas de duplication.
>
> Une ancienne app **desktop PyQt5** occupait la racine du dépôt ; elle a été
> archivée (tag git `legacy-desktop-2026-06-21`) et retirée de l'arbre. Sa doc
> (cartographie des modules, diagrammes Mermaid, séquences) est conservée sous
> **[docs/legacy/](docs/legacy/)**.

## Schéma d'ensemble

```
Navigateur                          Serveur
┌────────────────────┐     REST     ┌──────────────────────┐
│ React + TypeScript │ ←──────────→ │ FastAPI (Python)     │
│ Plotly.js (charts) │   /api/*     │  api/   (routers)    │
│ Zustand (state)    │  X-Session-Id│  core/  (traitement) │
│ Vite (build)       │              │  models/(schemas)    │
└────────────────────┘              └────────┬─────────────┘
                                             │  1 AppState / session
                                    ┌────────▼─────────────┐
                                    │ <sid>.db (SQLite)    │
                                    │ CSV/Excel uploadés   │
                                    └──────────────────────┘
```

## Cartographie rapide (web)

- **Backend API** : `web/backend/api/` — `upload`, `plot`, `extract`, `pool`, `metrics`
  (routers, tous scopés par session via le header `X-Session-Id`, sauf `metrics`).
  Il n'y a **pas** de router `process` : le traitement est appliqué **en ligne** par
  `plot` et `extract` (cf. [PITFALLS.md](PITFALLS.md) #34).
- **Backend Core** : `web/backend/core/` — `processing` (l'unique `apply_processing`),
  `extraction`, `denoise_methods`, `baseline_correction`, `data_loader`, `data_utils`,
  `db_schema`, `metrics`.
- **MCP** : `web/backend/mcp_server.py` — pilotage du backend par une LLM, monté sur `/mcp`.
- **Sessions / état** : `web/backend/sessions.py` (`SessionManager` multi-tenant,
  LRU RAM + persistance `<sid>.db` + TTL) et `web/backend/state.py` (`AppState` par session).
- **Frontend** : `web/frontend/src/components/` (FileTable, ColumnSelector, PlotView,
  PlotSettings, ProcessingPanel, ExtractPanel, StatsBar, StatsTable, SeriesPicker,
  StyleBar, MetricsView, HelpModal) + `src/store/appStore.ts` (Zustand)
  + `src/api/client.ts` + `src/utils/` (coloring, stats, clipboard…).

→ Détail des endpoints, des slices Zustand, du format `.db` et des conventions
cross-stack : docstrings de `web/backend/` et `web/frontend/src/store/appStore.ts`. Déploiement (nginx, NSSM, 3 environnements) :
**[web/deploy/DEPLOY.md](web/deploy/DEPLOY.md)**.

## Gabarit de docstrings

- `docs/docstring_template.md` — style de docstrings Python pour les APIs clés.

## Évolution minimale (rasoir d'Ockham)

1. Supprimer le code mort / les noms ambigus pour réduire la doc nécessaire.
2. Vérifier les imports avec un grep (`rg -n "^(from|import) "`) plutôt que de
   dessiner des diagrammes à la main.
3. Modifier a minima : types/docstrings là où c'est ambigu, et pointer vers les fichiers.
