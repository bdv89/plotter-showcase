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

## Évolution minimale (rasoir d’Ockham)
1) Supprimer le code mort/noms ambigus pour réduire la doc nécessaire.
2) Utiliser des générateurs (grep/rg) pour vérifier les imports; éviter le dessin manuel lourd.
3) Modifier a minima: types/docstrings là où c’est ambigu et pointer vers les fichiers.
4) Ajouter au besoin de petites séquences pour les 1–2 cas d’usage critiques.

## Regénération (manuel et simple)
- Vérifier les imports: `rg -n "^(from|import) " --no-heading | sort`
- Mettre à jour `docs/dep.mmd` en gardant la règle « A importe B ⇒ A --> B ».
