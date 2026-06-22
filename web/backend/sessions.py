"""Per-session state for multi-tenant central-server mode.

One AppState per browser session (X-Session-Id header). State is kept in memory
(LRU-capped, TTL-evicted) and auto-persisted to disk as <sid>.db using the same
pool format as Save/Load, so sessions survive a server restart (lazy-reloaded on
next access). If no session header is present, a shared "default" session is used
so the app keeps working before the frontend starts sending the header.
"""

import os
import shutil
import threading
import time
from collections import OrderedDict
from uuid import uuid4

import pandas as pd
from config import (
    HEAVY_CONCURRENCY,
    MAX_SESSIONS_IN_MEMORY,
    SESSION_RETENTION_DAYS,
    SESSION_TTL,
    SESSIONS_DIR,
    UPLOAD_DIR,
)
from core.db_schema import load_from_sqlite, save_to_sqlite
from fastapi import Header
from state import AppState

# Cap concurrent heavy CPU jobs (process/extract) so N users can't thrash the box.
HEAVY_SEM = threading.BoundedSemaphore(HEAVY_CONCURRENCY)

DEFAULT_SESSION = "default"


def session_db_path(sid: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{sid}.db")


def session_upload_dir(sid: str) -> str:
    d = os.path.join(UPLOAD_DIR, sid)
    os.makedirs(d, exist_ok=True)
    return d


def build_data_pool(state: AppState) -> dict:
    """Build the pool dict (Save/Load format) from a session's AppState."""
    csv_files = []
    for file_id, file_info in state.files.items():
        entry = {
            'filename': file_info['filename'],
            'data': file_info['data'],
            'headers': file_info.get('headers', list(file_info['data'].columns)),
            'units': file_info.get('units', {}),
        }
        if file_id in state.extracted_columns:
            entry['extracted_data'] = state.extracted_columns[file_id]
        csv_files.append(entry)

    # Styles are keyed by filename in the pool format (the .db has no UUIDs).
    by_name = {fid: state.files[fid]['filename'] for fid in state.files}
    return {
        'csv_files': csv_files,
        'line_colors': {by_name[fid]: s.get('line_color', '') for fid, s in state.styles.items() if fid in by_name},
        'line_colors_y2': {by_name[fid]: s.get('line_color_y2', '') for fid, s in state.styles.items() if fid in by_name},
        'line_styles': {by_name[fid]: s.get('line_style', '') for fid, s in state.styles.items() if fid in by_name},
        'legend_labels': {by_name[fid]: s.get('legend_label', '') for fid, s in state.styles.items() if fid in by_name},
        'checked_files': [state.files[fid]['filename'] for fid in state.files],
        'fit_results': {},
        'plot_settings': {
            'x_column': state.x_column,
            'y_columns': state.y_columns,
            'y2_columns': state.y2_columns,
        },
        'plot_style_settings': state.plot_style,
        'processing_settings': state.processing_settings,
        'metadata': {'version': 'web-0.1.0'},
    }


def restore_from_data_pool(state: AppState, data_pool: dict) -> None:
    """Restore a session's AppState from a loaded pool dict (new UUIDs)."""
    state.files.clear()
    state.styles.clear()
    state.processing_settings.clear()
    state.extracted_columns.clear()
    state.processed_cache.clear()

    for file_entry in data_pool.get('csv_files', []):
        filename = file_entry.get('filename', '')
        if not filename:
            continue
        file_id = str(uuid4())
        state.files[file_id] = {
            'filename': filename,
            'file_path': '',
            'data': file_entry.get('data', pd.DataFrame()),
            'headers': file_entry.get('headers', []),
            'units': file_entry.get('units', {}),
        }
        if 'extracted_data' in file_entry:
            state.extracted_columns[file_id] = file_entry['extracted_data']

    for file_id in state.files:
        name = state.files[file_id]['filename']
        state.styles[file_id] = {
            'line_color': data_pool.get('line_colors', {}).get(name, ''),
            'line_color_y2': data_pool.get('line_colors_y2', {}).get(name, ''),
            'line_style': data_pool.get('line_styles', {}).get(name, ''),
            'legend_label': data_pool.get('legend_labels', {}).get(name, ''),
        }

    state.plot_style = data_pool.get('plot_style_settings', {})
    plot_settings = data_pool.get('plot_settings', {})
    state.x_column = plot_settings.get('x_column', '')
    state.y_columns = plot_settings.get('y_columns', [])
    state.y2_columns = plot_settings.get('y2_columns', [])
    state.processing_settings = data_pool.get('processing_settings', {})


class SessionManager:
    def __init__(self):
        self._sessions: "OrderedDict[str, AppState]" = OrderedDict()
        self._access: dict[str, float] = {}
        self._lock = threading.RLock()

    def get(self, sid: str) -> AppState:
        with self._lock:
            self._sweep_ttl()
            st = self._sessions.get(sid)
            if st is None:
                st = AppState()
                st.sid = sid
                path = session_db_path(sid)
                if os.path.exists(path):
                    try:
                        restore_from_data_pool(st, load_from_sqlite(path))
                        print(f"🟢 Session {sid}: restored {len(st.files)} files from disk")
                    except Exception as e:
                        print(f"⚠️ Session {sid}: restore failed: {e}")
                self._sessions[sid] = st
            self._sessions.move_to_end(sid)
            self._access[sid] = time.time()
            self._evict_lru()
            return st

    def persist(self, sid: str) -> None:
        st = self._sessions.get(sid)
        if st is None:
            return
        path = session_db_path(sid)
        tmp = path + ".tmp"
        try:
            # Write to a temp file then atomically replace, so a crash mid-write
            # never corrupts an existing session .db.
            save_to_sqlite(build_data_pool(st), tmp)
            os.replace(tmp, path)
        except Exception as e:
            print(f"⚠️ Session {sid}: persist failed: {e}")
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _evict_lru(self) -> None:
        while len(self._sessions) > MAX_SESSIONS_IN_MEMORY:
            old_sid, _ = self._sessions.popitem(last=False)
            self._access.pop(old_sid, None)
            print(f"🟡 Session evicted from RAM (LRU): {old_sid}")

    def _sweep_ttl(self) -> None:
        if SESSION_TTL <= 0:
            return
        now = time.time()
        stale = [s for s, t in self._access.items() if now - t > SESSION_TTL]
        for s in stale:
            self._sessions.pop(s, None)
            self._access.pop(s, None)
            print(f"🟡 Session expired (TTL): {s}")


manager = SessionManager()


def get_session(x_session_id: str = Header(default=None)):
    """FastAPI dependency: resolve the session's AppState and hold its lock for
    the whole request, so concurrent requests on the SAME session serialise
    (no races on the in-memory dicts). Different sessions run concurrently."""
    st = manager.get(x_session_id or DEFAULT_SESSION)
    with st.lock:
        yield st


def cleanup_expired() -> int:
    """Purge abandoned sessions from disk: remove <sid>.db + its upload dir when
    the .db hasn't been written for SESSION_RETENTION_DAYS. Returns count removed."""
    if SESSION_RETENTION_DAYS <= 0:
        return 0
    cutoff = time.time() - SESSION_RETENTION_DAYS * 86400
    removed = 0
    try:
        names = os.listdir(SESSIONS_DIR)
    except OSError:
        return 0
    for name in names:
        if not name.endswith(".db"):
            continue
        path = os.path.join(SESSIONS_DIR, name)
        try:
            if os.path.getmtime(path) >= cutoff:
                continue
            sid = name[:-3]
            os.remove(path)
            shutil.rmtree(os.path.join(UPLOAD_DIR, sid), ignore_errors=True)
            removed += 1
        except OSError:
            continue
    if removed:
        print(f"🟡 Retention: purged {removed} abandoned session(s) from disk")
    return removed
