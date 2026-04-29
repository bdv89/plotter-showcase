import os
import pickle
import json
import pandas as pd
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from data_utils import convert_numeric_columns as _convert_numeric_columns

class LazyPlotSettings:
    """Lazy loader for plot settings to improve performance"""
    def __init__(self, file_path):
        self.file_path = file_path
        self._data = None
        self._loaded = False

    @property
    def data(self):
        """Load data on first access"""
        if not self._loaded:
            self._data = self._load_data()
            self._loaded = True
        return self._data

    def _load_data(self):
        """Internal method to actually load the data"""
        try:
            with open(self.file_path, 'r') as f:
                settings_data = json.load(f)

            if not isinstance(settings_data, dict):
                raise ValueError("Invalid settings file format")

            # Basic validation of required settings
            if 'plot_style_settings' not in settings_data:
                raise ValueError("Plot style settings not found in file")

            return settings_data
        except Exception as e:
            print(f"LazyPlotSettings: Error loading {self.file_path}: {str(e)}")
            return None

    def is_valid(self):
        """Check if settings can be loaded without actually loading them"""
        return self.data is not None

class StorageManager:
    """Manages data persistence and file operations with multiple format support"""
    
    SUPPORTED_FORMATS = {
        'csv': ('CSV Files (*.csv)', 'text/csv'),
        'json': ('JSON Files (*.json)', 'application/json'),
        'parquet': ('Parquet Files (*.parquet)', 'application/parquet'),
        'xlsx': ('Excel Files (*.xlsx)', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        'xls': ('Excel Files (*.xls)', 'application/vnd.ms-excel'),
        'dpool': ('Data Pool Files (*.dpool)', 'application/octet-stream'),
        'plot': ('Plot Settings Files (*.plot)', 'application/json')
    }
    
    @staticmethod
    def save_plot_settings(parent, plot_style_settings, plot_settings=None, processing_settings=None):
        """Save plot settings to a file

        Args:
            parent: Parent widget for dialog
            plot_style_settings (dict): Plot style settings from canvas
            plot_settings (dict, optional): Basic plot settings (axis limits, columns)
            processing_settings (dict, optional): Data processing pipeline settings
        """
        if not plot_style_settings:
            QMessageBox.warning(parent, "Warning", "No plot settings to save")
            return False
            
        file_filters = ";;".join([
            StorageManager.SUPPORTED_FORMATS['plot'][0],
            StorageManager.SUPPORTED_FORMATS['json'][0]
        ])
        
        file_path, selected_filter = QFileDialog.getSaveFileName(
            parent, "Save Plot Settings", "", file_filters
        )
        
        if not file_path:
            return False
            
        try:
            settings_data = {
                'plot_style_settings': plot_style_settings,
                'plot_settings': plot_settings if plot_settings else {},
                'processing_settings': processing_settings if processing_settings else {},
                'metadata': {
                    'version': '1.0.0',
                    'timestamp': pd.Timestamp.now().isoformat()
                }
            }
            
            with open(file_path, 'w') as f:
                json.dump(settings_data, f, indent=2)
                
            QMessageBox.information(parent, "Success", "Plot settings saved successfully")
            return True
        except Exception as e:
            QMessageBox.critical(parent, "Error", f"Error saving plot settings: {str(e)}")
            return False

    @staticmethod
    def load_plot_settings(parent):
        """Load plot settings from a file with lazy loading

        Args:
            parent: Parent widget for dialog

        Returns:
            dict: Dictionary containing plot_style_settings and plot_settings, or
            LazyPlotSettings: Lazy loader object if lazy=True
        """
        print("StorageManager: Starting load_plot_settings")
        file_filters = ";;".join([
            StorageManager.SUPPORTED_FORMATS['plot'][0],
            StorageManager.SUPPORTED_FORMATS['json'][0]
        ])

        file_path, _ = QFileDialog.getOpenFileName(
            parent, "Load Plot Settings", "", file_filters
        )

        if not file_path:
            print("StorageManager: No file selected")
            return None

        # Return LazyPlotSettings for deferred loading
        lazy_settings = LazyPlotSettings(file_path)

        # Quick validation - this will trigger loading
        if lazy_settings.is_valid():
            print("StorageManager: Settings file validated successfully")
            return lazy_settings.data  # Return the actual data
        else:
            QMessageBox.critical(parent, "Error", f"Error loading plot settings from {file_path}")
            return None

    @staticmethod
    def load_plot_settings_from_path(file_path):
        """Load plot settings from a specific file path (for auto-loading, no dialog)

        Args:
            file_path: Full path to the .plot file

        Returns:
            dict: Dictionary containing plot_style_settings and plot_settings, or None if error
        """
        if not os.path.exists(file_path):
            return None

        try:
            lazy_settings = LazyPlotSettings(file_path)
            if lazy_settings.is_valid():
                return lazy_settings.data
        except Exception:
            pass

        return None

    @staticmethod
    def load_plot_settings_lazy(parent):
        """Load plot settings with lazy loading (returns LazyPlotSettings object)

        Args:
            parent: Parent widget for dialog

        Returns:
            LazyPlotSettings: Lazy loader object, or None if no file selected
        """
        print("StorageManager: Starting load_plot_settings_lazy")
        file_filters = ";;".join([
            StorageManager.SUPPORTED_FORMATS['plot'][0],
            StorageManager.SUPPORTED_FORMATS['json'][0]
        ])

        file_path, _ = QFileDialog.getOpenFileName(
            parent, "Load Plot Settings", "", file_filters
        )

        if not file_path:
            print("StorageManager: No file selected")
            return None

        # Return LazyPlotSettings without immediate validation
        print(f"StorageManager: Created lazy loader for {file_path}")
        return LazyPlotSettings(file_path)

    @staticmethod
    def save_data_pool(parent, csv_files, line_colors, line_colors_y2, line_styles, legend_labels, plot_settings, checked_files, plot_style_settings=None, processing_settings=None, fit_results=None):
        """Save the current data pool to a file"""
        if not csv_files:
            QMessageBox.warning(parent, "Warning", "No data to save")
            return

        # Changed to .db (SQLite) as primary format
        file_filters = ";;".join([
            "Pool Files (*.db)",
            StorageManager.SUPPORTED_FORMATS['json'][0]
        ])

        file_path, selected_filter = QFileDialog.getSaveFileName(
            parent, "Save data pool", "", file_filters
        )
        if not file_path:
            return
            
        try:
            # Strip non-picklable objects (LazyDataFrame/DataPipeline) before serialization
            sanitized_csv_files = []
            for file_data in csv_files:
                if not isinstance(file_data, dict):
                    continue

                clean_entry = {}
                for key, value in file_data.items():
                    if key == 'lazy_data':
                        continue  # contains DataPipeline via LazyDataFrame → not picklable
                    if key == 'data':
                        try:
                            clean_entry['data'] = value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame(value)
                        except Exception:
                            continue
                    else:
                        clean_entry[key] = value

                sanitized_csv_files.append(clean_entry)

            data_pool = {
                'csv_files': sanitized_csv_files,
                'line_colors': line_colors,
                'line_colors_y2': line_colors_y2,
                'line_styles': line_styles,
                'legend_labels': legend_labels,
                'plot_settings': plot_settings,
                'checked_files': checked_files,
                'metadata': {
                    'version': '1.0.0',
                    'timestamp': pd.Timestamp.now().isoformat()
                }
            }

            # Add plot style settings if provided
            if plot_style_settings:
                data_pool['plot_style_settings'] = plot_style_settings

            # Add processing settings if provided
            if processing_settings:
                data_pool['processing_settings'] = processing_settings

            # Add fit results if provided
            if fit_results:
                data_pool['fit_results'] = fit_results

            # Add extracted column sort state if available
            if hasattr(parent, 'file_list') and hasattr(parent.file_list, 'extracted_column_sort_state'):
                data_pool['extracted_column_sort_state'] = parent.file_list.extracted_column_sort_state
                print(f"🟡 Saved sort state: {parent.file_list.extracted_column_sort_state}")

            if selected_filter == StorageManager.SUPPORTED_FORMATS['json'][0]:
                # JSON export (backward compatibility)
                for file_data in data_pool['csv_files']:
                    if 'data' in file_data:
                        file_data['data'] = file_data['data'].to_dict(orient='records')
                with open(file_path, 'w') as f:
                    json.dump(data_pool, f, indent=2)
            else:
                # SQLite .db format (primary)
                from db_schema import save_to_sqlite
                save_to_sqlite(data_pool, file_path)

            QMessageBox.information(parent, "Success", "Data pool saved successfully")
            return True
        except Exception as e:
            QMessageBox.critical(parent, "Error", f"Error saving data pool: {str(e)}")
            return False

    @staticmethod
    def load_data_pool(parent):
        """Load a previously saved data pool with auto-conversion from legacy .dpool"""
        # Accept both .dpool (legacy) and .db (new) formats
        file_filters = ";;".join([
            "Pool Files (*.db *.dpool)",
            StorageManager.SUPPORTED_FORMATS['json'][0]
        ])

        file_path, selected_filter = QFileDialog.getOpenFileName(
            parent, "Load data pool", "", file_filters
        )
        if not file_path:
            return None

        try:
            # Auto-detect format and load accordingly
            if file_path.lower().endswith('.json'):
                # JSON format (backward compatibility)
                with open(file_path, 'r') as f:
                    data_pool = json.load(f)
                    for file_data in data_pool['csv_files']:
                        if 'data' in file_data:
                            file_data['data'] = pd.DataFrame(file_data['data'])
                            # CRITICAL: Convert comma decimals to floats
                            file_data['data'] = _convert_numeric_columns(file_data['data'])

            elif file_path.lower().endswith('.dpool'):
                # Legacy .dpool format - auto-convert to .db
                print(f"🟡 Loading legacy .dpool file: {file_path}")
                with open(file_path, 'rb') as f:
                    data_pool = pickle.load(f)
                    # CRITICAL: Convert comma decimals to floats for all loaded files
                    for file_data in data_pool.get('csv_files', []):
                        if 'data' in file_data:
                            file_data['data'] = _convert_numeric_columns(file_data['data'])

                # Auto-convert to .db
                db_path = file_path.replace('.dpool', '.db')
                print(f"🟡 Auto-converting to SQLite: {db_path}")
                from db_schema import convert_dpool_to_db
                convert_dpool_to_db(data_pool, db_path)

                # Notify user of conversion
                QMessageBox.information(
                    parent,
                    "Converted to SQLite",
                    f"Legacy .dpool file has been converted to:\n{db_path}\n\n"
                    "Future saves will use the new .db format."
                )

            elif file_path.lower().endswith('.db'):
                # SQLite .db format (primary)
                print(f"🟢 Loading SQLite pool: {file_path}")
                from db_schema import load_from_sqlite
                data_pool = load_from_sqlite(file_path)

            else:
                QMessageBox.critical(parent, "Error", f"Unsupported file format: {file_path}")
                return None

            QMessageBox.information(parent, "Success", "Data pool loaded successfully")
            return data_pool

        except Exception as e:
            QMessageBox.critical(parent, "Error", f"Error loading data pool: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def export_data(parent, csv_files, checked_files):
        """Export selected files to various formats with parquet data"""
        if not checked_files:
            QMessageBox.warning(parent, "Warning", "Please select at least one file to export")
            return False
        
        file_filters = ";;".join([format_info[0] for format_info in StorageManager.SUPPORTED_FORMATS.values()])
        
        file_path, selected_filter = QFileDialog.getSaveFileName(
            parent, "Export Data", "", file_filters
        )
        if not file_path:
            return False
        
        try:
            all_data = []
            for filename in checked_files:
                file_data = next((f for f in csv_files if f['filename'] == filename), None)
                if file_data:
                    df = file_data['data'].copy()
                    df['Source_File'] = filename

                    # Add units if available (non-CSV formats only; CSV handled differently below)
                    if 'units' in file_data:
                        for col, unit in file_data['units'].items():
                            if col in df.columns:
                                df[f"{col}_unit"] = unit

                    # Add parquet data if available (non-CSV formats only)
                    if 'parquet_data' in file_data:
                        parquet_data = file_data['parquet_data']
                        for col, value in parquet_data.items():
                            if col != 'sample_id' and col != '_source_table':
                                prefix = 'parquet_'
                                if col.startswith(prefix):
                                    df[col] = value
                                else:
                                    df[f"{prefix}{col}"] = value

                    # Add extracted data if available (non-CSV formats only)
                    if 'extracted_data' in file_data:
                        extracted_data = file_data['extracted_data']
                        for col, val_or_dict in extracted_data.items():
                            # Extract value from dict if new format (backward compatibility)
                            if isinstance(val_or_dict, dict) and 'value' in val_or_dict:
                                value = val_or_dict['value']
                            else:
                                value = val_or_dict
                            df[f"calc_{col}"] = value

                    all_data.append({'filename': filename, 'df': df, 'file_data': file_data})

            if not all_data:
                QMessageBox.warning(parent, "Warning", "No data to export")
                return False

            metadata = {
                'source_files': checked_files,
                'export_date': pd.Timestamp.now().isoformat(),
                'version': '1.0.0'
            }

            # CSV export: place series side-by-side (wide format)
            if selected_filter == StorageManager.SUPPORTED_FORMATS['csv'][0]:
                # Determine X and Y selections from parent if available
                x_col = None
                y_cols = []
                y2_cols = []
                try:
                    if hasattr(parent, 'get_column_name') and hasattr(parent, 'x_combo'):
                        x_col = parent.get_column_name(parent.x_combo)
                    if hasattr(parent, 'get_selected_y_columns'):
                        y_cols = parent.get_selected_y_columns() or []
                    if hasattr(parent, 'get_selected_y2_columns'):
                        y2_cols = parent.get_selected_y2_columns() or []
                except Exception:
                    # Fallbacks handled below
                    pass

                selected_y_all = (y_cols or []) + (y2_cols or [])

                # If no X selected, try first numeric or first column from first df
                if x_col is None:
                    first_df = all_data[0]['df']
                    x_col = first_df.select_dtypes(include=['number']).columns.tolist()
                    x_col = x_col[0] if x_col else (first_df.columns[0] if len(first_df.columns) > 0 else None)

                if x_col is None:
                    QMessageBox.warning(parent, "Warning", "Unable to determine X column for CSV export")
                    return False

                # If no Y selected, do not auto-detect; treat as 'unused'
                if not selected_y_all:
                    QMessageBox.warning(parent, "Warning", "No Y columns selected for CSV export")
                    return False

                wide_df = None
                # Build a wide dataframe by merging on X
                for entry in all_data:
                    filename = entry['filename']
                    df_raw = entry['df']

                    if x_col not in df_raw.columns:
                        # Skip files missing the X column
                        continue

                    # Determine Y columns to include for this file (use only user selections)
                    y_for_file = [c for c in selected_y_all if c in df_raw.columns and c != x_col]

                    if not y_for_file:
                        continue

                    # Legend label from UI if available; fallback to filename base
                    try:
                        base_label = parent.file_list.get_legend_text(filename) if hasattr(parent, 'file_list') else None
                    except Exception:
                        base_label = None
                    if not base_label:
                        base_label = os.path.splitext(filename)[0]

                    # For each Y, create an x + y frame with a unique column name
                    for y_col_name in y_for_file:
                        sub_df = df_raw[[x_col, y_col_name]].copy()
                        # Include y name when multiple series are present
                        add_y_suffix = (len(y_for_file) > 1) or (len(all_data) > 1)
                        new_col_name = f"{base_label} - {y_col_name}" if add_y_suffix else base_label
                        sub_df.rename(columns={y_col_name: new_col_name}, inplace=True)

                        if wide_df is None:
                            wide_df = sub_df
                        else:
                            # Outer merge to preserve all X values across files
                            try:
                                wide_df = pd.merge(wide_df, sub_df, on=x_col, how='outer')
                            except Exception:
                                # If merge fails due to dtype mismatch, coerce X to string for alignment
                                wide_df[x_col] = wide_df[x_col].astype(str)
                                sub_df[x_col] = sub_df[x_col].astype(str)
                                wide_df = pd.merge(wide_df, sub_df, on=x_col, how='outer')

                if wide_df is None or wide_df.empty:
                    QMessageBox.warning(parent, "Warning", "No matching columns to export in CSV")
                    return False

                # DON'T sort by X - preserve original chronological order
                # This is critical for cyclic voltammetry (CV) and other time-series data
                # where the order represents the experimental sequence, not sorted values

                # Write CSV with semicolon as delimiter
                wide_df.to_csv(file_path, index=False, sep=';')
                QMessageBox.information(parent, "Success", "Data exported successfully")
                return True

            # Non-CSV export: keep original long/stacked format and metadata
            combined_df = pd.concat([e['df'] for e in all_data], ignore_index=True)

            if selected_filter == StorageManager.SUPPORTED_FORMATS['json'][0]:
                export_data = {
                    'metadata': metadata,
                    'data': combined_df.to_dict(orient='records')
                }
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
            elif selected_filter == StorageManager.SUPPORTED_FORMATS['parquet'][0]:
                combined_df.attrs['metadata'] = metadata
                combined_df.to_parquet(file_path, index=False)
            elif selected_filter in [StorageManager.SUPPORTED_FORMATS['xlsx'][0], StorageManager.SUPPORTED_FORMATS['xls'][0]]:
                # Excel export (KISS): filename + extracted calc_ columns only
                rows = []
                all_calc_cols = set()
                for entry in all_data:
                    file_data = entry['file_data']
                    extracted_data = file_data.get('extracted_data', {})
                    row = {'filename': entry['filename']}
                    for col, val_or_dict in extracted_data.items():
                        if isinstance(val_or_dict, dict) and 'value' in val_or_dict:
                            value = val_or_dict['value']
                        else:
                            value = val_or_dict
                        calc_col = f"calc_{col}"
                        row[calc_col] = value
                        all_calc_cols.add(calc_col)
                    rows.append(row)
                # Ensure stable column order: filename first, then sorted calc_ columns
                columns = ['filename'] + sorted(all_calc_cols)
                export_df = pd.DataFrame(rows, columns=columns)
                export_df.to_excel(file_path, index=False)
            else:
                # Default fallback for unknown filter: CSV stacked
                combined_df.to_csv(file_path, index=False, sep=';')

            QMessageBox.information(parent, "Success", "Data exported successfully")
            return True
        except Exception as e:
            QMessageBox.critical(parent, "Error", f"Error exporting data: {str(e)}")
            return False

    @staticmethod
    def import_data(parent):
        """Import data from various formats - supports multiple file selection"""
        file_filters = ";;".join([
            "All Supported Files (*.csv *.json *.parquet *.xlsx *.xls)",
            StorageManager.SUPPORTED_FORMATS['csv'][0],
            StorageManager.SUPPORTED_FORMATS['json'][0],
            StorageManager.SUPPORTED_FORMATS['parquet'][0],
            StorageManager.SUPPORTED_FORMATS['xlsx'][0],
            StorageManager.SUPPORTED_FORMATS['xls'][0]
        ])
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            parent, "Import Data (Multiple Selection Supported)", "", file_filters
        )
        if not file_paths:
            return None
            
        imported_files = []
        successful_count = 0
        failed_files = []
        
        for file_path in file_paths:
            try:
                file_data = StorageManager._process_single_file(file_path)
                if file_data:
                    imported_files.append(file_data)
                    successful_count += 1
                else:
                    failed_files.append(os.path.basename(file_path))
            except Exception as e:
                failed_files.append(f"{os.path.basename(file_path)} ({str(e)})")
        
        # Show summary message
        if successful_count > 0:
            message = f"Successfully imported {successful_count} file(s)"
            if failed_files:
                message += f"\nFailed to import: {', '.join(failed_files)}"
            QMessageBox.information(parent, "Import Summary", message)
        else:
            QMessageBox.critical(parent, "Import Failed", f"Failed to import any files:\n{chr(10).join(failed_files)}")
        
        # Return list of imported files or None if nothing was imported
        return imported_files if imported_files else None
    
    @staticmethod
    def _process_single_file(file_path):
        """Process a single file for import"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.csv':
                # Try different CSV formats
                try:
                    # First try semicolon delimiter
                    df = pd.read_csv(file_path, sep=';', encoding='utf-8')
                except (pd.errors.ParserError, UnicodeDecodeError, ValueError):
                    # Fallback to comma delimiter
                    df = pd.read_csv(file_path, sep=',', encoding='utf-8')
                units = {}
            elif file_ext == '.json':
                with open(file_path, 'r') as f:
                    json_data = json.load(f)
                if isinstance(json_data, dict) and 'data' in json_data:
                    df = pd.DataFrame(json_data['data'])
                    units = json_data.get('metadata', {}).get('units', {})
                else:
                    df = pd.DataFrame(json_data)
                    units = {}
            elif file_ext == '.parquet':
                df = pd.read_parquet(file_path)
                units = df.attrs.get('metadata', {}).get('units', {})
            elif file_ext in ['.xlsx', '.xls']:
                # Use pandas read_excel for Excel files
                engine = 'openpyxl' if file_ext == '.xlsx' else None
                df = pd.read_excel(file_path, engine=engine)
                units = {}  # Excel files don't typically have explicit units metadata
            else:
                return None

            # CRITICAL: Convert comma decimals to floats for imported data
            df = _convert_numeric_columns(df)

            return {
                'filename': os.path.basename(file_path),
                'data': df,
                'units': units,
                'headers': df.columns.tolist()
            }
        except Exception as e:
            raise Exception(f"Error importing {os.path.basename(file_path)}: {str(e)}")
