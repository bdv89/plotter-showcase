"""Pytest config: make the FastAPI backend importable from tests/.

The backend (web/backend) uses itself as its import root — modules do
`from core.X import Y`, `from config import ...`. Adding that directory to
sys.path lets the tests import the exact same code the running app uses.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).parent / "web" / "backend"
sys.path.insert(0, str(BACKEND))
