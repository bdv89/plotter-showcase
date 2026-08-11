"""Pydantic models for the CSV Plotter web API."""

from typing import Optional

from pydantic import BaseModel


class FileInfo(BaseModel):
    file_id: str = ""
    filename: str
    columns: list[str] = []
    row_count: int = 0
    error: Optional[str] = None


class PlotRequest(BaseModel):
    file_ids: list[str]
    x_column: str
    y_columns: list[str]
    y2_columns: list[str] = []
    # Session-wide ProcessingSettings, applied inline when building the traces.
    # A field the frontend sends but that is NOT declared here is dropped
    # silently by Pydantic — that is how processing used to be ignored.
    processing: dict = {}


class PlotTrace(BaseModel):
    x: list
    y: list
    name: str
    yaxis: str = "y"
    file_id: str = ""


class PlotDataResponse(BaseModel):
    traces: list[PlotTrace] = []


class ExtractRequest(BaseModel):
    file_id: str
    column: str
    operation: str
    processing: dict = {}  # same settings as PlotRequest: extract what is plotted
    x_column: Optional[str] = None
    x_value: Optional[float] = None
    x_min: Optional[float] = None  # borne basse de l'intervalle X (filtre optionnel)
    x_max: Optional[float] = None  # borne haute de l'intervalle X (filtre optionnel)
    precision: int = 6
    condition_column: Optional[str] = None
    threshold: Optional[float] = None
    operator: Optional[str] = None
    fallback_type: str = "none"
    fallback_value: Optional[float] = None


class ExtractRemoveRequest(BaseModel):
    # None → efface toutes les colonnes extraites ; sinon retire cette colonne.
    column_name: Optional[str] = None


class PoolSaveRequest(BaseModel):
    path: str = ""
    styles: dict = {}
    plot_style: dict = {}
    processing: dict = {}
    x_column: str = ""
    y_columns: list = []
    y2_columns: list = []


class StyleSettings(BaseModel):
    legend_location: str = "best"
    legend_fontfamily: str = "sans-serif"
    legend_fontsize: int = 12
    legend_columns: int = 1
    axes_fontfamily: str = "sans-serif"
    axes_fontsize: int = 10
    title_fontfamily: str = "sans-serif"
    title_fontsize: int = 16
    title_text: str = ""
    # Publication appearance (mirrors frontend DEFAULT_STYLE)
    font_family: str = "Arial, Helvetica, sans-serif"
    axis_title_fontsize: int = 16
    tick_fontsize: int = 13
    text_color: str = "#000000"
    plot_bgcolor: str = "#ffffff"
    show_axis_line: bool = True
    axis_line_width: float = 1.5
    axis_box: bool = True
    tick_direction: str = "outside"
    tick_length: int = 6
    tick_width: float = 1.5
    x_axis_title: str = ""
    y_axis_title: str = ""
    y2_axis_title: str = ""
    use_axis_limits: bool = False
    use_y2_axis_limits: bool = False
    auto_scale: bool = True
    x_scale: str = "linear"
    y_scale: str = "linear"
    y2_scale: str = "linear"
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    y2_min: Optional[float] = None
    y2_max: Optional[float] = None
    line_width: float = 1.75
    plot_width: int = 900
    plot_height: int = 600
    x_major_grid: bool = False
    x_minor_grid: bool = False
    y_major_grid: bool = False
    y_minor_grid: bool = False
    major_grid_style: str = "--"
    minor_grid_style: str = ":"
    major_grid_alpha: float = 0.4
    minor_grid_alpha: float = 0.25
    major_grid_width: float = 0.5
    minor_grid_width: float = 0.5
    x_major_spacing: Optional[float] = None
    x_minor_spacing: Optional[float] = None
    y_major_spacing: Optional[float] = None
    y_minor_spacing: Optional[float] = None
    grid_color: str = "#c8c8c8"
    show_peak_markers: bool = True
    show_peak_numbers: bool = True


DEFAULT_STYLE_SETTINGS = {
    'legend_location': 'best', 'legend_fontfamily': 'sans-serif', 'legend_fontsize': 12,
    'legend_columns': 1, 'axes_fontfamily': 'sans-serif', 'axes_fontsize': 10,
    'title_fontfamily': 'sans-serif', 'title_fontsize': 16, 'title_text': '',
    'font_family': 'Arial, Helvetica, sans-serif', 'axis_title_fontsize': 16, 'tick_fontsize': 13,
    'text_color': '#000000', 'plot_bgcolor': '#ffffff',
    'show_axis_line': True, 'axis_line_width': 1.5, 'axis_box': True,
    'tick_direction': 'outside', 'tick_length': 6, 'tick_width': 1.5,
    'x_axis_title': '', 'y_axis_title': '', 'y2_axis_title': '',
    'use_axis_limits': False, 'use_y2_axis_limits': False, 'auto_scale': True,
    'x_scale': 'linear', 'y_scale': 'linear', 'y2_scale': 'linear',
    'x_min': None, 'x_max': None, 'y_min': None, 'y_max': None,
    'y2_min': None, 'y2_max': None, 'line_width': 1.75,
    'plot_width': 900, 'plot_height': 600,
    'x_major_grid': False, 'x_minor_grid': False, 'y_major_grid': False, 'y_minor_grid': False,
    'major_grid_style': '--', 'minor_grid_style': ':', 'major_grid_alpha': 0.4,
    'minor_grid_alpha': 0.25, 'major_grid_width': 0.5, 'minor_grid_width': 0.5,
    'x_major_spacing': None, 'x_minor_spacing': None, 'y_major_spacing': None, 'y_minor_spacing': None,
    'grid_color': '#c8c8c8', 'show_peak_markers': True, 'show_peak_numbers': True,
}
