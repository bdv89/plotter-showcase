"""
Outliers removal processor using z-score.
"""

import numpy as np
import pandas as pd


def create_outliers_processor(threshold: float):
    """Return a simple z-score outlier removal processor."""
    threshold = float(threshold)

    def _fn(df: pd.DataFrame):
        result = df.copy()
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            s = result[col]
            std = s.std()
            if std and std > 0:
                z = (s - s.mean()) / std
                result = result[np.abs(z) < threshold]
        return result

    return _fn
