// Population statistics over EXTRACTED columns (one scalar per file).
// A "population" is a group of files sharing the same "Group by" key — i.e. the
// same tokens of their filename. Only CHECKED files count, so unchecking an
// outlier replicate immediately drops it out of the n / mean / SD.
//
// Nothing here talks to the backend: the extracted values already live in the
// store, and mean/SD of a handful of numbers is plain arithmetic.

import type { FileInfo } from '../types';
import { seriesKey, seriesLabel } from './coloring';

export const STAT_KEYS = ['n', 'mean', 'sd', 'cv', 'min', 'max', 'median'] as const;
export type StatKey = typeof STAT_KEYS[number];

// Decimals shown per extracted column. Capped at 6 because that is what the
// backend actually keeps: api/extract.py rounds with `round(result, precision)`
// and client.ts never sends one, so the Pydantic default of 6 applies. Asking
// for more would print rounding zeros as if they were measurement.
export const MIN_DECIMALS = 0;
export const MAX_DECIMALS = 6;
export const DEFAULT_DECIMALS = 3;

export const clampDecimals = (n: number): number =>
  Math.max(MIN_DECIMALS, Math.min(MAX_DECIMALS, Math.round(n)));

export const STAT_LABELS: Record<StatKey, string> = {
  n: 'n', mean: 'mean', sd: 'SD', cv: 'CV%', min: 'min', max: 'max', median: 'med',
};

export type ExtractedColumns = Record<string, Record<string, { value: number; precision: number }>>;

// null = not computable (e.g. SD of a single sample) — rendered as an empty cell,
// never as 0, which would read as "no dispersion".
// No `precision` here: how many decimals to show is a display setting per
// extracted column (store: extractedPrecision), not a property of the data.
export type ColumnStats = Record<StatKey, number | null>;

export interface PopulationRow {
  key: string;    // seriesKey — identity
  label: string;  // seriesLabel — what the user reads
  files: number;  // files in the population (all checked members)
  fileIds: string[];  // members, so a view can read their legend color

  stats: Record<string, ColumnStats>;  // extracted column name -> stats
}

/** Sample standard deviation (n-1). null below 2 samples. */
function sampleSd(values: number[], mean: number): number | null {
  if (values.length < 2) return null;
  const ss = values.reduce((acc, v) => acc + (v - mean) ** 2, 0);
  return Math.sqrt(ss / (values.length - 1));
}

function median(sorted: number[]): number {
  const m = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[m] : (sorted[m - 1] + sorted[m]) / 2;
}

function statsOf(values: number[]): ColumnStats {
  const n = values.length;
  const mean = values.reduce((a, b) => a + b, 0) / n;
  const sd = sampleSd(values, mean);
  const sorted = [...values].sort((a, b) => a - b);
  return {
    n,
    mean,
    sd,
    cv: sd != null && mean !== 0 ? (sd / mean) * 100 : null,
    min: sorted[0],
    max: sorted[n - 1],
    median: median(sorted),
  };
}

/** Extracted column names present on the checked files, in insertion order. */
export function extractedColumnNames(
  files: FileInfo[], checkedFiles: Set<string>, extractedColumns: ExtractedColumns,
): string[] {
  const names: string[] = [];
  files.forEach(f => {
    if (!checkedFiles.has(f.file_id)) return;
    Object.keys(extractedColumns[f.file_id] || {}).forEach(name => {
      if (!names.includes(name)) names.push(name);
    });
  });
  return names;
}

/**
 * Group the checked files by their "Group by" key and aggregate every extracted
 * column. With no token picked, all checked files form ONE population — which is
 * the useful degenerate case, not an error.
 */
export function computePopulations(
  files: FileInfo[],
  checkedFiles: Set<string>,
  extractedColumns: ExtractedColumns,
  seriesTokenIndices: number[],
): PopulationRow[] {
  const checked = files.filter(f => checkedFiles.has(f.file_id));
  if (checked.length === 0) return [];

  const groups = new Map<string, { label: string; members: FileInfo[] }>();
  checked.forEach(f => {
    const key = seriesKey(f.filename, seriesTokenIndices);
    const label = seriesTokenIndices.length === 0 ? 'All checked' : seriesLabel(f.filename, seriesTokenIndices);
    if (!groups.has(key)) groups.set(key, { label, members: [] });
    groups.get(key)!.members.push(f);
  });

  const columns = extractedColumnNames(files, checkedFiles, extractedColumns);

  return [...groups.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([key, { label, members }]) => {
      const stats: Record<string, ColumnStats> = {};
      columns.forEach(name => {
        const values: number[] = [];
        members.forEach(f => {
          const cell = extractedColumns[f.file_id]?.[name];
          // A file missing this extraction simply doesn't count for THIS column,
          // so the n is per column and may be below the population size.
          if (cell && Number.isFinite(cell.value)) values.push(cell.value);
        });
        if (values.length > 0) stats[name] = statsOf(values);
      });
      return { key, label, files: members.length, fileIds: members.map(f => f.file_id), stats };
    });
}

/**
 * Display string for one cell. `decimals` is the per-column display setting —
 * the stored value is untouched, so changing it never needs a re-extraction.
 * n is always an integer and CV% always one decimal: neither carries the unit
 * of the measurement, so the column setting does not apply to them.
 */
export function formatStat(stat: ColumnStats | undefined, k: StatKey, decimals: number): string {
  if (!stat) return '';
  const v = stat[k];
  if (v == null) return '';
  if (k === 'n') return String(v);
  if (k === 'cv') return v.toFixed(1);
  return v.toFixed(decimals);
}

export interface StatsGrid {
  headers: string[];              // stat label, one per column
  groups: string[];               // extracted-column name, ONLY on the first stat
                                  // of each group ('' elsewhere) — see below
  columns: string[][];            // column-major cells, parallel to headers
  aligns: ('left' | 'right')[];   // labels left, numbers right
  widths: number[];               // relative column widths (widest cell)
}

/**
 * The summary as a real grid — headers plus COLUMN-MAJOR cells, which is exactly
 * what a Plotly `table` trace expects. Only the statistics passed in appear, so
 * what is unchecked in the UI is absent from the exported figure too.
 *
 * Column-major, not row-major: a table trace takes one array per column.
 *
 * Two-level header: a Plotly table has a SINGLE header row (no colSpan), so the
 * extracted-column name would otherwise be repeated on every statistic
 * ("max(F) n", "max(F) mean", "max(F) SD"). `groups` carries it once, on the
 * first stat of its group, and the renderer stacks the two lines with <br>.
 */
export function buildStatsGrid(
  rows: PopulationRow[],
  columns: string[],
  statsCols: readonly StatKey[],
  decimalsOf: (column: string) => number,
): StatsGrid {
  const headers = ['Population', ...columns.flatMap(() => statsCols.map(k => STAT_LABELS[k]))];
  const groups = ['', ...columns.flatMap(c => statsCols.map((_, i) => (i === 0 ? c : '')))];
  const cells: string[][] = [
    rows.map(r => r.label),
    ...columns.flatMap(c => statsCols.map(k => rows.map(r => formatStat(r.stats[c], k, decimalsOf(c))))),
  ];
  return {
    headers,
    groups,
    columns: cells,
    aligns: headers.map((_, i) => (i === 0 ? 'left' : 'right')),
    // The group name sits above the first column of its group, so that column
    // must be wide enough to hold it — otherwise a long name spills over its
    // neighbour. Plotly normalizes these, so raw character counts are enough.
    widths: headers.map((h, i) => Math.max(h.length, groups[i].length, ...cells[i].map(v => v.length))),
  };
}
