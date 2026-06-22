"""Processing endpoints - apply data pipeline to files."""

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from models.schemas import ProcessRequest
from sessions import HEAVY_SEM, get_session
from state import AppState

router = APIRouter()


@router.post("/process")
def process_file(req: ProcessRequest, state: AppState = Depends(get_session)):
    """Apply processing pipeline to a file, return processed column data.

    Accepts settings like: smoothing_enabled, smoothing_window, denoise_enabled,
    denoise_method, denoise_window, denoise_polyorder, normalize_enabled,
    normalize_method, baseline_enabled, baseline_method, baseline_k,
    outlier_enabled, outlier_threshold.
    """
    print(f"🟢 Process request for {req.file_id}")

    if req.file_id not in state.files:
        raise HTTPException(status_code=404, detail=f"File '{req.file_id}' not found")

    df = state.files[req.file_id]['data'].copy()
    settings = req.settings

    # Cap concurrent heavy CPU work across all sessions (queue if saturated).
    with HEAVY_SEM:
        if settings.get('outlier_enabled', False):
            threshold = settings.get('outlier_threshold', 3.0)
            df = _remove_outliers(df, threshold)
            print(f"🟡 Outlier removal: threshold={threshold}")

        if settings.get('smoothing_enabled', False):
            window = int(settings.get('smoothing_window', 5))
            df = _smooth(df, window)
            print(f"🟡 Smoothing: window={window}")

        if settings.get('denoise_enabled', False):
            method = settings.get('denoise_method', 'savgol')
            window = int(settings.get('denoise_window', 11))
            polyorder = int(settings.get('denoise_polyorder', 3))
            df = _denoise(df, method, window=window, polyorder=polyorder)
            print(f"🟡 Denoising: method={method}")

        if settings.get('baseline_enabled', False):
            method = settings.get('baseline_method', 'snip')
            k = int(settings.get('baseline_k', 12))
            df = _baseline(df, method, k)
            print(f"🟡 Baseline correction: method={method}, K={k}")

        if settings.get('normalize_enabled', False):
            method = settings.get('normalize_method', 'minmax')
            df = _normalize(df, method)
            print(f"🟡 Normalize: method={method}")

    processed = df

    # Cache processed result
    state.cache_put(req.file_id, processed)
    state.processing_settings[req.file_id] = settings

    # Return column data
    result = {}
    for col in processed.columns:
        result[col] = processed[col].where(processed[col].notna(), None).tolist()

    print(f"✅ Processed {req.file_id}: {len(processed)} rows, {len(processed.columns)} cols")
    return {
        "file_id": req.file_id,
        "row_count": len(processed),
        "columns": list(processed.columns),
        "data": result,
    }


# --- Helper functions ---

def _remove_outliers(df, threshold):
    """Replace outliers with NaN using z-score (per-column, preserves row count)."""
    result = df.copy()
    numeric_cols = result.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        std = result[col].std()
        if std > 0:
            z_scores = np.abs((result[col] - result[col].mean()) / std)
            result.loc[z_scores >= threshold, col] = np.nan
    return result


def _smooth(df, window):
    """Apply rolling average smoothing."""
    result = df.copy()
    numeric_cols = result.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        result[col] = result[col].rolling(window=window, center=True).mean()
    return result


def _denoise(df, method, **kwargs):
    """Apply denoising."""
    from core.denoise_methods import denoise
    return denoise(df, method=method, **kwargs)


def _baseline(df, method, k):
    """Apply baseline correction to numeric columns (skips all-NaN / bad columns)."""
    from core.baseline_correction import subtract_baseline
    result = df.copy()
    numeric_cols = result.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        s = result[col]
        if s.notna().sum() == 0:
            continue  # all-NaN column: nothing to correct
        try:
            y_corrected, _ = subtract_baseline(result.index.values, s.values, method=method, K=k)
            result[col] = y_corrected
        except Exception as e:
            print(f"⚠️ baseline skipped column '{col}': {e}")
    return result


def _normalize(df, method):
    """Normalize numeric columns."""
    result = df.copy()
    numeric_cols = result.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
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
    return result
