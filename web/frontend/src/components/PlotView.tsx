import { useMemo, useCallback, useState, useRef, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { useAppStore } from '../store/appStore';
import { PlotSettings, type SettingsSection } from './PlotSettings';
import type { Data, Layout, Config, Dash, PlotMouseEvent } from 'plotly.js';

type Zone = 'legend' | 'xaxis' | 'yaxis' | 'y2axis' | 'plot';

// Classify a right-click into a plot zone. Plotly covers the plotting area with
// an invisible drag layer (.nsewdrag), so DOM classes only work on the axis
// titles — instead we compare the cursor to the plotting-area box: below it = X
// axis, left = Y axis, right = Y2 axis. Legend is matched by its own SVG group.
function classifyZone(e: React.MouseEvent, container: HTMLElement | null, hasY2: boolean): Zone {
  if ((e.target as HTMLElement).closest('.legend')) return 'legend';
  const area = container?.querySelector('.nsewdrag');
  const r = area?.getBoundingClientRect();
  if (!r) return 'plot';
  if (e.clientY > r.bottom) return 'xaxis';
  if (e.clientX < r.left) return 'yaxis';
  if (hasY2 && e.clientX > r.right) return 'y2axis';
  return 'plot';
}

const ZONE_LABEL: Record<Exclude<Zone, 'plot'>, string> = {
  legend: 'Legend settings…',
  xaxis: 'X-axis settings…',
  yaxis: 'Y-axis settings…',
  y2axis: 'Y2-axis settings…',
};

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

const GRID_DASH_MAP: Record<string, string> = {
  '-': 'solid',
  '--': 'dash',
  ':': 'dot',
  '-.': 'dashdot',
  'solid': 'solid',
  'dash': 'dash',
  'dot': 'dot',
  'dashdot': 'dashdot',
};

type Anchor = 'auto' | 'left' | 'center' | 'right';
type VAnchor = 'auto' | 'top' | 'middle' | 'bottom';

function legendPosition(loc: string): { x: number; y: number; xanchor?: Anchor; yanchor?: VAnchor } {
  const map: Record<string, { x: number; y: number; xanchor?: Anchor; yanchor?: VAnchor }> = {
    'best': { x: 1, y: 1, xanchor: 'auto' as Anchor, yanchor: 'auto' as VAnchor },
    'upper right': { x: 1, y: 1 },
    'upper left': { x: 0, y: 1 },
    'lower left': { x: 0, y: 0 },
    'lower right': { x: 1, y: 0 },
    'right': { x: 1, y: 0.5 },
    'center left': { x: 0, y: 0.5 },
    'center right': { x: 1, y: 0.5 },
    'lower center': { x: 0.5, y: 0 },
    'upper center': { x: 0.5, y: 1 },
    'center': { x: 0.5, y: 0.5 },
    'outside_right': { x: 1.02, y: 1, xanchor: 'left' },
    'outside_left': { x: -0.15, y: 1, xanchor: 'right' },
    'outside_top': { x: 0.5, y: 1.1, xanchor: 'center', yanchor: 'bottom' },
    'outside_bottom': { x: 0.5, y: -0.15, xanchor: 'center', yanchor: 'top' },
  };
  return map[loc] || map['best'];
}

const LINE_DASH_MAP: Record<string, string> = {
  'solid': 'solid', 'dashed': 'dash', 'dotted': 'dot', 'dashdot': 'dashdot',
  'dash': 'dash', 'dot': 'dot',
};

const LINE_STYLES = [
  { value: 'solid', label: 'Solid' },
  { value: 'dashed', label: 'Dashed' },
  { value: 'dotted', label: 'Dotted' },
  { value: 'dashdot', label: 'Dash-Dot' },
];

export function PlotView() {
  const traces = useAppStore(s => s.traces);
  const plotStyle = useAppStore(s => s.plotStyle);
  const fileStyles = useAppStore(s => s.fileStyles);
  const setFileStyle = useAppStore(s => s.setFileStyle);
  const setPlotStyle = useAppStore(s => s.setPlotStyle);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; zone: Zone } | null>(null);
  const [selectedCurve, setSelectedCurve] = useState<{ fileId: string; clickX: number; clickY: number } | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsFocus, setSettingsFocus] = useState<SettingsSection | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close context menu and curve popup on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (contextMenu && !target.closest('.context-menu')) setContextMenu(null);
      if (selectedCurve && !target.closest('.curve-popup')) setSelectedCurve(null);
      if (settingsOpen && !target.closest('.settings-popup') && !target.closest('.settings-toggle')) setSettingsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [contextMenu, selectedCurve, settingsOpen]);

  const hasY2 = traces.some(t => t.yaxis === 'y2');

  const data: Data[] = useMemo(() => {
    // One legend entry per label; traces sharing a label are grouped so clicking
    // the entry toggles the whole group (a color "series" hides in one click).
    const seenLabels = new Set<string>();
    return traces.map(trace => {
      const style = trace.file_id ? fileStyles[trace.file_id] : undefined;
      const isY2 = trace.yaxis === 'y2';
      const color = style ? (isY2 ? style.line_color_y2 : style.line_color) : undefined;
      const dash = style ? (LINE_DASH_MAP[style.line_style] || 'solid') : undefined;
      const label = style?.legend_label || '';
      const name = label || trace.name;
      const firstOfLabel = !!label && !seenLabels.has(label);
      if (label) seenLabels.add(label);
      return {
        x: trace.x,
        y: trace.y,
        name,
        legendgroup: label || undefined,
        showlegend: firstOfLabel,
        type: 'scatter' as const,
        mode: 'lines' as const,
        yaxis: isY2 ? 'y2' : undefined,
        line: {
          width: plotStyle.line_width,
          color,
          dash: dash as Dash,
        },
      };
    });
  }, [traces, plotStyle.line_width, fileStyles]);

  const layout: Partial<Layout> = useMemo(() => {
    const fg = plotStyle.text_color;
    const bg = plotStyle.plot_bgcolor;
    const baseFont = { family: plotStyle.font_family, color: fg };
    // Shared axis frame + tick props (publication box with ticks).
    const axisCommon = {
      color: fg,
      showline: plotStyle.show_axis_line,
      linecolor: fg,
      linewidth: plotStyle.axis_line_width,
      mirror: plotStyle.axis_box,
      zeroline: false,
      ticks: plotStyle.tick_direction as 'outside' | 'inside' | '',
      ticklen: plotStyle.tick_length,
      tickwidth: plotStyle.tick_width,
      tickcolor: fg,
      tickfont: { ...baseFont, size: plotStyle.tick_fontsize },
    };

    // Build an axis range that honors a single fixed bound: if only min (or only
    // max) is set, fill the open side from the actual data extent (+3% pad).
    // Both unset → undefined (autorange). Log axes keep the both-or-nothing rule.
    const axisRange = (
      minV: number | null,
      maxV: number | null,
      isLinear: boolean,
      pick: (t: (typeof traces)[number]) => number[],
      include: (t: (typeof traces)[number]) => boolean,
    ): [number, number] | undefined => {
      if (minV != null && maxV != null) return [minV, maxV];
      if (minV == null && maxV == null) return undefined;
      if (!isLinear) return undefined;
      let lo = Infinity, hi = -Infinity;
      for (const t of traces) {
        if (!include(t)) continue;
        for (const v of pick(t)) if (Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; }
      }
      if (!(lo <= hi)) return undefined;
      const pad = ((hi - lo) || Math.abs(hi) || 1) * 0.03;
      const rLo = minV != null ? minV : lo - pad;
      const rHi = maxV != null ? maxV : hi + pad;
      return rLo < rHi ? [rLo, rHi] : undefined;
    };

    const legendPos = legendPosition(plotStyle.legend_location);
    const gridDash = GRID_DASH_MAP[plotStyle.major_grid_style] || 'dash';
    const minorGridDash = GRID_DASH_MAP[plotStyle.minor_grid_style] || 'dot';
    const majorGridColor = hexToRgba(plotStyle.grid_color, plotStyle.major_grid_alpha);
    const minorGridColor = hexToRgba(plotStyle.grid_color, plotStyle.minor_grid_alpha);

    const l: Partial<Layout> = {
      title: plotStyle.title_text ? {
        text: plotStyle.title_text,
        font: { ...baseFont, size: plotStyle.title_fontsize },
      } : undefined,
      paper_bgcolor: bg,
      plot_bgcolor: bg,
      font: { ...baseFont, size: plotStyle.tick_fontsize },
      width: plotStyle.plot_width,
      height: plotStyle.plot_height,
      margin: { l: 70, r: hasY2 ? 70 : 30, t: plotStyle.title_text ? 50 : 30, b: 60 },
      legend: {
        ...legendPos,
        font: { ...baseFont, size: plotStyle.legend_fontsize },
        bgcolor: bg,
        bordercolor: fg,
        borderwidth: 1,
        ...(plotStyle.legend_columns > 1 ? {
          orientation: 'h' as const,
          entrywidth: Math.floor((plotStyle.plot_width - 120) / plotStyle.legend_columns),
          entrywidthmode: 'pixels' as const,
        } : {}),
      },
      xaxis: {
        ...axisCommon,
        title: plotStyle.x_axis_title
          ? { text: plotStyle.x_axis_title, font: { ...baseFont, size: plotStyle.axis_title_fontsize } }
          : undefined,
        type: plotStyle.x_scale === 'log' ? 'log' : 'linear',
        showgrid: plotStyle.x_major_grid,
        gridcolor: majorGridColor,
        griddash: gridDash as Dash,
        gridwidth: 1,
        ticksuffix: plotStyle.x_unit ? ` ${plotStyle.x_unit}` : undefined,
        ...(plotStyle.x_major_spacing != null ? { dtick: plotStyle.x_major_spacing } : {}),
        ...(plotStyle.x_auto ? {} : {
          range: axisRange(plotStyle.x_min, plotStyle.x_max, plotStyle.x_scale !== 'log',
            t => t.x, () => true),
        }),
        minor: {
          showgrid: plotStyle.x_minor_grid,
          gridcolor: minorGridColor,
          griddash: minorGridDash as Dash,
          ...(plotStyle.x_minor_spacing != null ? { dtick: plotStyle.x_minor_spacing } : {}),
        },
      },
      yaxis: {
        ...axisCommon,
        title: plotStyle.y_axis_title
          ? { text: plotStyle.y_axis_title, font: { ...baseFont, size: plotStyle.axis_title_fontsize } }
          : undefined,
        type: plotStyle.y_scale === 'log' ? 'log' : 'linear',
        showgrid: plotStyle.y_major_grid,
        gridcolor: majorGridColor,
        griddash: gridDash as Dash,
        gridwidth: 1,
        ticksuffix: plotStyle.y_unit ? ` ${plotStyle.y_unit}` : undefined,
        ...(plotStyle.y_major_spacing != null ? { dtick: plotStyle.y_major_spacing } : {}),
        ...(plotStyle.y_auto ? {} : {
          range: axisRange(plotStyle.y_min, plotStyle.y_max, plotStyle.y_scale !== 'log',
            t => t.y, t => t.yaxis !== 'y2'),
        }),
        minor: {
          showgrid: plotStyle.y_minor_grid,
          gridcolor: minorGridColor,
          griddash: minorGridDash as Dash,
          ...(plotStyle.y_minor_spacing != null ? { dtick: plotStyle.y_minor_spacing } : {}),
        },
      },
    };

    if (hasY2) {
      l.yaxis2 = {
        ...axisCommon,
        title: plotStyle.y2_axis_title
          ? { text: plotStyle.y2_axis_title, font: { ...baseFont, size: plotStyle.axis_title_fontsize } }
          : undefined,
        type: plotStyle.y2_scale === 'log' ? 'log' : 'linear',
        overlaying: 'y',
        side: 'right',
        showgrid: false,
        ticksuffix: plotStyle.y2_unit ? ` ${plotStyle.y2_unit}` : undefined,
        ...(plotStyle.y2_major_spacing != null ? { dtick: plotStyle.y2_major_spacing } : {}),
        ...(plotStyle.y2_auto ? {} : {
          range: axisRange(plotStyle.y2_min, plotStyle.y2_max, plotStyle.y2_scale !== 'log',
            t => t.y, t => t.yaxis === 'y2'),
        }),
        ...(plotStyle.y2_minor_spacing != null
          ? { minor: { dtick: plotStyle.y2_minor_spacing } } : {}),
      };
    }

    return l;
  }, [plotStyle, hasY2, traces]);

  const config: Partial<Config> = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'] as never[],
    edits: { titleText: true, axisTitleText: true },
  }), []);

  // Sync Plotly inline edits back to store
  const handleRelayout = useCallback((update: Record<string, unknown>) => {
    const style: Partial<typeof plotStyle> = {};
    if ('title.text' in update) style.title_text = update['title.text'] as string;
    if ('xaxis.title.text' in update) style.x_axis_title = update['xaxis.title.text'] as string;
    if ('yaxis.title.text' in update) style.y_axis_title = update['yaxis.title.text'] as string;
    if ('yaxis2.title.text' in update) style.y2_axis_title = update['yaxis2.title.text'] as string;
    if (Object.keys(style).length > 0) setPlotStyle(style);
  }, [setPlotStyle]);

  // Click on curve → show popup
  const handleClick = useCallback((event: Readonly<PlotMouseEvent>) => {
    if (event.points.length === 0) return;
    const point = event.points[0];
    const trace = traces[point.curveNumber];
    if (!trace?.file_id) return;
    const mouseEvent = event.event as unknown as MouseEvent;
    setSelectedCurve({
      fileId: trace.file_id,
      clickX: mouseEvent.clientX,
      clickY: mouseEvent.clientY,
    });
  }, [traces]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const zone = classifyZone(e, containerRef.current, hasY2);
    setContextMenu({ x: e.clientX, y: e.clientY, zone });
  }, [hasY2]);

  const openSettings = useCallback((section: SettingsSection | Zone | null) => {
    setSettingsFocus(section === 'plot' ? null : section);
    setSettingsOpen(true);
    setContextMenu(null);
  }, []);

  const handleToggleGrid = useCallback(() => {
    const store = useAppStore.getState();
    store.setPlotStyle({
      x_major_grid: !store.plotStyle.x_major_grid,
      y_major_grid: !store.plotStyle.y_major_grid,
    });
    setContextMenu(null);
  }, []);

  const handleExportPNG = useCallback(() => {
    const plotEl = containerRef.current?.querySelector('.js-plotly-plot') as HTMLElement | null;
    if (plotEl) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).Plotly?.downloadImage(plotEl, {
        format: 'png',
        width: plotStyle.plot_width,
        height: plotStyle.plot_height,
        filename: 'plot',
      });
    }
    setContextMenu(null);
  }, [plotStyle.plot_width, plotStyle.plot_height]);

  const handleZoomFit = useCallback(() => {
    useAppStore.getState().setPlotStyle({ x_auto: true, y_auto: true, y2_auto: true });
    setContextMenu(null);
  }, []);

  const curveStyle = selectedCurve ? fileStyles[selectedCurve.fileId] : null;

  if (traces.length === 0) {
    return (
      <div className="plot-view-empty">
        <div className="plot-placeholder">
          <span>Select files, choose columns, and click Plot</span>
        </div>
      </div>
    );
  }

  return (
    <div className="plot-view" ref={containerRef} onContextMenu={handleContextMenu}>
      {/* Settings gear */}
      <button
        className="settings-toggle"
        onClick={() => settingsOpen ? setSettingsOpen(false) : openSettings(null)}
        title="Plot settings"
      >
        &#9881;
      </button>

      <Plot
        data={data}
        layout={layout}
        config={config}
        useResizeHandler
        style={{ width: '100%', height: '100%' }}
        onRelayout={handleRelayout}
        onClick={handleClick}
      />

      {/* Context menu (right-click) */}
      {contextMenu && (
        <div className="context-menu" style={{ left: contextMenu.x, top: contextMenu.y }}>
          {contextMenu.zone !== 'plot' && (
            <>
              <button onClick={() => openSettings(contextMenu.zone)}>
                {ZONE_LABEL[contextMenu.zone]}
              </button>
              <div className="context-menu-sep" />
            </>
          )}
          <button onClick={handleToggleGrid}>Toggle Grid</button>
          <button onClick={handleExportPNG}>Export PNG</button>
          <button onClick={handleZoomFit}>Zoom Fit</button>
          <div className="context-menu-sep" />
          <button onClick={() => openSettings(null)}>Plot Settings…</button>
        </div>
      )}

      {/* Curve popup (click on trace) */}
      {selectedCurve && curveStyle && (
        <div
          className="curve-popup"
          style={{ left: selectedCurve.clickX, top: selectedCurve.clickY }}
        >
          <div className="popup-header">
            <span>{curveStyle.legend_label || 'Curve'}</span>
            <button onClick={() => setSelectedCurve(null)}>&times;</button>
          </div>
          <div className="field">
            <label>Color</label>
            <input
              type="color"
              value={curveStyle.line_color}
              onChange={e => setFileStyle(selectedCurve.fileId, { line_color: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Y2 Color</label>
            <input
              type="color"
              value={curveStyle.line_color_y2}
              onChange={e => setFileStyle(selectedCurve.fileId, { line_color_y2: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Style</label>
            <select
              value={curveStyle.line_style}
              onChange={e => setFileStyle(selectedCurve.fileId, { line_style: e.target.value })}
            >
              {LINE_STYLES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Legend</label>
            <input
              type="text"
              value={curveStyle.legend_label}
              onChange={e => setFileStyle(selectedCurve.fileId, { legend_label: e.target.value })}
            />
          </div>
        </div>
      )}

      {/* Settings panel (gear icon / right-click) */}
      {settingsOpen && (
        <PlotSettings focusSection={settingsFocus} onClose={() => setSettingsOpen(false)} />
      )}
    </div>
  );
}
