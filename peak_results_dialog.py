from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QMessageBox
)
import pandas as pd


class PeakResultsDialog(QDialog):
    """Display and export peak fitting results"""

    def __init__(self, fit_results, parent=None):
        super().__init__(parent)
        self.fit_results = fit_results
        method = fit_results.get('method', 'N/A').upper()
        self.setWindowTitle(f"Peak Analysis - {method}")
        self.setGeometry(200, 200, 700, 400)

        layout = QVBoxLayout(self)

        # Table
        self.table = QTableWidget()
        peaks = fit_results.get('peaks', [])
        self.table.setRowCount(len(peaks))

        # Columns: ID, 2θ, FWHM, Amplitude, Area, Sigma, (Gamma for Voigt)
        headers = ['ID', '2θ', 'FWHM', 'Amplitude', 'Area', 'Sigma']
        if peaks and 'gamma' in peaks[0]:
            headers.append('Gamma')

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        # Fill data
        for row, peak in enumerate(peaks):
            self.table.setItem(row, 0, QTableWidgetItem(str(peak.get('peak_id', row+1))))
            self.table.setItem(row, 1, QTableWidgetItem(f"{peak.get('2theta', 0):.4f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{peak.get('fwhm', 0):.4f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{peak.get('amplitude', 0):.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{peak.get('area', 0):.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{peak.get('sigma', 0):.4f}"))
            if 'gamma' in peak:
                self.table.setItem(row, 6, QTableWidgetItem(f"{peak.get('gamma', 0):.4f}"))

        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_export = QPushButton("Export CSV")
        btn_export.clicked.connect(self.export_csv)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_export)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def export_csv(self):
        """Export peak results to CSV file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Peak Results", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            peaks = self.fit_results.get('peaks', [])
            if not peaks:
                QMessageBox.warning(self, "Warning", "No peaks to export")
                return

            df = pd.DataFrame(peaks)
            df.to_csv(file_path, index=False, sep=';')
            QMessageBox.information(
                self, "Success",
                f"Exported {len(peaks)} peaks to {file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")
