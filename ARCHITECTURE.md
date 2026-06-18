# Architecture (LLM‑ready)

But: fournir des artefacts textuels, petits et reliés au code pour aider humains et LLMs à comprendre le projet sans complexité inutile.

## Index rapide
- Dépendances modules: `docs/dep.md`
- Séquence clé "charger → traiter → tracer": `docs/seq-load-and-plot.md`
- Gabarit de docstrings: `docs/docstring_template.md`

## Portée et conventions
- Diagrammes textuels (Mermaid), versionnés près du code, ≤ 9 nœuds chacun.
- Nœuds nommés par chemin de fichier (ex: `main_app.py`) ou `pkg.mod#Symbole` si pertinent.
- Flèches `A --> B` signifient: A importe/appele B (vue statique simple).
- Une séquence par use case; flèches annotées avec opération + type I/O quand utile.

## Cartographie rapide des modules
- Core: `launcher.py`, `main_app.py`
- Données: `data_manager.py`, `data_pipeline.py`, `data_cache.py`, `storage_manager.py`, `db_schema.py`
- Plotting/UI: `plot_window.py`, `plot_canvas.py`, `plot_styles.py`, `plot_style_window.py`, `plot_dialog_components.py`, `plot_processing_window.py`, `plot_manager.py`, `ui_components.py`
- Parquet: `parquet_linker.py`, `parquet_linker_multi.py`

## Coloration/exports par série (rappel rapide)
- Détection série: `ui_components.FileStyleTableWidget.detect_series_from_filenames()` découpe le nom sur espace/underscore/tiret/`;`, lowercased. Par défaut: heuristique (numérique répété), bouton menu “Choisir le token de série…” permet de fixer l’index de token (prefixe = token 0).
- Coloration intelligente (Y1/Y2): menus de l’en-tête table appellent `apply_intelligent_coloring`/`apply_intelligent_y2_coloring` en se basant sur ces séries.
- Export batch par série: `plot_window.batch_export_per_series()` récupère les séries détectées, coche les lignes de la série, trace, puis sauvegarde. `_save_current_figure` nettoie les noms (caractères interdits Windows) avant écriture.

## Lecture des artefacts
- Commencer par `docs/dep.mmd` pour voir qui dépend de qui.
- Lire `docs/seq-load-and-plot.mmd` pour le flux utilisateur principal.
- Ajouter des docstrings en suivant `docs/docstring_template.md` sur les APIs clés.

## Web Architecture (Mai 2026)

Portage web de l’application desktop. Deux versions coexistent et partagent le format .db SQLite.

```
Navigateur                          Serveur
┌────────────────────┐     REST     ┌──────────────────────┐
│ React + TypeScript │ ←──────────→ │ FastAPI (Python)      │
│ Plotly.js (charts) │   /api/*     │                      │
│ Zustand (state)    │              │ core/pipeline.py     │
│ Vite (build)       │              │ core/extraction.py   │
└────────────────────┘              │ core/data_loader.py  │
                                    │ core/db_schema.py    │
                                    └────────┬─────────────┘
                                             │
                                    ┌────────▼─────────────┐
                                    │ Share réseau (.db)    │
                                    │ CSV uploadés          │
                                    └──────────────────────┘
```

### Cartographie web
- **Backend API**: `web/backend/api/` — upload, plot, process, extract, pool (5 routers ; **tous scopés par session**)
- **Backend Core**: `web/backend/core/` — pipeline, extraction, denoise, baseline, data_loader, db_schema
- **Sessions**: `web/backend/sessions.py` — `SessionManager` multi-tenant (header `X-Session-Id` → `AppState`), LRU RAM (16) + persistance disque `<sid>.db` + TTL/rétention ; `HEAVY_SEM` borne les jobs CPU
- **Frontend**: `web/frontend/src/components/` — FileTable, ColumnSelector, PlotView, PlotSettings (tuning : engrenage ⚙️ + clic-droit axes/légende + preset `.json`), ProcessingPanel, ExtractionModal *(FileUpload retiré : drop sur le bouton Load)*
- **State**: `web/frontend/src/store/appStore.ts` (Zustand) + `web/backend/state.py` (`AppState` **par session**)

### Sessions multi-tenant & déploiement
- **1 `AppState` par navigateur** via `X-Session-Id` (UUID localStorage) → isolation sur serveur central, **zéro install** côté postes. Sessions chaudes en RAM (LRU `MAX_SESSIONS_IN_MEMORY`), reste sur disque (`<sid>.db`), rechargé à la demande ; éviction TTL + purge `SESSION_RETENTION_DAYS`.
- **Contrainte : 1 seul worker uvicorn** (état mémoire + locks threads + `HEAVY_SEM`).
- **Prod** : derrière nginx en **sous-chemin `/plotter/`** (statique `alias` sur `dist/` buildé `--base=/plotter/` + proxy `/plotter/api/` → `127.0.0.1:9099`), backend en **service NSSM `CSVPlotter`**, enregistré dans le services dashboard (`services.yaml`). Détails : **`web/deploy/DEPLOY.md`**.

### Relation avec le desktop
| Fichier desktop | Fichier web backend | Adaptation |
|----------------|--------------------|----|
| `data_utils.py` | `core/data_utils.py` | Copie directe |
| `denoise_methods.py` | `core/denoise_methods.py` | Copie directe |
| `baseline_correction.py` | `core/baseline_correction.py` | Copie directe |
| `data_pipeline.py` | `core/pipeline.py` | pyqtSignal → print() (non utilisé par /api/process) |
| `data_extraction.py` | `core/extraction.py` | QDialog retiré, logique conservée |
| `data_manager.py` | `core/data_loader.py` | QThread retiré, fonctions pures |
| `db_schema.py` | `core/db_schema.py` | Import path adapté |
| `processing/*` | `core/processors/*` | Imports adaptés |

### API endpoints
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/upload` | POST | Upload CSV/Excel (UUID file_id, validation ext/taille) |
| `/api/files` | GET | Liste fichiers chargés |
| `/api/files/{id}` | DELETE | Supprimer un fichier |
| `/api/files/{id}/columns` | GET | Colonnes d’un fichier |
| `/api/files/{id}/data` | GET | Données brutes paginées (`?limit&offset`) |
| `/api/plot-data` | POST | Données pour Plotly.js (traces x/y avec file_id) |
| `/api/process` | POST | Traitement (appels directs, pas de mutation pipeline) |
| `/api/extract` | POST | Extraction de métriques (file_id singulier) |
| `/api/extract/preview` | POST | Preview extraction (tous fichiers ou un seul) |
| `/api/extract/operations` | GET | Opérations disponibles |
| `/api/pool/export` | POST | Construit le pool .db et renvoie ses **octets** (le navigateur l'écrit via « Enregistrer sous ») |
| `/api/pool/save` | POST | Sauvegarder pool en .db côté serveur dans `UPLOAD_DIR` (plus utilisé par le front, conservé pour compat) |
| `/api/pool/load` | POST | Charger pool depuis .db (retourne plotStyle, processing, plot_settings avec colonnes) |
| `/api/pool/list` | GET | Lister .db sur le share |
| `/api/session` | GET | État de la session (rehydrate le front au chargement) |
| `/api/reset` | DELETE | Vider la session courante (RAM + son `.db`) |
| `/api/health` | GET | Status serveur (+ `sessions_in_memory`) |

### Sauvegarde / chargement des pools (dialogues fichiers natifs)

Les pools `.db` se manipulent via de vraies boîtes Windows, côté navigateur (**File System Access API**).

- **Save As** → `showSaveFilePicker` : vraie boîte « Enregistrer sous » (choix dossier + nom). Le `.db` provient de `POST /api/pool/export` (octets) puis est écrit dans le *handle* choisi.
- **Dossier par défaut = source des dernières données chargées** : au chargement, on capte un *handle* de fichier (`showOpenFilePicker` au clic Load ; `getAsFileSystemHandle()` au drop) → passé en `startIn` à la boîte « Enregistrer sous ».
- **Save** → réécrit **silencieusement** au dernier handle choisi ; sinon se comporte comme Save As. Le handle vit en mémoire (perdu au rechargement de page).
- **Load unifié** → `.db` restaure le pool (`/api/pool/load`) ; `.csv/.xlsx/.xls/.tsv` sont uploadés (`/api/upload`). Le bouton Load accepte aussi le **glisser-déposer**.
- **Copy Data** → copie dans le presse-papier un **TSV** (Filename, Legend, colonnes extraites) des fichiers **cochés**, décimale **virgule** — collable directement dans Excel/LibreOffice/Sheets.

**Support navigateur** — l'API n'existe que sur **Chrome/Edge** :

| Navigateur | Modifier le nom | Choisir le dossier |
|-----------|-----------------|--------------------|
| Chrome / Edge | ✅ | ✅ (boîte native, démarre dans le dossier source) |
| Firefox/Safari — réglé « Toujours demander où enregistrer » | ✅ | ✅ (boîte Windows) |
| Firefox/Safari — défaut (Téléchargements) | ✅ (nom proposé) | ❌ (va dans Téléchargements) |

Hors Chrome/Edge → **repli téléchargement** (`<a download>`) : le nom est proposé, mais le choix du dossier dépend du réglage Firefox « Toujours demander où enregistrer les fichiers ».

**Fichiers clés** : `web/frontend/src/utils/saveFile.ts` (`pickAndSave`, `writeBlob`, `openDataFiles`), `web/frontend/src/api/client.ts` (`exportPool`), `web/frontend/src/App.tsx` (handlers Save/Save As/Load + refs de handle), `web/backend/api/pool.py` (`export_pool`).

## Évolution minimale (rasoir d’Ockham)
1) Supprimer le code mort/noms ambigus pour réduire la doc nécessaire.
2) Utiliser des générateurs (grep/rg) pour vérifier les imports; éviter le dessin manuel lourd.
3) Modifier a minima: types/docstrings là où c’est ambigu et pointer vers les fichiers.
4) Ajouter au besoin de petites séquences pour les 1–2 cas d’usage critiques.

## Regénération (manuel et simple)
- Vérifier les imports: `rg -n "^(from|import) " --no-heading | sort`
- Mettre à jour `docs/dep.mmd` en gardant la règle « A importe B ⇒ A --> B ».
