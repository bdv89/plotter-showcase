import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useAppStore } from '../store/appStore';
import { getPlotData } from '../api/client';

type Tab = 'x' | 'y' | 'y2';

export function ColumnSelector() {
  const files = useAppStore(s => s.files);
  const checkedFiles = useAppStore(s => s.checkedFiles);
  const xColumn = useAppStore(s => s.xColumn);
  const yColumns = useAppStore(s => s.yColumns);
  const y2Columns = useAppStore(s => s.y2Columns);
  const fileStyles = useAppStore(s => s.fileStyles);
  const processing = useAppStore(s => s.processing);
  const setXColumn = useAppStore(s => s.setXColumn);
  const setYColumns = useAppStore(s => s.setYColumns);
  const setY2Columns = useAppStore(s => s.setY2Columns);
  const setTraces = useAppStore(s => s.setTraces);
  const setIsPlotting = useAppStore(s => s.setIsPlotting);
  const isPlotting = useAppStore(s => s.isPlotting);
  const autoPlot = useAppStore(s => s.autoPlot);
  const toggleAutoPlot = useAppStore(s => s.toggleAutoPlot);

  const [activeTab, setActiveTab] = useState<Tab>('x');
  const lastRequestRef = useRef('');

  // Get intersection of columns across all checked files
  const columns = useMemo(() => {
    const checkedArr = Array.from(checkedFiles);
    if (checkedArr.length === 0) return [];
    const checkedFileObjs = files.filter(f => checkedFiles.has(f.file_id));
    if (checkedFileObjs.length === 0) return [];
    const first = checkedFileObjs[0].columns || [];
    return first.filter(col =>
      checkedFileObjs.every(f => f.columns?.includes(col))
    );
  }, [files, checkedFiles]);

  const hasCheckedButNoColumns = checkedFiles.size > 0 && columns.length === 0;

  const toggleYColumn = useCallback((col: string) => {
    setYColumns(
      yColumns.includes(col) ? yColumns.filter(c => c !== col) : [...yColumns, col]
    );
  }, [yColumns, setYColumns]);

  const toggleY2Column = useCallback((col: string) => {
    setY2Columns(
      y2Columns.includes(col) ? y2Columns.filter(c => c !== col) : [...y2Columns, col]
    );
  }, [y2Columns, setY2Columns]);

  const handlePlot = useCallback(async () => {
    const fileIds = Array.from(checkedFiles);
    if (fileIds.length === 0 || !xColumn || yColumns.length === 0) return;

    setIsPlotting(true);
    try {
      const result = await getPlotData({
        file_ids: fileIds,
        x_column: xColumn,
        y_columns: yColumns,
        y2_columns: y2Columns.length > 0 ? y2Columns : undefined,
        styles: fileStyles,
        processing,
      });
      setTraces(result.traces);
    } catch (err) {
      console.error('Plot failed:', err);
    } finally {
      setIsPlotting(false);
    }
  }, [checkedFiles, xColumn, yColumns, y2Columns, fileStyles, processing, setTraces, setIsPlotting]);

  const canPlot = checkedFiles.size > 0 && xColumn && yColumns.length > 0;

  // Auto-plot: trigger plot when inputs change.
  // handlePlot is read through a ref so its identity churn (it depends on
  // fileStyles/processing) doesn't re-run this effect and cancel the pending
  // timer. lastRequestRef is set only when the timer actually fires, so a
  // cancelled timer (StrictMode double-mount or a dep change) always reschedules.
  const checkedFilesArr = useMemo(() => [...checkedFiles].sort(), [checkedFiles]);
  const handlePlotRef = useRef(handlePlot);
  handlePlotRef.current = handlePlot;
  useEffect(() => {
    if (!autoPlot || !canPlot) return;
    const fingerprint = JSON.stringify([checkedFilesArr, xColumn, yColumns, y2Columns]);
    if (fingerprint === lastRequestRef.current) return;
    const timer = setTimeout(() => {
      lastRequestRef.current = fingerprint;
      handlePlotRef.current();
    }, 300);
    return () => clearTimeout(timer);
  }, [autoPlot, canPlot, checkedFilesArr, xColumn, yColumns, y2Columns]);

  return (
    <div className="column-selector">
      <div className="tab-bar">
        <button className={activeTab === 'x' ? 'active' : ''} onClick={() => setActiveTab('x')}>
          X
        </button>
        <button className={activeTab === 'y' ? 'active' : ''} onClick={() => setActiveTab('y')}>
          Y ({yColumns.length})
        </button>
        <button className={activeTab === 'y2' ? 'active' : ''} onClick={() => setActiveTab('y2')}>
          Y2 ({y2Columns.length})
        </button>
      </div>

      <div className="column-list">
        {columns.length === 0 ? (
          <div className="column-empty">
            {hasCheckedButNoColumns
              ? 'No common columns across checked files'
              : 'Check files to see columns'}
          </div>
        ) : activeTab === 'x' ? (
          columns.map(col => (
            <label key={col} className={`column-item ${xColumn === col ? 'selected' : ''}`}>
              <input
                type="radio"
                name="x-column"
                checked={xColumn === col}
                onChange={() => setXColumn(col)}
              />
              {col}
            </label>
          ))
        ) : activeTab === 'y' ? (
          columns.map(col => (
            <label key={col} className={`column-item ${yColumns.includes(col) ? 'selected' : ''}`}>
              <input
                type="checkbox"
                checked={yColumns.includes(col)}
                onChange={() => toggleYColumn(col)}
              />
              {col}
            </label>
          ))
        ) : (
          columns.map(col => (
            <label key={col} className={`column-item ${y2Columns.includes(col) ? 'selected' : ''}`}>
              <input
                type="checkbox"
                checked={y2Columns.includes(col)}
                onChange={() => toggleY2Column(col)}
              />
              {col}
            </label>
          ))
        )}
      </div>

      <div className="plot-controls">
        <label className="auto-plot-toggle">
          <input type="checkbox" checked={autoPlot} onChange={toggleAutoPlot} />
          Auto-plot
        </label>
        {!autoPlot && (
          <button
            className="plot-button"
            disabled={!canPlot || isPlotting}
            onClick={handlePlot}
          >
            {isPlotting ? 'Plotting...' : 'Plot'}
          </button>
        )}
        {autoPlot && isPlotting && <span className="plot-status">Plotting...</span>}
      </div>
    </div>
  );
}
