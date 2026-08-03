import { create } from 'zustand';
import type { FileInfo, FileStyle, PlotTrace, StyleSettings, ProcessingSettings } from '../types';
import { COLOR_PALETTES, PALETTE_NAMES, seriesColorIndices } from '../utils/coloring';

const COLOR_PALETTE = [
  '#e27d60', '#85cdca', '#e8a87c', '#c38d9e', '#41b3a3', '#659dbd',
  '#daad86', '#bc986a', '#fbeec1', '#8d8741', '#5c3317', '#2d4059',
];

const DEFAULT_FILE_STYLE: FileStyle = {
  line_color: '#e27d60',
  line_color_y2: '#659dbd',
  line_style: 'solid',
  legend_label: '',
};

// Default preset tuned for academic-publication figures: white background, black
// axes/text, clean sans font, closed box with outward ticks, no gridlines.
const DEFAULT_STYLE: StyleSettings = {
  legend_location: 'best',
  legend_fontsize: 12,
  legend_columns: 1,
  title_text: '',
  title_fontsize: 16,
  font_family: 'Arial, Helvetica, sans-serif',
  axis_title_fontsize: 16,
  tick_fontsize: 13,
  text_color: '#000000',
  plot_bgcolor: '#ffffff',
  show_axis_line: true,
  axis_line_width: 1.5,
  axis_box: true,
  tick_direction: 'outside',
  tick_length: 6,
  tick_width: 1.5,
  x_axis_title: '',
  y_axis_title: '',
  y2_axis_title: '',
  x_auto: true,
  y_auto: true,
  y2_auto: true,
  x_scale: 'linear',
  y_scale: 'linear',
  y2_scale: 'linear',
  x_unit: '',
  y_unit: '',
  y2_unit: '',
  x_major_spacing: null,
  x_minor_spacing: null,
  y_major_spacing: null,
  y_minor_spacing: null,
  y2_major_spacing: null,
  y2_minor_spacing: null,
  x_min: null,
  x_max: null,
  y_min: null,
  y_max: null,
  y2_min: null,
  y2_max: null,
  line_width: 1.75,
  plot_width: 900,
  plot_height: 600,
  x_major_grid: false,
  x_minor_grid: false,
  y_major_grid: false,
  y_minor_grid: false,
  major_grid_style: '--',
  minor_grid_style: ':',
  major_grid_alpha: 0.4,
  minor_grid_alpha: 0.25,
  grid_color: '#c8c8c8',
};

const DEFAULT_PROCESSING: ProcessingSettings = {
  smoothing_enabled: false,
  smoothing_window: 5,
  denoise_enabled: false,
  denoise_method: 'savgol',
  denoise_window: 11,
  denoise_polyorder: 3,
  normalize_enabled: false,
  normalize_method: 'minmax',
  baseline_enabled: false,
  baseline_method: 'snip',
  baseline_k: 40,
  outlier_enabled: false,
  outlier_threshold: 3.0,
  peak_fitting_enabled: false,
  peak_prominence: 0.1,
  peak_distance: 10,
  peak_method: 'gauss',
};

interface AppStore {
  // Files
  files: FileInfo[];
  checkedFiles: Set<string>;
  setFiles: (files: FileInfo[]) => void;
  addFiles: (files: FileInfo[]) => void;
  toggleFile: (fileId: string) => void;
  checkFiles: (ids: string[]) => void;
  uncheckFiles: (ids: string[]) => void;

  // Columns
  xColumn: string;
  yColumns: string[];
  y2Columns: string[];
  setXColumn: (col: string) => void;
  setYColumns: (cols: string[]) => void;
  setY2Columns: (cols: string[]) => void;

  // Styles
  fileStyles: Record<string, FileStyle>;
  setFileStyle: (fileId: string, style: Partial<FileStyle>) => void;
  patchStyles: (patches: Record<string, Partial<FileStyle>>) => void;
  autoColorFiles: () => void;
  paletteName: string;
  applyPalette: (name: string) => void;
  seriesTokenIndices: number[];
  toggleSeriesToken: (i: number) => void;
  clearSeries: () => void;
  plotStyle: StyleSettings;
  setPlotStyle: (style: Partial<StyleSettings>) => void;

  // Plot data
  traces: PlotTrace[];
  setTraces: (traces: PlotTrace[]) => void;
  isPlotting: boolean;
  setIsPlotting: (v: boolean) => void;

  // Processing
  processing: ProcessingSettings;
  setProcessing: (settings: Partial<ProcessingSettings>) => void;
  resetProcessing: () => void;

  // Extracted columns
  extractedColumns: Record<string, Record<string, { value: number; precision: number }>>;
  setExtractedColumn: (fileId: string, colName: string, value: number, precision: number) => void;
  removeExtractedColumn: (name: string) => void;
  clearExtractedColumns: () => void;
  restorePool: (data: {
    files: FileInfo[];
    styles: Record<string, FileStyle>;
    extracted: Record<string, Record<string, { value: number; precision: number }>>;
    plot_style?: StyleSettings;
    processing?: ProcessingSettings;
    plot_settings?: { x_column: string; y_columns: string[]; y2_columns: string[] };
  }) => void;

  // Pool name
  currentPoolName: string;
  setCurrentPoolName: (name: string) => void;

  // Error state
  error: string | null;
  setError: (msg: string | null) => void;

  // File removal
  removeFile: (fileId: string) => void;

  // Auto-plot
  autoPlot: boolean;
  toggleAutoPlot: () => void;

  // Theme
  theme: 'dark' | 'light';
  toggleTheme: () => void;
}

export const useAppStore = create<AppStore>((set, get) => ({
  // Files
  files: [],
  checkedFiles: new Set<string>(),
  setFiles: (files) => set({ files }),
  addFiles: (incoming) => {
    // Drop failed uploads (empty file_id) — they'd collapse into a single
    // phantom style/legend entry. Surface their errors instead.
    const newFiles = incoming.filter(f => f.file_id);
    const failed = incoming.filter(f => !f.file_id);
    const existing = get().files;
    const existingStyles = get().fileStyles;
    const styles = { ...existingStyles };
    newFiles.forEach((f, i) => {
      if (!styles[f.file_id]) {
        const colorIdx = (existing.length + i) % COLOR_PALETTE.length;
        styles[f.file_id] = {
          line_color: COLOR_PALETTE[colorIdx],
          line_color_y2: COLOR_PALETTE[colorIdx],
          line_style: 'solid',
          // Rempli depuis le nom de fichier (comme restorePool) → légende visible
          // dès l'upload, cohérent avec le rechargement de page. Clear la vide.
          legend_label: f.filename.replace(/\.[^.]+$/, ''),
        };
      }
    });
    const checked = new Set(get().checkedFiles);
    newFiles.forEach(f => checked.add(f.file_id));
    set({ files: [...existing, ...newFiles], fileStyles: styles, checkedFiles: checked });
    if (failed.length > 0) {
      const detail = failed[0].error || 'upload failed';
      set({ error: `${failed.length} fichier(s) non chargé(s) : ${detail}` });
    }
  },
  toggleFile: (fileId) => {
    const checked = new Set(get().checkedFiles);
    if (checked.has(fileId)) checked.delete(fileId);
    else checked.add(fileId);
    set({ checkedFiles: checked });
  },
  checkFiles: (ids) => {
    const checked = new Set(get().checkedFiles);
    ids.forEach(id => checked.add(id));
    set({ checkedFiles: checked });
  },
  uncheckFiles: (ids) => {
    const checked = new Set(get().checkedFiles);
    ids.forEach(id => checked.delete(id));
    set({ checkedFiles: checked });
  },

  // Columns
  xColumn: '',
  yColumns: [],
  y2Columns: [],
  setXColumn: (col) => set({ xColumn: col }),
  setYColumns: (cols) => set({ yColumns: cols }),
  setY2Columns: (cols) => set({ y2Columns: cols }),

  // Styles
  fileStyles: {},
  setFileStyle: (fileId, style) => {
    const current = get().fileStyles[fileId] || DEFAULT_FILE_STYLE;
    set({ fileStyles: { ...get().fileStyles, [fileId]: { ...current, ...style } } });
  },
  // Merge many per-file style patches in a single set (O(N) vs N× O(N) spreads).
  patchStyles: (patches) => {
    const cur = get().fileStyles;
    const next = { ...cur };
    for (const id in patches) next[id] = { ...(cur[id] || DEFAULT_FILE_STYLE), ...patches[id] };
    set({ fileStyles: next });
  },
  autoColorFiles: () => {
    const { files, fileStyles, seriesTokenIndices, paletteName } = get();
    const palette = COLOR_PALETTES[paletteName];
    if (!palette || palette.length === 0) return;
    // Same series -> same color; Y2 gets the same color as Y1.
    const indices = seriesColorIndices(files.map(f => f.filename), seriesTokenIndices);
    const styles = { ...fileStyles };
    files.forEach((f, i) => {
      const idx = indices[i] ?? 0;
      const current = styles[f.file_id] || DEFAULT_FILE_STYLE;
      styles[f.file_id] = {
        ...current,
        line_color: palette[idx % palette.length],
        line_color_y2: palette[idx % palette.length],
      };
    });
    set({ fileStyles: styles });
  },
  paletteName: PALETTE_NAMES[0],
  applyPalette: (name) => { set({ paletteName: name }); get().autoColorFiles(); },
  seriesTokenIndices: [],
  toggleSeriesToken: (i) => {
    const cur = get().seriesTokenIndices;
    const next = cur.includes(i) ? cur.filter(x => x !== i) : [...cur, i];
    set({ seriesTokenIndices: next });
    get().autoColorFiles();
  },
  clearSeries: () => { set({ seriesTokenIndices: [] }); get().autoColorFiles(); },
  plotStyle: { ...DEFAULT_STYLE },
  setPlotStyle: (style) => set({ plotStyle: { ...get().plotStyle, ...style } }),

  // Plot data
  traces: [],
  setTraces: (traces) => set({ traces }),
  isPlotting: false,
  setIsPlotting: (v) => set({ isPlotting: v }),

  // Processing
  processing: { ...DEFAULT_PROCESSING },
  setProcessing: (settings) => set({ processing: { ...get().processing, ...settings } }),
  resetProcessing: () => set({ processing: { ...DEFAULT_PROCESSING } }),

  // Extracted columns
  extractedColumns: {},
  setExtractedColumn: (fileId, colName, value, precision) => {
    const current = get().extractedColumns;
    const fileData = current[fileId] || {};
    set({
      extractedColumns: {
        ...current,
        [fileId]: { ...fileData, [colName]: { value, precision } },
      },
    });
  },
  removeExtractedColumn: (name) => {
    const current = get().extractedColumns;
    const next: typeof current = {};
    for (const [fileId, cols] of Object.entries(current)) {
      const { [name]: _drop, ...rest } = cols;
      void _drop;
      next[fileId] = rest;
    }
    set({ extractedColumns: next });
  },
  clearExtractedColumns: () => set({ extractedColumns: {} }),
  restorePool: (data) => {
    const styles: Record<string, FileStyle> = {};
    const checked = new Set<string>();
    data.files.forEach((f, i) => {
      const fileId = f.file_id;
      checked.add(fileId);
      styles[fileId] = data.styles[fileId] || {
        line_color: COLOR_PALETTE[i % COLOR_PALETTE.length],
        line_color_y2: COLOR_PALETTE[i % COLOR_PALETTE.length],
        line_style: 'solid',
        legend_label: f.filename.replace(/\.[^.]+$/, ''),
      };
    });
    const update: Partial<AppStore> = {
      files: data.files,
      fileStyles: styles,
      checkedFiles: checked,
      extractedColumns: data.extracted || {},
      traces: [],
      xColumn: data.plot_settings?.x_column || '',
      yColumns: data.plot_settings?.y_columns || [],
      y2Columns: data.plot_settings?.y2_columns || [],
    };
    if (data.plot_style) {
      update.plotStyle = { ...DEFAULT_STYLE, ...data.plot_style };
    }
    if (data.processing) {
      update.processing = { ...DEFAULT_PROCESSING, ...data.processing };
    }
    set(update);
  },

  // Pool name
  currentPoolName: '',
  setCurrentPoolName: (name) => set({ currentPoolName: name }),

  // Error state
  error: null,
  setError: (msg) => set({ error: msg }),

  // File removal
  removeFile: (fileId) => {
    const state = get();
    const checked = new Set(state.checkedFiles);
    checked.delete(fileId);
    const { [fileId]: _dropStyle, ...restStyles } = state.fileStyles;
    void _dropStyle;
    const { [fileId]: _dropExtracted, ...restExtracted } = state.extractedColumns;
    void _dropExtracted;
    set({
      files: state.files.filter(f => f.file_id !== fileId),
      checkedFiles: checked,
      fileStyles: restStyles,
      extractedColumns: restExtracted,
      traces: state.traces.filter(t => t.file_id !== fileId),
    });
  },

  // Auto-plot
  autoPlot: true,
  toggleAutoPlot: () => set({ autoPlot: !get().autoPlot }),

  // Theme
  theme: (localStorage.getItem('csv-plotter-theme') as 'dark' | 'light') || 'dark',
  toggleTheme: () => {
    const next = get().theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('csv-plotter-theme', next);
    document.documentElement.setAttribute('data-theme', next);
    set({ theme: next });
  },
}));
