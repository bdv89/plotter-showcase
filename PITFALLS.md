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
