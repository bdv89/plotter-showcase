import { useRef, useEffect } from 'react';
import { useAppStore } from '../store/appStore';
import { exportStyle, importStyle } from '../utils/stylePreset';
import type { StyleSettings } from '../types';

export type SettingsSection =
  | 'title' | 'axes' | 'legend' | 'grid' | 'size' | 'range' | 'preset'
  // aliases coming from right-click zone detection:
  | 'xaxis' | 'yaxis' | 'y2axis';

const LEGEND_POSITIONS = [
  'best', 'upper right', 'upper left', 'lower left', 'lower right',
  'right', 'center left', 'center right', 'lower center', 'upper center', 'center',
  'outside_right', 'outside_left', 'outside_top', 'outside_bottom',
];

const GRID_DASH_OPTIONS = [
  { value: '-', label: 'Solid' },
  { value: '--', label: 'Dashed' },
  { value: ':', label: 'Dotted' },
  { value: '-.', label: 'Dash-Dot' },
];

const FONT_FAMILIES = [
  { value: 'Arial, Helvetica, sans-serif', label: 'Arial / Helvetica' },
  { value: '"Times New Roman", Times, serif', label: 'Times New Roman' },
  { value: 'Georgia, serif', label: 'Georgia' },
  { value: '"Calibri", "Segoe UI", sans-serif', label: 'Calibri' },
  { value: '"Courier New", monospace', label: 'Courier New' },
];

const TICK_OPTIONS = [
  { value: 'outside', label: 'Outside' },
  { value: 'inside', label: 'Inside' },
  { value: '', label: 'None' },
];

// Each axis now has its own section (data-section="xaxis"/"yaxis"/"y2axis"),
// so the focus id maps to the DOM section directly.
function resolveSection(s: SettingsSection | null | undefined): string | null {
  return s ?? null;
}

interface AxisCfg {
  id: 'xaxis' | 'yaxis' | 'y2axis';
  label: string;
  title: keyof StyleSettings; scale: keyof StyleSettings; unit: keyof StyleSettings;
  auto: keyof StyleSettings; min: keyof StyleSettings; max: keyof StyleSettings;
  major: keyof StyleSettings; minor: keyof StyleSettings;
}

const X_AXIS: AxisCfg = {
  id: 'xaxis', label: 'X', title: 'x_axis_title', scale: 'x_scale', unit: 'x_unit',
  auto: 'x_auto', min: 'x_min', max: 'x_max', major: 'x_major_spacing', minor: 'x_minor_spacing',
};
const Y_AXIS: AxisCfg = {
  id: 'yaxis', label: 'Y', title: 'y_axis_title', scale: 'y_scale', unit: 'y_unit',
  auto: 'y_auto', min: 'y_min', max: 'y_max', major: 'y_major_spacing', minor: 'y_minor_spacing',
};
const Y2_AXIS: AxisCfg = {
  id: 'y2axis', label: 'Y2', title: 'y2_axis_title', scale: 'y2_scale', unit: 'y2_unit',
  auto: 'y2_auto', min: 'y2_min', max: 'y2_max', major: 'y2_major_spacing', minor: 'y2_minor_spacing',
};

interface Props {
  focusSection?: SettingsSection | null;
  onClose: () => void;
}

export function PlotSettings({ focusSection, onClose }: Props) {
  const plotStyle = useAppStore(s => s.plotStyle);
  const setPlotStyle = useAppStore(s => s.setPlotStyle);
  const traces = useAppStore(s => s.traces);
  const hasY2 = traces.some(t => t.yaxis === 'y2');
  const importRef = useRef<HTMLInputElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  // Scroll to the focused section and briefly highlight it.
  useEffect(() => {
    const id = resolveSection(focusSection);
    if (!id || !popupRef.current) return;
    const el = popupRef.current.querySelector<HTMLElement>(`[data-section="${id}"]`);
    if (!el) return;
    el.scrollIntoView({ block: 'start', behavior: 'smooth' });
    el.classList.add('section-flash');
    const t = setTimeout(() => el.classList.remove('section-flash'), 1200);
    return () => clearTimeout(t);
  }, [focusSection]);

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    try {
      const imported = await importStyle(file);
      setPlotStyle(imported);
    } catch (err) {
      useAppStore.getState().setError(err instanceof Error ? err.message : 'Import style failed');
    }
  };

  const setKey = (k: keyof StyleSettings, v: unknown) =>
    setPlotStyle({ [k]: v } as Partial<StyleSettings>);
  const numOrNull = (s: string) => (s ? Number(s) : null);

  const renderAxis = (c: AxisCfg) => {
    const auto = plotStyle[c.auto] as boolean;
    return (
      <div className="settings-section" data-section={c.id} key={c.id}>
        <h5>{c.label} Axis</h5>
        <div className="field">
          <label>Title</label>
          <input type="text" value={plotStyle[c.title] as string}
            onChange={e => setKey(c.title, e.target.value)} />
        </div>
        <div className="field">
          <label>Unit</label>
          <input type="text" placeholder="e.g. N, mm" value={plotStyle[c.unit] as string}
            onChange={e => setKey(c.unit, e.target.value)} />
        </div>
        <div className="field-row">
          <label>Scale</label>
          <select value={plotStyle[c.scale] as string} onChange={e => setKey(c.scale, e.target.value)}>
            <option value="linear">Linear</option>
            <option value="log">Log</option>
          </select>
        </div>
        <div className="field-row">
          <label>
            <input type="checkbox" checked={auto} onChange={e => setKey(c.auto, e.target.checked)} />
            Auto scale
          </label>
        </div>
        {!auto && (
          <div className="field-row">
            <div className="field compact">
              <label>Min</label>
              <input type="number" value={(plotStyle[c.min] as number | null) ?? ''}
                onChange={e => setKey(c.min, numOrNull(e.target.value))} />
            </div>
            <div className="field compact">
              <label>Max</label>
              <input type="number" value={(plotStyle[c.max] as number | null) ?? ''}
                onChange={e => setKey(c.max, numOrNull(e.target.value))} />
            </div>
          </div>
        )}
        <div className="field-row">
          <div className="field compact">
            <label>Major unit</label>
            <input type="number" placeholder="auto" value={(plotStyle[c.major] as number | null) ?? ''}
              onChange={e => setKey(c.major, numOrNull(e.target.value))} />
          </div>
          <div className="field compact">
            <label>Minor unit</label>
            <input type="number" placeholder="auto" value={(plotStyle[c.minor] as number | null) ?? ''}
              onChange={e => setKey(c.minor, numOrNull(e.target.value))} />
          </div>
        </div>
      </div>
    );
  };

  // When opened on a specific section (right-click on an axis/legend), show ONLY
  // that section. The gear (focusSection null) shows the full panel.
  const SOLE = ['title', 'xaxis', 'yaxis', 'y2axis', 'legend', 'grid', 'size', 'preset'];
  const sole = focusSection && SOLE.includes(focusSection) ? focusSection : null;
  const show = (s: string) => !sole || sole === s;

  return (
    <div className="settings-popup" ref={popupRef}>
      <div className="settings-header">
        <h4>Plot Settings</h4>
        <button className="settings-close" onClick={onClose} title="Close">&times;</button>
      </div>

      {/* ===== Title ===== */}
      {show('title') && (
      <div className="settings-section" data-section="title">
        <h5>Title</h5>
        <div className="field">
          <label>Title Text</label>
          <input type="text" value={plotStyle.title_text}
            onChange={e => setPlotStyle({ title_text: e.target.value })} />
        </div>
        <div className="field">
          <label>Title Font Size</label>
          <input type="number" min={8} max={40} value={plotStyle.title_fontsize}
            onChange={e => setPlotStyle({ title_fontsize: Number(e.target.value) })} />
        </div>
      </div>
      )}

      {/* ===== Fonts ===== */}
      {show('fonts') && (
      <div className="settings-section" data-section="fonts">
        <h5>Fonts</h5>
        <div className="field">
          <label>Font Family</label>
          <select value={plotStyle.font_family} onChange={e => setKey('font_family', e.target.value)}>
            {FONT_FAMILIES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </div>
        <div className="field-row">
          <div className="field compact">
            <label>Axis Title Size</label>
            <input type="number" min={6} max={40} value={plotStyle.axis_title_fontsize}
              onChange={e => setKey('axis_title_fontsize', Number(e.target.value))} />
          </div>
          <div className="field compact">
            <label>Tick Label Size</label>
            <input type="number" min={6} max={32} value={plotStyle.tick_fontsize}
              onChange={e => setKey('tick_fontsize', Number(e.target.value))} />
          </div>
        </div>
      </div>
      )}

      {/* ===== Per-axis: title, unit, scale, limits, tick spacing ===== */}
      {show('xaxis') && renderAxis(X_AXIS)}
      {show('yaxis') && renderAxis(Y_AXIS)}
      {hasY2 && show('y2axis') && renderAxis(Y2_AXIS)}

      {/* ===== Axes frame & ticks (global) ===== */}
      {show('frame') && (
      <div className="settings-section" data-section="frame">
        <h5>Axes Frame &amp; Ticks</h5>
        <div className="field-row">
          <label><input type="checkbox" checked={plotStyle.show_axis_line}
            onChange={e => setKey('show_axis_line', e.target.checked)} /> Axis line</label>
          <label><input type="checkbox" checked={plotStyle.axis_box}
            onChange={e => setKey('axis_box', e.target.checked)} /> Closed box</label>
        </div>
        <div className="field">
          <label>Axis Line Width</label>
          <input type="number" min={0.5} max={6} step={0.5} value={plotStyle.axis_line_width}
            onChange={e => setKey('axis_line_width', Number(e.target.value))} />
        </div>
        <div className="field">
          <label>Ticks</label>
          <select value={plotStyle.tick_direction} onChange={e => setKey('tick_direction', e.target.value)}>
            {TICK_OPTIONS.map(o => <option key={o.label} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field-row">
          <div className="field compact">
            <label>Tick Length</label>
            <input type="number" min={0} max={20} value={plotStyle.tick_length}
              onChange={e => setKey('tick_length', Number(e.target.value))} />
          </div>
          <div className="field compact">
            <label>Tick Width</label>
            <input type="number" min={0.5} max={6} step={0.5} value={plotStyle.tick_width}
              onChange={e => setKey('tick_width', Number(e.target.value))} />
          </div>
        </div>
      </div>
      )}

      {/* ===== Legend ===== */}
      {show('legend') && (
      <div className="settings-section" data-section="legend">
        <h5>Legend</h5>
        <div className="field">
          <label>Position</label>
          <select value={plotStyle.legend_location} onChange={e => setPlotStyle({ legend_location: e.target.value })}>
            {LEGEND_POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Font Size</label>
          <input type="number" min={6} max={24} value={plotStyle.legend_fontsize}
            onChange={e => setPlotStyle({ legend_fontsize: Number(e.target.value) })} />
        </div>
        <div className="field">
          <label>Columns</label>
          <input type="number" min={1} max={6} value={plotStyle.legend_columns}
            onChange={e => setPlotStyle({ legend_columns: Number(e.target.value) })} />
        </div>
      </div>
      )}

      {/* ===== Grid ===== */}
      {show('grid') && (
      <div className="settings-section" data-section="grid">
        <h5>Grid</h5>
        <div className="field-row">
          <label>Grid Color</label>
          <input type="color" value={plotStyle.grid_color}
            onChange={e => setPlotStyle({ grid_color: e.target.value })} />
        </div>
        <div className="field-row">
          <label><input type="checkbox" checked={plotStyle.x_major_grid} onChange={e => setPlotStyle({ x_major_grid: e.target.checked })} /> X Grid</label>
          <label><input type="checkbox" checked={plotStyle.y_major_grid} onChange={e => setPlotStyle({ y_major_grid: e.target.checked })} /> Y Grid</label>
        </div>
        <div className="field-row">
          <label><input type="checkbox" checked={plotStyle.x_minor_grid} onChange={e => setPlotStyle({ x_minor_grid: e.target.checked })} /> X Minor</label>
          <label><input type="checkbox" checked={plotStyle.y_minor_grid} onChange={e => setPlotStyle({ y_minor_grid: e.target.checked })} /> Y Minor</label>
        </div>
        <div className="field">
          <label>Major Line Style</label>
          <select value={plotStyle.major_grid_style} onChange={e => setPlotStyle({ major_grid_style: e.target.value })}>
            {GRID_DASH_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Minor Line Style</label>
          <select value={plotStyle.minor_grid_style} onChange={e => setPlotStyle({ minor_grid_style: e.target.value })}>
            {GRID_DASH_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Major Opacity ({plotStyle.major_grid_alpha.toFixed(2)})</label>
          <input type="range" min={0} max={1} step={0.05} value={plotStyle.major_grid_alpha}
            onChange={e => setPlotStyle({ major_grid_alpha: Number(e.target.value) })} />
        </div>
        <div className="field">
          <label>Minor Opacity ({plotStyle.minor_grid_alpha.toFixed(2)})</label>
          <input type="range" min={0} max={1} step={0.05} value={plotStyle.minor_grid_alpha}
            onChange={e => setPlotStyle({ minor_grid_alpha: Number(e.target.value) })} />
        </div>
      </div>
      )}

      {/* ===== Appearance (colors) ===== */}
      {show('appearance') && (
      <div className="settings-section" data-section="appearance">
        <h5>Appearance</h5>
        <div className="field-row">
          <label>Background</label>
          <input type="color" value={plotStyle.plot_bgcolor}
            onChange={e => setKey('plot_bgcolor', e.target.value)} />
        </div>
        <div className="field-row">
          <label>Text &amp; Axes</label>
          <input type="color" value={plotStyle.text_color}
            onChange={e => setKey('text_color', e.target.value)} />
        </div>
      </div>
      )}

      {/* ===== Size ===== */}
      {show('size') && (
      <div className="settings-section" data-section="size">
        <h5>Size</h5>
        <div className="field">
          <label>Line Width</label>
          <input type="number" min={0.5} max={10} step={0.5} value={plotStyle.line_width}
            onChange={e => setPlotStyle({ line_width: Number(e.target.value) })} />
        </div>
        <div className="field">
          <label>Width</label>
          <input type="number" min={400} max={2000} step={50} value={plotStyle.plot_width}
            onChange={e => setPlotStyle({ plot_width: Number(e.target.value) })} />
        </div>
        <div className="field">
          <label>Height</label>
          <input type="number" min={300} max={1500} step={50} value={plotStyle.plot_height}
            onChange={e => setPlotStyle({ plot_height: Number(e.target.value) })} />
        </div>
      </div>
      )}

      {/* ===== Style Preset ===== */}
      {show('preset') && (
      <div className="settings-section" data-section="preset">
        <h5>Style Preset</h5>
        <div className="field-row preset-buttons">
          <button onClick={() => exportStyle(plotStyle)}>Export Style (.json)</button>
          <button onClick={() => importRef.current?.click()}>Import Style (.json)</button>
          <input ref={importRef} type="file" accept=".json" style={{ display: 'none' }} onChange={handleImport} />
        </div>
      </div>
      )}
    </div>
  );
}
