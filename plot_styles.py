from matplotlib.ticker import MultipleLocator

# Default style settings
DEFAULT_STYLE_SETTINGS = {
    'legend_location': 'best',
    'legend_fontfamily': 'sans-serif',
    'legend_fontsize': 10,
    'legend_columns': 1,
    'axes_fontfamily': 'sans-serif',
    'axes_fontsize': 10,
    'title_fontfamily': 'sans-serif',
    'title_fontsize': 12,
    'title_text': '',
    'x_axis_title': '',
    'y_axis_title': '',
    'y2_axis_title': '',
    'use_axis_limits': False,
    'use_y2_axis_limits': False,
    'auto_scale': True,
    'x_scale': 'linear',
    'y_scale': 'linear',
    'y2_scale': 'linear',
    'x_min': None,
    'x_max': None,
    'y_min': None,
    'y_max': None,
    'y2_min': None,
    'y2_max': None,
    'line_width': 0.1,
    'plot_width': 800,
    'plot_height': 800,
    # Grid settings
    'x_major_grid': True,
    'x_minor_grid': False,
    'y_major_grid': True,
    'y_minor_grid': False,
    'major_grid_style': '--',
    'minor_grid_style': ':',
    'major_grid_alpha': 0.5,
    'minor_grid_alpha': 0.2,
    'major_grid_width': 0.5,
    'minor_grid_width': 0.5,
    'x_major_spacing': None,
    'x_minor_spacing': None,
    'y_major_spacing': None,
    'y_minor_spacing': None,
    'grid_color': '#808080',
    # Peak fitting visual settings
    'show_peak_markers': True,
    'show_peak_numbers': True,
}

def apply_plot_styles(canvas):
    """Apply all plot styles to the canvas"""
    _apply_axis_styles(canvas)
    _apply_grid_settings(canvas)
    _apply_title_style(canvas)
    _update_legend(canvas)
    
    # Apply axis scales
    canvas.ax.set_xscale(canvas.plot_style.get('x_scale', 'linear'))
    canvas.ax.set_yscale(canvas.plot_style.get('y_scale', 'linear'))
    
    # Apply Y2 axis scale if ax2 exists
    if hasattr(canvas, 'ax2') and canvas.ax2:
        canvas.ax2.set_yscale(canvas.plot_style.get('y2_scale', 'linear'))
    
    # Apply axis limits if enabled and not auto-scaling
    if not canvas.plot_style.get('auto_scale', True):
        if canvas.plot_style.get('use_axis_limits'):
            if canvas.plot_style.get('x_min') is not None and canvas.plot_style.get('x_max') is not None:
                canvas.ax.set_xlim(canvas.plot_style['x_min'], canvas.plot_style['x_max'])
            if canvas.plot_style.get('y_min') is not None and canvas.plot_style.get('y_max') is not None:
                canvas.ax.set_ylim(canvas.plot_style['y_min'], canvas.plot_style['y_max'])
        
        # Apply Y2 axis limits if enabled and ax2 exists
        if canvas.plot_style.get('use_y2_axis_limits') and hasattr(canvas, 'ax2') and canvas.ax2:
            if canvas.plot_style.get('y2_min') is not None and canvas.plot_style.get('y2_max') is not None:
                canvas.ax2.set_ylim(canvas.plot_style['y2_min'], canvas.plot_style['y2_max'])

def _apply_axis_styles(canvas):
    """Apply font styles to axis labels and ticks"""
    font_props = {
        'family': canvas.plot_style['axes_fontfamily'],
        'size': canvas.plot_style['axes_fontsize']
    }
    
    # Apply to x and y axis labels
    canvas.ax.xaxis.label.set_fontfamily(font_props['family'])
    canvas.ax.xaxis.label.set_fontsize(font_props['size'])
    canvas.ax.yaxis.label.set_fontfamily(font_props['family'])
    canvas.ax.yaxis.label.set_fontsize(font_props['size'])
    
    # Apply to Y2 axis if it exists
    if hasattr(canvas, 'ax2') and canvas.ax2:
        canvas.ax2.yaxis.label.set_fontfamily(font_props['family'])
        canvas.ax2.yaxis.label.set_fontsize(font_props['size'])
    
    # Apply to tick labels
    canvas.ax.tick_params(axis='both', which='major', labelsize=font_props['size'])
    for tick in canvas.ax.get_xticklabels():
        tick.set_fontfamily(font_props['family'])
    for tick in canvas.ax.get_yticklabels():
        tick.set_fontfamily(font_props['family'])
    
    # Apply to Y2 tick labels if ax2 exists
    if hasattr(canvas, 'ax2') and canvas.ax2:
        canvas.ax2.tick_params(axis='y', which='major', labelsize=font_props['size'])
        for tick in canvas.ax2.get_yticklabels():
            tick.set_fontfamily(font_props['family'])

    # Ensure axis title texts are present after layout rebuilds
    # Only set when non-empty in style to avoid clearing data-derived labels
    try:
        style = canvas.plot_style
        if style.get('x_axis_title'):
            canvas.ax.set_xlabel(style['x_axis_title'])
        if style.get('y_axis_title'):
            canvas.ax.set_ylabel(style['y_axis_title'])
        if hasattr(canvas, 'ax2') and canvas.ax2 and style.get('y2_axis_title'):
            canvas.ax2.set_ylabel(style['y2_axis_title'])
    except Exception:
        pass

def _apply_grid_settings(canvas):
    """Apply grid settings to the plot"""
    # Clear existing grid with single call (more efficient than 3 separate calls)
    canvas.ax.grid(False, which='both')

    style = canvas.plot_style
    
    # Only proceed if any grid is enabled
    if not any([style['x_major_grid'], style['x_minor_grid'],
                style['y_major_grid'], style['y_minor_grid']]):
        return
        
    # Setup minor ticks if needed
    if style['x_minor_grid'] or style['y_minor_grid']:
        canvas.ax.minorticks_on()
    else:
        canvas.ax.minorticks_off()
    
    # Major grid settings
    if style['x_major_grid'] or style['y_major_grid']:
        if style['x_major_grid']:
            canvas.ax.xaxis.grid(True, which='major',
                            linestyle=style['major_grid_style'],
                            alpha=style['major_grid_alpha'],
                            linewidth=style['major_grid_width'],
                            color=style['grid_color'])
            
        if style['y_major_grid']:
            canvas.ax.yaxis.grid(True, which='major',
                            linestyle=style['major_grid_style'],
                            alpha=style['major_grid_alpha'],
                            linewidth=style['major_grid_width'],
                            color=style['grid_color'])
    
    # Minor grid settings
    if style['x_minor_grid'] or style['y_minor_grid']:
        if style['x_minor_grid']:
            canvas.ax.xaxis.grid(True, which='minor',
                            linestyle=style['minor_grid_style'],
                            alpha=style['minor_grid_alpha'],
                            linewidth=style['minor_grid_width'],
                            color=style['grid_color'])
            
        if style['y_minor_grid']:
            canvas.ax.yaxis.grid(True, which='minor',
                            linestyle=style['minor_grid_style'],
                            alpha=style['minor_grid_alpha'],
                            linewidth=style['minor_grid_width'],
                            color=style['grid_color'])
        
    # Apply custom tick spacing if specified
    if style['x_major_spacing']:
        canvas.ax.xaxis.set_major_locator(MultipleLocator(style['x_major_spacing']))
    if style['x_minor_spacing']:
        canvas.ax.xaxis.set_minor_locator(MultipleLocator(style['x_minor_spacing']))
    if style['y_major_spacing']:
        canvas.ax.yaxis.set_major_locator(MultipleLocator(style['y_major_spacing']))
    if style['y_minor_spacing']:
        canvas.ax.yaxis.set_minor_locator(MultipleLocator(style['y_minor_spacing']))

def _apply_title_style(canvas):
    """Apply font styles to plot title"""
    style = canvas.plot_style
    if style['title_text']:
        canvas.ax.set_title(
            style['title_text'],
            fontfamily=style['title_fontfamily'],
            fontsize=style['title_fontsize']
        )

def _update_legend(canvas):
    """Create or update the legend with current style settings.

    Uses matplotlib's modern 'outside' locations with constrained_layout
    (matplotlib >= 3.6) for clean legend placement without manual GridSpec.
    """
    from app_logging import logger

    # Check if we have any lines to show in legend
    has_left_lines = hasattr(canvas, 'plotted_lines') and canvas.plotted_lines
    has_right_lines = hasattr(canvas, 'plotted_lines_right') and canvas.plotted_lines_right

    if not has_left_lines and not has_right_lines:
        return
    if not hasattr(canvas, 'legend_labels') or not canvas.legend_labels:
        return

    style = canvas.plot_style
    loc = style.get('legend_location', 'best')
    ncol = style.get('legend_columns', 1)

    logger.debug(f"🟡 _update_legend: loc='{loc}', ncol={ncol}")

    # Map custom locations to matplotlib's 'outside' syntax (requires constrained_layout)
    LOCATION_MAP = {
        'outside_right': 'outside right center',
        'outside_left': 'outside left center',
        'outside_top': 'outside upper center',
        'outside_bottom': 'outside lower center',
    }

    # Special locations that need bbox_to_anchor
    BBOX_LOCATIONS = {
        'below_title': ('upper center', (0.5, 1.05)),
        'below_xaxis': ('lower center', (0.5, -0.15)),
    }

    font_props = {
        'family': style.get('legend_fontfamily', 'sans-serif'),
        'size': style.get('legend_fontsize', 10)
    }

    legend_line_width = 2

    # Collect all lines and labels from both axes
    all_lines = []
    if has_left_lines:
        all_lines.extend(canvas.plotted_lines)
    if has_right_lines:
        all_lines.extend(canvas.plotted_lines_right)

    all_labels = canvas.legend_labels[:len(all_lines)]

    # Store original line widths
    original_line_widths = {i: line.get_linewidth() for i, line in enumerate(all_lines)}
    for line in all_lines:
        line.set_linewidth(legend_line_width)

    # Remove any existing legends to avoid duplicates
    for leg in canvas.fig.legends:
        leg.remove()
    if canvas.ax.get_legend():
        canvas.ax.get_legend().remove()
    if hasattr(canvas, 'ax2') and canvas.ax2 and canvas.ax2.get_legend():
        canvas.ax2.get_legend().remove()

    legend = None

    # Determine legend placement
    if loc in LOCATION_MAP:
        # Use matplotlib's modern 'outside' locations (figure legend)
        mapped_loc = LOCATION_MAP[loc]
        logger.debug(f"🟡 Using fig.legend with loc='{mapped_loc}'")
        legend = canvas.fig.legend(
            all_lines,
            all_labels,
            loc=mapped_loc,
            ncol=ncol,
            prop=font_props,
            frameon=True,
        )
    elif loc in BBOX_LOCATIONS:
        # Special locations with bbox_to_anchor
        mpl_loc, bbox = BBOX_LOCATIONS[loc]
        logger.debug(f"🟡 Using ax.legend with loc='{mpl_loc}', bbox={bbox}")
        legend = canvas.ax.legend(
            all_lines,
            all_labels,
            loc=mpl_loc,
            bbox_to_anchor=bbox,
            ncol=ncol,
            prop=font_props,
        )
    else:
        # Standard matplotlib locations (inside plot)
        logger.debug(f"🟡 Using ax.legend with loc='{loc}'")
        legend = canvas.ax.legend(
            all_lines,
            all_labels,
            loc=loc,
            ncol=ncol,
            prop=font_props,
        )

    # Restore original line widths
    for i, line in enumerate(all_lines):
        if i in original_line_widths:
            line.set_linewidth(original_line_widths[i])

    # Make legend lines thicker
    if legend:
        for legline in legend.get_lines():
            legline.set_linewidth(legend_line_width)

    logger.debug(f"✅ Legend updated successfully")
