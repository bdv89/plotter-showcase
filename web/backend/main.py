"""FastAPI backend for CSV Plotter (multi-tenant central server)."""

import os
import shutil

from api.extract import router as extract_router
from api.plot import router as plot_router
from api.pool import router as pool_router
from api.process import router as process_router
from api.upload import router as upload_router
from config import FRONTEND_DIST, SESSIONS_DIR, SHARE_PATH, UPLOAD_DIR
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sessions import cleanup_expired, get_session, manager, session_db_path
from state import AppState

app = FastAPI(title="CSV Plotter API", version="0.2.0")

# CORS still allowed for dev (frontend on a different port). In production the
# built frontend is served same-origin (below), so CORS is a no-op there.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api", tags=["upload"])
app.include_router(plot_router, prefix="/api", tags=["plot"])
app.include_router(process_router, prefix="/api", tags=["process"])
app.include_router(extract_router, prefix="/api", tags=["extract"])
app.include_router(pool_router, prefix="/api", tags=["pool"])


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "upload_dir": UPLOAD_DIR,
        "share_path": SHARE_PATH,
        "sessions_dir": SESSIONS_DIR,
        "sessions_in_memory": len(manager._sessions),
    }


@app.delete("/api/reset")
def reset_state(state: AppState = Depends(get_session)):
    """Clear the calling session's state (RAM + its .db)."""
    count = len(state.files)
    state.clear_all()
    path = session_db_path(state.sid)
    if os.path.exists(path):
        os.remove(path)
    shutil.rmtree(os.path.join(UPLOAD_DIR, state.sid), ignore_errors=True)
    print(f"🟢 Reset session {state.sid}: cleared {count} files")
    return {"status": "reset", "files_cleared": count}


@app.on_event("startup")
def startup():
    print("🟢 CSV Plotter API starting (multi-tenant)")
    print(f"🟡 Upload dir: {UPLOAD_DIR}")
    print(f"🟡 Sessions dir: {SESSIONS_DIR}")
    print(f"🟡 Share path: {SHARE_PATH or '(not set)'}")
    cleanup_expired()  # purge abandoned sessions from disk on boot


# Serve the built frontend (npm run build → dist/) same-origin at "/".
# Mounted LAST so /api/* routes take precedence. Skipped if not built yet (dev).
_dist = os.path.abspath(FRONTEND_DIST)
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
    print(f"🟢 Serving frontend from {_dist}")
else:
    print(f"🟡 Frontend dist not found ({_dist}) — run 'npm run build' to serve UI same-origin")
