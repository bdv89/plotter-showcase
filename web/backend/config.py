import os

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/csv-plotter-uploads")
SHARE_PATH = os.environ.get("SHARE_PATH", "")
SETTINGS_DIR = os.path.join(SHARE_PATH, "plot_settings") if SHARE_PATH else ""

# Per-session disk persistence (one <sid>.db per browser session)
SESSIONS_DIR = os.environ.get("SESSIONS_DIR", os.path.join(UPLOAD_DIR, "sessions"))

# Connection-tracking metrics DB (one per deployment → isolé prod/beta via UPLOAD_DIR)
METRICS_DB = os.environ.get("METRICS_DB", os.path.join(UPLOAD_DIR, "metrics.sqlite"))

# Multi-tenant limits — good neighbour on a SHARED server. NVMe is the backing
# store: only actively-used sessions stay hot in RAM (≈ peak concurrency), the
# rest live on disk and are reloaded on return. RAM is decoupled from user count.
# Calibrated on real pools: ~0.27 MB/file (≈3,700 rows), so a 253-file session
# ≈ 64 MB. Worst case ≈ MAX_SESSIONS_IN_MEMORY × MAX_FILES × 0.3 MB ≈ 1.4 GB;
# typical < 0.5 GB. Trivial footprint on a shared 64 GB box.
MAX_FILES = int(os.environ.get("MAX_FILES", "300"))                 # per session (covers a 253-file session + margin)
MAX_SESSIONS_IN_MEMORY = int(os.environ.get("MAX_SESSIONS_IN_MEMORY", "16"))  # ~peak concurrency, not user count
SESSION_TTL = int(os.environ.get("SESSION_TTL", str(8 * 3600)))     # seconds idle → evict from RAM
HEAVY_CONCURRENCY = int(os.environ.get("HEAVY_CONCURRENCY", str(min(4, max(1, (os.cpu_count() or 4) - 1)))))
# Purge abandoned sessions from DISK (.db + upload dir) after this many idle days.
SESSION_RETENTION_DAYS = int(os.environ.get("SESSION_RETENTION_DAYS", "30"))

# Directory of the built frontend (served as static at "/")
FRONTEND_DIST = os.environ.get("FRONTEND_DIST", os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)
