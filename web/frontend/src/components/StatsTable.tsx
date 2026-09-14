import { useMemo, useState } from 'react';
import { useAppStore } from '../store/appStore';
import { computePopulations, extractedColumnNames, formatStat, DEFAULT_DECIMALS, STAT_LABELS } from '../utils/stats';
import { copyToClipboard } from '../utils/clipboard';

// Mean / SD / … of every extracted column, per population. A population is a
// "Group by" key restricted to the checked files (see utils/stats.ts).
export function StatsTable() {
  const files = useAppStore(s => s.files);
  const checkedFiles = useAppStore(s => s.checkedFiles);
  const extractedColumns = useAppStore(s => s.extractedColumns);
  const fileStyles = useAppStore(s => s.fileStyles);
  const seriesTokenIndices = useAppStore(s => s.seriesTokenIndices);
  const statsCols = useAppStore(s => s.statsCols);
  const statsHiddenExtracted = useAppStore(s => s.statsHiddenExtracted);
  const extractedDecimals = useAppStore(s => s.extractedDecimals);
  const [status, setStatus] = useState('');

  // Same display setting as the values table — one source, one look.
  const decimalsOf = (name: string) => extractedDecimals[name] ?? DEFAULT_DECIMALS;

  const columns = useMemo(
    () => extractedColumnNames(files, checkedFiles, extractedColumns)
      .filter(c => !statsHiddenExtracted.includes(c)),
    [files, checkedFiles, extractedColumns, statsHiddenExtracted],
  );

  const rows = useMemo(
    () => computePopulations(files, checkedFiles, extractedColumns, seriesTokenIndices),
    [files, checkedFiles, extractedColumns, seriesTokenIndices],
  );

  // Une population n'a une couleur que si TOUS ses membres la partagent — sans
  // « Group by » les fichiers cochés forment une population multicolore, où une
  // pastille mentirait.
  const popColor = (fileIds: string[]): string | null => {
    const colors = fileIds.map(id => fileStyles[id]?.line_color);
    return colors.length > 0 && colors.every(c => c && c === colors[0]) ? colors[0]! : null;
  };

  if (columns.length === 0 || statsCols.length === 0 || rows.length === 0) {
    return (
      <div className="stats-empty">
        {columns.length === 0
          ? 'Extract a value first — the summary aggregates extracted columns.'
          : 'Pick at least one statistic above.'}
      </div>
    );
  }

  // Same TSV conventions as the per-file copy: tab separated, decimal comma.
  const handleCopy = async () => {
    const header = ['Population', 'Files', ...columns.flatMap(c => statsCols.map(k => `${c} ${STAT_LABELS[k]}`))];
    const body = rows.map(r => [
      r.label,
      String(r.files),
      ...columns.flatMap(c => statsCols.map(k => formatStat(r.stats[c], k, decimalsOf(c)).replace('.', ','))),
    ]);
    const tsv = [header, ...body].map(r => r.join('\t')).join('\n');
    setStatus(await copyToClipboard(tsv) ? `Copié ${rows.length} population(s)` : 'Copie échouée');
    setTimeout(() => setStatus(''), 3000);
  };

  return (
    <div className="stats-table-wrap">
      <div className="stats-table-head">
        <h4>Populations</h4>
        <button onClick={handleCopy} title="Copier le résumé — collable dans un tableur">Copy TSV</button>
        {status && <span className="pool-status">{status}</span>}
      </div>
      <div className="stats-table-scroll">
        <table className="stats-table">
          <thead>
            <tr>
              <th rowSpan={2} className="col-legend-color"></th>
              <th rowSpan={2} className="col-pop">Population</th>
              <th rowSpan={2} className="col-pop-n">Files</th>
              {columns.map(c => (
                <th key={c} colSpan={statsCols.length} className="col-group">{c}</th>
              ))}
            </tr>
            <tr>
              {columns.flatMap(c => statsCols.map(k => (
                <th key={`${c}|${k}`} className="col-stat">{STAT_LABELS[k]}</th>
              )))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.key}>
                <td className="col-legend-color">
                  {popColor(r.fileIds) && (
                    <span className="legend-dot" style={{ background: popColor(r.fileIds)! }} />
                  )}
                </td>
                <td className="col-pop" title={r.label}>{r.label}</td>
                <td className="col-pop-n">{r.files}</td>
                {columns.flatMap(c => statsCols.map(k => (
                  <td key={`${c}|${k}`} className="col-stat">{formatStat(r.stats[c], k, decimalsOf(c))}</td>
                )))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
