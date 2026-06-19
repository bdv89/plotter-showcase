"""
Time-window averaging processor for oscillation data reduction.
Extracted from tribolab_method.py - preserves performance optimizations.
"""

import pandas as pd
from typing import List, Dict

# Polars for high-performance data operations (preferred)
try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

# NumPy for vectorized operations (fallback)
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _average_with_polars(
    data_rows: List[List[float]],
    column_names: List[str],
    time_points: List[float],
    window_radius: float,
    window_offset: float
) -> List[List[float]]:
    """
    High-performance averaging using Polars DataFrame operations.

    Expected speedup: 10-50x over NumPy on large datasets due to:
    - Rust-based implementation with SIMD
    - Query optimizer
    - Multi-threaded execution
    - Columnar data format (Apache Arrow)

    Args:
        data_rows: List of data rows [Time, Fx, Fz, ...]
        column_names: Column names (first must be "Time")
        time_points: Center times for averaging windows
        window_radius: Half-width of averaging window
        window_offset: Offset to shift window centers

    Returns:
        List of averaged rows with exact center times
    """
    if not data_rows:
        return []

    # Convert to Polars DataFrame
    df = pl.DataFrame(data_rows, schema=column_names, orient="row")

    # Ensure sorted by time (required for efficient filtering)
    df = df.sort("Time")

    result_rows = []

    for center_time in time_points:
        # Calculate window bounds
        window_start = max(0, center_time - window_radius + window_offset)
        window_end = center_time + window_radius + window_offset

        # Filter to window using Polars expressions (lazy evaluation + optimized)
        window_df = df.filter(
            (pl.col("Time") >= window_start) & (pl.col("Time") < window_end)
        )

        if window_df.height > 0:  # If rows exist in window
            # Compute mean across all columns (vectorized in Rust)
            avg_dict = window_df.mean().to_dicts()[0]

            # Override time with exact center time
            avg_dict["Time"] = center_time

            # Convert dict to list in correct column order
            avg_row = [avg_dict[col] for col in column_names]
            result_rows.append(avg_row)

    return result_rows


def _average_with_numpy(
    data_rows: List[List[float]],
    time_points: List[float],
    window_radius: float,
    window_offset: float
) -> List[List[float]]:
    """
    Vectorized averaging using NumPy with binary search optimization.

    Uses np.searchsorted for O(log n) window bounds lookup instead of O(n) boolean masking.
    """
    # Convert to NumPy array for vectorized operations
    data_array = np.array(data_rows)
    time_col = data_array[:, 0]

    result_rows = []

    for center_time in time_points:
        # Calculate window bounds
        window_start = max(0, center_time - window_radius + window_offset)
        window_end = center_time + window_radius + window_offset

        # Binary search for window boundaries (O(log n) vs O(n) for boolean mask)
        start_idx = np.searchsorted(time_col, window_start, side='left')
        end_idx = np.searchsorted(time_col, window_end, side='left')

        if end_idx > start_idx:
            # Slice array directly (faster than boolean indexing)
            window_data = data_array[start_idx:end_idx]
            # Vectorized mean across all columns
            avg_row = np.mean(window_data, axis=0).tolist()
            # Override time with exact center time
            avg_row[0] = center_time
            result_rows.append(avg_row)

    return result_rows


def _average_with_python(
    data_rows: List[List[float]],
    time_points: List[float],
    window_radius: float,
    window_offset: float
) -> List[List[float]]:
    """Fallback averaging using pure Python (slower but no NumPy dependency)."""
    result_rows = []

    for center_time in time_points:
        window_start = max(0, center_time - window_radius + window_offset)
        window_end = center_time + window_radius + window_offset

        # Select rows within window
        window_rows = [row for row in data_rows if window_start <= row[0] < window_end]

        if window_rows:
            # Calculate average for each column
            num_cols = len(window_rows[0])
            avg_row = []
            for col_idx in range(num_cols):
                col_sum = sum(row[col_idx] for row in window_rows)
                avg_row.append(col_sum / len(window_rows))

            # Override time with exact center time
            avg_row[0] = center_time
            result_rows.append(avg_row)

    return result_rows


def _average_data_windows(
    data_rows: List[List[float]],
    column_names: List[str],
    params: Dict[str, float],
    use_polars: bool = True
) -> List[List[float]]:
    """
    Perform time-window averaging on data rows.

    Fallback chain: Polars (fastest) → NumPy (fast) → Pure Python (baseline)

    Args:
        data_rows: List of data rows [Time, Fx, Fz, ...]
        column_names: Column names (first is Time)
        params: Processing parameters (start_time, first_interval, etc.)
        use_polars: Use Polars for high-performance operations if available

    Returns:
        List of averaged rows
    """
    if not data_rows:
        return []

    # Extract parameters
    start_time = params["start_time"]
    first_interval = params["first_interval"]
    regular_interval = params["regular_interval"]
    window_size = params["window_size"]
    window_offset = params["window_offset"]

    window_radius = window_size / 2
    max_time = max(row[0] for row in data_rows)

    # Generate time points
    time_points = [start_time]
    time_points.append(start_time + first_interval)
    current_time = time_points[-1]
    while current_time < max_time - regular_interval:
        current_time += regular_interval
        time_points.append(round(current_time, 4))

    # Fallback chain: Polars → NumPy → Python
    if use_polars and HAS_POLARS:
        return _average_with_polars(data_rows, column_names, time_points, window_radius, window_offset)
    elif HAS_NUMPY:
        return _average_with_numpy(data_rows, time_points, window_radius, window_offset)
    else:
        return _average_with_python(data_rows, time_points, window_radius, window_offset)


def _average_data_windows_df(
    df: pd.DataFrame,
    time_column: str,
    params: Dict[str, float]
) -> pd.DataFrame:
    """
    DataFrame wrapper for time-window averaging.

    Args:
        df: Input DataFrame with time_column + numeric columns
        time_column: Name of time column
        params: {start_time, first_interval, regular_interval, window_size, window_offset}

    Returns:
        Averaged DataFrame with same columns
    """
    if df.empty or time_column not in df.columns:
        return df

    # Sort by time column first (required for correct averaging)
    df_sorted = df.sort_values(by=time_column).reset_index(drop=True)

    # Convert DataFrame → List[List[float]]
    # Time column MUST be first
    other_cols = [c for c in df_sorted.columns if c != time_column]
    ordered_cols = [time_column] + other_cols
    data_rows = df_sorted[ordered_cols].values.tolist()

    # Call existing averaging function
    result_rows = _average_data_windows(
        data_rows,
        column_names=ordered_cols,
        params=params,
        use_polars=HAS_POLARS
    )

    # Convert back to DataFrame
    if not result_rows:
        return pd.DataFrame(columns=ordered_cols)

    return pd.DataFrame(result_rows, columns=ordered_cols)


def create_time_averaging_processor(
    time_column: str,
    start_time: float,
    first_interval: float,
    regular_interval: float,
    window_size: float,
    window_offset: float
):
    """
    Create time-window averaging processor.

    Args:
        time_column: Name of column containing time values
        start_time: First time point (seconds)
        first_interval: Interval to second point (seconds)
        regular_interval: Interval for subsequent points (seconds)
        window_size: Averaging window size (seconds)
        window_offset: Window center offset (seconds)

    Returns:
        Processor function (df → df)
    """
    params = {
        "start_time": start_time,
        "first_interval": first_interval,
        "regular_interval": regular_interval,
        "window_size": window_size,
        "window_offset": window_offset,
    }

    def _processor(df: pd.DataFrame) -> pd.DataFrame:
        return _average_data_windows_df(df, time_column, params)

    return _processor
