import { useMemo } from 'react';
import { useAppStore } from '../store/appStore';
import { STAT_KEYS, STAT_LABELS, extractedColumnNames } from '../utils/stats';

// Shared toggles for the population stats box, rendered BOTH in the Extract tab
// and above the Plot. All state lives in the store (same pattern as StyleBar),
// so the table and the in-figure box never drift apart.
export function StatsBar() {
  const files = useAppStore(s => s.files);
  const checkedFiles = useAppStore(s => s.checkedFiles);
  const extractedColumns = useAppStore(s => s.extractedColumns);
  const statsVisible = useAppStore(s => s.statsVisible);
  const statsCols = useAppStore(s => s.statsCols);
  const statsHiddenExtracted = useAppStore(s => s.statsHiddenExtracted);
  const toggleStatsVisible = useAppStore(s => s.toggleStatsVisible);
  const toggleStatCol = useAppStore(s => s.toggleStatCol);
  const toggleStatsExtracted = useAppStore(s => s.toggleStatsExtracted);

  const columns = useMemo(
    () => extractedColumnNames(files, checkedFiles, extractedColumns),
    [files, checkedFiles, extractedColumns],
  );

  // Nothing extracted yet → nothing to summarize, so no controls.
  if (columns.length === 0) return null;

  return (
    <div className="style-row">
      <div className="control-group" title="Which statistics appear in the summary and in the figure">
        <span className="control-label">Stats</span>
        <button
          className={`token-chip ${statsVisible ? 'active' : ''}`}
          onClick={toggleStatsVisible}
          title="Show / hide the whole stats box"
        >
          {statsVisible ? 'On' : 'Off'}
        </button>
        {STAT_KEYS.map(k => (
          <button
            key={k}
            className={`token-chip ${statsCols.includes(k) ? 'active' : ''}`}
            onClick={() => toggleStatCol(k)}
          >
            {STAT_LABELS[k]}
          </button>
        ))}
      </div>
      <div className="control-group" title="Which extracted columns are summarized">
        <span className="control-label">Columns</span>
        {columns.map(name => (
          <button
            key={name}
            className={`token-chip ${statsHiddenExtracted.includes(name) ? '' : 'active'}`}
            onClick={() => toggleStatsExtracted(name)}
          >
            {name}
          </button>
        ))}
      </div>
    </div>
  );
}
