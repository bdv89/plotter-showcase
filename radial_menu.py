"""Menu radial pour édition rapide du graphique via clic droit + molette"""
import math
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath

# Couleurs Flexoki Dark
FLEXOKI = {
    'bg': QColor('#100f0e'),
    'segment': QColor('#282726'),
    'hover': QColor('#3a3634'),
    'text': QColor('#d4be98'),
    'border': QColor('#403e3c'),
    'accent': QColor('#d4a959'),  # Jaune Flexoki pour accent
}

# Configuration des segments du menu radial
# Chaque segment: (nom, icône, description)
MENU_ITEMS = [
    ('grid', '#', 'Grille'),
    ('legend', '\U0001F4DC', 'Légende'),  # 📜
    ('linewidth', '\u2501', 'Épaisseur'),  # ━
    ('export', '\U0001F4F7', 'Export'),  # 📷
    ('zoom', '\U0001F50D', 'Zoom Fit'),  # 🔍
    ('style', '\u2699\uFE0F', 'Style'),  # ⚙️
]

# Styles de grille pour le cycle molette
GRID_STYLES = [
    ('--', 'Dashed'),
    ('-', 'Solid'),
    (':', 'Dotted'),
    ('off', 'Off'),
]

# Positions de légende pour le cycle molette
LEGEND_POSITIONS = [
    'best', 'upper right', 'upper left', 'lower left', 'lower right',
    'outside_right', 'outside_left', 'outside_top', 'outside_bottom'
]

# DPI pour export
EXPORT_DPIS = [100, 150, 300, 600]


class RadialMenu(QWidget):
    """Menu radial avec survol + molette pour ajuster les paramètres"""

    def __init__(self, canvas, plot_window, global_pos):
        super().__init__(None)  # Pas de parent = fenêtre indépendante
        self.canvas = canvas
        self.plot_window = plot_window
        self.global_pos = global_pos

        # Géométrie
        self.inner_radius = 40
        self.outer_radius = 120
        self.num_segments = len(MENU_ITEMS)
        self.segment_angle = 360 / self.num_segments

        # État
        self.hovered_segment = -1
        self.current_export_dpi_idx = 2  # 300 par défaut
        self.current_legend_idx = LEGEND_POSITIONS.index(
            canvas.plot_style.get('legend_location', 'best')
        ) if canvas.plot_style.get('legend_location', 'best') in LEGEND_POSITIONS else 0

        # Trouver l'index du style de grille actuel
        current_grid_style = canvas.plot_style.get('major_grid_style', '--')
        grid_enabled = canvas.plot_style.get('x_major_grid', True) or canvas.plot_style.get('y_major_grid', True)
        if not grid_enabled:
            self.current_grid_idx = 3  # 'off'
        else:
            self.current_grid_idx = next(
                (i for i, (style, _) in enumerate(GRID_STYLES) if style == current_grid_style),
                0
            )

        # Configuration fenêtre - Qt.Tool fonctionne mieux sur Wayland que Qt.Popup
        self.setWindowFlags(
            Qt.Tool |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setMouseTracking(True)

        # Taille et position
        size = self.outer_radius * 2 + 20
        self.setFixedSize(size, size)
        self.center = QPoint(size // 2, size // 2)

        # Positionner le menu centré sur le clic
        target_x = global_pos.x() - size // 2
        target_y = global_pos.y() - size // 2
        self.move(target_x, target_y)

        print(f"🟢 Menu radial ouvert à ({target_x}, {target_y}), taille={size}x{size}")

    def paintEvent(self, event):
        """Dessiner le menu radial"""
        print(f"🎨 paintEvent appelé, rect={self.rect()}")

        painter = QPainter(self)
        if not painter.isActive():
            print("❌ QPainter non actif!")
            return

        painter.setRenderHint(QPainter.Antialiasing)

        # Fond semi-transparent
        painter.setBrush(QBrush(QColor(16, 15, 14, 230)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.center, self.outer_radius + 5, self.outer_radius + 5)

        # Zone morte centrale
        painter.setBrush(QBrush(FLEXOKI['bg']))
        painter.setPen(QPen(FLEXOKI['border'], 1))
        painter.drawEllipse(self.center, self.inner_radius, self.inner_radius)

        # Dessiner les segments
        for i in range(self.num_segments):
            self._draw_segment(painter, i)

    def _draw_segment(self, painter, index):
        """Dessiner un segment du menu"""
        start_angle = index * self.segment_angle - 90  # Commencer en haut
        span_angle = self.segment_angle

        # Couleur selon survol
        is_hovered = (index == self.hovered_segment)
        fill_color = FLEXOKI['hover'] if is_hovered else FLEXOKI['segment']

        # Créer le chemin du segment (arc)
        path = QPainterPath()
        rect_outer = self.center.x() - self.outer_radius, self.center.y() - self.outer_radius, \
                     self.outer_radius * 2, self.outer_radius * 2
        rect_inner = self.center.x() - self.inner_radius, self.center.y() - self.inner_radius, \
                     self.inner_radius * 2, self.inner_radius * 2

        # Arc externe
        path.moveTo(self._point_on_circle(self.inner_radius, start_angle))
        path.arcTo(*rect_outer, -start_angle, -span_angle)
        path.arcTo(*rect_inner, -(start_angle + span_angle), span_angle)
        path.closeSubpath()

        # Remplir
        painter.setBrush(QBrush(fill_color))
        painter.setPen(QPen(FLEXOKI['border'], 1))
        painter.drawPath(path)

        # Dessiner l'icône et le texte
        mid_angle = start_angle + span_angle / 2
        mid_radius = (self.inner_radius + self.outer_radius) / 2
        icon_pos = self._point_on_circle(mid_radius, mid_angle)

        name, icon, desc = MENU_ITEMS[index]

        # Police pour l'icône
        icon_font = QFont('Segoe UI Emoji', 16)
        painter.setFont(icon_font)
        painter.setPen(QPen(FLEXOKI['accent'] if is_hovered else FLEXOKI['text']))

        # Centrer l'icône
        icon_rect = painter.fontMetrics().boundingRect(icon)
        icon_x = int(icon_pos.x() - icon_rect.width() / 2)
        icon_y = int(icon_pos.y() + icon_rect.height() / 4)
        painter.drawText(icon_x, icon_y, icon)

        # Si survolé, afficher la valeur actuelle au centre
        if is_hovered:
            self._draw_center_info(painter, index)

    def _draw_center_info(self, painter, index):
        """Afficher les infos au centre quand un segment est survolé"""
        name, icon, desc = MENU_ITEMS[index]

        # Valeur actuelle selon le type
        value_text = ""
        if name == 'grid':
            style, style_name = GRID_STYLES[self.current_grid_idx]
            value_text = style_name
        elif name == 'legend':
            value_text = LEGEND_POSITIONS[self.current_legend_idx].replace('_', ' ').title()
        elif name == 'linewidth':
            width = self.canvas.plot_style.get('line_width', 1.0)
            value_text = f"{width:.1f} px"
        elif name == 'export':
            value_text = f"{EXPORT_DPIS[self.current_export_dpi_idx]} DPI"
        elif name == 'zoom':
            value_text = "Reset"
        elif name == 'style':
            value_text = "Ouvrir"

        # Dessiner au centre
        painter.setFont(QFont('sans-serif', 10, QFont.Bold))
        painter.setPen(QPen(FLEXOKI['text']))
        painter.drawText(
            self.center.x() - 30, self.center.y() - 5,
            60, 20,
            Qt.AlignCenter,
            desc
        )
        painter.setFont(QFont('sans-serif', 8))
        painter.drawText(
            self.center.x() - 35, self.center.y() + 10,
            70, 15,
            Qt.AlignCenter,
            value_text
        )

    def _point_on_circle(self, radius, angle_deg):
        """Calculer un point sur un cercle"""
        angle_rad = math.radians(angle_deg)
        x = self.center.x() + radius * math.cos(angle_rad)
        y = self.center.y() + radius * math.sin(angle_rad)
        return QPoint(int(x), int(y))

    def mouseMoveEvent(self, event):
        """Détecter le segment survolé"""
        pos = event.pos()
        dx = pos.x() - self.center.x()
        dy = pos.y() - self.center.y()
        distance = math.sqrt(dx * dx + dy * dy)

        # Vérifier si dans la zone des segments
        if self.inner_radius < distance < self.outer_radius:
            # Calculer l'angle
            angle = math.degrees(math.atan2(dy, dx)) + 90
            if angle < 0:
                angle += 360

            # Trouver le segment
            segment = int(angle / self.segment_angle) % self.num_segments
            if segment != self.hovered_segment:
                self.hovered_segment = segment
                self.update()
        else:
            if self.hovered_segment != -1:
                self.hovered_segment = -1
                self.update()

    def wheelEvent(self, event):
        """Ajuster le paramètre du segment survolé avec la molette"""
        if self.hovered_segment < 0:
            return

        name, _, _ = MENU_ITEMS[self.hovered_segment]
        delta = 1 if event.angleDelta().y() > 0 else -1

        print(f"🟡 Molette sur {name}: delta={delta}")

        if name == 'grid':
            self._cycle_grid(delta)
        elif name == 'legend':
            self._cycle_legend(delta)
        elif name == 'linewidth':
            self._adjust_linewidth(delta)
        elif name == 'export':
            self._cycle_dpi(delta)

        self.update()

    def mousePressEvent(self, event):
        """Action au clic sur un segment"""
        if event.button() == Qt.LeftButton and self.hovered_segment >= 0:
            name, _, _ = MENU_ITEMS[self.hovered_segment]
            print(f"🔵 Clic sur {name}")

            if name == 'grid':
                self._toggle_grid()
            elif name == 'legend':
                self._toggle_legend_visibility()
            elif name == 'linewidth':
                self._reset_linewidth()
            elif name == 'export':
                self._export_png()
            elif name == 'zoom':
                self._zoom_fit()
            elif name == 'style':
                self._open_style_dialog()

            self.close()
        elif event.button() == Qt.RightButton:
            self.close()

    def keyPressEvent(self, event):
        """Navigation clavier du menu radial

        - Échap : fermer
        - Gauche/Droite : naviguer entre segments
        - Haut/Bas : ajuster valeur (comme molette)
        - Entrée/Espace : activer le segment
        """
        key = event.key()

        if key == Qt.Key_Escape:
            print("🔴 Menu radial fermé (Echap)")
            self.close()

        elif key in (Qt.Key_Left, Qt.Key_Right):
            # Navigation entre segments
            delta = -1 if key == Qt.Key_Left else 1
            if self.hovered_segment < 0:
                self.hovered_segment = 0
            else:
                self.hovered_segment = (self.hovered_segment + delta) % self.num_segments
            print(f"🟡 Navigation clavier → segment {self.hovered_segment}: {MENU_ITEMS[self.hovered_segment][0]}")
            self.update()

        elif key in (Qt.Key_Up, Qt.Key_Down):
            # Ajuster valeur (comme molette)
            if self.hovered_segment < 0:
                return
            delta = 1 if key == Qt.Key_Up else -1
            name, _, _ = MENU_ITEMS[self.hovered_segment]
            print(f"🟡 Ajustement clavier {name}: delta={delta}")

            if name == 'grid':
                self._cycle_grid(delta)
            elif name == 'legend':
                self._cycle_legend(delta)
            elif name == 'linewidth':
                self._adjust_linewidth(delta)
            elif name == 'export':
                self._cycle_dpi(delta)
            self.update()

        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            # Activer le segment sélectionné
            if self.hovered_segment >= 0:
                name, _, _ = MENU_ITEMS[self.hovered_segment]
                print(f"🔵 Activation clavier: {name}")

                if name == 'grid':
                    self._toggle_grid()
                elif name == 'legend':
                    self._toggle_legend_visibility()
                elif name == 'linewidth':
                    self._reset_linewidth()
                elif name == 'export':
                    self._export_png()
                elif name == 'zoom':
                    self._zoom_fit()
                elif name == 'style':
                    self._open_style_dialog()
                self.close()
        else:
            super().keyPressEvent(event)

    # === Actions ===

    def _cycle_grid(self, delta):
        """Changer le style de grille"""
        self.current_grid_idx = (self.current_grid_idx + delta) % len(GRID_STYLES)
        style, style_name = GRID_STYLES[self.current_grid_idx]

        plot_style = self.canvas.plot_style.copy()

        if style == 'off':
            plot_style['x_major_grid'] = False
            plot_style['y_major_grid'] = False
        else:
            plot_style['x_major_grid'] = True
            plot_style['y_major_grid'] = True
            plot_style['major_grid_style'] = style

        self.canvas.set_plot_style(plot_style)
        print(f"✅ Grille: {style_name}")

    def _toggle_grid(self):
        """Toggle grille on/off"""
        plot_style = self.canvas.plot_style.copy()
        grid_on = plot_style.get('x_major_grid', True) or plot_style.get('y_major_grid', True)

        plot_style['x_major_grid'] = not grid_on
        plot_style['y_major_grid'] = not grid_on

        self.canvas.set_plot_style(plot_style)
        print(f"✅ Grille: {'ON' if not grid_on else 'OFF'}")

    def _cycle_legend(self, delta):
        """Changer la position de la légende"""
        self.current_legend_idx = (self.current_legend_idx + delta) % len(LEGEND_POSITIONS)
        new_loc = LEGEND_POSITIONS[self.current_legend_idx]

        plot_style = self.canvas.plot_style.copy()
        plot_style['legend_location'] = new_loc
        self.canvas.set_plot_style(plot_style)
        print(f"✅ Légende: {new_loc}")

    def _toggle_legend_visibility(self):
        """Toggle visibilité de la légende (via position 'none' simulé)"""
        # Pour simplifier, on cycle juste la position
        self._cycle_legend(1)

    def _adjust_linewidth(self, delta):
        """Ajuster l'épaisseur des lignes"""
        plot_style = self.canvas.plot_style.copy()
        current = plot_style.get('line_width', 1.0)
        new_width = max(0.1, min(10.0, current + delta * 0.2))

        plot_style['line_width'] = new_width
        self.canvas.set_plot_style(plot_style)
        print(f"✅ Épaisseur: {new_width:.1f} px")

    def _reset_linewidth(self):
        """Reset épaisseur à 1.0"""
        plot_style = self.canvas.plot_style.copy()
        plot_style['line_width'] = 1.0
        self.canvas.set_plot_style(plot_style)
        print("✅ Épaisseur: reset à 1.0 px")

    def _cycle_dpi(self, delta):
        """Changer le DPI d'export"""
        self.current_export_dpi_idx = (self.current_export_dpi_idx + delta) % len(EXPORT_DPIS)
        print(f"✅ Export DPI: {EXPORT_DPIS[self.current_export_dpi_idx]}")

    def _export_png(self):
        """Exporter le graphique en PNG"""
        from PyQt5.QtWidgets import QFileDialog
        dpi = EXPORT_DPIS[self.current_export_dpi_idx]

        filepath, _ = QFileDialog.getSaveFileName(
            self.plot_window,
            "Exporter le graphique",
            "plot.png",
            "PNG (*.png);;All Files (*)"
        )

        if filepath:
            try:
                self.canvas.fig.savefig(filepath, dpi=dpi)
                print(f"✅ Exporté: {filepath} ({dpi} DPI)")
            except Exception as e:
                print(f"❌ Erreur export: {e}")

    def _zoom_fit(self):
        """Reset le zoom à la vue complète"""
        try:
            self.canvas.ax.autoscale()
            if hasattr(self.canvas, 'ax2') and self.canvas.ax2:
                self.canvas.ax2.autoscale()
            self.canvas.draw_idle()  # Non-blocking draw for better UI responsiveness
            print("✅ Zoom: reset")
        except Exception as e:
            print(f"❌ Erreur zoom: {e}")

    def _open_style_dialog(self):
        """Ouvrir la fenêtre PlotStyleWindow"""
        if hasattr(self.plot_window, 'style_window'):
            self.plot_window.style_window.show()
            self.plot_window.style_window.activateWindow()
            print("✅ Style dialog ouvert")


def show_radial_menu(global_pos, canvas, plot_window):
    """Afficher le menu radial à la position donnée

    Args:
        global_pos: QPoint en coordonnées globales (écran)
        canvas: PlotCanvas instance
        plot_window: PlotWindow parent
    """
    # Fermer l'ancien menu s'il existe
    if hasattr(canvas, '_radial_menu') and canvas._radial_menu is not None:
        try:
            canvas._radial_menu.close()
        except:
            pass

    menu = RadialMenu(canvas, plot_window, global_pos)

    # Garder une référence pour éviter le garbage collection
    canvas._radial_menu = menu

    menu.show()
    menu.raise_()
    menu.activateWindow()
    menu.setFocus()

    # Debug: vérifier la visibilité
    print(f"🔵 Menu visible={menu.isVisible()}, geometry={menu.geometry()}")

    return menu
