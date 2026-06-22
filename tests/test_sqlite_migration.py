"""Tests for the SQLite pool format (core.db_schema).

Covers: schema creation, save/load round-trip, and raw-SQL inspectability.
"""

import sqlite3

import pandas as pd
from core.db_schema import create_schema, load_from_sqlite, save_to_sqlite

EXPECTED_TABLES = {"files", "file_data", "styles", "extracted_columns", "pool_settings", "fit_results"}


def test_schema_creation(tmp_path):
    db = tmp_path / "schema.db"
    conn = sqlite3.connect(db)
    try:
        create_schema(conn.cursor())
        conn.commit()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert EXPECTED_TABLES <= tables, f"missing tables: {EXPECTED_TABLES - tables}"


def test_save_load_roundtrip(tmp_path):
    db = tmp_path / "roundtrip.db"
    df1 = pd.DataFrame({
        "Time(s)": [0, 1, 2, 3],
        "Voltage(V)": [1.0, 1.1, 1.2, 1.3],
        "Current(A)": [0.1, 0.2, 0.3, 0.4],
    })
    df2 = pd.DataFrame({"Time(s)": [0, 1, 2], "Force(N)": [10.0, 20.0, 30.0]})

    data_pool = {
        "csv_files": [
            {
                "filename": "test1.csv",
                "data": df1,
                "headers": list(df1.columns),
                "units": {"Time(s)": "s", "Voltage(V)": "V", "Current(A)": "A"},
                "extracted_data": {
                    "Max Voltage": {"value": 1.3, "operation": "Max", "precision": 6}
                },
            },
            {
                "filename": "test2.csv",
                "data": df2,
                "headers": list(df2.columns),
                "units": {"Time(s)": "s", "Force(N)": "N"},
            },
        ],
        "line_colors": {"test1.csv": "#FF0000", "test2.csv": "#0000FF"},
        "line_colors_y2": {},
        "line_styles": {"test1.csv": "-", "test2.csv": "--"},
        "legend_labels": {"test1.csv": "Experiment 1", "test2.csv": "Experiment 2"},
        "plot_settings": {"x_column": "Time(s)", "y_columns": ["Voltage(V)"], "y2_columns": []},
        "checked_files": ["test1.csv"],
        "metadata": {"version": "1.0.0", "timestamp": "2025-12-14T12:00:00"},
        "plot_style_settings": {"grid": True},
        "processing_settings": {"smooth": {"enabled": True, "window": 5}},
        "fit_results": {"test1.csv": {"method": "gauss", "peaks": [{"x": 1.5, "y": 1.15}]}},
        "extracted_column_sort_state": {5: "asc"},
    }

    save_to_sqlite(data_pool, str(db))
    assert db.exists() and db.stat().st_size > 0

    loaded = load_from_sqlite(str(db))

    assert len(loaded["csv_files"]) == 2
    file1 = loaded["csv_files"][0]
    assert file1["filename"] == "test1.csv"
    assert file1["data"].shape == df1.shape
    assert file1["data"].iloc[0].equals(df1.iloc[0])
    assert file1["extracted_data"]["Max Voltage"]["value"] == 1.3
    assert loaded["line_colors"]["test1.csv"] == "#FF0000"
    assert loaded["plot_settings"]["x_column"] == "Time(s)"
    assert loaded["fit_results"]["test1.csv"]["method"] == "gauss"


def test_inspect_with_raw_sql(tmp_path):
    db = tmp_path / "inspect.db"
    df = pd.DataFrame({"X": [1, 2, 3], "Y": [10, 20, 30]})
    data_pool = {
        "csv_files": [
            {
                "filename": "data.csv",
                "data": df,
                "headers": ["X", "Y"],
                "units": {},
                "extracted_data": {"Max Y": {"value": 30.0, "operation": "Max", "precision": 6}},
            }
        ],
        "line_colors": {}, "line_colors_y2": {}, "line_styles": {}, "legend_labels": {},
        "plot_settings": {}, "checked_files": [],
        "metadata": {"version": "1.0.0", "timestamp": "2025-12-14"},
        "plot_style_settings": {}, "processing_settings": {}, "fit_results": {},
        "extracted_column_sort_state": {},
    }
    save_to_sqlite(data_pool, str(db))

    conn = sqlite3.connect(db)
    try:
        extracted = conn.execute(
            "SELECT f.filename, ec.column_name, ec.value "
            "FROM files f JOIN extracted_columns ec ON f.id = ec.file_id"
        ).fetchall()
        assert len(extracted) == 1
        assert extracted[0][1] == "Max Y" and extracted[0][2] == 30.0

        csv_text = conn.execute(
            "SELECT fd.csv_text FROM file_data fd "
            "JOIN files f ON fd.file_id = f.id WHERE f.filename = 'data.csv'"
        ).fetchone()[0]
        assert "X;Y" in csv_text
    finally:
        conn.close()
