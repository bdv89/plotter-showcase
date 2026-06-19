# Per-session in-memory state. One AppState instance per browser session,
# managed by sessions.SessionManager (multi-tenant central server).

import threading
from collections import OrderedDict

MAX_CACHE_SIZE = 50


class AppState:
    def __init__(self):
        self.sid = ""  # session id (set by SessionManager)
        self.lock = threading.RLock()  # serialises requests within one session

        self.files = {}  # file_id -> {filename, file_path, data (DataFrame), headers, units}
        self.styles = {}  # file_id -> {line_color, line_color_y2, line_style, legend_label}
        self.processing_settings = {}  # file_id -> settings dict
        self.plot_style = {}  # DEFAULT_STYLE_SETTINGS
        self.extracted_columns = {}  # file_id -> {col_name: {value, precision}}
        self.x_column = ""
        self.y_columns = []
        self.y2_columns = []
        self.pipeline = None  # DataPipeline instance
        self.processed_cache = OrderedDict()  # file_id -> processed DataFrame (LRU, max 50)

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
        print("✅ All state cleared")
