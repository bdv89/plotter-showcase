import { useAppStore } from '../store/appStore';
import { PALETTE_NAMES, displayTokens, seriesColorIndices } from '../utils/coloring';
import { SeriesPicker } from './SeriesPicker';

// Shared styling controls (Group by / Palette / Legend), used both in the DATA
// toolbar and above the Plot. All state lives in the store so both stay in sync.
export function StyleBar() {
  const files = useAppStore(s => s.files);
  const seriesTokenIndices = useAppStore(s => s.seriesTokenIndices);
  const paletteName = useAppStore(s => s.paletteName);
  const applyPalette = useAppStore(s => s.applyPalette);
  const patchStyles = useAppStore(s => s.patchStyles);

  const autoLegendFromNames = () => {
    patchStyles(Object.fromEntries(
      files.map(f => [f.file_id, { legend_label: f.filename.replace(/\.[^.]+$/, '') }]),
    ));
  };
  const clearLegend = () => {
    patchStyles(Object.fromEntries(files.map(f => [f.file_id, { legend_label: '' }])));
  };
  // Legend from color grouping: every member of a group gets the SAME token label.
  // PlotView then shows one entry per label (dedup) and groups them via legendgroup,
  // so clicking that entry toggles the whole series.
  const autoLegendFromSeries = () => {
    const indices = seriesColorIndices(files.map(f => f.filename), seriesTokenIndices);
    const picked = seriesTokenIndices.slice().sort((a, b) => a - b);
    const groupLabel: Record<number, string> = {};
    files.forEach((f, i) => {
      const grp = indices[i];
      if (!(grp in groupLabel)) {
        groupLabel[grp] = picked.length > 0
          ? picked.map(t => displayTokens(f.filename)[t] ?? '').filter(Boolean).join(' ')
          : f.filename.replace(/\.[^.]+$/, '');
      }
    });
    patchStyles(Object.fromEntries(
      files.map((f, i) => [f.file_id, { legend_label: groupLabel[indices[i]] }]),
    ));
  };

  return (
    <div className="style-row">
      <SeriesPicker />
      <div className="control-group">
        <span className="control-label">Palette</span>
        <select
          value={paletteName}
          onChange={e => applyPalette(e.target.value)}
          title="Color palette (applied immediately)"
        >
          {PALETTE_NAMES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      <div className="control-group">
        <span className="control-label">Legend</span>
        <button onClick={autoLegendFromNames} title="Fill legends from filenames">From names</button>
        <button onClick={autoLegendFromSeries} title="Fill legend from color grouping (one entry per color)">From series</button>
        <button onClick={clearLegend} title="Clear all legends">Clear</button>
      </div>
    </div>
  );
}
