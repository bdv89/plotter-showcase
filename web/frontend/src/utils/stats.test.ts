import { describe, expect, it } from 'vitest';
import { buildStatsGrid, computePopulations, extractedColumnNames, formatStat, DEFAULT_DECIMALS } from './stats';
import type { ExtractedColumns } from './stats';
import type { FileInfo } from '../types';

const file = (id: string, filename: string): FileInfo =>
  ({ file_id: id, filename, columns: [], row_count: 0 });

// Two conditions, 3 + 2 replicates. Token index 1 ("80c" / "120c") is the condition.
const FILES = [
  file('a', 'PEEK_80C_01.csv'),
  file('b', 'PEEK_80C_02.csv'),
  file('c', 'PEEK_80C_03.csv'),
  file('d', 'PEEK_120C_01.csv'),
  file('e', 'PEEK_120C_02.csv'),
];
const ALL = new Set(FILES.map(f => f.file_id));

const val = (v: number) => ({ value: v, precision: 2 });
const EXTRACTED: ExtractedColumns = {
  a: { 'max(F)': val(10) },
  b: { 'max(F)': val(12) },
  c: { 'max(F)': val(14) },
  d: { 'max(F)': val(20) },
  e: { 'max(F)': val(24) },
};

describe('computePopulations', () => {
  it('groups by the picked token and uses the sample SD (n-1)', () => {
    const rows = computePopulations(FILES, ALL, EXTRACTED, [1]);
    expect(rows.map(r => r.label)).toEqual(['120C', '80C']);

    const c80 = rows.find(r => r.label === '80C')!;
    expect(c80.files).toBe(3);
    expect(c80.stats['max(F)'].n).toBe(3);
    expect(c80.stats['max(F)'].mean).toBe(12);
    // sample SD of 10/12/14 is 2 (population SD would be ~1.633)
    expect(c80.stats['max(F)'].sd).toBeCloseTo(2, 10);
    expect(c80.stats['max(F)'].median).toBe(12);
    expect(c80.stats['max(F)'].cv).toBeCloseTo(100 * 2 / 12, 10);
  });

  it('with no token picked, all checked files form ONE population', () => {
    const rows = computePopulations(FILES, ALL, EXTRACTED, []);
    expect(rows).toHaveLength(1);
    expect(rows[0].label).toBe('All checked');
    expect(rows[0].stats['max(F)'].n).toBe(5);
    expect(rows[0].stats['max(F)'].mean).toBe(16);
  });

  it('only counts checked files — unchecking an outlier drops it', () => {
    const rows = computePopulations(FILES, new Set(['a', 'b']), EXTRACTED, [1]);
    expect(rows).toHaveLength(1);
    expect(rows[0].stats['max(F)'].n).toBe(2);
    expect(rows[0].stats['max(F)'].mean).toBe(11);
  });

  it('n = 1 leaves SD and CV empty rather than 0', () => {
    const rows = computePopulations(FILES, new Set(['a']), EXTRACTED, [1]);
    const stat = rows[0].stats['max(F)'];
    expect(stat.n).toBe(1);
    expect(stat.sd).toBeNull();
    expect(stat.cv).toBeNull();
    expect(formatStat(stat, 'sd', 2)).toBe('');
    expect(formatStat(stat, 'mean', 2)).toBe('10.00');
  });

  it('a file missing an extraction lowers that column n only', () => {
    const partial: ExtractedColumns = {
      ...EXTRACTED,
      c: {},  // no max(F) for this replicate
    };
    const rows = computePopulations(FILES, ALL, partial, [1]);
    const c80 = rows.find(r => r.label === '80C')!;
    expect(c80.files).toBe(3);          // still 3 files in the population
    expect(c80.stats['max(F)'].n).toBe(2);  // but only 2 values for this column
  });

  it('extractedColumnNames ignores unchecked files', () => {
    expect(extractedColumnNames(FILES, ALL, EXTRACTED)).toEqual(['max(F)']);
    expect(extractedColumnNames(FILES, new Set<string>(), EXTRACTED)).toEqual([]);
  });
});

describe('buildStatsGrid', () => {
  const rows = computePopulations(FILES, ALL, EXTRACTED, [1]);

  it('renders only the requested statistics — what is unchecked never reaches the figure', () => {
    expect(buildStatsGrid(rows, ['max(F)'], ['n', 'mean', 'cv'], () => 2).headers).toContain('CV%');
    expect(buildStatsGrid(rows, ['max(F)'], ['n', 'mean'], () => 2).headers).not.toContain('CV%');
  });

  it('emits COLUMN-major cells, which is what a Plotly table trace expects', () => {
    const g = buildStatsGrid(rows, ['max(F)'], ['n', 'mean'], () => 2);
    expect(g.headers).toEqual(['Population', 'n', 'mean']);
    // one array per column, each holding one entry per population
    expect(g.columns).toHaveLength(3);
    expect(g.columns[0]).toEqual(['120C', '80C']);
    expect(g.columns[1]).toEqual(['2', '3']);
    expect(g.columns.every(c => c.length === rows.length)).toBe(true);
  });

  it('aligns the population label left and every number right', () => {
    const g = buildStatsGrid(rows, ['max(F)'], ['n', 'mean', 'sd'], () => 2);
    expect(g.aligns).toEqual(['left', 'right', 'right', 'right']);
  });

  it('names each grandeur ONCE, on the first stat of its group', () => {
    const g = buildStatsGrid(rows, ['max(F)', 'other'], ['n', 'mean', 'sd'], () => 2);
    // headers carry only the statistic…
    expect(g.headers).toEqual(['Population', 'n', 'mean', 'SD', 'n', 'mean', 'SD']);
    // …and the grandeur appears once per group, never repeated
    expect(g.groups).toEqual(['', 'max(F)', '', '', 'other', '', '']);
    expect(g.groups.filter(x => x === 'max(F)')).toHaveLength(1);
  });

  it('a single grandeur is named once too, not inlined into every header', () => {
    const g = buildStatsGrid(rows, ['max(F)'], ['mean'], () => 2);
    expect(g.headers).toEqual(['Population', 'mean']);
    expect(g.groups).toEqual(['', 'max(F)']);
  });

  it('widths follow the widest cell, group name included', () => {
    const g = buildStatsGrid(rows, ['max(F)'], ['n'], () => 2);
    expect(g.widths[0]).toBe('Population'.length);
    // 'n' is 1 char but the column must hold 'max(F)' stacked above it
    expect(g.widths[1]).toBe('max(F)'.length);
  });
});

describe('display decimals', () => {
  const rows = computePopulations(FILES, ALL, EXTRACTED, [1]);
  const stat = rows.find(r => r.label === '80C')!.stats['max(F)'];

  it('changes only the rendering — the stored value is untouched', () => {
    expect(formatStat(stat, 'mean', 0)).toBe('12');
    expect(formatStat(stat, 'mean', 4)).toBe('12.0000');
    expect(stat.mean).toBe(12);   // same number in both cases
  });

  it('n stays an integer and CV% one decimal, whatever the column setting', () => {
    expect(formatStat(stat, 'n', 5)).toBe('3');
    expect(formatStat(stat, 'cv', 5)).toBe(formatStat(stat, 'cv', 0));
  });

  it('the grid honours a different precision per column', () => {
    const g = buildStatsGrid(rows, ['max(F)'], ['mean'], () => 1);
    expect(g.columns[1]).toEqual(['22.0', '12.0']);
  });

  it('defaults to 3 decimals', () => {
    expect(DEFAULT_DECIMALS).toBe(3);
    expect(formatStat(stat, 'mean', DEFAULT_DECIMALS)).toBe('12.000');
  });
});
