# Per-session in-memory state. One AppState instance per browser session,
# managed by sessions.SessionManager (multi-tenant central server).

import threading
from collections import OrderedDict

MAX_CACHE_SIZE = 50


class AppState:
    def __init__(self):
        self.sid = ""  # session id (set by SessionManager)
        # Serialises requests within one session. threading.Lock (not RLock):
        # get_session holds it across a sync-generator yield, whose __enter__ /
        # __exit__ can run on DIFFERENT anyio threadpool threads. RLock checks the
        # owner thread on release → "cannot release un-acquired lock", and worse,
        # a failed release leaves the lock held forever → the next request on that
        # session hangs (UI freeze). Lock has no owner check and tolerates
        # cross-thread release. Safe here because the lock is never acquired
        # re-entrantly (only used in get_session, once per request).
        self.lock = threading.Lock()

        self.files = {}  # file_id -> {filename, file_path, data (DataFrame), headers, units}
        self.styles = {}  # file_id -> {line_color, line_color_y2, line_style, legend_label}
        self.processing_settings = {}  # flat, session-wide ProcessingSettings dict
        self.plot_style = {}  # DEFAULT_STYLE_SETTINGS
        self.extracted_columns = {}  # file_id -> {col_name: {value, precision}}
        self.x_column = ""
        self.y_columns = []
        self.y2_columns = []
        # Processed DataFrames (LRU, max 50). Key = file_id + processing settings
        # + columns (built in core/processing.py) so a stale entry is impossible.
        self.processed_cache = OrderedDict()
        # Folder watch (api/watch.py), RAM only: watched folder, {filename: (size, mtime)}
        # already loaded, and when the session was last persisted by a reload.
        self.watch_folder = ""
        self.watch_sigs = {}
        self.watch_persisted = 0.0

    def cache_get(self, key):
        """Return a cached processed DataFrame (marking it recently used), or None."""
        if key not in self.processed_cache:
            return None
        self.processed_cache.move_to_end(key)
        return self.processed_cache[key]

    def cache_put(self, key, value):
        """Add to processed_cache with LRU eviction."""
        if key in self.processed_cache:
            self.processed_cache.move_to_end(key)
        self.processed_cache[key] = value
        while len(self.processed_cache) > MAX_CACHE_SIZE:
            evicted_key, _ = self.processed_cache.popitem(last=False)
            print(f"🟡 Cache evicted: {evicted_key}")

    def clear_all(self):
        """Clear all state for reset."""
        self.files.clear()
        self.styles.clear()
        self.processing_settings.clear()
        self.plot_style.clear()
        self.extracted_columns.clear()
        self.x_column = ""
        self.y_columns = []
        self.y2_columns = []
        self.processed_cache.clear()
        self.watch_folder = ""
        self.watch_sigs = {}
        print("✅ All state cleared")
