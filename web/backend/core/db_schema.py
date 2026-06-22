"""
SQLite schema and conversion functions for .dpool → .db migration

This module provides:
- Schema creation for SQLite .db files
- Conversion from legacy .dpool (pickle) to .db (SQLite)
- Save/Load functions for SQLite format

Design: POC approach - simple standalone functions, relational schema
"""

import io
import json
import sqlite3

import pandas as pd


def create_schema(cursor):
    """Create SQLite schema with 6 tables for data pool storage

    Tables:
    - files: file metadata (filename, headers, units, is_checked)
    - file_data: DataFrame stored as CSV text (';' delimiter)
    - styles: visual styling (line_color, line_style, legend_label)
    - extracted_columns: data extraction results
    - pool_settings: global pool config (singleton)
    - fit_results: peak fitting results

    Args:
        cursor: sqlite3.Cursor object
    """
    # 1. FILES: Métadonnées des fichiers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            headers TEXT,
            units TEXT,
            is_checked BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. FILE_DATA: DataFrames stockés en CSV text
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_data (
            file_id INTEGER PRIMARY KEY,
            csv_text TEXT NOT NULL,
            row_count INTEGER,
            column_count INTEGER,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
        )
    """)

    # 3. STYLES: Styles visuels par fichier
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS styles (
            file_id INTEGER PRIMARY KEY,
            line_color TEXT,
            line_color_y2 TEXT,
            line_style TEXT,
            legend_label TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
        )
    """)

    # 4. EXTRACTED_COLUMNS: Colonnes extraites (data_extraction feature)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS extracted_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            value REAL,
            operation TEXT,
            precision INTEGER DEFAULT 6,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
            UNIQUE(file_id, column_name)
        )
    """)

    # 5. POOL_SETTINGS: Config globale du pool (singleton)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pool_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            x_column TEXT,
            y_columns TEXT,
            y2_columns TEXT,
            plot_style_settings TEXT,
            processing_settings TEXT,
            extracted_sort_state TEXT,
            version TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 6. FIT_RESULTS: Résultats de peak fitting
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fit_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            method TEXT,
            peak_data TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
            UNIQUE(file_id)
        )
    """)

    # Indexes pour requêtes courantes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_checked ON files(is_checked)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_extracted_file_value ON extracted_columns(file_id, value)")


def convert_dpool_to_db(data_pool, db_path):
    """Convert legacy .dpool (pickle) to SQLite .db format

    Args:
        data_pool (dict): Loaded .dpool data structure
        db_path (str): Path to save .db file

    Raises:
        Exception: If conversion fails with detailed error message
    """
    print(f"🟢 Starting .dpool → .db conversion for {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create schema
        create_schema(cursor)
        print(f"🟡 Created schema in {db_path}")

        csv_files = data_pool.get('csv_files', [])
        print(f"🟡 Converting {len(csv_files)} files")

        file_id_map = {}

        # Process each file
        for file_data in csv_files:
            if not isinstance(file_data, dict):
                print(f"⚠️ Skipping non-dict entry: {file_data}")
                continue

            filename = file_data.get('filename')
            if not filename:
                print("⚠️ Skipping entry without filename")
                continue

            # 1. INSERT into files table
            try:
                cursor.execute("""
                    INSERT INTO files (filename, headers, units, is_checked)
                    VALUES (?, ?, ?, ?)
                """, (
                    filename,
                    json.dumps(file_data.get('headers', [])),
                    json.dumps(file_data.get('units', {})),
                    1 if filename in data_pool.get('checked_files', []) else 0
                ))
                file_id = cursor.lastrowid
                file_id_map[filename] = file_id
                print(f"✅ Converted file {filename} (file_id={file_id})")
            except sqlite3.IntegrityError as e:
                print(f"❌ Failed to insert {filename}: {e}")
                continue

            # 2. INSERT DataFrame as CSV text
            if 'data' in file_data:
                try:
                    df = file_data['data']
                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, sep=';', index=False)
                    csv_text = csv_buffer.getvalue()

                    cursor.execute("""
                        INSERT INTO file_data (file_id, csv_text, row_count, column_count)
                        VALUES (?, ?, ?, ?)
                    """, (file_id, csv_text, len(df), len(df.columns)))
                    print(f"🔵 Saved DataFrame for {filename} ({len(df)} rows, {len(df.columns)} cols)")
                except Exception as e:
                    print(f"⚠️ Failed to save DataFrame for {filename}: {e}")

            # 3. INSERT into styles table
            try:
                cursor.execute("""
                    INSERT INTO styles (file_id, line_color, line_color_y2, line_style, legend_label)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    file_id,
                    data_pool.get('line_colors', {}).get(filename),
                    data_pool.get('line_colors_y2', {}).get(filename),
                    data_pool.get('line_styles', {}).get(filename),
                    data_pool.get('legend_labels', {}).get(filename)
                ))
            except Exception as e:
                print(f"⚠️ Failed to save styles for {filename}: {e}")

            # 4. INSERT extracted_data
            if 'extracted_data' in file_data:
                extracted_count = 0
                for col_name, col_data in file_data['extracted_data'].items():
                    try:
                        # Handle both old format (raw value) and new format (dict)
                        if isinstance(col_data, dict):
                            value = col_data.get('value')
                            operation = col_data.get('operation', 'Unknown')
                            precision = col_data.get('precision', 6)
                        else:
                            value = col_data
                            operation = 'Unknown'
                            precision = 6

                        cursor.execute("""
                            INSERT INTO extracted_columns (file_id, column_name, value, operation, precision)
                            VALUES (?, ?, ?, ?, ?)
                        """, (file_id, col_name, value, operation, precision))
                        extracted_count += 1
                    except Exception as e:
                        print(f"⚠️ Failed to save extracted column '{col_name}' for {filename}: {e}")

                if extracted_count > 0:
                    print(f"🔵 Saved {extracted_count} extracted columns for {filename}")

        # 5. INSERT pool_settings (singleton)
        try:
            cursor.execute("""
                INSERT INTO pool_settings (
                    x_column, y_columns, y2_columns,
                    plot_style_settings, processing_settings, extracted_sort_state,
                    version, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data_pool.get('plot_settings', {}).get('x_column'),
                json.dumps(data_pool.get('plot_settings', {}).get('y_columns', [])),
                json.dumps(data_pool.get('plot_settings', {}).get('y2_columns', [])),
                json.dumps(data_pool.get('plot_style_settings', {})),
                json.dumps(data_pool.get('processing_settings', {})),
                json.dumps(data_pool.get('extracted_column_sort_state', {})),
                data_pool.get('metadata', {}).get('version', '1.0.0'),
                data_pool.get('metadata', {}).get('timestamp')
            ))
            print("🔵 Saved pool settings")
        except Exception as e:
            print(f"⚠️ Failed to save pool settings: {e}")

        # 6. INSERT fit_results
        fit_count = 0
        for filename, fit_data in data_pool.get('fit_results', {}).items():
            if filename not in file_id_map:
                print(f"⚠️ Skipping fit_results for unknown file: {filename}")
                continue

            try:
                cursor.execute("""
                    INSERT INTO fit_results (file_id, method, peak_data)
                    VALUES (?, ?, ?)
                """, (
                    file_id_map[filename],
                    fit_data.get('method') if isinstance(fit_data, dict) else None,
                    json.dumps(fit_data.get('peaks', []) if isinstance(fit_data, dict) else [])
                ))
                fit_count += 1
            except Exception as e:
                print(f"⚠️ Failed to save fit_results for {filename}: {e}")

        if fit_count > 0:
            print(f"🔵 Saved fit_results for {fit_count} files")

        conn.commit()
        conn.close()
        print(f"✅ Conversion complete: {db_path}")

    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def save_to_sqlite(data_pool, db_path):
    """Save data pool to SQLite .db file

    This is functionally identical to convert_dpool_to_db() but used for
    direct saving (not conversion from legacy format).

    Args:
        data_pool (dict): Data pool structure to save
        db_path (str): Path to save .db file

    Raises:
        Exception: If save fails with detailed error message
    """
    print(f"🟢 Saving data pool to {db_path}")

    # Remove existing file to start fresh
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🟡 Removed existing {db_path}")

    # Use conversion function (same logic)
    convert_dpool_to_db(data_pool, db_path)


def load_from_sqlite(db_path):
    """Load data pool from SQLite .db file

    Reconstructs the data_pool dictionary structure expected by main_app.py

    Args:
        db_path (str): Path to .db file

    Returns:
        dict: Data pool structure with all settings and data

    Raises:
        Exception: If load fails with detailed error message
    """
    print(f"🟢 Loading pool from {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Dict-like access to rows
        cursor = conn.cursor()

        # Initialize data_pool structure
        data_pool = {
            'csv_files': [],
            'line_colors': {},
            'line_colors_y2': {},
            'line_styles': {},
            'legend_labels': {},
            'checked_files': [],
            'fit_results': {},
            'metadata': {},
            'plot_settings': {},
            'plot_style_settings': {},
            'processing_settings': {},
            'extracted_column_sort_state': {}
        }

        # Load files with JOIN to get all data in one query
        cursor.execute("""
            SELECT f.id, f.filename, f.headers, f.units, f.is_checked,
                   fd.csv_text,
                   s.line_color, s.line_color_y2, s.line_style, s.legend_label
            FROM files f
            LEFT JOIN file_data fd ON f.id = fd.file_id
            LEFT JOIN styles s ON f.id = s.file_id
        """)

        rows = cursor.fetchall()
        print(f"🟡 Loaded {len(rows)} files from database")

        for row in rows:
            # Reconstruct DataFrame from CSV text
            if row['csv_text']:
                try:
                    df = pd.read_csv(io.StringIO(row['csv_text']), sep=';')

                    # CRITICAL: Apply European decimal conversion
                    from core.data_utils import convert_numeric_columns
                    df = convert_numeric_columns(df)
                except Exception as e:
                    print(f"❌ Failed to parse DataFrame for {row['filename']}: {e}")
                    df = pd.DataFrame()  # Empty fallback
            else:
                df = pd.DataFrame()

            # Parse JSON fields
            try:
                headers = json.loads(row['headers']) if row['headers'] else []
            except Exception as e:
                print(f"⚠️ Failed to parse headers JSON for {row['filename']}: {e}")
                headers = []

            try:
                units = json.loads(row['units']) if row['units'] else {}
            except Exception as e:
                print(f"⚠️ Failed to parse units JSON for {row['filename']}: {e}")
                units = {}

            file_entry = {
                'filename': row['filename'],
                'data': df,
                'headers': headers,
                'units': units
            }

            # Load extracted columns for this file
            cursor.execute("""
                SELECT column_name, value, operation, precision
                FROM extracted_columns
                WHERE file_id = ?
            """, (row['id'],))

            extracted_rows = cursor.fetchall()
            if extracted_rows:
                extracted = {}
                for ext_row in extracted_rows:
                    extracted[ext_row['column_name']] = {
                        'value': ext_row['value'],
                        'operation': ext_row['operation'],
                        'precision': ext_row['precision']
                    }
                file_entry['extracted_data'] = extracted
                print(f"✅ Restored {len(extracted)} extracted columns for {row['filename']}")

            data_pool['csv_files'].append(file_entry)

            # Populate style dicts
            if row['is_checked']:
                data_pool['checked_files'].append(row['filename'])
            if row['line_color']:
                data_pool['line_colors'][row['filename']] = row['line_color']
            if row['line_color_y2']:
                data_pool['line_colors_y2'][row['filename']] = row['line_color_y2']
            if row['line_style']:
                data_pool['line_styles'][row['filename']] = row['line_style']
            if row['legend_label']:
                data_pool['legend_labels'][row['filename']] = row['legend_label']

        # Load pool_settings (singleton)
        cursor.execute("SELECT * FROM pool_settings WHERE id = 1")
        settings_row = cursor.fetchone()

        if settings_row:
            try:
                data_pool['plot_settings'] = {
                    'x_column': settings_row['x_column'],
                    'y_columns': json.loads(settings_row['y_columns']) if settings_row['y_columns'] else [],
                    'y2_columns': json.loads(settings_row['y2_columns']) if settings_row['y2_columns'] else []
                }
            except Exception as e:
                print(f"⚠️ Failed to parse plot_settings: {e}")
                data_pool['plot_settings'] = {}

            try:
                data_pool['plot_style_settings'] = json.loads(settings_row['plot_style_settings']) if settings_row['plot_style_settings'] else {}
            except Exception as e:
                print(f"⚠️ Failed to parse plot_style_settings: {e}")
                data_pool['plot_style_settings'] = {}

            try:
                data_pool['processing_settings'] = json.loads(settings_row['processing_settings']) if settings_row['processing_settings'] else {}
            except Exception as e:
                print(f"⚠️ Failed to parse processing_settings: {e}")
                data_pool['processing_settings'] = {}

            try:
                data_pool['extracted_column_sort_state'] = json.loads(settings_row['extracted_sort_state']) if settings_row['extracted_sort_state'] else {}
            except Exception as e:
                print(f"⚠️ Failed to parse extracted_sort_state: {e}")
                data_pool['extracted_column_sort_state'] = {}

            data_pool['metadata'] = {
                'version': settings_row['version'],
                'timestamp': settings_row['timestamp']
            }
            print("✅ Loaded pool settings")

        # Load fit_results
        cursor.execute("""
            SELECT f.filename, fr.method, fr.peak_data
            FROM fit_results fr
            JOIN files f ON fr.file_id = f.id
        """)

        fit_rows = cursor.fetchall()
        if fit_rows:
            for row in fit_rows:
                try:
                    data_pool['fit_results'][row['filename']] = {
                        'method': row['method'],
                        'peaks': json.loads(row['peak_data']) if row['peak_data'] else []
                    }
                except Exception as e:
                    print(f"⚠️ Failed to parse fit_results for {row['filename']}: {e}")
            print(f"✅ Loaded fit_results for {len(fit_rows)} files")

        conn.close()
        print(f"✅ Load complete: {len(data_pool['csv_files'])} files")

        return data_pool

    except Exception as e:
        print(f"❌ Load failed: {e}")
        import traceback
        traceback.print_exc()
        raise
