"""Data processing pipeline — the single implementation.

Applied INLINE by /plot-data and /extract. There is deliberately no separate
/process endpoint: processing that runs beside the read path can never go stale,
whereas the old side-channel wrote into a cache keyed on file_id alone, so a file
checked after the settings changed was plotted raw (see PITFALLS #34).

Only the columns actually being read are processed — the X column is never
touched (min-max normalising X used to squash the axis into 0-1).
"""

import json

import numpy as np
import pandas as pd
from core.baseline_correction import subtract_baseline
from core.denoise_methods import denoise
from sessions import HEAVY_SEM

# Each denoise method takes its OWN kwargs. Passing window=/polyorder= to all of
# them raised TypeError (500) for median/wavelet/fft — and denoise() only catches
# ValueError, so it escaped as a 500 the frontend swallowed in console.error.
DENOISE_KWARGS = {
    'savgol': lambda s: {
        'window': int(s.get('denoise_window', 11)),
        'polyorder': int(s.get('denoise_polyorder', 3)),
    },
    'median': lambda s: {'kernel_size': int(s.get('denoise_window', 5))},
    'wavelet': lambda s: {},                    # wavelet_denoise defaults (db4, soft)
    'fft': lambda s: {'cutoff_freq': 0.1},      # fraction of Nyquist
}

ENABLE_FLAGS = (
    'outlier_enabled', 'smoothing_enabled', 'denoise_enabled',
    'baseline_enabled', 'normalize_enabled',
)


def is_active(settings: dict) -> bool:
    """True if at least one processing step is switched on."""
    return any(settings.get(flag, False) for flag in ENABLE_FLAGS)


def apply_processing(
    df: pd.DataFrame,
    settings: dict,
    columns: list[str],
    x_column: str = "",
) -> pd.DataFrame:
    """Run the enabled processing steps on `columns` only, return a new DataFrame.

    Order: outliers → smoothing → denoise → baseline → normalize.
    Every step degrades per column (a bad column is skipped, not the whole file).
    """
    if not is_active(settings) or not columns:
        return df

    cols = [c for c in columns if c in df.columns
            and pd.api.types.is_numeric_dtype(df[c])]
    if not cols:
        return df

    result = df.copy()
    # Real x values when usable (baseline is x-aware), row index otherwise.
    if x_column in df.columns and pd.api.types.is_numeric_dtype(df[x_column]):
        x_values = df[x_column].values
    else:
        x_values = df.index.values

    # Cap concurrent heavy CPU work across all sessions (queue if saturated).
    with HEAVY_SEM:
        if settings.get('outlier_enabled', False):
            threshold = float(settings.get('outlier_threshold', 3.0))
            _remove_outliers(result, cols, threshold)
            print(f"🟡 Outlier removal: threshold={threshold} on {len(cols)} col(s)")

        if settings.get('smoothing_enabled', False):
            window = int(settings.get('smoothing_window', 5))
            _smooth(result, cols, window)
            print(f"🟡 Smoothing: window={window}")

        if settings.get('denoise_enabled', False):
            method = str(settings.get('denoise_method', 'savgol')).lower()
            _denoise(result, cols, method, settings)
            print(f"🟡 Denoising: method={method}")

        if settings.get('baseline_enabled', False):
            method = settings.get('baseline_method', 'snip')
            k = int(settings.get('baseline_k', 40))
            _baseline(result, cols, x_values, method, k)
            print(f"🟡 Baseline correction: method={method}, K={k}")

        if settings.get('normalize_enabled', False):
            method = settings.get('normalize_method', 'minmax')
            _normalize(result, cols, method)
            print(f"🟡 Normalize: method={method}")

    return result


def apply_processing_cached(
    state,
    file_id: str,
    df: pd.DataFrame,
    settings: dict,
    columns: list[str],
    x_column: str = "",
) -> pd.DataFrame:
    """apply_processing + per-session LRU cache.

    The cache key carries the SETTINGS and the columns, so a stale entry is
    impossible — that was the root cause of the old side-channel bug.
    """
    if not is_active(settings) or not columns:
        return df

    key = "|".join([
        file_id,
        json.dumps(settings, sort_keys=True, default=str),
        ",".join(sorted(columns)),
        x_column,
    ])
    cached = state.cache_get(key)
    if cached is not None:
        return cached

    processed = apply_processing(df, settings, columns, x_column)
    state.cache_put(key, processed)
    return processed


# --- Steps (mutate `result` in place, per column) ---

def _remove_outliers(result: pd.DataFrame, cols: list[str], threshold: float) -> None:
    """Replace outliers with NaN using z-score (preserves row count)."""
    for col in cols:
        std = result[col].std()
        if std > 0:
            z_scores = np.abs((result[col] - result[col].mean()) / std)
            result.loc[z_scores >= threshold, col] = np.nan


def _smooth(result: pd.DataFrame, cols: list[str], window: int) -> None:
    """Rolling average. min_periods=1 keeps the edges instead of NaN-ing them."""
    for col in cols:
        result[col] = result[col].rolling(window=window, center=True, min_periods=1).mean()


def _denoise(result: pd.DataFrame, cols: list[str], method: str, settings: dict) -> None:
    """Denoise column by column with the kwargs that method actually accepts."""
    kwargs = DENOISE_KWARGS.get(method, DENOISE_KWARGS['savgol'])(settings)
    for col in cols:
        s = result[col]
        if s.notna().sum() == 0:
            continue  # all-NaN column (e.g. METADATA): nothing to denoise
        try:
            result[col] = denoise(s, method=method, **kwargs)
        except (ValueError, TypeError) as e:
            # e.g. column shorter than the window — leave it unchanged
            print(f"⚠️ denoise skipped column '{col}': {e}")


def _baseline(result: pd.DataFrame, cols: list[str], x_values, method: str, k: int) -> None:
    """Baseline correction against the REAL x column (not the row index)."""
    for col in cols:
        s = result[col]
        if s.notna().sum() == 0:
            continue  # all-NaN column: nothing to correct
        try:
            y_corrected, _ = subtract_baseline(x_values, s.values, method=method, K=k)
            result[col] = y_corrected
        except Exception as e:
            print(f"⚠️ baseline skipped column '{col}': {e}")


def _normalize(result: pd.DataFrame, cols: list[str], method: str) -> None:
    for col in cols:
        if method == 'minmax':
            min_val = result[col].min()
            max_val = result[col].max()
            if max_val > min_val:
                result[col] = (result[col] - min_val) / (max_val - min_val)
        elif method == 'zscore':
            mean = result[col].mean()
            std = result[col].std()
            if std > 0:
                result[col] = (result[col] - mean) / std
