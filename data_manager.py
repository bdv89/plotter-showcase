import os
from io import StringIO
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal
import weakref
from data_cache import DataCache
from data_pipeline import DataPipeline, register_default_processors

# Check if Excel support is available
try:
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False

class LazyDataFrame:
    """A wrapper for lazy loading of pandas DataFrames from CSV and Excel files"""
    def __init__(self, file_path, delimiter=None, header_line=0, units_line=None, pipeline=None, sheet_name=0):
        self.file_path = file_path
        self.delimiter = delimiter
        self.header_line = header_line
        self.units_line = units_line
        self._df = None
        self._units = None
        self._headers = None
        self._is_loaded = False
        self.pipeline = pipeline  # Optional pipeline for data processing
        self.sheet_name = sheet_name  # For Excel files
        self.is_excel = self._is_excel_file()
    
    def _is_excel_file(self):
        """Check if the file is an Excel file"""
        return self.file_path.lower().endswith(('.xlsx', '.xls'))
        
    @property
    def data(self):
        """Loads the DataFrame only when accessed"""
        if not self._is_loaded:
            self._load_data()
        return self._df
    
    @property
    def units(self):
        """Returns units dictionary"""
        if not self._is_loaded:
            self._load_data()
        return self._units
    
    @property
    def headers(self):
        """Returns headers list"""
        if not self._is_loaded:
            self._load_data()
        return self._headers
    
    @property
    def is_loaded(self):
        """Returns whether the data has been loaded"""
        return self._is_loaded
    
    def _load_data(self):
        """Load data from file when needed"""
        try:
            if self.is_excel:
                self._load_excel_data()
            else:
                self._load_csv_data()
                
        except Exception as e:
            print(f"Error loading data from {self.file_path}: {str(e)}")
            self._df = pd.DataFrame()
            self._is_loaded = True  # Mark as loaded even on error to prevent repeated loading attempts
    
    def _load_excel_data(self):
        """Load data from Excel file"""
        # Determine appropriate engine based on file extension
        file_ext = os.path.splitext(self.file_path)[1].lower()
        engine = 'openpyxl' if file_ext == '.xlsx' else None
        
        # Read the Excel file
        df = pd.read_excel(self.file_path, sheet_name=self.sheet_name, 
                          header=self.header_line, engine=engine)
        
        # Extract headers
        self._headers = df.columns.tolist()
        
        # For Excel files, units are typically in the row after headers (if units_line is specified)
        self._units = {}
        if self.units_line is not None and self.units_line > self.header_line:
            # Read units from specified line
            units_df = pd.read_excel(self.file_path, sheet_name=self.sheet_name, 
                                   header=None, skiprows=self.units_line, nrows=1, engine=engine)
            if not units_df.empty:
                units_row = units_df.iloc[0].tolist()
                for i, header in enumerate(self._headers):
                    if i < len(units_row) and pd.notna(units_row[i]):
                        self._units[header] = str(units_row[i])
                        
                # Re-read data skipping the units line
                skip_rows = list(range(self.header_line + 1, self.units_line + 1))
                df = pd.read_excel(self.file_path, sheet_name=self.sheet_name, 
                                 header=self.header_line, skiprows=skip_rows, engine=engine)
        
        # Apply pipeline processing if available
        if self.pipeline and hasattr(df, 'shape') and df.shape[0] > 0:
            basename = os.path.basename(self.file_path)
            self._df = self.pipeline.process_data(df, source_id=basename)
        else:
            self._df = df
            
        self._is_loaded = True
    
    def _load_csv_data(self):
        """Load data from CSV file"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Get headers
        headers = [h.strip() for h in lines[self.header_line].strip().split(self.delimiter)]
        self._headers = headers
        
        # Process units if available
        self._units = {}
        if self.units_line is not None:
            units = [u.strip() for u in lines[self.units_line].strip().split(self.delimiter)]
            if len(headers) == len(units):
                self._units = {header: unit for header, unit in zip(headers, units)}
        
        # Find start of data
        data_start = self.header_line + 1
        if self.units_line is not None:
            data_start = self.units_line + 2  # Skip units line and an extra line
        
        data_lines = [line.strip() for line in lines[data_start:] if line.strip()]

        if not data_lines:
            self._df = pd.DataFrame(columns=headers)
            self._is_loaded = True
            return

        # Use pandas to parse the numeric data instead of manual float conversion.
        # This aggressively removes the previous custom parsing that was silently
        # leaving object dtypes (strings) when a weird value slipped through,
        # which in turn made matplotlib interpret the series as categories
        # and draw a straight diagonal (each point mapped to its index).
        decimal_sep = ',' if self.delimiter == ';' else '.'
        data_buffer = StringIO("\n".join(data_lines))

        try:
            loaded_df = pd.read_csv(
                data_buffer,
                sep=self.delimiter if self.delimiter else None,
                header=None,
                names=headers,
                decimal=decimal_sep,
                engine='python'
            )
        except Exception as parse_error:
            print(f"Error parsing CSV data from {self.file_path}: {parse_error}")
            loaded_df = pd.DataFrame(columns=headers)

        # Force numeric conversion for all columns (robust handling of comma decimals).
        # Even if pandas already succeeded, re-run the coercion to guarantee float dtype
        # on the electrochemistry columns we care about.
        for col in loaded_df.columns:
            try:
                converted = pd.to_numeric(
                    loaded_df[col].astype(str).str.replace(',', '.'),
                    errors='coerce'
                )
                if converted.notna().any():
                    loaded_df[col] = converted
            except Exception:
                pass  # Keep original if any error occurs

        # Apply pipeline processing if available
        if self.pipeline and hasattr(loaded_df, 'shape') and loaded_df.shape[0] > 0:
            basename = os.path.basename(self.file_path)
            self._df = self.pipeline.process_data(loaded_df, source_id=basename)
        else:
            self._df = loaded_df
            
        self._is_loaded = True
    
    def empty(self):
        """Check if DataFrame would be empty, without fully loading it"""
        try:
            if self.is_excel:
                # For Excel files, read just the header to check if there's data
                file_ext = os.path.splitext(self.file_path)[1].lower()
                engine = 'openpyxl' if file_ext == '.xlsx' else None
                df = pd.read_excel(self.file_path, sheet_name=self.sheet_name, 
                                 header=self.header_line, nrows=1, engine=engine)
                return df.empty
            else:
                # Fast check by just loading a few lines to see if there's data
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    # Read just enough lines to check if there's data after headers and units
                    lines = []
                    for _ in range(self.header_line + 5):  # Read a few extra lines beyond headers
                        line = f.readline()
                        if not line:
                            break
                        lines.append(line)
                    
                # Find start of data
                data_start = self.header_line + 1
                if self.units_line is not None:
                    data_start = self.units_line + 2
                
                # Check if there are any data lines
                data_lines = [line.strip() for line in lines[data_start:] if line.strip()]
                return len(data_lines) == 0
            
        except Exception:
            return True  # Assume empty on error


class DataManager(QThread):
    """Manages CSV data loading and processing"""
    update_progress = pyqtSignal(str)
    finished_loading = pyqtSignal(list)
    data_ready = pyqtSignal(object, str)  # For data pipeline integration
    
    def __init__(self, folder_path, use_cache=True):
        super().__init__()
        self.folder_path = folder_path
        self.use_cache = use_cache
        self.cache = DataCache() if use_cache else None
        self.pipeline = DataPipeline()
        
        # Register default data processors
        register_default_processors(self.pipeline)
        
        # Connect pipeline signals
        self.pipeline.pipeline_status.connect(lambda msg: self.update_progress.emit(msg))
        self.pipeline.data_processed.connect(self.data_ready)
        
    def run(self):
        csv_files = []
        try:
            # Determine supported file extensions
            supported_extensions = ['.csv']
            if EXCEL_SUPPORT:
                supported_extensions.extend(['.xlsx', '.xls'])

            # DIAGNOSTIC: Afficher le chemin scanné
            print(f"[DEBUG] Scanning folder: {self.folder_path}")
            print(f"[DEBUG] Looking for extensions: {', '.join(supported_extensions)}")
            self.update_progress.emit(f"Scanning folder: {self.folder_path}")
            self.update_progress.emit(f"Looking for extensions: {', '.join(supported_extensions)}")

            # DIAGNOSTIC: Vérifier si le dossier existe et est lisible
            if not os.path.exists(self.folder_path):
                print(f"[DEBUG] ERROR: Folder does not exist: {self.folder_path}")
                self.update_progress.emit(f"ERROR: Folder does not exist: {self.folder_path}")
                self.finished_loading.emit([])
                return

            if not os.path.isdir(self.folder_path):
                print(f"[DEBUG] ERROR: Path is not a directory: {self.folder_path}")
                self.update_progress.emit(f"ERROR: Path is not a directory: {self.folder_path}")
                self.finished_loading.emit([])
                return

            # DIAGNOSTIC: Lister TOUS les fichiers trouvés
            all_files = os.listdir(self.folder_path)
            print(f"[DEBUG] Total files in folder: {len(all_files)}")
            print(f"[DEBUG] All files: {all_files}")
            self.update_progress.emit(f"Total files in folder: {len(all_files)}")
            if all_files:
                self.update_progress.emit(f"Files found: {', '.join(all_files[:10])}{'...' if len(all_files) > 10 else ''}")

            files = [f for f in all_files
                    if f.lower().endswith(tuple(supported_extensions))]

            print(f"[DEBUG] Files matching extensions: {files}")

            if not files:
                file_types = "CSV" + (" and Excel" if EXCEL_SUPPORT else "")
                print(f"[DEBUG] No {file_types} files found!")
                self.update_progress.emit(f"No {file_types} files found in folder: {self.folder_path}")
                if all_files:
                    self.update_progress.emit(f"Found {len(all_files)} other files (wrong extensions)")
                else:
                    self.update_progress.emit("Folder is empty")
                self.finished_loading.emit([])
                return

            print(f"[DEBUG] Matched {len(files)} data files: {files}")
            self.update_progress.emit(f"Matched {len(files)} data files: {', '.join(files)}")
            
            for i, filename in enumerate(files):
                print(f"[DEBUG] Processing file {i+1}/{len(files)}: {filename}")
                self.update_progress.emit(f"Loading {i+1}/{len(files)}: {filename}")
                try:
                    file_path = os.path.join(self.folder_path, filename)
                    print(f"[DEBUG] Full path: {file_path}")
                    processed_result = self._process_file_lazy(file_path, filename)
                    print(f"[DEBUG] Processed result: {processed_result}")
                    if processed_result:
                        csv_files.extend(processed_result)
                        print(f"[DEBUG] Successfully processed {filename}: {len(processed_result)} files added")
                        self.update_progress.emit(f"Successfully processed {filename}: {len(processed_result)} files added")
                    else:
                        print(f"[DEBUG] No data extracted from {filename}")
                        self.update_progress.emit(f"No data extracted from {filename}")

                except Exception as e:
                    print(f"[DEBUG] ERROR processing {filename}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    self.update_progress.emit(f"Error processing {filename}: {str(e)}")

            print(f"[DEBUG] Final csv_files count: {len(csv_files)}")
            if csv_files:
                self.update_progress.emit(f"Loading complete: {len(csv_files)} data files processed successfully")
            else:
                print("[DEBUG] No valid data files could be processed - emitting empty list")
                self.update_progress.emit("No valid data files could be processed")
            self.finished_loading.emit(csv_files)
            
        except Exception as e:
            self.update_progress.emit(f"Critical error: {str(e)}")
            self.finished_loading.emit([])

    def _process_file_lazy(self, file_path, filename):
        """Process individual data file with lazy loading (CSV or Excel)"""
        print(f"[DEBUG] _process_file_lazy called for: {filename}")
        processed_files = []

        # Check if the file is in cache first
        if self.use_cache and self.cache:
            print(f"[DEBUG] Checking cache for: {file_path}")
            cached_data = self.cache.get_cached_data(file_path)
            if cached_data:
                print(f"[DEBUG] Cache HIT for {filename}")
                self.update_progress.emit(f"Using cached data for {filename}")

                # CRITICAL FIX: Force numeric conversion on cached data
                # The cache may contain strings with commas if data was cached before conversion
                if 'data' in cached_data:
                    df = cached_data['data']
                    for col in df.columns:
                        try:
                            # Convert column to string, replace commas with dots, then to numeric
                            converted = pd.to_numeric(
                                df[col].astype(str).str.replace(',', '.'),
                                errors='coerce'
                            )
                            # Replace if we got at least ONE valid conversion (not all NaN)
                            if converted.notna().any():
                                df[col] = converted
                        except Exception:
                            pass  # Keep original if any error occurs

                processed_files.append(cached_data)
                print(f"[DEBUG] Returning cached data for {filename}")
                return processed_files

        print(f"[DEBUG] Cache MISS for {filename}, loading from file")

        # Check if it's an Excel file
        if filename.lower().endswith(('.xlsx', '.xls')):
            print(f"[DEBUG] Excel file detected: {filename}")
            if not EXCEL_SUPPORT:
                self.update_progress.emit(f"Warning: Excel support not available for {filename} (missing openpyxl)")
                return processed_files
            return self._process_excel_file_lazy(file_path, filename)

        print(f"[DEBUG] CSV file detected: {filename}")
        try:
            # Check file encoding and get a few lines to determine format
            print(f"[DEBUG] Opening file to detect format: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                # Just read enough lines to determine format, not the entire file
                preview_lines = []
                for _ in range(30):  # Read up to 30 lines for format detection
                    line = f.readline()
                    if not line:
                        break
                    preview_lines.append(line)
        except UnicodeDecodeError:
            self.update_progress.emit(f"Error: {filename} appears to be a binary file or uses an unsupported encoding")
            return processed_files
        except IOError as e:
            self.update_progress.emit(f"Error reading {filename}: {str(e)}")
            return processed_files
            
        if not preview_lines:
            self.update_progress.emit(f"Error: {filename} is empty")
            return processed_files
        
        # Try different CSV formats based on preview
        if ';' in preview_lines[0]:
            delimiter = ';'
            header_line = 0
            units_line = None
        elif len(preview_lines) > 20 and ',' in preview_lines[20]:
            delimiter = ','
            header_line = 20
            units_line = 21
        else:
            self.update_progress.emit(f"Error: Unrecognized format in {filename}")
            return processed_files
        
        # Create lazy dataframe wrapper
        lazy_df = LazyDataFrame(file_path, delimiter, header_line, units_line, pipeline=self.pipeline)
        
        # Check for emptiness without fully loading
        if lazy_df.empty():
            self.update_progress.emit(f"Error: No valid data found in {filename}")
            return processed_files
        
        # Load just the headers to store meta information
        preview_headers = lazy_df.headers
        
        processed_file = {
            'filename': filename,
            'lazy_data': lazy_df,  # Store the lazy loading wrapper
            'data': weakref.proxy(lazy_df.data),  # Proxy to the actual data property
            'units': lazy_df.units,
            'headers': preview_headers,
            'file_path': file_path  # Store file path for cache reference
        }
        
        # Cache the processed file data
        if self.use_cache and self.cache:
            try:
                self.cache.cache_data(file_path, processed_file)
                print(f"[DEBUG] Cached data for {filename}")
            except (TypeError, AttributeError) as e:
                # LazyDataFrame with DataPipeline cannot be pickled - skip caching
                print(f"[DEBUG] Cannot cache {filename}: {str(e)}")
                pass
        
        processed_files.append(processed_file)
        
        # Send data to pipeline for any registered listeners
        self.pipeline.process_data(lazy_df.data, source_id=filename)
        
        return processed_files

    def _process_excel_file_lazy(self, file_path, filename):
        """Process individual Excel file with lazy loading"""
        processed_files = []
        
        try:
            # Create lazy dataframe wrapper for Excel file
            # Use default parameters: header at row 0, no units line, first sheet
            lazy_df = LazyDataFrame(file_path, delimiter=None, header_line=0, 
                                  units_line=None, pipeline=self.pipeline, sheet_name=0)
            
            # Check for emptiness without fully loading
            try:
                is_empty = lazy_df.empty()
                if is_empty:
                    self.update_progress.emit(f"Error: No valid data found in {filename}")
                    return processed_files
            except Exception as e:
                self.update_progress.emit(f"Error checking if {filename} is empty: {str(e)}")
                return processed_files
            
            # Try to load headers safely
            try:
                preview_headers = lazy_df.headers
                units_dict = lazy_df.units
            except Exception as e:
                self.update_progress.emit(f"Error reading Excel headers for {filename}: {str(e)}")
                return processed_files
            
            processed_file = {
                'filename': filename,
                'lazy_data': lazy_df,  # Store the lazy loading wrapper
                'data': weakref.proxy(lazy_df.data),  # Proxy to the actual data property
                'units': units_dict,
                'headers': preview_headers,
                'file_path': file_path  # Store file path for cache reference
            }
            
            # Cache the processed file data
            if self.use_cache and self.cache:
                self.cache.cache_data(file_path, processed_file)
            
            processed_files.append(processed_file)
            
            # Note: Don't process through pipeline here as it would trigger full data loading
            # The pipeline processing will happen when data is actually accessed
            
        except Exception as e:
            self.update_progress.emit(f"Error processing Excel file {filename}: {str(e)}")

        return processed_files
