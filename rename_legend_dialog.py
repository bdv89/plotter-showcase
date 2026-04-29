from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt5.QtCore import Qt
import os
import re


class BatchLegendRenameDialog(QDialog):
    """Dialog to batch-rename legends based on filename parts.

    Expected filename pattern: nom_date_serie_item[.ext]
    - You can set a new value for one part for all checked files
    - Leave value empty to erase that part (keeps underscores)
    """

    PATTERN = re.compile(r'^(.+?)_(\d{6})_(\d+)_(\d+)(?:\.[^.]+)?$')

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("Batch Rename Legends")
        self.resize(560, 420)

        layout = QVBoxLayout(self)

        # Which component to modify
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Champ à modifier:"))
        self.component = QComboBox()
        # Map display -> index in parts
        self.components = [
            ("Nom", 0),
            ("Date", 1),
            ("Série", 2),
            ("Item", 3),
        ]
        for label, idx in self.components:
            self.component.addItem(label, idx)
        row1.addWidget(self.component)
        layout.addLayout(row1)

        # New value
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Nouvelle valeur (laisser vide pour effacer):"))
        self.value_edit = QLineEdit()
        row2.addWidget(self.value_edit)
        layout.addLayout(row2)

        # Preview list
        layout.addWidget(QLabel("Aperçu (fichiers cochés):"))
        self.preview_list = QListWidget()
        layout.addWidget(self.preview_list)

        # Buttons
        buttons = QHBoxLayout()
        self.preview_btn = QPushButton("Aperçu")
        self.preview_btn.clicked.connect(self.update_preview)
        self.apply_btn = QPushButton("Appliquer")
        self.apply_btn.clicked.connect(self.apply_changes)
        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.preview_btn)
        buttons.addStretch()
        buttons.addWidget(self.apply_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        # Initial preview
        self.update_preview()

    def get_checked_filenames(self):
        return self.app.file_list.get_checked_items() if self.app and hasattr(self.app, 'file_list') else []

    def parse_parts(self, filename):
        """Parse filename into (nom, date, serie, item). Return None if not match."""
        base = os.path.basename(filename)
        m = self.PATTERN.match(base)
        if m:
            return list(m.groups()[:4])  # ignore extension capture
        # Fallback: try split without extension
        stem = os.path.splitext(base)[0]
        parts = stem.split('_')
        if len(parts) >= 4:
            return parts[:4]
        return None

    def build_legend(self, parts):
        return '_'.join(parts)

    def compute_new_legend(self, filename, target_index, new_value):
        parts = self.parse_parts(filename)
        if not parts:
            return None
        parts[target_index] = new_value  # can be empty string
        return self.build_legend(parts)

    def update_preview(self):
        self.preview_list.clear()
        target_index = self.component.currentData()
        new_value = self.value_edit.text()
        files = self.get_checked_filenames()
        if not files:
            self.preview_list.addItem(QListWidgetItem("(Aucun fichier coché)"))
            return
        for fn in files:
            new_legend = self.compute_new_legend(fn, target_index, new_value)
            if new_legend is None:
                item = QListWidgetItem(f"{fn} -> (format non reconnu, inchangé)")
            else:
                item = QListWidgetItem(f"{fn} -> {new_legend}")
            self.preview_list.addItem(item)

    def apply_changes(self):
        target_index = self.component.currentData()
        new_value = self.value_edit.text()
        files = self.get_checked_filenames()
        if not files:
            QMessageBox.information(self, "Renommer les légendes", "Aucun fichier coché.")
            return

        updated = 0
        table = self.app.file_list
        for row in range(table.rowCount()):
            # Skip search row
            if table.item(row, 0) and hasattr(table.item(row, 0), 'is_search_row'):
                continue
            file_item = table.item(row, 0)
            if not file_item:
                continue
            filename = file_item.text()
            if filename not in files:
                continue
            new_legend = self.compute_new_legend(filename, target_index, new_value)
            if new_legend is None:
                continue
            legend_edit = table.cellWidget(row, 5)
            if legend_edit:
                legend_edit.setText(new_legend)
                updated += 1

        QMessageBox.information(self, "Renommer les légendes", f"Légendes mises à jour: {updated}")
        self.accept()

