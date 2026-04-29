from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QLabel, QPushButton, QWidget
)
from PyQt5.QtCore import Qt
import numpy as np
import pandas as pd
from data_pipeline import DataPipeline
from processing import (
    create_denoise_processor,
    create_smooth_processor,
    create_outliers_processor,
    create_normalize_processor,
    create_baseline_processor,
    create_time_averaging_processor
)


# All processor creation functions have been moved to processing/ module


class ProcessingWindow(QDialog):
    """Floating window to control live data processing (smoothing, denoise, normalize)."""

    def __init__(self, plot_window):
        super().__init__(plot_window)
        self.plot_window = plot_window
        self.setWindowTitle("Processing")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setModal(False)
        self.processing_order = ['baseline', 'denoise_adv', 'time_avg', 'smooth', 'outliers', 'normalize', 'fitting']
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Smoothing controls
        smooth_group = QGroupBox("Smoothing")
        s_outer = QVBoxLayout()
        s_layout = QHBoxLayout()
        self.chk_smooth = QCheckBox("Enable")
        self.spin_window = QSpinBox()
        self.spin_window.setRange(1, 999)
        self.spin_window.setSingleStep(1)
        self.spin_window.setValue(5)
        s_layout.addWidget(self.chk_smooth)
        s_layout.addWidget(QLabel("Window"))
        s_layout.addWidget(self.spin_window)
        s_outer.addLayout(s_layout)
        # Order buttons
        s_order = QHBoxLayout()
        self.btn_smooth_up = QPushButton("↑")
        self.btn_smooth_down = QPushButton("↓")
        self.btn_smooth_up.setMaximumWidth(30)
        self.btn_smooth_down.setMaximumWidth(30)
        self.btn_smooth_up.clicked.connect(lambda: self.move_up('smooth'))
        self.btn_smooth_down.clicked.connect(lambda: self.move_down('smooth'))
        self.lbl_smooth_order = QLabel("#0")
        self.lbl_smooth_order.setMinimumWidth(25)
        s_order.addWidget(QLabel("Order:"))
        s_order.addWidget(self.lbl_smooth_order)
        s_order.addWidget(self.btn_smooth_up)
        s_order.addWidget(self.btn_smooth_down)
        s_order.addStretch()
        s_outer.addLayout(s_order)
        smooth_group.setLayout(s_outer)
        layout.addWidget(smooth_group)

        # Outliers controls
        out_group = QGroupBox("Denoise (Z-score outliers)")
        o_outer = QVBoxLayout()
        o_layout = QHBoxLayout()
        self.chk_outliers = QCheckBox("Enable")
        self.spin_z = QDoubleSpinBox()
        self.spin_z.setRange(0.1, 10.0)
        self.spin_z.setSingleStep(0.1)
        self.spin_z.setValue(3.0)
        o_layout.addWidget(self.chk_outliers)
        o_layout.addWidget(QLabel("Threshold"))
        o_layout.addWidget(self.spin_z)
        o_outer.addLayout(o_layout)
        # Order buttons
        o_order = QHBoxLayout()
        self.btn_outliers_up = QPushButton("↑")
        self.btn_outliers_down = QPushButton("↓")
        self.btn_outliers_up.setMaximumWidth(30)
        self.btn_outliers_down.setMaximumWidth(30)
        self.btn_outliers_up.clicked.connect(lambda: self.move_up('outliers'))
        self.btn_outliers_down.clicked.connect(lambda: self.move_down('outliers'))
        self.lbl_outliers_order = QLabel("#0")
        self.lbl_outliers_order.setMinimumWidth(25)
        o_order.addWidget(QLabel("Order:"))
        o_order.addWidget(self.lbl_outliers_order)
        o_order.addWidget(self.btn_outliers_up)
        o_order.addWidget(self.btn_outliers_down)
        o_order.addStretch()
        o_outer.addLayout(o_order)
        out_group.setLayout(o_outer)
        layout.addWidget(out_group)

        # Normalize controls
        norm_group = QGroupBox("Normalize")
        n_outer = QVBoxLayout()
        n_layout = QHBoxLayout()
        self.chk_norm = QCheckBox("Enable")
        self.combo_norm = QComboBox()
        self.combo_norm.addItems(["minmax", "zscore"])
        n_layout.addWidget(self.chk_norm)
        n_layout.addWidget(QLabel("Method"))
        n_layout.addWidget(self.combo_norm)
        n_outer.addLayout(n_layout)
        # Order buttons
        n_order = QHBoxLayout()
        self.btn_normalize_up = QPushButton("↑")
        self.btn_normalize_down = QPushButton("↓")
        self.btn_normalize_up.setMaximumWidth(30)
        self.btn_normalize_down.setMaximumWidth(30)
        self.btn_normalize_up.clicked.connect(lambda: self.move_up('normalize'))
        self.btn_normalize_down.clicked.connect(lambda: self.move_down('normalize'))
        self.lbl_normalize_order = QLabel("#0")
        self.lbl_normalize_order.setMinimumWidth(25)
        n_order.addWidget(QLabel("Order:"))
        n_order.addWidget(self.lbl_normalize_order)
        n_order.addWidget(self.btn_normalize_up)
        n_order.addWidget(self.btn_normalize_down)
        n_order.addStretch()
        n_outer.addLayout(n_order)
        norm_group.setLayout(n_outer)
        layout.addWidget(norm_group)

        # Advanced Denoising controls
        denoise_group = QGroupBox("Advanced Denoising")
        d_outer = QVBoxLayout()

        # Enable + Method selector
        d_method_layout = QHBoxLayout()
        self.chk_denoise_adv = QCheckBox("Enable")
        self.combo_denoise_method = QComboBox()
        # UI display names for denoising methods
        # Backend mapping: processing/denoise.py:method_map
        # Si ajout méthode: 1) Ajouter ici, 2) Ajouter dans method_map
        self.combo_denoise_method.addItems(["Savitzky-Golay", "Median Filter", "Wavelet", "FFT Low-pass"])
        d_method_layout.addWidget(self.chk_denoise_adv)
        d_method_layout.addWidget(QLabel("Method"))
        d_method_layout.addWidget(self.combo_denoise_method)
        d_outer.addLayout(d_method_layout)

        # Parameters container (dynamic based on method)
        self.denoise_params_widget = QWidget()
        self.denoise_params_layout = QVBoxLayout(self.denoise_params_widget)

        # Savitzky-Golay params
        self.savgol_params = QWidget()
        savgol_layout = QHBoxLayout(self.savgol_params)
        self.spin_savgol_window = QSpinBox()
        self.spin_savgol_window.setRange(5, 51)
        self.spin_savgol_window.setSingleStep(2)
        self.spin_savgol_window.setValue(11)
        self.spin_savgol_polyorder = QSpinBox()
        self.spin_savgol_polyorder.setRange(1, 5)
        self.spin_savgol_polyorder.setValue(3)
        savgol_layout.addWidget(QLabel("Window"))
        savgol_layout.addWidget(self.spin_savgol_window)
        savgol_layout.addWidget(QLabel("Polyorder"))
        savgol_layout.addWidget(self.spin_savgol_polyorder)
        savgol_layout.addStretch()

        # Median params
        self.median_params = QWidget()
        median_layout = QHBoxLayout(self.median_params)
        self.spin_median_kernel = QSpinBox()
        self.spin_median_kernel.setRange(3, 21)
        self.spin_median_kernel.setSingleStep(2)
        self.spin_median_kernel.setValue(5)
        median_layout.addWidget(QLabel("Kernel size"))
        median_layout.addWidget(self.spin_median_kernel)
        median_layout.addStretch()

        # Wavelet params
        self.wavelet_params = QWidget()
        wavelet_layout = QHBoxLayout(self.wavelet_params)
        self.combo_wavelet_type = QComboBox()
        self.combo_wavelet_type.addItems(["db4", "sym8", "coif5"])
        self.combo_wavelet_mode = QComboBox()
        self.combo_wavelet_mode.addItems(["soft", "hard"])
        wavelet_layout.addWidget(QLabel("Wavelet"))
        wavelet_layout.addWidget(self.combo_wavelet_type)
        wavelet_layout.addWidget(QLabel("Mode"))
        wavelet_layout.addWidget(self.combo_wavelet_mode)
        wavelet_layout.addStretch()

        # FFT params
        self.fft_params = QWidget()
        fft_layout = QHBoxLayout(self.fft_params)
        self.spin_fft_cutoff = QDoubleSpinBox()
        self.spin_fft_cutoff.setRange(0.01, 0.5)
        self.spin_fft_cutoff.setSingleStep(0.01)
        self.spin_fft_cutoff.setValue(0.1)
        self.spin_fft_cutoff.setDecimals(3)
        fft_layout.addWidget(QLabel("Cutoff freq"))
        fft_layout.addWidget(self.spin_fft_cutoff)
        fft_layout.addStretch()

        # Add all param widgets to stack
        self.denoise_params_layout.addWidget(self.savgol_params)
        self.denoise_params_layout.addWidget(self.median_params)
        self.denoise_params_layout.addWidget(self.wavelet_params)
        self.denoise_params_layout.addWidget(self.fft_params)
        d_outer.addWidget(self.denoise_params_widget)

        # Connect method change to update visible params
        self.combo_denoise_method.currentIndexChanged.connect(self._update_denoise_params_visibility)
        self._update_denoise_params_visibility()  # Initialize

        # Order buttons
        d_order = QHBoxLayout()
        self.btn_denoise_up = QPushButton("↑")
        self.btn_denoise_down = QPushButton("↓")
        self.btn_denoise_up.setMaximumWidth(30)
        self.btn_denoise_down.setMaximumWidth(30)
        self.btn_denoise_up.clicked.connect(lambda: self.move_up('denoise_adv'))
        self.btn_denoise_down.clicked.connect(lambda: self.move_down('denoise_adv'))
        self.lbl_denoise_order = QLabel("#0")
        self.lbl_denoise_order.setMinimumWidth(25)
        d_order.addWidget(QLabel("Order:"))
        d_order.addWidget(self.lbl_denoise_order)
        d_order.addWidget(self.btn_denoise_up)
        d_order.addWidget(self.btn_denoise_down)
        d_order.addStretch()
        d_outer.addLayout(d_order)
        denoise_group.setLayout(d_outer)
        layout.addWidget(denoise_group)

        # Baseline Correction controls
        baseline_group = QGroupBox("Baseline Correction")
        b_layout = QVBoxLayout()

        # Enable + Method selector
        b_row1 = QHBoxLayout()
        self.chk_baseline = QCheckBox("Enable")
        self.combo_baseline_method = QComboBox()
        # UI display names for baseline methods
        # Backend: baseline_correction.py:subtract_baseline()
        # Si ajout méthode: 1) Ajouter ici, 2) Ajouter elif dans backend
        self.combo_baseline_method.addItems(["SNIP", "arPLS", "AsLS", "Polynomial"])  # order of recommended
        b_row1.addWidget(self.chk_baseline)
        b_row1.addWidget(QLabel("Method"))
        b_row1.addWidget(self.combo_baseline_method)
        b_layout.addLayout(b_row1)

        # SNIP params: K + transform
        b_row_snip = QHBoxLayout()
        self.spin_snip_K = QSpinBox()
        self.spin_snip_K.setRange(1, 1000)
        self.spin_snip_K.setValue(12)  # preset
        self.combo_snip_transform = QComboBox()
        self.combo_snip_transform.addItems(["sqrt", "log", "none"])
        b_row_snip.addWidget(QLabel("SNIP K"))
        b_row_snip.addWidget(self.spin_snip_K)
        b_row_snip.addWidget(QLabel("Transform"))
        b_row_snip.addWidget(self.combo_snip_transform)
        b_layout.addLayout(b_row_snip)

        # arPLS param: lambda
        b_row_arpls = QHBoxLayout()
        self.spin_arpls_lambda = QDoubleSpinBox()
        self.spin_arpls_lambda.setDecimals(0)
        self.spin_arpls_lambda.setRange(1e2, 1e9)
        self.spin_arpls_lambda.setValue(1e6)
        self.spin_arpls_lambda.setSingleStep(1e5)
        b_row_arpls.addWidget(QLabel("arPLS λ"))
        b_row_arpls.addWidget(self.spin_arpls_lambda)
        b_layout.addLayout(b_row_arpls)

        # AsLS params: lambda + p
        b_row_asls = QHBoxLayout()
        self.spin_asls_lambda = QDoubleSpinBox()
        self.spin_asls_lambda.setDecimals(0)
        self.spin_asls_lambda.setRange(1e2, 1e9)
        self.spin_asls_lambda.setValue(1e6)
        self.spin_asls_lambda.setSingleStep(1e5)
        self.spin_asls_p = QDoubleSpinBox()
        self.spin_asls_p.setDecimals(6)
        self.spin_asls_p.setRange(1e-6, 0.5)
        self.spin_asls_p.setValue(1e-3)
        self.spin_asls_p.setSingleStep(5e-4)
        b_row_asls.addWidget(QLabel("AsLS λ"))
        b_row_asls.addWidget(self.spin_asls_lambda)
        b_row_asls.addWidget(QLabel("p"))
        b_row_asls.addWidget(self.spin_asls_p)
        b_layout.addLayout(b_row_asls)

        # Polynomial (legacy): degree + peak sensitivity
        b_row_poly1 = QHBoxLayout()
        self.spin_degree = QSpinBox()
        self.spin_degree.setRange(1, 10)
        self.spin_degree.setValue(3)
        b_row_poly1.addWidget(QLabel("Polynomial Degree"))
        b_row_poly1.addWidget(self.spin_degree)
        b_layout.addLayout(b_row_poly1)

        b_row_poly2 = QHBoxLayout()
        self.spin_prominence = QDoubleSpinBox()
        self.spin_prominence.setRange(0.1, 10.0)
        self.spin_prominence.setSingleStep(0.5)
        self.spin_prominence.setValue(2.0)
        b_row_poly2.addWidget(QLabel("Peak Sensitivity"))
        b_row_poly2.addWidget(self.spin_prominence)
        b_layout.addLayout(b_row_poly2)

        # Order buttons for baseline
        b_order = QHBoxLayout()
        self.btn_baseline_up = QPushButton("↑")
        self.btn_baseline_down = QPushButton("↓")
        self.btn_baseline_up.setMaximumWidth(30)
        self.btn_baseline_down.setMaximumWidth(30)
        self.btn_baseline_up.clicked.connect(lambda: self.move_up('baseline'))
        self.btn_baseline_down.clicked.connect(lambda: self.move_down('baseline'))
        self.lbl_baseline_order = QLabel("#0")
        self.lbl_baseline_order.setMinimumWidth(25)
        b_order.addWidget(QLabel("Order:"))
        b_order.addWidget(self.lbl_baseline_order)
        b_order.addWidget(self.btn_baseline_up)
        b_order.addWidget(self.btn_baseline_down)
        b_order.addStretch()
        b_layout.addLayout(b_order)

        baseline_group.setLayout(b_layout)
        layout.addWidget(baseline_group)

        # Time-Window Averaging controls
        time_avg_group = QGroupBox("Time-Window Averaging")
        ta_outer = QVBoxLayout()

        # Enable checkbox
        ta_enable_layout = QHBoxLayout()
        self.chk_time_avg = QCheckBox("Enable")
        ta_enable_layout.addWidget(self.chk_time_avg)
        ta_enable_layout.addStretch()
        ta_outer.addLayout(ta_enable_layout)

        # Time column selector
        ta_col_layout = QHBoxLayout()
        ta_col_layout.addWidget(QLabel("Time Column"))
        self.combo_time_column = QComboBox()
        self.combo_time_column.setMinimumWidth(120)
        ta_col_layout.addWidget(self.combo_time_column)
        ta_col_layout.addStretch()
        ta_outer.addLayout(ta_col_layout)

        # Parameters row 1: start_time, first_interval
        ta_params1 = QHBoxLayout()
        self.spin_ta_start = QDoubleSpinBox()
        self.spin_ta_start.setRange(0.0, 1000.0)
        self.spin_ta_start.setSingleStep(0.01)
        self.spin_ta_start.setValue(0.03)
        self.spin_ta_start.setDecimals(3)
        ta_params1.addWidget(QLabel("Start (s)"))
        ta_params1.addWidget(self.spin_ta_start)

        self.spin_ta_first_interval = QDoubleSpinBox()
        self.spin_ta_first_interval.setRange(0.01, 1000.0)
        self.spin_ta_first_interval.setSingleStep(0.1)
        self.spin_ta_first_interval.setValue(1.03)
        self.spin_ta_first_interval.setDecimals(3)
        ta_params1.addWidget(QLabel("1st Interval (s)"))
        ta_params1.addWidget(self.spin_ta_first_interval)
        ta_params1.addStretch()
        ta_outer.addLayout(ta_params1)

        # Parameters row 2: regular_interval, window_size
        ta_params2 = QHBoxLayout()
        self.spin_ta_regular_interval = QDoubleSpinBox()
        self.spin_ta_regular_interval.setRange(0.01, 1000.0)
        self.spin_ta_regular_interval.setSingleStep(0.1)
        self.spin_ta_regular_interval.setValue(2.06)
        self.spin_ta_regular_interval.setDecimals(3)
        ta_params2.addWidget(QLabel("Interval (s)"))
        ta_params2.addWidget(self.spin_ta_regular_interval)

        self.spin_ta_window_size = QDoubleSpinBox()
        self.spin_ta_window_size.setRange(0.1, 100.0)
        self.spin_ta_window_size.setSingleStep(0.1)
        self.spin_ta_window_size.setValue(2.0)
        self.spin_ta_window_size.setDecimals(2)
        ta_params2.addWidget(QLabel("Window (s)"))
        ta_params2.addWidget(self.spin_ta_window_size)
        ta_params2.addStretch()
        ta_outer.addLayout(ta_params2)

        # Parameters row 3: window_offset
        ta_params3 = QHBoxLayout()
        self.spin_ta_window_offset = QDoubleSpinBox()
        self.spin_ta_window_offset.setRange(-10.0, 10.0)
        self.spin_ta_window_offset.setSingleStep(0.1)
        self.spin_ta_window_offset.setValue(0.75)
        self.spin_ta_window_offset.setDecimals(2)
        ta_params3.addWidget(QLabel("Offset (s)"))
        ta_params3.addWidget(self.spin_ta_window_offset)
        ta_params3.addStretch()
        ta_outer.addLayout(ta_params3)

        # Order buttons
        ta_order = QHBoxLayout()
        self.btn_time_avg_up = QPushButton("↑")
        self.btn_time_avg_down = QPushButton("↓")
        self.btn_time_avg_up.setMaximumWidth(30)
        self.btn_time_avg_down.setMaximumWidth(30)
        self.btn_time_avg_up.clicked.connect(lambda: self.move_up('time_avg'))
        self.btn_time_avg_down.clicked.connect(lambda: self.move_down('time_avg'))
        self.lbl_time_avg_order = QLabel("#0")
        self.lbl_time_avg_order.setMinimumWidth(25)
        ta_order.addWidget(QLabel("Order:"))
        ta_order.addWidget(self.lbl_time_avg_order)
        ta_order.addWidget(self.btn_time_avg_up)
        ta_order.addWidget(self.btn_time_avg_down)
        ta_order.addStretch()
        ta_outer.addLayout(ta_order)

        time_avg_group.setLayout(ta_outer)
        layout.addWidget(time_avg_group)

        # Peak Fitting controls
        fit_group = QGroupBox("Peak Fitting")
        fit_layout = QVBoxLayout()

        # Enable + Method
        fit_row1 = QHBoxLayout()
        self.chk_fitting = QCheckBox("Enable")
        self.combo_fit_method = QComboBox()
        self.combo_fit_method.addItems(["Gauss", "Voigt"])
        fit_row1.addWidget(self.chk_fitting)
        fit_row1.addWidget(QLabel("Method"))
        fit_row1.addWidget(self.combo_fit_method)
        fit_layout.addLayout(fit_row1)

        # Detection parameters
        fit_row2 = QHBoxLayout()
        self.spin_fit_prominence = QDoubleSpinBox()
        self.spin_fit_prominence.setRange(0.01, 1.0)
        self.spin_fit_prominence.setSingleStep(0.05)
        self.spin_fit_prominence.setValue(0.1)
        self.spin_fit_prominence.setDecimals(2)
        self.spin_fit_min_distance = QSpinBox()
        self.spin_fit_min_distance.setRange(1, 100)
        self.spin_fit_min_distance.setValue(10)
        fit_row2.addWidget(QLabel("Prominence"))
        fit_row2.addWidget(self.spin_fit_prominence)
        fit_row2.addWidget(QLabel("Min dist"))
        fit_row2.addWidget(self.spin_fit_min_distance)
        fit_layout.addLayout(fit_row2)

        # Visual indicators checkboxes
        fit_row_visual = QHBoxLayout()
        self.chk_show_peak_markers = QCheckBox("Show peak markers")
        self.chk_show_peak_markers.setChecked(True)  # Default: enabled
        self.chk_show_peak_numbers = QCheckBox("Show peak IDs")
        self.chk_show_peak_numbers.setChecked(True)  # Default: enabled
        fit_row_visual.addWidget(self.chk_show_peak_markers)
        fit_row_visual.addWidget(self.chk_show_peak_numbers)
        fit_layout.addLayout(fit_row_visual)

        # Results display (read-only)
        fit_row3 = QHBoxLayout()
        self.lbl_n_peaks = QLabel("Peaks: --")
        self.lbl_n_peaks.setStyleSheet("font-weight: normal;")
        self.btn_view_peaks = QPushButton("View Table")
        self.btn_view_peaks.setEnabled(False)
        self.btn_view_peaks.clicked.connect(self.show_peaks_table)
        fit_row3.addWidget(self.lbl_n_peaks)
        fit_row3.addWidget(self.btn_view_peaks)
        fit_layout.addLayout(fit_row3)

        fit_group.setLayout(fit_layout)
        layout.addWidget(fit_group)

        # Store peak results for table display
        self.current_fit_results = None

        # Bottom buttons
        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("Apply")
        self.btn_reset = QPushButton("Reset")
        self.btn_close = QPushButton("Close")
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        # Wire events for live updates
        for w in [self.chk_smooth, self.chk_outliers, self.chk_norm, self.chk_baseline,
                  self.chk_denoise_adv, self.chk_time_avg, self.chk_fitting,
                  self.chk_show_peak_markers, self.chk_show_peak_numbers]:
            w.stateChanged.connect(self.apply_settings)
        for w in [self.spin_window, self.spin_z, self.combo_norm,
                  self.spin_snip_K, self.combo_snip_transform,
                  self.spin_arpls_lambda, self.spin_asls_lambda, self.spin_asls_p,
                  self.spin_degree, self.spin_prominence,
                  self.combo_baseline_method,
                  self.combo_denoise_method,
                  self.spin_savgol_window, self.spin_savgol_polyorder,
                  self.spin_median_kernel,
                  self.combo_wavelet_type, self.combo_wavelet_mode,
                  self.spin_fft_cutoff,
                  self.combo_time_column, self.spin_ta_start, self.spin_ta_first_interval,
                  self.spin_ta_regular_interval, self.spin_ta_window_size, self.spin_ta_window_offset,
                  self.spin_fit_prominence, self.spin_fit_min_distance, self.combo_fit_method]:
            try:
                w.valueChanged.connect(self.apply_settings)
            except Exception:
                # QComboBox provides currentIndexChanged
                w.currentIndexChanged.connect(self.apply_settings)
        self.btn_apply.clicked.connect(self.apply_settings)
        self.btn_reset.clicked.connect(self.reset_settings)
        self.btn_close.clicked.connect(self.close)

        # Initialize button states
        self._update_order_buttons()

    def _get_app_and_pipeline(self):
        """Return the main app instance and its data pipeline.

        PlotWindow is created as a top-level window (parent=None) and stores a
        reference to the main app in `plot_win.app`. Using `plot_win.parent()`
        would therefore return None. This method prefers the explicit `app`
        attribute and falls back to the Qt parent only if needed.
        """
        plot_win = self.plot_window
        if not plot_win:
            return None, None

        # Prefer the explicit reference set by PlotWindow(__init__) via `app=`
        app = getattr(plot_win, 'app', None)
        if app is None:
            # Fallback to Qt parent if available (older behavior)
            app = plot_win.parent()

        pipeline = getattr(app, 'pipeline', None) if app else None
        return app, pipeline

    def populate_time_columns(self, available_columns):
        """
        Populate time column selector with ALL numeric columns.
        First column is selected by default (standard QComboBox behavior).
        User can manually select any column as time reference.

        Args:
            available_columns: List of column names from loaded data
        """
        # Block signals to prevent triggering apply_settings() during programmatic changes
        self.combo_time_column.blockSignals(True)

        self.combo_time_column.clear()

        if not available_columns:
            print(f"⚠️ [TIME-COLS] populate_time_columns received empty list")
            self.combo_time_column.blockSignals(False)  # Unblock before return
            return

        print(f"✅ [TIME-COLS] Populating dropdown with {len(available_columns)} columns")

        # Add all columns (assume numeric filtering done by caller)
        for col in available_columns:
            self.combo_time_column.addItem(col)

        # First column is auto-selected by QComboBox (index 0)
        # User can manually select any column - no automatic filtering by name

        # Unblock signals after modifications complete
        self.combo_time_column.blockSignals(False)

    def move_up(self, section):
        """Move a processing section up in the execution order."""
        idx = self.processing_order.index(section)
        if idx > 0:
            self.processing_order[idx], self.processing_order[idx - 1] = \
                self.processing_order[idx - 1], self.processing_order[idx]
            self._update_order_buttons()
            self.apply_settings()

    def move_down(self, section):
        """Move a processing section down in the execution order."""
        idx = self.processing_order.index(section)
        if idx < len(self.processing_order) - 1:
            self.processing_order[idx], self.processing_order[idx + 1] = \
                self.processing_order[idx + 1], self.processing_order[idx]
            self._update_order_buttons()
            self.apply_settings()

    def _update_order_buttons(self):
        """Enable/disable order buttons based on current position."""
        button_map = {
            'baseline': (self.btn_baseline_up, self.btn_baseline_down, self.lbl_baseline_order),
            'denoise_adv': (self.btn_denoise_up, self.btn_denoise_down, self.lbl_denoise_order),
            'time_avg': (self.btn_time_avg_up, self.btn_time_avg_down, self.lbl_time_avg_order),
            'smooth': (self.btn_smooth_up, self.btn_smooth_down, self.lbl_smooth_order),
            'outliers': (self.btn_outliers_up, self.btn_outliers_down, self.lbl_outliers_order),
            'normalize': (self.btn_normalize_up, self.btn_normalize_down, self.lbl_normalize_order)
        }

        for section, (btn_up, btn_down, lbl_order) in button_map.items():
            idx = self.processing_order.index(section)
            btn_up.setEnabled(idx > 0)
            btn_down.setEnabled(idx < len(self.processing_order) - 1)
            lbl_order.setText(f"#{idx + 1}")

    def _update_denoise_params_visibility(self):
        """Show/hide denoise parameters based on selected method."""
        method_idx = self.combo_denoise_method.currentIndex()

        # Hide all
        self.savgol_params.hide()
        self.median_params.hide()
        self.wavelet_params.hide()
        self.fft_params.hide()

        # Show selected
        if method_idx == 0:  # Savitzky-Golay
            self.savgol_params.show()
        elif method_idx == 1:  # Median Filter
            self.median_params.show()
        elif method_idx == 2:  # Wavelet
            self.wavelet_params.show()
        elif method_idx == 3:  # FFT Low-pass
            self.fft_params.show()

    def apply_settings(self):
        print(f"🟢 apply_settings() STARTED")
        app, pipeline = self._get_app_and_pipeline()
        if not app or not isinstance(pipeline, DataPipeline):
            return

        # Build processor definitions map
        processor_defs = {}

        baseline_x_col = None

        if self.chk_baseline.isChecked():
            method_text = self.combo_baseline_method.currentText()
            method = method_text.lower()
            params = {}
            if method == 'snip':
                params['K'] = int(self.spin_snip_K.value())
                params['transform'] = self.combo_snip_transform.currentText()
            elif method == 'arpls':
                params['lam'] = float(self.spin_arpls_lambda.value())
                params['niter'] = 15
            elif method == 'asls':
                params['lam'] = float(self.spin_asls_lambda.value())
                params['p'] = float(self.spin_asls_p.value())
                params['niter'] = 20
            elif method == 'polynomial':
                params['degree'] = int(self.spin_degree.value())
                params['prominence_factor'] = float(self.spin_prominence.value())

            try:
                xi = app.x_combo.currentIndex()
                x_col = app.x_combo.itemData(xi) if xi >= 0 else None
            except Exception:
                x_col = getattr(app.x_combo, 'currentText', lambda: None)()
            if x_col:
                baseline_x_col = x_col
                processor_defs['baseline'] = (
                    'baseline_live',
                    create_baseline_processor(x_col, method, params)
                )

        if self.chk_smooth.isChecked():
            processor_defs['smooth'] = (
                'smooth_live',
                create_smooth_processor(int(self.spin_window.value()))
            )

        if self.chk_outliers.isChecked():
            processor_defs['outliers'] = (
                'outliers_live',
                create_outliers_processor(float(self.spin_z.value()))
            )

        if self.chk_norm.isChecked():
            processor_defs['normalize'] = (
                'normalize_live',
                create_normalize_processor(self.combo_norm.currentText())
            )

        # Advanced denoising processor
        if self.chk_denoise_adv.isChecked():
            print(f"🟡 Advanced Denoising checkbox IS CHECKED")
            method_idx = self.combo_denoise_method.currentIndex()
            print(f"🟡 method_idx={method_idx}")
            if method_idx == 0:  # Savitzky-Golay
                params = {
                    'window': int(self.spin_savgol_window.value()),
                    'polyorder': int(self.spin_savgol_polyorder.value())
                }
                processor_defs['denoise_adv'] = (
                    'denoise_savgol',
                    create_denoise_processor('savgol', params)
                )
            elif method_idx == 1:  # Median Filter
                params = {'kernel_size': int(self.spin_median_kernel.value())}
                processor_defs['denoise_adv'] = (
                    'denoise_median',
                    create_denoise_processor('median', params)
                )
            elif method_idx == 2:  # Wavelet
                params = {
                    'wavelet': self.combo_wavelet_type.currentText(),
                    'mode': self.combo_wavelet_mode.currentText()
                }
                processor_defs['denoise_adv'] = (
                    'denoise_wavelet',
                    create_denoise_processor('wavelet', params)
                )
            elif method_idx == 3:  # FFT Low-pass
                params = {'cutoff_freq': float(self.spin_fft_cutoff.value())}
                processor_defs['denoise_adv'] = (
                    'denoise_fft',
                    create_denoise_processor('fft', params)
                )

        # Time-window averaging processor
        if self.chk_time_avg.isChecked():
            time_col = self.combo_time_column.currentText()
            if time_col:  # Only apply if time column selected
                processor_defs['time_avg'] = (
                    'time_avg_live',
                    create_time_averaging_processor(
                        time_column=time_col,
                        start_time=float(self.spin_ta_start.value()),
                        first_interval=float(self.spin_ta_first_interval.value()),
                        regular_interval=float(self.spin_ta_regular_interval.value()),
                        window_size=float(self.spin_ta_window_size.value()),
                        window_offset=float(self.spin_ta_window_offset.value())
                    )
                )

        # Peak fitting processor
        if self.chk_fitting.isChecked():
            method_text = self.combo_fit_method.currentText()
            method = method_text.lower()

            try:
                xi = app.x_combo.currentIndex()
                x_col = app.x_combo.itemData(xi) if xi >= 0 else None

                # Get Y column (prefer Y1, fallback to Y2)
                yi = app.y_list.currentIndex()
                y_col = app.y_list.itemData(yi) if yi >= 0 else None
                if not y_col:
                    y2i = app.y2_list.currentIndex()
                    y_col = app.y2_list.itemData(y2i) if y2i >= 0 else None
            except Exception:
                x_col = y_col = None

            if x_col and y_col:
                from data_pipeline import create_fit_multi_peaks_processor
                fit_params = {
                    'prominence': float(self.spin_fit_prominence.value()),
                    'min_distance': int(self.spin_fit_min_distance.value())
                }
                processor_defs['fitting'] = (
                    f'fit_{method}_live',
                    create_fit_multi_peaks_processor(x_col, y_col, method, **fit_params)
                )

        # Build steps list according to processing_order
        steps = []
        print(f"🔴 processor_defs keys: {list(processor_defs.keys())}")
        print(f"🔴 processing_order: {self.processing_order}")
        for section in self.processing_order:
            print(f"🔴 Checking section '{section}' in processor_defs: {section in processor_defs}")
            if section in processor_defs:
                name, func = processor_defs[section]
                pipeline.register_processor(name, func)
                steps.append(name)
                print(f"🔴 Added step '{name}'")

        pipeline.create_pipeline('current_pipeline', steps)
        print(f"⚫ Pipeline created with steps: {steps}")
        print(f"⚫ Verify: pipeline.pipelines['current_pipeline'] = {pipeline.pipelines.get('current_pipeline', 'NOT FOUND')}")
        self._update_order_buttons()

        settings_snapshot = self._collect_settings(baseline_x_col)
        if app and hasattr(app, 'set_processing_settings'):
            app.set_processing_settings(settings_snapshot, source='ui')

        # Update visual options in app
        if app:
            app.show_peak_markers = self.chk_show_peak_markers.isChecked()
            app.show_peak_numbers = self.chk_show_peak_numbers.isChecked()

        # Trigger redraw only if a valid plot selection exists
        try:
            has_files = bool(getattr(app.file_list, 'get_checked_items', lambda: [])())
            has_x = getattr(app.x_combo, 'count', lambda: 0)() > 0
            # New single-selection: consider selected if index >= 0
            # Consider selected only if current item has non-empty userData
            yi = getattr(app.y_list, 'currentIndex', lambda: -1)()
            y2i = getattr(app.y2_list, 'currentIndex', lambda: -1)()
            y_ok = (yi >= 0) and bool(app.y_list.itemData(yi))
            y2_ok = (y2i >= 0) and bool(app.y2_list.itemData(y2i))
            has_y = y_ok or y2_ok
            if has_files and has_x and has_y:
                app.plot_selected()
                # Update peak count after plotting if fitting is enabled
                self._update_peak_display()
        except Exception:
            # Silently ignore if plotting can't run (e.g., controls not ready)
            pass

    def reset_settings(self):
        # Uncheck all, reset values, clear pipeline
        self.processing_order = ['baseline', 'denoise_adv', 'smooth', 'outliers', 'normalize', 'fitting']
        self.chk_baseline.setChecked(False)
        self.chk_smooth.setChecked(False)
        self.chk_outliers.setChecked(False)
        self.chk_norm.setChecked(False)
        self.chk_denoise_adv.setChecked(False)
        self.chk_fitting.setChecked(False)
        # Baseline presets
        self.combo_baseline_method.setCurrentText('SNIP')
        self.spin_snip_K.setValue(12)
        self.combo_snip_transform.setCurrentText('sqrt')
        self.spin_arpls_lambda.setValue(1e6)
        self.spin_asls_lambda.setValue(1e6)
        self.spin_asls_p.setValue(1e-3)
        # Legacy polynomial
        self.spin_degree.setValue(3)
        self.spin_prominence.setValue(2.0)
        self.spin_window.setValue(5)
        self.spin_z.setValue(3.0)
        self.combo_norm.setCurrentText('minmax')
        # Advanced denoising presets
        self.combo_denoise_method.setCurrentIndex(0)  # Savitzky-Golay
        self.spin_savgol_window.setValue(11)
        self.spin_savgol_polyorder.setValue(3)
        self.spin_median_kernel.setValue(5)
        self.combo_wavelet_type.setCurrentIndex(0)  # db4
        self.combo_wavelet_mode.setCurrentIndex(0)  # soft
        self.spin_fft_cutoff.setValue(0.1)
        # Fitting presets
        self.combo_fit_method.setCurrentText('Gauss')
        self.spin_fit_prominence.setValue(0.1)
        self.spin_fit_min_distance.setValue(10)
        self.chk_show_peak_markers.setChecked(True)
        self.chk_show_peak_numbers.setChecked(True)
        self.lbl_n_peaks.setText("Peaks: --")
        self.lbl_n_peaks.setStyleSheet("font-weight: normal; color: black;")
        self.btn_view_peaks.setEnabled(False)
        self.current_fit_results = None

        app, pipeline = self._get_app_and_pipeline()
        settings_snapshot = self._collect_settings()
        if app and isinstance(pipeline, DataPipeline):
            pipeline.create_pipeline('current_pipeline', [])
            try:
                has_files = bool(getattr(app.file_list, 'get_checked_items', lambda: [])())
                has_x = getattr(app.x_combo, 'count', lambda: 0)() > 0
                yi = getattr(app.y_list, 'currentIndex', lambda: -1)()
                y2i = getattr(app.y2_list, 'currentIndex', lambda: -1)()
                y_ok = (yi >= 0) and bool(app.y_list.itemData(yi))
                y2_ok = (y2i >= 0) and bool(app.y2_list.itemData(y2i))
                has_y = y_ok or y2_ok
                if has_files and has_x and has_y:
                    app.plot_selected()
            except Exception:
                pass
            if hasattr(app, 'set_processing_settings'):
                app.set_processing_settings(settings_snapshot, source='ui')
        elif app and hasattr(app, 'set_processing_settings'):
            app.set_processing_settings(settings_snapshot, source='ui')

        self._update_order_buttons()

    def _collect_denoise_params(self):
        """Collect current denoise parameters based on selected method."""
        method_idx = self.combo_denoise_method.currentIndex()
        if method_idx == 0:  # Savitzky-Golay
            return {
                'window': int(self.spin_savgol_window.value()),
                'polyorder': int(self.spin_savgol_polyorder.value())
            }
        elif method_idx == 1:  # Median
            return {'kernel_size': int(self.spin_median_kernel.value())}
        elif method_idx == 2:  # Wavelet
            return {
                'wavelet': self.combo_wavelet_type.currentText(),
                'mode': self.combo_wavelet_mode.currentText()
            }
        elif method_idx == 3:  # FFT
            return {'cutoff_freq': float(self.spin_fft_cutoff.value())}
        return {}

    def _collect_settings(self, baseline_x_column=None):
        """Capture the current processing configuration."""
        settings = {
            'order': list(self.processing_order),
            'smooth': {
                'enabled': self.chk_smooth.isChecked(),
                'window': int(self.spin_window.value())
            },
            'outliers': {
                'enabled': self.chk_outliers.isChecked(),
                'threshold': float(self.spin_z.value())
            },
            'normalize': {
                'enabled': self.chk_norm.isChecked(),
                'method': self.combo_norm.currentText()
            },
            'denoise_adv': {
                'enabled': self.chk_denoise_adv.isChecked(),
                'method': self.combo_denoise_method.currentText(),
                'params': self._collect_denoise_params()
            },
            'time_avg': {
                'enabled': self.chk_time_avg.isChecked(),
                'time_column': self.combo_time_column.currentText(),
                'start_time': float(self.spin_ta_start.value()),
                'first_interval': float(self.spin_ta_first_interval.value()),
                'regular_interval': float(self.spin_ta_regular_interval.value()),
                'window_size': float(self.spin_ta_window_size.value()),
                'window_offset': float(self.spin_ta_window_offset.value()),
            },
            'baseline': {
                'enabled': self.chk_baseline.isChecked(),
                'method': self.combo_baseline_method.currentText(),
                'params': {},
                'x_column': baseline_x_column
            },
            'fitting': {
                'enabled': self.chk_fitting.isChecked(),
                'method': self.combo_fit_method.currentText(),
                'params': {
                    'prominence': float(self.spin_fit_prominence.value()),
                    'min_distance': int(self.spin_fit_min_distance.value())
                } if self.chk_fitting.isChecked() else {},
                'x_column': None,
                'y_column': None,
                'show_peak_markers': self.chk_show_peak_markers.isChecked(),
                'show_peak_numbers': self.chk_show_peak_numbers.isChecked()
            }
        }

        baseline_cfg = settings['baseline']
        if baseline_cfg['enabled']:
            method_lower = baseline_cfg['method'].lower()
            if baseline_x_column is None:
                app, _ = self._get_app_and_pipeline()
                if app:
                    try:
                        baseline_x_column = app.get_column_name(app.x_combo)
                    except Exception:
                        baseline_x_column = None
                baseline_cfg['x_column'] = baseline_x_column

            if method_lower == 'snip':
                baseline_cfg['params'] = {
                    'K': int(self.spin_snip_K.value()),
                    'transform': self.combo_snip_transform.currentText()
                }
            elif method_lower == 'arpls':
                baseline_cfg['params'] = {
                    'lam': float(self.spin_arpls_lambda.value()),
                    'niter': 15
                }
            elif method_lower == 'asls':
                baseline_cfg['params'] = {
                    'lam': float(self.spin_asls_lambda.value()),
                    'p': float(self.spin_asls_p.value()),
                    'niter': 20
                }
            elif method_lower == 'polynomial':
                baseline_cfg['params'] = {
                    'degree': int(self.spin_degree.value()),
                    'prominence_factor': float(self.spin_prominence.value())
                }
        else:
            baseline_cfg['params'] = {}
            baseline_cfg['x_column'] = None

        fitting_cfg = settings['fitting']
        if fitting_cfg['enabled']:
            method_text = fitting_cfg.get('method', '')
            fitting_cfg['method'] = method_text
            app, _ = self._get_app_and_pipeline()
            x_col = y_col = None
            if app:
                try:
                    xi = app.x_combo.currentIndex()
                    x_col = app.x_combo.itemData(xi) if xi >= 0 else None
                except Exception:
                    x_col = getattr(app.x_combo, 'currentText', lambda: None)()

                try:
                    yi = app.y_list.currentIndex()
                    y_col = app.y_list.itemData(yi) if yi >= 0 else None
                    if not y_col:
                        y2i = app.y2_list.currentIndex()
                        y_col = app.y2_list.itemData(y2i) if y2i >= 0 else None
                except Exception:
                    y_col = None

            fitting_cfg['x_column'] = x_col
            fitting_cfg['y_column'] = y_col
        else:
            fitting_cfg['params'] = {}
            fitting_cfg['x_column'] = None
            fitting_cfg['y_column'] = None

        return settings

    def load_settings(self, settings):
        """Restore the processing UI from a saved configuration."""
        if not settings:
            self.reset_settings()
            return

        widgets = [
            self.chk_baseline, self.chk_smooth, self.chk_outliers, self.chk_norm,
            self.chk_denoise_adv, self.chk_time_avg, self.chk_fitting,
            self.spin_window, self.spin_z, self.combo_norm,
            self.spin_snip_K, self.combo_snip_transform,
            self.spin_arpls_lambda,
            self.spin_asls_lambda, self.spin_asls_p,
            self.spin_degree, self.spin_prominence,
            self.combo_baseline_method,
            self.combo_denoise_method,
            self.spin_savgol_window, self.spin_savgol_polyorder,
            self.spin_median_kernel,
            self.combo_wavelet_type, self.combo_wavelet_mode,
            self.spin_fft_cutoff,
            self.combo_time_column, self.spin_ta_start, self.spin_ta_first_interval,
            self.spin_ta_regular_interval, self.spin_ta_window_size, self.spin_ta_window_offset,
            self.combo_fit_method,
            self.spin_fit_prominence, self.spin_fit_min_distance,
            self.chk_show_peak_markers, self.chk_show_peak_numbers
        ]
        previous_states = [w.blockSignals(True) for w in widgets]

        try:
            default_order = ['baseline', 'denoise_adv', 'time_avg', 'smooth', 'outliers', 'normalize', 'fitting']
            saved_order = settings.get('order', [])
            merged_order = [section for section in saved_order if section in default_order]
            for section in default_order:
                if section not in merged_order:
                    merged_order.append(section)
            self.processing_order = merged_order

            smooth_cfg = settings.get('smooth', {})
            self.chk_smooth.setChecked(bool(smooth_cfg.get('enabled')))
            self.spin_window.setValue(int(smooth_cfg.get('window', self.spin_window.value())))

            out_cfg = settings.get('outliers', {})
            self.chk_outliers.setChecked(bool(out_cfg.get('enabled')))
            self.spin_z.setValue(float(out_cfg.get('threshold', self.spin_z.value())))

            norm_cfg = settings.get('normalize', {})
            self.chk_norm.setChecked(bool(norm_cfg.get('enabled')))
            norm_method = norm_cfg.get('method')
            if norm_method:
                idx = self.combo_norm.findText(norm_method)
                if idx >= 0:
                    self.combo_norm.setCurrentIndex(idx)

            # Advanced denoising
            denoise_cfg = settings.get('denoise_adv', {})
            self.chk_denoise_adv.setChecked(bool(denoise_cfg.get('enabled')))
            denoise_method = denoise_cfg.get('method')
            if denoise_method:
                idx = self.combo_denoise_method.findText(denoise_method)
                if idx >= 0:
                    self.combo_denoise_method.setCurrentIndex(idx)

            denoise_params = denoise_cfg.get('params', {})
            # Restore parameters based on method
            if 'window' in denoise_params:  # Savitzky-Golay
                self.spin_savgol_window.setValue(int(denoise_params.get('window', self.spin_savgol_window.value())))
                self.spin_savgol_polyorder.setValue(int(denoise_params.get('polyorder', self.spin_savgol_polyorder.value())))
            if 'kernel_size' in denoise_params:  # Median
                self.spin_median_kernel.setValue(int(denoise_params.get('kernel_size', self.spin_median_kernel.value())))
            if 'wavelet' in denoise_params:  # Wavelet
                wavelet_idx = self.combo_wavelet_type.findText(denoise_params.get('wavelet', 'db4'))
                if wavelet_idx >= 0:
                    self.combo_wavelet_type.setCurrentIndex(wavelet_idx)
                mode_idx = self.combo_wavelet_mode.findText(denoise_params.get('mode', 'soft'))
                if mode_idx >= 0:
                    self.combo_wavelet_mode.setCurrentIndex(mode_idx)
            if 'cutoff_freq' in denoise_params:  # FFT
                self.spin_fft_cutoff.setValue(float(denoise_params.get('cutoff_freq', self.spin_fft_cutoff.value())))

            # Time-window averaging
            if 'time_avg' in settings:
                ta_settings = settings['time_avg']
                self.chk_time_avg.setChecked(ta_settings.get('enabled', False))

                # Restore time column selection
                time_col = ta_settings.get('time_column', '')
                if time_col:
                    idx = self.combo_time_column.findText(time_col)
                    if idx >= 0:
                        self.combo_time_column.setCurrentIndex(idx)

                self.spin_ta_start.setValue(ta_settings.get('start_time', 0.03))
                self.spin_ta_first_interval.setValue(ta_settings.get('first_interval', 1.03))
                self.spin_ta_regular_interval.setValue(ta_settings.get('regular_interval', 2.06))
                self.spin_ta_window_size.setValue(ta_settings.get('window_size', 2.0))
                self.spin_ta_window_offset.setValue(ta_settings.get('window_offset', 0.75))

            baseline_cfg = settings.get('baseline', {})
            self.chk_baseline.setChecked(bool(baseline_cfg.get('enabled')))
            method_text = baseline_cfg.get('method')
            if method_text:
                idx = self.combo_baseline_method.findText(method_text)
                if idx >= 0:
                    self.combo_baseline_method.setCurrentIndex(idx)

            params = baseline_cfg.get('params', {})
            method_lower = (method_text or '').lower()
            if method_lower == 'snip':
                self.spin_snip_K.setValue(int(params.get('K', self.spin_snip_K.value())))
                transform = params.get('transform', self.combo_snip_transform.currentText())
                transform_idx = self.combo_snip_transform.findText(transform)
                if transform_idx >= 0:
                    self.combo_snip_transform.setCurrentIndex(transform_idx)
            elif method_lower == 'arpls':
                self.spin_arpls_lambda.setValue(float(params.get('lam', self.spin_arpls_lambda.value())))
            elif method_lower == 'asls':
                self.spin_asls_lambda.setValue(float(params.get('lam', self.spin_asls_lambda.value())))
                self.spin_asls_p.setValue(float(params.get('p', self.spin_asls_p.value())))
            elif method_lower == 'polynomial':
                self.spin_degree.setValue(int(params.get('degree', self.spin_degree.value())))
                self.spin_prominence.setValue(float(params.get('prominence_factor', self.spin_prominence.value())))

            fitting_cfg = settings.get('fitting', {})
            self.chk_fitting.setChecked(bool(fitting_cfg.get('enabled')))
            fit_method = fitting_cfg.get('method')
            if fit_method:
                idx = self.combo_fit_method.findText(fit_method)
                if idx >= 0:
                    self.combo_fit_method.setCurrentIndex(idx)

            fit_params = fitting_cfg.get('params', {})
            if fit_params:
                self.spin_fit_prominence.setValue(float(fit_params.get('prominence', self.spin_fit_prominence.value())))
                self.spin_fit_min_distance.setValue(int(fit_params.get('min_distance', self.spin_fit_min_distance.value())))

            if 'show_peak_markers' in fitting_cfg:
                self.chk_show_peak_markers.setChecked(bool(fitting_cfg.get('show_peak_markers')))
            if 'show_peak_numbers' in fitting_cfg:
                self.chk_show_peak_numbers.setChecked(bool(fitting_cfg.get('show_peak_numbers')))
        finally:
            for widget, previous_state in zip(widgets, previous_states):
                widget.blockSignals(previous_state)

        self._update_order_buttons()
        self.apply_settings()

    def _update_peak_display(self):
        """Update peak count display from last processed data with color feedback"""
        if not self.chk_fitting.isChecked():
            self.lbl_n_peaks.setText("Peaks: --")
            self.lbl_n_peaks.setStyleSheet("font-weight: normal; color: black;")
            self.btn_view_peaks.setEnabled(False)
            return

        app, _ = self._get_app_and_pipeline()
        if not app:
            return

        # Get fit results from the last processed data stored in app
        try:
            if hasattr(app, 'last_fit_results') and app.last_fit_results:
                fit_res = app.last_fit_results
                n_peaks = fit_res.get('n_peaks', 0)
                self.current_fit_results = fit_res

                # Color feedback based on peak count
                if n_peaks == 0:
                    self.lbl_n_peaks.setText("Peaks: 0 (none detected)")
                    self.lbl_n_peaks.setStyleSheet("font-weight: bold; color: orange;")
                    self.btn_view_peaks.setEnabled(False)
                else:
                    self.lbl_n_peaks.setText(f"Peaks: {n_peaks}")
                    self.lbl_n_peaks.setStyleSheet("font-weight: bold; color: green;")
                    self.btn_view_peaks.setEnabled(True)
            else:
                self.lbl_n_peaks.setText("Peaks: --")
                self.lbl_n_peaks.setStyleSheet("font-weight: normal; color: black;")
                self.btn_view_peaks.setEnabled(False)
        except Exception:
            self.lbl_n_peaks.setText("Peaks: --")
            self.lbl_n_peaks.setStyleSheet("font-weight: normal; color: black;")
            self.btn_view_peaks.setEnabled(False)

    def show_peaks_table(self):
        """Display peak results in a table dialog"""
        if not self.current_fit_results:
            return

        from peak_results_dialog import PeakResultsDialog
        dialog = PeakResultsDialog(self.current_fit_results, self)
        dialog.exec_()
