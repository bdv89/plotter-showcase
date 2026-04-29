import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QSizePolicy
from plot_styles import DEFAULT_STYLE_SETTINGS, apply_plot_styles
from app_logging import logger

class PlotCanvas(FigureCanvas):
    """Matplotlib widget for plotting graphs"""

    def __init__(self, parent=None, width=5, height=4, dpi=100, constrained_layout=True):
        # Use constrained_layout=True by default for proper 'outside' legend support
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi, layout='constrained')
        super().__init__(self.fig)
        self.setParent(parent)

        # Default DPI (used for size conversion)
        self.default_dpi = dpi

        # Secondary Y axis (created on demand)
        self.ax2 = None

        FigureCanvas.setSizePolicy(self,
                                 QSizePolicy.Expanding,
                                 QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self.plotted_lines = []
        self.plotted_lines_right = []  # Lines on right axis
        self.legend_labels = []

        # Initialize with default style settings
        self.plot_style = DEFAULT_STYLE_SETTINGS.copy()

        # Style caching for performance
        self._cached_style_hash = None

        # Defer drawing flag - when True, draw calls are skipped until flag is reset
        self._defer_drawing = False

        # Display size locking (UI): when True, the Qt widget keeps a
        # fixed pixel size equal to plot_width/plot_height.
        self._lock_display_size = False

    def plot_data(self, df, x_col, y_col, label=None, clear_first=True, line_style='-', color=None, use_right_axis=False, defer_draw=True, **kwargs):
        """Plot data from dataframe."""
        logger.debug(f"[DEBUG] plot_canvas.plot_data: x_col='{x_col}', y_col='{y_col}', label='{label}'")
        logger.debug(f"[DEBUG] plot_canvas.plot_data: df.shape={df.shape}, df.columns={list(df.columns)[:10]}...")

        if clear_first:
            self.clear_plot()

        # Create secondary axis if needed and not exists
        if use_right_axis and self.ax2 is None:
            self.ax2 = self.ax.twinx()

        # Choose which axis to plot on
        axis = self.ax2 if use_right_axis else self.ax

        line_width = self.plot_style.get('line_width', 1.0)

        # Debug: verify columns exist
        if x_col not in df.columns:
            logger.error(f"[ERROR] plot_canvas: x_col '{x_col}' NOT in DataFrame columns!")
            logger.error(f"[ERROR] Available columns: {list(df.columns)}")
        if y_col not in df.columns:
            logger.error(f"[ERROR] plot_canvas: y_col '{y_col}' NOT in DataFrame columns!")
            logger.error(f"[ERROR] Available columns: {list(df.columns)}")

        x_data = df[x_col]
        y_data = df[y_col]
        logger.debug(f"[DEBUG] plot_canvas: x_data type={type(x_data.iloc[0]) if len(x_data) > 0 else 'empty'}, range={x_data.min()} to {x_data.max()}")
        logger.debug(f"[DEBUG] plot_canvas: y_data type={type(y_data.iloc[0]) if len(y_data) > 0 else 'empty'}, range={y_data.min()} to {y_data.max()}")

        line, = axis.plot(x_data, y_data, linestyle=line_style, color=color,
                         label=label, linewidth=line_width)

        # Track lines by axis
        if use_right_axis:
            self.plotted_lines_right.append(line)
        else:
            self.plotted_lines.append(line)

        # Plot fitted curve if present (from peak fitting)
        if hasattr(df, 'attrs') and 'fit_results' in df.attrs:
            fit_results = df.attrs['fit_results']
            method = fit_results.get('method', 'gauss')
            fit_col = f'{method}_fit'
            if fit_col in df.columns:
                # Plot fitted curve as dashed line with same color but slightly transparent
                fit_line, = axis.plot(
                    df[x_col], df[fit_col],
                    linestyle='--',
                    color=color if color else line.get_color(),
                    alpha=0.7,
                    linewidth=line_width * 0.8,
                    label=f"{label} (fit)" if label else "fit"
                )
                # Track fit line too
                if use_right_axis:
                    self.plotted_lines_right.append(fit_line)
                else:
                    self.plotted_lines.append(fit_line)

                # Add visual indicators for peaks (markers and annotations)
                self._add_peak_visual_indicators(
                    axis, df, x_col, fit_results,
                    color if color else line.get_color()
                )
            
        if label:
            self.legend_labels.append(label)
        
        # Set axis titles
        x_title = self.plot_style.get('x_axis_title') or x_col
        self.ax.set_xlabel(x_title)

        logger.debug(f"[DEBUG plot_canvas] Setting X axis label to: '{x_title}' (from col: '{x_col}')")

        if not use_right_axis:
            y_title = self.plot_style.get('y_axis_title') or y_col
            self.ax.set_ylabel(y_title)
            logger.debug(f"[DEBUG plot_canvas] Setting Y axis label to: '{y_title}' (from col: '{y_col}')")
        else:
            y2_title = self.plot_style.get('y2_axis_title') or y_col
            if self.ax2:
                self.ax2.set_ylabel(y2_title)
                logger.debug(f"[DEBUG plot_canvas] Setting Y2 axis label to: '{y2_title}' (from col: '{y_col}')")
        
        # Apply all plot styles
        apply_plot_styles(self)

        # Let constrained_layout handle spacing; avoid tight_layout to prevent conflicts

        self._update_figure_size()
        if not defer_draw:
            self.draw_idle()  # Non-blocking draw for better UI responsiveness
            # Réappliquer les pickers après le dessin pour l'édition interactive
            self._reapply_pickers_if_needed()

    def clear_plot(self):
        """Clear all plot contents"""
        self.ax.clear()
        if self.ax2:
            self.ax2.clear()
            # Don't destroy ax2, keep it for reuse
        self.plotted_lines = []
        self.plotted_lines_right = []
        self.legend_labels = []
        # Clear figure legends
        for leg in self.fig.legends:
            leg.remove()
        if not getattr(self, '_defer_drawing', False):
            self.draw_idle()  # Non-blocking draw for better UI responsiveness
            # Réappliquer les pickers après le dessin
            self._reapply_pickers_if_needed()
    
    def set_plot_style(self, style_dict):
        """Update the plot style settings with caching optimization"""
        # Calculate hash of new style settings
        try:
            new_style_hash = hash(frozenset(style_dict.items()))
        except TypeError:
            # Fallback for unhashable values
            new_style_hash = hash(str(sorted(style_dict.items())))

        # Skip if identical to cached style
        if new_style_hash == self._cached_style_hash:
            return

        # Store old style for comparison
        old_style = self.plot_style.copy() if hasattr(self, 'plot_style') else {}

        # Replace the entire plot_style dict instead of updating it
        self.plot_style = style_dict.copy()

        if hasattr(self, 'ax'):
            # Apply selective styles based on what changed
            self._apply_styles_selective(old_style, style_dict)

            # Update any plotted lines if present
            line_width = self.plot_style.get('line_width', 1.0)
            for line in self.plotted_lines:
                line.set_linewidth(line_width)
            for line in self.plotted_lines_right:
                line.set_linewidth(line_width)

            # Update figure size if needed
            if 'plot_width' in style_dict or 'plot_height' in style_dict:
                self._update_figure_size()

            # Cache the new style hash
            self._cached_style_hash = new_style_hash
            if not getattr(self, '_defer_drawing', False):
                self.draw_idle()  # Non-blocking draw for better UI responsiveness
                # Réappliquer les pickers après le dessin
                self._reapply_pickers_if_needed()
    
    def set_title(self, title_text):
        """Set the plot title"""
        self.plot_style['title_text'] = title_text
        apply_plot_styles(self)
        if not getattr(self, '_defer_drawing', False):
            self.draw_idle()  # Non-blocking draw for better UI responsiveness

    def _update_figure_size(self):
        """Update the figure size based on plot_style settings.
        Always enforce the overall figure to exactly plot_width x plot_height (in px),
        without auto-expanding for outside legends. This keeps the canvas at a
        deterministic 800x800 by default.
        """
        width_px = int(self.plot_style.get('plot_width', 800))
        height_px = int(self.plot_style.get('plot_height', 800))

        width_in = width_px / float(self.default_dpi)
        height_in = height_px / float(self.default_dpi)

        # Enforce exact figure size
        self.fig.set_size_inches(width_in, height_in)

        # If display locking is enabled, enforce the widget size too
        if getattr(self, '_lock_display_size', False):
            try:
                self.setFixedSize(width_px, height_px)
                self.updateGeometry()  # Notify parent (QScrollArea) of size change
            except Exception:
                pass

    def _apply_styles_selective(self, old_style, new_style):
        """Apply only the style components that have changed"""
        from plot_styles import _apply_axis_styles, _apply_grid_settings, _apply_title_style, _update_legend

        # Check what changed and apply selectively
        grid_changed = self._grid_settings_changed(old_style, new_style)
        axis_changed = self._axis_settings_changed(old_style, new_style)
        title_changed = old_style.get('title_text') != new_style.get('title_text')
        legend_changed = self._legend_settings_changed(old_style, new_style)

        if grid_changed:
            _apply_grid_settings(self)

        if axis_changed:
            _apply_axis_styles(self)
            # Apply axis scales and limits
            self.ax.set_xscale(self.plot_style.get('x_scale', 'linear'))
            self.ax.set_yscale(self.plot_style.get('y_scale', 'linear'))

            if hasattr(self, 'ax2') and self.ax2:
                self.ax2.set_yscale(self.plot_style.get('y2_scale', 'linear'))

            # Apply axis limits if enabled and not auto-scaling
            if not self.plot_style.get('auto_scale', True):
                if self.plot_style.get('use_axis_limits'):
                    if self.plot_style.get('x_min') is not None and self.plot_style.get('x_max') is not None:
                        self.ax.set_xlim(self.plot_style['x_min'], self.plot_style['x_max'])
                    if self.plot_style.get('y_min') is not None and self.plot_style.get('y_max') is not None:
                        self.ax.set_ylim(self.plot_style['y_min'], self.plot_style['y_max'])

                if self.plot_style.get('use_y2_axis_limits') and hasattr(self, 'ax2') and self.ax2:
                    if self.plot_style.get('y2_min') is not None and self.plot_style.get('y2_max') is not None:
                        self.ax2.set_ylim(self.plot_style['y2_min'], self.plot_style['y2_max'])

        if title_changed:
            _apply_title_style(self)

        if legend_changed:
            _update_legend(self)

    def _grid_settings_changed(self, old_style, new_style):
        """Check if grid-related settings have changed"""
        grid_keys = ['x_major_grid', 'x_minor_grid', 'y_major_grid', 'y_minor_grid',
                     'major_grid_style', 'minor_grid_style', 'major_grid_alpha', 'minor_grid_alpha',
                     'major_grid_width', 'minor_grid_width', 'x_major_spacing', 'x_minor_spacing',
                     'y_major_spacing', 'y_minor_spacing', 'grid_color']

        for key in grid_keys:
            if old_style.get(key) != new_style.get(key):
                return True
        return False

    def _axis_settings_changed(self, old_style, new_style):
        """Check if axis-related settings have changed"""
        axis_keys = ['axes_fontfamily', 'axes_fontsize', 'x_scale', 'y_scale', 'y2_scale',
                     'use_axis_limits', 'use_y2_axis_limits', 'auto_scale',
                     'x_min', 'x_max', 'y_min', 'y_max', 'y2_min', 'y2_max',
                     'x_axis_title', 'y_axis_title', 'y2_axis_title']

        for key in axis_keys:
            if old_style.get(key) != new_style.get(key):
                return True
        return False

    def _legend_settings_changed(self, old_style, new_style):
        """Check if legend-related settings have changed"""
        legend_keys = ['legend_location', 'legend_fontfamily', 'legend_fontsize', 'legend_columns']

        for key in legend_keys:
            if old_style.get(key) != new_style.get(key):
                return True
        return False

    def set_lock_display_size(self, lock: bool):
        """Lock/unlock the Qt widget display size to plot_width/height.
        When unlocked, the canvas uses Expanding policies and follows the window.
        """
        from PyQt5.QtWidgets import QSizePolicy

        self._lock_display_size = bool(lock)
        if self._lock_display_size:
            # Apply fixed widget size according to current plot_style
            self._update_figure_size()
            FigureCanvas.setSizePolicy(self, QSizePolicy.Fixed, QSizePolicy.Fixed)
            FigureCanvas.updateGeometry(self)  # Notify parent (QScrollArea) of size change
        else:
            # Restore expanding behavior
            FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
            FigureCanvas.updateGeometry(self)
        self.update()

    def _add_peak_visual_indicators(self, axis, df, x_col, fit_results, base_color):
        """Add visual indicators for detected peaks (markers and annotations)

        Args:
            axis: Matplotlib axis to plot on
            df: DataFrame containing the data
            x_col: X column name
            fit_results: Dict containing peak fitting results
            base_color: Base color for the indicators
        """
        # Get settings from plot_style (no parent traversal needed)
        show_markers = self.plot_style.get('show_peak_markers', True)
        show_numbers = self.plot_style.get('show_peak_numbers', True)

        peaks = fit_results.get('peaks', [])
        if not peaks:
            return

        # Extract peak positions and amplitudes
        peak_positions = [p.get('2theta') for p in peaks]
        peak_amplitudes = [p.get('amplitude') for p in peaks]

        # Add red dots on peaks
        if show_markers:
            axis.scatter(
                peak_positions,
                peak_amplitudes,
                color='red',
                marker='o',
                s=50,  # Size
                alpha=0.8,
                zorder=10,  # Draw on top
                edgecolors='darkred',
                linewidths=1.5
            )

        # Add peak ID annotations
        if show_numbers:
            for peak in peaks:
                peak_id = peak.get('peak_id')
                peak_x = peak.get('2theta')
                peak_y = peak.get('amplitude')

                # Add text annotation above the peak
                axis.annotate(
                    f"{peak_id}",
                    xy=(peak_x, peak_y),
                    xytext=(0, 12),  # 12 points above the peak
                    textcoords='offset points',
                    ha='center',
                    va='bottom',
                    fontsize=9,
                    color='red',
                    weight='bold',
                    bbox=dict(
                        boxstyle='round,pad=0.3',
                        facecolor='white',
                        edgecolor='red',
                        alpha=0.8,
                        linewidth=1
                    )
                )

    def _reapply_pickers_if_needed(self):
        """Réappliquer les pickers pour l'édition interactive si configuré"""
        try:
            # Import dynamique pour éviter les dépendances circulaires
            from plot_interactive_edit import reapply_pickers
            reapply_pickers(self)
        except ImportError:
            # Si le module n'est pas disponible, on ignore silencieusement
            pass
        except Exception:
            # Toute autre erreur est ignorée pour ne pas casser le plotting
            pass
