from PyQt5.QtWidgets import (QTableWidget, QTableWidgetItem, QPushButton,
                           QComboBox, QLineEdit, QColorDialog, QMenu,
                           QAction, QGridLayout, QWidget, QHeaderView,
                           QTableWidgetSelectionRange, QInputDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QMimeData, QByteArray, QItemSelection, QItemSelectionModel
from PyQt5.QtGui import QColor, QIcon, QPixmap, QDrag
from difflib import SequenceMatcher
import os
import re
from app_logging import logger


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem avec tri numérique au lieu d'alphabétique"""

    def __init__(self, value, precision=6):
        """
        Args:
            value: float/int to display, OR dict {'value': float, 'precision': int}
            precision: number of decimals (ignored if value is dict)
        """
        # Handle dict format (new extracted columns with precision)
        if isinstance(value, dict) and 'value' in value:
            self.numeric_value = float(value['value'])
            precision = value.get('precision', 6)
        # Handle raw numeric (backward compatibility for parquet columns)
        elif isinstance(value, (int, float)):
            self.numeric_value = float(value)
        else:
            self.numeric_value = float('inf')

        # Format display with correct precision
        if isinstance(self.numeric_value, float) and self.numeric_value != float('inf'):
            super().__init__(f"{self.numeric_value:.{precision}f}")
        else:
            super().__init__(str(value))

    def __lt__(self, other):
        """Enable numeric sorting (called by QTableWidget.sortItems())"""
        if isinstance(other, NumericTableWidgetItem):
            return self.numeric_value < other.numeric_value
        return super().__lt__(other)


class FileStyleTableWidget(QTableWidget):
    """Table with checkboxes for each file and style options"""
    
    colorChanged = pyqtSignal(str, str)  # (filename, color)
    y2ColorChanged = pyqtSignal(str, str)  # (filename, y2_color)
    styleChanged = pyqtSignal(str, str)  # (filename, style)
    legendChanged = pyqtSignal(str, str)  # (filename, legend_text)
    linkClicked = pyqtSignal(str)  # (filename)

    # Define color palettes
    COLOR_PALETTES = {
        "Retro Metro": ["#ea5545", "#f46a9b", "#ef9b20", "#edbf33", "#ede15b", "#bdcf32", "#87bc45", "#27aeef", "#b33dc6"],
        "Dutch Field": ["#e60049", "#0bb4ff", "#50e991", "#e6d800", "#9b19f5", "#ffa300", "#dc0ab4", "#b3d4ff", "#00bfa0"],
        "River Nights": ["#b30000", "#7c1158", "#4421af", "#1a53ff", "#0d88e6", "#00b7c7", "#5ad45a", "#8be04e", "#ebdc78"],
        "Spring Pastels": ["#fd7f6f", "#7eb0d5", "#b2e061", "#bd7ebe", "#ffb55a", "#ffee65", "#beb9db", "#fdcce5", "#8bd3c7"],
        "Blue to Yellow": ["#115f9a", "#1984c5", "#22a7f0", "#48b5c4", "#76c68f", "#a6d75b", "#c9e52f", "#d0ee11", "#f4f100"],
        "Grey to Red": ["#d7e1ee", "#cbd6e4", "#bfcbdb", "#b3bfd1", "#a4a2a8", "#df8879", "#c86558", "#b04238", "#991f17"],
        "Black to Pink": ["#2e2b28", "#3b3734", "#474440", "#54504c", "#6b506b", "#ab3da9", "#de25da", "#eb44e8", "#ff80ff"],
        "Blues": ["#0000b3", "#0010d9", "#0020ff", "#0040ff", "#0060ff", "#0080ff", "#009fff", "#00bfff", "#00ffff"],
        "Blue to Red": ["#1984c5", "#22a7f0", "#63bff0", "#a7d5ed", "#e2e2e2", "#e1a692", "#de6e56", "#e14b31", "#c23728"],
        "Orange to Purple": ["#ffb400", "#d2980d", "#a57c1b", "#786028", "#363445", "#48446e", "#5e569b", "#776bcd", "#9080ff"],
        "Pink Foam": ["#54bebe", "#76c8c8", "#98d1d1", "#badbdb", "#dedad2", "#e4bcad", "#df979e", "#d7658b", "#c80064"],
        "Salmon to Aqua": ["#e27c7c", "#a86464", "#6d4b4b", "#503f3f", "#333333", "#3c4e4b", "#466964", "#599e94", "#6cd4c5"]
    }
    
    # Group palettes by category
    PALETTE_CATEGORIES = {
        "Complete": ["Retro Metro", "Dutch Field", "River Nights", "Spring Pastels"],
        "Sequential": ["Blue to Yellow", "Grey to Red", "Black to Pink", "Blues"],
        "Diverging": ["Blue to Red", "Orange to Purple", "Pink Foam", "Salmon to Aqua"]
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(7)  # Base columns: File, Select, Y1, Y2, Line Style, Legend Label, Link
        self.setHorizontalHeaderLabels(["File", "Select", "Y1", "Y2", "Line Style", "Legend Label", "Link"])
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        
        # Enable multi-selection
        self.setSelectionMode(QTableWidget.ExtendedSelection)

        # Enable drag & drop reordering of rows (custom handling to move cell widgets too)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        # Use generic drag/drop mode; we handle the drop ourselves
        self.setDragDropMode(QTableWidget.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropOverwriteMode(False)
        
        # Set selection style
        self.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #e0e7ff;
                color: black;
            }
            QTableWidget::item:selected:focus {
                background-color: #c7d2fe;
                color: black;
            }
        """)

        # Set minimum size to prevent collapse when empty
        self.setMinimumSize(600, 200)

        # Dictionary to store parquet columns for each file
        self.parquet_columns = {}
        # Dictionary to store extracted data columns for each file
        self.extracted_columns = {}
        # Dictionary to store sort state for extracted columns {col_index: 'asc' or 'desc'}
        self.extracted_column_sort_state = {}
        # Allow user to force which token is used as series identifier (None = auto)
        self.series_token_index = None
        
        # Search functionality
        self.search_widget = None
        self.search_column = -1
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_fuzzy_search)
        
        # Connect the header click signal to toggle all checkboxes
        self.horizontalHeader().sectionClicked.connect(self.header_clicked)

        # Enable context menu on header
        self.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

    # ---------- Row reordering helpers (DnD + keyboard) ----------
    def _is_search_row(self, row):
        """Check if the given row is the search row.

        Args:
            row: Row index to check

        Returns:
            bool: True if this is the search row, False otherwise
        """
        item = self.item(row, 0)
        return item is not None and hasattr(item, 'is_search_row')

    def _search_row_index(self):
        """Return the index of the search row if present, else -1."""
        for row in range(self.rowCount()):
            if self._is_search_row(row):
                return row
        return -1

    def _is_contiguous(self, rows):
        if not rows:
            return True
        return rows == list(range(rows[0], rows[0] + len(rows)))

    def startDrag(self, supportedActions):
        rows = self.get_selected_rows()
        if not rows:
            return
        # Prevent dragging the search row
        sidx = self._search_row_index()
        rows = [r for r in rows if r != sidx]
        if not rows:
            return
        mime = QMimeData()
        mime.setData('application/x-qtablewidget-rows', QByteArray(','.join(map(str, rows)).encode()))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.MoveAction)

    def mimeTypes(self):
        # Limit to our custom format to avoid default item-model drops
        return ['application/x-qtablewidget-rows']

    def supportedDropActions(self):
        return Qt.MoveAction

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-qtablewidget-rows') and event.source() is self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat('application/x-qtablewidget-rows') and event.source() is self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat('application/x-qtablewidget-rows') and event.source() is self:
            rows_bytes = event.mimeData().data('application/x-qtablewidget-rows')
            try:
                rows = [int(x) for x in bytes(rows_bytes).decode().split(',') if x]
            except Exception:
                rows = []
            if rows:
                # Determine target row (before removal)
                pos = event.pos()
                target_row = self.rowAt(pos.y())
                if target_row < 0:
                    target_row = self.rowCount()
                # Do not allow dropping above the search row
                sidx = self._search_row_index()
                if sidx == 0 and target_row <= 0:
                    target_row = 1
                # If dropping inside the selected block, place after the block
                rmin, rmax = min(rows), max(rows)
                if rmin <= target_row <= rmax + 1:
                    target_row = rmax + 1
                # Perform move using target BEFORE removal; function will adjust
                self._move_rows_to_target(rows, target_row)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def _get_row_state(self, row):
        """Extract current row state (values only) so we can rebuild widgets safely."""
        state = {}
        # Filename
        state['filename'] = self.item(row, 0).text() if self.item(row, 0) else ''
        # Checked
        chk = self.item(row, 1)
        state['checked'] = (chk.checkState() == Qt.Checked) if chk else False
        # Y1 color
        y1_btn = self.cellWidget(row, 2)
        state['y1_color'] = getattr(y1_btn, 'color', None) or '#1f77b4'
        # Y2 color
        y2_btn = self.cellWidget(row, 3)
        state['y2_color'] = getattr(y2_btn, 'color', None) or '#ff7f0e'
        # Line style
        combo = self.cellWidget(row, 4)
        state['line_style'] = combo.itemData(combo.currentIndex()) if combo else '-'
        # Legend text
        led = self.cellWidget(row, 5)
        state['legend'] = led.text() if led else ''
        # Link status (sample_id)
        link_btn = self.cellWidget(row, 6)
        sample_id = None
        if link_btn and link_btn.text().startswith('Linked: '):
            sample_id = link_btn.text()[8:].strip()
        # Prefer stored parquet_columns if consistent
        if hasattr(self, 'parquet_columns') and state['filename'] in self.parquet_columns:
            sample_id = self.parquet_columns[state['filename']].get('sample_id', sample_id)
        state['sample_id'] = sample_id
        return state

    def _add_row_from_state(self, insert_at, state):
        """Insert a new row at index using provided state values."""
        # Ensure we insert at specific index
        self.insertRow(insert_at)
        # Column 0: filename
        self.setItem(insert_at, 0, QTableWidgetItem(state['filename']))
        # Column 1: checkbox
        checkbox_item = QTableWidgetItem()
        checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        checkbox_item.setCheckState(Qt.Checked if state.get('checked') else Qt.Unchecked)
        self.setItem(insert_at, 1, checkbox_item)
        # Column 2: Y1 color button
        color_button = QPushButton()
        color_button.setStyleSheet(f"background-color: {state['y1_color']}; min-height: 20px;")
        color_button.color = state['y1_color']
        color_button.filename = state['filename']
        color_button.clicked.connect(lambda checked, btn=color_button: self.select_color(btn))
        self.setCellWidget(insert_at, 2, color_button)
        # Column 3: Y2 color button
        y2_button = QPushButton()
        y2_button.setStyleSheet(f"background-color: {state['y2_color']}; min-height: 20px;")
        y2_button.color = state['y2_color']
        y2_button.filename = state['filename']
        y2_button.clicked.connect(lambda checked, btn=y2_button: self.select_y2_color(btn))
        self.setCellWidget(insert_at, 3, y2_button)
        # Column 4: line style combo
        style_combo = QComboBox()
        styles = [('-', 'Solid line'), ('--', 'Dashed line'), ('-.', 'Dash-dot line'), (':', 'Dotted line')]
        for style_value, style_name in styles:
            style_combo.addItem(style_name, style_value)
        # set current
        idx = next((i for i in range(style_combo.count()) if style_combo.itemData(i) == state['line_style']), 0)
        style_combo.setCurrentIndex(idx)
        style_combo.filename = state['filename']
        style_combo.currentIndexChanged.connect(lambda index, combo=style_combo: self.line_style_changed(combo))
        self.setCellWidget(insert_at, 4, style_combo)
        # Column 5: legend edit
        legend_edit = QLineEdit()
        legend_edit.setText(state.get('legend') or os.path.splitext(state['filename'])[0])
        legend_edit.filename = state['filename']
        legend_edit.textChanged.connect(lambda text, edit=legend_edit: self.legend_text_changed(edit))
        self.setCellWidget(insert_at, 5, legend_edit)
        # Column 6: link button
        link_button = QPushButton("Link")
        link_button.filename = state['filename']
        link_button.clicked.connect(lambda checked, btn=link_button: self.link_clicked(btn))
        if state.get('sample_id'):
            link_button.setText(f"Linked: {state['sample_id']}")
            link_button.setStyleSheet("background-color: lightgreen;")
        self.setCellWidget(insert_at, 6, link_button)

    def _move_rows_to_target(self, rows, target_row_before_removal):
        """Move the specified rows (ascending indices) as a block to the target index
        specified relative to the pre-removal layout. Widgets move with cells.
        """
        if not rows:
            return
        rows = sorted(rows)
        # Exclude search row if present
        sidx = self._search_row_index()
        rows = [r for r in rows if r != sidx]
        if not rows:
            return

        # Capture state
        states = [self._get_row_state(r) for r in rows]
        self.setUpdatesEnabled(False)
        try:
            # Remove rows bottom-up to keep indices valid
            for r in sorted(rows, reverse=True):
                self.removeRow(r)

            # Adjust target by number of removed rows that were above it
            k = sum(1 for r in rows if r < target_row_before_removal)
            insert_at = target_row_before_removal - k
            # Clamp insert_at
            if sidx == 0 and insert_at <= 0:
                insert_at = 1
            insert_at = max(0, min(insert_at, self.rowCount()))

            # Insert rows in original order at the insertion point
            cur = insert_at
            for st in states:
                self._add_row_from_state(cur, st)
                cur += 1

            # Reselect moved block as a contiguous range so selection persists
            # across subsequent moves and even after Qt's post-drop handling.
            def reselection():
                if states:
                    top_left = self.model().index(insert_at, 0)
                    bottom_right = self.model().index(insert_at + len(states) - 1, self.columnCount() - 1)
                    # Prefer QTableWidgetSelectionRange for QTableWidget
                    rng = QTableWidgetSelectionRange(insert_at, 0, insert_at + len(states) - 1, self.columnCount() - 1)
                    self.setRangeSelected(rng, True)
                    # Keep a current cell inside the selection without altering selection
                    self.setCurrentCell(insert_at, 0, QItemSelectionModel.NoUpdate)
                    self.setFocus()

            # Apply now (for keyboard moves) and also defer once (for DnD)
            reselection()
            QTimer.singleShot(0, reselection)
        finally:
            self.setUpdatesEnabled(True)

    def move_selected_rows(self, direction):
        """Move current selection up (-1) or down (+1) by one row."""
        rows = self.get_selected_rows()
        if not rows:
            return
        sidx = self._search_row_index()
        if direction < 0:
            # Can't move above the first data row
            lower_bound = 1 if sidx == 0 else 0
            if min(rows) <= lower_bound:
                return
            target_before = min(rows) - 1
            self._move_rows_to_target(rows, target_before)
        elif direction > 0:
            # Can't move below the last row
            if max(rows) >= self.rowCount() - 1:
                return
            target_before = max(rows) + 2  # see derivation in analysis
            self._move_rows_to_target(rows, target_before)
        
    def add_file_row(self, filename, color, line_style, line_styles, legend_label=None, linked_id=None, y2_color=None):
        row = self.rowCount()
        self.insertRow(row)
        
        self.setItem(row, 0, QTableWidgetItem(filename))
        
        checkbox_item = QTableWidgetItem()
        checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        checkbox_item.setCheckState(Qt.Unchecked)
        self.setItem(row, 1, checkbox_item)
        
        # Y1 Color button (column 2)
        color_button = QPushButton()
        color_button.setStyleSheet(f"background-color: {color}; min-height: 20px;")
        color_button.color = color
        color_button.filename = filename
        color_button.clicked.connect(lambda checked, btn=color_button: self.select_color(btn))
        self.setCellWidget(row, 2, color_button)
        
        # Y2 Color button (column 3)
        if y2_color is None:
            y2_color = "#ff7f0e"  # Default orange color for Y2
        y2_color_button = QPushButton()
        y2_color_button.setStyleSheet(f"background-color: {y2_color}; min-height: 20px;")
        y2_color_button.color = y2_color
        y2_color_button.filename = filename
        y2_color_button.clicked.connect(lambda checked, btn=y2_color_button: self.select_y2_color(btn))
        self.setCellWidget(row, 3, y2_color_button)
        
        # Add link button in column 6
        link_button = QPushButton("Link")
        link_button.filename = filename
        link_button.clicked.connect(lambda checked, btn=link_button: self.link_clicked(btn))
        
        # If already linked, update button appearance
        if linked_id:
            link_button.setText(f"Linked: {linked_id}")
            link_button.setStyleSheet("background-color: lightgreen;")
            
        self.setCellWidget(row, 6, link_button)

        style_combo = QComboBox()
        styles = [
            ("-", "Solid line"),  # Set this as default
            ("--", "Dashed line"),
            ("-.", "Dash-dot line"),
            (":", "Dotted line"),
        ]
        for style_value, style_name in styles:
            style_combo.addItem(style_name, style_value)
        
        # Set default to "Solid line" if no specific style is provided
        if not line_style or line_style not in [s[0] for s in styles]:
            style_combo.setCurrentIndex(0)  # Set to first item (Solid line)
        else:
            # Otherwise set to the specified style if it exists
            for i in range(style_combo.count()):
                if style_combo.itemData(i) == line_style:
                    style_combo.setCurrentIndex(i)
                    break
                
        style_combo.filename = filename
        style_combo.currentIndexChanged.connect(
            lambda index, combo=style_combo: self.line_style_changed(combo)
        )
        self.setCellWidget(row, 4, style_combo)
        
        # Add legend text field
        legend_edit = QLineEdit()
        if legend_label:
            legend_text = legend_label
        else:
            # Default legend shows filename without extension (e.g., foo_123 not foo_123.csv)
            legend_text = os.path.splitext(filename)[0]
        legend_edit.setText(legend_text)
        legend_edit.filename = filename
        legend_edit.textChanged.connect(
            lambda text, edit=legend_edit: self.legend_text_changed(edit)
        )
        self.setCellWidget(row, 5, legend_edit)

    def link_clicked(self, button):
        """Handle link button clicks"""
        self.linkClicked.emit(button.filename)
        
    def update_link_status(self, filename, sample_id, sample_data=None):
        """Update the link button text and style when a file is linked"""
        for row in range(self.rowCount()):
            # Skip search row
            if self._is_search_row(row):
                continue
                
            item = self.item(row, 0)
            if item and item.text() == filename:
                # Update link button (column 6)
                link_button = self.cellWidget(row, 6)
                if link_button:
                    link_button.setText(f"Linked: {sample_id}")
                    link_button.setStyleSheet("background-color: lightgreen;")
                
                # Store the sample data for this file
                if sample_data:
                    self.parquet_columns[filename] = sample_data
                    self.update_parquet_columns_display()
                break

    def get_selected_rows(self):
        """Get the row indices of all selected rows, excluding search row"""
        rows = []
        for index in self.selectedIndexes():
            row = index.row()
            # Skip search row and avoid duplicates
            if row not in rows and not self._is_search_row(row):
                rows.append(row)
        return sorted(rows)  # Sort rows to maintain order
    
    def get_selected_filenames(self):
        """Get the filenames of all selected rows"""
        filenames = []
        for row in self.get_selected_rows():
            if self.item(row, 0):
                filenames.append(self.item(row, 0).text())
        return filenames

    def select_color(self, button):
        """Show color menu when color button is clicked"""
        # Get the row containing this button
        button_row = -1
        for row in range(self.rowCount()):
            if self.cellWidget(row, 2) == button:
                button_row = row
                break
        
        logger.debug(f"Button clicked in row {button_row}")

        # Get all currently selected rows
        selected_rows = self.get_selected_rows()
        logger.debug(f"Currently selected rows: {selected_rows}")
        
        # If button's row is not in selected rows, add it to selection
        if button_row not in selected_rows:
            self.clearSelection()
            self.selectRow(button_row)
            selected_rows = [button_row]
        
        # Important: Store the button row for use in color application
        self._last_clicked_row = button_row
        
        # Show the color menu
        menu = self.create_color_menu(button, True)
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def select_y2_color(self, button):
        """Show Y2 color menu when Y2 color button is clicked"""
        # Get the row containing this button
        button_row = -1
        for row in range(self.rowCount()):
            if self.cellWidget(row, 3) == button:  # Y2 color is in column 3
                button_row = row
                break
        
        logger.debug(f"Y2 Button clicked in row {button_row}")

        # Get all currently selected rows
        selected_rows = self.get_selected_rows()
        logger.debug(f"Currently selected rows: {selected_rows}")
        
        # If button's row is not in selected rows, add it to selection
        if button_row not in selected_rows:
            self.clearSelection()
            self.selectRow(button_row)
            selected_rows = [button_row]
        
        # Important: Store the button row for use in color application
        self._last_clicked_row = button_row
        
        # Show the Y2 color menu
        menu = self.create_color_menu(button, False)  # False = Y2 color
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def apply_color_to_selection(self, color):
        """Apply a single color to all selected files"""
        logger.debug(f"Applying color {color} to selected rows")
        selected_rows = self.get_selected_rows()

        # Include the clicked row if it's not in the selection
        if hasattr(self, '_last_clicked_row') and self._last_clicked_row not in selected_rows:
            selected_rows = [self._last_clicked_row] + selected_rows

        logger.debug(f"Selected rows (including clicked): {selected_rows}")

        # Determine if this is Y1 or Y2 color based on stored type
        is_y1_color = getattr(self, '_current_color_type', True)
        column_index = 2 if is_y1_color else 3  # Y1=column 2, Y2=column 3

        for row in selected_rows:
            color_button = self.cellWidget(row, column_index)
            if color_button:
                color_button.setStyleSheet(f"background-color: {color}; min-height: 20px;")
                color_button.color = color
                filename = self.item(row, 0).text()
                logger.debug(f"Updating {'Y1' if is_y1_color else 'Y2'} color for file {filename} to {color}")
                
                if is_y1_color:
                    self.colorChanged.emit(filename, color)
                else:
                    self.y2ColorChanged.emit(filename, color)

    def create_color_menu(self, button, is_y1_color=True):
        """Create a popup menu with color palette options"""
        menu = QMenu(self)
        
        # Store the button type for later use
        self._current_color_type = is_y1_color
        
        # Add "Color Picker" option at the top
        picker_action = QAction("Color Picker...", self)
        picker_action.triggered.connect(lambda: self.show_color_dialog(button))
        menu.addAction(picker_action)
        menu.addSeparator()
        
        # Add each palette category
        for category, palette_names in self.PALETTE_CATEGORIES.items():
            category_menu = menu.addMenu(category)
            
            # Add each palette in this category
            for palette_name in palette_names:
                palette_menu = category_menu.addMenu(palette_name)
                
                # Add option to apply entire palette (works for single or multiple selections)
                apply_palette_action = QAction("Apply Entire Palette", self)
                # Store the palette name in the action's data
                apply_palette_action.setData(palette_name)
                apply_palette_action.triggered.connect(
                    lambda checked, p=palette_name: self.apply_palette_colors_to_selection(p)
                )
                palette_menu.addAction(apply_palette_action)
                palette_menu.addSeparator()
                
                # Add individual colors from the palette
                colors = self.COLOR_PALETTES[palette_name]
                for color in colors:
                    color_action = QAction(self)
                    pixmap = QPixmap(16, 16)
                    pixmap.fill(QColor(color))
                    color_action.setIcon(QIcon(pixmap))
                    color_action.setData(color)
                    color_action.setText(color)
                    color_action.triggered.connect(
                        lambda checked, c=color: self.apply_color_to_selection(c)
                    )
                    palette_menu.addAction(color_action)
        
        return menu



    def show_color_dialog(self, button):
        """Show the standard color dialog and apply color to all selected rows"""
        color = QColorDialog.getColor(QColor(button.color), self, "Select line color")
        if color.isValid():
            logger.debug(f"Color dialog selected color: {color.name()}")
            self.apply_color_to_selection(color.name())

    def apply_palette_colors_to_selection(self, palette_name):
        """Apply a color palette to selected files, cycling through the palette"""
        # Get all selected rows including the clicked row
        selected_rows = self.get_selected_rows()
        
        # Include the clicked row if it's not in the selection
        if hasattr(self, '_last_clicked_row') and self._last_clicked_row not in selected_rows:
            selected_rows = [self._last_clicked_row] + selected_rows
        
        logger.debug(f"Applying palette {palette_name} to rows: {selected_rows}")

        if not selected_rows or palette_name not in self.COLOR_PALETTES:
            return

        palette = self.COLOR_PALETTES[palette_name]
        if not palette:
            return

        # Apply colors from palette cyclically to selected rows
        for i, row in enumerate(selected_rows):
            color = palette[i % len(palette)]
            logger.debug(f"Applying color {color} to row {row}")
            color_button = self.cellWidget(row, 2)
            if color_button:
                color_button.setStyleSheet(f"background-color: {color}; min-height: 20px;")
                color_button.color = color
                filename = self.item(row, 0).text()
                self.colorChanged.emit(filename, color)

    def show_color_header_menu(self, position):
        """Show menu with both normal and intelligent coloring options"""
        menu = QMenu(self)
        
        # Add intelligent coloring option
        intelligent_action = QAction("🎨 Coloration intelligente par série", self)
        intelligent_action.triggered.connect(lambda: self.show_intelligent_color_menu(position))
        menu.addAction(intelligent_action)
        menu.addSeparator()
        
        # Add normal palette options for all files
        normal_menu = menu.addMenu("Coloration normale (tous les fichiers)")
        
        # Add each palette category for normal coloring
        for category, palette_names in self.PALETTE_CATEGORIES.items():
            category_menu = normal_menu.addMenu(category)
            
            # Add each palette in this category
            for palette_name in palette_names:
                action = QAction(palette_name, self)
                action.triggered.connect(lambda checked, p=palette_name: self.apply_palette_to_all(p))
                category_menu.addAction(action)
        
        menu.exec_(position)

    def show_y2_color_header_menu(self, position):
        """Show menu with both normal and intelligent coloring options for Y2"""
        menu = QMenu(self)
        
        # Add intelligent coloring option for Y2
        intelligent_action = QAction("🎨 Coloration intelligente par série (Y2)", self)
        intelligent_action.triggered.connect(lambda: self.show_intelligent_y2_color_menu(position))
        menu.addAction(intelligent_action)
        menu.addSeparator()
        
        # Add normal palette options for all files (Y2)
        normal_menu = menu.addMenu("Coloration normale Y2 (tous les fichiers)")
        
        # Add each palette category for normal Y2 coloring
        for category, palette_names in self.PALETTE_CATEGORIES.items():
            category_menu = normal_menu.addMenu(category)
            
            # Add each palette in this category
            for palette_name in palette_names:
                action = QAction(palette_name, self)
                action.triggered.connect(lambda checked, p=palette_name: self.apply_y2_palette_to_all(p))
                category_menu.addAction(action)
        
        menu.exec_(position)

    def show_palette_menu_for_all(self, position):
        """Show menu with palette options for all files"""
        menu = QMenu(self)
        
        # Add each palette category
        for category, palette_names in self.PALETTE_CATEGORIES.items():
            category_menu = menu.addMenu(category)
            
            # Add each palette in this category
            for palette_name in palette_names:
                action = QAction(palette_name, self)
                action.triggered.connect(lambda checked, p=palette_name: self.apply_palette_to_all(p))
                category_menu.addAction(action)
        
        menu.exec_(position)

    def apply_palette_to_all(self, palette_name):
        """Apply a palette to all files"""
        if palette_name not in self.COLOR_PALETTES:
            return
            
        palette = self.COLOR_PALETTES[palette_name]
        if not palette:
            return
            
        # Get all files (excluding search row)
        file_rows = []
        for row in range(self.rowCount()):
            if not self._is_search_row(row):
                file_rows.append((row, self.item(row, 0).text()))
        
        # Apply colors from palette cyclically
        for i, (row, filename) in enumerate(file_rows):
            color = palette[i % len(palette)]
            color_button = self.cellWidget(row, 2)
            if color_button:
                color_button.setStyleSheet(f"background-color: {color}; min-height: 20px;")
                color_button.color = color
                self.colorChanged.emit(filename, color)

    def apply_y2_palette_to_all(self, palette_name):
        """Apply a palette to all files for Y2 colors"""
        if palette_name not in self.COLOR_PALETTES:
            return
            
        palette = self.COLOR_PALETTES[palette_name]
        if not palette:
            return
            
        # Get all files (excluding search row)
        file_rows = []
        for row in range(self.rowCount()):
            if not self._is_search_row(row):
                file_rows.append((row, self.item(row, 0).text()))
        
        # Apply colors from palette cyclically to Y2 color buttons (column 3)
        for i, (row, filename) in enumerate(file_rows):
            color = palette[i % len(palette)]
            y2_color_button = self.cellWidget(row, 3)  # Column 3 for Y2 colors
            if y2_color_button:
                y2_color_button.setStyleSheet(f"background-color: {color}; min-height: 20px;")
                y2_color_button.color = color
                self.y2ColorChanged.emit(filename, color)

    def line_style_changed(self, combo):
        """Handle line style changes"""
        style = combo.currentData()
        self.styleChanged.emit(combo.filename, style)
    
    def legend_text_changed(self, edit):
        """Handle legend text changes"""
        text = edit.text()
        self.legendChanged.emit(edit.filename, text)

    def get_checked_items(self):
        """Get list of checked filenames"""
        checked_items = []
        for row in range(self.rowCount()):
            # Skip search row
            if self._is_search_row(row):
                continue
                
            item = self.item(row, 1)
            if item and item.checkState() == Qt.Checked:
                filename = self.item(row, 0).text()
                checked_items.append(filename)
        return checked_items
    
    def get_legend_text(self, filename):
        """Get legend text for a file"""
        for row in range(self.rowCount()):
            # Skip search row
            if self._is_search_row(row):
                continue
                
            file_item = self.item(row, 0)
            if file_item and file_item.text() == filename:
                legend_edit = self.cellWidget(row, 5)  # Fixed: Column 5 contains QLineEdit, not column 4
                if legend_edit and isinstance(legend_edit, QLineEdit):  # Added type checking
                    return legend_edit.text()
        return filename  # Default to filename if not found

    def header_clicked(self, section):
        """Handle clicks on table header sections"""
        # Check if the "Select" column header was clicked (section 1)
        if section == 1:
            # Toggle all checkboxes
            any_unchecked = False
            for row in range(self.rowCount()):
                if not self._is_search_row(row):
                    item = self.item(row, 1)
                    if item and item.checkState() == Qt.Unchecked:
                        any_unchecked = True
                        break
            
            new_state = Qt.Checked if any_unchecked else Qt.Unchecked
            for row in range(self.rowCount()):
                if not self._is_search_row(row):
                    item = self.item(row, 1)
                    if item:
                        item.setCheckState(new_state)
        
        # Check if the "Y1 Color" column header was clicked (section 2)
        elif section == 2:
            # Show menu with both normal and intelligent coloring options
            header_global_pos = self.horizontalHeader().mapToGlobal(QPoint(0, 0))
            header_pos = QPoint(
                header_global_pos.x() + self.horizontalHeader().sectionPosition(section),
                header_global_pos.y() + self.horizontalHeader().height()
            )
            self.show_color_header_menu(header_pos)
        
        # Check if the "Y2 Color" column header was clicked (section 3)
        elif section == 3:
            # Show menu with both normal and intelligent coloring options for Y2
            header_global_pos = self.horizontalHeader().mapToGlobal(QPoint(0, 0))
            header_pos = QPoint(
                header_global_pos.x() + self.horizontalHeader().sectionPosition(section),
                header_global_pos.y() + self.horizontalHeader().height()
            )
            self.show_y2_color_header_menu(header_pos)
        
        # Check for searchable columns (File: 0, Legend Label: 5) or dynamic columns (7+)
        elif section == 0 or section == 5:
            self.start_fuzzy_search(section)
        elif section >= 7:
            # Differentiate extracted columns vs parquet columns
            header_text = self.horizontalHeaderItem(section).text() if self.horizontalHeaderItem(section) else ""

            if self.is_extracted_column(header_text):
                # Extracted column → sort numerically
                self.sort_by_extracted_column(section)
                logger.debug(f"🟢 Sorting by extracted column: {header_text}")
            else:
                # Parquet column → search
                self.start_fuzzy_search(section)

    def update_parquet_columns_display(self):
        """Update the table to display parquet columns if any files have parquet data"""
        if not self.parquet_columns:
            return
                
        # Get all unique column names from all linked files
        all_columns = set()
        for data in self.parquet_columns.values():
            all_columns.update(data.keys())
                
        # Remove sample_id as it's already shown in the Link column
        if 'sample_id' in all_columns:
            all_columns.remove('sample_id')
                
        # Sort columns for consistent display
        parquet_cols = sorted(all_columns)
        
        # Check if we need to add columns
        current_columns = self.columnCount()
        base_columns = 6  # File, Select, Color, Line Style, Legend Label, Link
        
        # Get current header labels - safely handling None items
        current_headers = []
        for i in range(current_columns):
            header_item = self.horizontalHeaderItem(i)
            if header_item is not None:
                current_headers.append(header_item.text())
            else:
                current_headers.append("")  # Default value for missing headers
        
        # Add new columns if needed
        for col in parquet_cols:
            if col not in current_headers:
                self.insertColumn(current_columns)
                self.setHorizontalHeaderItem(current_columns, QTableWidgetItem(col))
                current_columns += 1
                    
        # Update all rows with parquet data
        for row in range(self.rowCount()):
            # Skip search row
            if self._is_search_row(row):
                continue
                
            filename = self.item(row, 0).text()
            if filename in self.parquet_columns:
                file_data = self.parquet_columns[filename]
                
                for col_idx in range(base_columns, self.columnCount()):
                    col_name = self.horizontalHeaderItem(col_idx).text()
                    value = str(file_data.get(col_name, ""))
                    
                    # Create or update item
                    if self.item(row, col_idx) is None:
                        self.setItem(row, col_idx, QTableWidgetItem(value))
                    else:
                        self.item(row, col_idx).setText(value)
        
        # Resize columns to fit content
        self.resizeColumnsToContents()

        # Cap base column widths to prevent window from becoming too wide
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
            if col < self.columnCount() and self.columnWidth(col) > max_width:
                self.setColumnWidth(col, max_width)

        # Set a maximum width for parquet columns to prevent extreme stretching
        for i in range(base_columns, self.columnCount()):
            if self.columnWidth(i) > 200:
                self.setColumnWidth(i, 200)

    def is_extracted_column(self, column_name):
        """Check if a column name is an extracted column

        Args:
            column_name: Name of the column to check

        Returns:
            bool: True if column exists in extracted_columns for any file
        """
        if not self.extracted_columns:
            return False

        # Check if column name exists in any file's extracted data
        for file_data in self.extracted_columns.values():
            if column_name in file_data:
                return True
        return False

    def update_extracted_columns_display(self):
        """Update the table to display extracted columns if any files have extracted data"""
        if not self.extracted_columns:
            return

        # Get all unique column names from all files with extracted data
        all_columns = set()
        for data in self.extracted_columns.values():
            all_columns.update(data.keys())

        # Sort columns for consistent display
        extracted_cols = sorted(all_columns)

        # Check if we need to add columns
        current_columns = self.columnCount()
        base_columns = 6  # File, Select, Color, Line Style, Legend Label, Link

        # Get current header labels - safely handling None items
        current_headers = []
        for i in range(current_columns):
            header_item = self.horizontalHeaderItem(i)
            if header_item is not None:
                current_headers.append(header_item.text())
            else:
                current_headers.append("")  # Default value for missing headers

        # Add new columns if needed
        for col in extracted_cols:
            if col not in current_headers:
                self.insertColumn(current_columns)
                self.setHorizontalHeaderItem(current_columns, QTableWidgetItem(col))
                current_columns += 1

        # Update all rows with extracted data
        for row in range(self.rowCount()):
            # Skip search row
            if self._is_search_row(row):
                continue

            filename = self.item(row, 0).text()
            if filename in self.extracted_columns:
                file_data = self.extracted_columns[filename]

                for col_idx in range(base_columns, self.columnCount()):
                    col_name = self.horizontalHeaderItem(col_idx).text()
                    raw_value = file_data.get(col_name, "")

                    # Use NumericTableWidgetItem for numeric sorting
                    # Always replace item to ensure correct type
                    self.setItem(row, col_idx, NumericTableWidgetItem(raw_value))

        # Resize columns to fit content
        self.resizeColumnsToContents()

        # Cap base column widths to prevent window from becoming too wide
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
            if col < self.columnCount() and self.columnWidth(col) > max_width:
                self.setColumnWidth(col, max_width)

        # Set a maximum width for extracted columns to prevent extreme stretching
        for i in range(base_columns, self.columnCount()):
            if self.columnWidth(i) > 200:
                self.setColumnWidth(i, 200)

    def sort_by_extracted_column(self, section):
        """Sort table rows by extracted column values (numeric)

        Args:
            section: Column index to sort by
        """
        # Toggle sort order
        current_order = self.extracted_column_sort_state.get(section, None)

        if current_order == 'asc':
            new_order = 'desc'
            qt_order = Qt.DescendingOrder
        else:
            new_order = 'asc'
            qt_order = Qt.AscendingOrder

        self.extracted_column_sort_state[section] = new_order

        logger.debug(f"🔵 Sorting column {section} in {new_order} order")

        # Use QTableWidget built-in sort
        # Works because we're using NumericTableWidgetItem with __lt__ override
        self.sortItems(section, qt_order)

        logger.info(f"✅ Sort complete")

    def start_fuzzy_search(self, column):
        """Start fuzzy search for a specific column"""
        # Close existing search if any
        self.close_search()
        
        self.search_column = column
        
        # Create search widget
        self.search_widget = QLineEdit()
        header_text = self.horizontalHeaderItem(column).text() if self.horizontalHeaderItem(column) else f"Colonne {column}"
        self.search_widget.setPlaceholderText(f"Recherche dans {header_text}... (ENTER=valider, ESC=annuler)")
        self.search_widget.textChanged.connect(self.on_search_text_changed)
        
        # Add search row at the top
        self.insertRow(0)
        self.setCellWidget(0, column, self.search_widget)
        
        # Mark this as a search row
        search_item = QTableWidgetItem("")
        search_item.is_search_row = True
        self.setItem(0, 0, search_item)
        
        # Focus and select the search widget
        self.search_widget.setFocus()
        
    def close_search(self):
        """Close the search widget"""
        if self.search_widget:
            # Remove search row
            for row in range(self.rowCount()):
                if self._is_search_row(row):
                    self.removeRow(row)
                    break
            
            self.search_widget = None
            self.search_column = -1
    
    
    def on_search_text_changed(self, text):
        """Handle search text changes with debouncing"""
        self.search_timer.stop()
        if text:
            self.search_timer.start(300)  # 300ms debounce
        else:
            self.show_all_rows()
    
    def perform_fuzzy_search(self):
        """Perform simple substring search and filter rows"""
        if not self.search_widget or self.search_column == -1:
            return
        
        search_text = self.search_widget.text().lower()
        if not search_text:
            self.show_all_rows()
            return
        
        # Simple substring search - hide rows that don't match
        for row in range(self.rowCount()):
            if self._is_search_row(row):
                continue
            
            # Get text from the search column
            target_text = ""
            widget = self.cellWidget(row, self.search_column)
            if widget and isinstance(widget, QLineEdit):
                target_text = widget.text()
            elif self.item(row, self.search_column):
                target_text = self.item(row, self.search_column).text()
            
            # Simple contains check
            should_show = search_text in target_text.lower()
            self.setRowHidden(row, not should_show)
    
    def show_all_rows(self):
        """Show all rows (clear search filter)"""
        for row in range(self.rowCount()):
            if not self._is_search_row(row):
                self.setRowHidden(row, False)
    
    def keyPressEvent(self, event):
        """Handle key press events (search + row move shortcuts)"""
        if self.search_widget:
            if event.key() == Qt.Key_Escape:
                self.show_all_rows()
                self.close_search()
                return
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.close_search()
                return

        # Global shortcuts when not typing in search
        if event.modifiers() & Qt.AltModifier:
            if event.key() == Qt.Key_Up:
                self.move_selected_rows(-1)
                event.accept()  # prevent default selection handling (Shift/Ctrl)
                return
            elif event.key() == Qt.Key_Down:
                self.move_selected_rows(1)
                event.accept()  # prevent default selection handling (Shift/Ctrl)
                return

        super().keyPressEvent(event)

    def detect_series_from_filenames(self):
        """Detect series from filenames using simple token heuristics."""
        series_groups = {}
        handled_rows = set()

        def _content_tokens(name):
            """Split a filename (without extension) into content tokens."""
            tokens = re.split(r'[\\s_;-]+', name, flags=re.IGNORECASE)
            tokens = [t for t in tokens if t]
            return [t.lower() for t in tokens]

        # Keep the old strict pattern as a first pass
        strict_pattern = re.compile(r'^(.+?)_(\d{6})_(\d+)_(\d+)$')
        rows_info = []

        for row in range(self.rowCount()):
            if self._is_search_row(row) or not self.item(row, 0):
                continue

            filename = self.item(row, 0).text()
            base_name = os.path.splitext(os.path.basename(filename))[0]
            tokens = _content_tokens(base_name)
            rows_info.append({'row': row, 'filename': filename, 'base': base_name, 'tokens': tokens})

            match = strict_pattern.match(base_name)
            if match and self.series_token_index is None:
                series_key = f"{match.group(1)}_{match.group(2)}_{match.group(3)}"
                series_groups.setdefault(series_key, []).append((row, filename))
                handled_rows.add(row)

        # If user forced a token index, bypass heuristics and use it
        if self.series_token_index is not None:
            for info in rows_info:
                tokens = info['tokens']
                prefix = tokens[0] if tokens else info['base']
                if len(tokens) > self.series_token_index:
                    series_token = tokens[self.series_token_index]
                else:
                    series_token = info['base']
                series_key = f"{prefix}|{series_token}"
                series_groups.setdefault(series_key, []).append((info['row'], info['filename']))
            return series_groups

        # Second pass: heuristic token-based grouping
        remaining = [info for info in rows_info if info['row'] not in handled_rows]
        if not remaining:
            return series_groups

        # Group by first token to avoid mixing unrelated families
        prefix_groups = {}
        for info in remaining:
            prefix = info['tokens'][0] if info['tokens'] else info['base']
            prefix_groups.setdefault(prefix, []).append(info)

        for prefix, infos in prefix_groups.items():
            candidate_counts = {}

            # Count numeric tokens by position to find the repeating "series" slot
            for info in infos:
                for idx, token in enumerate(info['tokens'][1:], start=1):
                    num_match = re.search(r'\d+', token)
                    if not num_match:
                        continue
                    num = num_match.group(0)
                    key = (idx, num)
                    looks_date = len(num) == 6
                    entry = candidate_counts.get(key, {'count': 0, 'looks_date': looks_date})
                    entry['count'] += 1
                    candidate_counts[key] = entry

            # Pick the best repeating numeric slot (prefer non-date numbers)
            best_key = None
            best_score = None
            for key, data in candidate_counts.items():
                if data['count'] < 2:
                    continue
                idx, num = key
                score = (0 if data['looks_date'] else 1, data['count'], -idx)
                if best_score is None or score > best_score:
                    best_score = score
                    best_key = key

            if best_key:
                target_idx, _ = best_key
                for info in infos:
                    series_token = info['base']
                    if len(info['tokens']) > target_idx:
                        match = re.search(r'\d+', info['tokens'][target_idx])
                        series_token = match.group(0) if match else info['tokens'][target_idx]
                    series_key = f"{prefix}|{series_token}"
                    series_groups.setdefault(series_key, []).append((info['row'], info['filename']))
            else:
                # Fallback: group by prefix only
                series_key = f"{prefix}|all"
                for info in infos:
                    series_groups.setdefault(series_key, []).append((info['row'], info['filename']))

        return series_groups

    def apply_intelligent_coloring(self, palette_name):
        """Apply intelligent coloring based on detected series"""
        if palette_name not in self.COLOR_PALETTES:
            return
            
        palette = self.COLOR_PALETTES[palette_name]
        if not palette:
            return
        
        # Detect series from filenames
        series_groups = self.detect_series_from_filenames()
        
        # Apply colors: one color per series, cycling through palette
        series_keys = sorted(series_groups.keys())  # Consistent ordering
        
        for series_index, series_key in enumerate(series_keys):
            color = palette[series_index % len(palette)]
            
            # Apply this color to all files in this series
            for row, filename in series_groups[series_key]:
                color_button = self.cellWidget(row, 2)
                if color_button:
                    color_button.setStyleSheet(f"background-color: {color}; min-height: 20px;")
                    color_button.color = color
                    self.colorChanged.emit(filename, color)

    def apply_intelligent_y2_coloring(self, palette_name):
        """Apply intelligent Y2 coloring based on detected series"""
        if palette_name not in self.COLOR_PALETTES:
            return
            
        palette = self.COLOR_PALETTES[palette_name]
        if not palette:
            return
        
        # Detect series from filenames
        series_groups = self.detect_series_from_filenames()
        
        # Apply colors: one color per series, cycling through palette
        series_keys = sorted(series_groups.keys())  # Consistent ordering
        
        for series_index, series_key in enumerate(series_keys):
            color = palette[series_index % len(palette)]
            
            # Apply this color to all files in this series (Y2 column = 3)
            for row, filename in series_groups[series_key]:
                y2_color_button = self.cellWidget(row, 3)  # Column 3 for Y2 colors
                if y2_color_button:
                    y2_color_button.setStyleSheet(f"background-color: {color}; min-height: 20px;")
                    y2_color_button.color = color
                    self.y2ColorChanged.emit(filename, color)

    def show_intelligent_color_menu(self, position):
        """Show menu with palette options for intelligent coloring"""
        menu = QMenu(self)
        
        # Add title
        title_action = QAction("🎨 Coloration intelligente par série", self)
        title_action.setEnabled(False)
        menu.addAction(title_action)
        menu.addSeparator()

        # Allow manual choice of which token defines the series
        choose_action = QAction("Choisir le token de série…", self)
        choose_action.triggered.connect(self.choose_series_token)
        menu.addAction(choose_action)
        menu.addSeparator()
        
        # Add each palette category (intelligent per-series coloring)
        for category, palette_names in self.PALETTE_CATEGORIES.items():
            category_menu = menu.addMenu(category)
            
            # Add each palette in this category
            for palette_name in palette_names:
                action = QAction(palette_name, self)
                action.triggered.connect(lambda checked, p=palette_name: self.apply_intelligent_coloring(p))
                category_menu.addAction(action)
        
        # Add option: same color for all files (Y1)
        menu.addSeparator()
        same_color_menu = menu.addMenu("Même couleur pour tous (Y1)")

        # Color Picker option
        picker_action = QAction("Color Picker...", self)
        picker_action.triggered.connect(lambda: self.choose_and_apply_single_color(is_y1=True))
        same_color_menu.addAction(picker_action)
        same_color_menu.addSeparator()

        # Palette-based single-color choices
        for category, palette_names in self.PALETTE_CATEGORIES.items():
            category_menu = same_color_menu.addMenu(category)
            for palette_name in palette_names:
                palette_menu = category_menu.addMenu(palette_name)
                colors = self.COLOR_PALETTES[palette_name]
                for color in colors:
                    color_action = QAction(self)
                    pixmap = QPixmap(16, 16)
                    pixmap.fill(QColor(color))
                    color_action.setIcon(QIcon(pixmap))
                    color_action.setData(color)
                    color_action.setText(color)
                    color_action.triggered.connect(
                        lambda checked, c=color: self.apply_single_color_to_all(c, is_y1=True)
                    )
                    palette_menu.addAction(color_action)

        menu.exec_(position)

    def show_intelligent_y2_color_menu(self, position):
        """Show menu with palette options for intelligent Y2 coloring"""
        menu = QMenu(self)
        
        # Add title
        title_action = QAction("🎨 Coloration intelligente par série (Y2)", self)
        title_action.setEnabled(False)
        menu.addAction(title_action)
        menu.addSeparator()

        # Allow manual choice of which token defines the series
        choose_action = QAction("Choisir le token de série…", self)
        choose_action.triggered.connect(self.choose_series_token)
        menu.addAction(choose_action)
        menu.addSeparator()
        
        # Add each palette category (intelligent per-series coloring)
        for category, palette_names in self.PALETTE_CATEGORIES.items():
            category_menu = menu.addMenu(category)
            
            # Add each palette in this category
            for palette_name in palette_names:
                action = QAction(palette_name, self)
                action.triggered.connect(lambda checked, p=palette_name: self.apply_intelligent_y2_coloring(p))
                category_menu.addAction(action)
        
        # Add option: same color for all files (Y2)
        menu.addSeparator()
        same_color_menu = menu.addMenu("Même couleur pour tous (Y2)")

        # Color Picker option
        picker_action = QAction("Color Picker...", self)
        picker_action.triggered.connect(lambda: self.choose_and_apply_single_color(is_y1=False))
        same_color_menu.addAction(picker_action)
        same_color_menu.addSeparator()

        # Palette-based single-color choices
        for category, palette_names in self.PALETTE_CATEGORIES.items():
            category_menu = same_color_menu.addMenu(category)
            for palette_name in palette_names:
                palette_menu = category_menu.addMenu(palette_name)
                colors = self.COLOR_PALETTES[palette_name]
                for color in colors:
                    color_action = QAction(self)
                    pixmap = QPixmap(16, 16)
                    pixmap.fill(QColor(color))
                    color_action.setIcon(QIcon(pixmap))
                    color_action.setData(color)
                    color_action.setText(color)
                    color_action.triggered.connect(
                        lambda checked, c=color: self.apply_single_color_to_all(c, is_y1=False)
                    )
                    palette_menu.addAction(color_action)

        menu.exec_(position)

    def apply_single_color_to_all(self, color, is_y1=True):
        """Apply a single color to all files (Y1 or Y2)."""
        column_index = 2 if is_y1 else 3
        for row in range(self.rowCount()):
            # Skip search row
            if self._is_search_row(row):
                continue
            button = self.cellWidget(row, column_index)
            if button:
                button.setStyleSheet(f"background-color: {color}; min-height: 20px;")
                button.color = color
                filename = self.item(row, 0).text()
                if is_y1:
                    self.colorChanged.emit(filename, color)
                else:
                    self.y2ColorChanged.emit(filename, color)

    def choose_and_apply_single_color(self, is_y1=True):
        """Open a color dialog and apply the chosen color to all files (Y1 or Y2)."""
        initial = QColor("#1f77b4")
        color = QColorDialog.getColor(initial, self, "Select line color")
        if color.isValid():
            self.apply_single_color_to_all(color.name(), is_y1=is_y1)

    def choose_series_token(self):
        """Let user choose which token (position) defines the series; None = auto."""
        # Find first non-search row to build a token list example
        example_tokens = []
        example_name = ""
        for row in range(self.rowCount()):
            if self._is_search_row(row):
                continue
            item = self.item(row, 0)
            if item:
                example_name = os.path.splitext(os.path.basename(item.text()))[0]
                example_tokens = re.split(r'[\\s_;-]+', example_name, flags=re.IGNORECASE)
                example_tokens = [t for t in example_tokens if t]
                break

        options = ["Auto (détection)"]
        for idx, tok in enumerate(example_tokens):
            options.append(f"{idx}: {tok}")

        choice, ok = QInputDialog.getItem(self, "Choisir le token série",
                                          f"Nom exemple: {example_name}\nChoisir le token qui définit la série",
                                          options, 0, False)
        if not ok:
            return

        if choice.startswith("Auto"):
            self.series_token_index = None
            logger.debug("[SERIES] Mode auto réactivé")
        else:
            try:
                idx = int(choice.split(":")[0])
                self.series_token_index = idx
                label = example_tokens[idx] if idx < len(example_tokens) else "?"
                logger.debug(f"[SERIES] Token forcé: position {idx} ({label})")
            except Exception:
                self.series_token_index = None
                logger.debug("[SERIES] Sélection invalide, retour auto")

    def show_header_context_menu(self, position):
        """Show context menu when right-clicking on a column header"""
        # Get the column index at the clicked position
        column = self.horizontalHeader().logicalIndexAt(position)

        # Check if this is an extracted column
        header_item = self.horizontalHeaderItem(column)
        if not header_item:
            return

        header_text = header_item.text()

        # Only show menu for extracted columns
        if not self.is_extracted_column(header_text):
            return

        logger.debug(f"🟢 Right-click on extracted column: {header_text}")

        # Create context menu
        menu = QMenu(self)
        delete_action = QAction("Supprimer cette colonne", self)
        delete_action.triggered.connect(lambda: self.delete_extracted_column(column, header_text))
        menu.addAction(delete_action)

        # Show menu at cursor position
        menu.exec_(self.horizontalHeader().mapToGlobal(position))

    def delete_extracted_column(self, column_index, column_name):
        """Delete an extracted column from all files and remove from table"""
        logger.debug(f"🟡 Deleting extracted column: {column_name} (index {column_index})")

        # Remove column from extracted_columns dict for all files
        files_affected = 0
        for filename in list(self.extracted_columns.keys()):
            if column_name in self.extracted_columns[filename]:
                del self.extracted_columns[filename][column_name]
                files_affected += 1
                logger.debug(f"  → Removed from {filename}")

            # Clean up empty dicts
            if not self.extracted_columns[filename]:
                del self.extracted_columns[filename]

        # Remove the physical column from table
        self.removeColumn(column_index)

        logger.info(f"✅ Deleted column '{column_name}' from {files_affected} files")
        logger.info(f"✅ Removed column {column_index} from table")
