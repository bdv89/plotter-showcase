"""
Normalization processor (minmax or zscore).
"""

import numpy as np
import pandas as pd


def create_normalize_processor(method: str):
    """Return a normalization processor ('minmax' or 'zscore')."""
    method = (method or 'minmax').lower()

    def _fn(df: pd.DataFrame):
        result = df.copy()
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            s = result[col]
            if method == 'minmax':
                min_v, max_v = s.min(), s.max()
                if max_v > min_v:
                    result[col] = (s - min_v) / (max_v - min_v)
            else:  # zscore
                std = s.std()
                if std and std > 0:
                    result[col] = (s - s.mean()) / std
        return result

    return _fn
