"""
Smoothing processor using rolling mean.
"""

import numpy as np
import pandas as pd


def create_smooth_processor(window: int):
    """Return a rolling mean processor for the given window size."""
    window = max(1, int(window))

    def _fn(df: pd.DataFrame):
        result = df.copy()
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            # Use min_periods=1 to avoid NaNs at edges
            result[col] = result[col].rolling(window=window, center=True, min_periods=1).mean()
        return result

    return _fn
