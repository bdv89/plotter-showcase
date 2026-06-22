"""
Data loader - adapted from data_manager.py (NO PyQt).

Pure Python functions for loading CSV and Excel files.
"""

import os
from io import StringIO

import pandas as pd
from core.data_utils import convert_numeric_columns


def detect_csv_format(file_path: str) -> dict:
    """Auto-detect CSV format (delimiter, header line, units line).

    Args:
        file_path: Path to CSV file

    Returns:
        dict with keys: delimiter, header_line, units_line
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            preview_lines = []
            for _ in range(30):
                line = f.readline()
                if not line:
                    break
                preview_lines.append(line)
    except UnicodeDecodeError:
        raise ValueError(f"{file_path} appears to be a binary file or uses an unsupported encoding")

    if not preview_lines:
        raise ValueError(f"{file_path} is empty")

    # Header is always on line 0. Pick delimiter from the first line.
    first = preview_lines[0]
    if ';' in first:
        return {'delimiter': ';', 'header_line': 0, 'units_line': None}
    elif '\t' in first:
        return {'delimiter': '\t', 'header_line': 0, 'units_line': None}
    else:
        # Default: comma
        return {'delimiter': ',', 'header_line': 0, 'units_line': None}


def parse_csv(file_path: str, delimiter=None, header_line=0, units_line=None) -> dict:
    """Parse a CSV file and return data, headers, units.

    Args:
        file_path: Path to CSV file
        delimiter: Column delimiter (auto-detected if None)
        header_line: Line number of headers (0-based)
        units_line: Line number of units (None if no units row)

    Returns:
        dict with keys: data (DataFrame), headers (list), units (dict)
    """
    if delimiter is None:
        fmt = detect_csv_format(file_path)
        delimiter = fmt['delimiter']
        header_line = fmt['header_line']
        units_line = fmt['units_line']

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if not lines:
        return {'data': pd.DataFrame(), 'headers': [], 'units': {}}

    # Get headers
    headers = [h.strip() for h in lines[header_line].strip().split(delimiter)]

    # Process units if available
    units = {}
    if units_line is not None and units_line < len(lines):
        unit_values = [u.strip() for u in lines[units_line].strip().split(delimiter)]
        if len(headers) == len(unit_values):
            units = {header: unit for header, unit in zip(headers, unit_values)}

    # Find start of data
    data_start = header_line + 1
    if units_line is not None:
        data_start = units_line + 2  # Skip units line and an extra line

    data_lines = [line.strip() for line in lines[data_start:] if line.strip()]

    if not data_lines:
        return {'data': pd.DataFrame(columns=headers), 'headers': headers, 'units': units}

    # Parse data
    decimal_sep = ',' if delimiter == ';' else '.'
    data_buffer = StringIO("\n".join(data_lines))

    try:
        df = pd.read_csv(
            data_buffer,
            sep=delimiter,
            header=None,
            names=headers,
            decimal=decimal_sep,
            engine='python'
        )
    except Exception as e:
        print(f"❌ Error parsing CSV data from {file_path}: {e}")
        df = pd.DataFrame(columns=headers)

    # Apply numeric conversion
    df = convert_numeric_columns(df)

    return {'data': df, 'headers': headers, 'units': units}


def parse_excel(file_path: str, sheet_name=0, header_line=0, units_line=None) -> dict:
    """Parse an Excel file and return data, headers, units.

    Args:
        file_path: Path to Excel file
        sheet_name: Sheet name or index
        header_line: Line number of headers (0-based)
        units_line: Line number of units (None if no units row)

    Returns:
        dict with keys: data (DataFrame), headers (list), units (dict)
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    engine = 'openpyxl' if file_ext == '.xlsx' else None

    df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_line, engine=engine)

    headers = df.columns.tolist()
    units = {}

    if units_line is not None and units_line > header_line:
        units_df = pd.read_excel(
            file_path, sheet_name=sheet_name,
            header=None, skiprows=units_line, nrows=1, engine=engine
        )
        if not units_df.empty:
            units_row = units_df.iloc[0].tolist()
            for i, header in enumerate(headers):
                if i < len(units_row) and pd.notna(units_row[i]):
                    units[header] = str(units_row[i])

            # Re-read data skipping the units line
            skip_rows = list(range(header_line + 1, units_line + 1))
            df = pd.read_excel(
                file_path, sheet_name=sheet_name,
                header=header_line, skiprows=skip_rows, engine=engine
            )

    # Apply numeric conversion
    df = convert_numeric_columns(df)

    return {'data': df, 'headers': headers, 'units': units}


def load_file(file_path: str) -> dict:
    """Auto-detect format and load a file.

    Args:
        file_path: Path to CSV or Excel file

    Returns:
        dict with keys: data (DataFrame), headers (list), units (dict)
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext in ('.xlsx', '.xls'):
        print(f"🟡 Loading Excel file: {file_path}")
        result = parse_excel(file_path)
    elif ext in ('.csv', '.txt', '.tsv'):
        print(f"🟡 Loading CSV file: {file_path}")
        result = parse_csv(file_path)
    else:
        # Try CSV as default
        print(f"🟡 Loading file as CSV (unknown ext): {file_path}")
        result = parse_csv(file_path)

    row_count = len(result['data']) if result['data'] is not None else 0
    col_count = len(result['headers'])
    print(f"✅ Loaded {os.path.basename(file_path)}: {row_count} rows, {col_count} columns")

    return result
