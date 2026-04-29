import os
import json
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QMessageBox, QColorDialog,
                           QPushButton)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QMessageBox, QColorDialog,
                           QPushButton, QGroupBox, QFormLayout, QLabel, 
                           QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit,
                           QCheckBox, QHBoxLayout, QScrollArea, QWidget)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt, QTimer
from plot_dialog_components import (
    create_group_box, create_form_layout, create_scroll_area,
    create_spin_box, create_combo_box, create_font_combo_box,
    create_checkbox, create_line_edit, create_button_row,
    GRID_STYLE_MAP, GRID_STYLE_REVERSE_MAP, LEGEND_LOCATIONS, SCALE_TYPES
)
from app_logging import logger

class PlotStyleWindow(QDialog):
    """Window for plot style options"""

    # Debounce delay in milliseconds for live updates
    DEBOUNCE_DELAY_MS = 200

    def __init__(self, plot_window):
        super().__init__(plot_window)
        self.plot_window = plot_window
        self.setWindowTitle("Plot Style Options")
        self.setMinimumWidth(400)

        # Debounce timer for update_styles
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(self.DEBOUNCE_DELAY_MS)
        self._debounce_timer.timeout.connect(self._do_update_styles)

        # Create scroll area for all controls
        scroll = create_scroll_area(self._create_main_widget())

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        # Initialize controls with current settings
        self._set_initial_values()

        # Connect the update handlers after initializing values
        self._connect_update_handlers()

    def showEvent(self, event):
        """Sync controls with canvas style when window is shown"""
        super().showEvent(event)
        self._set_initial_values()

    def _create_main_widget(self):
        """Create the main widget containing all controls"""
        container = QDialog()
        layout = QVBoxLayout(container)
        
        # Title controls
        layout.addWidget(self._create_title_group())
        
        # Add axis settings group
        layout.addWidget(self._create_axis_settings_group())
        
        # Legend controls
        layout.addWidget(self._create_legend_group())
        
        # Axes font controls
        layout.addWidget(self._create_axes_group())
        
        # Line styles group
        layout.addWidget(self._create_line_group())
        
        # Grid settings group
        layout.addWidget(self._create_grid_group())
        
        # Plot size controls
        layout.addWidget(self._create_size_group())
        
        # Action buttons
        layout.addLayout(self._create_control_buttons())
        
        # Add stretcher
        layout.addStretch()
        
        return container

    def _create_title_group(self):
        """Create title controls group"""
        title_form = create_form_layout()
        
        self.title_input = create_line_edit()
        self.title_input.textChanged.connect(self.update_title)
        title_form.addRow("Plot Title:", self.title_input)
        
        self.title_font = create_font_combo_box()
        self.title_font.currentFontChanged.connect(self.update_styles)
        title_form.addRow("Font:", self.title_font)
        
        self.title_size = create_spin_box(8, 30, 12)
        self.title_size.valueChanged.connect(self.update_styles)
        title_form.addRow("Size:", self.title_size)
        
        return create_group_box("Title", title_form)

    def _create_axis_settings_group(self):
        """Create axis settings group"""
        axis_form = create_form_layout()
        
        # Axis Titles
        self.x_axis_title = create_line_edit()
        self.x_axis_title.textChanged.connect(self.update_styles)
        axis_form.addRow("X-Axis Title:", self.x_axis_title)
        
        self.y_axis_title = create_line_edit()
        self.y_axis_title.textChanged.connect(self.update_styles)
        axis_form.addRow("Y1-Axis Title (Left):", self.y_axis_title)
        
        self.y2_axis_title = create_line_edit()
        self.y2_axis_title.textChanged.connect(self.update_styles)
        axis_form.addRow("Y2-Axis Title (Right):", self.y2_axis_title)
        
        # Scale types
        self.x_scale_type = create_combo_box(SCALE_TYPES)
        self.x_scale_type.currentTextChanged.connect(self.update_styles)
        axis_form.addRow("X-Axis Scale:", self.x_scale_type)
        
        self.y_scale_type = create_combo_box(SCALE_TYPES)
        self.y_scale_type.currentTextChanged.connect(self.update_styles)
        axis_form.addRow("Y1-Axis Scale:", self.y_scale_type)
        
        self.y2_scale_type = create_combo_box(SCALE_TYPES)
        self.y2_scale_type.currentTextChanged.connect(self.update_styles)
        axis_form.addRow("Y2-Axis Scale:", self.y2_scale_type)
        
        # Auto scale option
        self.auto_scale = create_checkbox("Auto Scale", True)
        self.auto_scale.stateChanged.connect(self.toggle_auto_scale)
        axis_form.addRow(self.auto_scale)
        
        # Y1 Axis limits
        self.use_axis_limits = create_checkbox("Use Custom Y1 Limits")
        self.use_axis_limits.stateChanged.connect(self.toggle_axis_limits)
        axis_form.addRow(self.use_axis_limits)
        
        # Y2 Axis limits
        self.use_y2_axis_limits = create_checkbox("Use Custom Y2 Limits")
        self.use_y2_axis_limits.stateChanged.connect(self.toggle_y2_axis_limits)
        axis_form.addRow(self.use_y2_axis_limits)
        
        # Spinboxes for limits
        self.x_min_spin = create_spin_box(-1e9, 1e9, decimals=3)
        self.x_min_spin.valueChanged.connect(self.update_styles)
        axis_form.addRow("X Min:", self.x_min_spin)
        
        self.x_max_spin = create_spin_box(-1e9, 1e9, decimals=3)
        self.x_max_spin.valueChanged.connect(self.update_styles)
        axis_form.addRow("X Max:", self.x_max_spin)
        
        self.y_min_spin = create_spin_box(-1e9, 1e9, decimals=3)
        self.y_min_spin.valueChanged.connect(self.update_styles)
        axis_form.addRow("Y1 Min:", self.y_min_spin)
        
        self.y_max_spin = create_spin_box(-1e9, 1e9, decimals=3)
        self.y_max_spin.valueChanged.connect(self.update_styles)
        axis_form.addRow("Y1 Max:", self.y_max_spin)
        
        self.y2_min_spin = create_spin_box(-1e9, 1e9, decimals=3)
        self.y2_min_spin.valueChanged.connect(self.update_styles)
        axis_form.addRow("Y2 Min:", self.y2_min_spin)
        
        self.y2_max_spin = create_spin_box(-1e9, 1e9, decimals=3)
        self.y2_max_spin.valueChanged.connect(self.update_styles)
        axis_form.addRow("Y2 Max:", self.y2_max_spin)
        
        return create_group_box("Axis Settings", axis_form)

    def _create_legend_group(self):
        """Create legend controls group"""
        legend_form = create_form_layout()
        
        self.legend_font = create_font_combo_box()
        self.legend_font.currentFontChanged.connect(self.update_styles)
        legend_form.addRow("Font:", self.legend_font)
        
        self.legend_size = create_spin_box(6, 24, 10)
        self.legend_size.valueChanged.connect(self.update_styles)
        legend_form.addRow("Size:", self.legend_size)
        
        self.legend_columns = create_spin_box(1, 10, 1)
        self.legend_columns.valueChanged.connect(self.update_styles)
        legend_form.addRow("Columns:", self.legend_columns)
        
        self.legend_location = create_combo_box()
        for name, value in LEGEND_LOCATIONS:
            self.legend_location.addItem(name, value)
        self.legend_location.currentIndexChanged.connect(self.update_styles)
        legend_form.addRow("Position:", self.legend_location)
        
        return create_group_box("Legend", legend_form)

    def _create_axes_group(self):
        """Create axes font controls group"""
        axes_form = create_form_layout()
        
        self.axes_font = create_font_combo_box()
        self.axes_font.currentFontChanged.connect(self.update_styles)
        axes_form.addRow("Font:", self.axes_font)
        
        self.axes_size = create_spin_box(6, 24, 10)
        self.axes_size.valueChanged.connect(self.update_styles)
        axes_form.addRow("Size:", self.axes_size)
        
        return create_group_box("Axes", axes_form)

    def _create_line_group(self):
        """Create line style controls group"""
        line_form = create_form_layout()
        
        self.line_width = create_spin_box(1, 100, 10, step=1, decimals=1)
        self.line_width.valueChanged.connect(self.update_styles)
        line_form.addRow("Line Width:", self.line_width)
        
        return create_group_box("Line Styles", line_form)

    def _create_grid_group(self):
        """Create grid settings group"""
        grid_form = create_form_layout()
        
        # Grid checkboxes
        self.x_major_grid = create_checkbox("Major", True)
        self.x_minor_grid = create_checkbox("Minor")
        self.y_major_grid = create_checkbox("Major", True)
        self.y_minor_grid = create_checkbox("Minor")
        
        grid_form.addRow("X Grid:", self.x_major_grid)
        grid_form.addRow("", self.x_minor_grid)
        grid_form.addRow("Y Grid:", self.y_major_grid)
        grid_form.addRow("", self.y_minor_grid)
        
        # Grid styles
        self.major_grid_style = create_combo_box(list(GRID_STYLE_MAP.values()))
        self.minor_grid_style = create_combo_box(list(GRID_STYLE_MAP.values()))
        grid_form.addRow("Major Style:", self.major_grid_style)
        grid_form.addRow("Minor Style:", self.minor_grid_style)
        
        # Grid properties
        self.major_grid_alpha = create_spin_box(0, 100, 50, decimals=1)
        self.minor_grid_alpha = create_spin_box(0, 100, 20, decimals=1)
        self.major_grid_width = create_spin_box(1, 50, 5, decimals=1)
        self.minor_grid_width = create_spin_box(1, 50, 5, decimals=1)
        
        grid_form.addRow("Major Alpha:", self.major_grid_alpha)
        grid_form.addRow("Minor Alpha:", self.minor_grid_alpha)
        grid_form.addRow("Major Width:", self.major_grid_width)
        grid_form.addRow("Minor Width:", self.minor_grid_width)
        
        # Grid spacing
        self.x_major_spacing = create_spin_box(0, 1000, special_value_text="Auto")
        self.x_minor_spacing = create_spin_box(0, 1000, special_value_text="Auto")
        self.y_major_spacing = create_spin_box(0, 1000, special_value_text="Auto")
        self.y_minor_spacing = create_spin_box(0, 1000, special_value_text="Auto")
        
        grid_form.addRow("X Major Spacing:", self.x_major_spacing)
        grid_form.addRow("X Minor Spacing:", self.x_minor_spacing)
        grid_form.addRow("Y Major Spacing:", self.y_major_spacing)
        grid_form.addRow("Y Minor Spacing:", self.y_minor_spacing)
        
        # Grid color
        self.grid_color_button = QPushButton()
        self.grid_color_button.setStyleSheet("background-color: #808080;")
        self.grid_color_button.clicked.connect(self.select_grid_color)
        grid_form.addRow("Grid Color:", self.grid_color_button)
        
        return create_group_box("Grid Settings", grid_form)

    def _create_size_group(self):
        """Create plot size controls group"""
        size_form = create_form_layout()
        
        self.plot_width = create_spin_box(200, 3000, 800, step=50)
        self.plot_width.valueChanged.connect(self.update_styles)
        size_form.addRow("Width (px):", self.plot_width)

        self.plot_height = create_spin_box(200, 3000, 800, step=50)
        self.plot_height.valueChanged.connect(self.update_styles)
        size_form.addRow("Height (px):", self.plot_height)
        
        return create_group_box("Plot Size", size_form)

    def _create_control_buttons(self):
        """Create control buttons"""
        apply_button = QPushButton("Apply Styles")
        # Apply button should apply immediately, bypassing debounce
        apply_button.clicked.connect(self._do_update_styles)

        save_style_button = QPushButton("Save as Default")
        save_style_button.clicked.connect(self.save_style_as_default)

        return create_button_row(apply_button, save_style_button)

    def _connect_update_handlers(self):
        """Connect all the UI controls to the update_styles handler"""
        for grid_checkbox in [self.x_major_grid, self.x_minor_grid, 
                            self.y_major_grid, self.y_minor_grid]:
            grid_checkbox.stateChanged.connect(self.update_styles)
        
        for combo in [self.major_grid_style, self.minor_grid_style]:
            combo.currentIndexChanged.connect(self.update_styles)
        
        for spin in [self.major_grid_alpha, self.minor_grid_alpha,
                    self.major_grid_width, self.minor_grid_width,
                    self.x_major_spacing, self.x_minor_spacing,
                    self.y_major_spacing, self.y_minor_spacing]:
            spin.valueChanged.connect(self.update_styles)

    def select_grid_color(self):
        """Open color dialog for grid color selection"""
        current_color = self.grid_color_button.styleSheet().split(': ')[1].rstrip(';')
        color = QColorDialog.getColor(QColor(current_color), self)
        if color.isValid():
            self.grid_color_button.setStyleSheet(f"background-color: {color.name()}")
            self.update_styles()

    def toggle_auto_scale(self):
        """Handle auto scale checkbox changes"""
        is_auto = self.auto_scale.isChecked()
        self.use_axis_limits.setEnabled(not is_auto)
        if is_auto:
            self.use_axis_limits.setChecked(False)
        self.update_styles()

    def toggle_axis_limits(self):
        """Enable/disable Y1 axis limit spinboxes"""
        enabled = self.use_axis_limits.isChecked()
        self.x_min_spin.setEnabled(enabled)
        self.x_max_spin.setEnabled(enabled)
        self.y_min_spin.setEnabled(enabled)
        self.y_max_spin.setEnabled(enabled)
        self.update_styles()
    
    def toggle_y2_axis_limits(self):
        """Enable/disable Y2 axis limit spinboxes"""
        enabled = self.use_y2_axis_limits.isChecked()
        self.y2_min_spin.setEnabled(enabled)
        self.y2_max_spin.setEnabled(enabled)
        self.update_styles()

    def update_title(self):
        """Update just the plot title"""
        self.plot_window.canvas.set_title(self.title_input.text())

    def update_styles(self):
        """Debounced trigger for style updates"""
        self._debounce_timer.start()  # Restart timer on each change

    def _do_update_styles(self):
        """Actually update all plot styles (called after debounce)"""
        logger.debug("🟡 Updating plot styles...")
        if not hasattr(self.plot_window.canvas, 'plot_style'):
            logger.debug("❌ No plot style found on canvas")
            return
        
        # Convert UI labels to backend codes using GRID_STYLE_REVERSE_MAP
        major_grid_style_text = self.major_grid_style.currentText()
        minor_grid_style_text = self.minor_grid_style.currentText()

        major_grid_style = GRID_STYLE_REVERSE_MAP.get(major_grid_style_text, '--')
        minor_grid_style = GRID_STYLE_REVERSE_MAP.get(minor_grid_style_text, ':')
        
        # Get grid color from the button's style sheet
        grid_color = self.grid_color_button.styleSheet().split(': ')[1].rstrip(';')
        
        style_dict = {
            'title_text': self.title_input.text(),
            'x_axis_title': self.x_axis_title.text(),
            'y_axis_title': self.y_axis_title.text(),
            'y2_axis_title': self.y2_axis_title.text(),
            'x_scale': self.x_scale_type.currentText(),
            'y_scale': self.y_scale_type.currentText(),
            'y2_scale': self.y2_scale_type.currentText(),
            'auto_scale': self.auto_scale.isChecked(),
            'use_axis_limits': self.use_axis_limits.isChecked(),
            'use_y2_axis_limits': self.use_y2_axis_limits.isChecked(),
            'x_min': self.x_min_spin.value(),
            'x_max': self.x_max_spin.value(),
            'y_min': self.y_min_spin.value(),
            'y_max': self.y_max_spin.value(),
            'y2_min': self.y2_min_spin.value(),
            'y2_max': self.y2_max_spin.value(),
            'legend_location': self.legend_location.currentData(),
            'legend_fontfamily': self.legend_font.currentFont().family(),
            'legend_fontsize': self.legend_size.value(),
            'legend_columns': self.legend_columns.value(),
            'axes_fontfamily': self.axes_font.currentFont().family(),
            'axes_fontsize': self.axes_size.value(),
            'title_fontfamily': self.title_font.currentFont().family(),
            'title_fontsize': self.title_size.value(),
            'line_width': self.line_width.value() / 10.0,  # UI: 1-100 -> Style: 0.1-10.0
            'plot_width': self.plot_width.value(),
            'plot_height': self.plot_height.value(),
            # Add grid-related settings
            'x_major_grid': self.x_major_grid.isChecked(),
            'x_minor_grid': self.x_minor_grid.isChecked(),
            'y_major_grid': self.y_major_grid.isChecked(),
            'y_minor_grid': self.y_minor_grid.isChecked(),
            'major_grid_style': major_grid_style,
            'minor_grid_style': minor_grid_style,
            'major_grid_alpha': self.major_grid_alpha.value() / 100.0,  # UI: 0-100% -> Style: 0.0-1.0
            'minor_grid_alpha': self.minor_grid_alpha.value() / 100.0,  # UI: 0-100% -> Style: 0.0-1.0
            'major_grid_width': self.major_grid_width.value() / 10.0,   # UI: 1-50 -> Style: 0.1-5.0
            'minor_grid_width': self.minor_grid_width.value() / 10.0,   # UI: 1-50 -> Style: 0.1-5.0
            'grid_color': grid_color
        }
        
        # Handle grid spacing - convert 0 to None for "Auto" mode
        for spacing_name, spin in [
            ('x_major_spacing', self.x_major_spacing),
            ('x_minor_spacing', self.x_minor_spacing),
            ('y_major_spacing', self.y_major_spacing),
            ('y_minor_spacing', self.y_minor_spacing)
        ]:
            value = spin.value()
            style_dict[spacing_name] = None if value == 0 else value
        
        logger.debug(f"🟡 New style dict: {style_dict}")
        self.plot_window.canvas.set_plot_style(style_dict)
        logger.debug("✅ Plot style updated")

    def _set_initial_values(self):
        """Set initial values from current canvas settings"""
        logger.debug("🟢 Setting initial values in style window...")

        if not hasattr(self.plot_window.canvas, 'plot_style'):
            logger.debug("❌ No plot style found on canvas")
            return

        logger.debug(f"🟡 Current canvas plot style: {self.plot_window.canvas.plot_style}")

        # Temporarily block signals
        logger.debug("🟡 Blocking widget signals...")
        for widget in self.findChildren((QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QCheckBox)):
            widget.blockSignals(True)
        
        try:
            style = self.plot_window.canvas.plot_style

            # Updating title
            logger.debug(f"🟡 Setting title: {style.get('title_text', '')}")
            self.title_input.setText(style.get('title_text', ''))
            
            # Update axis settings
            logger.debug("🟡 Setting axis titles...")
            self.x_axis_title.setText(style.get('x_axis_title', ''))
            self.y_axis_title.setText(style.get('y_axis_title', ''))
            self.y2_axis_title.setText(style.get('y2_axis_title', ''))
            
            logger.debug("🟡 Setting axis scales...")
            self.x_scale_type.setCurrentText(style.get('x_scale', 'linear'))
            self.y_scale_type.setCurrentText(style.get('y_scale', 'linear'))
            self.y2_scale_type.setCurrentText(style.get('y2_scale', 'linear'))

            # Auto scale and limits
            auto_scale = style.get('auto_scale', True)
            use_limits = style.get('use_axis_limits', False)
            use_y2_limits = style.get('use_y2_axis_limits', False)
            
            self.auto_scale.setChecked(auto_scale)
            self.use_axis_limits.setChecked(use_limits)
            self.use_axis_limits.setEnabled(not auto_scale)
            self.use_y2_axis_limits.setChecked(use_y2_limits)
            self.use_y2_axis_limits.setEnabled(not auto_scale)
            
            # Axis limit values - handle None values safely
            x_min = style.get('x_min')
            x_max = style.get('x_max')
            y_min = style.get('y_min')
            y_max = style.get('y_max')
            y2_min = style.get('y2_min')
            y2_max = style.get('y2_max')
            
            # Use 0 as default if None is encountered
            self.x_min_spin.setValue(0 if x_min is None else x_min)
            self.x_max_spin.setValue(100 if x_max is None else x_max)
            self.y_min_spin.setValue(0 if y_min is None else y_min)
            self.y_max_spin.setValue(100 if y_max is None else y_max)
            self.y2_min_spin.setValue(0 if y2_min is None else y2_min)
            self.y2_max_spin.setValue(100 if y2_max is None else y2_max)
            
            self.x_min_spin.setEnabled(use_limits and not auto_scale)
            self.x_max_spin.setEnabled(use_limits and not auto_scale)
            self.y_min_spin.setEnabled(use_limits and not auto_scale)
            self.y_max_spin.setEnabled(use_limits and not auto_scale)
            self.y2_min_spin.setEnabled(use_y2_limits and not auto_scale)
            self.y2_max_spin.setEnabled(use_y2_limits and not auto_scale)
            
            # Grid settings
            self.x_major_grid.setChecked(style.get('x_major_grid', True))
            self.x_minor_grid.setChecked(style.get('x_minor_grid', False))
            self.y_major_grid.setChecked(style.get('y_major_grid', True))
            self.y_minor_grid.setChecked(style.get('y_minor_grid', False))
            
            # Grid styles (use GRID_STYLE_MAP from plot_dialog_components)
            major_style = style.get('major_grid_style', '--')
            minor_style = style.get('minor_grid_style', ':')

            self.major_grid_style.setCurrentText(GRID_STYLE_MAP.get(major_style, 'Dashed --'))
            self.minor_grid_style.setCurrentText(GRID_STYLE_MAP.get(minor_style, 'Dotted :'))
            
            # Grid properties
            self.major_grid_alpha.setValue(style.get('major_grid_alpha', 0.5) * 100)
            self.minor_grid_alpha.setValue(style.get('minor_grid_alpha', 0.2) * 100)
            self.major_grid_width.setValue(style.get('major_grid_width', 0.5) * 10)
            self.minor_grid_width.setValue(style.get('minor_grid_width', 0.5) * 10)
            
            # Grid spacing - handle None values
            x_major_spacing = style.get('x_major_spacing')
            x_minor_spacing = style.get('x_minor_spacing')
            y_major_spacing = style.get('y_major_spacing')
            y_minor_spacing = style.get('y_minor_spacing')
            
            self.x_major_spacing.setValue(0 if x_major_spacing is None else x_major_spacing)
            self.x_minor_spacing.setValue(0 if x_minor_spacing is None else x_minor_spacing)
            self.y_major_spacing.setValue(0 if y_major_spacing is None else y_major_spacing)
            self.y_minor_spacing.setValue(0 if y_minor_spacing is None else y_minor_spacing)
            
            # Grid color
            grid_color = style.get('grid_color', '#808080')
            self.grid_color_button.setStyleSheet(f"background-color: {grid_color};")
            
            # Legend settings
            legend_loc = style.get('legend_location', 'best')
            for i in range(self.legend_location.count()):
                if self.legend_location.itemData(i) == legend_loc:
                    self.legend_location.setCurrentIndex(i)
                    break
                    
            self.legend_columns.setValue(style.get('legend_columns', 1))
            
            # Font settings
            legend_font = QFont(style.get('legend_fontfamily', 'sans-serif'))
            axes_font = QFont(style.get('axes_fontfamily', 'sans-serif'))
            title_font = QFont(style.get('title_fontfamily', 'sans-serif'))
            
            self.legend_font.setCurrentFont(legend_font)
            self.legend_size.setValue(style.get('legend_fontsize', 10))
            
            self.axes_font.setCurrentFont(axes_font)
            self.axes_size.setValue(style.get('axes_fontsize', 10))
            
            self.title_font.setCurrentFont(title_font)
            self.title_size.setValue(style.get('title_fontsize', 12))
            
            # Line settings
            self.line_width.setValue(style.get('line_width', 0.1) * 10)
            
            # Plot size
            self.plot_width.setValue(style.get('plot_width', 800))
            self.plot_height.setValue(style.get('plot_height', 800))
            
        finally:
            # Unblock signals
            logger.debug("🟡 Unblocking widget signals...")
            for widget in self.findChildren((QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QCheckBox)):
                widget.blockSignals(False)

        logger.debug("✅ Finished setting initial values")

        # Force an update to the plot (bypass debounce for initialization)
        logger.debug("🟡 Updating plot styles...")
        self._do_update_styles()

    def save_style_as_default(self):
        """Save current style settings as default"""
        self._do_update_styles()  # Ensure current settings are applied (bypass debounce)
        style_dict = self.plot_window.canvas.plot_style.copy()
        
        try:
            home_dir = os.path.expanduser("~")
            settings_dir = os.path.join(home_dir, '.csv_plotter_settings')
            if not os.path.exists(settings_dir):
                os.makedirs(settings_dir)
                
            settings_file = os.path.join(settings_dir, 'plot_style_settings.json')
            with open(settings_file, 'w') as f:
                json.dump(style_dict, f, indent=2)
                
            QMessageBox.information(self, "Success", "Plot style settings saved as default")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save style settings: {str(e)}")