"""Interactive plot element editing via right-click with picker events"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                           QLineEdit, QSpinBox, QComboBox, QLabel, QFormLayout,
                           QFontComboBox, QColorDialog, QCheckBox, QDoubleSpinBox,
                           QTabWidget, QWidget)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt, QPoint, QTimer
from plot_dialog_components import SCALE_TYPES, LEGEND_LOCATIONS, GRID_STYLE_MAP

# Debounce delay in milliseconds for live updates
DEBOUNCE_DELAY_MS = 200

# Dictionnaire pour stocker les fenêtres ouvertes (éviter doublons)
_open_windows = {
    'title': None,
    'axes_grid': None,
    'lines_legend': None
}


class TitleEditDialog(QWidget):
    """Fenêtre non-modale pour éditer le titre du graphique avec live update"""
    def __init__(self, parent, canvas):
        super().__init__(parent)
        self.canvas = canvas
        self.setWindowTitle("Éditer le titre")
        self.setWindowFlags(Qt.Window)  # Fenêtre indépendante non-modale

        # Debounce timer for live updates
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(DEBOUNCE_DELAY_MS)
        self._debounce_timer.timeout.connect(self._do_apply_live_update)

        layout = QFormLayout(self)

        # Texte du titre
        self.title_input = QLineEdit()
        self.title_input.setText(canvas.plot_style.get('title_text', ''))
        self.title_input.textChanged.connect(self._apply_live_update)
        layout.addRow("Titre:", self.title_input)

        # Police
        self.font_combo = QFontComboBox()
        font = QFont(canvas.plot_style.get('title_fontfamily', 'sans-serif'))
        self.font_combo.setCurrentFont(font)
        self.font_combo.currentFontChanged.connect(self._apply_live_update)
        layout.addRow("Police:", self.font_combo)

        # Taille
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 30)
        self.size_spin.setValue(canvas.plot_style.get('title_fontsize', 12))
        self.size_spin.valueChanged.connect(self._apply_live_update)
        layout.addRow("Taille:", self.size_spin)

        # Bouton Fermer
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addRow(btn_layout)

    def _apply_live_update(self):
        """Debounced trigger for live update"""
        self._debounce_timer.start()  # Restart timer on each change

    def _do_apply_live_update(self):
        """Applique les modifications en temps réel au plot"""
        style = self.canvas.plot_style.copy()
        style.update({
            'title_text': self.title_input.text(),
            'title_fontfamily': self.font_combo.currentFont().family(),
            'title_fontsize': self.size_spin.value()
        })
        self.canvas.set_plot_style(style)

    def keyPressEvent(self, event):
        """Fermer la fenêtre si Enter/Return est pressé"""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.close()
        else:
            super().keyPressEvent(event)


class AxesAndGridEditDialog(QWidget):
    """Fenêtre non-modale pour éditer axes ET grilles avec live update"""
    def __init__(self, parent, canvas):
        super().__init__(parent)
        self.canvas = canvas
        self.setWindowTitle("Éditer axes et grilles")
        self.setWindowFlags(Qt.Window)  # Fenêtre indépendante non-modale
        self.setMinimumWidth(400)

        # Debounce timer for live updates
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(DEBOUNCE_DELAY_MS)
        self._debounce_timer.timeout.connect(self._do_apply_live_update)

        # Layout principal
        main_layout = QVBoxLayout(self)

        # Onglets
        tabs = QTabWidget()

        # Onglet Axes
        axes_widget = self._create_axes_tab()
        tabs.addTab(axes_widget, "Axes")

        # Onglet Grilles
        grid_widget = self._create_grid_tab()
        tabs.addTab(grid_widget, "Grilles")

        main_layout.addWidget(tabs)

        # Bouton Fermer
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)

    def _create_axes_tab(self):
        """Créer l'onglet des axes X/Y/Y2"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Axe X
        layout.addRow(QLabel("<b>Axe X</b>"))
        self.x_title = QLineEdit(self.canvas.plot_style.get('x_axis_title', ''))
        self.x_title.textChanged.connect(self._apply_live_update)
        layout.addRow("Titre X:", self.x_title)

        self.x_scale = QComboBox()
        self.x_scale.addItems(SCALE_TYPES)
        self.x_scale.setCurrentText(self.canvas.plot_style.get('x_scale', 'linear'))
        self.x_scale.currentTextChanged.connect(self._apply_live_update)
        layout.addRow("Échelle X:", self.x_scale)

        self.x_use_limits = QCheckBox("Limites personnalisées X")
        self.x_use_limits.setChecked(self.canvas.plot_style.get('use_axis_limits', False))
        self.x_use_limits.stateChanged.connect(self._apply_live_update)
        layout.addRow(self.x_use_limits)

        self.x_min = QDoubleSpinBox()
        self.x_min.setRange(-1e9, 1e9)
        self.x_min.setDecimals(3)
        self.x_min.setValue(self.canvas.plot_style.get('x_min', 0))
        self.x_min.setEnabled(self.x_use_limits.isChecked())
        self.x_min.valueChanged.connect(self._apply_live_update)
        layout.addRow("X Min:", self.x_min)

        self.x_max = QDoubleSpinBox()
        self.x_max.setRange(-1e9, 1e9)
        self.x_max.setDecimals(3)
        self.x_max.setValue(self.canvas.plot_style.get('x_max', 100))
        self.x_max.setEnabled(self.x_use_limits.isChecked())
        self.x_max.valueChanged.connect(self._apply_live_update)
        layout.addRow("X Max:", self.x_max)

        self.x_use_limits.stateChanged.connect(lambda: self.x_min.setEnabled(self.x_use_limits.isChecked()))
        self.x_use_limits.stateChanged.connect(lambda: self.x_max.setEnabled(self.x_use_limits.isChecked()))

        # Axe Y
        layout.addRow(QLabel(""))
        layout.addRow(QLabel("<b>Axe Y</b>"))
        self.y_title = QLineEdit(self.canvas.plot_style.get('y_axis_title', ''))
        self.y_title.textChanged.connect(self._apply_live_update)
        layout.addRow("Titre Y:", self.y_title)

        self.y_scale = QComboBox()
        self.y_scale.addItems(SCALE_TYPES)
        self.y_scale.setCurrentText(self.canvas.plot_style.get('y_scale', 'linear'))
        self.y_scale.currentTextChanged.connect(self._apply_live_update)
        layout.addRow("Échelle Y:", self.y_scale)

        self.y_min = QDoubleSpinBox()
        self.y_min.setRange(-1e9, 1e9)
        self.y_min.setDecimals(3)
        self.y_min.setValue(self.canvas.plot_style.get('y_min', 0))
        self.y_min.setEnabled(self.x_use_limits.isChecked())
        self.y_min.valueChanged.connect(self._apply_live_update)
        layout.addRow("Y Min:", self.y_min)

        self.y_max = QDoubleSpinBox()
        self.y_max.setRange(-1e9, 1e9)
        self.y_max.setDecimals(3)
        self.y_max.setValue(self.canvas.plot_style.get('y_max', 100))
        self.y_max.setEnabled(self.x_use_limits.isChecked())
        self.y_max.valueChanged.connect(self._apply_live_update)
        layout.addRow("Y Max:", self.y_max)

        # Axe Y2 (si existe)
        if hasattr(self.canvas, 'ax2') and self.canvas.ax2 is not None:
            layout.addRow(QLabel(""))
            layout.addRow(QLabel("<b>Axe Y2</b>"))
            self.y2_title = QLineEdit(self.canvas.plot_style.get('y2_axis_title', ''))
            self.y2_title.textChanged.connect(self._apply_live_update)
            layout.addRow("Titre Y2:", self.y2_title)

            self.y2_scale = QComboBox()
            self.y2_scale.addItems(SCALE_TYPES)
            self.y2_scale.setCurrentText(self.canvas.plot_style.get('y2_scale', 'linear'))
            self.y2_scale.currentTextChanged.connect(self._apply_live_update)
            layout.addRow("Échelle Y2:", self.y2_scale)

            self.y2_use_limits = QCheckBox("Limites personnalisées Y2")
            self.y2_use_limits.setChecked(self.canvas.plot_style.get('use_y2_axis_limits', False))
            self.y2_use_limits.stateChanged.connect(self._apply_live_update)
            layout.addRow(self.y2_use_limits)

            self.y2_min = QDoubleSpinBox()
            self.y2_min.setRange(-1e9, 1e9)
            self.y2_min.setDecimals(3)
            self.y2_min.setValue(self.canvas.plot_style.get('y2_min', 0))
            self.y2_min.setEnabled(self.y2_use_limits.isChecked())
            self.y2_min.valueChanged.connect(self._apply_live_update)
            layout.addRow("Y2 Min:", self.y2_min)

            self.y2_max = QDoubleSpinBox()
            self.y2_max.setRange(-1e9, 1e9)
            self.y2_max.setDecimals(3)
            self.y2_max.setValue(self.canvas.plot_style.get('y2_max', 100))
            self.y2_max.setEnabled(self.y2_use_limits.isChecked())
            self.y2_max.valueChanged.connect(self._apply_live_update)
            layout.addRow("Y2 Max:", self.y2_max)

            self.y2_use_limits.stateChanged.connect(lambda: self.y2_min.setEnabled(self.y2_use_limits.isChecked()))
            self.y2_use_limits.stateChanged.connect(lambda: self.y2_max.setEnabled(self.y2_use_limits.isChecked()))
        else:
            self.y2_title = None

        return widget

    def _create_grid_tab(self):
        """Créer l'onglet des grilles"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Grilles X
        self.x_major_grid = QCheckBox("Grille majeure X")
        self.x_major_grid.setChecked(self.canvas.plot_style.get('x_major_grid', True))
        self.x_major_grid.stateChanged.connect(self._apply_live_update)
        layout.addRow(self.x_major_grid)

        self.x_minor_grid = QCheckBox("Grille mineure X")
        self.x_minor_grid.setChecked(self.canvas.plot_style.get('x_minor_grid', False))
        self.x_minor_grid.stateChanged.connect(self._apply_live_update)
        layout.addRow(self.x_minor_grid)

        # Grilles Y
        self.y_major_grid = QCheckBox("Grille majeure Y")
        self.y_major_grid.setChecked(self.canvas.plot_style.get('y_major_grid', True))
        self.y_major_grid.stateChanged.connect(self._apply_live_update)
        layout.addRow(self.y_major_grid)

        self.y_minor_grid = QCheckBox("Grille mineure Y")
        self.y_minor_grid.setChecked(self.canvas.plot_style.get('y_minor_grid', False))
        self.y_minor_grid.stateChanged.connect(self._apply_live_update)
        layout.addRow(self.y_minor_grid)

        # Style grille majeure
        self.major_style = QComboBox()
        self.major_style.addItems(list(GRID_STYLE_MAP.values()))
        major_style = self.canvas.plot_style.get('major_grid_style', '--')
        grid_style_map = {'-': 'Solid -', '--': 'Dashed --', '-.': 'Dash-dot -.', ':': 'Dotted :'}
        self.major_style.setCurrentText(grid_style_map.get(major_style, 'Dashed --'))
        self.major_style.currentTextChanged.connect(self._apply_live_update)
        layout.addRow("Style majeure:", self.major_style)

        # Style grille mineure
        self.minor_style = QComboBox()
        self.minor_style.addItems(list(GRID_STYLE_MAP.values()))
        minor_style = self.canvas.plot_style.get('minor_grid_style', ':')
        self.minor_style.setCurrentText(grid_style_map.get(minor_style, 'Dotted :'))
        self.minor_style.currentTextChanged.connect(self._apply_live_update)
        layout.addRow("Style mineure:", self.minor_style)

        # Opacités
        self.major_alpha = QSpinBox()
        self.major_alpha.setRange(0, 100)
        self.major_alpha.setValue(int(self.canvas.plot_style.get('major_grid_alpha', 0.5) * 100))
        self.major_alpha.setSuffix(" %")
        self.major_alpha.valueChanged.connect(self._apply_live_update)
        layout.addRow("Opacité majeure:", self.major_alpha)

        self.minor_alpha = QSpinBox()
        self.minor_alpha.setRange(0, 100)
        self.minor_alpha.setValue(int(self.canvas.plot_style.get('minor_grid_alpha', 0.2) * 100))
        self.minor_alpha.setSuffix(" %")
        self.minor_alpha.valueChanged.connect(self._apply_live_update)
        layout.addRow("Opacité mineure:", self.minor_alpha)

        return widget

    def _apply_live_update(self):
        """Debounced trigger for live update"""
        self._debounce_timer.start()  # Restart timer on each change

    def _do_apply_live_update(self):
        """Applique les modifications en temps réel au plot"""
        grid_style_map_inv = {'Solid -': '-', 'Dashed --': '--', 'Dash-dot -.': '-.', 'Dotted :': ':'}

        style = self.canvas.plot_style.copy()
        style.update({
            # Axes
            'x_axis_title': self.x_title.text(),
            'x_scale': self.x_scale.currentText(),
            'use_axis_limits': self.x_use_limits.isChecked(),
            'x_min': self.x_min.value(),
            'x_max': self.x_max.value(),
            'y_axis_title': self.y_title.text(),
            'y_scale': self.y_scale.currentText(),
            'y_min': self.y_min.value(),
            'y_max': self.y_max.value(),
            # Grilles
            'x_major_grid': self.x_major_grid.isChecked(),
            'x_minor_grid': self.x_minor_grid.isChecked(),
            'y_major_grid': self.y_major_grid.isChecked(),
            'y_minor_grid': self.y_minor_grid.isChecked(),
            'major_grid_style': grid_style_map_inv.get(self.major_style.currentText(), '--'),
            'minor_grid_style': grid_style_map_inv.get(self.minor_style.currentText(), ':'),
            'major_grid_alpha': self.major_alpha.value() / 100.0,
            'minor_grid_alpha': self.minor_alpha.value() / 100.0,
        })

        # Y2 si existe
        if self.y2_title is not None:
            style.update({
                'y2_axis_title': self.y2_title.text(),
                'y2_scale': self.y2_scale.currentText(),
                'use_y2_axis_limits': self.y2_use_limits.isChecked(),
                'y2_min': self.y2_min.value(),
                'y2_max': self.y2_max.value(),
            })

        self.canvas.set_plot_style(style)

    def keyPressEvent(self, event):
        """Fermer la fenêtre si Enter/Return est pressé"""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.close()
        else:
            super().keyPressEvent(event)


class LinesAndLegendEditDialog(QWidget):
    """Fenêtre non-modale pour éditer courbes ET légende avec live update"""
    def __init__(self, parent, canvas):
        super().__init__(parent)
        self.canvas = canvas
        self.setWindowTitle("Éditer courbes et légende")
        self.setWindowFlags(Qt.Window)  # Fenêtre indépendante non-modale
        self.setMinimumWidth(400)

        # Debounce timer for live updates
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(DEBOUNCE_DELAY_MS)
        self._debounce_timer.timeout.connect(self._do_apply_live_update)

        # Layout principal
        main_layout = QVBoxLayout(self)

        # Onglets
        tabs = QTabWidget()

        # Onglet Courbes
        lines_widget = self._create_lines_tab()
        tabs.addTab(lines_widget, "Courbes")

        # Onglet Légende
        legend_widget = self._create_legend_tab()
        tabs.addTab(legend_widget, "Légende")

        main_layout.addWidget(tabs)

        # Bouton Fermer
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)

    def _create_lines_tab(self):
        """Créer l'onglet des courbes"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Épaisseur des lignes
        self.line_width = QDoubleSpinBox()
        self.line_width.setRange(0.1, 10.0)
        self.line_width.setDecimals(1)
        self.line_width.setSingleStep(0.1)
        self.line_width.setValue(self.canvas.plot_style.get('line_width', 1.0))
        self.line_width.setSuffix(" px")
        self.line_width.valueChanged.connect(self._apply_live_update)
        layout.addRow("Épaisseur:", self.line_width)

        # Info
        info_label = QLabel("Cette modification s'applique à toutes les courbes")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addRow(info_label)

        return widget

    def _create_legend_tab(self):
        """Créer l'onglet de la légende"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Position
        self.legend_location = QComboBox()
        for name, value in LEGEND_LOCATIONS:
            self.legend_location.addItem(name, value)

        current_loc = self.canvas.plot_style.get('legend_location', 'best')
        for i in range(self.legend_location.count()):
            if self.legend_location.itemData(i) == current_loc:
                self.legend_location.setCurrentIndex(i)
                break
        self.legend_location.currentIndexChanged.connect(self._apply_live_update)
        layout.addRow("Position:", self.legend_location)

        # Police
        self.legend_font = QFontComboBox()
        font = QFont(self.canvas.plot_style.get('legend_fontfamily', 'sans-serif'))
        self.legend_font.setCurrentFont(font)
        self.legend_font.currentFontChanged.connect(self._apply_live_update)
        layout.addRow("Police:", self.legend_font)

        # Taille
        self.legend_size = QSpinBox()
        self.legend_size.setRange(6, 24)
        self.legend_size.setValue(self.canvas.plot_style.get('legend_fontsize', 10))
        self.legend_size.valueChanged.connect(self._apply_live_update)
        layout.addRow("Taille:", self.legend_size)

        # Colonnes
        self.legend_columns = QSpinBox()
        self.legend_columns.setRange(1, 10)
        self.legend_columns.setValue(self.canvas.plot_style.get('legend_columns', 1))
        self.legend_columns.valueChanged.connect(self._apply_live_update)
        layout.addRow("Colonnes:", self.legend_columns)

        return widget

    def _apply_live_update(self):
        """Debounced trigger for live update"""
        self._debounce_timer.start()  # Restart timer on each change

    def _do_apply_live_update(self):
        """Applique les modifications en temps réel au plot"""
        style = self.canvas.plot_style.copy()
        style.update({
            # Courbes
            'line_width': self.line_width.value(),
            # Légende
            'legend_location': self.legend_location.currentData(),
            'legend_fontfamily': self.legend_font.currentFont().family(),
            'legend_fontsize': self.legend_size.value(),
            'legend_columns': self.legend_columns.value()
        })
        self.canvas.set_plot_style(style)

    def keyPressEvent(self, event):
        """Fermer la fenêtre si Enter/Return est pressé"""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.close()
        else:
            super().keyPressEvent(event)


def setup_interactive_editing(canvas, plot_window):
    """Configure le canvas pour l'édition interactive via clic droit

    Args:
        canvas: PlotCanvas instance
        plot_window: PlotWindow parent
    """
    # Connecter le gestionnaire de clic droit (détection par bbox)
    canvas.mpl_connect('button_press_event', lambda event: _on_button_press(event, canvas, plot_window))


def _is_near_line(event, canvas, tolerance=10):
    """Vérifie si le clic est proche d'une courbe

    Args:
        event: MouseEvent matplotlib
        canvas: PlotCanvas instance
        tolerance: Distance en pixels pour considérer un clic comme "proche"

    Returns:
        bool: True si proche d'une courbe, False sinon
    """
    if not event.inaxes:
        return False

    # Récupérer toutes les lignes de l'axe concerné
    lines = event.inaxes.get_lines()
    if not lines:
        return False

    # Position du clic en coordonnées display (pixels)
    click_x, click_y = event.x, event.y

    # Vérifier chaque ligne
    for line in lines:
        # Récupérer les données de la ligne
        xdata = line.get_xdata()
        ydata = line.get_ydata()

        if len(xdata) == 0:
            continue

        # Transformer les coordonnées data en coordonnées display
        transform = line.get_transform()
        points_display = transform.transform(list(zip(xdata, ydata)))

        # Vérifier la distance au clic pour chaque segment
        for i in range(len(points_display) - 1):
            x1, y1 = points_display[i]
            x2, y2 = points_display[i + 1]

            # Distance du point au segment
            dist = _point_to_segment_distance(click_x, click_y, x1, y1, x2, y2)

            if dist < tolerance:
                return True

    return False


def _point_to_segment_distance(px, py, x1, y1, x2, y2):
    """Calcule la distance d'un point à un segment de ligne

    Args:
        px, py: Coordonnées du point
        x1, y1, x2, y2: Coordonnées du segment

    Returns:
        float: Distance minimale en pixels
    """
    # Longueur du segment au carré
    dx = x2 - x1
    dy = y2 - y1
    segment_length_sq = dx * dx + dy * dy

    if segment_length_sq == 0:
        # Segment réduit à un point
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5

    # Paramètre t pour la projection du point sur la ligne
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / segment_length_sq))

    # Point projeté
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy

    # Distance au point projeté
    return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5


def _on_button_press(event, canvas, plot_window):
    """Gestionnaire de clic droit - ouvre le menu radial

    Args:
        event: MouseEvent matplotlib
        canvas: PlotCanvas instance
        plot_window: PlotWindow parent
    """
    # Vérifier que c'est un clic droit
    if event.button != 3:
        return

    print("🟢 Clic droit détecté - ouverture menu radial")

    # Convertir les coordonnées matplotlib en coordonnées globales Qt
    # event.x et event.y sont en pixels depuis le coin bas-gauche du canvas
    # Qt utilise le coin haut-gauche
    try:
        from radial_menu import show_radial_menu

        # Coordonnées dans le canvas (matplotlib utilise y inversé)
        canvas_x = int(event.x) if event.x is not None else canvas.width() // 2
        canvas_y = int(canvas.height() - event.y) if event.y is not None else canvas.height() // 2

        # Convertir en coordonnées globales
        global_pos = canvas.mapToGlobal(QPoint(canvas_x, canvas_y))

        show_radial_menu(global_pos, canvas, plot_window)
    except ImportError as e:
        print(f"❌ Erreur import radial_menu: {e}")
        # Fallback vers l'ancien comportement
        _on_button_press_legacy(event, canvas, plot_window)


def _on_button_press_legacy(event, canvas, plot_window):
    """Ancien gestionnaire de clic droit - 4 zones simples (fallback)

    Args:
        event: MouseEvent matplotlib
        canvas: PlotCanvas instance
        plot_window: PlotWindow parent
    """
    # 4 zones KISS : Titre, Courbes, Zone axes, Tout le reste

    # 1. Titre (priorité)
    try:
        if hasattr(canvas.ax, 'title') and canvas.ax.title:
            bbox = canvas.ax.title.get_window_extent()
            if event.x is not None and event.y is not None and bbox.contains(event.x, event.y):
                _edit_title(canvas, plot_window)
                return
    except (AttributeError, RuntimeError):
        pass

    # 2. Courbes (détection de proximité)
    if event.inaxes in [canvas.ax, getattr(canvas, 'ax2', None)]:
        # Vérifier si le clic est proche d'une courbe
        if _is_near_line(event, canvas):
            _edit_lines_and_legend(canvas, plot_window)
            return

        # Sinon, on édite les axes/grilles
        _edit_axes_and_grid(canvas, plot_window)
        return

    # 3. Tout le reste (hors axes, légende externe, etc.) → Courbes + Légende
    _edit_lines_and_legend(canvas, plot_window)


def _edit_axes_and_grid(canvas, plot_window):
    """Ouvrir la fenêtre non-modale axes + grilles (ou activer si déjà ouverte)"""
    global _open_windows

    # Si la fenêtre existe déjà et est visible, l'activer
    if _open_windows['axes_grid'] is not None and _open_windows['axes_grid'].isVisible():
        _open_windows['axes_grid'].raise_()
        _open_windows['axes_grid'].activateWindow()
        return

    # Créer et afficher la nouvelle fenêtre
    window = AxesAndGridEditDialog(plot_window, canvas)
    _open_windows['axes_grid'] = window
    window.show()


def _edit_lines_and_legend(canvas, plot_window):
    """Ouvrir la fenêtre non-modale courbes + légende (ou activer si déjà ouverte)"""
    global _open_windows

    # Si la fenêtre existe déjà et est visible, l'activer
    if _open_windows['lines_legend'] is not None and _open_windows['lines_legend'].isVisible():
        _open_windows['lines_legend'].raise_()
        _open_windows['lines_legend'].activateWindow()
        return

    # Créer et afficher la nouvelle fenêtre
    window = LinesAndLegendEditDialog(plot_window, canvas)
    _open_windows['lines_legend'] = window
    window.show()


def _edit_title(canvas, plot_window):
    """Ouvrir la fenêtre non-modale d'édition du titre (ou activer si déjà ouverte)"""
    global _open_windows

    # Si la fenêtre existe déjà et est visible, l'activer
    if _open_windows['title'] is not None and _open_windows['title'].isVisible():
        _open_windows['title'].raise_()
        _open_windows['title'].activateWindow()
        return

    # Créer et afficher la nouvelle fenêtre
    window = TitleEditDialog(plot_window, canvas)
    _open_windows['title'] = window
    window.show()


