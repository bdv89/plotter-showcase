# Known Pitfalls & Solutions

Quick reference for common bugs and their fixes.

## Index

1. [European Decimal Format](#european-decimal-format)
2. [DataPipeline Pickle Serialization](#datapipeline-pickle-serialization)
3. [PyQt5 Empty Table Window Sizing](#pyqt5-empty-table-window-sizing)
4. [Python Bytecode Cache](#python-bytecode-cache)
5. [QComboBox vs QListWidget API](#qcombobox-vs-qlistwidget-api)
6. [UI Display Names vs Backend Codes](#ui-display-names-vs-backend-codes)
7. [PyQt5 Signal Loops](#pyqt5-signal-loops)
8. [Widget Initialization Order](#widget-initialization-order)
9. [Extracted Columns Not Persisting in .dpool](#extracted-columns-not-persisting-in-dpool) ✅ RESOLVED
10. [Plot Style Settings Not Applied on Load Pool](#plot-style-settings-not-applied-on-load-pool) ✅ FIXED
11. [Sort State Column Type Mismatch](#sort-state-column-type-mismatch) ✅ FIXED
12. [Dialog Double-Init](#dialog-double-init) ✅ FIXED
13. [Dead Code in DataManager](#dead-code-in-datamanager) ✅ REMOVED
14. [GridSpec Legend Complexity](#gridspec-legend-complexity) ✅ REMOVED
15. [Parent Navigation Anti-Pattern](#parent-navigation-anti-pattern) ✅ FIXED
16. [Bidirectional Signal Coupling](#bidirectional-signal-coupling) ✅ FIXED
17. [QScrollArea Not Scrolling Full Canvas](#qscrollarea-not-scrolling-full-canvas) ✅ FIXED

**Web (2026)**
18. [CSV header auto-detected at line 20](#csv-header-auto-detected-at-line-20) ✅ FIXED
19. [Emoji prints crash on Windows console (cp1252)](#emoji-prints-crash-on-windows-console-cp1252) ✅ FIXED
20. [Auto-color makes everything one color](#auto-color-makes-everything-one-color) ✅ FIXED
21. [Failed uploads pollute the file list](#failed-uploads-pollute-the-file-list) ✅ FIXED
22. [Sub-path deploy: blank page (vite base)](#sub-path-deploy-blank-page-vite-base) ⚠️ RÉCURRENT
23. [Single uvicorn worker mandatory](#single-uvicorn-worker-mandatory)
24. [nginx reload when nginx is a Windows service](#nginx-reload-when-nginx-is-a-windows-service)
25. [Port 8099 reserved (Hyper-V/WSL)](#port-8099-reserved-hyper-vwsl)
26. [Broken node_modules on Windows (rollup native)](#broken-node_modules-on-windows-rollup-native)
27. [Processing crashes on all-NaN / short columns](#processing-crashes-on-all-nan--short-columns) ✅ FIXED
28. [Auto-plot doesn't fire on the first plot](#auto-plot-doesnt-fire-on-the-first-plot) ✅ FIXED
29. [Promotion robocopy hangs / copies 374 MB (venv not excluded)](#promotion-robocopy-hangs--copies-374-mb-venv-not-excluded) ✅ FIXED
30. [Fixed Y min ignored → axis autoscales to -1](#fixed-y-min-ignored--axis-autoscales-to--1) ✅ FIXED
31. [Copy Data: navigator.clipboard undefined on HTTP/LAN](#copy-data-navigatorclipboard-undefined-on-httplan) ✅ FIXED
32. [Old .db pool loads with no legend](#old-db-pool-loads-with-no-legend) ⚠️ PAR DESIGN
33. [Clear all + Load freezes: RLock released cross-thread](#clear-all--load-freezes-rlock-released-cross-thread) ✅ FIXED
34. [Le traitement s'appliquait à côté du chemin de plot](#le-traitement-sappliquait-à-côté-du-chemin-de-plot) ✅ FIXED

---

## European Decimal Format

**Cause**: pandas reads European CSV (`,` decimal separator) as strings instead of floats → plots show diagonal lines instead of curves.

**Solution**: Apply numeric conversion at ALL data entry points via centralized utility:
```python
from data_utils import convert_numeric_columns
df = convert_numeric_columns(df)  # Converts "1,23" → 1.23
```

**Single Source of Truth** (March 2025): Conversion logic centralized in `data_utils.py`:
- `storage_manager.py` - Imports from data_utils for .db/.dpool/.import
- `db_schema.py` - Imports from data_utils for SQLite load
- `data_manager.py:140-173` - Uses inline version with `decimal=','` + `pd.to_numeric()`
- Verify dtypes: `dtype=float64` (not `object`)

**Prévention**:
- Test with European CSV during development
- Add `print(df.dtypes)` after data loading to verify numeric conversion
- Use `convert_numeric_columns()` from `data_utils.py` for any new data entry point

---

## DataPipeline Pickle Serialization

**Cause**: `LazyDataFrame` contains `DataPipeline` with PyQt5 signals (QObject) → cannot be pickled → cache fails → file processing crashes.

**Solution**: Graceful degradation in `data_manager.py:427-435`
```python
if self.use_cache and self.cache:
    try:
        self.cache.cache_data(file_path, processed_file)
    except (TypeError, AttributeError):
        pass  # Skip caching, continue processing
```

**Prévention**:
- Verify objects are picklable before caching
- Consider cache failures non-fatal unless critical to functionality

---

## PyQt5 Empty Table Window Sizing

**Cause**: `QTableWidget.resizeColumnsToContents()` on empty table (0 rows) returns unpredictable widths → window becomes erratic.

**Solution**: Set minimum sizes + explicit widths when empty
- `main_app.py:39` → `self.setMinimumSize(800, 600)`
- `ui_components.py:76` → `self.setMinimumSize(600, 200)`
- `main_app.py:656-660` → Set explicit column widths instead of `resizeColumnsToContents()` when table empty

**Prévention**:
- Always set minimum size on windows/tables that can become empty
- Avoid `resizeColumnsToContents()` on 0-row tables

---

## Python Bytecode Cache

**Cause**: Python caches `.pyc` files in `__pycache__/` → modified `.py` files may not execute if cache not invalidated.

**Solution**: Delete cache after code changes
```bash
# WSL/Linux
rm -rf __pycache__ && python3 launcher.py

# Windows
rmdir /s /q __pycache__ && python launcher.py

# Or bypass cache during dev
python3 -B launcher.py
```

**Prévention**:
- Always delete `__pycache__/` after significant changes
- Launch via terminal (not double-click) during active development

---

## QComboBox vs QListWidget API

**Cause**: `self.y_list` and `self.y2_list` are **QComboBox** but variable names suggest QListWidget → API confusion → AttributeError.

**Solution**: Use correct QComboBox API
```python
# CORRECT (QComboBox)
index = self.y_list.findText(text)  # Returns int
if index >= 0:
    self.y_list.setCurrentIndex(index)

# WRONG (QListWidget API)
self.y_list.clearSelection()  # AttributeError!
item = self.y_list.item(i)    # AttributeError!
```

**Quick Reference**:
| Action | QComboBox | QListWidget |
|--------|-----------|-------------|
| Set selection | `setCurrentIndex(idx)` | `item(idx).setSelected(True)` |
| Find text | `findText(text)` | `findItems(text)` |
| Clear selection | `setCurrentIndex(-1)` | `clearSelection()` |

**Prévention**:
- Verify widget type before using selection methods: `print(type(self.widget))`
- Search codebase for existing usage patterns (e.g., `main_app.py:583-596`)

---

## UI Display Names vs Backend Codes

**Cause**: UI sends display names ("Savitzky-Golay") but backend expects method codes ("savgol") → silent failure (function returns original data unchanged).

**Solution**: Add translation map in `processing/denoise.py:13-19`
```python
method_map = {
    'savitzky-golay': 'savgol',
    'median filter': 'median',
    'wavelet': 'wavelet',
    'fft low-pass': 'fft'
}
method_code = method_map.get(method.lower(), method.lower())
```

**Prévention**:
- Create translation map immediately when UI options map to backend functions
- Add debug print at UI→backend junction: `print(f"UI: {ui_name} → Backend: {code}")`
- Use enums/constants instead of free-form strings

---

## PyQt5 Signal Loops

**Cause**: `QComboBox.clear()` triggers `currentIndexChanged(-1)` signal → calls `apply_settings()` → repopulates combo → triggers signal again → infinite loop.

**Solution**: Block signals during programmatic updates
```python
def populate_time_columns(self, available_columns):
    self.combo_time_column.blockSignals(True)
    self.combo_time_column.clear()
    for col in available_columns:
        self.combo_time_column.addItem(col)
    self.combo_time_column.blockSignals(False)
```

**When to use `blockSignals()`**:
- ✅ Populating widgets from data (`populate_*` functions)
- ✅ Restoring settings from file (`load_settings`)
- ✅ Synchronizing widgets programmatically
- ❌ User-triggered changes (signals should fire normally)

**Prévention**:
- Always use `blockSignals()` when programmatically modifying widgets in `__init__` or `load_*` functions
- Test by calling populate function multiple times rapidly
- Add debug prints to detect loops: if you see 🟢 repeatedly without ✅, you have a loop

---

## Widget Initialization Order

**Cause**: Parent loads data via `_on_files_loaded()` but child widget created later (lazy initialization) → data can't be passed → silent failure.

**Solution**: Pending Data Pattern
```python
# 1. In parent __init__()
self.pending_time_columns = []

# 2. When data available BEFORE child created
def _on_files_loaded(self, csv_files):
    self.pending_time_columns = numeric_cols  # STORE for later
    if hasattr(self, 'child_widget') and self.child_widget:
        self.child_widget.populate(numeric_cols)  # Populate if exists

# 3. When child widget CREATED
def show_child_window(self):
    self.child_widget = ChildWidget()
    if self.pending_time_columns:
        self.child_widget.populate(self.pending_time_columns)  # Transfer pending
```

**Prévention**:
- Initialize `pending_*` variables in `__init__()` for all deferred populations
- Identify parent-child widget dependencies during design
- Add debug prints to trace data flow: 🟢 store → 🔵 transfer → ✅ populate

---

## Debug Strategy

For all pitfalls, use strategic debug prints with emoji color-coding:
- 🟢 = Entry point (UI trigger, function start)
- 🟡 = Data processing/conversion
- 🔴 = Object/pipeline creation
- ⚫ = Verification/validation
- 🔵 = Execution (data transformation)
- ✅ = Success confirmed
- ❌ = Failure detected

**Example**:
```python
print(f"🟢 Loading file: {file_path}")
data = load_csv(file_path)
print(f"🟡 Converted dtypes: {data.dtypes}")
print(f"✅ Loading complete: {len(data)} rows")
```

**Rule**: If you spend >2 minutes debugging, add prints immediately.

---

## Extracted Columns Not Persisting in .dpool

> ✅ **RESOLVED** (Dec 2025): This issue is now fixed with SQLite migration (.db format). The enhanced_csv_files pattern is preserved and works correctly with the new db_schema.py. See CLAUDE.md "SQLite Migration" section.

**Cause**: `save_data_pool()` passed `self.csv_files` directly to `StorageManager`, but `extracted_data` was only stored in UI (`file_list.extracted_columns`) and never copied to `csv_files` before save → .dpool files saved without extracted_data → load_pool() found nothing to restore.

**Symptom**: Extracted columns (📊) disappear after Save Pool → Load Pool cycle.

**Solution**: Copy extracted_data to enhanced csv_files before save (main_app.py:549-570)
```python
def save_data_pool(self):
    # ... (plot settings, fit results, etc.)

    # Enhance csv_files with extracted_data before saving
    enhanced_csv_files = []
    for csv_file in self.csv_files:
        filename = csv_file['filename']
        enhanced_file = csv_file.copy()

        # Add extracted data if available
        if hasattr(self.file_list, 'extracted_columns') and filename in self.file_list.extracted_columns:
            enhanced_file['extracted_data'] = self.file_list.extracted_columns[filename]
            print(f"🟡 Adding extracted_data to {filename} for pool save")

        enhanced_csv_files.append(enhanced_file)

    StorageManager.save_data_pool(self, enhanced_csv_files, ...)  # Pass enhanced_csv_files
```

**Pattern**: Same as `export_data()` (lines 502-516) which already did this correctly for CSV/Excel exports.

**Prevention**:
- When adding new UI-only data (like `parquet_columns` or `extracted_columns`), ensure it's copied to `csv_files` before BOTH `save_data_pool()` AND `export_data()`
- Add debug prints at save/load junctions: `🟡 Adding {data_type} to {filename}` and `✅ Restored {data_type} for {count} files`
- Test full save/load cycle, not just export

**Related**: This pattern applies to any UI-stored metadata that needs persistence (line colors, styles, legend labels all follow this pattern).

---

## Plot Style Settings Not Applied on Load Pool

> ✅ **FIXED** (Dec 2025): Missing UI synchronization after applying pending plot settings.

**Cause**: `apply_plot_settings_to_window()` called `canvas.set_plot_style()` but didn't call `style_window._set_initial_values()` to update the UI controls → plot style settings were applied to the canvas but the style window UI showed wrong values → auto-presets could overwrite loaded settings.

**Symptom**: After "Load Pool", plot displays default settings or auto-preset settings instead of the pool's saved plot_style_settings (titles, fonts, colors, etc.).

**Root Cause Chain**:
1. Load Pool → `plot_style_settings` stored in `pending_plot_settings` (window not open yet)
2. User clicks PLOT → auto-preset loads (e.g., "banc_TC.plot") and applies
3. `apply_plot_settings_to_window()` called to apply pending settings
4. ❌ Missing: `style_window._set_initial_values()` → UI not synced
5. ❌ Missing: Clear `pending_plot_settings` after application
6. User interaction → UI controls trigger style changes with wrong values

**Solution**: Add UI sync + cleanup in `main_app.py:1427-1431`
```python
def apply_plot_settings_to_window(self, settings_data):
    if not self.plot_window or not hasattr(self.plot_window, 'canvas'):
        return

    if 'plot_style_settings' in settings_data:
        self.plot_window.canvas.set_plot_style(settings_data['plot_style_settings'])

        # CRITICAL: Update UI to reflect loaded settings
        if hasattr(self.plot_window, 'style_window'):
            self.plot_window.style_window._set_initial_values()

        # Clear pending settings after successful application
        if hasattr(self, 'pending_plot_settings'):
            self.pending_plot_settings = None
```

**Why This Works**:
- `_set_initial_values()` reads current canvas settings → updates all UI controls (combos, spinboxes, etc.)
- Clearing `pending_plot_settings` prevents re-application on subsequent plot window opens

**Prevention**:
- Always call UI sync methods after programmatic state changes: `canvas.set_plot_style()` → `style_window._set_initial_values()`
- Test "Load Pool → PLOT" flow, verify pool settings override auto-presets
- Add pattern to checklist: After changing canvas state, sync dependent UI

**Related**: Same pattern in `_apply_plot_style_settings()` (lines 672-674) already had this sync call.

---

## Sort State Column Type Mismatch

> ✅ **FIXED** (Dec 2025): Column indices stored as strings in JSON/SQLite but QTableWidget.sortItems() expects int.

**Cause**: `extracted_column_sort_state` dict keys stored as strings (JSON/SQLite constraint) but `sortItems(column: int, order)` requires int → `TypeError: argument 1 has unexpected type 'str'`.

**Symptom**: Crash during "Load Pool" with traceback:
```
TypeError: sortItems(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder): argument 1 has unexpected type 'str'
  File "main_app.py", line 617, in load_data_pool
    self.file_list.sortItems(col_idx, qt_order)
```

**Root Cause**:
1. User sorts table by clicking column header → `extracted_column_sort_state = {8: 'desc', 10: 'asc'}` (int keys)
2. Save Pool → stored in SQLite/JSON → dict keys become strings: `{'8': 'desc', '10': 'asc'}`
3. Load Pool → `sortItems(col_idx, ...)` receives `'8'` (str) instead of `8` (int) → crash

**Solution**: Type conversion in `main_app.py:616-618`
```python
for col_idx, order in self.file_list.extracted_column_sort_state.items():
    if order:  # 'asc' or 'desc'
        qt_order = Qt.AscendingOrder if order == 'asc' else Qt.DescendingOrder
        # Convert col_idx to int (stored as string in JSON/SQLite)
        col_idx_int = int(col_idx) if isinstance(col_idx, str) else col_idx
        self.file_list.sortItems(col_idx_int, qt_order)
```

**Prevention**:
- When loading data from JSON/SQLite, assume dict keys are strings
- Add type conversion for all numeric dict keys at load boundary
- Test save/load cycle for any persisted state containing numeric indices

**Related**: Same issue can occur with any dict-stored indices (row numbers, column positions, etc.).

---

## Dialog Double-Init

> ✅ **FIXED** (March 2025): Duplicate `init_ui()` and `setWindowTitle()` calls removed.

**Cause**: `TableSelectDialog.__init__()` in `parquet_linker.py` called `setWindowTitle()` and `init_ui()` twice due to copy-paste error → widgets duplicated in dialog.

**Symptom**: Dialog may show duplicated UI elements or have unexpected layout.

**Code Before**:
```python
def __init__(self, parent, table_names):
    super().__init__(parent)
    self.table_names = table_names
    self.selected_table = None

    self.setWindowTitle("Select Table")
    self.init_ui()

    self.setWindowTitle("Select Table")  # DUPLICATE
    self.init_ui()                        # DUPLICATE
```

**Solution**: Remove duplicate calls (lines 769-770 removed).

**Prevention**:
- Code review for obvious copy-paste duplicates
- Use `git diff` before commit to spot accidental repetitions
- Static analysis tools can detect identical consecutive statements

---

## Dead Code in DataManager

> ✅ **REMOVED** (March 2025): Unused methods deleted to reduce maintenance burden.

**Cause**: `data_manager.py` contained two methods never called anywhere:
- `_process_file()` (~35 lines)
- `_parse_csv_data()` (~55 lines)

These were replaced by `_process_file_lazy()` which uses lazy loading, but the old methods were never removed.

**Impact**:
- ~90 lines of dead code to maintain
- Confusion about which method is actually used
- Potential bugs if someone accidentally calls the dead methods

**Solution**: Delete both methods entirely.

**Prevention**:
- Follow CLAUDE.md rule: "Puis-je simplement SUPPRIMER du code au lieu d'en ajouter?"
- Use IDE "Find Usages" before assuming code is needed
- Grep for function names before refactoring: `grep -r "_process_file\b" *.py`
- When adding new implementations, delete replaced code immediately

---

## GridSpec Legend Complexity

> ✅ **REMOVED** (Mars 2026): 180+ lines of GridSpec code replaced by matplotlib's modern `loc='outside'` API.

**Cause**: Before matplotlib 3.6, placing legends outside the plot required manual GridSpec manipulation with dedicated legend axes, snapshot/restore of plot lines, complex layout calculations.

**Original Code Size**: ~180 lines across:
- `_snapshot_lines()` - Save line data before layout rebuild
- `_replot_from_snapshot()` - Restore lines after rebuild
- `ensure_legend_layout()` - Main layout orchestration
- `_rebuild_layout_optimized()` - GridSpec creation per legend position
- `_get_layout_signature()` - Cache invalidation

**Problem Symptoms**:
- Freeze on rapid legend position changes (recursive layout rebuilds)
- Inconsistent figure sizes when switching positions
- Legend sometimes clipped or overlapping

**Discovery**: Matplotlib >= 3.6 natively supports `fig.legend(loc='outside right center')` with `layout='constrained'`.

**Solution**: Delete all GridSpec code, use modern API in `plot_styles.py`:
```python
# plot_canvas.py - Enable constrained_layout
self.fig, self.ax = plt.subplots(layout='constrained')

# plot_styles.py - Simple location mapping
LOCATION_MAP = {
    'outside_right': 'outside right center',
    'outside_left': 'outside left center',
    'outside_top': 'outside upper center',
    'outside_bottom': 'outside lower center',
}
canvas.fig.legend(lines, labels, loc=LOCATION_MAP[loc])
```

**Result**: -244 lines in plot_canvas.py (629 → 385)

**Prevention**:
- Before writing complex code, ask: "Quel outil fait DÉJÀ ça?"
- Check library release notes for new features that may replace workarounds
- Matplotlib 3.6+ features: `layout='constrained'`, `loc='outside'`, `subfigures`

---

## Parent Navigation Anti-Pattern

> ✅ **FIXED** (Mars 2026): Settings now read from plot_style dict instead of traversing parent hierarchy.

**Cause**: Code traversed widget parent hierarchy to read settings:
```python
parent = self.parent()
while parent is not None:
    if hasattr(parent, 'show_peak_markers'):
        show_markers = parent.show_peak_markers
        break
    parent = parent.parent()
```

**Problems**:
- 15 lines for 2 booleans
- Fragile: breaks if widget hierarchy changes
- Hard to test: requires full GUI instantiation
- Violates encapsulation: child knows about parent internals

**Solution**: Store settings in the centralized `plot_style` dict:
```python
# In DEFAULT_STYLE_SETTINGS (plot_styles.py)
'show_peak_markers': True,
'show_peak_numbers': True,

# In _add_peak_visual_indicators() (plot_canvas.py)
show_markers = self.plot_style.get('show_peak_markers', True)
show_numbers = self.plot_style.get('show_peak_numbers', True)
```

**Prevention**:
- Store all configuration in a central dict, not spread across widget attributes
- Child widgets should receive config via method parameters or shared dict
- If you see `parent.parent()`, refactor to pass data explicitly

---

## Bidirectional Signal Coupling

> ✅ **FIXED** (Mars 2026): Signal removed, replaced by showEvent synchronization.

**Cause**: `PlotCanvas.styleChanged` signal emitted on every style change, connected to `PlotStyleWindow._set_initial_values()`:
```python
# plot_canvas.py
self.styleChanged.emit(self.plot_style)

# plot_window.py
self.canvas.styleChanged.connect(self.style_window._set_initial_values)
```

**Problems**:
- Potential signal loops: style change → emit → update UI → trigger style change
- Performance: UI updated even when style window not visible
- Complexity: signal management across multiple files

**Solution**: Remove signal, sync UI only when window shown:
```python
# plot_style_window.py
def showEvent(self, event):
    """Sync controls with canvas style when window is shown"""
    super().showEvent(event)
    self._set_initial_values()
```

**Benefits**:
- No signal to manage
- UI only updated when needed (window visible)
- Clear data flow: canvas is source of truth, UI reads on demand

**Prevention**:
- Prefer pull (read on demand) over push (emit signals) for UI synchronization
- Use `showEvent()` to sync dialog state with parent
- Signals are for cross-module communication, not UI-to-sibling-UI sync

---

## QScrollArea Not Scrolling Full Canvas

> ✅ **FIXED** (Mars 2026): Missing `updateGeometry()` after `setFixedSize()` prevented QScrollArea from recalculating scrollable area.

**Cause**: `PlotCanvas.setFixedSize()` changes widget size, but without calling `updateGeometry()`, the parent `QScrollArea` doesn't know the content size changed → scrollbars don't allow full navigation.

**Symptom**: When plot window is smaller than canvas (e.g., 800×800 plot in 600×400 window), scrollbars appear but cannot scroll to all four corners of the canvas.

**Root Cause**:
1. User resizes PlotWindow smaller than plot dimensions
2. QScrollArea shows scrollbars (correct)
3. `setFixedSize()` called but `updateGeometry()` not called
4. QScrollArea's internal `scrollAreaWidgetContents` not updated
5. Scroll range incomplete → corners inaccessible

**Solution**: Add `updateGeometry()` after size changes in `plot_canvas.py`:
```python
# In _update_figure_size() (line 223-224)
if getattr(self, '_lock_display_size', False):
    try:
        self.setFixedSize(width_px, height_px)
        self.updateGeometry()  # Notify parent (QScrollArea)
    except Exception:
        pass

# In set_lock_display_size() (line 311-312)
if self._lock_display_size:
    self._update_figure_size()
    FigureCanvas.setSizePolicy(self, QSizePolicy.Fixed, QSizePolicy.Fixed)
    FigureCanvas.updateGeometry(self)  # Notify parent (QScrollArea)
```

**Why This Works**:
- `updateGeometry()` signals to Qt that the widget's size hint has changed
- Parent `QScrollArea` recalculates its `scrollAreaWidgetContents` bounds
- Scrollbar ranges now reflect actual widget size

**Prevention**:
- Always call `updateGeometry()` after `setFixedSize()` or `setSizePolicy()` changes
- Test scroll behavior with window smaller than content
- Verify all four corners accessible via scrollbars

---

# Web / Déploiement (2026)

## CSV header auto-detected at line 20

> ✅ **FIXED** (2026): heuristic in `core/data_loader.py` picked the header from line 20 for any comma CSV with >20 rows.

**Cause**: `detect_csv_format()` had a branch `elif len(preview_lines) > 20 and ',' in preview_lines[20]: header_line=20`. Any normal comma CSV longer than 20 rows → header read from row 20 (data values) → empty/garbage columns, no data to select.

**Solution**: removed the line-20 branch; header is always line 0 (delimiter from line 0: `;` / tab / `,`).

**Prevention**: don't encode instrument-specific offsets in a generic detector; one source of truth for the header line.

---

## Emoji prints crash on Windows console (cp1252)

> ✅ **FIXED** (2026): `print("🟢…")` raised `UnicodeEncodeError` on the Windows console (cp1252), which `upload.py` caught as a parse failure → files loaded with empty columns.

**Cause**: backend uses emoji-prefixed prints; the default Windows console encoding (cp1252) can't encode them.

**Solution**: set `PYTHONUTF8=1` (and `PYTHONIOENCODING=utf-8`) when launching the backend — done in `start-plotter.ps1` and the NSSM service env. WSL/utf-8 consoles are unaffected.

**Prevention**: force UTF-8 for any Python process that prints non-ASCII on Windows.

---

## Auto-color makes everything one color

> ✅ **FIXED** (2026): `seriesColorIndices` collapsed all files into one color.

**Cause**: auto-color groups "same series → same color". If the detected/selected series collapses to a single group (constant/out-of-range token, or an over-eager heuristic), every file gets `palette[0]` → monochrome.

**Solution** (`utils/coloring.ts`): **Auto = one distinct color per file**; tokens selected = group by tokens; **safety fallback** to per-file if grouping yields ≤1 group; the fragile heuristic was removed.

**Prevention**: never let a grouping function silently map everything to index 0; guard the degenerate case.

---

## Failed uploads pollute the file list

> ✅ **FIXED** (2026): rejected uploads (e.g. over `MAX_FILES`) returned `file_id=""` and were added to the UI.

**Cause**: backend returns `FileInfo(file_id="", error=…)` on rejection; `addFiles` added them → all shared the empty-string key → single phantom style/legend → "one color, one legend".

**Solution** (`store/appStore.ts`): `addFiles` drops entries with empty `file_id` and surfaces their error via `setError`.

**Prevention**: at any ingest boundary, filter out failed records and show the error rather than storing them.

---

## Sub-path deploy: blank page (vite base)

> ⚠️ **RÉCURRENT** : resurgit à **chaque** build qui oublie le flag `--base` (revu en 2026-06 : le `dist/` prod avait été buildé en `base=/`). Pas un bug « réglé une fois » — c'est une étape de build à ne jamais oublier.

**Cause**: a default `vite build` (`base=/`) emits `index.html` referencing `/assets/...` (absolute). Served under `/plotter/`, the browser requests `/assets/...` → 404 → blank page (only the Vite dev server hid this).

**Solution**: build with the sub-path — `VITE_API_URL=/plotter/api` + `npm run build -- --base=/plotter/` → assets at `/plotter/assets/...`.

**Prevention**: the build base must match the nginx location prefix; verify `dist/index.html` references `/<prefix>/assets/`.

---

## Single uvicorn worker mandatory

**Cause**: state is in-memory per session (`SessionManager` dict + `threading.RLock` + global `HEAVY_SEM`). Multiple uvicorn workers = separate processes → sessions not shared, semaphore not global.

**Rule**: run **1 worker** (no `--workers>1`), no `--reload` in prod. To scale: externalize state (Redis). ~50 LAN users are fine on 1 worker.

---

## nginx reload when nginx is a Windows service

**Cause**: `nginx -s reload` fails with `OpenEvent("Global\ngx_reload_…") failed (5: Accès refusé)` — even from an elevated shell — because nginx runs under the service account; the reload signal can't cross sessions.

**Solution**: `Restart-Service Nginx` (admin) after `nginx -t`. Brief blip for all sites; config is validated first.

---

## Port 8099 reserved (Hyper-V/WSL)

**Cause**: binding 8099 fails with `WinError 10013 (access denied)` although nothing listens — the port falls in a Hyper-V/WSL reserved range (`netsh interface ipv4 show excludedportrange protocol=tcp`). Ranges shift after reboot.

**Solution**: use **9099** (dev + prod here). To probe a free port: try-bind a `TcpListener` on loopback.

---

## Broken node_modules on Windows (rollup native)

**Cause**: a `node_modules` installed on another OS (e.g. WSL) is missing the Windows rollup binary and `.bin` shims → `vite`/`tsc`/`eslint` "not recognized", and `Cannot find module @rollup/rollup-win32-x64-msvc`.

**Solution**: clean reinstall on Windows — remove `node_modules` + `package-lock.json`, then `npm install`.

**Prevention**: don't share `node_modules` across OSes; install per platform.

---

## Processing crashes on all-NaN / short columns

> ✅ **FIXED** (2026): denoise + baseline crashed on every real tribology file (0/253 processed).

**Cause**: real files carry a numeric column that is entirely NaN (e.g. `METADATA`, dtype float64). The processors iterate numeric columns without skipping it → `denoise` raises `ValueError: Input data contains only NaN values`, `baseline` raises `array of sample points is empty`. Separately, files shorter than the Savitzky-Golay window (e.g. 11) raise `window_length must be ≤ size of x`.

**Solution**:
- `core/denoise_methods.py` (DataFrame loop): skip all-NaN columns; `try/except ValueError` per column → leave it unchanged (covers the short-window case too).
- `_baseline()`: skip all-NaN columns + `try/except` per column. *(Vivait alors dans `api/process.py` ; depuis la consolidation — entrée #34 — c'est `core/processing.py`, où chaque étape dégrade toujours par colonne.)*
- (`_smooth`/`_normalize`/`_remove_outliers` were already safe: NaN std/min/max guards.)

**Symptom**: enabling denoise or baseline returns 500 on these files; nothing processes.

**Prevention**: any per-column processor must skip columns with no finite data and degrade per-column instead of aborting the whole file. Test processing on a real multi-column export (with a metadata/empty column), not just clean synthetic data.

---

## Auto-plot doesn't fire on the first plot

> ✅ **FIXED** (2026): the first auto-plot got swallowed; user had to click **Plot** once before auto-plot started working.

**Cause** (`components/ColumnSelector.tsx`): the auto-plot `useEffect` had `handlePlot` in its dependency array, and set `lastRequestRef.current = fingerprint` *before* the 300 ms `setTimeout` fired. `handlePlot` is a `useCallback` that depends on `fileStyles`/`processing`, so its identity churns; React StrictMode also double-mounts effects in dev. Either one re-runs the effect → cleanup clears the pending timer → the re-run sees a matching fingerprint → early `return` without rescheduling → **the plot never fires**.

**Symptom**: after upload + checking files + selecting X/Y, no curves appear; clicking **Plot** manually once "unlocks" auto-plot for subsequent changes.

**Solution**: read `handlePlot` through a ref (so its churn no longer re-runs the effect) and set `lastRequestRef` *inside* the timer callback (so a cancelled timer always reschedules):
```ts
const handlePlotRef = useRef(handlePlot);
handlePlotRef.current = handlePlot;
useEffect(() => {
  if (!autoPlot || !canPlot) return;
  const fingerprint = JSON.stringify([checkedFilesArr, xColumn, yColumns, y2Columns]);
  if (fingerprint === lastRequestRef.current) return;
  const timer = setTimeout(() => {
    lastRequestRef.current = fingerprint;   // set only when it actually runs
    handlePlotRef.current();
  }, 300);
  return () => clearTimeout(timer);
}, [autoPlot, canPlot, checkedFilesArr, xColumn, yColumns, y2Columns]);  // no handlePlot
```

**Prevention**: in a debounced-effect pattern, don't put the churning callback in the deps (use a ref), and commit the dedup key only after the action runs — never before a cancellable timer.

---

## Promotion robocopy hangs / copies 374 MB (venv not excluded)

> ✅ **FIXED** (2026): `promote-dev-to-beta.ps1` / `promote-exp-to-prod.ps1` (and the DEPLOY.md robocopy snippets) excluded `venv_win` but **not** `venv`.

**Cause**: the backend has two Python environments — `backend\venv_win` (Windows) **and** `backend\venv` (WSL/Linux). The robocopy `/XD` list only excluded `venv_win`, so every promotion mirrored the ~374 MB WSL venv (6000+ files). One of its dirs failed to copy, and with robocopy's **default retries `/R:1000000 /W:30`** that single failure retried near-forever → the script appeared **frozen** at "[1/3] Copie…".

**Symptom**: promotion stuck at the copy step (silent because output went to `Out-Null`); a `/L /R:0` dry-run showed 374 MB + 1 failed dir.

**Solution** (`web\deploy\promote-*.ps1` + DEPLOY.md): add `venv` (and `.git`/`.jj`/`/XJ`) to `/XD`, add `/R:1 /W:1` so a locked file fails fast instead of hanging, and drop `Out-Null` so progress is visible:
```powershell
robocopy $src $dst /MIR /R:1 /W:1 /NP /XJ `
  /XD venv venv_win node_modules dist __pycache__ uploads logs .git .jj /XF *.log
```
Dry-run after fix: 64 files / 533 KB, 0 failures.

**Prevention**: for any mirror/copy, exclude **all** regenerable heavy dirs (both venvs!) and always cap robocopy retries (`/R` /`/W`) — the defaults turn one locked file into an infinite hang. Validate with a `/L` dry-run first.

---

## Fixed Y min ignored → axis autoscales to -1

> ✅ **FIXED** (2026): a manual axis range was applied only when **both** min and max were set; one bound alone was silently dropped.

**Cause** (`components/PlotView.tsx`): `range: y_min != null && y_max != null ? [y_min, y_max] : undefined`. Unchecking *Auto scale* and setting only **Y min = 0** (Max blank) left `range` undefined → Plotly autoranged with ~5% padding below the data → the axis bottom landed at ≈ **-1** despite "min = 0", and Plotly's default **zeroline** (drawn at y=0) then sat slightly above the frame. The white-bg/black-box publication preset made both newly visible (they blended into the old dark theme).

**Solution**: `axisRange()` helper fills the open side from the actual data extent (+3% pad) when only one bound is set; both unset → autorange; log axes keep the both-or-nothing rule. Also set `zeroline: false` on all axes (cleaner for a boxed publication plot, removes the stray 0 line). Layout `useMemo` now depends on `traces` since the range reads data.

**Prevention**: when mapping optional user bounds to a library that needs a complete range, fall back to data extents per side instead of discarding partial input; don't require all-or-nothing.

---

## Copy Data: navigator.clipboard undefined on HTTP/LAN

> ✅ **FIXED** (2026): `Copy Data` crashait `can't access property "writeText", navigator.clipboard is undefined` quand le plotter était ouvert via une IP LAN en HTTP (Firefox, toutes plateformes).

**Cause** (`App.tsx`, `handleCopyData`): `navigator.clipboard` n'est exposé par les navigateurs **que dans un contexte sécurisé** (HTTPS ou `localhost`). En dev `localhost:5174` ça marche, mais dès qu'on ouvre l'URL via une IP LAN (`http://192.168.x.x:5174/…`), Firefox laisse `navigator.clipboard` à `undefined` → `navigator.clipboard.writeText(...)` lève.

**Solution**: helper `copyToClipboard()` qui tente `navigator.clipboard.writeText` quand il existe, sinon retombe sur l'ancien `document.execCommand('copy')` via un `<textarea>` temporaire (qui fonctionne en HTTP). `handleCopyData` route désormais par ce helper.

**Prevention**: ne jamais supposer `navigator.clipboard` disponible — c'est une API à contexte sécurisé. Tester `navigator.clipboard?.writeText` avant usage et garder le fallback `execCommand` pour l'accès LAN/HTTP. (Pour supprimer le besoin du fallback : servir le LAN en HTTPS.)

---

## Old .db pool loads with no legend

> ⚠️ **PAR DESIGN** (2026) : un pool `.db` **sauvegardé avant** le fix « légende visible par défaut » recharge sans légende. Ce n'est pas une régression du fix — c'est le pool qui porte l'ancienne valeur.

**Cause** (`store/appStore.ts`, `restorePool`) : le remplissage du `legend_label` depuis le nom de fichier ne se fait **que si l'objet style est absent** (`data.styles[fileId] || { …, legend_label: filename }`). Un pool sauvegardé avant le fix a persisté des styles **avec** `legend_label: ''` (l'ancien défaut vide) → l'objet style existe → `restorePool` respecte le label vide → aucune trace n'a `showlegend` → **pas de légende**. À distinguer de la réhydratation au reload, qui elle passe par `/api/session` renvoyant `styles: {}` (objet absent) → labels remplis → légende OK.

**Symptom** : `Load` d'un vieux `.db` → courbes tracées mais pas de légende, alors qu'un upload frais des mêmes fichiers l'affiche.

**Contournement (sans code)** : bouton **Auto** dans la barre d'outils de `FileTable` (re-remplit les légendes depuis les noms), puis **Save / Save As** pour re-sauver le pool → le `.db` repart avec des labels remplis. Les pools sauvegardés **après** le fix ne sont pas concernés.

**Fix optionnel** (si on veut que les vieux pools s'affichent sans manip) : dans `restorePool`, forcer le repli filename quand le label persistté est vide, p.ex. `legend_label: data.styles[fileId]?.legend_label || f.filename.replace(/\.[^.]+$/, '')`. Non retenu ici : on préfère respecter ce qu'un pool a explicitement sauvé (un `Clear` volontaire doit rester vide au rechargement). Voir la section « Légende » de [CLAUDE.md](CLAUDE.md).

**Prevention**: quand un défaut applicatif change, se rappeler que les artefacts persistés (pools `.db`) portent l'**ancien** défaut ; le fallback ne s'applique qu'aux champs réellement absents, pas aux valeurs vides explicitement enregistrées.

---

## Clear all + Load freezes: RLock released cross-thread

> ✅ **FIXED** (2026): après un **Clear all** (qui appelait `/api/reset`) suivi d'un **Load**, l'app restait figée sur « Loading… ». Cause réelle : le verrou de session (`threading.RLock`) restait bloqué à jamais.

**Cause** (`sessions.py` `get_session` + `state.py`): la dépendance FastAPI `get_session` tient le verrou **à cheval sur le `yield`** :
```python
def get_session(...):
    st = manager.get(sid)
    with st.lock:      # __enter__ = acquire
        yield st       # requête traitée
                       # __exit__ = release
```
Pour une dépendance **sync-generator**, Starlette exécute `__enter__` et `__exit__` via le threadpool anyio, **potentiellement sur deux threads différents**. Un `threading.RLock` est lié au thread : `release()` depuis un autre thread lève `RuntimeError: cannot release un-acquired lock`. Pire, l'exception laisse le verrou **jamais relâché** → la requête suivante sur la **même session** (le `Load`) bloque indéfiniment sur `with st.lock:` → **UI figée en loading**. Le polling constant de l'onglet Metrics augmentait la probabilité de tomber sur le mauvais thread.

**Symptom**: `backend.err.log` montre `RuntimeError: cannot release un-acquired lock` à `sessions.py … with st.lock:` ; côté UI, un enchaînement Clear all → Load (ou toute séquence de requêtes rapprochées) fige l'app.

**Solution** (`state.py`): passer le verrou de session de `RLock` à `threading.Lock`. Un `Lock` **n'a pas de contrôle de propriétaire** → il tolère un `release()` cross-thread (pas d'exception, pas de blocage permanent). Sûr ici car le verrou n'est **jamais ré-entrant** (utilisé au seul endroit `get_session`, une fois par requête — vérifié par `grep "\.lock"`).
```python
# state.py — AppState.__init__
self.lock = threading.Lock()  # PAS RLock : release peut arriver sur un autre thread
```

**Prevention**: ne jamais tenir un `threading.RLock` à cheval sur le `yield` d'une dépendance FastAPI sync (acquire/release peuvent changer de thread). Utiliser un `threading.Lock` (tolère le release cross-thread) tant qu'il n'y a pas de ré-entrance, ou verrouiller **à l'intérieur** de chaque handler plutôt qu'autour du yield. Un `RLock` qui échoue au release reste verrouillé → gel garanti de la session.

---

## Page blanche en prod : `import Plotly from 'plotly.js'` laisse un import nu dans le bundle

> ✅ **FIXED** (2026-08-10) : après le déploiement du calque de dessin, `/plotter/` affichait **le fond et rien d'autre**. Aucune erreur serveur : le JS partait en `200` (9,9 Mo) et n'était simplement jamais exécuté.

**Cause** (`components/PlotView.tsx`) : le fix « export SVG/PNG » importait Plotly par son entrée **source** :
```ts
import Plotly from 'plotly.js';          // ❌ entrée source
```
`react-plotly.js` charge en interne le bundle **pré-compilé** (`require('plotly.js/dist/plotly')`). Importer l'entrée source ajoute donc **une deuxième copie** de Plotly ET tout son graphe de modules Node (`typedarray-pool`→`buffer`, `probe-image-size`→`stream`, `stream-parser`→`assert`). Rollup n'a pas pu résoudre `buffer/` et l'a traité **en dépendance externe** — c'est-à-dire qu'il a laissé un `import` nu en **première instruction du bundle** :
```js
import ame from"buffer/";   // le navigateur ne sait pas résoudre un specifier nu
```
Un specifier non résolu fait échouer le **chargement du module entier** : React ne monte jamais, la page reste vide. **Invisible en dev** : le serveur Vite pré-bundle les deps avec esbuild et résout ces stubs.

**Symptom** : page vide (fond stylé si le CSS passe encore), aucune erreur backend, JS servi en `200` dans `access.log`. Signature dans la sortie de build :
```
"buffer/" is imported by " buffer/?commonjs-external", but could not be resolved – treating it as an external dependency.
```
Symptômes annexes du même bug : bundle qui **double de taille** (9,9 Mo vs 5,0) et `1783 modules transformed` au lieu de `59`.

**Solution** : importer le **même** bundle pré-compilé que react-plotly.js → une seule copie, aucun graphe Node.
```ts
import Plotly from 'plotly.js/dist/plotly';   // ✅
```
Le chemin n'a pas de `.d.ts` → déclaration dans `src/vite-env.d.ts` (`declare module 'plotly.js/dist/plotly'`, réexporte les types de `'plotly.js'`). Les `import type … from 'plotly.js'` restent inchangés (effacés au build). Le CSS bundle passe de 82 ko à 17 ko : les 65 ko étaient le CSS de Plotly, que le bundle `dist` **injecte lui-même au runtime** — comportement d'avant le calque de dessin, rien n'est perdu.

**Prevention** : ne **jamais** ignorer un `could not be resolved – treating it as an external dependency` dans un build navigateur : contrairement aux messages « has been externalized for browser compatibility » (bénins, stubs vides), celui-ci laisse un vrai `import` nu et casse toute la page. Vérification en une commande après build :
```powershell
(Get-Content dist\assets\index-*.js -TotalCount 1).Substring(0,200)   # doit commencer par "(function(){", pas par "import … from"
```
Et plus généralement : **un test en dev ne vaut pas un test du build de prod** — Vite dev et Rollup ne résolvent pas les deps de la même façon. Voir la section « Calque de dessin » de [CLAUDE.md](CLAUDE.md).

---

## Sous-titre fantôme : `edits.titleText: false` casse aussi l'édition du titre

> ✅ **FIXED** (2026-08-10) : un « sous-titre » gris apparaissait sous le titre du graphe. Le désactiver via `edits.titleText: false` l'a bien supprimé — **et a supprimé l'édition du titre au clic** au passage. Symptôme rapporté : « titres des axes OK, titre principal KO ».

**Cause** (`plotly.js` ≥ 2.34, vérifié dans `src/components/titles/index.js` de la 2.35.3) :

```js
if(prop === 'title.text')          editAttr = 'titleText';
else if(prop.indexOf('axis') !== -1) editAttr = 'axisTitleText';
var editable = gd._context.edits[editAttr];        // ligne 106
// ligne 101 : "Subtitle is editable if and only if title is editable"
```

`titleText` est **le même interrupteur** que `axisTitleText` pour les axes. Le passer à `false` fait deux choses d'un coup : plus de sous-titre, plus d'édition en place. D'où l'asymétrie constatée entre axes et titre.

**Ce que le « sous-titre » est réellement** : pas une ligne permanente. Le sous-titre vide est transparent (`if(subtitleTxt === '') subtitleOpacity = 0`, ligne 125), puis `setPlaceholder` (lignes 344-350) lui pose le texte *« Click to enter Plot subtitle »* et un `mouseover → opacity 1`. Il se révèle donc **au survol**, c'est-à-dire pile quand on approche la souris du titre pour le cliquer.

**Solution** — neutraliser le sous-titre **sans** toucher à `editable` :

```ts
// PlotView.tsx — config
edits: { titleText: true, axisTitleText: true, /* … */ },
locales: { en: { dictionary: { 'Click to enter Plot subtitle': ' ' } } },
```
```css
/* App.css */
.gtitle-subtitle { pointer-events: none; }
```

- **`locales`** est un réglage **public** (`src/plot_api/plot_config.js:450`), typé dans `@types/plotly.js:2533` → aucun cast. ⚠️ **Un espace, pas une chaîne vide** : `src/lib/localize.js` fait `var out = dict[s]; if(out) return out;` — `''` est falsy et retombe sur la clé d'origine, `' '` passe.
- Clé **`en`** : la locale par défaut est `en-US`, dont la base `en` est consultée en repli.
- **`pointer-events: none`** en ceinture et bretelles : l'élément (déjà en `opacity 0`) ne reçoit plus ni survol (pas de révélation) ni clic (pas de sous-titre créé par mégarde). **Aucun effet de mise en page** : `src/plot_api/subroutines.js:460` lit le bbox du **titre** pour positionner le sous-titre, jamais l'inverse.

**Ne pas** tenter à la place :
- `dictionary: { … : '' }` → falsy, sans effet (cf. ci-dessus).
- Masquer en CSS le seul `.gtitle-subtitle` en `display:none` sans le dictionnaire → le texte d'invite reste **dans le DOM**, donc dans le SVG exporté (`tosvg.js` ne lit que le style **inline**, pas nos règles CSS).
- Un contournement maison « clic sur le titre → ouvre le panneau de réglages » : il entre en **conflit** avec l'édition en place une fois `titleText` réactivé (les deux se déclenchent sur le même clic).

**Prevention** : avant de désactiver un `config.edits.*` pour faire disparaître un élément, vérifier ce que cet interrupteur commande **d'autre** — dans Plotly un même flag couvre souvent le titre et ses satellites. Le réflexe utile : `node_modules/plotly.js/src/` est livré en clair, bien plus lisible que le `dist/` minifié.

---

## Le traitement s'appliquait à côté du chemin de plot

**Symptômes** (tous silencieux, aucun message d'erreur) : cocher un fichier après avoir réglé le lissage → il arrive **brut** au milieu de courbes traitées · F5 → cases toujours cochées mais plot brut · activer Normalize → **l'axe X écrasé en 0–1** · Median/Wavelet/FFT → aucun effet visible.

**Cause — deux ruptures qui se cumulent :**

1. **Le traitement était un canal parallèle.** `ProcessingPanel` postait sur `/api/process`, qui rangeait le DataFrame traité dans `state.processed_cache[file_id]` — **clé = `file_id` seul, sans les réglages**. `/plot-data` se contentait de *lire* ce cache. Donc : un fichier jamais passé par `/process` sortait brut, un fichier passé avec d'anciens réglages sortait périmé, et le cache étant en RAM, un restart serveur remettait tout au brut pendant que l'UI affichait toujours les réglages.
2. **Un champ non déclaré côté Pydantic est jeté sans erreur.** `ColumnSelector` envoyait bien `processing` (et `styles`) dans le corps de `/plot-data`, mais `PlotRequest` ne les déclarait pas → Pydantic les ignore **silencieusement**. Même chose côté `extractData`, où `processing` était un paramètre TypeScript déclaré et jamais mis dans le body.

Deux bugs collatéraux venaient du même endroit : le pipeline bouclait sur `select_dtypes(include=[np.number])`, donc **la colonne X était traitée comme les autres** ; et `_denoise` passait `window=`/`polyorder=` à **toutes** les méthodes alors que `median_filter_denoise(kernel_size)`, `wavelet_denoise(wavelet, level, mode)` et `fft_lowpass_denoise(cutoff_freq)` ne les acceptent pas → `TypeError`, non attrapé par le `except ValueError` de `denoise_methods.denoise` → **500** avalé en `console.error`.

**Solution — supprimer le canal parallèle** (`core/processing.py`) :

- `apply_processing(df, settings, columns, x_column)` est appelé **en ligne** par `/plot-data` et `/extract`. `/api/process`, `ProcessRequest`, `client.processFile` et l'effet de `ProcessingPanel` sont **supprimés** — le panneau est redevenu de l'UI pure sur le store.
- `PlotRequest` / `ExtractRequest` déclarent `processing: dict = {}`.
- `ColumnSelector` est le **seul** déclencheur de plot ; `processing` fait partie de son empreinte d'auto-plot (toutes les sections restent montées, donc ça couvre aussi l'onglet Process).
- **Clé de cache = `file_id | settings JSON | colonnes | x_column`** → une entrée périmée est impossible. Corollaire : `DELETE /api/files/{id}` doit purger **tous** les préfixes `f"{file_id}|"`, pas la clé `file_id`.
- `columns` = les colonnes réellement lues → **X n'est jamais traité**.
- `DENOISE_KWARGS` : chaque méthode reçoit les kwargs qu'elle accepte.

**Deux découvertes en vérifiant :**

- **Wavelet était un no-op même après le fix des kwargs** : pandas *copy-on-write* renvoie des `.values` en **lecture seule**, et pywt écrit dans son buffer d'entrée → `ValueError: buffer source array is read-only`, attrapé par la garde par-colonne → colonne laissée telle quelle, sans bruit. Fix dans `denoise_methods._validate_data` : `if not arr.flags.writeable: arr = arr.copy()`.
- **`subtract_baseline(x, y, …)` ignore `x`** pour `snip`/`asls`/`arpls` (seul `polynomial`, non exposé dans l'UI, l'utilise). Lui passer la vraie colonne X est correct mais ne change **rien** au résultat des trois méthodes proposées — ne pas l'annoncer comme un correctif visible.

**Prevention** :
- Un champ envoyé par le front doit exister dans le modèle Pydantic, sinon il disparaît **sans erreur**. Au moindre doute : `print(req)` côté endpoint.
- Un cache dont la clé ne porte pas les paramètres du calcul **est** un bug, pas une optimisation.
- Un traitement doit vivre **sur** le chemin de lecture des données, pas à côté avec un cache comme point de rendez-vous.
- Un `except` par colonne évite de perdre un fichier entier (pitfall #27) mais **cache aussi les vraies erreurs** : quand une méthode « ne fait rien », lire les `⚠️` du backend avant de conclure.

---

## API en 404 : `--base` posé, `VITE_API_URL` oublié

> ✅ **FIXED** (2026-08-11) : `/plotter/` s'affichait normalement (HTTP 200, assets OK) mais **tous** les appels API répondaient 404 — app inutilisable pendant ~14 h sans que rien ne le signale.

**Symptom** — dans `access.log`, des requêtes API en **chemin absolu**, sans le sous-chemin :
```
GET /api/session          404   referrer: http://mn-panda/plotter/
GET /api/metrics/summary  404
CreateFile() "<NGINX_DIR>/html/api/session" failed      (error.log)
```
nginx n'a pas de `location /api/` : la requête tombe sur la racine statique → 404.

**Cause** : un build de prod lancé à la main avec `--base=/plotter/` **mais sans** `VITE_API_URL=/plotter/api`. `src/api/client.ts` fait :
```ts
const API_BASE = import.meta.env.VITE_API_URL || '/api';   // <- repli silencieux
```
Ce sont **deux réglages distincts**, et ils échouent très différemment :

| Oubli | Conséquence | Visibilité |
|---|---|---|
| `--base=/plotter/` | assets en `/assets/…` → 404 → **page blanche** | immédiate |
| `VITE_API_URL=/plotter/api` | page **parfaite**, toutes les données en 404 | **aucune** — il faut ouvrir la console ou les logs |

Le second est le plus dangereux : rien ne distingue visuellement l'app cassée d'une app sans données chargées.

**Diagnostic en une commande** — l'URL d'API est compilée en dur dans le bundle :
```powershell
Select-String dist\assets\index-*.js -Pattern '/plotter/api' | Measure-Object   # 0 = casse
```

**Solution** : rebuilder avec les **deux** réglages (ce que fait déjà `deploy/promote-exp-to-prod.ps1:69-70` — la prod ne devrait jamais se builder à la main) :
```powershell
$env:VITE_API_URL = '/plotter/api'; npm run build -- --base=/plotter/
```

**Prevention** — `web/frontend/scripts/check-build.mjs`, branché en **`postbuild`** dans `package.json` : npm le lance après *chaque* `npm run build`, y compris manuel. Il extrait la base réellement écrite dans `dist/index.html` et exige que le bundle contienne `<base>api` ; sinon il sort en code 1 avec la commande correcte à recopier. C'est une vérification de **cohérence interne** : rien n'est codé en dur, elle vaut pour `/plotter/`, `/plotter-exp/` et la racine. Il contrôle au passage l'absence d'import nu (cf. « Page blanche en prod »).

⚠️ Le garde-fou rejette **après** l'écriture du `dist/` : un build refusé laisse donc un `dist/` cassé sur le disque. Les scripts de promotion s'arrêtent (`$LASTEXITCODE -ne 0` → `throw`) avant de redémarrer quoi que ce soit, mais la prod étant servie **directement** depuis `dist/`, un build refusé la casse jusqu'au rebuild correct. L'échec est bruyant : relancer immédiatement avec la commande affichée.

## Un tableau simulé en annotation : ni aligné, ni capable de pousser les axes

**Symptôme** — le tableau de stats posé dans la figure a ses **colonnes décalées
par rapport aux titres**, et il **flotte par-dessus la courbe** : la zone de tracé
ne se réduit pas pour lui faire de la place.

**Cause** — première version : une **annotation** Plotly contenant un bloc de
texte dont les colonnes tenaient par du bourrage d'espaces insécables en police
monospace. Deux impasses, chacune structurelle :

1. **L'alignement est typographique.** Il dépend de la police effectivement
   appliquée au rendu. Dès que ce n'est pas exactement du monospace, ou que les
   espaces sont traités autrement, la grille se décale. Aucun réglage ne fiabilise ça.
2. **Une annotation ne réserve jamais de place.** En coordonnées `paper`, elle est
   posée *au-dessus* du tracé. Plotly ne prévoit aucun mécanisme pour qu'une
   annotation repousse les axes — contrairement à une légende ou à une marge.

**Correctif** — utiliser un **vrai trace `table`** :

```ts
{ type: 'table', domain: { x: [0, 1], y: [0, height] },
  columnwidth, header: { values, align }, cells: { values /* COLONNE-major */, align } }
```

…et rétrécir la bande cartésienne d'autant, ce que l'annotation ne pouvait pas faire :

```ts
if (statsTable && l.yaxis) {
  const top = Math.min(0.9, statsTable.height + 0.08);
  l.yaxis.domain = [top, 1];
  if (l.yaxis2) l.yaxis2.domain = [top, 1];   // y2 « overlaying: y » doit suivre
}
```

L'alignement devient **structurel** (header et cells partagent les mêmes colonnes,
dans n'importe quelle police) et la zone de dessin se redimensionne réellement.

**Et l'export ?** Le trace `table` se dessine dans `gd._fullLayout._paper`
(`src/traces/table/plot.js:20`) — le SVG que `toSVG` sérialise
(`src/snapshot/tosvg.js:32`). Il **part donc dans le PNG/SVG**, comme le reste.
Le module est bien dans le bundle utilisé (`lib/index.js:47`).

**Ce qu'on perd** — un trace se place par son `domain`, il ne se glisse pas à la
souris comme une annotation. La position est un choix de mise en page, pas un
geste.

**Bénéfice collatéral** — un trace n'est **pas** une annotation, donc il ne
traverse jamais `layout.annotations`. Toute la machinerie de filtrage qu'exigeait
la version annotation (marqueur + exclusion dans `handleRelayout` pour éviter que
la boîte soit capturée dans `drawings` et figée) **disparaît**.

**Cells en COLONNE-major** — `cells.values` attend *un tableau par colonne*, pas
par ligne. C'est l'inverse d'une table HTML ; `buildStatsGrid` (`utils/stats.ts`)
produit directement la bonne forme.

## `npm run build` nu écrase le dist que la prod sert en direct

**Symptôme** — après un simple `npm run build` en session de dev, `/plotter/`
part en page blanche et toutes ses requêtes API en 404. Rien ne l'annonce : le
build affiche « built in 12s » et le contrôle de cohérence passe.

**Cause** — le service `CSVPlotter` sert `web/frontend/dist` **en direct**
(nginx `alias` sur ce dossier, cf. `deploy/services-plotter.conf`). Un build de
dev l'écrit en base `/` au lieu de `/plotter/`. Comme `dist/` **n'est pas
versionné**, l'ancien build est définitivement perdu — il n'y a rien à restaurer,
seulement à reconstruire.

**Correctif** — rebuild aux flags de déploiement :

```powershell
$env:VITE_API_URL='/plotter/api'; npm run build -- --base=/plotter/
```

⚠️ **Depuis PowerShell, pas depuis Git Bash.** Sous Git Bash (MSYS), un argument
qui commence par `/` est converti en chemin Windows : `--base=/plotter/` devient
`--base=/Program Files/Git/plotter/`. Et comme `VITE_API_URL` subit la **même**
conversion, les deux valeurs restent cohérentes entre elles → `check-build.mjs`
valide un dist pourtant inutilisable. Poser `MSYS_NO_PATHCONV=1` sinon.

**Garde-fou** — `check-build.mjs` détecte désormais le cas (build en base `/` +
service `CSVPlotter`/`CSVPlotter_Exp` en cours d'exécution) et affiche la commande
de réparation. C'est un **avertissement**, pas un rejet : à ce stade le dist est
déjà écrit, seule la reconstruction répare.

**Ne pas** lancer `promote-exp-to-prod.ps1` pour réparer en cours de
développement : son étape 1 est un `robocopy /MIR` de `260324-exp\web` vers
`260324\web`, qui **supprime le code non encore propagé vers la beta**.

## Un tableau flex écrasé à zéro par `flex-basis: auto`

**Symptôme** — dans l'onglet Extract, le tableau de résumé du bas **disparaît**.
Il est pourtant bien dans le DOM, sans erreur console : il est simplement haut
de **0 pixel**.

**Cause** — les deux blocs empilés déclaraient `flex-basis: auto` :

```css
.extract-values  { flex: 1 1 auto; min-height: 0; }   /* table des valeurs */
.extract-summary { flex: 0 1 auto; min-height: 0; }   /* résumé */
```

Avec `basis: auto`, la taille initiale de chaque bloc est la hauteur de son
**contenu**. La table des valeurs contient toutes les lignes de fichiers, donc
la somme dépasse le conteneur et le navigateur doit **rétrécir** — en
répartissant proportionnellement à la base. Le gros bloc encaisse peu en
proportion, le petit prend presque tout, et `min-height: 0` l'autorise à tomber
à zéro.

Le déclencheur avait été un changement sans rapport apparent (`width: max-content`
+ `white-space: nowrap`), qui a fait grandir la base de la table des valeurs et
rompu un équilibre qui ne tenait que par chance.

**Correctif**

```css
.extract-values  { flex: 1 1 0;    min-height: 140px; }  /* base 0 */
.extract-summary { flex: 0 0 auto; max-height: 50%; }    /* jamais comprimé */
```

`flex-basis: 0` sur l'élément qui grandit rend la répartition de l'espace
**indépendante de la hauteur du contenu** — c'est le remède standard. Et
`flex: 0 0 auto` sur le voisin garantit qu'il ne peut plus être comprimé.

**Règle générale** — dans une colonne flex de hauteur fixe, un seul élément doit
absorber l'espace, et il doit le faire avec `basis: 0`. Deux `basis: auto` qui se
disputent la place produisent un gagnant proportionnel à son contenu, pas à son
importance.

**À vérifier aussi** — un conteneur intermédiaire sans `display: flex` annule
silencieusement le `flex: 1` de son enfant (c'était le cas de `.stats-table-wrap`,
dont la zone de défilement interne n'existait donc pas).

## Plotly garde un état de visibilité que React écrase

**Symptôme** — on masque une courbe en cliquant sa légende ; elle **revient
toute seule** dès qu'on touche à autre chose (une couleur, une case cochée, un
réglage). Et le tableau de stats de la figure continue de compter la courbe
masquée.

**Cause** — un clic de légende écrit `visible: 'legendonly'` dans l'état
**interne** de Plotly. Or `data` est reconstruit depuis le store à chaque rendu
et ne porte aucun `visible` : le rebuild remet donc tout à `true`. L'état vivait
à un endroit que React ne connaissait pas, et que React piétinait.

**Correctif** — reprendre l'événement, et **retourner `false`** pour que Plotly
n'entretienne pas un état parallèle :

```ts
const handleLegendClick = useCallback((e: { curveNumber: number }) => {
  const label = labelOfCurve(e.curveNumber);
  if (label) toggleHiddenLegend(label);
  return false;                       // <-- Plotly ne garde rien de son côté
}, [labelOfCurve, toggleHiddenLegend]);
```

`data` calcule alors `visible` depuis le store, et tout ce qui dérive de « ce que
la figure montre » (ici le tableau de stats, via `shownFiles`) suit
automatiquement. Clé = le **label** de légende, puisque les entrées sont
dédupliquées par label et groupées par `legendgroup`.

⚠️ Intercepter `onLegendClick` neutralise aussi le **double-clic** natif
(isoler une série) : il faut reprendre `onLegendDoubleClick` dans la foulée,
sinon on supprime une fonctionnalité sans s'en rendre compte.

**Règle générale** — le même piège que la capture d'annotations : dès qu'une
bibliothèque tient un état que l'on reconstruit à chaque rendu, il faut soit le
remonter dans le store, soit ne jamais reconstruire. Les deux à moitié donnent un
bug intermittent.

## Une valeur extraite sans la recette qui l'a produite

**Symptôme** — on ajoute des fichiers après avoir extrait `max(Force)` : les
nouvelles lignes affichent `-`. Pour les remplir il faut re-saisir tous les
réglages **et** retaper le nom de colonne à l'identique — une faute de frappe et
on crée une deuxième colonne au lieu de compléter la première.

**Cause** — l'onglet Extract ne stockait que le **résultat**
(`extractedColumns[file_id][nom] = value`), jamais les **entrées** (colonne,
opération, X, intervalle, seuil). Un calcul dont on jette les paramètres n'est
pas rejouable : le nom de colonne est alors la seule trace de la recette, et
c'est une trace que l'humain doit re-taper de mémoire.

**Correctif** — un slice `extractRecipes: Record<nomColonne, ExtractRecipe>`
rempli au moment de l'extraction, et **un seul** chemin d'exécution partagé :

```ts
// « Extract » exécute une recette fraîche, « ↻ Re-extract » rejoue les enregistrées.
const runRecipe = async (colName: string, recipe: ExtractRecipe) => { … }
```

Deux détails qui comptent :

- **Le `processing` n'est PAS figé dans la recette** — on rejoue avec celui de la
  session, comme `/plot-data`. Le figer recréerait le canal parallèle supprimé au
  commit `726c2d6` (cf. « Le traitement s'appliquait à côté du chemin de plot ») :
  une valeur calculée avec des réglages que l'écran n'affiche plus.
- **Pas de mode « ne combler que les trous »** — `Re-extract` recalcule tout ce
  qui est coché. Ne remplir que les cases vides laisserait survivre des valeurs
  périmées à côté de valeurs fraîches, dans la même colonne, sans rien de visible.

**Persistance** — les recettes voyagent dans `plot_style.recipes`, comme
`drawings` / `stats` / `hiddenLegend` : **zéro modif backend**. Un pool sauvé
avant ce champ garde ses colonnes mais elles ne sont pas rejouables — le bouton
les ignore et l'annonce dans son statut, plutôt que d'échouer en silence.

**Règle générale** — dès qu'un résultat affiché vient de paramètres saisis à la
main, stocker les paramètres avec le résultat. Sinon le seul moyen de le
reproduire est la mémoire de l'utilisateur.

## « Mon changement n'apparaît pas » : aucun serveur dev ne tournait

**Symptôme** — le code est modifié, `tsc`/`lint`/`tests` passent, le bouton est
bien dans le JSX… et il est invisible dans le navigateur. On soupçonne une
condition d'affichage, du CSS, le store — tout sauf le bon coupable.

**Cause** — l'onglet ouvert pointait sur `/plotter/` (ou `/plotter-exp/`),
c'est-à-dire un **`dist/` buildé**, pas le code source. Les services NSSM tournent
en permanence : on peut très bien « avoir l'app ouverte » sans qu'aucun Vite ne
tourne. Éditer `src/` n'a alors **strictement aucun effet visible**.

**Diagnostic en deux commandes** — avant de chercher dans le code :

```bash
netstat -ano | grep LISTENING | grep -E ":(5173|5174|9099|9199)"   # un Vite tourne-t-il ?
ls -l web/frontend/dist/index.html                                    # le dist date de quand ?
grep -o 'src="[^"]*"' web/frontend/dist/index.html                    # base / ou /plotter/ ?
```

Un `dist/index.html` plus vieux que le fichier source qu'on vient d'éditer suffit
à conclure. Ensuite : soit lancer `start-plotter.ps1` (dev, 5174), soit rebuilder
la cible (⚠️ **depuis PowerShell**, cf. « `npm run build` nu écrase le dist »).

**Règle générale** — avant de déboguer un symptôme visuel, vérifier **quel
artefact** le navigateur charge. Un hash de bundle inchangé après un build, c'est
un build qui n'a rien produit de neuf.
