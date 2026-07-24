> ⚠️ **Doc legacy (desktop PyQt5 archivé)** — décrit une conception jamais portée
> sur la web app. Voir [README.md](README.md). Code : tag `legacy-desktop-2026-06-21`.

# THINK.md - Réflexion Architecture Multi-Plot

## Contexte Initial

**Problématique** : Comment lier plusieurs types de graphiques (UV-visible, tribologie, DRX, etc.) à des données expérimentales ?

**Cas d'usage réel** :
- Base de données croissante (centaines d'expériences)
- 5+ types d'analyses par expérience
- Besoin d'exploration dynamique
- Comparaison inter-expériences essentielle
- Ajout/retrait facile d'expériences dans la vue

## Évolution de la Réflexion

### Phase 1 : Mes Propositions Initiales

#### Option 1 : Multi-Window Simple
- 3 instances séparées de l'app (UV-vis, Tribo, DRX)
- Même base parquet partagée
- 3 `.db` distincts
- **Verdict** : Trop manuel pour >10 expériences

#### Option 2 : Multi-Tab avec Pool Partagé
- Onglets par technique dans une seule fenêtre
- Pool unifié avec champ `measurement_type`
- 1 seul `.db` multi-types
- **Verdict** : Bon compromis mais problème de visibilité

#### Option 3 : Master-Slave Multi-Plot
- Fenêtre manager qui ouvre des CSVPlotterApp filtrées
- Synchronisation par `sample_id`
- Architecture "experiment-centric"
- **Verdict** : Overhead pour usage quotidien

### Phase 2 : Proposition Utilisateur (YAML-based)

**Architecture "Lab Notebook Digital"** :
- Modèle : Experiments → Measurements → Plots
- Filesystem structuré : `data/<exp_id>/{uvvis,tribo,xrd}/`
- `meta.yaml` comme single source of truth
- Pipeline Snakemake pour batch processing
- DVC/Git LFS pour données lourdes

**Forces** :
- Traçabilité scientifique
- Reproductibilité
- Scalabilité >500 expériences

**Faiblesses identifiées** :
- Overhead configuration (YAML manuel)
- Gap avec GUI PyQt5 existante
- Perte d'interactivité (plots statiques)

### Phase 3 : Solution Hybride Proposée

**Architecture en 3 couches** :
1. **Layer GUI** (PyQt5) - Exploration interactive
2. **Layer Experiment Manager** - Pont vers meta.yaml
3. **Layer Filesystem** - Structure `data/<exp_id>/`

**Plan incrémental** :
- Phase 1 : Ajouter `experiment_id` optionnel aux `csv_files`
- Phase 2 : Créer `experiment_manager.py` (CLI)
- Phase 3 : Multi-Tab GUI "experiment-aware"
- Phase 4 : Pipeline Snakemake (optionnel)

### Phase 4 : Révélation du Besoin Réel

**Feedback utilisateur** :
> "Les onglets ne me satisfont pas. Les plots de différentes analyses sont côte à côte. La taille de la fenêtre n'est pas un problème."

**Nouvelle contrainte** : Vue grid/mosaic avec tous les plots visibles simultanément

## Solution Finale Retenue : Multi-Panel Grid View

### Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Experiment Browser + Multi-Panel Viewer                                 │
├────────────────┬─────────────────────────────────────────────────────────┤
│ 📋 Experiments │ 📊 Multi-Panel Grid (techniques × expériences)          │
│                │                                                          │
│ Search: [___]  │  ┌─────────────┬─────────────┬─────────────┬─────────┐ │
│ ☑ E2025-001    │  │  UV-Vis     │  Tribologie │     DRX     │  FTIR   │ │
│ ☐ E2025-002    │  │  [Plot 1]   │  [Plot 1]   │  [Plot 1]   │ [Plot 1]│ │
│ ☑ E2025-003    │  │  ― E2025-001│  ― E2025-001│  ― E2025-001│ ― E001  │ │
│ ...            │  │  ― E2025-003│  ― E2025-003│  ― E2025-003│ ― E003  │ │
│                │  ├─────────────┼─────────────┼─────────────┼─────────┤ │
│ [+] [-] [↻]    │  │     SEM     │     NMR     │    Raman    │  XPS    │ │
│                │  │  [Plot 2]   │  [Plot 2]   │  [Plot 2]   │ [Plot 2]│ │
│ 500 more...    │  │  ― E2025-001│  ― E2025-001│  ― E2025-001│ ― E001  │ │
│                │  │  ― E2025-003│  ― E2025-003│  ― E2025-003│ ― E003  │ │
│                │  └─────────────┴─────────────┴─────────────┴─────────┘ │
│                │  [Export Grid] [Resize Panels] [Toggle Axes Sync]      │
└────────────────┴─────────────────────────────────────────────────────────┘
```

### Composants Principaux

#### 1. `db_manager.py` - Base de Données Centralisée

**Schéma `experiments.parquet`** :
| Column | Type | Description |
|--------|------|-------------|
| `exp_id` | str | E2025-001 |
| `date` | datetime | 2025-01-15 |
| `sample_name` | str | Coating A |
| `technique` | str | uvvis, tribo, drx, ftir, sem |
| `csv_path` | str | data/E2025-001/uvvis/E2025-001_uvvis_01.csv |
| `status` | str | raw, processed, validated |
| `notes` | str | Optional metadata |

**Classe `ExperimentDatabase`** :
```python
class ExperimentDatabase:
    def __init__(self, db_path='experiments.parquet')
    def add_experiment(self, exp_id, technique, csv_path, **metadata)
    def get_experiments(self, exp_ids=None, techniques=None)
    def save()
    def load_csv_data(self, csv_path)  # Cache LRU (max 50)
```

#### 2. `experiment_browser.py` - Interface Principale

**Split View** :
- **LEFT (20%)** : Sidebar avec search/filter + liste exp_id avec checkboxes
- **RIGHT (80%)** : Multi-Panel Grid

**Méthodes clés** :
```python
def create_sidebar()          # Search + liste + boutons +/-/↻
def create_grid_panel()       # Canvas grid + toolbar
def populate_list()           # Remplit depuis DB
def filter_experiments()      # Search dynamique
def add_to_grid()            # Ajoute expériences cochées
def remove_from_grid()       # Retire expériences décochées
def refresh_grid()           # Recharge tous les plots
def toggle_sync()            # Synchronisation axes
def export_grid()            # Export PDF/PNG/SVG
```

#### 3. `grid_canvas.py` - Multi-Panel Grid Canvas

**Classe `MultiPanelGridCanvas(FigureCanvas)`** :
- Hérite de `matplotlib.backends.backend_qt5agg.FigureCanvasQTAgg`
- Crée un grid de subplots avec `GridSpec`
- Layout par défaut : 2 colonnes (optimal pour 3-6 techniques)

**Méthodes** :
```python
def __init__(self, techniques)  # ['uvvis', 'tribo', 'drx', ...]
def plot_experiment(exp_id, technique, df, x_col, y_col, color, label)
def clear_technique(technique)
def clear_all()
def sync_zoom(enable=True)  # Zoom synchronisé entre axes
def set_layout(layout_type)  # 'auto', 'row', 'col', 'grid'
```

**Grid Structure** :
- 1 subplot (`matplotlib.axes.Axes`) par technique
- Superposition de toutes les expériences sélectionnées dans chaque subplot
- Palette de couleurs automatique (1 couleur/expérience)

### Workflow Utilisateur

1. **Lancement** :
   ```bash
   python launcher.py  # Ouvre ExperimentBrowser en fullscreen
   ```

2. **Exploration** :
   - Taper dans search bar : "E2025-0"
   - Filtrer par technique : "uvvis"
   - Cocher 3 expériences : E2025-001, E2025-003, E2025-007

3. **Affichage** :
   - Cliquer [+] ou appuyer ENTER
   - Grid se remplit avec 5 subplots (UV-vis, Tribo, DRX, FTIR, SEM)
   - Chaque subplot contient 3 courbes superposées

4. **Interaction** :
   - Activer "Sync Axes" → zoom/pan synchronisé
   - Cliquer "Auto-Resize Panels" → tight_layout()
   - Décocher E2025-003 + cliquer [-] → courbe disparaît

5. **Export** :
   - Cliquer "Export Grid" → PDF haute résolution (300 dpi)

### Optimisations Techniques

#### Gestion Mémoire (500+ expériences)
```python
# Cache LRU pour CSV
self._csv_cache = {}  # Max 50 fichiers
def load_csv_data(csv_path):
    if csv_path in self._csv_cache:
        return self._csv_cache[csv_path]
    df = pd.read_csv(csv_path, sep=';')
    if len(self._csv_cache) > 50:
        self._csv_cache.popitem(last=False)  # FIFO
    self._csv_cache[csv_path] = df
    return df
```

#### Performance Table (QTableView au lieu de QTableWidget)
```python
# Pour 500+ lignes, utiliser Model/View
model = PandasModel(self.db.df)
self.table.setModel(model)  # 10x plus rapide
```

#### Column Mapping Intelligent
```python
def get_column_mapping(technique):
    mappings = {
        'uvvis': {'x': 'wavelength', 'y': 'absorbance'},
        'tribo': {'x': 'time', 'y': 'friction_coefficient'},
        'drx': {'x': '2theta', 'y': 'intensity'},
        'ftir': {'x': 'wavenumber', 'y': 'transmittance'},
        'sem': {'x': 'x_position', 'y': 'signal'}
    }
    return mappings.get(technique, {'x': df.columns[0], 'y': df.columns[1]})
```

### Features Avancées (Phase 4, optionnel)

1. **Layouts Personnalisables**
   - `'row'` : 1 ligne (toutes côte à côte)
   - `'col'` : 1 colonne (toutes empilées)
   - `'grid'` : grille carrée (2×2, 3×3)

2. **Drag & Drop**
   - Réorganiser les subplots par glisser-déposer

3. **Raccourcis Clavier**
   - `Ctrl+A` : Select all visible
   - `Ctrl+Click` : Multiselection
   - `Enter` : Refresh grid
   - `Ctrl+F` : Focus search bar

4. **Persistence Session**
   ```python
   # Sauvegarde dans .last_session.json
   {
       'selected_experiments': ['E2025-001', 'E2025-003'],
       'filters': {'technique': 'uvvis', 'search': 'coating'}
   }
   ```

## Plan d'Implémentation

### Phase 1 : Database Structure (2-3h)
- [ ] Créer `db_manager.py` avec classe `ExperimentDatabase`
- [ ] Définir schéma parquet (exp_id, date, sample_name, technique, csv_path, status, notes)
- [ ] Implémenter méthodes : `add_experiment()`, `get_experiments()`, `save()`, `load_csv_data()`
- [ ] Créer script de migration `migrate_existing_data.py`
- [ ] Tester : peupler DB avec 20-30 CSV existants

### Phase 2 : Experiment Browser avec Sidebar (3-4h)
- [ ] Créer `experiment_browser.py` avec classe `ExperimentBrowser(QMainWindow)`
- [ ] Implémenter split view : `QSplitter(Qt.Horizontal)` avec ratio 1:4
- [ ] Créer sidebar gauche :
  - [ ] Search bar (`QLineEdit` + autocomplete)
  - [ ] Technique filter (`QComboBox`)
  - [ ] Liste expériences (`QListWidget` avec checkboxes)
  - [ ] Boutons actions : +/- (ajouter/retirer), ↻ (refresh)
- [ ] Implémenter filtrage dynamique : `filter_experiments()`
- [ ] Tester : recherche + sélection de 5 expériences

### Phase 3 : Multi-Panel Grid Canvas (5-6h) ⭐ CORE
- [ ] Créer `grid_canvas.py` avec classe `MultiPanelGridCanvas(FigureCanvas)`
- [ ] Initialisation :
  - [ ] Calculer grid optimal (2 colonnes par défaut)
  - [ ] Créer `GridSpec` et axes via `fig.add_subplot()`
  - [ ] Stocker axes dans dict : `self.axes[technique] = ax`
- [ ] Implémenter `plot_experiment()` :
  - [ ] Charger CSV depuis DB
  - [ ] Détecter colonnes X/Y (column mapping)
  - [ ] Tracer courbe avec couleur/label
  - [ ] Configurer axes (xlabel, ylabel, legend, grid)
- [ ] Implémenter `clear_all()` et `clear_technique()`
- [ ] Implémenter `sync_zoom()` :
  - [ ] Connecter callbacks `xlim_changed` et `ylim_changed`
  - [ ] Synchroniser tous les axes
- [ ] Intégrer dans `experiment_browser.py` :
  - [ ] Créer `create_grid_panel()` avec toolbar
  - [ ] Implémenter `refresh_grid()` pour charger toutes les courbes
- [ ] Tester : afficher 3 expériences × 5 techniques

### Phase 4 : Polish & Features Avancées (3-4h, optionnel)
- [ ] Column mapping intelligent par technique
- [ ] Layouts personnalisables (`set_layout()`)
- [ ] Export PDF haute résolution (300 dpi)
- [ ] Raccourcis clavier
- [ ] Persistence session (`.last_session.json`)
- [ ] Gestion mémoire optimisée (cache LRU)

## Estimation Totale

**Effort** : 13-17 heures de développement

**Bénéfice** :
- Exploration visuelle de centaines d'expériences multi-techniques
- Ajout/retrait dynamique d'expériences en temps réel
- Comparaison côte à côte immédiate
- Export publication-ready en 1 clic

## Comparaison : Onglets vs Grid

| Critère | Onglets | Grid Multi-Panel |
|---------|---------|------------------|
| Visibilité simultanée | ❌ (1 à la fois) | ✅ (tous visibles) |
| Comparaison inter-techniques | ❌ (switch manuel) | ✅ (immédiate) |
| Utilisation écran | 🟡 (espace gaspillé) | ✅ (optimal fullscreen) |
| Navigation | 🟡 (clicks répétés) | ✅ (scroll vertical) |
| Export | 🟡 (1 plot/fois) | ✅ (tout en 1 PDF) |
| Performance (500 exp) | ✅ (lazy load) | 🟡 (RAM si >20 exp) |

## Décisions Architecturales Clés

### 1. Pourquoi Parquet au lieu de SQLite ?
- Pandas natif (déjà utilisé dans le projet)
- Performance lecture bulk (vs requêtes SQL)
- Portabilité (1 fichier, pas de serveur)
- Compatible DVC/Git LFS

### 2. Pourquoi Matplotlib GridSpec au lieu de subplots() ?
- Flexibilité layout (ratios personnalisables)
- Support legend dédiée (axes séparés)
- Compatible avec `constrained_layout`

### 3. Pourquoi QListWidget au lieu de QTableWidget ?
- Sidebar compacte (1 colonne suffit)
- Checkboxes natives (`Qt.ItemIsUserCheckable`)
- Performance >500 items

### 4. Pourquoi Cache LRU au lieu de tout charger ?
- Limite RAM (50 CSV = ~500 MB max)
- Latence acceptable (<100ms)
- Évite OOM avec >100 expériences

## Risques & Mitigations

### Risque 1 : Performance avec >20 expériences simultanées
**Mitigation** :
- Limiter sélection à 10 exp max (warning si dépassé)
- Downsampling automatique (1 point/10 si >10k points)
- Option "Plot Summary" (moyennes au lieu de toutes les courbes)

### Risque 2 : CSV avec formats hétérogènes
**Mitigation** :
- Column mapping configurable par technique
- Fallback : utiliser colonnes 0 et 1 par défaut
- Log warnings pour fichiers non conformes

### Risque 3 : DB corruption (parquet file)
**Mitigation** :
- Backup automatique (`experiments.parquet.bak`)
- Validation schema à chaque save
- Export JSON périodique (human-readable)

## Extensions Futures

### Court Terme (1-2 mois)
- [ ] Import direct depuis instruments (parsers USB/RS232)
- [ ] Tags/labels pour grouper expériences (ex: "Campaign 2025-Q1")
- [ ] Annotations sur plots (flèches, texte)

### Moyen Terme (3-6 mois)
- [ ] Pipeline batch processing (Snakemake integration)
- [ ] Notion API sync (push plots vers workspace)
- [ ] Multi-utilisateurs (DB partagée sur réseau)

### Long Terme (6-12 mois)
- [ ] Machine learning (détection anomalies, clustering)
- [ ] Web interface (Flask/Django + Plotly)
- [ ] API REST pour automatisation

## Références

### Documentation Matplotlib
- GridSpec : https://matplotlib.org/stable/api/_as_gen/matplotlib.gridspec.GridSpec.html
- Subplots : https://matplotlib.org/stable/gallery/subplots_axes_and_figures/subplots_demo.html
- Shared axes : https://matplotlib.org/stable/gallery/subplots_axes_and_figures/shared_axis_demo.html

### PyQt5 Best Practices
- Model/View : https://doc.qt.io/qt-5/model-view-programming.html
- QSplitter : https://doc.qt.io/qt-5/qsplitter.html
- Performance : https://wiki.qt.io/Performance_Tips

### Pandas Parquet
- read_parquet : https://pandas.pydata.org/docs/reference/api/pandas.read_parquet.html
- to_parquet : https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_parquet.html

## Conclusion

La solution **Multi-Panel Grid View** répond parfaitement aux besoins identifiés :
- ✅ Scalabilité (500+ expériences)
- ✅ Exploration dynamique (search/filter)
- ✅ Visibilité simultanée (grid layout)
- ✅ Comparaison inter-techniques (côte à côte)
- ✅ Ajout/retrait facile (boutons +/-)

L'implémentation se fait de manière incrémentale, avec chaque phase apportant une valeur utilisable. La Phase 3 (Grid Canvas) est le cœur du système et doit être priorisée après la Phase 1 (Database).
