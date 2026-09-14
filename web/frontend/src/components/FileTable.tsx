import { useState, useMemo, useEffect, useRef, type MouseEvent } from 'react';
import { useAppStore } from '../store/appStore';
import type { FileStyle } from '../types';
import { ColumnSelector } from './ColumnSelector';
import { StyleBar } from './StyleBar';
import { deleteFile, resetSession } from '../api/client';
import { COLOR_PALETTES } from '../utils/coloring';

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
  const toggleFile = useAppStore(s => s.toggleFile);
  const setFileStyle = useAppStore(s => s.setFileStyle);
  const patchStyles = useAppStore(s => s.patchStyles);
  const removeFile = useAppStore(s => s.removeFile);
  const checkFiles = useAppStore(s => s.checkFiles);
  const uncheckFiles = useAppStore(s => s.uncheckFiles);
  const paletteName = useAppStore(s => s.paletteName);
  const y2Columns = useAppStore(s => s.y2Columns);
  const showY2 = y2Columns.length > 0;

  // Live search (substring, case-insensitive) on sample names.
  const [search, setSearch] = useState('');

  // Shared color popover (palette swatches + Custom) — one instance, positioned
  // fixed at the clicked swatch so the table's internal scroll never clips it.
  const [picker, setPicker] = useState<{ x: number; y: number; current: string; apply: (c: string) => void } | null>(null);
  const activePalette = COLOR_PALETTES[paletteName] || [];
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

  // Apply one hand-picked color to every checked sample at once (Y1 or Y2, independent).
  const applyColorToChecked = (color: string, axis: 'y1' | 'y2') => {
    const key = axis === 'y1' ? 'line_color' : 'line_color_y2';
    const patches: Record<string, Partial<FileStyle>> = {};
    files.forEach(f => {
      if (checkedFiles.has(f.file_id)) patches[f.file_id] = { [key]: color };
    });
    patchStyles(patches);
  };

  const visibleFiles = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return files;
    return files.filter(f => f.filename.toLowerCase().includes(q));
  }, [files, search]);

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

    // Group By tokens (Alt+Shift+digit) are handled globally in App (DATA + Plot).

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
          </div>
        </div>

        <div className="style-panel">
          <StyleBar />
          <div className="style-row">
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
            <th className="col-delete"></th>
          </tr>
        </thead>
        <tbody>
          {visibleFiles.map((file, rowIdx) => {
            const style = fileStyles[file.file_id];
            const isChecked = checkedFiles.has(file.file_id);
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
