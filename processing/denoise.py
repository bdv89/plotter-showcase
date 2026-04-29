"""
Advanced denoising processor for signal cleaning.
"""

import pandas as pd


def create_denoise_processor(method: str, params: dict):
    """Return an advanced denoising processor."""
    from denoise_methods import denoise

    # Map UI display names to method codes
    # Source UI: plot_processing_window.py:140
    method_map = {
        'savitzky-golay': 'savgol',
        'median filter': 'median',
        'wavelet': 'wavelet',
        'fft low-pass': 'fft'
    }
    method_code = method_map.get(method.lower(), method.lower())

    def _fn(df: pd.DataFrame):
        try:
            return denoise(df, method=method_code, **params)
        except Exception:
            # Silently fall back to original data if denoising fails
            return df

    return _fn
