import { useState, useCallback, useMemo } from 'react';
import { useAppStore } from '../store/appStore';
import { extractData } from '../api/client';

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

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ExtractionModal({ open, onClose }: Props) {
  const files = useAppStore(s => s.files);
  const checkedFiles = useAppStore(s => s.checkedFiles);
  const processing = useAppStore(s => s.processing);
  const setExtractedColumn = useAppStore(s => s.setExtractedColumn);

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
  const [precision, setPrecision] = useState(4);
  const [preview, setPreview] = useState<Record<string, number | null> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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

  const handlePreview = useCallback(async () => {
    if (!column) { setError('Select a column'); return; }
    if (checkedFileList.length === 0) { setError('No files checked'); return; }

    setLoading(true);
    setError('');
    try {
      const result = await extractData({
        file_ids: checkedFileList.map(f => f.file_id),
        column,
        operation,
        x_column: showXColumn ? xColumn : undefined,
        x_value: needsXValue ? xValue : undefined,
        x_min: useXRange ? xMinNum : undefined,
        x_max: useXRange ? xMaxNum : undefined,
        threshold: needsThreshold ? threshold : undefined,
        condition_column: needsThreshold ? xColumn : undefined,
        operator: operation === 'y_when_x_gt' ? '>' : operation === 'y_when_x_lt' ? '<' : undefined,
        processing,
      });
      setPreview(result.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extraction failed');
    } finally {
      setLoading(false);
    }
  }, [column, operation, xColumn, xValue, threshold, checkedFileList, showXColumn, needsXValue, needsThreshold, useXRange, xMinNum, xMaxNum, processing]);

  const handleApply = useCallback(() => {
    if (!preview) return;
    const rangeSuffix = useXRange ? `[X:${xMin || '…'}–${xMax || '…'}]` : '';
    const colName = customName || `${operation}(${column})${rangeSuffix}`;
    if (!colName.trim()) { setError('Enter a column name'); return; }

    Object.entries(preview).forEach(([fileId, value]) => {
      if (value != null) {
        setExtractedColumn(fileId, colName, value, precision);
      }
    });
    onClose();
  }, [preview, customName, operation, column, precision, useXRange, xMin, xMax, setExtractedColumn, onClose]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Extract Data</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body">
          {checkedFileList.length === 0 ? (
            <div className="modal-warning">No files checked. Check files in the table first.</div>
          ) : (
            <>
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

              <div className="field">
                <label>
                  <input
                    type="checkbox"
                    checked={useXRange}
                    onChange={e => setUseXRange(e.target.checked)}
                  />
                  {' '}Restrict to X interval
                </label>
              </div>

              {useXRange && (
                <div className="field">
                  <label>X interval (min / max — leave one empty for an open bound)</label>
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
                <label>Custom column name</label>
                <input
                  type="text"
                  placeholder={`${operation}(${column || '...'})`}
                  value={customName}
                  onChange={e => setCustomName(e.target.value)}
                />
              </div>

              <div className="field">
                <label>Precision</label>
                <input type="number" min={0} max={15} value={precision} onChange={e => setPrecision(Number(e.target.value))} />
              </div>

              {error && <div className="modal-error">{error}</div>}

              <div className="modal-buttons">
                <button className="preview-button" onClick={handlePreview} disabled={loading}>
                  {loading ? 'Computing...' : 'Preview'}
                </button>
                <button className="apply-button" onClick={handleApply} disabled={!preview}>
                  Apply
                </button>
              </div>

              {preview && (
                <div className="preview-results">
                  <h4>Preview Results</h4>
                  <table className="preview-table">
                    <thead>
                      <tr>
                        <th>File</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {checkedFileList.map(f => (
                        <tr key={f.file_id}>
                          <td>{f.filename}</td>
                          <td>
                            {preview[f.file_id] != null
                              ? preview[f.file_id]!.toFixed(precision)
                              : 'N/A'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
