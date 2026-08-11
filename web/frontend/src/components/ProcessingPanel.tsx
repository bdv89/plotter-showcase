import { useCallback, useMemo } from 'react';
import { useAppStore } from '../store/appStore';
import type { ProcessingSettings } from '../types';
import Plot from 'react-plotly.js';

const DENOISE_METHODS = [
  { value: 'savgol', label: 'Savitzky-Golay' },
  { value: 'median', label: 'Median' },
  { value: 'wavelet', label: 'Wavelet' },
  { value: 'fft', label: 'FFT' },
];

const NORMALIZE_METHODS = [
  { value: 'minmax', label: 'Min-Max' },
  { value: 'zscore', label: 'Z-Score' },
];

const BASELINE_METHODS = [
  { value: 'snip', label: 'SNIP' },
  { value: 'asls', label: 'AsLS' },
  { value: 'arpls', label: 'arPLS' },
];

export function ProcessingPanel() {
  const processing = useAppStore(s => s.processing);
  const setProcessing = useAppStore(s => s.setProcessing);
  const resetProcessing = useAppStore(s => s.resetProcessing);
  const fileStyles = useAppStore(s => s.fileStyles);
  const traces = useAppStore(s => s.traces);

  const update = useCallback((partial: Partial<ProcessingSettings>) => {
    setProcessing(partial);
  }, [setProcessing]);

  // No API call here: `processing` is sent with every /plot-data request
  // (ColumnSelector's auto-plot watches it), so this panel is pure UI over the
  // store. The old "process each file, then re-plot" loop wrote into a
  // server cache keyed on file_id alone → stale as soon as the selection moved.

  const handleReset = useCallback(() => {
    resetProcessing();
  }, [resetProcessing]);

  // Miniature plot data
  const miniData = useMemo(() => {
    return traces.map(trace => {
      const style = fileStyles[trace.file_id || ''];
      return {
        x: trace.x,
        y: trace.y,
        type: 'scatter' as const,
        mode: 'lines' as const,
        line: { color: style?.line_color || '#888', width: 1 },
        showlegend: false,
      };
    });
  }, [traces, fileStyles]);

  return (
    <div className="processing-panel">
      <h3 className="panel-title">Processing</h3>

      {/* Miniature plot */}
      {traces.length > 0 && (
        <div className="mini-plot">
          <Plot
            data={miniData}
            layout={{
              height: 200,
              showlegend: false,
              margin: { l: 30, r: 10, t: 10, b: 30 },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              xaxis: { showgrid: false, zeroline: false, color: 'var(--text-dim)' },
              yaxis: { showgrid: false, zeroline: false, color: 'var(--text-dim)' },
            }}
            config={{ staticPlot: true, displaylogo: false }}
            style={{ width: '100%', height: '200px' }}
            useResizeHandler
          />
        </div>
      )}

      {/* Smoothing */}
      <div className="proc-section">
        <label className="proc-enable">
          <input type="checkbox" checked={processing.smoothing_enabled} onChange={e => update({ smoothing_enabled: e.target.checked })} />
          Smoothing
        </label>
        {processing.smoothing_enabled && (
          <div className="proc-fields">
            <div className="field">
              <label>Window</label>
              <input type="number" min={3} max={101} step={2} value={processing.smoothing_window}
                onChange={e => update({ smoothing_window: Number(e.target.value) })} />
            </div>
          </div>
        )}
      </div>

      {/* Denoise */}
      <div className="proc-section">
        <label className="proc-enable">
          <input type="checkbox" checked={processing.denoise_enabled} onChange={e => update({ denoise_enabled: e.target.checked })} />
          Advanced Denoising
        </label>
        {processing.denoise_enabled && (
          <div className="proc-fields">
            <div className="field">
              <label>Method</label>
              <select value={processing.denoise_method} onChange={e => update({ denoise_method: e.target.value })}>
                {DENOISE_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Window</label>
              <input type="number" min={3} max={101} step={2} value={processing.denoise_window}
                onChange={e => update({ denoise_window: Number(e.target.value) })} />
            </div>
            <div className="field">
              <label>Poly Order</label>
              <input type="number" min={1} max={10} value={processing.denoise_polyorder}
                onChange={e => update({ denoise_polyorder: Number(e.target.value) })} />
            </div>
          </div>
        )}
      </div>

      {/* Normalize */}
      <div className="proc-section">
        <label className="proc-enable">
          <input type="checkbox" checked={processing.normalize_enabled} onChange={e => update({ normalize_enabled: e.target.checked })} />
          Normalize
        </label>
        {processing.normalize_enabled && (
          <div className="proc-fields">
            <div className="field">
              <label>Method</label>
              <select value={processing.normalize_method} onChange={e => update({ normalize_method: e.target.value })}>
                {NORMALIZE_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Baseline */}
      <div className="proc-section">
        <label className="proc-enable">
          <input type="checkbox" checked={processing.baseline_enabled} onChange={e => update({ baseline_enabled: e.target.checked })} />
          Baseline Correction
        </label>
        {processing.baseline_enabled && (
          <div className="proc-fields">
            <div className="field">
              <label>Method</label>
              <select value={processing.baseline_method} onChange={e => update({ baseline_method: e.target.value })}>
                {BASELINE_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
            <div className="field">
              <label>K</label>
              <input type="number" min={1} max={200} value={processing.baseline_k}
                onChange={e => update({ baseline_k: Number(e.target.value) })} />
            </div>
          </div>
        )}
      </div>

      {/* Outlier */}
      <div className="proc-section">
        <label className="proc-enable">
          <input type="checkbox" checked={processing.outlier_enabled} onChange={e => update({ outlier_enabled: e.target.checked })} />
          Outlier Removal
        </label>
        {processing.outlier_enabled && (
          <div className="proc-fields">
            <div className="field">
              <label>Threshold</label>
              <input type="number" min={1} max={10} step={0.5} value={processing.outlier_threshold}
                onChange={e => update({ outlier_threshold: Number(e.target.value) })} />
            </div>
          </div>
        )}
      </div>

      <div className="proc-buttons">
        <button className="reset-button" onClick={handleReset}>Reset</button>
      </div>
    </div>
  );
}
