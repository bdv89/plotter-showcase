import { useState, useMemo, useEffect, useRef, Fragment, type MouseEvent } from 'react';
import { useAppStore } from '../store/appStore';
import { ColumnSelector } from './ColumnSelector';
import { deleteFile, resetSession, removeExtractedColumn as removeExtractedColumnApi } from '../api/client';
import { PALETTE_NAMES, COLOR_PALETTES, displayTokens, seriesColorIndices } from '../utils/coloring';

const LINE_STYLES = [
  { value: 'solid', label: 'Solid' },
  { value: 'dash', label: 'Dashed' },
  { value: 'dot', label: 'Dotted' },
  { value: 'dashdot', label: 'Dash-Dot' },
];

export function FileTable() {
  const files = useAppStore(s => s.files);
  const checkedFiles = useAppStore(s => s.checkedFiles);
  const fileStyles = useAppStore(s => s.fileStyles);
  const extractedColumns = useAppStore(s => s.extractedColumns);
  const toggleFile = useAppStore(s => s.toggleFile);
  const setFileStyle = useAppStore(s => s.setFileStyle);
  const removeFile = useAppStore(s => s.removeFile);
  const checkFiles = useAppStore(s => s.checkFiles);
  const uncheckFiles = useAppStore(s => s.uncheckFiles);
  const autoColorFiles = useAppStore(s => s.autoColorFiles);
  const seriesTokenIndices = useAppStore(s => s.seriesTokenIndices);
  const setSeriesTokenIndices = useAppStore(s => s.setSeriesTokenIndices);
  const removeExtractedColumn = useAppStore(s => s.removeExtractedColumn);
  const clearExtractedColumns = useAppStore(s => s.clearExtractedColumns);
  const y2Columns = useAppStore(s => s.y2Columns);
  const showY2 = y2Columns.length > 0;

  // Live search (substring, case-insensitive) on sample names + auto-color palette.
  const [search, setSearch] = useState('');
  const [palette, setPalette] = useState(PALETTE_NAMES[0]);

  // Shared color popover (palette swatches + Custom) — one instance, positioned
  // fixed at the clicked swatch so the table's internal scroll never clips it.
  const [picker, setPicker] = useState<{ x: number; y: number; current: string; apply: (c: string) => void } | null>(null);
  const activePalette = COLOR_PALETTES[palette] || [];
  const openPicker = (e: MouseEvent<HTMLButtonElement>, current: string, apply: (c: string) => void) => {
    const r = e.currentTarget.getBoundingClientRect();
    setPicker({ x: r.left, y: r.bottom + 4, current, apply });
  };
  // Displayed color of the two bulk "Selected color" swatches.
  const [selY1, setSelY1] = useState('#e27d60');
  const [selY2, setSelY2] = useState('#659dbd');

  // Keyboard "active row" cursor (index into visibleFiles).
  const [activeRow, setActiveRow] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // Example tokens from the first loaded file, for the visual series picker.
  const exampleTokens = useMemo(
    () => (files.length > 0 ? displayTokens(files[0].filename) : []),
    [files],
  );

  // Toggle a series-defining token (empty selection = auto) and re-color immediately.
  const toggleSeriesToken = (i: number) => {
    const next = seriesTokenIndices.includes(i)
      ? seriesTokenIndices.filter(x => x !== i)
      : [...seriesTokenIndices, i];
    setSeriesTokenIndices(next);
    autoColorFiles(palette);
  };

  const clearSeries = () => {
    setSeriesTokenIndices([]);
    autoColorFiles(palette);
  };

  // Fill every legend from the filename (without extension), or clear them all.
  const autoLegend = () => {
    files.forEach(f =>
      setFileStyle(f.file_id, { legend_label: f.filename.replace(/\.[^.]+$/, '') }),
    );
  };
  const clearLegend = () => {
    files.forEach(f => setFileStyle(f.file_id, { legend_label: '' }));
  };

  // Peuple la légende depuis le regroupement de couleur (mêmes séries -> même
  // couleur) : une seule entrée par couleur (1er sample = token(s) de série, les
  // autres vides -> masqués de la légende Plotly). Sans token sélectionné, chaque
  // fichier est son propre groupe -> nom complet (comme Auto).
  const autoLegendByColor = () => {
    const indices = seriesColorIndices(files.map(f => f.filename), seriesTokenIndices);
    const picked = seriesTokenIndices.slice().sort((a, b) => a - b);
    const seen = new Set<number>();
    files.forEach((f, i) => {
      const grp = indices[i];
      let label = '';
      if (!seen.has(grp)) {
        seen.add(grp);
        label = picked.length > 0
          ? picked.map(t => displayTokens(f.filename)[t] ?? '').filter(Boolean).join(' ')
          : f.filename.replace(/\.[^.]+$/, '');
      }
      setFileStyle(f.file_id, { legend_label: label });
    });
  };

  // Apply one hand-picked color to every checked sample at once (Y1 or Y2, independent).
  const applyColorToChecked = (color: string, axis: 'y1' | 'y2') => {
    const key = axis === 'y1' ? 'line_color' : 'line_color_y2';
    files.forEach(f => {
      if (checkedFiles.has(f.file_id)) setFileStyle(f.file_id, { [key]: color });
    });
  };

  const visibleFiles = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return files;
    return files.filter(f => f.filename.toLowerCase().includes(q));
  }, [files, search]);

  // Supprime une colonne extraite (tous fichiers), avec confirmation, côté
  // serveur + store → ne réapparaît pas au rechargement.
  const handleDeleteExtracted = async (name: string) => {
    if (!window.confirm(`Supprimer la colonne « ${name} » ?`)) return;
    try {
      await removeExtractedColumnApi(name);
    } catch (err) {
      console.error('Failed to delete extracted column:', err);
    }
    removeExtractedColumn(name);
  };

  // Supprime toutes les colonnes extraites (un seul appel serveur).
  const handleClearExtracted = async () => {
    if (!window.confirm('Supprimer toutes les colonnes extraites ?')) return;
    try {
      await removeExtractedColumnApi();
    } catch (err) {
      console.error('Failed to clear extracted columns:', err);
    }
    clearExtractedColumns();
  };

  const handleDelete = async (fileId: string) => {
    try {
      await deleteFile(fileId);
      removeFile(fileId);
    } catch (err) {
      console.error('Failed to delete file:', err);
    }
  };

  // Vide toute la liste (avec confirmation). Un seul appel /reset côté serveur
  // (une écriture .db) au lieu de N suppressions unitaires → rapide en LAN.
  const clearAll = async () => {
    if (files.length === 0) return;
    if (!window.confirm(`Supprimer les ${files.length} fichier(s) ?`)) return;
    try {
      await resetSession();
    } catch (err) {
      console.error('Clear all failed:', err);
    }
    files.forEach(f => removeFile(f.file_id));
  };

  // Collect all extracted column names
  const extractedColNames = new Set<string>();
  Object.values(extractedColumns).forEach(cols => {
    Object.keys(cols).forEach(name => extractedColNames.add(name));
  });
  const extraCols = Array.from(extractedColNames);

  // Keep the active-row cursor within bounds when the visible list shrinks.
  useEffect(() => {
    setActiveRow(a => Math.min(a, Math.max(0, visibleFiles.length - 1)));
  }, [visibleFiles.length]);

  // Keyboard workflow for the DATA table. Guarded so nothing fires while typing
  // in a field, or when the DATA tab is hidden (inactive tabs are display:none).
  // The handler is kept in a ref (updated each render) so the document listener
  // subscribes once yet always sees fresh state — same pattern as handlePlotRef.
  const keyHandlerRef = useRef<(e: KeyboardEvent) => void>(() => {});
  keyHandlerRef.current = (e: KeyboardEvent) => {
    if (wrapperRef.current?.offsetParent === null) return;
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

    // "/" focuses search (preventDefault kills Firefox's Quick Find).
    if (e.key === '/') {
      e.preventDefault();
      searchRef.current?.focus();
      return;
    }

    const ids = visibleFiles.map(f => f.file_id);

    // Group By tokens — Alt+Shift+1..9 toggle, Alt+Shift+0 = Auto.
    if (e.altKey && e.shiftKey) {
      const m = /^Digit([0-9])$/.exec(e.code);
      if (!m) return;
      e.preventDefault();
      const n = Number(m[1]);
      if (n === 0) clearSeries();
      else if (n - 1 < exampleTokens.length) toggleSeriesToken(n - 1);
      return;
    }

    // Ctrl/Cmd+A — toggle select-all of the visible rows.
    if ((e.ctrlKey || e.metaKey) && e.code === 'KeyA') {
      e.preventDefault();
      const allSel = ids.length > 0 && ids.every(id => checkedFiles.has(id));
      if (allSel) uncheckFiles(ids); else checkFiles(ids);
      return;
    }

    // Alt+digit (tabs) is handled in App; ignore all other modifier combos here.
    if (e.altKey || e.ctrlKey || e.metaKey) return;

    // Plain 1..9 — apply palette color N to the checked rows.
    const digit = /^Digit([1-9])$/.exec(e.code);
    if (digit) {
      const idx = Number(digit[1]) - 1;
      if (checkedFiles.size > 0 && activePalette[idx]) {
        e.preventDefault();
        applyColorToChecked(activePalette[idx], 'y1');
      }
      return;
    }

    if (ids.length === 0) return;
    if (e.code === 'ArrowDown' || e.code === 'ArrowUp') {
      e.preventDefault();
      const next = Math.min(ids.length - 1, Math.max(0, activeRow + (e.code === 'ArrowDown' ? 1 : -1)));
      setActiveRow(next);
      if (e.shiftKey) checkFiles([ids[next]]);
      wrapperRef.current?.querySelector(`tbody tr:nth-child(${next + 1})`)?.scrollIntoView({ block: 'nearest' });
      return;
    }
    if (e.code === 'Space') {
      e.preventDefault();
      if (ids[activeRow]) toggleFile(ids[activeRow]);
    }
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => keyHandlerRef.current(e);
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  if (files.length === 0) {
    return <div className="file-table-empty">No files loaded</div>;
  }

  const allChecked = visibleFiles.length > 0 && visibleFiles.every(f => checkedFiles.has(f.file_id));

  return (
    <div className="file-table-wrapper" ref={wrapperRef}>
      <div className="file-toolbar">
        <div className="toolbar-top">
          <input
            ref={searchRef}
            className="file-search"
            type="text"
            placeholder="Search samples… ( / )"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => { if (e.key === 'Escape') e.currentTarget.blur(); }}
          />
          <div className="toolbar-cleanup">
            <button onClick={clearAll} title="Remove all files from the list">Clear all</button>
            {extraCols.length > 0 && (
              <button onClick={handleClearExtracted} title="Delete all extracted columns">Clear extracted</button>
            )}
          </div>
        </div>

        <div className="style-panel">
          <div className="style-row">
            {exampleTokens.length > 0 && (
              <div className="control-group series-picker" title="Define what makes a series (click a part of the example name)">
                <span className="control-label">Group by</span>
                <button
                  className={`token-chip ${seriesTokenIndices.length === 0 ? 'active' : ''}`}
                  onClick={clearSeries}
                >
                  Auto
                </button>
                <span className="series-eg">e.g.</span>
                {exampleTokens.map((tok, i) => (
                  <Fragment key={i}>
                    {i > 0 && <span className="series-sep">·</span>}
                    <button
                      className={`token-chip ${seriesTokenIndices.includes(i) ? 'active' : ''}`}
                      onClick={() => toggleSeriesToken(i)}
                    >
                      {tok}
                    </button>
                  </Fragment>
                ))}
              </div>
            )}
            <div className="control-group">
              <span className="control-label">Palette</span>
              <select
                value={palette}
                onChange={e => { setPalette(e.target.value); autoColorFiles(e.target.value); }}
                title="Color palette (applied immediately)"
              >
                {PALETTE_NAMES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>
          <div className="style-row">
            <div className="control-group">
              <span className="control-label">Legend</span>
              <button onClick={autoLegend} title="Fill legends from filenames">From names</button>
              <button onClick={autoLegendByColor} title="Fill legend from color grouping (one entry per color)">From series</button>
              <button onClick={clearLegend} title="Clear all legends">Clear</button>
            </div>
            <div className="control-group">
              <span className="control-label">Selected</span>
              <button
                className="swatch-label-btn"
                disabled={checkedFiles.size === 0}
                onClick={e => openPicker(e, selY1, c => { setSelY1(c); applyColorToChecked(c, 'y1'); })}
                title="Apply a color (Y1) to all checked samples"
              >
                Y1 <span className="swatch-dot" style={{ background: selY1 }} />
              </button>
              {showY2 && (
                <button
                  className="swatch-label-btn"
                  disabled={checkedFiles.size === 0}
                  onClick={e => openPicker(e, selY2, c => { setSelY2(c); applyColorToChecked(c, 'y2'); })}
                  title="Apply a color (Y2) to all checked samples"
                >
                  Y2 <span className="swatch-dot" style={{ background: selY2 }} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
      <div className="data-main">
      <div className="file-table-scroll">
      <table className="file-table">
        <thead>
          <tr>
            <th className="col-check">
              <input
                type="checkbox"
                checked={allChecked}
                onChange={() => {
                  const ids = visibleFiles.map(f => f.file_id);
                  if (allChecked) uncheckFiles(ids);
                  else checkFiles(ids);
                }}
              />
            </th>
            <th className="col-filename">Filename</th>
            <th className="col-color">{showY2 ? 'Y1' : 'Color'}</th>
            {showY2 && <th className="col-color">Y2</th>}
            <th className="col-style">Style</th>
            <th className="col-legend">Legend</th>
            {extraCols.map(name => (
              <th key={name} className="col-extracted">
                {name}
                <button
                  className="delete-btn"
                  title={`Delete column "${name}"`}
                  onClick={() => handleDeleteExtracted(name)}
                  style={{ marginLeft: 4 }}
                >
                  ✕
                </button>
              </th>
            ))}
            <th className="col-delete"></th>
          </tr>
        </thead>
        <tbody>
          {visibleFiles.map((file, rowIdx) => {
            const style = fileStyles[file.file_id];
            const isChecked = checkedFiles.has(file.file_id);
            const fileExtracted = extractedColumns[file.file_id] || {};
            const cls = [isChecked ? 'row-checked' : '', rowIdx === activeRow ? 'row-active' : ''].filter(Boolean).join(' ');

            return (
              <tr key={file.file_id} className={cls}>
                <td className="col-check">
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleFile(file.file_id)}
                  />
                </td>
                <td className="col-filename" title={file.filename}>
                  {file.filename}
                </td>
                <td className="col-color">
                  <button
                    className="color-swatch"
                    style={{ background: style?.line_color || '#e27d60' }}
                    onClick={e => openPicker(e, style?.line_color || '#e27d60', c => setFileStyle(file.file_id, { line_color: c }))}
                    title="Pick color (Y1)"
                  />
                </td>
                {showY2 && (
                  <td className="col-color">
                    <button
                      className="color-swatch"
                      style={{ background: style?.line_color_y2 || '#659dbd' }}
                      onClick={e => openPicker(e, style?.line_color_y2 || '#659dbd', c => setFileStyle(file.file_id, { line_color_y2: c }))}
                      title="Pick color (Y2)"
                    />
                  </td>
                )}
                <td className="col-style">
                  <select
                    value={style?.line_style || 'solid'}
                    onChange={e => setFileStyle(file.file_id, { line_style: e.target.value })}
                  >
                    {LINE_STYLES.map(ls => (
                      <option key={ls.value} value={ls.value}>{ls.label}</option>
                    ))}
                  </select>
                </td>
                <td className="col-legend">
                  <input
                    type="text"
                    value={style?.legend_label || ''}
                    onChange={e => setFileStyle(file.file_id, { legend_label: e.target.value })}
                  />
                </td>
                {extraCols.map(name => {
                  const ext = fileExtracted[name];
                  return (
                    <td key={name} className="col-extracted">
                      {ext != null ? ext.value.toFixed(ext.precision) : '-'}
                    </td>
                  );
                })}
                <td className="col-delete">
                  <button
                    className="delete-btn"
                    title="Delete file"
                    onClick={() => handleDelete(file.file_id)}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
      <ColumnSelector />
      </div>

      {picker && (
        <div className="color-popover-backdrop" onClick={() => setPicker(null)}>
          <div
            className="color-popover"
            style={{ left: picker.x, top: picker.y }}
            onClick={e => e.stopPropagation()}
          >
            <div className="swatch-grid">
              {activePalette.map(c => (
                <button
                  key={c}
                  className="swatch-opt"
                  style={{ background: c }}
                  title={c}
                  onClick={() => { picker.apply(c); setPicker(null); }}
                />
              ))}
            </div>
            <label className="swatch-custom">
              Custom…
              <input
                type="color"
                defaultValue={picker.current}
                onChange={e => { picker.apply(e.target.value); setPicker(null); }}
              />
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
