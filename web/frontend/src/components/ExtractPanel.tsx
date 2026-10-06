import { useState, useCallback, useMemo } from 'react';
import { useAppStore } from '../store/appStore';
import type { ExtractRecipe } from '../types';
import { removeExtractedColumn as removeExtractedColumnApi } from '../api/client';
import { runRecipe as runRecipeOn } from '../utils/recipes';
import { copyToClipboard } from '../utils/clipboard';
import { DEFAULT_DECIMALS, MAX_DECIMALS, MIN_DECIMALS } from '../utils/stats';
import { SeriesPicker } from './SeriesPicker';
import { StatsBar } from './StatsBar';
import { StatsTable } from './StatsTable';

const OPERATIONS = [
  { value: 'max', label: 'Max' },
  { value: 'min', label: 'Min' },
  { value: 'mean', label: 'Mean' },
  { value: 'median', label: 'Median' },
  { value: 'std', label: 'Std Dev' },
  { value: 'integral', label: 'Integral' },
  { value: 'slope', label: 'Slope' },
  { value: 'y_at_max_x', label: 'Y at max(X)' },
  { value: 'value_at_x', label: 'Value at X' },
  { value: 'y_when_x_gt', label: 'Y when X > threshold' },
  { value: 'y_when_x_lt', label: 'Y when X < threshold' },
];

const NEEDS_X_COLUMN = ['integral', 'slope', 'y_at_max_x', 'value_at_x', 'y_when_x_gt', 'y_when_x_lt'];
const NEEDS_X_VALUE = ['value_at_x'];
const NEEDS_THRESHOLD = ['y_when_x_gt', 'y_when_x_lt'];

// The Extract tab: settings, per-file values, and the population summary.
// Replaces the old modal — its preview table was a duplicate of the values table
// that now sits right below the settings and updates live.
export function ExtractPanel() {
  const files = useAppStore(s => s.files);
  const checkedFiles = useAppStore(s => s.checkedFiles);
  const fileStyles = useAppStore(s => s.fileStyles);
  const extractedColumns = useAppStore(s => s.extractedColumns);
  const extractRecipes = useAppStore(s => s.extractRecipes);
  const setExtractRecipe = useAppStore(s => s.setExtractRecipe);
  const removeExtractedColumn = useAppStore(s => s.removeExtractedColumn);
  const clearExtractedColumns = useAppStore(s => s.clearExtractedColumns);
  const toggleFile = useAppStore(s => s.toggleFile);
  const extractedDecimals = useAppStore(s => s.extractedDecimals);
  const setExtractedDecimals = useAppStore(s => s.setExtractedDecimals);

  const [column, setColumn] = useState('');
  const [operation, setOperation] = useState('max');
  const [xColumn, setXColumn] = useState('');
  const [xValue, setXValue] = useState(0);
  const [threshold, setThreshold] = useState(0);
  // Filtre optionnel sur un intervalle X (ex. moyenne de Y pour X entre min et max).
  const [useXRange, setUseXRange] = useState(false);
  const [xMin, setXMin] = useState('');
  const [xMax, setXMax] = useState('');
  const [customName, setCustomName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  const checkedFileList = useMemo(() =>
    files.filter(f => checkedFiles.has(f.file_id)),
    [files, checkedFiles]
  );

  const columns = useMemo(() => {
    if (checkedFileList.length === 0) return [];
    return checkedFileList[0].columns;
  }, [checkedFileList]);

  const needsXColumn = NEEDS_X_COLUMN.includes(operation);
  const needsXValue = NEEDS_X_VALUE.includes(operation);
  const needsThreshold = NEEDS_THRESHOLD.includes(operation);
  // X column est requise si l'opération en a besoin OU si on filtre sur un intervalle X.
  const showXColumn = needsXColumn || useXRange;
  // Bornes parsées : champ vide = borne ouverte (undefined).
  const xMinNum = xMin.trim() === '' ? undefined : Number(xMin);
  const xMaxNum = xMax.trim() === '' ? undefined : Number(xMax);

  // Decimals are a per-column DISPLAY setting, adjustable any time from the
  // column header — no re-extraction to change how a number reads.
  const decimalsOf = (name: string) => extractedDecimals[name] ?? DEFAULT_DECIMALS;

  // Union of extracted column names over ALL files (not just the checked ones),
  // so a column stays reachable — and deletable — whatever is checked.
  const extraCols = useMemo(() => {
    const names: string[] = [];
    Object.values(extractedColumns).forEach(cols => {
      Object.keys(cols).forEach(n => { if (!names.includes(n)) names.push(n); });
    });
    return names;
  }, [extractedColumns]);

  // Colonnes rejouables = celles dont on a gardé la recette. Une colonne d'un
  // pool sauvé avant les recettes reste affichée, simplement pas rejouable.
  const replayable = useMemo(
    () => extraCols.filter(n => extractRecipes[n]),
    [extraCols, extractRecipes]
  );

  // « Extract » exécute une recette fraîche, « Re-extract » rejoue celles déjà
  // enregistrées — sur les fichiers cochés. Même code que le suivi de dossier
  // (utils/recipes.ts) → une valeur recalculée est identique à la valeur d'origine.
  const runRecipe = useCallback(
    (colName: string, recipe: ExtractRecipe) =>
      runRecipeOn(colName, recipe, checkedFileList.map(f => f.file_id)),
    [checkedFileList]
  );

  // Compute + store in one go: the values table below IS the preview.
  const handleExtract = useCallback(async () => {
    if (!column) { setError('Select a column'); return; }
    if (checkedFileList.length === 0) { setError('No files checked'); return; }
    const rangeSuffix = useXRange ? `[X:${xMin || '…'}–${xMax || '…'}]` : '';
    const colName = (customName || `${operation}(${column})${rangeSuffix}`).trim();
    if (!colName) { setError('Enter a column name'); return; }

    const recipe: ExtractRecipe = {
      column,
      operation,
      x_column: showXColumn ? xColumn : undefined,
      x_value: needsXValue ? xValue : undefined,
      x_min: useXRange ? xMinNum : undefined,
      x_max: useXRange ? xMaxNum : undefined,
      threshold: needsThreshold ? threshold : undefined,
      condition_column: needsThreshold ? xColumn : undefined,
      operator: operation === 'y_when_x_gt' ? '>' : operation === 'y_when_x_lt' ? '<' : undefined,
    };

    setLoading(true);
    setError('');
    try {
      const ok = await runRecipe(colName, recipe);
      setExtractRecipe(colName, recipe);
      setStatus(`${colName} — ${ok}/${checkedFileList.length} valeur(s)`);
      setTimeout(() => setStatus(''), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extraction failed');
    } finally {
      setLoading(false);
    }
  }, [column, operation, xColumn, xValue, threshold, checkedFileList, showXColumn, needsXValue,
      needsThreshold, useXRange, xMinNum, xMaxNum, xMin, xMax, customName, runRecipe,
      setExtractRecipe]);

  // Rejoue TOUTES les colonnes rejouables sur les fichiers cochés du moment :
  // les nouveaux fichiers se remplissent, les anciens sont recalculés. Pas de
  // mode « ne combler que les trous » — ça laisserait survivre des valeurs
  // périmées si le traitement a changé entre-temps.
  const handleReExtract = useCallback(async () => {
    if (checkedFileList.length === 0) { setError('No files checked'); return; }
    setLoading(true);
    setError('');
    try {
      for (const name of replayable) {
        await runRecipe(name, extractRecipes[name]);
      }
      const skipped = extraCols.length - replayable.length;
      setStatus(
        `${replayable.length} colonne(s) × ${checkedFileList.length} fichier(s)`
        + (skipped > 0 ? ` — ${skipped} sans recette, ignorée(s)` : '')
      );
      setTimeout(() => setStatus(''), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extraction failed');
    } finally {
      setLoading(false);
    }
  }, [checkedFileList, replayable, extraCols, extractRecipes, runRecipe]);

  // Server + store, so the column doesn't come back on reload.
  const handleDeleteExtracted = async (name: string) => {
    if (!window.confirm(`Supprimer la colonne « ${name} » ?`)) return;
    try {
      await removeExtractedColumnApi(name);
    } catch (err) {
      console.error('Failed to delete extracted column:', err);
    }
    removeExtractedColumn(name);
  };

  const handleClearExtracted = async () => {
    if (!window.confirm('Supprimer toutes les colonnes extraites ?')) return;
    try {
      await removeExtractedColumnApi();
    } catch (err) {
      console.error('Failed to clear extracted columns:', err);
    }
    clearExtractedColumns();
  };

  // Copy checked files as TSV (Filename, Legend, extracted columns) for spreadsheets.
  const handleCopyData = async () => {
    if (checkedFileList.length === 0) {
      setStatus('Aucun fichier coché');
      setTimeout(() => setStatus(''), 3000);
      return;
    }
    const cols: string[] = [];
    checkedFileList.forEach(f => {
      Object.keys(extractedColumns[f.file_id] || {}).forEach(c => {
        if (!cols.includes(c)) cols.push(c);
      });
    });
    const header = ['Filename', 'Legend', ...cols];
    const body = checkedFileList.map(f => {
      const legend = fileStyles[f.file_id]?.legend_label || f.filename.replace(/\.[^.]+$/, '');
      const values = cols.map(c => {
        const e = extractedColumns[f.file_id]?.[c];
        return e ? e.value.toFixed(decimalsOf(c)).replace('.', ',') : '';
      });
      return [f.filename, legend, ...values];
    });
    const tsv = [header, ...body].map(r => r.join('\t')).join('\n');
    setStatus(await copyToClipboard(tsv) ? `Copié ${checkedFileList.length} ligne(s)` : 'Copie échouée');
    setTimeout(() => setStatus(''), 3000);
  };

  if (files.length === 0) {
    return <div className="file-table-empty">No files loaded</div>;
  }

  return (
    <div className="extract-panel">
      <div className="extract-settings">
        {checkedFileList.length === 0 ? (
          <div className="modal-warning">No files checked. Check files in the Data tab first.</div>
        ) : (
          <div className="extract-fields">
            <div className="field">
              <label>Column to analyze</label>
              <select value={column} onChange={e => setColumn(e.target.value)}>
                <option value="">-- Select --</option>
                {columns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div className="field">
              <label>Operation</label>
              <select value={operation} onChange={e => setOperation(e.target.value)}>
                {OPERATIONS.map(op => <option key={op.value} value={op.value}>{op.label}</option>)}
              </select>
            </div>

            {showXColumn && (
              <div className="field">
                <label>X Column</label>
                <select value={xColumn} onChange={e => setXColumn(e.target.value)}>
                  <option value="">-- Select --</option>
                  {columns.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            )}

            {needsXValue && (
              <div className="field">
                <label>X Value</label>
                <input type="number" step="any" value={xValue} onChange={e => setXValue(Number(e.target.value))} />
              </div>
            )}

            {needsThreshold && (
              <div className="field">
                <label>Threshold</label>
                <input type="number" step="any" value={threshold} onChange={e => setThreshold(Number(e.target.value))} />
              </div>
            )}

            <div className="field">
              <label>
                <input
                  type="checkbox"
                  checked={useXRange}
                  onChange={e => setUseXRange(e.target.checked)}
                />
                {' '}Restrict to X interval
              </label>
              {useXRange && (
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="number" step="any" placeholder="X min"
                    value={xMin} onChange={e => setXMin(e.target.value)}
                  />
                  <input
                    type="number" step="any" placeholder="X max"
                    value={xMax} onChange={e => setXMax(e.target.value)}
                  />
                </div>
              )}
            </div>

            <div className="field">
              <label>Custom column name</label>
              <input
                type="text"
                placeholder={`${operation}(${column || '...'})`}
                value={customName}
                onChange={e => setCustomName(e.target.value)}
              />
            </div>

            <div className="field extract-actions">
              <button className="apply-button" onClick={handleExtract} disabled={loading}>
                {loading ? 'Computing…' : `Extract (${checkedFileList.length})`}
              </button>
            </div>
          </div>
        )}
        {error && <div className="modal-error">{error}</div>}
      </div>

      <div className="extract-values">
        <div className="stats-table-head">
          <h4>Values</h4>
          {replayable.length > 0 && (
            <button
              onClick={handleReExtract}
              disabled={loading || checkedFileList.length === 0}
              title={`Rejouer ${replayable.length} extraction(s) sur les ${checkedFileList.length} fichier(s) coché(s)`
                + (extraCols.length > replayable.length
                  ? ` — ${extraCols.length - replayable.length} colonne(s) sans recette seront ignorées`
                  : '')}
            >
              {loading ? 'Computing…' : `↻ Re-extract (${replayable.length})`}
            </button>
          )}
          <button onClick={handleCopyData} title="Copier (filename, legend, colonnes extraites)">Copy TSV</button>
          {extraCols.length > 0 && (
            <button onClick={handleClearExtracted} title="Delete all extracted columns">Clear extracted</button>
          )}
          {status && <span className="pool-status">{status}</span>}
        </div>
        <div className="stats-table-scroll">
          <table className="file-table">
            <thead>
              <tr>
                <th className="col-check"></th>
                <th className="col-legend-color"></th>
                <th className="col-filename">Filename</th>
                {extraCols.map(name => (
                  <th key={name} className="col-extracted">
                    <div className="col-extracted-head">
                      <span className="col-extracted-name" title={name}>{name}</span>
                      <button
                        className="delete-btn"
                        title={`Delete column "${name}"`}
                        onClick={() => handleDeleteExtracted(name)}
                      >
                        ✕
                      </button>
                    </div>
                    <div className="decimals-control" title="Décimales affichées (0–6) — n'affecte que l'affichage">
                      <button
                        onClick={() => setExtractedDecimals(name, decimalsOf(name) - 1)}
                        disabled={decimalsOf(name) <= MIN_DECIMALS}
                      >
                        −
                      </button>
                      <span>{decimalsOf(name)} dec.</span>
                      <button
                        onClick={() => setExtractedDecimals(name, decimalsOf(name) + 1)}
                        disabled={decimalsOf(name) >= MAX_DECIMALS}
                      >
                        +
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {files.map(file => {
                const fileExtracted = extractedColumns[file.file_id] || {};
                const isChecked = checkedFiles.has(file.file_id);
                return (
                  <tr key={file.file_id} className={isChecked ? 'row-checked' : ''}>
                    <td className="col-check">
                      <input type="checkbox" checked={isChecked} onChange={() => toggleFile(file.file_id)} />
                    </td>
                    <td className="col-legend-color">
                      {/* Même couleur que la courbe : on relie une ligne du
                          tableau à une courbe du plot sans la chercher. */}
                      <span
                        className="legend-dot"
                        style={{ background: fileStyles[file.file_id]?.line_color || '#e27d60' }}
                      />
                    </td>
                    <td className="col-filename" title={file.filename}>{file.filename}</td>
                    {extraCols.map(name => {
                      const ext = fileExtracted[name];
                      return (
                        <td key={name} className="col-extracted">
                          {ext != null ? ext.value.toFixed(decimalsOf(name)) : '-'}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="extract-summary">
        {/* Group by defines the populations, so it belongs here as much as in
            the DATA toolbar — same store state, same control. */}
        <div className="style-row"><SeriesPicker /></div>
        <StatsBar />
        <StatsTable />
      </div>
    </div>
  );
}
