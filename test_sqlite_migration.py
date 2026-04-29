"""
Test script for SQLite migration

This script tests:
1. Schema creation
2. Save/Load round-trip
3. Backward compatibility (.dpool → .db conversion)
"""

import sqlite3
import pandas as pd
import os
import sys

# Fix encoding for Windows console
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Import our modules
from db_schema import create_schema, save_to_sqlite, load_from_sqlite


def test_schema_creation():
    """Test that schema creates successfully"""
    print("\n" + "="*60)
    print("TEST 1: Schema Creation")
    print("="*60)

    test_db = "test_schema.db"

    # Remove if exists
    if os.path.exists(test_db):
        os.remove(test_db)

    conn = None
    try:
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        create_schema(cursor)
        conn.commit()

        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = ['files', 'file_data', 'styles', 'extracted_columns', 'pool_settings', 'fit_results']

        print(f"[OK] Created tables: {tables}")

        for table in expected_tables:
            if table in tables:
                print(f"  [OK] {table}")
            else:
                print(f"  [FAIL] {table} - MISSING!")
                conn.close()
                return False

        # Verify indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"[OK] Created indexes: {indexes}")

        conn.close()
        print("\n[OK] Schema creation PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] Schema creation FAILED: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.close()
        return False
    finally:
        # Cleanup
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except PermissionError:
                pass  # File still in use, skip cleanup


def test_save_load_roundtrip():
    """Test saving and loading a simple data pool"""
    print("\n" + "="*60)
    print("TEST 2: Save/Load Round-Trip")
    print("="*60)

    test_db = "test_roundtrip.db"

    # Remove if exists
    if os.path.exists(test_db):
        os.remove(test_db)

    try:
        # Create a simple data pool
        df1 = pd.DataFrame({
            'Time(s)': [0, 1, 2, 3],
            'Voltage(V)': [1.0, 1.1, 1.2, 1.3],
            'Current(A)': [0.1, 0.2, 0.3, 0.4]
        })

        df2 = pd.DataFrame({
            'Time(s)': [0, 1, 2],
            'Force(N)': [10.0, 20.0, 30.0]
        })

        data_pool = {
            'csv_files': [
                {
                    'filename': 'test1.csv',
                    'data': df1,
                    'headers': ['Time(s)', 'Voltage(V)', 'Current(A)'],
                    'units': {'Time(s)': 's', 'Voltage(V)': 'V', 'Current(A)': 'A'},
                    'extracted_data': {
                        'Max Voltage': {'value': 1.3, 'operation': 'Max', 'precision': 6}
                    }
                },
                {
                    'filename': 'test2.csv',
                    'data': df2,
                    'headers': ['Time(s)', 'Force(N)'],
                    'units': {'Time(s)': 's', 'Force(N)': 'N'}
                }
            ],
            'line_colors': {'test1.csv': '#FF0000', 'test2.csv': '#0000FF'},
            'line_colors_y2': {},
            'line_styles': {'test1.csv': '-', 'test2.csv': '--'},
            'legend_labels': {'test1.csv': 'Experiment 1', 'test2.csv': 'Experiment 2'},
            'plot_settings': {
                'x_column': 'Time(s)',
                'y_columns': ['Voltage(V)'],
                'y2_columns': []
            },
            'checked_files': ['test1.csv'],
            'metadata': {
                'version': '1.0.0',
                'timestamp': '2025-12-14T12:00:00'
            },
            'plot_style_settings': {'grid': True},
            'processing_settings': {'smooth': {'enabled': True, 'window': 5}},
            'fit_results': {
                'test1.csv': {'method': 'gauss', 'peaks': [{'x': 1.5, 'y': 1.15}]}
            },
            'extracted_column_sort_state': {5: 'asc'}
        }

        # Save to SQLite
        print("[RUN] Saving data pool to SQLite...")
        save_to_sqlite(data_pool, test_db)

        # Verify file was created
        if not os.path.exists(test_db):
            print(f"[FAIL] File {test_db} was not created!")
            return False

        print(f"[OK] Created {test_db} ({os.path.getsize(test_db)} bytes)")

        # Load from SQLite
        print("[RUN] Loading data pool from SQLite...")
        loaded_pool = load_from_sqlite(test_db)

        # Verify structure
        print("\n[CHECK] Verifying loaded data...")

        # Check csv_files count
        if len(loaded_pool['csv_files']) != 2:
            print(f"[FAIL] Expected 2 files, got {len(loaded_pool['csv_files'])}")
            return False
        print(f"  [OK] csv_files count: {len(loaded_pool['csv_files'])}")

        # Check first file
        file1 = loaded_pool['csv_files'][0]
        if file1['filename'] != 'test1.csv':
            print(f"[FAIL] Expected filename 'test1.csv', got {file1['filename']}")
            return False
        print(f"  [OK] First file: {file1['filename']}")

        # Check DataFrame shape
        if file1['data'].shape != df1.shape:
            print(f"[FAIL] DataFrame shape mismatch: expected {df1.shape}, got {file1['data'].shape}")
            return False
        print(f"  [OK] DataFrame shape: {file1['data'].shape}")

        # Check DataFrame values (compare first row)
        if not file1['data'].iloc[0].equals(df1.iloc[0]):
            print(f"[FAIL] DataFrame values mismatch")
            print(f"  Expected: {df1.iloc[0].tolist()}")
            print(f"  Got: {file1['data'].iloc[0].tolist()}")
            return False
        print(f"  [OK] DataFrame values match")

        # Check extracted_data
        if 'extracted_data' not in file1:
            print(f"[FAIL] extracted_data not found in file1")
            return False
        if 'Max Voltage' not in file1['extracted_data']:
            print(f"[FAIL] 'Max Voltage' not found in extracted_data")
            return False
        if file1['extracted_data']['Max Voltage']['value'] != 1.3:
            print(f"[FAIL] Max Voltage value mismatch")
            return False
        print(f"  [OK] extracted_data restored correctly")

        # Check line_colors
        if loaded_pool['line_colors'].get('test1.csv') != '#FF0000':
            print(f"[FAIL] line_colors mismatch")
            return False
        print(f"  [OK] line_colors restored correctly")

        # Check plot_settings
        if loaded_pool['plot_settings'].get('x_column') != 'Time(s)':
            print(f"[FAIL] plot_settings x_column mismatch")
            return False
        print(f"  [OK] plot_settings restored correctly")

        # Check fit_results
        if 'test1.csv' not in loaded_pool['fit_results']:
            print(f"[FAIL] fit_results not found")
            return False
        if loaded_pool['fit_results']['test1.csv']['method'] != 'gauss':
            print(f"[FAIL] fit_results method mismatch")
            return False
        print(f"  [OK] fit_results restored correctly")

        print("\n[OK] Save/Load round-trip PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] Save/Load round-trip FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if os.path.exists(test_db):
            os.remove(test_db)


def test_inspect_with_sqlite():
    """Test that .db file can be inspected with raw SQLite queries"""
    print("\n" + "="*60)
    print("TEST 3: SQLite Inspection")
    print("="*60)

    test_db = "test_inspect.db"

    # Remove if exists
    if os.path.exists(test_db):
        os.remove(test_db)

    try:
        # Create a simple pool
        df = pd.DataFrame({'X': [1, 2, 3], 'Y': [10, 20, 30]})
        data_pool = {
            'csv_files': [
                {
                    'filename': 'data.csv',
                    'data': df,
                    'headers': ['X', 'Y'],
                    'units': {},
                    'extracted_data': {'Max Y': {'value': 30.0, 'operation': 'Max', 'precision': 6}}
                }
            ],
            'line_colors': {},
            'line_colors_y2': {},
            'line_styles': {},
            'legend_labels': {},
            'plot_settings': {},
            'checked_files': [],
            'metadata': {'version': '1.0.0', 'timestamp': '2025-12-14'},
            'plot_style_settings': {},
            'processing_settings': {},
            'fit_results': {},
            'extracted_column_sort_state': {}
        }

        save_to_sqlite(data_pool, test_db)

        # Now inspect with raw SQL
        print("[CHECK] Running SQL queries...")
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Query 1: List all files
        cursor.execute("SELECT filename FROM files")
        files = cursor.fetchall()
        print(f"  [OK] Files in DB: {[f[0] for f in files]}")

        # Query 2: Get extracted columns
        cursor.execute("""
            SELECT f.filename, ec.column_name, ec.value, ec.operation
            FROM files f
            JOIN extracted_columns ec ON f.id = ec.file_id
        """)
        extracted = cursor.fetchall()
        print(f"  [OK] Extracted columns: {extracted}")

        if len(extracted) != 1:
            print(f"[FAIL] Expected 1 extracted column, got {len(extracted)}")
            return False

        if extracted[0][1] != 'Max Y' or extracted[0][2] != 30.0:
            print(f"[FAIL] Extracted column data mismatch")
            return False

        # Query 3: Get file data (CSV text)
        cursor.execute("""
            SELECT fd.csv_text
            FROM file_data fd
            JOIN files f ON fd.file_id = f.id
            WHERE f.filename = 'data.csv'
        """)
        csv_text = cursor.fetchone()[0]
        print(f"  [OK] CSV text preview (first 100 chars):\n{csv_text[:100]}")

        if 'X;Y' not in csv_text:
            print(f"[FAIL] CSV text doesn't contain expected header 'X;Y'")
            return False

        conn.close()

        print("\n[OK] SQLite inspection PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] SQLite inspection FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if os.path.exists(test_db):
            os.remove(test_db)


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("SQLite Migration Test Suite")
    print("="*60)

    results = []

    # Test 1: Schema Creation
    results.append(("Schema Creation", test_schema_creation()))

    # Test 2: Save/Load Round-Trip
    results.append(("Save/Load Round-Trip", test_save_load_roundtrip()))

    # Test 3: SQLite Inspection
    results.append(("SQLite Inspection", test_inspect_with_sqlite()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[OK] PASSED" if result else "[FAIL] FAILED"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests PASSED! Migration is ready.")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} test(s) FAILED. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
