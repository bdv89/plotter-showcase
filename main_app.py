import sys
import os
import copy
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QLabel, QFileDialog, QComboBox, QGridLayout,
                            QGroupBox, QFormLayout, QCheckBox, QDoubleSpinBox, QMessageBox,
                            QTabWidget, QListWidget, QPushButton,
                            QAbstractItemView, QListWidgetItem, QTabBar, QSizePolicy)

from data_manager import DataManager
from plot_window import PlotWindow
from ui_components import FileStyleTableWidget
from storage_manager import StorageManager
from data_pipeline import (
    DataPipeline,
    register_default_processors,
    create_fit_multi_peaks_processor,
)
from data_cache import DataCache
from parquet_linker import ParquetLinker, MultiTableLinkDialog
from rename_legend_dialog import BatchLegendRenameDialog
from processing import (
    create_baseline_processor,
    create_denoise_processor,
    create_normalize_processor,
    create_outliers_processor,
    create_smooth_processor,
    create_time_averaging_processor,
)
from version import __version__, check_for_updates, format_version_display
from app_logging import logger

class CSVPlotterApp(QMainWindow):
    """Main application for plotting CSV files"""
    def __init__(self):
        super().__init__()
        self.plot_window = None
        self.setWindowTitle(f"CSV Visualizer ({format_version_display(__version__)})")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(800, 600)  # Prevent erratic resizing when table is empty

        self.csv_files = []
        self.current_folder = ""
        
        self.line_colors = {}
        self.line_colors_y2 = {}  # Colors for Y2 axis (right)
        self.line_styles = {}
        self.legend_labels = {}

        # Initialize pending plot settings storage
        self.pending_plot_settings = None
        self.processing_settings = None
        self.pending_processing_settings = None
        self.pending_time_columns = []  # Store numeric columns until processing_window is ready

        # Store last fit results for display in processing window
        self.last_fit_results = None

        # Visual options for peak fitting display
        self.show_peak_markers = True
        self.show_peak_numbers = True

        # Guard to suppress automatic Plot window opening during bulk operations
        self._suppress_plot_window_open = False

        # Initialize data cache and pipeline
        self.cache = DataCache()
        self.pipeline = DataPipeline()
        register_default_processors(self.pipeline)
        
        # Initialize multi-table parquet linker
        self.parquet_linker = ParquetLinker(self)

        self.init_ui()

        # Check for updates on startup (after UI is initialized)
        self._check_updates_on_startup()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Apply app-wide button styles via role-based properties
        self.setStyleSheet(self._build_stylesheet())

        def create_button(label, handler, role):
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            btn.setProperty("role", role)
            return btn

        # Top action buttons: 4 columns, stacked per column
        top_buttons_widget = QWidget()
        top_row_layout = QHBoxLayout(top_buttons_widget)

        # Column 1
        col1 = QVBoxLayout()
        for label, handler in [
            ("Select Folder", self.select_folder),
            ("Import Data", self.import_data),
        ]:
            btn = create_button(label, handler, role="primary")
            col1.addWidget(btn)
        top_row_layout.addLayout(col1)

        # Column 2
        col2 = QVBoxLayout()
        # Load is primary (white), Save is save-action (blue)
        btn_load_pool = create_button("Load Pool", self.load_data_pool, role="primary")
        col2.addWidget(btn_load_pool)
        btn_save_pool = create_button("Save Pool", self.save_data_pool, role="save")
        col2.addWidget(btn_save_pool)
        top_row_layout.addLayout(col2)

        # Column 3
        col3 = QVBoxLayout()
        for label, handler in [
            ("Remove Selected", self.remove_selected_from_pool),
            ("Clear", self.clear_plot),
        ]:
            btn = create_button(label, handler, role="destructive")
            col3.addWidget(btn)
        top_row_layout.addLayout(col3)

        # Column 4
        col4 = QVBoxLayout()
        btn_link = create_button("Link Database", self.link_to_database, role="secondary")
        col4.addWidget(btn_link)
        # New: Rename legend button under Link Database
        btn_rename = create_button("Rename Legend", self.rename_legend_batch, role="secondary")
        col4.addWidget(btn_rename)
        top_row_layout.addLayout(col4)

        # Column 5
        col5 = QVBoxLayout()
        btn_extract = create_button("Extract Data", self.open_extraction_dialog, role="tool")
        col5.addWidget(btn_extract)
        top_row_layout.addLayout(col5)

        # Prevent the top buttons block from consuming extra vertical space
        top_buttons_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        main_layout.addWidget(top_buttons_widget)

        # Folder/status display (no button here now)
        folder_layout = QHBoxLayout()
        self.folder_label = QLabel("No folder selected")
        folder_layout.addWidget(self.folder_label)
        main_layout.addLayout(folder_layout)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        main_layout.addLayout(status_layout)
        
        # Create tabs
        self.tabs = QTabWidget()
        
        # Main plotting tab
        plot_tab = QWidget()
        plot_layout = QVBoxLayout(plot_tab)
        
        # File list and controls
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Data Files (check to plot):"))
        
        self.file_list = FileStyleTableWidget(self)
        # Make the data files table occupy remaining vertical space
        self.file_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_list.cellClicked.connect(self.check_file_clicked)
        self.file_list.colorChanged.connect(
            lambda filename, color: self.update_style_parameter('color', filename, color))
        self.file_list.y2ColorChanged.connect(
            lambda filename, color: self.update_style_parameter('y2_color', filename, color))
        self.file_list.styleChanged.connect(
            lambda filename, style: self.update_style_parameter('style', filename, style))
        self.file_list.legendChanged.connect(
            lambda filename, text: self.update_style_parameter('legend', filename, text))
        self.file_list.linkClicked.connect(self.handle_link_clicked)
        # Give the table a stretch factor so it grows vertically
        left_layout.addWidget(self.file_list, 1)
        
        # Column selection: Tab bar + one dropdown per axis
        self.axis_tabbar = QTabBar()
        self.axis_tabbar.addTab("X Axis")
        self.axis_tabbar.addTab("Y Axis Left")
        self.axis_tabbar.addTab("Y Axis Right")
        left_layout.addWidget(self.axis_tabbar)

        # Second line: three drop-downs aligned with tabs
        dropdowns_layout = QHBoxLayout()
        self.x_combo = QComboBox()
        self.y_list = QComboBox()   # kept name for backward compatibility
        self.y2_list = QComboBox()  # kept name for backward compatibility
        dropdowns_layout.addWidget(self.x_combo)
        dropdowns_layout.addWidget(self.y_list)
        dropdowns_layout.addWidget(self.y2_list)
        left_layout.addLayout(dropdowns_layout)
        
        # Action buttons previously here are now placed as top/bottom stacks on main window
        
        plot_layout.addLayout(left_layout)
        
        # Add tabs (only Plot; processing now uses floating window in plot window)
        self.tabs.addTab(plot_tab, "Plot")
        
        main_layout.addWidget(self.tabs)

        # Bottom action buttons (side-by-side)
        bottom_buttons_widget = QWidget()
        bottom_buttons_layout = QHBoxLayout(bottom_buttons_widget)
        # Bottom row: load settings (primary/white), plot (plot control/green), export (save/blue)
        bottom_buttons_layout.addWidget(create_button("Load Settings", self.load_plot_settings_main, role="primary"))
        bottom_buttons_layout.addWidget(create_button("Plot Selection", self.plot_selected, role="plot"))
        bottom_buttons_layout.addWidget(create_button("Export Data", self.export_data, role="save"))
        # Prevent bottom buttons row from stretching vertically
        bottom_buttons_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        main_layout.addWidget(bottom_buttons_widget)

        # Ensure the central tabs take all remaining vertical space
        # Order in main_layout: 0=top_buttons, 1=folder_layout, 2=status_layout, 3=tabs, 4=bottom_buttons
        main_layout.setStretch(0, 0)
        main_layout.setStretch(1, 0)
        main_layout.setStretch(2, 0)
        main_layout.setStretch(3, 1)
        main_layout.setStretch(4, 0)

    # Data Processing tab removed

    def _setup_action_buttons(self, parent_layout):
        # Deprecated: buttons moved to top/bottom of main window per new UI layout
        return

    def _build_stylesheet(self):
        """Define role-based button styles for main window actions."""
        return """
        QPushButton {
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        /* Primary actions: white */
        QPushButton[role="primary"] {
            background-color: #ffffff;
            color: #222222;
            border: 1px solid #cfcfcf;
        }
        QPushButton[role="primary"]:hover {
            background-color: #f7f7f7;
        }
        QPushButton[role="primary"]:pressed {
            background-color: #eeeeee;
        }

        /* Secondary actions: grey border only */
        QPushButton[role="secondary"] {
            background-color: transparent;
            color: #444444;
            border: 1px solid #bdbdbd;
        }
        QPushButton[role="secondary"]:hover {
            background-color: #f9f9f9;
        }
        QPushButton[role="secondary"]:pressed {
            background-color: #efefef;
        }

        /* Save/export actions: blue */
        QPushButton[role="save"] {
            background-color: #1976d2;
            color: #ffffff;
            border: 1px solid #1565c0;
        }
        QPushButton[role="save"]:hover {
            background-color: #1565c0;
        }
        QPushButton[role="save"]:pressed {
            background-color: #0d47a1;
        }

        /* Destructive actions: subtle red */
        QPushButton[role="destructive"] {
            background-color: #fdecea; /* light red */
            color: #c62828;             /* red text */
            border: 1px solid #f5c6cb;  /* soft red border */
        }
        QPushButton[role="destructive"]:hover {
            background-color: #f9d7d5;
        }
        QPushButton[role="destructive"]:pressed {
            background-color: #f8caca;
        }

        /* Plot control: strong green, white text */
        QPushButton[role="plot"] {
            background-color: #2e7d32; /* strong green */
            color: #ffffff;             /* white text */
            border: 1px solid #1b5e20;  /* darker green border */
        }
        QPushButton[role="plot"]:hover {
            background-color: #1b5e20; /* darker on hover */
        }
        QPushButton[role="plot"]:pressed {
            background-color: #145a1f; /* darkest on press */
        }
        """

    def _extract_preset_suffix(self, filename):
        """Extract preset suffix from filename (e.g., 'OCV' from 'sample_01_OCV.csv')"""
        basename = os.path.splitext(filename)[0]  # Remove extension (.csv, .xlsx, etc.)
        suffix = basename.split('_')[-1]  # Get last part after underscore
        return suffix if suffix else None

    def _auto_load_preset_if_applicable(self, new_files):
        """Auto-load preset if conditions are met (silent, no user messages)

        Conditions:
        - All new files have the same preset suffix
        - A matching .plot file exists in plot_settings/

        Args:
            new_files: List of file dicts with 'filename' key
        """
        logger.debug(f"[AUTO-PRESET] Called with {len(new_files)} files")

        if not new_files:
            logger.debug("[AUTO-PRESET] No files, skipping")
            return

        # Extract unique suffixes from all new files
        suffixes = {self._extract_preset_suffix(f['filename'])
                    for f in new_files
                    if self._extract_preset_suffix(f['filename']) is not None}

        logger.debug(f"[AUTO-PRESET] Detected suffixes: {suffixes}")

        # Only auto-load if exactly one unique suffix (all files have same type)
        if len(suffixes) == 1:
            suffix = suffixes.pop()
            logger.debug(f"[AUTO-PRESET] Single suffix detected: '{suffix}'")

            # Build path to preset file (compatible with .exe via __file__)
            preset_dir = os.path.join(os.path.dirname(__file__), 'plot_settings')
            preset_path = os.path.join(preset_dir, f'{suffix}.plot')

            logger.debug(f"[AUTO-PRESET] Looking for preset: {preset_path}")
            logger.debug(f"[AUTO-PRESET] Preset exists: {os.path.exists(preset_path)}")

            # Silently attempt to load preset
            settings_data = StorageManager.load_plot_settings_from_path(preset_path)
            logger.debug(f"[AUTO-PRESET] Settings loaded: {settings_data is not None}")

            if settings_data:
                # Store settings for future use
                self.pending_plot_settings = settings_data
                logger.debug(f"[AUTO-PRESET] Preset stored in pending_plot_settings")

                # Apply immediately if plot window exists
                if self.plot_window and hasattr(self.plot_window, 'canvas'):
                    logger.debug(f"[AUTO-PRESET] Plot window exists, applying immediately")
                    self.apply_plot_settings_to_window(settings_data)
                else:
                    logger.debug(f"[AUTO-PRESET] No plot window yet, stored for later")
        else:
            logger.debug(f"[AUTO-PRESET] Multiple suffixes ({len(suffixes)}), skipping auto-load")

    def _apply_preset_to_main_window(self, settings_data):
        """Apply preset settings to main window X/Y combobox (before plotting)

        Args:
            settings_data: Dict with 'plot_settings' containing x_column, y_columns, y2_columns
        """
        logger.debug(f"[APPLY-PRESET-MAIN] Applying preset to main window comboboxes")

        if 'plot_settings' not in settings_data:
            logger.debug(f"[APPLY-PRESET-MAIN] No plot_settings in preset, skipping")
            return

        plot_settings = settings_data['plot_settings']

        # Apply X column selection
        if 'x_column' in plot_settings and plot_settings['x_column']:
            x_col = plot_settings['x_column']
            logger.debug(f"[APPLY-PRESET-MAIN] Setting X axis to: {x_col}")

            # Find index of column in combobox
            index = self.x_combo.findText(x_col)
            if index >= 0:
                self.x_combo.setCurrentIndex(index)
                logger.debug(f"[APPLY-PRESET-MAIN] X axis set successfully")
            else:
                logger.debug(f"[APPLY-PRESET-MAIN] WARNING: X column '{x_col}' not found in combobox")

        # Apply Y1 columns selection (QComboBox = single selection)
        if 'y_columns' in plot_settings and plot_settings['y_columns']:
            y_col = plot_settings['y_columns'][0]  # Take first column (QComboBox single selection)
            logger.debug(f"[APPLY-PRESET-MAIN] Setting Y axis to: {y_col}")

            index = self.y_list.findText(y_col)
            if index >= 0:
                self.y_list.setCurrentIndex(index)
                logger.debug(f"[APPLY-PRESET-MAIN] Y axis set successfully")
            else:
                logger.debug(f"[APPLY-PRESET-MAIN] WARNING: Y column '{y_col}' not found in combobox")

        # Apply Y2 columns selection (QComboBox = single selection)
        if 'y2_columns' in plot_settings and plot_settings['y2_columns']:
            y2_col = plot_settings['y2_columns'][0]  # Take first column (QComboBox single selection)
            logger.debug(f"[APPLY-PRESET-MAIN] Setting Y2 axis to: {y2_col}")

            index = self.y2_list.findText(y2_col)
            if index >= 0:
                self.y2_list.setCurrentIndex(index)
                logger.debug(f"[APPLY-PRESET-MAIN] Y2 axis set successfully")
            else:
                logger.debug(f"[APPLY-PRESET-MAIN] WARNING: Y2 column '{y2_col}' not found in combobox")

        logger.debug(f"[APPLY-PRESET-MAIN] Preset applied to main window successfully")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if folder:
            # VALIDATION: Vérifier que le dossier est valide
            if not os.path.exists(folder):
                self.status_label.setText(f"ERROR: Selected folder does not exist: {folder}")
                return
            if not os.path.isdir(folder):
                self.status_label.setText(f"ERROR: Selected path is not a directory: {folder}")
                return

            # Capture if table was empty BEFORE loading (for auto-preset)
            was_empty = len(self.csv_files) == 0

            self.current_folder = folder
            self.folder_label.setText(f"Folder: {folder}")
            self.status_label.setText("Loading data files...")

            # Clear rows without resetting headers to avoid blank rows accumulating
            self.file_list.setRowCount(0)
            self.x_combo.clear()
            self.y_list.clear()
            self.y2_list.clear()
            if self.plot_window:
                self.plot_window.canvas.clear_plot()

            # Cache UI removed; default to using cache
            use_cache = True

            self.loader_thread = DataManager(folder, use_cache=use_cache)
            self.loader_thread.update_progress.connect(self.update_status)
            # Use lambda to pass was_empty state to display function
            self.loader_thread.finished_loading.connect(
                lambda csv_files: self._on_files_loaded(csv_files, was_empty)
            )
            self.loader_thread.data_ready.connect(self.on_data_processed)
            self.loader_thread.start()

    def update_status(self, message):
        self.status_label.setText(message)

    def import_data(self):
        # Capture if table was empty BEFORE import (for auto-preset)
        was_empty = len(self.csv_files) == 0

        imported_data = StorageManager.import_data(self)
        if imported_data:
            # imported_data is now a list of files
            if isinstance(imported_data, list):
                # Multiple files imported
                new_files = imported_data  # Track newly imported files

                self.csv_files.extend(imported_data)
                filenames = [file_data['filename'] for file_data in imported_data]
                self.update_status(f"Imported {len(imported_data)} files: {', '.join(filenames)}")
            else:
                # Single file (backward compatibility, should not happen with new code)
                new_files = [imported_data]  # Wrap single file in list

                self.csv_files.append(imported_data)
                self.update_status(f"Imported {imported_data['filename']} successfully")

            # Display files first (populates X/Y comboboxes)
            self.display_csv_files(self.csv_files)

            # Auto-load preset if table was empty and conditions met
            if was_empty:
                self._auto_load_preset_if_applicable(new_files)

                # Apply preset to main window comboboxes
                if self.pending_plot_settings:
                    self._apply_preset_to_main_window(self.pending_plot_settings)

    def export_data(self):
        """Export selected files to various formats with parquet data"""
        checked_files = self.file_list.get_checked_items()
        
        # Extend each CSV file with its linked parquet data if available
        enhanced_csv_files = []
        for csv_file in self.csv_files:
            filename = csv_file['filename']
            if filename in checked_files:
                enhanced_file = csv_file.copy()
                
                # Add linked parquet data if available
                if hasattr(self.file_list, 'parquet_columns') and filename in self.file_list.parquet_columns:
                    enhanced_file['parquet_data'] = self.file_list.parquet_columns[filename]

                # Add extracted data if available
                if hasattr(self.file_list, 'extracted_columns') and filename in self.file_list.extracted_columns:
                    enhanced_file['extracted_data'] = self.file_list.extracted_columns[filename]

                enhanced_csv_files.append(enhanced_file)
        
        # Call the storage manager with enhanced data
        if enhanced_csv_files:
            StorageManager.export_data(self, enhanced_csv_files, checked_files)
        else:
            StorageManager.export_data(self, self.csv_files, checked_files)

    def save_data_pool(self):
        # Basic plot settings (columns)
        # Save display texts for later UI restoration
        y_text = self.y_list.currentText() if self.y_list.currentIndex() >= 0 else ''
        y2_text = self.y2_list.currentText() if self.y2_list.currentIndex() >= 0 else ''
        plot_settings = {
            'x_column': self.x_combo.currentText(),
            'y_columns': [y_text] if y_text else [],
            'y2_columns': [y2_text] if y2_text else []
        }

        # Advanced plot style settings
        plot_style_settings = None
        if self.plot_window and hasattr(self.plot_window, 'canvas'):
            plot_style_settings = self.plot_window.canvas.plot_style.copy()

        # Collect fit results from all files
        fit_results = {}
        if hasattr(self, 'csv_files'):
            for file_data in self.csv_files:
                filename = file_data['filename']
                df = file_data.get('data')
                if df is not None and hasattr(df, 'attrs') and 'fit_results' in df.attrs:
                    fit_results[filename] = df.attrs['fit_results']

        checked_files = self.file_list.get_checked_items()

        # Enhance csv_files with extracted_data before saving (same pattern as export_data)
        enhanced_csv_files = []
        for csv_file in self.csv_files:
            filename = csv_file['filename']
            enhanced_file = csv_file.copy()

            # Add extracted data if available
            if hasattr(self.file_list, 'extracted_columns') and filename in self.file_list.extracted_columns:
                enhanced_file['extracted_data'] = self.file_list.extracted_columns[filename]
                logger.debug(f"🟡 Adding extracted_data to {filename} for pool save")

            enhanced_csv_files.append(enhanced_file)

        StorageManager.save_data_pool(
            self, enhanced_csv_files, self.line_colors, self.line_colors_y2,
            self.line_styles, self.legend_labels, plot_settings, checked_files,
            plot_style_settings=plot_style_settings,
            processing_settings=self.processing_settings,
            fit_results=fit_results if fit_results else None
        )

    def load_data_pool(self):
        # Suppress plot window auto-open during pool load
        self._suppress_plot_window_open = True
        try:
            data_pool = StorageManager.load_data_pool(self)
            if data_pool:
                self.csv_files = data_pool['csv_files']
                self.line_colors = data_pool['line_colors']
                self.line_colors_y2 = data_pool.get('line_colors_y2', {})
                self.line_styles = data_pool['line_styles']
                self.legend_labels = data_pool.get('legend_labels', {})
                
                self.display_csv_files(self.csv_files)

                # Restore extracted columns from loaded csv_files
                for csv_file in self.csv_files:
                    if 'extracted_data' in csv_file and csv_file['extracted_data']:
                        self.file_list.extracted_columns[csv_file['filename']] = csv_file['extracted_data']

                # Update display for extracted columns
                if hasattr(self.file_list, 'extracted_columns') and self.file_list.extracted_columns:
                    self.file_list.update_extracted_columns_display()
                    logger.info(f"✅ Restored extracted columns for {len(self.file_list.extracted_columns)} files")

                # Restore fit_results to DataFrame.attrs (fix bug - they were saved but not restored)
                fit_results = data_pool.get('fit_results', {})
                if fit_results:
                    for csv_file in self.csv_files:
                        filename = csv_file['filename']
                        if filename in fit_results and 'data' in csv_file:
                            csv_file['data'].attrs['fit_results'] = fit_results[filename]
                            logger.info(f"✅ Restored fit_results for {filename}")
                    logger.debug(f"🔵 Restored fit_results for {len(fit_results)} files")

                # Restore sort state if available
                if 'extracted_column_sort_state' in data_pool:
                    self.file_list.extracted_column_sort_state = data_pool['extracted_column_sort_state']
                    logger.debug(f"🟡 Restored sort state: {self.file_list.extracted_column_sort_state}")

                    # Re-apply last sort if any
                    for col_idx, order in self.file_list.extracted_column_sort_state.items():
                        if order:  # 'asc' or 'desc'
                            qt_order = Qt.AscendingOrder if order == 'asc' else Qt.DescendingOrder
                            # Convert col_idx to int (stored as string in JSON/SQLite)
                            col_idx_int = int(col_idx) if isinstance(col_idx, str) else col_idx
                            self.file_list.sortItems(col_idx_int, qt_order)
                            logger.info(f"✅ Re-applied sort on column {col_idx_int} ({order})")

                if 'checked_files' in data_pool:
                    for row in range(self.file_list.rowCount()):
                        item = self.file_list.item(row, 0)
                        checkbox = self.file_list.item(row, 1)
                        if item and checkbox and item.text() in data_pool['checked_files']:
                            checkbox.setCheckState(Qt.Checked)
                
                if 'plot_settings' in data_pool:
                    settings = data_pool['plot_settings']
                    self._apply_plot_settings(settings)

                # Apply plot style settings if available (deferred if window absent)
                if 'plot_style_settings' in data_pool and data_pool['plot_style_settings']:
                    self._apply_plot_style_settings(data_pool['plot_style_settings'])

                # Apply processing settings if available
                if 'processing_settings' in data_pool and data_pool['processing_settings']:
                    self._apply_processing_settings(data_pool['processing_settings'])
        finally:
            self._suppress_plot_window_open = False

    def _apply_plot_settings(self, settings):
        """Apply loaded plot settings"""
        # Apply X column setting
        if 'x_column' in settings and settings['x_column']:
            index = self.x_combo.findText(settings['x_column'])
            if index >= 0:
                self.x_combo.setCurrentIndex(index)
        
        # Apply Y column (now single selection) - support legacy list
        if 'y_columns' in settings and settings['y_columns']:
            target = settings['y_columns'][0]
            idx = self.y_list.findText(target)
            if idx >= 0:
                self.y_list.setCurrentIndex(idx)
        elif 'y_column' in settings and settings['y_column']:
            idx = self.y_list.findText(settings['y_column'])
            if idx >= 0:
                self.y_list.setCurrentIndex(idx)
        
        # Apply Y2 column (now single selection)
        if 'y2_columns' in settings and settings['y2_columns']:
            target = settings['y2_columns'][0]
            idx = self.y2_list.findText(target)
            if idx >= 0:
                self.y2_list.setCurrentIndex(idx)
                    
    def _apply_plot_style_settings(self, style_settings):
        """Apply loaded plot style settings to the plot window"""
        # Do not auto-open the plot window here; apply immediately if it exists,
        # otherwise defer by storing into pending settings.
        if self.plot_window and hasattr(self.plot_window, 'canvas'):
            self.plot_window.canvas.set_plot_style(style_settings)
            if hasattr(self.plot_window, 'style_window'):
                self.plot_window.style_window._set_initial_values()
        else:
            # Merge into pending settings so they apply when plot window opens next time
            if not self.pending_plot_settings:
                self.pending_plot_settings = {}
            self.pending_plot_settings['plot_style_settings'] = style_settings

    def set_processing_settings(self, settings, source='ui'):
        """Store processing settings and ensure the pipeline reflects them."""
        settings_copy = copy.deepcopy(settings) if settings else None
        self.processing_settings = settings_copy
        self.pending_processing_settings = settings_copy
        self._apply_processing_pipeline(settings_copy)

    def _apply_processing_pipeline(self, settings):
        """Translate a settings dict into registered pipeline processors."""
        pipeline = getattr(self, 'pipeline', None)
        if not isinstance(pipeline, DataPipeline):
            return

        pipeline.create_pipeline('current_pipeline', [])

        if not settings:
            return

        default_order = ['baseline', 'denoise_adv', 'time_avg', 'smooth', 'outliers', 'normalize', 'fitting']
        saved_order = settings.get('order', [])
        ordered_sections = [section for section in saved_order if section in default_order]
        for section in default_order:
            if section not in ordered_sections:
                ordered_sections.append(section)

        steps = []

        for section in ordered_sections:
            if section == 'baseline':
                baseline_cfg = settings.get('baseline', {})
                if not baseline_cfg or not baseline_cfg.get('enabled'):
                    continue
                method_text = baseline_cfg.get('method', '')
                method = (method_text or '').lower()
                params = dict(baseline_cfg.get('params', {}) or {})
                x_column = baseline_cfg.get('x_column') or self.get_column_name(self.x_combo)
                if not x_column:
                    continue
                pipeline.register_processor(
                    'baseline_live',
                    create_baseline_processor(x_column, method, params)
                )
                steps.append('baseline_live')

            elif section == 'denoise_adv':
                denoise_cfg = settings.get('denoise_adv', {})
                if not denoise_cfg or not denoise_cfg.get('enabled'):
                    continue
                method = denoise_cfg.get('method', 'savgol')
                params = dict(denoise_cfg.get('params', {}) or {})
                pipeline.register_processor('denoise_live', create_denoise_processor(method, params))
                steps.append('denoise_live')

            elif section == 'time_avg':
                time_avg_cfg = settings.get('time_avg', {})
                if not time_avg_cfg or not time_avg_cfg.get('enabled'):
                    continue
                time_col = time_avg_cfg.get('time_column')
                if not time_col:
                    continue
                processor_func = create_time_averaging_processor(
                    time_column=time_col,
                    start_time=float(time_avg_cfg.get('start_time', 0.03)),
                    first_interval=float(time_avg_cfg.get('first_interval', 1.03)),
                    regular_interval=float(time_avg_cfg.get('regular_interval', 2.06)),
                    window_size=float(time_avg_cfg.get('window_size', 2.0)),
                    window_offset=float(time_avg_cfg.get('window_offset', 0.75))
                )
                pipeline.register_processor('time_avg_current', processor_func)
                steps.append('time_avg_current')

            elif section == 'smooth':
                smooth_cfg = settings.get('smooth', {})
                if not smooth_cfg or not smooth_cfg.get('enabled'):
                    continue
                window = max(1, int(smooth_cfg.get('window', 5)))
                pipeline.register_processor('smooth_live', create_smooth_processor(window))
                steps.append('smooth_live')

            elif section == 'outliers':
                out_cfg = settings.get('outliers', {})
                if not out_cfg or not out_cfg.get('enabled'):
                    continue
                threshold = float(out_cfg.get('threshold', 3.0))
                pipeline.register_processor('outliers_live', create_outliers_processor(threshold))
                steps.append('outliers_live')

            elif section == 'normalize':
                norm_cfg = settings.get('normalize', {})
                if not norm_cfg or not norm_cfg.get('enabled'):
                    continue
                method = norm_cfg.get('method', 'minmax')
                pipeline.register_processor('normalize_live', create_normalize_processor(method))
                steps.append('normalize_live')

            elif section == 'fitting':
                fit_cfg = settings.get('fitting', {})
                if not fit_cfg or not fit_cfg.get('enabled'):
                    # Even if disabled, respect stored visual toggles
                    if isinstance(fit_cfg, dict):
                        self.show_peak_markers = bool(fit_cfg.get('show_peak_markers', self.show_peak_markers))
                        self.show_peak_numbers = bool(fit_cfg.get('show_peak_numbers', self.show_peak_numbers))
                    continue

                # Update visual toggles from settings before plotting
                self.show_peak_markers = bool(fit_cfg.get('show_peak_markers', self.show_peak_markers))
                self.show_peak_numbers = bool(fit_cfg.get('show_peak_numbers', self.show_peak_numbers))

                method_text = fit_cfg.get('method', 'Gauss')
                method = (method_text or 'gauss').lower()

                params = dict(fit_cfg.get('params', {}) or {})
                x_column = fit_cfg.get('x_column') or self.get_column_name(self.x_combo)
                y_column = fit_cfg.get('y_column')

                if not y_column:
                    selected_y = self.get_selected_y_columns()
                    if selected_y:
                        y_column = selected_y[0]
                    else:
                        selected_y2 = self.get_selected_y2_columns()
                        if selected_y2:
                            y_column = selected_y2[0]

                if not x_column or not y_column:
                    continue

                processor_name = f'fit_{method}_live'
                pipeline.register_processor(
                    processor_name,
                    create_fit_multi_peaks_processor(x_column, y_column, method, **params)
                )
                steps.append(processor_name)

        pipeline.create_pipeline('current_pipeline', steps)

    def _apply_processing_settings(self, processing_settings):
        """Apply loaded processing settings to the data pipeline"""
        settings_copy = copy.deepcopy(processing_settings) if processing_settings else None
        self.set_processing_settings(settings_copy, source='load')

        if self.plot_window and hasattr(self.plot_window, 'processing_window'):
            self.plot_window.processing_window.load_settings(settings_copy)
        else:
            self.pending_processing_settings = settings_copy

    def _on_files_loaded(self, csv_files, was_empty):
        """Handle loaded files with auto-preset logic

        Args:
            csv_files: List of loaded file dicts
            was_empty: True if table was empty before loading
        """
        logger.debug(f"[FILES-LOADED] was_empty={was_empty}, files={len(csv_files)}")

        # Display files first (populates X/Y comboboxes)
        self.display_csv_files(csv_files)

        # Populate time columns for time-window averaging
        if csv_files:
            try:
                first_file_data = csv_files[0]['data']
                numeric_cols = first_file_data.select_dtypes(include=[np.number]).columns.tolist()
                self.pending_time_columns = numeric_cols
                logger.debug(f"🟢 [TIME-COLS] Extracted {len(numeric_cols)} numeric columns: {numeric_cols[:5]}{'...' if len(numeric_cols) > 5 else ''}")

                # If processing_window already exists, populate immediately
                if hasattr(self, 'plot_window') and self.plot_window:
                    if hasattr(self.plot_window, 'processing_window') and self.plot_window.processing_window:
                        logger.debug(f"🔵 [TIME-COLS] Processing window exists, populating immediately")
                        self.plot_window.processing_window.populate_time_columns(numeric_cols)
            except (AttributeError, KeyError, TypeError) as e:
                logger.error(f"❌ [TIME-COLS] Failed to extract numeric columns: {e}")
                self.pending_time_columns = []

        # Then apply preset if table was empty
        if was_empty:
            logger.debug(f"[FILES-LOADED] Table was empty, triggering auto-preset")
            self._auto_load_preset_if_applicable(csv_files)

            # Apply preset to main window comboboxes
            if self.pending_plot_settings:
                self._apply_preset_to_main_window(self.pending_plot_settings)
        else:
            logger.debug(f"[FILES-LOADED] Table not empty, skipping auto-preset")

    def display_csv_files(self, csv_files):
        self.csv_files = csv_files
        # Clear only rows (not headers) to prevent blank rows
        self.file_list.setRowCount(0)
        
        default_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                         '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        line_styles = ['-', '--', '-.', ':']
        
        for i, csv_file in enumerate(csv_files):
            filename = csv_file['filename']
            
            if filename not in self.line_colors:
                self.line_colors[filename] = default_colors[i % len(default_colors)]
            
            # Initialize Y2 color if not already set
            if filename not in self.line_colors_y2:
                # Use different color for Y2, offset by half the palette
                offset = len(default_colors) // 2
                self.line_colors_y2[filename] = default_colors[(i + offset) % len(default_colors)]
            
            # Force solid line style regardless of what's in self.line_styles
            self.line_styles[filename] = '-'  # Force solid line
            
            # Use previously set legend if available; otherwise let UI default to filename without extension
            legend_label = self.legend_labels.get(filename)
            
            self.file_list.add_file_row(
                filename,
                self.line_colors[filename],
                '-',  # Force solid line here too
                line_styles,
                legend_label,
                None,  # linked_id
                self.line_colors_y2[filename]  # y2_color
            )

        # Handle column sizing differently for empty vs non-empty table
        if csv_files:
            # With data: resize to contents then cap widths
            self.file_list.resizeColumnsToContents()

            # Cap column widths to prevent window from becoming too wide
            max_widths = {
                0: 200,  # File column
                1: 60,   # Select checkbox
                2: 60,   # Y1 color
                3: 60,   # Y2 color
                4: 100,  # Line Style
                5: 250,  # Legend Label (can be longer)
                6: 120,  # Link button
            }
            for col, max_width in max_widths.items():
                if self.file_list.columnWidth(col) > max_width:
                    self.file_list.setColumnWidth(col, max_width)
        else:
            # Without data: set explicit widths instead of resizeColumnsToContents
            # This prevents erratic sizing on empty table
            for col, width in [(0, 200), (1, 60), (2, 60), (3, 60), (4, 100), (5, 250), (6, 120)]:
                self.file_list.setColumnWidth(col, width)

        if csv_files:
            self.update_status(f"{len(csv_files)} data files loaded")
            self.update_columns_list()
        else:
            self.update_status("No data files found")

    def remove_selected_from_pool(self):
        """Remove selected files from the in-memory data pool and refresh UI."""
        # Prefer explicit selection from the table
        selected_filenames = []
        if hasattr(self.file_list, 'get_selected_filenames'):
            selected_filenames = self.file_list.get_selected_filenames()

        if not selected_filenames:
            QMessageBox.information(self, "Remove", "Select one or more rows to remove")
            return

        # Filter out selected files from csv_files
        remaining = []
        removed = []
        selected_set = set(selected_filenames)
        for f in self.csv_files:
            if f.get('filename') in selected_set:
                removed.append(f.get('filename'))
            else:
                remaining.append(f)

        if not removed:
            return

        # Update internal state
        self.csv_files = remaining
        for name in removed:
            self.line_colors.pop(name, None)
            self.line_colors_y2.pop(name, None)
            self.line_styles.pop(name, None)
            self.legend_labels.pop(name, None)
            # Clear parquet link data tracked in the table widget
            if hasattr(self.file_list, 'parquet_columns'):
                self.file_list.parquet_columns.pop(name, None)

        # Refresh UI
        self.display_csv_files(self.csv_files)
        self.update_status(f"Removed {len(removed)} file(s): {', '.join(removed)}")

    def update_columns_list(self):
        if not self.csv_files:
            return
        
        selected_file = self.csv_files[0]
        
        if selected_file and 'headers' in selected_file:
            current_x = self.x_combo.currentText()
            current_y_text = self.y_list.currentText() if self.y_list.currentIndex() >= 0 else ''

            self.x_combo.clear()
            self.y_list.clear()
            self.y2_list.clear()

            # Add empty option to allow 'unused' axis
            self.x_combo.addItem("", None)
            self.y_list.addItem("", None)
            self.y2_list.addItem("", None)

            headers = selected_file['headers']
            units = selected_file['units']

            # First, try to get numeric columns from data
            numeric_columns = []
            if hasattr(selected_file['data'], 'select_dtypes'):
                numeric_columns = selected_file['data'].select_dtypes(include=[np.number]).columns.tolist()
            if not numeric_columns:
                numeric_columns = headers

            for col in numeric_columns:
                unit = units.get(col, "")
                display_name = f"{col} ({unit})" if unit else col
                # Store raw column as userData
                self.x_combo.addItem(display_name, col)
                self.y_list.addItem(display_name, col)
                self.y2_list.addItem(display_name, col)

            self._set_default_columns(current_x, [current_y_text] if current_y_text else [])

    def _set_default_columns(self, current_x, current_y_list):
        # Set X column default (skip empty item at index 0)
        x_index = self.x_combo.findText(current_x)
        if x_index >= 1:
            self.x_combo.setCurrentIndex(x_index)
        else:
            # Prefer a column containing 'Time' if present
            time_index = next((i for i in range(1, self.x_combo.count())
                               if 'Time' in self.x_combo.itemText(i)), -1)
            if time_index >= 1:
                self.x_combo.setCurrentIndex(time_index)

        # Set Y column default (single selection)
        if self.y_list.count() > 1:
            chosen_index = -1
            if current_y_list:
                target = current_y_list[0]
                idx = self.y_list.findText(target)
                chosen_index = idx if idx >= 1 else -1
            if chosen_index < 0:
                # Try to prefer 'COF'
                for i in range(1, self.y_list.count()):
                    if 'COF' in self.y_list.itemText(i):
                        chosen_index = i
                        break
            if chosen_index < 0:
                # Choose first different from X if possible
                x_raw = self.get_column_name(self.x_combo)
                for i in range(1, self.y_list.count()):
                    if self.y_list.itemData(i) != x_raw:
                        chosen_index = i
                        break
            if chosen_index < 0:
                # Leave empty (index 0) to mean 'unused'
                chosen_index = 0
            self.y_list.setCurrentIndex(chosen_index)

    def check_file_clicked(self, row, column):
        if column == 1:
            item = self.file_list.item(row, column)
            if item:
                new_state = Qt.Checked if item.checkState() == Qt.Unchecked else Qt.Unchecked
                item.setCheckState(new_state)

    def update_style_parameter(self, param_type, filename, value):
        """Generic handler for updating style parameters"""
        if param_type == 'color':
            self.line_colors[filename] = value
        elif param_type == 'y2_color':
            self.line_colors_y2[filename] = value
        elif param_type == 'style':
            self.line_styles[filename] = value
        elif param_type == 'legend':
            self.legend_labels[filename] = value

    def get_column_name(self, combo_box):
        index = combo_box.currentIndex()
        if index >= 0:
            col_name = combo_box.itemData(index)
            logger.debug(f"[DEBUG] get_column_name: index={index}, itemData='{col_name}'")
            return col_name
        logger.debug(f"[DEBUG] get_column_name: no selection (index={index})")
        return None
    
    def get_selected_y_columns(self):
        """Get list of selected Y column names (single selection)"""
        idx = self.y_list.currentIndex()
        val = self.y_list.itemData(idx) if idx >= 0 else None
        return [val] if val else []
    
    def get_selected_y2_columns(self):
        """Get list of selected Y2 column names (single selection)"""
        idx = self.y2_list.currentIndex()
        val = self.y2_list.itemData(idx) if idx >= 0 else None
        return [val] if val else []

    def plot_selected(self):
        """Plot selected files"""
        checked_files = self.file_list.get_checked_items()
        if not checked_files:
            QMessageBox.warning(self, "Warning", "Please select at least one CSV file to plot")
            return
        
        if self.x_combo.count() == 0 or (self.y_list.count() == 0 and self.y2_list.count() == 0):
            QMessageBox.warning(self, "Warning", "Please select X and Y columns to plot")
            return
        
        x_col = self.get_column_name(self.x_combo)
        y_cols = self.get_selected_y_columns()
        y2_cols = self.get_selected_y2_columns()

        logger.debug(f"[DEBUG] plot_selected: x_col='{x_col}', y_cols={y_cols}, y2_cols={y2_cols}")

        if not x_col or (not y_cols and not y2_cols):
            QMessageBox.warning(self, "Error", "Unable to get column names. Please select X and Y columns.")
            return

        self.show_plot_window()
        self.plot_data(checked_files, x_col, y_cols, y2_cols)

    def get_processed_data(self, filename):
        """Get processed data for a file (what would be plotted)

        Returns DataFrame after applying pipeline if configured.
        Used by data extraction to compute metrics on processed data.

        Args:
            filename: Name of file to get data for

        Returns:
            pd.DataFrame or None: Processed DataFrame, or None if file not found
        """
        # Find file data
        file_data = next((f for f in self.csv_files if f['filename'] == filename), None)
        if not file_data:
            return None

        df = file_data['data']

        # Apply processing pipeline if configured (same logic as plot_data)
        try:
            has_pipeline = hasattr(self, 'pipeline')
            is_datapipeline = isinstance(getattr(self, 'pipeline', None), DataPipeline)
            has_current = 'current_pipeline' in self.pipeline.pipelines if has_pipeline else False
            pipeline_steps = self.pipeline.pipelines.get('current_pipeline') if has_current else None

            if has_pipeline and is_datapipeline and has_current and pipeline_steps:
                logger.debug(f"🟡 Applying pipeline to {filename} for extraction")
                df = self.pipeline.process_data(
                    df.copy(),  # Don't modify original
                    pipeline_id='current_pipeline',
                    source_id=filename
                )
                logger.info(f"✅ Pipeline applied successfully")
        except Exception as e:
            logger.error(f"🔴 Pipeline processing failed in get_processed_data: {e}")
            # Fall back to raw data
            df = file_data['data']

        return df

    def plot_data(self, checked_files, x_col, y_cols, y2_cols=None):
        """Plot data for selected files with Y1 and Y2 columns"""
        if self.plot_window is None:
            self.show_plot_window()

        # Pass visual settings to plot window
        if hasattr(self.plot_window, 'show_peak_markers'):
            self.plot_window.show_peak_markers = self.show_peak_markers
            self.plot_window.show_peak_numbers = self.show_peak_numbers

        self.plot_window.canvas.clear_plot()
        plot_success = False

        # Combine all columns to check
        all_y_cols = (y_cols or []) + (y2_cols or [])

        for filename in checked_files:
            file_data = next((f for f in self.csv_files if f['filename'] == filename), None)
            if not file_data:
                continue

            # Apply processing pipeline to data if configured
            df_to_plot = file_data['data']
            logger.debug(f"[DEBUG] plot_data: file='{filename}', columns={list(df_to_plot.columns)[:10]}...")
            try:
                has_pipeline = hasattr(self, 'pipeline')
                is_datapipeline = isinstance(getattr(self, 'pipeline', None), DataPipeline)
                has_current = 'current_pipeline' in self.pipeline.pipelines if has_pipeline else False
                pipeline_steps = self.pipeline.pipelines.get('current_pipeline') if has_current else None

                logger.debug(f"⚫ main_app.py Pipeline check:")
                logger.debug(f"⚫   has_pipeline={has_pipeline}")
                logger.debug(f"⚫   is_datapipeline={is_datapipeline}")
                logger.debug(f"⚫   has_current={has_current}")
                logger.debug(f"⚫   pipeline_steps={pipeline_steps}")
                logger.debug(f"⚫   self.pipeline.pipelines keys={list(self.pipeline.pipelines.keys()) if has_pipeline else 'N/A'}")
                logger.debug(f"[DEBUG] Pipeline check: has_pipeline={has_pipeline}, is_datapipeline={is_datapipeline}, has_current={has_current}, steps={pipeline_steps}")

                if has_pipeline and is_datapipeline and has_current and pipeline_steps:
                    logger.debug(f"[DEBUG] Applying pipeline with steps: {pipeline_steps}")
                    df_to_plot = self.pipeline.process_data(
                        df_to_plot,
                        pipeline_id='current_pipeline',
                        source_id=filename
                    )
                    logger.debug(f"[DEBUG] Pipeline applied successfully, new shape: {df_to_plot.shape}")
                    # Store fit results if present (for the last file, which is typically what's displayed)
                    if hasattr(df_to_plot, 'attrs') and 'fit_results' in df_to_plot.attrs:
                        self.last_fit_results = df_to_plot.attrs['fit_results']
                        # Also store back to csv_files for persistence
                        file_data['data'].attrs['fit_results'] = df_to_plot.attrs['fit_results']
            except Exception as e:
                # If processing fails, fall back to raw data
                logger.error(f"[ERROR] Pipeline processing failed: {e}")
                import traceback
                traceback.print_exc()
                df_to_plot = file_data['data']

            # Check if x_col and all y_cols exist in file
            missing_cols = [col for col in [x_col] + all_y_cols if col not in df_to_plot.columns]
            logger.debug(f"[DEBUG] plot_data: checking cols: x='{x_col}', y={all_y_cols}, missing={missing_cols}")
            if missing_cols:
                logger.error(f"[ERROR] Missing columns {missing_cols} in file '{filename}'")
                QMessageBox.warning(self, "Error", f"Columns {missing_cols} not found in file '{filename}'")
                continue

            try:
                line_style = self.line_styles.get(filename, '-')
                line_color = self.line_colors.get(filename, None)
                base_legend_label = self.file_list.get_legend_text(filename)

                # Plot Y1 columns (left axis)
                if y_cols:
                    for i, y_col in enumerate(y_cols):
                        legend_label = f"{base_legend_label} - {y_col}" if len(all_y_cols) > 1 else base_legend_label

                        # DEBUG: Print what we're actually plotting
                        logger.debug(f"\n=== PLOT DEBUG ===")
                        logger.debug(f"User selected - X: '{x_col}', Y: '{y_col}'")
                        logger.debug(f"File: {filename}")
                        logger.debug(f"DataFrame shape: {df_to_plot.shape}")
                        logger.debug(f"Data types: X={df_to_plot[x_col].dtype}, Y={df_to_plot[y_col].dtype}")
                        logger.debug(f"X first 5: {df_to_plot[x_col].head().tolist()}")
                        logger.debug(f"Y first 5: {df_to_plot[y_col].head().tolist()}")
                        logger.debug(f"X range: [{df_to_plot[x_col].min()}, {df_to_plot[x_col].max()}]")
                        logger.debug(f"Y range: [{df_to_plot[y_col].min()}, {df_to_plot[y_col].max()}]")

                        self.plot_window.canvas.plot_data(
                            df_to_plot,
                            x_col,
                            y_col,
                            label=legend_label,
                            clear_first=not plot_success,
                            line_style=line_style,
                            color=line_color if i == 0 else None,
                            use_right_axis=False,
                            defer_draw=True
                        )
                        plot_success = True

                # Plot Y2 columns (right axis)  
                if y2_cols:
                    line_color_y2 = self.line_colors_y2.get(filename, None)
                    for i, y_col in enumerate(y2_cols):
                        legend_label = f"{base_legend_label} - {y_col} (R)" if len(all_y_cols) > 1 else f"{base_legend_label} (R)"

                        # Use Y2 color for first Y2 series, auto for others
                        color_to_use = line_color_y2 if i == 0 else None

                        self.plot_window.canvas.plot_data(
                            df_to_plot,
                            x_col,
                            y_col,
                            label=legend_label,
                            clear_first=not plot_success,
                            line_style=line_style,
                            color=color_to_use,
                            use_right_axis=True,
                            defer_draw=True
                        )
                plot_success = True
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error plotting file '{filename}': {str(e)}")
                
        # Update plot window controls to match current canvas settings
        if plot_success and hasattr(self.plot_window, 'style_window'):
            self.plot_window.style_window._set_initial_values()
        # Perform a single draw at the end to keep UI responsive
        if self.plot_window and hasattr(self.plot_window, 'canvas'):
            self.plot_window.canvas.draw()

    def show_plot_window(self):
        """Create and show plot window"""
        if getattr(self, '_suppress_plot_window_open', False):
            # Defer opening; pending settings will be applied later
            return
        if self.plot_window is None:
            # Create as independent top-level window for better Windows snap by drag
            self.plot_window = PlotWindow(None, app=self)

            # Transfer pending time columns to processing_window
            if self.pending_time_columns and hasattr(self.plot_window, 'processing_window'):
                logger.debug(f"🔵 [TIME-COLS] Transferring {len(self.pending_time_columns)} pending columns to processing_window")
                self.plot_window.processing_window.populate_time_columns(self.pending_time_columns)
            else:
                if not self.pending_time_columns:
                    logger.debug(f"⚠️ [TIME-COLS] No pending columns to transfer (list empty)")
                else:
                    logger.debug(f"⚠️ [TIME-COLS] Processing window not ready for transfer")

            # Apply pending settings if available
            if hasattr(self, 'pending_plot_settings') and self.pending_plot_settings:
                self.apply_plot_settings_to_window(self.pending_plot_settings)
            if self.pending_processing_settings and hasattr(self.plot_window, 'processing_window'):
                try:
                    self.plot_window.processing_window.load_settings(self.pending_processing_settings)
                except Exception:
                    pass
        # Open plot window in normal size for better Windows tiling
        self.plot_window.show()

    def clear_plot(self):
        """Clear the plot window"""
        if self.plot_window:
            self.plot_window.canvas.clear_plot()

    def clear_cache(self):
        """Clear the data cache"""
        if self.cache:
            self.cache.clear_cache()
            QMessageBox.information(self, "Cache Cleared", "Data cache has been cleared")
    
    def handle_link_clicked(self, filename):
        """Handle clicks on the link button to connect a specific CSV file to parquet samples"""
        if not self.csv_files:
            QMessageBox.warning(self, "Warning", "No CSV files loaded")
            return
            
        # First check if we already have tables defined
        if not hasattr(self.parquet_linker, 'tables') or not self.parquet_linker.tables:
            # No tables loaded yet, ask user to set up tables
            if not self.parquet_linker.select_parquet_files():
                return  # User cancelled or error occurred
        
        # Find the file in csv_files
        file_info = next((f for f in self.csv_files if f['filename'] == filename), None)
        if not file_info:
            QMessageBox.warning(self, "Error", f"Could not find file {filename}")
            return
            
        # Use the multi-table link dialog for a single file
        dialog = MultiTableLinkDialog(self, [file_info], self.parquet_linker)
        if dialog.exec_():
            links = dialog.get_links()
            if filename in links:
                sample_data = links[filename]
                sample_id = sample_data.get('sample_id', '')
                self.file_list.update_link_status(filename, sample_id, sample_data)
                QMessageBox.information(self, "Success", f"Linked {filename} to sample {sample_id}")

    def open_extraction_dialog(self):
        """Open dialog to extract metrics from data"""
        from data_extraction import DataExtractionDialog

        checked_files = self.file_list.get_checked_items()
        if not checked_files:
            QMessageBox.warning(self, "Warning", "No files selected. Please check files to extract data from.")
            return

        logger.debug("🟢 Opening Extract Data dialog")
        dialog = DataExtractionDialog(self)
        dialog.exec_()

    def link_to_database(self):
        """Link all CSV files to a parquet sample database with multiple tables"""
        if not self.csv_files:
            QMessageBox.warning(self, "Warning", "No CSV files loaded")
            return
            
        # Check if we already have tables defined
        if not hasattr(self.parquet_linker, 'tables') or not self.parquet_linker.tables:
            # No tables loaded yet, ask user to set up tables
            if not self.parquet_linker.select_parquet_files():
                return  # User cancelled or error occurred
                
        # Show the link dialog
        links = self.parquet_linker.show_link_dialog(self.csv_files)
        
        # Update UI for linked files
        if links:
            for filename, sample_data in links.items():
                # Get the sample_id from the linked data
                sample_id = sample_data.get('sample_id', '')
                self.file_list.update_link_status(filename, sample_id, sample_data)
            
            QMessageBox.information(self, "Success", f"Linked {len(links)} files to sample database")
            
    # open_pipeline_dialog removed with Data Processing tab

    def rename_legend_batch(self):
        """Open dialog to batch-rename legends for checked files based on filename parts."""
        dlg = BatchLegendRenameDialog(self, self)
        dlg.exec_()

    def on_data_processed(self, data, source_id):
        """Handle processed data from the pipeline"""
        # This method receives data that has been processed through the pipeline
        self.status_label.setText(f"Processed data from {source_id}: {data.shape[0]} rows")

    def load_plot_settings_main(self):
        """Load plot settings from file and apply to current or future plot window"""
        settings_data = StorageManager.load_plot_settings(self)
        if not settings_data:
            return

        # Store settings for future use
        self.pending_plot_settings = settings_data

        # Apply immediately if plot window exists
        if self.plot_window and hasattr(self.plot_window, 'canvas'):
            self.apply_plot_settings_to_window(settings_data)
            QMessageBox.information(self, "Success", "Plot settings loaded and applied to current plot")
        else:
            QMessageBox.information(self, "Success", "Plot settings loaded. They will be applied when you create a plot.")

    def apply_plot_settings_to_window(self, settings_data):
        """Apply loaded settings to the plot window"""
        if not self.plot_window or not hasattr(self.plot_window, 'canvas'):
            return

        # Apply plot style settings
        if 'plot_style_settings' in settings_data:
            self.plot_window.canvas.set_plot_style(settings_data['plot_style_settings'])
            # IMPORTANT: Update UI to reflect loaded settings
            if hasattr(self.plot_window, 'style_window'):
                self.plot_window.style_window._set_initial_values()
            # Clear pending settings after successful application
            if hasattr(self, 'pending_plot_settings'):
                self.pending_plot_settings = None

        # Apply other plot settings if available
        if 'plot_settings' in settings_data:
            # Could include axis limits, column selections, etc.
            plot_settings = settings_data['plot_settings']
            # Add specific setting applications here if needed

    def _check_updates_on_startup(self):
        """Check for updates and show notification if available.

        Silently skips if:
        - Update checking is disabled (CSVPLOTTER_UPDATE_PATH=0)
        - Network is unavailable
        - No update available
        """
        update_info = check_for_updates()
        if update_info:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Mise à jour disponible")
            msg.setText(f"Version du {format_version_display(update_info['version'])} disponible")
            msg.setInformativeText(
                f"Version actuelle: {format_version_display(__version__)}\n\n"
                f"Téléchargez la nouvelle version depuis:\n{update_info['path']}\n\n"
                f"Copiez le fichier pour remplacer l'exécutable actuel."
            )
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CSVPlotterApp()
    window.show()
    sys.exit(app.exec_())
