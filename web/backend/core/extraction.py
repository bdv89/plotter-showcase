"""
Data extraction functions - adapted from data_extraction.py (NO PyQt).

Pure functions for computing statistical metrics from data columns.
"""

import traceback

import numpy as np


def compute_linear_slope(y_series, x_series):
    """Compute slope using linear regression

    Args:
        y_series: Y values (pandas Series)
        x_series: X values (pandas Series)

    Returns:
        float: Slope of linear regression
    """
    from scipy import stats

    min_len = min(len(x_series), len(y_series))
    x = x_series.iloc[:min_len].values
    y = y_series.iloc[:min_len].values

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return slope


def interpolate_at_x(y_series, x_series, target_x):
    """Find Y value at specific X using interpolation

    Args:
        y_series: Y values (pandas Series)
        x_series: X values (pandas Series)
        target_x: Target X value to interpolate at

    Returns:
        float: Interpolated Y value at target_x
    """
    from scipy.interpolate import interp1d

    min_len = min(len(x_series), len(y_series))
    x = x_series.iloc[:min_len].values
    y = y_series.iloc[:min_len].values

    f = interp1d(x, y, kind='linear', fill_value=np.nan, bounds_error=False)
    result = float(f(target_x))
    if np.isnan(result):
        print(f"⚠️ Interpolation returned NaN: target_x={target_x} is outside data range [{x.min()}, {x.max()}]")
    return result


def y_at_max_x(y_series, x_series):
    """Extract Y value when X is at maximum

    Args:
        y_series: Y values (pandas Series)
        x_series: X values (pandas Series)

    Returns:
        float: Y value at index where X is maximum
    """
    max_idx = x_series.idxmax()
    return float(y_series.loc[max_idx])


def y_at_condition(y_series, condition_series, operator, threshold, fallback_type='none', fallback_value=None):
    """Extract Y value when condition column crosses threshold

    Args:
        y_series: Y values to extract (pandas Series)
        condition_series: Column to check condition against (pandas Series)
        operator: '>' or '<'
        threshold: Threshold value (float)
        fallback_type: 'none', 'custom', 'first', 'last' (default: 'none')
        fallback_value: Custom fallback value (only used if fallback_type='custom')

    Returns:
        float: Y value at first point where condition is met, or fallback value
        None: if condition never met AND no fallback configured
    """
    if operator == '>':
        mask = condition_series > threshold
    elif operator == '<':
        mask = condition_series < threshold
    else:
        raise ValueError(f"Unsupported operator: {operator}")

    matching_indices = condition_series[mask].index

    if len(matching_indices) == 0:
        print(f"⚫ Condition never met, applying fallback: {fallback_type}")

        if fallback_type == 'custom':
            if fallback_value is None:
                print("❌ Custom fallback requested but no value provided")
                return None
            print(f"✅ Using custom fallback value: {fallback_value}")
            return float(fallback_value)
        elif fallback_type == 'first':
            result = float(y_series.iloc[0])
            print(f"✅ Using first Y value as fallback: {result}")
            return result
        elif fallback_type == 'last':
            result = float(y_series.iloc[-1])
            print(f"✅ Using last Y value as fallback: {result}")
            return result
        else:
            print("❌ Condition never met, no fallback configured")
            return None

    first_match_idx = matching_indices[0]
    result = float(y_series.loc[first_match_idx])
    print(f"✅ Condition met at index {first_match_idx}, Y = {result}")
    return result


# OPERATIONS dict - SINGLE SOURCE OF TRUTH
OPERATIONS = {
    'Max': ('basic', lambda series: series.max()),
    'Min': ('basic', lambda series: series.min()),
    'Mean': ('basic', lambda series: series.mean()),
    'Median': ('basic', lambda series: series.median()),
    'Std Dev': ('basic', lambda series: series.std()),
    'Integral': ('needs_x', lambda series, x_series: np.trapz(series.values, x_series.values)),
    'Slope': ('needs_x', compute_linear_slope),
    'Y at max(X)': ('needs_x', y_at_max_x),
    'Value at X': ('needs_x_value', interpolate_at_x),
    'Y when X > threshold': ('conditional', lambda y, cond, op, thresh, fb_type='none', fb_val=None:
                                            y_at_condition(y, cond, op, thresh, fb_type, fb_val)),
    'Y when X < threshold': ('conditional', lambda y, cond, op, thresh, fb_type='none', fb_val=None:
                                            y_at_condition(y, cond, op, thresh, fb_type, fb_val)),
}


def compute_extraction(df, column, operation, x_column=None, x_value=None,
                       condition_column=None, threshold=None, operator=None,
                       fallback_type='none', fallback_value=None,
                       x_min=None, x_max=None):
    """Compute a single extraction on a DataFrame.

    Args:
        df: pandas DataFrame
        column: Column name to analyze
        operation: Operation name (must be in OPERATIONS dict)
        x_column: X column name (for operations that need it)
        x_value: Target X value (for 'Value at X')
        condition_column: Condition column (for conditional operations)
        threshold: Threshold value (for conditional operations)
        operator: '>' or '<' (for conditional operations)
        fallback_type: 'none', 'custom', 'first', 'last'
        fallback_value: Custom fallback value
        x_min: Lower bound of an optional X interval (rows with X >= x_min)
        x_max: Upper bound of an optional X interval (rows with X <= x_max)

    Returns:
        float or None: Extracted value, or None if error
    """
    print(f"🟡 Computing {operation} for column '{column}'")

    try:
        if column not in df.columns:
            print(f"❌ Column '{column}' not found")
            return None

        # Optional X-interval filter: restrict the DataFrame to rows where
        # x_min <= X <= x_max BEFORE computing the operation. Honors a single
        # bound if the other is None. Applies to every operation (basic + needs_x).
        if x_min is not None or x_max is not None:
            if not x_column or x_column not in df.columns:
                print(f"❌ X interval requested but X column '{x_column}' not found")
                return None
            xcol = df[x_column]
            mask = xcol.notna()
            if x_min is not None:
                mask &= xcol >= x_min
            if x_max is not None:
                mask &= xcol <= x_max
            df = df[mask]
            print(f"🟡 X interval [{x_min}, {x_max}] → {len(df)} points")
            if len(df) == 0:
                print(f"❌ No data points in X interval [{x_min}, {x_max}]")
                return None

        series = df[column].dropna()

        if len(series) == 0:
            print(f"❌ Column '{column}' has no valid data")
            return None

        if operation not in OPERATIONS:
            print(f"❌ Unknown operation: {operation}")
            return None

        op_type, op_func = OPERATIONS[operation]

        if op_type == 'basic':
            result = op_func(series)

        elif op_type == 'needs_x':
            if not x_column or x_column not in df.columns:
                print(f"❌ X column '{x_column}' not found")
                return None
            x_series = df[x_column].dropna()
            min_len = min(len(series), len(x_series))
            series = series.iloc[:min_len]
            x_series = x_series.iloc[:min_len]
            result = op_func(series, x_series)

        elif op_type == 'needs_x_value':
            if not x_column or x_column not in df.columns:
                print(f"❌ X column '{x_column}' not found")
                return None
            if x_value is None:
                print("❌ X value not provided")
                return None
            x_series = df[x_column].dropna()
            min_len = min(len(series), len(x_series))
            series = series.iloc[:min_len]
            x_series = x_series.iloc[:min_len]
            result = op_func(series, x_series, x_value)

        elif op_type == 'conditional':
            if not condition_column or condition_column not in df.columns:
                print(f"❌ Condition column '{condition_column}' not found")
                return None
            if threshold is None:
                print("❌ Threshold not provided")
                return None
            if not operator:
                operator = '>' if '>' in operation else '<'

            cond_series = df[condition_column].dropna()
            min_len = min(len(series), len(cond_series))
            series = series.iloc[:min_len]
            cond_series = cond_series.iloc[:min_len]
            result = y_at_condition(series, cond_series, operator, threshold, fallback_type, fallback_value)

        else:
            print(f"❌ Unknown operation type: {op_type}")
            return None

        print(f"✅ {operation}({column}) = {result}")
        return result

    except Exception as e:
        print(f"🔴 Extraction failed: {e}")
        traceback.print_exc()
        return None
