"""
Data Extraction Dialog

Permet d'extraire des métriques statistiques depuis les données des graphiques
et les afficher comme colonnes dans le tableau principal.
"""

import traceback
import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QListWidget, QPushButton, QMessageBox, QFormLayout, QSpinBox
)
from PyQt5.QtCore import Qt


def compute_linear_slope(y_series, x_series):
    """Compute slope using linear regression

    Args:
        y_series: Y values (pandas Series)
        x_series: X values (pandas Series)

    Returns:
        float: Slope of linear regression
    """
    from scipy import stats

    # Ensure arrays are same length
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

    # Ensure arrays are same length
    min_len = min(len(x_series), len(y_series))
    x = x_series.iloc[:min_len].values
    y = y_series.iloc[:min_len].values

    f = interp1d(x, y, kind='linear', fill_value='extrapolate')
    return float(f(target_x))


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
    # Filter based on operator
    if operator == '>':
        mask = condition_series > threshold
    elif operator == '<':
        mask = condition_series < threshold
    else:
        raise ValueError(f"Unsupported operator: {operator}")

    # Find first index where condition is True
    matching_indices = condition_series[mask].index

    if len(matching_indices) == 0:
        # Condition never met - apply fallback
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

        else:  # 'none' or any other value
            print("❌ Condition never met, no fallback configured")
            return None

    # Condition met normally
    first_match_idx = matching_indices[0]
    result = float(y_series.loc[first_match_idx])
    print(f"✅ Condition met at index {first_match_idx}, Y = {result}")
    return result


class DataExtractionDialog(QDialog):
    """Dialog to extract metrics from data columns"""

    # Operations dictionary - SINGLE SOURCE OF TRUTH
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

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app  # CSVPlotterApp instance

        print("🟢 Extract Data dialog opened")

        self.setWindowTitle("Extract Data from Files")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.init_ui()

    def init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout()

        # Form layout for inputs
        form_layout = QFormLayout()

        # Column selector
        self.column_combo = QComboBox()
        self.populate_column_list()
        form_layout.addRow("Column to analyze:", self.column_combo)

        # Operation selector
        self.operation_combo = QComboBox()
        self.operation_combo.addItems(list(self.OPERATIONS.keys()))
        self.operation_combo.currentTextChanged.connect(self.on_operation_changed)
        form_layout.addRow("Operation:", self.operation_combo)

        # Custom column name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Max Force")
        form_layout.addRow("Custom column name:", self.name_edit)

        # Decimal precision selector
        self.precision_spinbox = QSpinBox()
        self.precision_spinbox.setRange(0, 15)
        self.precision_spinbox.setValue(6)  # Default precision
        self.precision_spinbox.setToolTip("Number of decimal places to display")
        form_layout.addRow("Decimal precision:", self.precision_spinbox)

        # X column selector (for operations that need X)
        self.x_column_label = QLabel("X column:")
        self.x_column_combo = QComboBox()
        self.populate_x_column_list()
        form_layout.addRow(self.x_column_label, self.x_column_combo)

        # X value input (for "Value at X" operation)
        self.x_value_label = QLabel("X value:")
        self.x_value_edit = QLineEdit()
        self.x_value_edit.setPlaceholderText("e.g., 5.0")
        form_layout.addRow(self.x_value_label, self.x_value_edit)

        # Condition column selector (for conditional operations)
        self.condition_column_label = QLabel("Condition column:")
        self.condition_column_combo = QComboBox()
        self.populate_condition_column_list()
        form_layout.addRow(self.condition_column_label, self.condition_column_combo)

        # Threshold value input (for conditional operations)
        self.threshold_label = QLabel("Threshold value:")
        self.threshold_edit = QLineEdit()
        self.threshold_edit.setPlaceholderText("e.g., 0.5")
        form_layout.addRow(self.threshold_label, self.threshold_edit)

        # Fallback type selector (for conditional operations)
        self.fallback_type_label = QLabel("If condition not met:")
        self.fallback_type_combo = QComboBox()
        self.fallback_type_combo.addItems(['No fallback (ERROR)', 'Custom value', 'First Y value', 'Last Y value'])
        self.fallback_type_combo.currentTextChanged.connect(self.on_fallback_type_changed)
        form_layout.addRow(self.fallback_type_label, self.fallback_type_combo)

        # Fallback custom value input (only visible when 'Custom value' selected)
        self.fallback_value_label = QLabel("Fallback value:")
        self.fallback_value_edit = QLineEdit()
        self.fallback_value_edit.setPlaceholderText("e.g., 0")
        form_layout.addRow(self.fallback_value_label, self.fallback_value_edit)

        layout.addLayout(form_layout)

        # Preview list
        preview_label = QLabel("Preview (checked files):")
        layout.addWidget(preview_label)

        self.preview_list = QListWidget()
        self.preview_list.setMinimumHeight(150)
        layout.addWidget(self.preview_list)

        # Buttons
        button_layout = QHBoxLayout()

        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self.preview_extractions)
        button_layout.addWidget(preview_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_extractions)
        button_layout.addWidget(apply_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Initial visibility update
        self.on_operation_changed()

    def populate_column_list(self):
        """Populate column list from first checked file"""
        self.column_combo.clear()

        checked_files = self.app.file_list.get_checked_items()
        if not checked_files:
            return

        # Get columns from first checked file
        first_file = checked_files[0]
        file_data = next((f for f in self.app.csv_files if f['filename'] == first_file), None)

        if file_data and 'data' in file_data:
            df = file_data['data']
            columns = list(df.columns)
            self.column_combo.addItems(columns)

    def populate_x_column_list(self):
        """Populate X column list (same as column list)"""
        self.x_column_combo.clear()

        checked_files = self.app.file_list.get_checked_items()
        if not checked_files:
            return

        # Get columns from first checked file
        first_file = checked_files[0]
        file_data = next((f for f in self.app.csv_files if f['filename'] == first_file), None)

        if file_data and 'data' in file_data:
            df = file_data['data']
            columns = list(df.columns)
            self.x_column_combo.addItems(columns)

            # Try to select X column from main app if available
            if hasattr(self.app, 'x_combo'):
                current_x = self.app.x_combo.currentText()
                idx = self.x_column_combo.findText(current_x)
                if idx >= 0:
                    self.x_column_combo.setCurrentIndex(idx)

    def populate_condition_column_list(self):
        """Populate condition column list (same as column list)"""
        self.condition_column_combo.clear()

        checked_files = self.app.file_list.get_checked_items()
        if not checked_files:
            return

        # Get columns from first checked file
        first_file = checked_files[0]
        file_data = next((f for f in self.app.csv_files if f['filename'] == first_file), None)

        if file_data and 'data' in file_data:
            df = file_data['data']
            columns = list(df.columns)
            self.condition_column_combo.addItems(columns)

    def on_fallback_type_changed(self):
        """Show/hide fallback value input based on fallback type"""
        fallback_type = self.fallback_type_combo.currentText()

        # Show custom value input only if "Custom value" selected
        is_custom = fallback_type == 'Custom value'
        self.fallback_value_label.setVisible(is_custom)
        self.fallback_value_edit.setVisible(is_custom)

    def on_operation_changed(self):
        """Show/hide X column and X value inputs based on operation"""
        operation = self.operation_combo.currentText()

        if operation not in self.OPERATIONS:
            return

        op_type, _ = self.OPERATIONS[operation]

        # Show X column for operations that need it
        needs_x = op_type in ['needs_x', 'needs_x_value']
        self.x_column_label.setVisible(needs_x)
        self.x_column_combo.setVisible(needs_x)

        # Show X value only for "Value at X"
        needs_x_value = op_type == 'needs_x_value'
        self.x_value_label.setVisible(needs_x_value)
        self.x_value_edit.setVisible(needs_x_value)

        # Show condition inputs only for conditional operations
        is_conditional = op_type == 'conditional'
        self.condition_column_label.setVisible(is_conditional)
        self.condition_column_combo.setVisible(is_conditional)
        self.threshold_label.setVisible(is_conditional)
        self.threshold_edit.setVisible(is_conditional)

        # Show fallback inputs only for conditional operations
        self.fallback_type_label.setVisible(is_conditional)
        self.fallback_type_combo.setVisible(is_conditional)

        # Trigger fallback visibility update
        if is_conditional:
            self.on_fallback_type_changed()
        else:
            self.fallback_value_label.setVisible(False)
            self.fallback_value_edit.setVisible(False)

        # Auto-populate custom name if empty
        if not self.name_edit.text():
            column = self.column_combo.currentText()
            if column:
                if operation == "Y at max(X)":
                    x_col = self.x_column_combo.currentText()
                    self.name_edit.setText(f"{column} at max({x_col})")
                elif is_conditional:
                    cond_col = self.condition_column_combo.currentText()
                    operator = '>' if '>' in operation else '<'
                    self.name_edit.setText(f"{column} when {cond_col}{operator}threshold")
                else:
                    self.name_edit.setText(f"{operation} {column}")

    def compute_extraction(self, filename, column, operation):
        """Compute extraction for a single file

        Args:
            filename: Name of file to extract from
            column: Column name to analyze
            operation: Operation name (must be in OPERATIONS dict)

        Returns:
            float or None: Extracted value, or None if error
        """
        print(f"🟡 Computing {operation} for column '{column}' in {filename}")

        try:
            # Get processed data (after pipeline if configured)
            df = self.app.get_processed_data(filename)

            if df is None:
                print(f"❌ Could not get data for {filename}")
                return None

            if column not in df.columns:
                print(f"❌ Column '{column}' not found in {filename}")
                return None

            # Get series and remove NaN values
            series = df[column].dropna()

            if len(series) == 0:
                print(f"❌ Column '{column}' has no valid data in {filename}")
                return None

            # Get operation function
            if operation not in self.OPERATIONS:
                print(f"❌ Unknown operation: {operation}")
                return None

            op_type, op_func = self.OPERATIONS[operation]

            # Execute operation based on type
            if op_type == 'basic':
                result = op_func(series)
            elif op_type == 'needs_x':
                # Get X column
                x_col = self.x_column_combo.currentText()
                if not x_col or x_col not in df.columns:
                    print(f"❌ X column '{x_col}' not found")
                    return None

                x_series = df[x_col].dropna()

                # Ensure same length
                min_len = min(len(series), len(x_series))
                series = series.iloc[:min_len]
                x_series = x_series.iloc[:min_len]

                result = op_func(series, x_series)
            elif op_type == 'needs_x_value':
                # Get X column and target value
                x_col = self.x_column_combo.currentText()
                if not x_col or x_col not in df.columns:
                    print(f"❌ X column '{x_col}' not found")
                    return None

                try:
                    target_x = float(self.x_value_edit.text())
                except ValueError:
                    print(f"❌ Invalid X value: {self.x_value_edit.text()}")
                    return None

                x_series = df[x_col].dropna()

                # Ensure same length
                min_len = min(len(series), len(x_series))
                series = series.iloc[:min_len]
                x_series = x_series.iloc[:min_len]

                result = op_func(series, x_series, target_x)
            elif op_type == 'conditional':
                # Get condition column
                cond_col = self.condition_column_combo.currentText()
                if not cond_col or cond_col not in df.columns:
                    print(f"❌ Condition column '{cond_col}' not found")
                    return None

                # Parse threshold
                try:
                    threshold = float(self.threshold_edit.text())
                except ValueError:
                    print(f"❌ Invalid threshold value: {self.threshold_edit.text()}")
                    return None

                # Extract operator from operation name
                operator = '>' if '>' in operation else '<'

                # Get fallback parameters
                fallback_type_text = self.fallback_type_combo.currentText()
                fallback_type_map = {
                    'No fallback (ERROR)': 'none',
                    'Custom value': 'custom',
                    'First Y value': 'first',
                    'Last Y value': 'last'
                }
                fallback_type = fallback_type_map.get(fallback_type_text, 'none')

                fallback_value = None
                if fallback_type == 'custom':
                    try:
                        fallback_value = float(self.fallback_value_edit.text())
                    except ValueError:
                        print(f"❌ Invalid fallback value: {self.fallback_value_edit.text()}")
                        return None

                print(f"🟡 Condition: {cond_col} {operator} {threshold}, fallback={fallback_type}")

                # Get condition series
                cond_series = df[cond_col].dropna()

                # Ensure same length
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

    def preview_extractions(self):
        """Preview extraction results for all checked files"""
        print("🟡 Previewing extractions")

        self.preview_list.clear()

        # Validate inputs
        column = self.column_combo.currentText()
        operation = self.operation_combo.currentText()
        custom_name = self.name_edit.text().strip()

        if not column:
            QMessageBox.warning(self, "Warning", "Please select a column")
            return

        if not operation:
            QMessageBox.warning(self, "Warning", "Please select an operation")
            return

        if not custom_name:
            QMessageBox.warning(self, "Warning", "Please enter a custom column name")
            return

        # Get checked files
        checked_files = self.app.file_list.get_checked_items()
        if not checked_files:
            QMessageBox.warning(self, "Warning", "No files checked")
            return

        # Compute for each file
        success_count = 0
        precision = self.precision_spinbox.value()
        for filename in checked_files:
            result = self.compute_extraction(filename, column, operation)

            if result is not None:
                formatted_value = f"{result:.{precision}f}"
                self.preview_list.addItem(f"{filename} → {custom_name} = {formatted_value}")
                success_count += 1
            else:
                self.preview_list.addItem(f"{filename} → ERROR")

        print(f"✅ Preview complete: {success_count}/{len(checked_files)} successful")

    def apply_extractions(self):
        """Apply extractions and store in app.file_list.extracted_columns"""
        print("🟢 Applying extractions")

        # Validate inputs
        column = self.column_combo.currentText()
        operation = self.operation_combo.currentText()
        custom_name = self.name_edit.text().strip()

        if not column:
            QMessageBox.warning(self, "Warning", "Please select a column")
            return

        if not operation:
            QMessageBox.warning(self, "Warning", "Please select an operation")
            return

        if not custom_name:
            QMessageBox.warning(self, "Warning", "Please enter a custom column name")
            return

        # Get checked files
        checked_files = self.app.file_list.get_checked_items()
        if not checked_files:
            QMessageBox.warning(self, "Warning", "No files checked")
            return

        # Compute for each file and store
        success_count = 0
        precision = self.precision_spinbox.value()
        for filename in checked_files:
            result = self.compute_extraction(filename, column, operation)

            if result is not None:
                # Initialize dict for this file if needed
                if filename not in self.app.file_list.extracted_columns:
                    self.app.file_list.extracted_columns[filename] = {}

                # Round to specified precision and store with precision for correct display
                rounded_value = round(result, precision)
                self.app.file_list.extracted_columns[filename][custom_name] = {
                    'value': rounded_value,
                    'precision': precision
                }
                print(f"🟡 Stored {custom_name} = {rounded_value} (precision={precision})")
                success_count += 1

        # Update display
        self.app.file_list.update_extracted_columns_display()

        print(f"✅ Applied {success_count}/{len(checked_files)} extractions")

        QMessageBox.information(
            self,
            "Success",
            f"Extracted data for {success_count}/{len(checked_files)} files.\n"
            f"Column '{custom_name}' added to table."
        )

        # Clear custom name for next extraction
        self.name_edit.clear()
        self.preview_list.clear()
