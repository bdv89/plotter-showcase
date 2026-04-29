"""Quick Processing Dialog - Dialog horizontal pour le traitement de données

Invoqué par le bouton Processing, affiche toutes les options d'un coup d'œil.
Même pattern que QuickStyleDialog mais pour le data processing.
"""

from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QFrame, QSizePolicy, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer

from plot_dialog_components import create_spin_box, create_combo_box, create_checkbox

# Debounce delay pour live update
DEBOUNCE_MS = 200


class QuickProcessingDialog(QDialog):
    """Dialog horizontal avec toutes les options de processing visibles"""

    def __init__(self, plot_window):
        super().__init__(plot_window)
        self.plot_window = plot_window
        self.processing_window = plot_window.processing_window  # Référence à l'ancien ProcessingWindow

        self.setWindowTitle("Quick Processing")
        self.setMinimumWidth(1200)

        # Debounce timer
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._do_apply)

        self._build_ui()
        self._connect_signals()
        self._sync_from_processing_window()

        print("🟢 QuickProcessingDialog créé")

    def _build_ui(self):
        """Construire l'interface - tout visible horizontalement"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # Ligne 1 : Smoothing + Denoise Z-score + Normalize
        row1 = QHBoxLayout()
        row1.addWidget(self._create_smooth_section())
        row1.addWidget(self._create_outliers_section())
        row1.addWidget(self._create_normalize_section())
        row1.addStretch()
        main_layout.addLayout(row1)

        # Ligne 2 : Advanced Denoising + Baseline Correction
        row2 = QHBoxLayout()
        row2.addWidget(self._create_adv_denoise_section())
        row2.addWidget(self._create_baseline_section())
        row2.addStretch()
        main_layout.addLayout(row2)

        # Ligne 3 : Time Averaging + Peak Fitting
        row3 = QHBoxLayout()
        row3.addWidget(self._create_time_avg_section())
        row3.addWidget(self._create_fitting_section())
        row3.addStretch()
        main_layout.addLayout(row3)

        # Ligne 4 : Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset_all)
        btn_layout.addWidget(reset_btn)

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

    def _vsep(self):
        """Créer un séparateur vertical"""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        return sep

    # === Sections ===

    def _create_smooth_section(self):
        """Section Smoothing"""
        frame, layout = self._create_section_frame("Smoothing")

        self.chk_smooth = create_checkbox("Enable")
        layout.addWidget(self.chk_smooth)

        layout.addWidget(QLabel("Window:"))
        self.spin_smooth_window = create_spin_box(1, 999, 5)
        layout.addWidget(self.spin_smooth_window)

        return frame

    def _create_outliers_section(self):
        """Section Denoise Z-score"""
        frame, layout = self._create_section_frame("Denoise (Z-score)")

        self.chk_outliers = create_checkbox("Enable")
        layout.addWidget(self.chk_outliers)

        layout.addWidget(QLabel("Threshold:"))
        self.spin_z_threshold = create_spin_box(1, 100, 30, decimals=1)
        self.spin_z_threshold.setValue(30)  # 3.0 * 10
        layout.addWidget(self.spin_z_threshold)

        return frame

    def _create_normalize_section(self):
        """Section Normalize"""
        frame, layout = self._create_section_frame("Normalize")

        self.chk_normalize = create_checkbox("Enable")
        layout.addWidget(self.chk_normalize)

        layout.addWidget(QLabel("Method:"))
        self.combo_norm_method = create_combo_box(["minmax", "zscore"])
        layout.addWidget(self.combo_norm_method)

        return frame

    def _create_adv_denoise_section(self):
        """Section Advanced Denoising"""
        frame, layout = self._create_section_frame("Advanced Denoising")

        self.chk_adv_denoise = create_checkbox("Enable")
        layout.addWidget(self.chk_adv_denoise)

        layout.addWidget(QLabel("Method:"))
        self.combo_denoise_method = create_combo_box([
            "Savitzky-Golay", "Median Filter", "Wavelet", "FFT Low-pass"
        ])
        layout.addWidget(self.combo_denoise_method)

        layout.addWidget(self._vsep())

        # Savitzky-Golay params (toujours visibles pour simplicité)
        layout.addWidget(QLabel("Win:"))
        self.spin_savgol_window = create_spin_box(5, 51, 11, step=2)
        layout.addWidget(self.spin_savgol_window)

        layout.addWidget(QLabel("Poly:"))
        self.spin_savgol_poly = create_spin_box(1, 5, 3)
        layout.addWidget(self.spin_savgol_poly)

        return frame

    def _create_baseline_section(self):
        """Section Baseline Correction"""
        frame, layout = self._create_section_frame("Baseline Correction")

        self.chk_baseline = create_checkbox("Enable")
        layout.addWidget(self.chk_baseline)

        layout.addWidget(QLabel("Method:"))
        self.combo_baseline_method = create_combo_box([
            "SNIP", "arPLS", "AsLS", "Polynomial"
        ])
        layout.addWidget(self.combo_baseline_method)

        layout.addWidget(self._vsep())

        # SNIP params (commun)
        layout.addWidget(QLabel("K:"))
        self.spin_snip_k = create_spin_box(1, 1000, 12)
        layout.addWidget(self.spin_snip_k)

        return frame

    def _create_time_avg_section(self):
        """Section Time-Window Averaging"""
        frame, layout = self._create_section_frame("Time Averaging")

        self.chk_time_avg = create_checkbox("Enable")
        layout.addWidget(self.chk_time_avg)

        layout.addWidget(QLabel("Start:"))
        self.spin_ta_start = create_spin_box(0, 10000, 30, decimals=3)
        self.spin_ta_start.setValue(30)  # 0.03 * 1000
        layout.addWidget(self.spin_ta_start)

        layout.addWidget(QLabel("Interval:"))
        self.spin_ta_interval = create_spin_box(10, 10000, 2060, decimals=3)
        self.spin_ta_interval.setValue(2060)  # 2.06 * 1000
        layout.addWidget(self.spin_ta_interval)

        layout.addWidget(QLabel("Window:"))
        self.spin_ta_window = create_spin_box(1, 1000, 20, decimals=2)
        self.spin_ta_window.setValue(20)  # 2.0 * 10
        layout.addWidget(self.spin_ta_window)

        return frame

    def _create_fitting_section(self):
        """Section Peak Fitting"""
        frame, layout = self._create_section_frame("Peak Fitting")

        self.chk_fitting = create_checkbox("Enable")
        layout.addWidget(self.chk_fitting)

        layout.addWidget(QLabel("Method:"))
        self.combo_fit_method = create_combo_box(["Gauss", "Voigt"])
        layout.addWidget(self.combo_fit_method)

        layout.addWidget(self._vsep())

        layout.addWidget(QLabel("Prom:"))
        self.spin_fit_prom = create_spin_box(1, 100, 10, decimals=2)
        self.spin_fit_prom.setValue(10)  # 0.1 * 100
        layout.addWidget(self.spin_fit_prom)

        layout.addWidget(QLabel("Dist:"))
        self.spin_fit_dist = create_spin_box(1, 100, 10)
        layout.addWidget(self.spin_fit_dist)

        layout.addWidget(self._vsep())

        self.chk_show_markers = create_checkbox("Markers", True)
        layout.addWidget(self.chk_show_markers)

        self.chk_show_numbers = create_checkbox("IDs", True)
        layout.addWidget(self.chk_show_numbers)

        return frame

    # === Signals & Sync ===

    def _connect_signals(self):
        """Connecter tous les signaux au debounce"""
        # Checkboxes
        for chk in [self.chk_smooth, self.chk_outliers, self.chk_normalize,
                    self.chk_adv_denoise, self.chk_baseline, self.chk_time_avg,
                    self.chk_fitting, self.chk_show_markers, self.chk_show_numbers]:
            chk.stateChanged.connect(self._schedule_update)

        # Spinboxes
        for spin in [self.spin_smooth_window, self.spin_z_threshold,
                     self.spin_savgol_window, self.spin_savgol_poly,
                     self.spin_snip_k, self.spin_ta_start, self.spin_ta_interval,
                     self.spin_ta_window, self.spin_fit_prom, self.spin_fit_dist]:
            spin.valueChanged.connect(self._schedule_update)

        # Combos
        for combo in [self.combo_norm_method, self.combo_denoise_method,
                      self.combo_baseline_method, self.combo_fit_method]:
            combo.currentIndexChanged.connect(self._schedule_update)

    def _sync_from_processing_window(self):
        """Synchroniser depuis le ProcessingWindow existant"""
        pw = self.processing_window
        if not pw:
            return

        # Block signals pendant la sync
        all_widgets = (
            [self.chk_smooth, self.chk_outliers, self.chk_normalize,
             self.chk_adv_denoise, self.chk_baseline, self.chk_time_avg,
             self.chk_fitting, self.chk_show_markers, self.chk_show_numbers] +
            [self.spin_smooth_window, self.spin_z_threshold,
             self.spin_savgol_window, self.spin_savgol_poly,
             self.spin_snip_k, self.spin_ta_start, self.spin_ta_interval,
             self.spin_ta_window, self.spin_fit_prom, self.spin_fit_dist] +
            [self.combo_norm_method, self.combo_denoise_method,
             self.combo_baseline_method, self.combo_fit_method]
        )

        for w in all_widgets:
            w.blockSignals(True)

        try:
            # Smoothing
            self.chk_smooth.setChecked(pw.chk_smooth.isChecked())
            self.spin_smooth_window.setValue(pw.spin_window.value())

            # Outliers
            self.chk_outliers.setChecked(pw.chk_outliers.isChecked())
            self.spin_z_threshold.setValue(int(pw.spin_z.value() * 10))

            # Normalize
            self.chk_normalize.setChecked(pw.chk_norm.isChecked())
            idx = self.combo_norm_method.findText(pw.combo_norm.currentText())
            if idx >= 0:
                self.combo_norm_method.setCurrentIndex(idx)

            # Advanced Denoising
            self.chk_adv_denoise.setChecked(pw.chk_denoise_adv.isChecked())
            idx = self.combo_denoise_method.findText(pw.combo_denoise_method.currentText())
            if idx >= 0:
                self.combo_denoise_method.setCurrentIndex(idx)
            self.spin_savgol_window.setValue(pw.spin_savgol_window.value())
            self.spin_savgol_poly.setValue(pw.spin_savgol_polyorder.value())

            # Baseline
            self.chk_baseline.setChecked(pw.chk_baseline.isChecked())
            idx = self.combo_baseline_method.findText(pw.combo_baseline_method.currentText())
            if idx >= 0:
                self.combo_baseline_method.setCurrentIndex(idx)
            self.spin_snip_k.setValue(pw.spin_snip_K.value())

            # Time Averaging
            self.chk_time_avg.setChecked(pw.chk_time_avg.isChecked())
            self.spin_ta_start.setValue(int(pw.spin_ta_start.value() * 1000))
            self.spin_ta_interval.setValue(int(pw.spin_ta_regular_interval.value() * 1000))
            self.spin_ta_window.setValue(int(pw.spin_ta_window_size.value() * 10))

            # Peak Fitting
            self.chk_fitting.setChecked(pw.chk_fitting.isChecked())
            idx = self.combo_fit_method.findText(pw.combo_fit_method.currentText())
            if idx >= 0:
                self.combo_fit_method.setCurrentIndex(idx)
            self.spin_fit_prom.setValue(int(pw.spin_fit_prominence.value() * 100))
            self.spin_fit_dist.setValue(pw.spin_fit_min_distance.value())
            self.chk_show_markers.setChecked(pw.chk_show_peak_markers.isChecked())
            self.chk_show_numbers.setChecked(pw.chk_show_peak_numbers.isChecked())

        finally:
            for w in all_widgets:
                w.blockSignals(False)

    def _schedule_update(self):
        """Debounce trigger"""
        self._debounce_timer.start()

    def _do_apply(self):
        """Appliquer les changements au ProcessingWindow et déclencher apply_settings"""
        pw = self.processing_window
        if not pw:
            return

        # Bloquer les signaux du ProcessingWindow pour éviter les boucles
        pw.blockSignals(True)

        try:
            # Smoothing
            pw.chk_smooth.setChecked(self.chk_smooth.isChecked())
            pw.spin_window.setValue(self.spin_smooth_window.value())

            # Outliers
            pw.chk_outliers.setChecked(self.chk_outliers.isChecked())
            pw.spin_z.setValue(self.spin_z_threshold.value() / 10.0)

            # Normalize
            pw.chk_norm.setChecked(self.chk_normalize.isChecked())
            idx = pw.combo_norm.findText(self.combo_norm_method.currentText())
            if idx >= 0:
                pw.combo_norm.setCurrentIndex(idx)

            # Advanced Denoising
            pw.chk_denoise_adv.setChecked(self.chk_adv_denoise.isChecked())
            idx = pw.combo_denoise_method.findText(self.combo_denoise_method.currentText())
            if idx >= 0:
                pw.combo_denoise_method.setCurrentIndex(idx)
            pw.spin_savgol_window.setValue(self.spin_savgol_window.value())
            pw.spin_savgol_polyorder.setValue(self.spin_savgol_poly.value())

            # Baseline
            pw.chk_baseline.setChecked(self.chk_baseline.isChecked())
            idx = pw.combo_baseline_method.findText(self.combo_baseline_method.currentText())
            if idx >= 0:
                pw.combo_baseline_method.setCurrentIndex(idx)
            pw.spin_snip_K.setValue(self.spin_snip_k.value())

            # Time Averaging
            pw.chk_time_avg.setChecked(self.chk_time_avg.isChecked())
            pw.spin_ta_start.setValue(self.spin_ta_start.value() / 1000.0)
            pw.spin_ta_regular_interval.setValue(self.spin_ta_interval.value() / 1000.0)
            pw.spin_ta_window_size.setValue(self.spin_ta_window.value() / 10.0)

            # Peak Fitting
            pw.chk_fitting.setChecked(self.chk_fitting.isChecked())
            idx = pw.combo_fit_method.findText(self.combo_fit_method.currentText())
            if idx >= 0:
                pw.combo_fit_method.setCurrentIndex(idx)
            pw.spin_fit_prominence.setValue(self.spin_fit_prom.value() / 100.0)
            pw.spin_fit_min_distance.setValue(self.spin_fit_dist.value())
            pw.chk_show_peak_markers.setChecked(self.chk_show_markers.isChecked())
            pw.chk_show_peak_numbers.setChecked(self.chk_show_numbers.isChecked())

        finally:
            pw.blockSignals(False)

        # Déclencher l'application
        pw.apply_settings()
        print("✅ QuickProcessingDialog: settings appliqués")

    def _reset_all(self):
        """Reset toutes les options"""
        self.processing_window.reset_settings()
        self._sync_from_processing_window()
        print("✅ QuickProcessingDialog: reset effectué")

    def showEvent(self, event):
        """Sync à l'ouverture"""
        super().showEvent(event)
        self._sync_from_processing_window()

    def keyPressEvent(self, event):
        """Fermer avec Échap"""
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


def show_quick_processing(plot_window):
    """Ouvrir le QuickProcessingDialog"""
    # Réutiliser le dialog existant s'il existe
    if hasattr(plot_window, '_quick_processing_dialog') and plot_window._quick_processing_dialog is not None:
        try:
            plot_window._quick_processing_dialog._sync_from_processing_window()
            plot_window._quick_processing_dialog.show()
            plot_window._quick_processing_dialog.raise_()
            plot_window._quick_processing_dialog.activateWindow()
            return plot_window._quick_processing_dialog
        except:
            pass

    dialog = QuickProcessingDialog(plot_window)
    plot_window._quick_processing_dialog = dialog

    dialog.show()
    print("🟢 QuickProcessingDialog ouvert")
    return dialog
