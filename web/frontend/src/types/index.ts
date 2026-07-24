export interface FileInfo {
  file_id: string;
  filename: string;
  columns: string[];
  row_count: number;
  error?: string;
}

export interface FileStyle {
  line_color: string;
  line_color_y2: string;
  line_style: string;
  legend_label: string;
}

export interface PlotTrace {
  x: number[];
  y: number[];
  name: string;
  yaxis: string;
  file_id?: string;
}

export interface StyleSettings {
  legend_location: string;
  legend_fontsize: number;
  legend_columns: number;
  title_text: string;
  title_fontsize: number;
  // Fonts & colors (publication appearance, independent of the UI dark/light theme)
  font_family: string;
  axis_title_fontsize: number;
  tick_fontsize: number;
  text_color: string;
  plot_bgcolor: string;
  // Axis frame & ticks
  show_axis_line: boolean;
  axis_line_width: number;
  axis_box: boolean;          // mirror axes → closed box around the plot
  tick_direction: string;    // 'outside' | 'inside' | '' (none)
  tick_length: number;
  tick_width: number;
  x_axis_title: string;
  y_axis_title: string;
  y2_axis_title: string;
  x_auto: boolean;
  y_auto: boolean;
  y2_auto: boolean;
  x_scale: string;
  y_scale: string;
  y2_scale: string;
  x_unit: string;
  y_unit: string;
  y2_unit: string;
  x_major_spacing: number | null;
  x_minor_spacing: number | null;
  y_major_spacing: number | null;
  y_minor_spacing: number | null;
  y2_major_spacing: number | null;
  y2_minor_spacing: number | null;
  x_min: number | null;
  x_max: number | null;
  y_min: number | null;
  y_max: number | null;
  y2_min: number | null;
  y2_max: number | null;
  line_width: number;
  plot_width: number;
  plot_height: number;
  x_major_grid: boolean;
  x_minor_grid: boolean;
  y_major_grid: boolean;
  y_minor_grid: boolean;
  major_grid_style: string;
  minor_grid_style: string;
  major_grid_alpha: number;
  minor_grid_alpha: number;
  grid_color: string;
}

export interface ProcessingSettings {
  smoothing_enabled: boolean;
  smoothing_window: number;
  denoise_enabled: boolean;
  denoise_method: string;
  denoise_window: number;
  denoise_polyorder: number;
  normalize_enabled: boolean;
  normalize_method: string;
  baseline_enabled: boolean;
  baseline_method: string;
  baseline_k: number;
  outlier_enabled: boolean;
  outlier_threshold: number;
  peak_fitting_enabled: boolean;
  peak_prominence: number;
  peak_distance: number;
  peak_method: string;
}

export interface ExtractionResult {
  file_id: string;
  column_name: string;
  value: number | null;
  precision: number;
}

// Connection-tracking metrics (onglet Metrics)
export interface MetricsSummary {
  total_requests: number;
  unique_ips_total: number;
  unique_ips_today: number;
  first_date: string | null;
  last_date: string | null;
}

export interface MetricsDailyRow {
  date: string;
  requests: number;
  unique_ips: number;
}

export interface MetricsEndpointRow {
  endpoint: string;
  total: number;
  last_activity: string | null;
}
