"""Version and update checking for CSV Plotter.

This module handles:
- Auto-generated version numbers based on build date (YYMMDD format)
- Update checking against SMB share
- Version display formatting

Environment Variables:
    CSVPLOTTER_UPDATE_PATH: Override default SMB path or disable updates
        - "0" or "" → disables update checking
        - Any other path → uses that path instead of default
"""
import os
from pathlib import Path
from datetime import datetime

# Version auto-generated from build date (YYMMDD format)
# This will be frozen to a static string during the build process
__version__ = datetime.now().strftime("%y%m%d")

# Default SMB share path (CHANGE THIS FOR YOUR SERVER)
# Examples:
#   r"\\FILESERVER01\CSVPlotter"
#   r"\\192.168.1.100\CSVPlotter"
DEFAULT_SMB_PATH = r"\\<FILE_SERVER>\<SHARE>"

# Allow override via environment variable
# Special values:
#   - "0" or empty string → DISABLE update checking
#   - Any other path → use that path instead of default
SMB_SHARE_PATH = os.getenv("CSVPLOTTER_UPDATE_PATH", DEFAULT_SMB_PATH)

VERSION_FILE = "version.txt"


def check_for_updates():
    """Check if a newer version is available on the SMB share.

    Returns:
        dict | None: Dictionary with 'version' and 'path' if update available,
                     None if no update or checking disabled

    Examples:
        >>> update = check_for_updates()
        >>> if update:
        ...     print(f"Version {update['version']} available at {update['path']}")
    """
    # Kill switch: disable if env var is "0" or empty
    if SMB_SHARE_PATH in ("0", ""):
        return None

    try:
        version_path = Path(SMB_SHARE_PATH) / VERSION_FILE
        if not version_path.exists():
            return None

        server_version = version_path.read_text().strip()

        # String comparison works for YYMMDD: "251118" < "251119"
        if server_version > __version__:
            return {
                "version": server_version,
                "path": str(Path(SMB_SHARE_PATH) / "csvplotter.exe")
            }
    except Exception:
        # Silent fail if network unavailable, permissions denied, etc.
        pass

    return None


def format_version_display(version_str):
    """Convert YYMMDD timestamp to human-readable date format.

    Args:
        version_str: Version string in YYMMDD format (e.g., "251118")

    Returns:
        Formatted date string (e.g., "18 Nov 2025")
        Falls back to raw string if parsing fails

    Examples:
        >>> format_version_display("251118")
        "18 Nov 2025"
        >>> format_version_display("invalid")
        "invalid"
    """
    try:
        dt = datetime.strptime(version_str, "%y%m%d")
        return dt.strftime("%d %b %Y")
    except (ValueError, TypeError):
        return version_str  # Fallback to raw string if parsing fails
