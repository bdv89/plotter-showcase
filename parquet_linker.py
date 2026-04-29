import os
import pandas as pd
from PyQt5.QtWidgets import (QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout,
                           QLabel, QPushButton, QTableWidget, QTableWidgetItem, 
                           QComboBox, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QCheckBox, QLineEdit)


class TableRelationship:
    """Defines a relationship between two parquet tables"""
    
    def __init__(self, source_table, target_table, source_key, target_key):
        self.source_table = source_table
        self.target_table = target_table
        self.source_key = source_key
        self.target_key = target_key
    
    def get_related_data(self, key_value):
        """Get related data from target table based on key value"""
        if not isinstance(self.target_table.data, pd.DataFrame):
            return None
            
        related_rows = self.target_table.data[self.target_table.data[self.target_key] == key_value]
        if related_rows.empty:
            return None
            
        return related_rows


class ParquetTable:
    """Represents a single parquet table with metadata"""
    
    def __init__(self, name, path=None, data=None, primary_key='sample_id'):
        self.name = name
        self.path = path
        self.data = data
        self.primary_key = primary_key
        
    def load_data(self, path=None):
        """Load data from parquet file"""
        if path:
            self.path = path
            
        if not self.path:
            return False
            
        try:
            self.data = pd.read_parquet(self.path)
            return True
        except Exception as e:
            print(f"Error loading parquet table {self.name}: {str(e)}")
            return False


class ParquetLinker:
    """Handles linking CSV files to multiple parquet database tables"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.tables = {}  # Dictionary of ParquetTable objects
        self.relationships = []  # List of TableRelationship objects
        self.links = {}  # Maps CSV filenames to table data
        self.direct_link_tables = []  # Tables that can be directly linked to CSVs
        
    def add_table(self, name, path=None, data=None, primary_key='sample_id', direct_link=False):
        """Add a parquet table to the linker
        
        Args:
            name (str): Name of the table
            path (str, optional): Path to parquet file
            data (DataFrame, optional): Pre-loaded data
            primary_key (str): Primary key column
            direct_link (bool): Whether CSV files can be directly linked to this table
        """
        table = ParquetTable(name, path, data, primary_key)
        # Fix: Change "if path and not data:" to "if path and data is None:"
        if path and data is None:
            table.load_data()
            
        self.tables[name] = table
        
        if direct_link:
            self.direct_link_tables.append(name)
            
        return table
        
    def add_relationship(self, source_table, target_table, source_key, target_key):
        """Add a relationship between two tables
        
        Args:
            source_table (str): Name of source table
            target_table (str): Name of target table
            source_key (str): Column in source table for the relationship
            target_key (str): Column in target table for the relationship
        """
        if source_table not in self.tables or target_table not in self.tables:
            return False
            
        relationship = TableRelationship(
            self.tables[source_table],
            self.tables[target_table],
            source_key,
            target_key
        )
        
        self.relationships.append(relationship)
        return True
        
    def select_parquet_files(self):
        """Load multiple parquet files and set up tables and relationships"""
        dialog = MultiTableSetupDialog(self.parent, self)
        if dialog.exec_():
            return True
        return False
    
    def get_table_for_csv(self, filename):
        """Determine which table a CSV file should link to based on filename pattern"""
        # Default logic: try to match against direct link tables
        # This could be enhanced with more sophisticated pattern matching
        for table_name in self.direct_link_tables:
            table = self.tables[table_name]
            parsed = self.parse_csv_filename(filename)
            
            if parsed and table.data is not None:
                key_column = table.primary_key
                if key_column in table.data.columns:
                    potential_matches = table.data[table.data[key_column] == parsed['sample_id']]
                    if not potential_matches.empty:
                        return table_name
                        
        # No match found
        return self.direct_link_tables[0] if self.direct_link_tables else None
    
    def parse_csv_filename(self, filename):
        """Parse CSV filename to extract sample_id and iteration"""
        # Remove extension
        basename = os.path.splitext(filename)[0]
        
        # Split by underscore
        parts = basename.split('_')
        
        # Expecting format: sample_id_iteration where sample_id may contain underscores
        if len(parts) >= 2:
            # The last part is the iteration, everything before is the sample_id
            iteration = parts[-1]
            sample_id = '_'.join(parts[:-1])
            return {
                'sample_id': sample_id,
                'iteration': iteration,
                'date': sample_id  # Add date for compatibility with existing code
            }
        return None
    
    def find_matching_samples(self, csv_files):
        """Find matching samples in parquet tables for CSV files"""
        if not self.tables or not self.direct_link_tables:
            return {}
            
        matches = {}
        for file_info in csv_files:
            filename = file_info['filename']
            table_name = self.get_table_for_csv(filename)
            
            if not table_name:
                continue
                
            table = self.tables[table_name]
            parsed = self.parse_csv_filename(filename)
            
            if parsed and table.data is not None:
                # Find matches in parquet data
                possible_matches = table.data[
                    table.data[table.primary_key] == parsed['sample_id']
                ]
                
                if not possible_matches.empty:
                    # Use the first match if multiple found
                    sample_data = possible_matches.iloc[0].to_dict()
                    sample_data['_source_table'] = table_name  # Add source table info
                    
                    # Add related data from other tables
                    for relationship in self.relationships:
                        if relationship.source_table.name == table_name:
                            source_value = sample_data.get(relationship.source_key)
                            if source_value:
                                related_data = relationship.get_related_data(source_value)
                                if related_data is not None and len(related_data) > 0:
                                    for col in related_data.columns:
                                        if col != relationship.target_key:  # Avoid key duplication
                                            # Prefix with table name to avoid column name collisions
                                            new_col = f"{relationship.target_table.name}_{col}"
                                            sample_data[new_col] = related_data.iloc[0][col]
                    
                    matches[filename] = sample_data
        
        return matches
    
    def show_link_dialog(self, csv_files):
        """Show dialog to link CSV files with parquet data"""
        if not self.tables or not self.direct_link_tables:
            if not self.select_parquet_files():
                return {}
        
        # Create and show the dialog
        dialog = MultiTableLinkDialog(self.parent, csv_files, self)
        if dialog.exec_():
            self.links = dialog.get_links()
            return self.links
        return {}


class MultiTableSetupDialog(QDialog):
    """Dialog for setting up multiple parquet tables and relationships"""
    
    def __init__(self, parent, linker):
        super().__init__(parent)
        self.linker = linker
        self.tables = {}
        
        self.setWindowTitle("Setup Parquet Tables")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Tables group
        tables_group = QGroupBox("Parquet Tables")
        tables_layout = QVBoxLayout()
        
        # Table list
        self.table_list = QTableWidget()
        self.table_list.setColumnCount(4)
        self.table_list.setHorizontalHeaderLabels(["Table Name", "Primary Key", "Direct Link", "File Path"])
        self.table_list.horizontalHeader().setStretchLastSection(True)
        tables_layout.addWidget(self.table_list)
        
        # Add table button
        table_buttons = QHBoxLayout()
        add_table_btn = QPushButton("Add Table")
        add_table_btn.clicked.connect(self.add_table)
        table_buttons.addWidget(add_table_btn)
        
        remove_table_btn = QPushButton("Remove Table")
        remove_table_btn.clicked.connect(self.remove_table)
        table_buttons.addWidget(remove_table_btn)
        
        tables_layout.addLayout(table_buttons)
        tables_group.setLayout(tables_layout)
        layout.addWidget(tables_group)
        
        # Relationships group
        relations_group = QGroupBox("Table Relationships")
        relations_layout = QVBoxLayout()
        
        # Relationships list
        self.relations_list = QTableWidget()
        self.relations_list.setColumnCount(4)
        self.relations_list.setHorizontalHeaderLabels(["Source Table", "Source Key", "Target Table", "Target Key"])
        relations_layout.addWidget(self.relations_list)
        
        # Add relationship button
        rel_buttons = QHBoxLayout()
        add_rel_btn = QPushButton("Add Relationship")
        add_rel_btn.clicked.connect(self.add_relationship)
        rel_buttons.addWidget(add_rel_btn)
        
        remove_rel_btn = QPushButton("Remove Relationship")
        remove_rel_btn.clicked.connect(self.remove_relationship)
        rel_buttons.addWidget(remove_rel_btn)
        
        relations_layout.addLayout(rel_buttons)
        relations_group.setLayout(relations_layout)
        layout.addWidget(relations_group)
        
        # OK/Cancel buttons
        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        buttons.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        layout.addLayout(buttons)
    
    def add_table(self):
        """Add a new parquet table"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Parquet File", "", "Parquet Files (*.parquet)"
        )
        
        if not file_path:
            return
        
        try:
            # Load parquet file to get columns
            df = pd.read_parquet(file_path)
            
            # Create a dialog to configure the table
            dialog = TableConfigDialog(self, os.path.basename(file_path), df.columns.tolist())
            if dialog.exec_():
                table_name, primary_key, direct_link = dialog.get_config()
                
                # Add to list
                row = self.table_list.rowCount()
                self.table_list.insertRow(row)
                
                self.table_list.setItem(row, 0, QTableWidgetItem(table_name))
                self.table_list.setItem(row, 1, QTableWidgetItem(primary_key))
                
                direct_item = QTableWidgetItem()
                direct_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                direct_item.setCheckState(Qt.Checked if direct_link else Qt.Unchecked)
                self.table_list.setItem(row, 2, direct_item)
                
                self.table_list.setItem(row, 3, QTableWidgetItem(file_path))
                
                # Store in linker
                self.linker.add_table(
                    table_name, 
                    file_path, 
                    df, 
                    primary_key,
                    direct_link
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load parquet file: {str(e)}"
            )
    
    def remove_table(self):
        """Remove the selected table"""
        selected_row = self.table_list.currentRow()
        if selected_row >= 0:
            table_name = self.table_list.item(selected_row, 0).text()
            self.table_list.removeRow(selected_row)
            
            # Remove from linker
            if table_name in self.linker.tables:
                del self.linker.tables[table_name]
                
                if table_name in self.linker.direct_link_tables:
                    self.linker.direct_link_tables.remove(table_name)
                
                # Remove relationships involving this table
                self.linker.relationships = [
                    r for r in self.linker.relationships 
                    if r.source_table.name != table_name and r.target_table.name != table_name
                ]
                
                # Update relationships list
                self.update_relationships_list()
    
    def add_relationship(self):
        """Add a new relationship between tables"""
        if len(self.linker.tables) < 2:
            QMessageBox.warning(self, "Warning", "You need at least two tables to create a relationship")
            return
            
        dialog = RelationshipConfigDialog(self, list(self.linker.tables.keys()))
        if dialog.exec_():
            source_table, source_key, target_table, target_key = dialog.get_config()
            
            # Add to linker
            self.linker.add_relationship(source_table, target_table, source_key, target_key)
            
            # Update list
            self.update_relationships_list()
    
    def remove_relationship(self):
        """Remove the selected relationship"""
        selected_row = self.relations_list.currentRow()
        if selected_row >= 0 and selected_row < len(self.linker.relationships):
            del self.linker.relationships[selected_row]
            self.update_relationships_list()
    
    def update_relationships_list(self):
        """Update the relationships list"""
        self.relations_list.setRowCount(0)
        
        for i, relationship in enumerate(self.linker.relationships):
            self.relations_list.insertRow(i)
            self.relations_list.setItem(i, 0, QTableWidgetItem(relationship.source_table.name))
            self.relations_list.setItem(i, 1, QTableWidgetItem(relationship.source_key))
            self.relations_list.setItem(i, 2, QTableWidgetItem(relationship.target_table.name))
            self.relations_list.setItem(i, 3, QTableWidgetItem(relationship.target_key))
    
    def accept(self):
        """Check configuration before accepting"""
        if not self.linker.tables:
            QMessageBox.warning(self, "Warning", "You must add at least one table")
            return
            
        if not self.linker.direct_link_tables:
            QMessageBox.warning(self, "Warning", "You must have at least one table marked for direct linking")
            return
            
        super().accept()


class TableConfigDialog(QDialog):
    """Dialog for configuring a parquet table"""
    
    def __init__(self, parent, filename, columns):
        super().__init__(parent)
        self.columns = columns
        
        self.setWindowTitle("Configure Table")
        self.init_ui(filename)
    
    def init_ui(self, filename):
        layout = QFormLayout(self)
        
        # Table name
        self.name_input = QLineEdit()
        self.name_input.setText(os.path.splitext(filename)[0])
        layout.addRow("Table Name:", self.name_input)
        
        # Primary key
        self.key_combo = QComboBox()
        for column in self.columns:
            self.key_combo.addItem(column)
            
        # Set default to sample_id if available
        default_key = "sample_id"
        key_index = self.key_combo.findText(default_key)
        if key_index >= 0:
            self.key_combo.setCurrentIndex(key_index)
        layout.addRow("Primary Key:", self.key_combo)
        
        # Direct link option
        self.direct_link = QCheckBox("Allow direct linking from CSV files")
        self.direct_link.setChecked(True)
        layout.addWidget(self.direct_link)
        
        # Buttons
        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        buttons.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        layout.addRow("", buttons)
    
    def get_config(self):
        """Get the configuration values"""
        return (
            self.name_input.text(),
            self.key_combo.currentText(),
            self.direct_link.isChecked()
        )


class RelationshipConfigDialog(QDialog):
    """Dialog for configuring table relationships"""
    
    def __init__(self, parent, table_names):
        super().__init__(parent)
        self.table_names = table_names  # Save the table_names as instance variable
        
        self.setWindowTitle("Configure Relationship")
        self.init_ui()
    
    def init_ui(self):
        layout = QFormLayout(self)
        
        # Source table
        self.source_combo = QComboBox()
        for table in self.table_names:
            self.source_combo.addItem(table)
        self.source_combo.currentIndexChanged.connect(self.update_source_columns)
        layout.addRow("Source Table:", self.source_combo)
        
        # Source key
        self.source_key_combo = QComboBox()
        layout.addRow("Source Key:", self.source_key_combo)
        
        # Target table
        self.target_combo = QComboBox()
        for table in self.table_names:
            self.target_combo.addItem(table)
        if len(self.table_names) > 1:  # Fixed: use self.table_names instead of table_names
            self.target_combo.setCurrentIndex(1)  # Default to second table
        self.target_combo.currentIndexChanged.connect(self.update_target_columns)
        layout.addRow("Target Table:", self.target_combo)
        
        # Target key
        self.target_key_combo = QComboBox()
        layout.addRow("Target Key:", self.target_key_combo)
        
        # Initialize columns
        self.update_source_columns()
        self.update_target_columns()
        
        # Buttons
        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        buttons.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        layout.addRow("", buttons)
    
    def update_source_columns(self):
        """Update source key columns based on selected source table"""
        table_name = self.source_combo.currentText()
        table = self.parent().linker.tables.get(table_name)
        
        self.source_key_combo.clear()
        if table and hasattr(table.data, 'columns'):
            for column in table.data.columns:
                self.source_key_combo.addItem(column)
    
    def update_target_columns(self):
        """Update target key columns based on selected target table"""
        table_name = self.target_combo.currentText()
        table = self.parent().linker.tables.get(table_name)
        
        self.target_key_combo.clear()
        if table and hasattr(table.data, 'columns'):
            for column in table.data.columns:
                self.target_key_combo.addItem(column)
    
    def get_config(self):
        """Get the configuration values"""
        return (
            self.source_combo.currentText(),
            self.source_key_combo.currentText(),
            self.target_combo.currentText(),
            self.target_key_combo.currentText()
        )


class MultiTableLinkDialog(QDialog):
    """Dialog for linking CSV files to parquet tables with relationship support"""
    
    def __init__(self, parent, csv_files, linker):
        super().__init__(parent)
        self.csv_files = csv_files
        self.linker = linker
        self.links = {}
        
        self.setWindowTitle("Link CSV Files to Sample Database")
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        
        self.init_ui()
        self.populate_table()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        layout.addWidget(QLabel(
            "Link CSV files to sample IDs. CSV filenames should follow the pattern: sample_id_iteration"
        ))
        
        # Get column names for display - include from all tables
        self.display_columns = ['sample_id', '_source_table']  # Always show these
        
        # Add columns from all tables
        for table_name, table in self.linker.tables.items():
            if table.data is not None:
                for col in table.data.columns:
                    if col != 'sample_id' and col not in self.display_columns:
                        self.display_columns.append(col)
        
        # Add relationship columns
        for relationship in self.linker.relationships:
            target_table = relationship.target_table
            if target_table.data is not None:
                for col in target_table.data.columns:
                    if col != relationship.target_key:  # Avoid key duplication
                        prefixed_col = f"{target_table.name}_{col}"
                        if prefixed_col not in self.display_columns:
                            self.display_columns.append(prefixed_col)
        
        # Table for showing links with columns from all tables
        self.table = QTableWidget()
        
        # Set columns: CSV File + all data columns + Action
        self.table.setColumnCount(len(self.display_columns) + 2)
        
        # Set headers
        headers = ["CSV File"] + self.display_columns + ["Action"]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Set column widths
        self.table.setColumnWidth(0, 200)  # CSV File
        for i in range(len(self.display_columns)):
            self.table.setColumnWidth(i + 1, 150)
        
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.auto_link_button = QPushButton("Auto-Link All")
        self.auto_link_button.clicked.connect(self.auto_link_all)
        button_layout.addWidget(self.auto_link_button)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def populate_table(self):
        """Populate table with CSV files and potential links"""
        self.table.setRowCount(len(self.csv_files))
        
        for row, file_info in enumerate(self.csv_files):
            filename = file_info['filename']
            
            # CSV filename column
            self.table.setItem(row, 0, QTableWidgetItem(filename))
            
            # Empty cells for data columns
            for i in range(len(self.display_columns)):
                self.table.setItem(row, i + 1, QTableWidgetItem(""))
            
            # Link button
            link_button = QPushButton("Link")
            link_button.clicked.connect(lambda checked, r=row: self.link_file(r))
            self.table.setCellWidget(row, len(self.display_columns) + 1, link_button)
    
    def link_file(self, row):
        """Open sample selector dialog for a specific file"""
        filename = self.table.item(row, 0).text()
        parsed = self.linker.parse_csv_filename(filename)
        
        if not parsed:
            QMessageBox.warning(
                self, 
                "Invalid Filename", 
                f"The file {filename} does not follow the required naming pattern (sample_id_iteration)"
            )
            return
        
        # Choose which table to link to
        table_dialog = TableSelectDialog(self, self.linker.direct_link_tables)
        if not table_dialog.exec_():
            return
            
        selected_table = table_dialog.get_selected_table()
        if not selected_table or selected_table not in self.linker.tables:
            return
            
        table = self.linker.tables[selected_table]
        
        # Find potential matches
        potential_matches = table.data[
            table.data[table.primary_key] == parsed['sample_id']
        ]
        
        if potential_matches.empty:
            QMessageBox.warning(
                self,
                "No Matches",
                f"No matching samples found for {filename} in table {selected_table}"
            )
            return
        
        # If only one match, use it directly
        if len(potential_matches) == 1:
            sample_data = potential_matches.iloc[0].to_dict()
            sample_data['_source_table'] = selected_table
            
            # Add related data from relationships
            sample_data = self.add_related_data(selected_table, sample_data)
            
            # Update UI
            self.update_row_data(row, sample_data)
            self.links[filename] = sample_data
            return
        
        # If multiple matches, show selector dialog
        selector = SampleSelectorDialog(self, potential_matches, self.display_columns)
        if selector.exec_():
            selected_sample = selector.get_selected_sample()
            if selected_sample is not None:
                selected_sample['_source_table'] = selected_table
                
                # Add related data from relationships
                selected_sample = self.add_related_data(selected_table, selected_sample)
                
                # Update UI
                self.update_row_data(row, selected_sample)
                self.links[filename] = selected_sample
    
    def add_related_data(self, table_name, sample_data):
        """Add data from related tables based on relationships"""
        # Find relationships where this table is the source
        for relationship in self.linker.relationships:
            if relationship.source_table.name == table_name:
                source_value = sample_data.get(relationship.source_key)
                if source_value:
                    related_data = relationship.get_related_data(source_value)
                    if related_data is not None and len(related_data) > 0:
                        for col in related_data.columns:
                            if col != relationship.target_key:  # Avoid key duplication
                                # Prefix with table name to avoid column name collisions
                                new_col = f"{relationship.target_table.name}_{col}"
                                sample_data[new_col] = related_data.iloc[0][col]
        
        return sample_data
    
    def update_row_data(self, row, sample_data):
        """Update a row with sample data"""
        for i, col in enumerate(self.display_columns):
            value = str(sample_data.get(col, ""))
            self.table.item(row, i + 1).setText(value)
    
    def auto_link_all(self):
        """Automatically link all files based on filename pattern"""
        matches = self.linker.find_matching_samples(self.csv_files)
        
        if not matches:
            QMessageBox.warning(self, "No Matches", "No matching samples found for any CSV files")
            return
            
        for row in range(self.table.rowCount()):
            filename = self.table.item(row, 0).text()
            if filename in matches:
                sample_data = matches[filename]
                self.update_row_data(row, sample_data)
                self.links[filename] = sample_data
        
        QMessageBox.information(
            self, 
            "Auto-Link Complete", 
            f"Linked {len(matches)} files to sample database"
        )
    
    def get_links(self):
        """Return the links dictionary"""
        return self.links


class TableSelectDialog(QDialog):
    """Dialog for selecting which table to link to"""

    def __init__(self, parent, table_names):
        super().__init__(parent)
        self.table_names = table_names  # Store table_names as instance variable
        self.selected_table = None

        self.setWindowTitle("Select Table")
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select which table to link to:"))
        
        self.table_combo = QComboBox()
        for table in self.table_names:
            self.table_combo.addItem(table)
        layout.addWidget(self.table_combo)
        
        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        buttons.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        layout.addLayout(buttons)
    
    def accept(self):
        self.selected_table = self.table_combo.currentText()
        super().accept()
    
    def get_selected_table(self):
        return self.selected_table


class SampleSelectorDialog(QDialog):
    """Dialog for selecting from multiple matching samples"""
    
    def __init__(self, parent, samples_df, display_columns=None):
        super().__init__(parent)
        self.samples_df = samples_df
        self.display_columns = display_columns or ['sample_id']
        self.selected_sample = None
        
        self.setWindowTitle("Select Sample")
        self.setMinimumWidth(800)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Multiple matching samples found. Please select one:"))
        
        # Table for showing samples with all columns
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.display_columns) + 1)  # +1 for Select button
        
        # Set headers
        headers = self.display_columns + ["Select"]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Set columns width
        for i in range(len(self.display_columns)):
            self.table.setColumnWidth(i, 150)
        
        self.table.setRowCount(len(self.samples_df))
        
        for row, (_, sample) in enumerate(self.samples_df.iterrows()):
            # Display all columns
            for i, col in enumerate(self.display_columns):
                if col in sample:
                    value = str(sample.get(col, ""))
                    self.table.setItem(row, i, QTableWidgetItem(value))
                else:
                    self.table.setItem(row, i, QTableWidgetItem(""))
            
            # Select button in the last column
            select_button = QPushButton("Select")
            select_button.clicked.connect(lambda checked, r=row: self.select_sample(r))
            self.table.setCellWidget(row, len(self.display_columns), select_button)
        
        layout.addWidget(self.table)
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)
    
    def select_sample(self, row):
        """Select a sample and close the dialog"""
        # Get all columns for the selected sample
        sample_data = {}
        for i, col in enumerate(self.display_columns):
            item = self.table.item(row, i)
            if item is not None:
                sample_data[col] = item.text()
        
        self.selected_sample = sample_data
        self.accept()
    
    def get_selected_sample(self):
        """Return the selected sample with all columns"""
        return self.selected_sample