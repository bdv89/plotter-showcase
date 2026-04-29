"""
Baseline correction processor.
"""

import numpy as np
import pandas as pd
from baseline_correction import subtract_baseline


def create_baseline_processor(x_col: str, method: str, params: dict):
    """Return a baseline correction processor using subtract_baseline."""
    method = (method or '').lower()
    params = dict(params or {})

    def _fn(df: pd.DataFrame):
        result = df.copy()

        if not x_col or x_col not in result.columns:
            return result

        x_data = result[x_col].values
        numeric_cols = result.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            if col == x_col:
                continue

            try:
                y_data = result[col].values
                y_corrected, _ = subtract_baseline(
                    x_data,
                    y_data,
                    method=method,
                    **params
                )
                result[col] = y_corrected
            except Exception:
                # Skip columns that fail (e.g., insufficient data)
                pass

        return result

    return _fn
