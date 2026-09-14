/* eslint-disable @typescript-eslint/no-explicit-any */
import { beforeEach, describe, expect, it } from 'vitest';
import { useAppStore } from './appStore';

const reset = () =>
  useAppStore.setState({
    statsVisible: true,
    statsCols: ['n', 'mean', 'sd'],
    statsHiddenExtracted: [],
    hiddenLegend: [],
  });

describe('stats box store', () => {
  beforeEach(reset);

  it('toggleStatCol keeps the canonical column order, not the click order', () => {
    const { toggleStatCol } = useAppStore.getState();
    toggleStatCol('max');
    toggleStatCol('cv');
    // STAT_KEYS order is n, mean, sd, cv, min, max, median
    expect(useAppStore.getState().statsCols).toEqual(['n', 'mean', 'sd', 'cv', 'max']);
  });

  it('toggleStatCol removes an active column', () => {
    useAppStore.getState().toggleStatCol('sd');
    expect(useAppStore.getState().statsCols).toEqual(['n', 'mean']);
  });

  it('extracted columns are a blacklist, so a new extraction shows up by default', () => {
    const { toggleStatsExtracted } = useAppStore.getState();
    toggleStatsExtracted('max(F)');
    expect(useAppStore.getState().statsHiddenExtracted).toEqual(['max(F)']);
    toggleStatsExtracted('max(F)');
    expect(useAppStore.getState().statsHiddenExtracted).toEqual([]);
  });

  it('restorePool reads the stats box back out of plot_style', () => {
    useAppStore.getState().restorePool({
      files: [],
      styles: {},
      extracted: {},
      plot_style: {
        title_text: 'kept',
        stats: {
          visible: false,
          cols: ['n', 'median'],
          hiddenExtracted: ['slope(F)'],
        },
      } as any,
    });
    const s = useAppStore.getState();
    expect(s.statsVisible).toBe(false);
    expect(s.statsCols).toEqual(['n', 'median']);
    expect(s.statsHiddenExtracted).toEqual(['slope(F)']);
    // …and never leaks the wrapper into plotStyle itself
    expect(s.plotStyle.title_text).toBe('kept');
    expect('stats' in s.plotStyle).toBe(false);
  });

  it('a pool saved before this feature restores the defaults', () => {
    useAppStore.setState({ statsVisible: true, statsCols: ['min'] });
    useAppStore.getState().restorePool({
      files: [], styles: {}, extracted: {},
      plot_style: { title_text: 'old pool' } as any,
    });
    const s = useAppStore.getState();
    // Le tableau de stats est OFF par défaut : un vieux pool ne le rallume pas.
    expect(s.statsVisible).toBe(false);
    expect(s.statsCols).toEqual(['n', 'mean', 'sd']);
  });
});

describe('legend visibility', () => {
  beforeEach(() => useAppStore.setState({ hiddenLegend: [] }));

  it('toggling a legend entry adds and removes it', () => {
    const { toggleHiddenLegend } = useAppStore.getState();
    toggleHiddenLegend('80C');
    expect(useAppStore.getState().hiddenLegend).toEqual(['80C']);
    toggleHiddenLegend('80C');
    expect(useAppStore.getState().hiddenLegend).toEqual([]);
  });

  it('isolate hides every other entry, and a second isolate restores all', () => {
    const all = ['80C', '120C', '160C'];
    const { isolateLegend } = useAppStore.getState();
    isolateLegend('80C', all);
    expect(useAppStore.getState().hiddenLegend.sort()).toEqual(['120C', '160C']);
    isolateLegend('80C', all);
    expect(useAppStore.getState().hiddenLegend).toEqual([]);
  });

  it('isolate on a lone entry is a no-op rather than hiding everything', () => {
    useAppStore.getState().isolateLegend('80C', ['80C']);
    expect(useAppStore.getState().hiddenLegend).toEqual([]);
  });

  it('survives a pool round-trip — a figure reopens the way it was saved', () => {
    useAppStore.getState().restorePool({
      files: [], styles: {}, extracted: {},
      plot_style: { title_text: 'x', hiddenLegend: ['120C'] } as any,
    });
    expect(useAppStore.getState().hiddenLegend).toEqual(['120C']);
    expect('hiddenLegend' in useAppStore.getState().plotStyle).toBe(false);
  });
});
