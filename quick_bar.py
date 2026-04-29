"""Quick Style Dialog - Dialog horizontal d'édition rapide du graphique

Invoqué par Q, affiche toutes les options d'un coup d'œil.
QDialog utilisant les mêmes composants que PlotStyleWindow.
"""

from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QFrame, QSizePolicy, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QLineEdit, QFontComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

# Réutiliser les composants et constantes de plot_dialog_components
from plot_dialog_components import (
    create_spin_box, create_combo_box, create_checkbox, create_line_edit,
    create_font_combo_box,
    GRID_STYLE_MAP, GRID_STYLE_REVERSE_MAP, LEGEND_LOCATIONS, SCALE_TYPES
)

# Debounce delay pour live update (même valeur que PlotStyleWindow)
DEBOUNCE_MS = 200


class QuickStyleDialog(QDialog):
    """Dialog horizontal avec toutes les options visibles

    Même pattern que PlotStyleWindow mais layout horizontal.
    """

    def __init__(self, plot_window):
        super().__init__(plot_window)
        self.plot_window = plot_window
        self.canvas = plot_window.canvas

        self.setWindowTitle("Quick Style")
        self.setMinimumWidth(1000)

        # Debounce timer (même pattern que PlotStyleWindow)
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._do_update_styles)

        self._build_ui()
        self._connect_signals()
        self._sync_from_canvas()

        print("🟢 QuickStyleDialog créé")

    def _build_ui(self):
        """Construire l'interface - tout visible horizontalement"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # Ligne 1 : Title + Axes Titles
        row1 = QHBoxLayout()
        row1.addWidget(self._create_title_section())
        row1.addWidget(self._create_axes_titles_section())
        row1.addStretch()
        main_layout.addLayout(row1)

        # Ligne 2 : Grid + Legend
        row2 = QHBoxLayout()
        row2.addWidget(self._create_grid_section())
        row2.addWidget(self._create_legend_section())
        row2.addStretch()
        main_layout.addLayout(row2)

        # Ligne 3 : Lines + Axes Scale + Size
        row3 = QHBoxLayout()
        row3.addWidget(self._create_lines_section())
        row3.addWidget(self._create_axes_scale_section())
        row3.addWidget(self._create_size_section())
        row3.addStretch()
        main_layout.addLayout(row3)

        # Ligne 4 : Axis Limits (optionnel)
        row4 = QHBoxLayout()
        row4.addWidget(self._create_limits_section())
        row4.addStretch()
        main_layout.addLayout(row4)

        # Ligne 5 : Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        main_layout.addLayout(btn_layout)

    def _create_section_frame(self, title):
        """Créer un frame de section avec titre"""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(4)

        # Titre
        title_label = QLabel(f"<b>{title}</b>")
        layout.addWidget(title_label)

        # Container pour les options
        options_layout = QHBoxLayout()
        options_layout.setSpacing(8)
        layout.addLayout(options_layout)

        return frame, options_layout

    def _create_title_section(self):
        """Section Title"""
        frame, layout = self._create_section_frame("Title")

        # Texte du titre
        self.title_input = create_line_edit()
        self.title_input.setMinimumWidth(150)
        self.title_input.setPlaceholderText("Titre du graphique")
        layout.addWidget(self.title_input)

        # Separator
        layout.addWidget(self._vsep())

        # Police
        layout.addWidget(QLabel("Police:"))
        self.title_font = create_font_combo_box()
        self.title_font.setMaximumWidth(120)
        layout.addWidget(self.title_font)

        # Taille
        layout.addWidget(QLabel("Taille:"))
        self.title_size = create_spin_box(8, 30, 12)
        layout.addWidget(self.title_size)

        return frame

    def _create_axes_titles_section(self):
        """Section Axes Titles"""
        frame, layout = self._create_section_frame("Axes Titles")

        # X axis title
        layout.addWidget(QLabel("X:"))
        self.x_axis_title = create_line_edit()
        self.x_axis_title.setMinimumWidth(100)
        layout.addWidget(self.x_axis_title)

        # Y axis title
        layout.addWidget(QLabel("Y:"))
        self.y_axis_title = create_line_edit()
        self.y_axis_title.setMinimumWidth(100)
        layout.addWidget(self.y_axis_title)

        # Y2 axis title
        layout.addWidget(QLabel("Y2:"))
        self.y2_axis_title = create_line_edit()
        self.y2_axis_title.setMinimumWidth(100)
        layout.addWidget(self.y2_axis_title)

        return frame

    def _create_grid_section(self):
        """Section Grid"""
        frame, layout = self._create_section_frame("Grid")

        # Checkboxes
        self.x_major_grid = create_checkbox("X Maj", True)
        layout.addWidget(self.x_major_grid)

        self.y_major_grid = create_checkbox("Y Maj", True)
        layout.addWidget(self.y_major_grid)

        self.x_minor_grid = create_checkbox("X Min")
        layout.addWidget(self.x_minor_grid)

        self.y_minor_grid = create_checkbox("Y Min")
        layout.addWidget(self.y_minor_grid)

        # Separator
        layout.addWidget(self._vsep())

        # Style
        layout.addWidget(QLabel("Style:"))
        self.major_grid_style = create_combo_box(list(GRID_STYLE_MAP.values()))
        layout.addWidget(self.major_grid_style)

        # Alpha
        layout.addWidget(QLabel("α:"))
        self.major_grid_alpha = create_spin_box(0, 100, 50)
        self.major_grid_alpha.setSuffix("%")
        layout.addWidget(self.major_grid_alpha)

        return frame

    def _create_legend_section(self):
        """Section Legend"""
        frame, layout = self._create_section_frame("Legend")

        # Position
        layout.addWidget(QLabel("Pos:"))
        self.legend_location = create_combo_box()
        for name, value in LEGEND_LOCATIONS:
            self.legend_location.addItem(name, value)
        layout.addWidget(self.legend_location)

        # Taille
        layout.addWidget(QLabel("Taille:"))
        self.legend_size = create_spin_box(6, 24, 10)
        layout.addWidget(self.legend_size)

        # Colonnes
        layout.addWidget(QLabel("Cols:"))
        self.legend_columns = create_spin_box(1, 10, 1)
        layout.addWidget(self.legend_columns)

        return frame

    def _create_lines_section(self):
        """Section Lines"""
        frame, layout = self._create_section_frame("Lines")

        layout.addWidget(QLabel("Épaisseur:"))
        self.line_width = create_spin_box(1, 100, 10, step=1, decimals=1)
        layout.addWidget(self.line_width)

        return frame

    def _create_axes_scale_section(self):
        """Section Axes Scale"""
        frame, layout = self._create_section_frame("Scale")

        # Scale X
        layout.addWidget(QLabel("X:"))
        self.x_scale_type = create_combo_box(SCALE_TYPES)
        layout.addWidget(self.x_scale_type)

        # Scale Y
        layout.addWidget(QLabel("Y:"))
        self.y_scale_type = create_combo_box(SCALE_TYPES)
        layout.addWidget(self.y_scale_type)

        # Scale Y2
        layout.addWidget(QLabel("Y2:"))
        self.y2_scale_type = create_combo_box(SCALE_TYPES)
        layout.addWidget(self.y2_scale_type)

        return frame

    def _create_size_section(self):
        """Section Size"""
        frame, layout = self._create_section_frame("Size")

        layout.addWidget(QLabel("W:"))
        self.plot_width = create_spin_box(200, 3000, 800, step=50)
        layout.addWidget(self.plot_width)

        layout.addWidget(QLabel("H:"))
        self.plot_height = create_spin_box(200, 3000, 800, step=50)
        layout.addWidget(self.plot_height)

        return frame

    def _create_limits_section(self):
        """Section Axis Limits"""
        frame, layout = self._create_section_frame("Axis Limits")

        # Auto scale checkbox
        self.auto_scale = create_checkbox("Auto", True)
        self.auto_scale.stateChanged.connect(self._toggle_limits_enabled)
        layout.addWidget(self.auto_scale)

        layout.addWidget(self._vsep())

        # X limits
        layout.addWidget(QLabel("X:"))
        self.x_min_spin = create_spin_box(-1e9, 1e9, 0, decimals=2)
        self.x_min_spin.setMaximumWidth(80)
        layout.addWidget(self.x_min_spin)
        layout.addWidget(QLabel("→"))
        self.x_max_spin = create_spin_box(-1e9, 1e9, 100, decimals=2)
        self.x_max_spin.setMaximumWidth(80)
        layout.addWidget(self.x_max_spin)

        layout.addWidget(self._vsep())

        # Y limits
        layout.addWidget(QLabel("Y:"))
        self.y_min_spin = create_spin_box(-1e9, 1e9, 0, decimals=2)
        self.y_min_spin.setMaximumWidth(80)
        layout.addWidget(self.y_min_spin)
        layout.addWidget(QLabel("→"))
        self.y_max_spin = create_spin_box(-1e9, 1e9, 100, decimals=2)
        self.y_max_spin.setMaximumWidth(80)
        layout.addWidget(self.y_max_spin)

        layout.addWidget(self._vsep())

        # Y2 limits
        layout.addWidget(QLabel("Y2:"))
        self.y2_min_spin = create_spin_box(-1e9, 1e9, 0, decimals=2)
        self.y2_min_spin.setMaximumWidth(80)
        layout.addWidget(self.y2_min_spin)
        layout.addWidget(QLabel("→"))
        self.y2_max_spin = create_spin_box(-1e9, 1e9, 100, decimals=2)
        self.y2_max_spin.setMaximumWidth(80)
        layout.addWidget(self.y2_max_spin)

        return frame

    def _vsep(self):
        """Créer un séparateur vertical"""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        return sep

    def _toggle_limits_enabled(self):
        """Activer/désactiver les spinbox de limites selon Auto"""
        enabled = not self.auto_scale.isChecked()
        for spin in [self.x_min_spin, self.x_max_spin,
                     self.y_min_spin, self.y_max_spin,
                     self.y2_min_spin, self.y2_max_spin]:
            spin.setEnabled(enabled)
        self._schedule_update()

    def _connect_signals(self):
        """Connecter tous les signaux au debounce"""
        # Title
        self.title_input.textChanged.connect(self._schedule_update)
        self.title_font.currentFontChanged.connect(self._schedule_update)
        self.title_size.valueChanged.connect(self._schedule_update)

        # Axes titles
        self.x_axis_title.textChanged.connect(self._schedule_update)
        self.y_axis_title.textChanged.connect(self._schedule_update)
        self.y2_axis_title.textChanged.connect(self._schedule_update)

        # Grid
        self.x_major_grid.stateChanged.connect(self._schedule_update)
        self.y_major_grid.stateChanged.connect(self._schedule_update)
        self.x_minor_grid.stateChanged.connect(self._schedule_update)
        self.y_minor_grid.stateChanged.connect(self._schedule_update)
        self.major_grid_style.currentIndexChanged.connect(self._schedule_update)
        self.major_grid_alpha.valueChanged.connect(self._schedule_update)

        # Legend
        self.legend_location.currentIndexChanged.connect(self._schedule_update)
        self.legend_size.valueChanged.connect(self._schedule_update)
        self.legend_columns.valueChanged.connect(self._schedule_update)

        # Lines
        self.line_width.valueChanged.connect(self._schedule_update)

        # Axes scale
        self.x_scale_type.currentTextChanged.connect(self._schedule_update)
        self.y_scale_type.currentTextChanged.connect(self._schedule_update)
        self.y2_scale_type.currentTextChanged.connect(self._schedule_update)

        # Size
        self.plot_width.valueChanged.connect(self._schedule_update)
        self.plot_height.valueChanged.connect(self._schedule_update)

        # Limits
        self.x_min_spin.valueChanged.connect(self._schedule_update)
        self.x_max_spin.valueChanged.connect(self._schedule_update)
        self.y_min_spin.valueChanged.connect(self._schedule_update)
        self.y_max_spin.valueChanged.connect(self._schedule_update)
        self.y2_min_spin.valueChanged.connect(self._schedule_update)
        self.y2_max_spin.valueChanged.connect(self._schedule_update)

    def _sync_from_canvas(self):
        """Synchroniser depuis le canvas (même logique que PlotStyleWindow)"""
        if not hasattr(self.canvas, 'plot_style'):
            return

        style = self.canvas.plot_style

        # Block signals
        for widget in self.findChildren((QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QLineEdit, QFontComboBox)):
            widget.blockSignals(True)

        try:
            # Title
            self.title_input.setText(style.get('title_text', ''))
            title_font = QFont(style.get('title_fontfamily', 'sans-serif'))
            self.title_font.setCurrentFont(title_font)
            self.title_size.setValue(style.get('title_fontsize', 12))

            # Axes titles
            self.x_axis_title.setText(style.get('x_axis_title', ''))
            self.y_axis_title.setText(style.get('y_axis_title', ''))
            self.y2_axis_title.setText(style.get('y2_axis_title', ''))

            # Grid
            self.x_major_grid.setChecked(style.get('x_major_grid', True))
            self.y_major_grid.setChecked(style.get('y_major_grid', True))
            self.x_minor_grid.setChecked(style.get('x_minor_grid', False))
            self.y_minor_grid.setChecked(style.get('y_minor_grid', False))

            major_style = style.get('major_grid_style', '--')
            self.major_grid_style.setCurrentText(GRID_STYLE_MAP.get(major_style, 'Dashed --'))
            self.major_grid_alpha.setValue(int(style.get('major_grid_alpha', 0.5) * 100))

            # Legend
            legend_loc = style.get('legend_location', 'best')
            for i in range(self.legend_location.count()):
                if self.legend_location.itemData(i) == legend_loc:
                    self.legend_location.setCurrentIndex(i)
                    break
            self.legend_size.setValue(style.get('legend_fontsize', 10))
            self.legend_columns.setValue(style.get('legend_columns', 1))

            # Lines
            self.line_width.setValue(int(style.get('line_width', 1.0) * 10))

            # Axes scale
            self.x_scale_type.setCurrentText(style.get('x_scale', 'linear'))
            self.y_scale_type.setCurrentText(style.get('y_scale', 'linear'))
            self.y2_scale_type.setCurrentText(style.get('y2_scale', 'linear'))

            # Size
            self.plot_width.setValue(style.get('plot_width', 800))
            self.plot_height.setValue(style.get('plot_height', 800))

            # Limits
            self.auto_scale.setChecked(style.get('auto_scale', True))

            x_min = style.get('x_min')
            x_max = style.get('x_max')
            y_min = style.get('y_min')
            y_max = style.get('y_max')
            y2_min = style.get('y2_min')
            y2_max = style.get('y2_max')

            self.x_min_spin.setValue(0 if x_min is None else x_min)
            self.x_max_spin.setValue(100 if x_max is None else x_max)
            self.y_min_spin.setValue(0 if y_min is None else y_min)
            self.y_max_spin.setValue(100 if y_max is None else y_max)
            self.y2_min_spin.setValue(0 if y2_min is None else y2_min)
            self.y2_max_spin.setValue(100 if y2_max is None else y2_max)

            # Enable/disable limits
            self._toggle_limits_enabled()

        finally:
            for widget in self.findChildren((QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QLineEdit, QFontComboBox)):
                widget.blockSignals(False)

    def _schedule_update(self):
        """Debounce trigger"""
        self._debounce_timer.start()

    def _do_update_styles(self):
        """Appliquer au canvas (mêmes conversions que PlotStyleWindow)"""
        if not hasattr(self.canvas, 'plot_style'):
            return

        style = self.canvas.plot_style.copy()

        # Title
        style['title_text'] = self.title_input.text()
        style['title_fontfamily'] = self.title_font.currentFont().family()
        style['title_fontsize'] = self.title_size.value()

        # Axes titles
        style['x_axis_title'] = self.x_axis_title.text()
        style['y_axis_title'] = self.y_axis_title.text()
        style['y2_axis_title'] = self.y2_axis_title.text()

        # Grid
        style['x_major_grid'] = self.x_major_grid.isChecked()
        style['y_major_grid'] = self.y_major_grid.isChecked()
        style['x_minor_grid'] = self.x_minor_grid.isChecked()
        style['y_minor_grid'] = self.y_minor_grid.isChecked()
        style['major_grid_style'] = GRID_STYLE_REVERSE_MAP.get(
            self.major_grid_style.currentText(), '--')
        style['major_grid_alpha'] = self.major_grid_alpha.value() / 100.0

        # Legend
        style['legend_location'] = self.legend_location.currentData()
        style['legend_fontsize'] = self.legend_size.value()
        style['legend_columns'] = self.legend_columns.value()

        # Lines
        style['line_width'] = self.line_width.value() / 10.0

        # Axes scale
        style['x_scale'] = self.x_scale_type.currentText()
        style['y_scale'] = self.y_scale_type.currentText()
        style['y2_scale'] = self.y2_scale_type.currentText()

        # Size
        style['plot_width'] = self.plot_width.value()
        style['plot_height'] = self.plot_height.value()

        # Limits
        style['auto_scale'] = self.auto_scale.isChecked()
        if not self.auto_scale.isChecked():
            style['use_axis_limits'] = True
            style['x_min'] = self.x_min_spin.value()
            style['x_max'] = self.x_max_spin.value()
            style['y_min'] = self.y_min_spin.value()
            style['y_max'] = self.y_max_spin.value()
            style['use_y2_axis_limits'] = True
            style['y2_min'] = self.y2_min_spin.value()
            style['y2_max'] = self.y2_max_spin.value()
        else:
            style['use_axis_limits'] = False
            style['use_y2_axis_limits'] = False

        self.canvas.set_plot_style(style)
        print("✅ QuickStyleDialog: styles appliqués")

    def showEvent(self, event):
        """Sync à l'ouverture"""
        super().showEvent(event)
        self._sync_from_canvas()

    def keyPressEvent(self, event):
        """Fermer avec Échap"""
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


def show_quick_bar(canvas, plot_window):
    """Ouvrir le QuickStyleDialog"""
    # Réutiliser le dialog existant s'il existe
    if hasattr(plot_window, '_quick_style_dialog') and plot_window._quick_style_dialog is not None:
        try:
            plot_window._quick_style_dialog._sync_from_canvas()
            plot_window._quick_style_dialog.show()
            plot_window._quick_style_dialog.raise_()
            plot_window._quick_style_dialog.activateWindow()
            return plot_window._quick_style_dialog
        except:
            pass

    dialog = QuickStyleDialog(plot_window)
    plot_window._quick_style_dialog = dialog

    dialog.show()
    print("🟢 QuickStyleDialog ouvert")
    return dialog
