"""
Logging wrapper - preserves emoji style from CLAUDE.md

Usage:
    from app_logging import logger
    logger.debug("🟢 Loading file")
    logger.info("✅ Success")
    logger.error("❌ Failed")

Emoji mapping (CLAUDE.md compliant):
    🟢🟡🔴⚫🔵 → DEBUG (process steps)
    ✅ → INFO (success confirmation)
    ❌ → ERROR (failure detected)
"""

import logging
import os
import sys
from datetime import datetime

# Create logger
logger = logging.getLogger('csvplotter')
logger.setLevel(logging.DEBUG)

# Avoid duplicate handlers on re-import
if not logger.handlers:
    # Console handler - INFO level (user-facing messages)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler - DEBUG level (all messages)
    # Create logs directory next to app_logging.py
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, 'app_debug.log')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)


# Convenience aliases for cleaner code
def debug(msg):
    """For process steps: 🟢🟡🔴⚫🔵"""
    logger.debug(msg)

def info(msg):
    """For success confirmations: ✅"""
    logger.info(msg)

def warning(msg):
    """For warnings"""
    logger.warning(msg)

def error(msg):
    """For failures: ❌"""
    logger.error(msg)
