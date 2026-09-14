import { useMemo, Fragment } from 'react';
import { useAppStore } from '../store/appStore';
import { displayTokens } from '../utils/coloring';

// "Group by": click the parts of an example filename that define a series.
// One control, three placements (DATA toolbar, above the Plot, Extract tab) —
// the state lives in the store, so they can never disagree.
//
// The same key drives BOTH the coloring and the populations of the Extract tab,
// which is why this had to stop being buried inside StyleBar.
export function SeriesPicker() {
  const files = useAppStore(s => s.files);
  const seriesTokenIndices = useAppStore(s => s.seriesTokenIndices);
  const toggleSeriesToken = useAppStore(s => s.toggleSeriesToken);
  const clearSeries = useAppStore(s => s.clearSeries);

  const exampleTokens = useMemo(
    () => (files.length > 0 ? displayTokens(files[0].filename) : []),
    [files],
  );

  if (exampleTokens.length === 0) return null;

  return (
    <div
      className="control-group series-picker"
      title="Define what makes a series / a population (click a part of the example name)"
    >
      <span className="control-label">Group by</span>
      <button
        className={`token-chip ${seriesTokenIndices.length === 0 ? 'active' : ''}`}
        onClick={clearSeries}
      >
        Auto
      </button>
      <span className="series-eg">e.g.</span>
      {exampleTokens.map((tok, i) => (
        <Fragment key={i}>
          {i > 0 && <span className="series-sep">·</span>}
          <button
            className={`token-chip ${seriesTokenIndices.includes(i) ? 'active' : ''}`}
            onClick={() => toggleSeriesToken(i)}
          >
            {tok}
          </button>
        </Fragment>
      ))}
    </div>
  );
}
