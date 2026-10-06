"""
Shared data utility functions for CSV Plotter application.

This module centralizes common data transformation functions to avoid
code duplication across data_manager.py, storage_manager.py, and db_schema.py.

Single Source of Truth.
"""

import pandas as pd


def convert_numeric_columns(df):
    """
    Convert DataFrame columns from strings with commas to numeric (float).

    This is critical for CSV files using European number format (comma as decimal separator).
    Without this conversion, numeric data remains as strings which causes matplotlib to plot
    row indices instead of actual values, resulting in straight diagonal lines.

    Args:
        df: pandas DataFrame potentially containing string columns with comma decimals

    Returns:
        DataFrame with numeric columns converted to float64

    Example:
        >>> df = pd.DataFrame({'value': ['1,23', '4,56', '7,89']})
        >>> df = convert_numeric_columns(df)
        >>> df['value'].dtype
        dtype('float64')
    """
    for col in df.columns:
        try:
            # Convert column to string, replace commas with dots, then to numeric
            # errors='coerce' converts invalid values to NaN instead of raising errors
            converted = pd.to_numeric(
                df[col].astype(str).str.replace(',', '.'),
                errors='coerce'
            )
            # Only replace if we got at least ONE valid conversion (not all NaN)
            # This preserves text columns while converting numeric ones
            if converted.notna().any():
                df[col] = converted
        except Exception:
            pass  # Keep original if any error occurs
    return df
