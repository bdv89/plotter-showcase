import { useState, useMemo } from 'react';
import { useAppStore } from '../store/appStore';
import { deleteFile } from '../api/client';
import { PALETTE_NAMES, displayTokens } from '../utils/coloring';

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

  // Live search (substring, case-insensitive) on sample names + auto-color palette.
  const [search, setSearch] = useState('');
  const [palette, setPalette] = useState(PALETTE_NAMES[0]);

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

  // Collect all extracted column names
  const extractedColNames = new Set<string>();
  Object.values(extractedColumns).forEach(cols => {
    Object.keys(cols).forEach(name => extractedColNames.add(name));
  });
  const extraCols = Array.from(extractedColNames);

  if (files.length === 0) {
    return <div className="file-table-empty">No files loaded</div>;
  }

  const allChecked = visibleFiles.length > 0 && visibleFiles.every(f => checkedFiles.has(f.file_id));

  return (
    <div className="file-table-wrapper">
      <div className="file-toolbar">
        <input
          className="file-search"
          type="text"
          placeholder="Search samples…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="file-controls">
          <div className="control-group">
            <span className="control-label">Colors</span>
            <select
              value={palette}
              onChange={e => { setPalette(e.target.value); autoColorFiles(e.target.value); }}
              title="Color palette (applied immediately)"
            >
              {PALETTE_NAMES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="control-group">
            <span className="control-label">Legend</span>
            <button onClick={autoLegend} title="Fill legends from filenames">Auto</button>
            <button onClick={clearLegend} title="Clear all legends">Clear</button>
          </div>
          {exampleTokens.length > 0 && (
            <div className="control-group series-picker" title="Define what makes a series (click a part of the example name)">
              <span className="control-label">Series</span>
              <button
                className={`token-chip ${seriesTokenIndices.length === 0 ? 'active' : ''}`}
                onClick={clearSeries}
              >
                Auto
              </button>
              {exampleTokens.map((tok, i) => (
                <button
                  key={i}
                  className={`token-chip ${seriesTokenIndices.includes(i) ? 'active' : ''}`}
                  onClick={() => toggleSeriesToken(i)}
                >
                  {tok}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
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
            <th className="col-color">Y1</th>
            <th className="col-color">Y2</th>
            <th className="col-style">Style</th>
            <th className="col-legend">Legend</th>
            {extraCols.map(name => (
              <th key={name} className="col-extracted">{name}</th>
            ))}
            <th className="col-delete"></th>
          </tr>
        </thead>
        <tbody>
          {visibleFiles.map(file => {
            const style = fileStyles[file.file_id];
            const isChecked = checkedFiles.has(file.file_id);
            const fileExtracted = extractedColumns[file.file_id] || {};

            return (
              <tr key={file.file_id} className={isChecked ? 'row-checked' : ''}>
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
                  <input
                    type="color"
                    value={style?.line_color || '#e27d60'}
                    onChange={e => setFileStyle(file.file_id, { line_color: e.target.value })}
                  />
                </td>
                <td className="col-color">
                  <input
                    type="color"
                    value={style?.line_color_y2 || '#659dbd'}
                    onChange={e => setFileStyle(file.file_id, { line_color_y2: e.target.value })}
                  />
                </td>
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
  );
}
