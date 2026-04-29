#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import logging
import traceback
from datetime import datetime
from main_app import CSVPlotterApp
from PyQt5.QtWidgets import QApplication


def _setup_file_logging():
    """Configure a basic file logger to capture early startup errors."""
    try:
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'app_debug.log')

        # Simple file handler without altering global config too much
        handler = logging.FileHandler(log_path, encoding='utf-8')
        fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        handler.setFormatter(fmt)

        root = logging.getLogger()
        root.setLevel(logging.INFO)
        # Avoid duplicate handlers if run repeatedly in same interpreter
        if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == handler.baseFilename for h in root.handlers):
            root.addHandler(handler)

        # Write a header for the new session
        logging.info('--- Application launch: %s ---', datetime.now().isoformat())
        return log_path
    except Exception:
        # Don't block launch if logging fails
        return None


def _install_exception_hook(log_path: str = None):
    """Capture unhandled exceptions to the log file and stderr."""
    def _hook(exc_type, exc_value, exc_tb):
        tb_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            logging.error('Unhandled exception:\n%s', tb_text)
        finally:
            # Also print to stderr so console users see it
            sys.stderr.write(tb_text)
        # Let default behavior continue (non-zero exit)
    sys.excepthook = _hook

def main():
    log_path = _setup_file_logging()
    _install_exception_hook(log_path)
    app = QApplication(sys.argv)
    window = CSVPlotterApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
