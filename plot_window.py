import os
import json
import re
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QPushButton, QHBoxLayout,
                           QMessageBox, QMenu, QFileDialog, QShortcut, QScrollArea, QSizePolicy)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt
from plot_canvas import PlotCanvas
from plot_style_window import PlotStyleWindow
from plot_processing_window import ProcessingWindow
from plot_dialog_components import CustomNavigationToolbar
from storage_manager import StorageManager
from plot_styles import apply_plot_styles
from plot_interactive_edit import setup_interactive_editing
from app_logging import logger

class PlotWindow(QMainWindow):
    """Main window for displaying the plot
    If created with a Qt parent, Windows may treat it as an owned window,
    which can limit drag-based tiling. Pass app=main_window and parent=None
    to make it an independent top-level window while keeping app access.
    """
    def __init__(self, parent=None, app=None):
        super().__init__(parent)
        # Hold an explicit reference to the main application window
        self.app = app if app is not None else parent
        self.setWindowTitle("Plot")
        self.setGeometry(200, 200, 800, 600)
        # Make it a normal top-level window with system menu and min/max buttons
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowTitleHint |
            Qt.WindowSystemMenuHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.init_ui()
        
    def init_ui(self):
        # Central widget + layout, required for QMainWindow
        # Apply local stylesheet for role-based button styling in plot window
        self.setStyleSheet(self._build_stylesheet())

        def create_button(label, handler=None, role="primary", checkable=False):
            btn = QPushButton(label)
            btn.setProperty("role", role)
            btn.setCheckable(checkable)
            if handler is not None:
                btn.clicked.connect(handler)
            return btn

        central = QWidget(self)
        self.central_layout = QVBoxLayout(central)
        self.setCentralWidget(central)
        
        # Plot area
        self.canvas = PlotCanvas(self, width=5, height=4)
        # Use custom toolbar instead of default
        self.toolbar = CustomNavigationToolbar(self.canvas, self)
        self.central_layout.addWidget(self.toolbar)

        # Make the plot scrollable while keeping buttons visible
        self.plot_scroll = QScrollArea(self)
        self.plot_scroll.setWidget(self.canvas)
        # Let canvas dictate its own size when locked; otherwise fit to viewport
        self.plot_scroll.setWidgetResizable(False)
        self.plot_scroll.setAlignment(Qt.AlignCenter)
        self.plot_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.central_layout.addWidget(self.plot_scroll)
        
        # Settings buttons
        settings_layout = QHBoxLayout()
        
        style_button = create_button("Plot Style Options", self.show_quick_bar, role="primary")
        settings_layout.addWidget(style_button)

        processing_button = create_button("Processing", self.show_quick_processing, role="primary")
        settings_layout.addWidget(processing_button)
        
        save_settings_button = create_button("Save Settings", self.save_current_settings, role="save")
        settings_layout.addWidget(save_settings_button)
        
        load_settings_button = create_button("Load Settings", self.load_plot_settings, role="primary")
        settings_layout.addWidget(load_settings_button)

        # Batch save button with menu options
        batch_button = create_button("Sauvegarde batch 💾💾", self.show_batch_menu, role="save")
        settings_layout.addWidget(batch_button)

        # Tools menu (e.g., Clear Cache)
        tools_button = create_button("Outils ⚙️", self.show_tools_menu, role="primary")
        settings_layout.addWidget(tools_button)

        # Fullscreen toggle
        self.fullscreen_button = create_button("Plein écran ⛶", self.toggle_fullscreen, role="primary", checkable=True)
        settings_layout.addWidget(self.fullscreen_button)

        # Lock display size toggle (keep canvas at plot size)
        self.lock_size_button = create_button("Verrouiller taille", role="primary", checkable=True)
        self.lock_size_button.setToolTip("Garder le graphe à la taille définie (pixels)")
        self.lock_size_button.clicked.connect(self.toggle_lock_size)
        settings_layout.addWidget(self.lock_size_button)
        
        # Wrap settings into a container so we can control stretch
        self.buttons_container = QWidget(self)
        self.buttons_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.buttons_container.setLayout(settings_layout)
        self.central_layout.addWidget(self.buttons_container)
        
        # Close button
        close_button = create_button("Close", self.close, role="primary")
        self.central_layout.addWidget(close_button)

        # Layout stretch: make scroll area take all extra space
        # Indexes: 0 toolbar, 1 scroll, 2 buttons_container, 3 close_button
        self.central_layout.setStretch(0, 0)
        self.central_layout.setStretch(1, 1)
        self.central_layout.setStretch(2, 0)
        self.central_layout.setStretch(3, 0)
        
        # Create style window but don't show it yet
        self.style_window = PlotStyleWindow(self)
        # Create processing window but don't show it yet
        self.processing_window = ProcessingWindow(self)

        # If main app has pending time columns, populate now (safety fallback)
        if hasattr(self, 'app') and self.app and hasattr(self.app, 'pending_time_columns'):
            if self.app.pending_time_columns:
                self.processing_window.populate_time_columns(self.app.pending_time_columns)

        # Load default style settings
        self._load_default_style()

        # Keyboard shortcut for fullscreen (F11)
        fs_shortcut = QShortcut(QKeySequence("F11"), self)
        fs_shortcut.activated.connect(self.toggle_fullscreen)

        # Keyboard shortcut for radial menu (R)
        radial_shortcut = QShortcut(QKeySequence("R"), self)
        radial_shortcut.activated.connect(self.show_radial_menu)

        # Keyboard shortcut for quick bar (Q)
        quickbar_shortcut = QShortcut(QKeySequence("Q"), self)
        quickbar_shortcut.activated.connect(self.show_quick_bar)

        # Enable display size lock by default
        try:
            self.lock_size_button.setChecked(True)
            self.toggle_lock_size(True)
        except Exception:
            pass

        # Setup interactive editing (click on elements to edit)
        setup_interactive_editing(self.canvas, self)

    def _build_stylesheet(self):
        """Stylesheet for plot window: white buttons by default, save buttons in blue."""
        return """
        QPushButton {
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: 500;
        }

        /* Primary (white) */
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

        /* Save (blue) */
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
        """

    def show_batch_menu(self):
        """Show menu to choose batch export mode"""
        menu = QMenu(self)
        per_data_action = menu.addAction("Une donnée par plot")
        per_series_action = menu.addAction("Une série par plot")
        menu.addSeparator()
        per_date_action = menu.addAction("Par date (un plot/date)")
        per_project_action = menu.addAction("Par projet (un plot/projet)")

        # Position menu near the triggering button
        sender = self.sender()
        pos = sender.mapToGlobal(sender.rect().bottomLeft()) if sender else self.mapToGlobal(self.rect().center())
        action = menu.exec_(pos)
        if action == per_data_action:
            self.batch_export_per_data()
        elif action == per_series_action:
            self.batch_export_per_series()
        elif action == per_date_action:
            self.batch_export_per_date()
        elif action == per_project_action:
            self.batch_export_per_project()

    def show_tools_menu(self):
        """Show a small tools menu with maintenance actions."""
        menu = QMenu(self)
        clear_cache_action = menu.addAction("Vider le cache des données")

        sender = self.sender()
        pos = sender.mapToGlobal(sender.rect().bottomLeft()) if sender else self.mapToGlobal(self.rect().center())
        action = menu.exec_(pos)
        if action == clear_cache_action:
            if self.app and hasattr(self.app, 'clear_cache'):
                self.app.clear_cache()

    def _choose_output_directory(self):
        """Ask user to choose an output directory for batch images"""
        directory = QFileDialog.getExistingDirectory(self, "Choisir le dossier de sortie")
        return directory if directory else None

    def _set_checked_files(self, filenames):
        """Set the table check state so only given filenames are checked"""
        parent = self.app
        if not parent or not hasattr(parent, 'file_list'):
            return
        table = parent.file_list
        for row in range(table.rowCount()):
            item_name = table.item(row, 0)
            item_chk = table.item(row, 1)
            if item_name and item_chk and not hasattr(item_name, 'is_search_row'):
                fn = item_name.text()
                item_chk.setCheckState(Qt.Checked if fn in filenames else Qt.Unchecked)

    def _get_originally_checked(self):
        parent = self.app
        if not parent or not hasattr(parent, 'file_list'):
            return []
        return parent.file_list.get_checked_items()

    def _save_current_figure(self, out_dir, filename_base, fmt='png', dpi=300):
        """Save current figure to file in out_dir with given base name"""
        try:
            # Sanitize for Windows: replace forbidden characters and trim trailing dots/spaces
            safe_base = re.sub(r'[<>:"/\\\\|?*]', '_', filename_base)
            safe_base = safe_base.strip().strip('.')
            if not safe_base:
                safe_base = "plot"
            out_path = os.path.join(out_dir, f"{safe_base}.{fmt}")
            # Save with exact requested size; avoid bbox_inches='tight'
            # which changes final image dimensions unpredictably
            self.canvas.fig.savefig(out_path, dpi=dpi)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de sauvegarde: {str(e)}")
            return False

    def batch_export_per_data(self):
        """Export one plot per checked data (file)"""
        parent = self.app
        if not parent or not hasattr(parent, 'file_list'):
            QMessageBox.warning(self, "Avertissement", "Contexte parent introuvable")
            return
        checked_files = parent.file_list.get_checked_items()
        if not checked_files:
            QMessageBox.warning(self, "Avertissement", "Veuillez sélectionner au moins un fichier")
            return
        out_dir = self._choose_output_directory()
        if not out_dir:
            return
        original_checked = self._get_originally_checked()
        try:
            for filename in checked_files:
                # check only this file
                self._set_checked_files([filename])
                # plot using existing logic
                parent.plot_selected()
                # save figure with base name (no extension)
                base = os.path.splitext(filename)[0]
                if not self._save_current_figure(out_dir, base):
                    return
            QMessageBox.information(self, "Succès", f"Export batch terminé dans: {out_dir}")
        finally:
            # restore original selection
            self._set_checked_files(original_checked)

    def batch_export_per_series(self):
        """Export one plot per detected series containing checked files"""
        parent = self.app
        if not parent or not hasattr(parent, 'file_list'):
            QMessageBox.warning(self, "Avertissement", "Contexte parent introuvable")
            return
        table = parent.file_list
        checked = set(table.get_checked_items())
        if not checked:
            QMessageBox.warning(self, "Avertissement", "Veuillez sélectionner au moins un fichier")
            return
        # Detect all series and filter to those with any checked file
        try:
            series_groups = table.detect_series_from_filenames()
        except Exception:
            series_groups = {}
        if not series_groups:
            QMessageBox.warning(self, "Avertissement", "Aucune série détectée")
            return
        # Map series -> filenames that are checked
        series_checked = {}
        for series_key, rows in series_groups.items():
            fns = [fn for (_row, fn) in rows if fn in checked]
            if fns:
                series_checked[series_key] = fns
        if not series_checked:
            QMessageBox.warning(self, "Avertissement", "Aucune série ne contient des fichiers sélectionnés")
            return
        out_dir = self._choose_output_directory()
        if not out_dir:
            return
        original_checked = self._get_originally_checked()
        try:
            for series_key in sorted(series_checked.keys()):
                filenames = series_checked[series_key]
                # check only files of this series
                self._set_checked_files(filenames)
                parent.plot_selected()
                base = f"serie_{series_key}"
                if not self._save_current_figure(out_dir, base):
                    return
            QMessageBox.information(self, "Succès", f"Export batch terminé dans: {out_dir}")
        finally:
            self._set_checked_files(original_checked)

    def _parse_name_date(self, filename):
        """Parse filename into (name, date, series, file_no) using common pattern.
        Returns tuple or None if no match.
        """
        pattern = re.compile(r'^(.+?)_(\d{6})_(\d+)_(\d+)(?:\.[^.]+)?$')
        m = pattern.match(filename)
        if not m:
            return None
        name, date, series_no, file_no = m.groups()
        return name, date, series_no, file_no

    def batch_export_per_date(self):
        """Export one plot per date among checked files"""
        parent = self.app
        if not parent or not hasattr(parent, 'file_list'):
            QMessageBox.warning(self, "Avertissement", "Contexte parent introuvable")
            return
        table = parent.file_list
        checked = set(table.get_checked_items())
        if not checked:
            QMessageBox.warning(self, "Avertissement", "Veuillez sélectionner au moins un fichier")
            return
        groups = {}
        for fn in checked:
            parsed = self._parse_name_date(fn)
            if not parsed:
                continue
            _, date, _, _ = parsed
            groups.setdefault(date, []).append(fn)
        if not groups:
            QMessageBox.warning(self, "Avertissement", "Aucune date détectée parmi les fichiers sélectionnés")
            return
        out_dir = self._choose_output_directory()
        if not out_dir:
            return
        original_checked = self._get_originally_checked()
        try:
            for date in sorted(groups.keys()):
                filenames = groups[date]
                self._set_checked_files(filenames)
                parent.plot_selected()
                base = f"date_{date}"
                if not self._save_current_figure(out_dir, base):
                    return
            QMessageBox.information(self, "Succès", f"Export batch par date terminé dans: {out_dir}")
        finally:
            self._set_checked_files(original_checked)

    def batch_export_per_project(self):
        """Export one plot per project (prefix) among checked files"""
        parent = self.app
        if not parent or not hasattr(parent, 'file_list'):
            QMessageBox.warning(self, "Avertissement", "Contexte parent introuvable")
            return
        table = parent.file_list
        checked = set(table.get_checked_items())
        if not checked:
            QMessageBox.warning(self, "Avertissement", "Veuillez sélectionner au moins un fichier")
            return
        groups = {}
        for fn in checked:
            parsed = self._parse_name_date(fn)
            if not parsed:
                # fall back to stem before first underscore
                name = os.path.splitext(fn)[0].split('_')[0]
            else:
                name = parsed[0]
            groups.setdefault(name, []).append(fn)
        if not groups:
            QMessageBox.warning(self, "Avertissement", "Aucun projet détecté parmi les fichiers sélectionnés")
            return
        out_dir = self._choose_output_directory()
        if not out_dir:
            return
        original_checked = self._get_originally_checked()
        try:
            for name in sorted(groups.keys()):
                filenames = groups[name]
                self._set_checked_files(filenames)
                parent.plot_selected()
                base = f"projet_{name}"
                if not self._save_current_figure(out_dir, base):
                    return
            QMessageBox.information(self, "Succès", f"Export batch par projet terminé dans: {out_dir}")
        finally:
            self._set_checked_files(original_checked)
    
    def save_current_settings(self):
        """Save current plot settings to a file"""
        if not hasattr(self, 'canvas') or not hasattr(self.canvas, 'plot_style'):
            QMessageBox.warning(self, "Warning", "No plot settings available")
            return
            
        plot_style_settings = self.canvas.plot_style.copy()
        
        # Get basic plot settings from parent window if available
        plot_settings = None
        if self.app:
            try:
                # Use currentText from the new single-selection comboboxes
                y_text = self.app.y_list.currentText() if self.app.y_list.currentIndex() >= 0 else ''
                y2_text = self.app.y2_list.currentText() if self.app.y2_list.currentIndex() >= 0 else ''

                plot_settings = {
                    'x_column': self.app.x_combo.currentText(),
                    'y_columns': [y_text] if y_text else [],
                    'y2_columns': [y2_text] if y2_text else []
                }
            except AttributeError:
                pass
        
        StorageManager.save_plot_settings(self, plot_style_settings, plot_settings)

    def load_plot_settings(self):
        """Load plot settings from a file"""
        logger.debug("Starting load_plot_settings")
        settings_data = StorageManager.load_plot_settings(self)
        if not settings_data:
            logger.debug("No settings data returned")
            return

        # Apply plot style settings
        if 'plot_style_settings' in settings_data:
            logger.debug("Found plot_style_settings, applying...")

            # Defer drawing during bulk operations to avoid multiple redraws
            self.canvas._defer_drawing = True
            try:
                # Replace the entire plot style
                self.canvas.set_plot_style(settings_data['plot_style_settings'])

                # Force a complete redraw of the plot if there are existing lines
                if hasattr(self.canvas, 'plotted_lines') and self.canvas.plotted_lines:
                    logger.debug(f"Redrawing {len(self.canvas.plotted_lines)} existing lines with new style")
                    # Store current lines and their data
                    lines_data = []
                    for line in self.canvas.plotted_lines:
                        lines_data.append({
                            'xdata': line.get_xdata(),
                            'ydata': line.get_ydata(),
                            'label': line.get_label(),
                            'color': line.get_color(),
                            'linestyle': line.get_linestyle()
                        })

                    # Clear and redraw
                    self.canvas.clear_plot()

                    # Replot with new styles
                    for line_data in lines_data:
                        self.canvas.ax.plot(
                            line_data['xdata'],
                            line_data['ydata'],
                            label=line_data['label'],
                            color=line_data['color'],
                            linestyle=line_data['linestyle']
                        )

                    self.canvas.plotted_lines = self.canvas.ax.get_lines()
                    self.canvas.legend_labels = [line.get_label() for line in self.canvas.plotted_lines if line.get_label()]

                    # Restore axis titles explicitly from style (cleared by ax.clear())
                    try:
                        style = settings_data.get('plot_style_settings', {})
                        x_title = style.get('x_axis_title')
                        y_title = style.get('y_axis_title')
                        y2_title = style.get('y2_axis_title')

                        if x_title:
                            self.canvas.ax.set_xlabel(x_title)
                        if y_title:
                            self.canvas.ax.set_ylabel(y_title)
                        # Apply to Y2 axis if it exists and a title is provided
                        if getattr(self.canvas, 'ax2', None) is not None and y2_title:
                            self.canvas.ax2.set_ylabel(y2_title)
                    except Exception:
                        pass

                    # Update all plot styles after redrawing lines and restoring labels
                    apply_plot_styles(self.canvas)

                # Update style window controls if it exists
                if hasattr(self, 'style_window'):
                    logger.debug("Updating style window controls")
                    self.style_window._set_initial_values()
            finally:
                # Re-enable drawing and perform single redraw
                self.canvas._defer_drawing = False
                self.canvas.draw_idle()
                self.canvas._reapply_pickers_if_needed()
                logger.debug("Canvas redrawn (single draw after defer)")
        else:
            logger.debug("No plot_style_settings found in settings data")
        
        # Apply basic plot settings to parent window if available
        if ('plot_settings' in settings_data and self.app):
            logger.debug("Applying basic plot settings to parent window")
            try:
                plot_settings = settings_data['plot_settings']
                parent = self.app

                # Update all parent window controls
                if hasattr(parent, 'x_min_spin'):
                    parent.x_min_spin.setValue(plot_settings.get('x_min', 0))
                    parent.x_max_spin.setValue(plot_settings.get('x_max', 100))
                    parent.y_min_spin.setValue(plot_settings.get('y_min', 0))
                    parent.y_max_spin.setValue(plot_settings.get('y_max', 100))
                    parent.use_axis_limits.setChecked(plot_settings.get('use_limits', False))

                # Update column selections
                for setting, combo in [('x_column', parent.x_combo), ('y_column', parent.y_combo)]:
                    if setting in plot_settings:
                        index = combo.findText(plot_settings[setting])
                        if index >= 0:
                            combo.setCurrentIndex(index)
            except AttributeError as e:
                logger.error(f"Error applying parent window settings: {str(e)}")
    
    def show_style_window(self):
        """Show the plot style options window"""
        self.style_window.show()
        self.style_window.activateWindow()

    def show_processing_window(self):
        """Show the processing options window"""
        self.processing_window.show()
        self.processing_window.activateWindow()

    def show_radial_menu(self):
        """Show the radial menu centered on the canvas (shortcut: R)"""
        try:
            from radial_menu import show_radial_menu
            from PyQt5.QtCore import QPoint

            # Position au centre du canvas
            center = self.canvas.rect().center()
            global_pos = self.canvas.mapToGlobal(center)

            print("🟢 Menu radial ouvert via raccourci R")
            menu = show_radial_menu(global_pos, self.canvas, self)

            # Pré-sélectionner le premier segment pour la navigation clavier
            if menu:
                menu.hovered_segment = 0
                menu.update()
        except ImportError as e:
            print(f"❌ Erreur import radial_menu: {e}")

    def show_quick_bar(self):
        """Show the quick bar for detailed editing (shortcut: Q)"""
        try:
            from quick_bar import show_quick_bar
            show_quick_bar(self.canvas, self)
        except ImportError as e:
            print(f"❌ Erreur import quick_bar: {e}")

    def show_quick_processing(self):
        """Show the quick processing dialog"""
        try:
            from quick_processing import show_quick_processing
            show_quick_processing(self)
        except ImportError as e:
            print(f"❌ Erreur import quick_processing: {e}")

    def toggle_fullscreen(self, checked=None):
        """Toggle the Plot window fullscreen state.
        If called from the button, 'checked' is a bool; from shortcut it's None.
        """
        # Determine desired state
        if isinstance(checked, bool):
            to_fullscreen = checked
        else:
            to_fullscreen = not self.isFullScreen()

        if to_fullscreen:
            self.showFullScreen()
            if hasattr(self, 'fullscreen_button'):
                self.fullscreen_button.setChecked(True)
        else:
            self.showNormal()
            if hasattr(self, 'fullscreen_button'):
                self.fullscreen_button.setChecked(False)

    def toggle_lock_size(self, checked: bool):
        """Toggle locking of canvas display size to plot size"""
        if hasattr(self, 'canvas'):
            self.canvas.set_lock_display_size(checked)
            # Center the canvas in its scroll area when locked
            try:
                if hasattr(self, 'plot_scroll') and self.plot_scroll:
                    self.plot_scroll.setAlignment(Qt.AlignCenter if checked else (Qt.AlignLeft | Qt.AlignTop))
                    # When locked, keep canvas size and scroll; when unlocked, resize to viewport
                    self.plot_scroll.setWidgetResizable(not checked)
            except Exception:
                pass

    def _load_default_style(self):
        """Load default style settings if available"""
        try:
            home_dir = os.path.expanduser("~")
            settings_file = os.path.join(home_dir, '.csv_plotter_settings', 'plot_style_settings.json')
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    style_dict = json.load(f)
                    
                if isinstance(style_dict, dict) and style_dict:
                    self.canvas.set_plot_style(style_dict)
                    return True
        except Exception as e:
            logger.error(f"Error loading default style: {str(e)}")
            QMessageBox.warning(self, "Error", f"Failed to load default style settings: {str(e)}")
            
        return False
