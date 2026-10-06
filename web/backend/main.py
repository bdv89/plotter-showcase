"""FastAPI backend for CSV Plotter (multi-tenant central server)."""

import os
import shutil
from contextlib import asynccontextmanager

from api.extract import router as extract_router
from api.metrics import router as metrics_router
from api.plot import router as plot_router
from api.pool import router as pool_router
from api.upload import router as upload_router
from api.watch import router as watch_router
from config import FRONTEND_DIST, METRICS_DB, SESSIONS_DIR, SHARE_PATH, UPLOAD_DIR
from core import metrics
from fastapi import Depends, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from mcp_server import mcp
from sessions import cleanup_expired, get_session, manager, session_db_path
from state import AppState

# Serveur MCP (LLM) monté plus bas sur /mcp. streamable_http_app() doit être
# appelé AVANT d'accéder à mcp.session_manager (créé paresseusement).
_mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Démarrage + gestionnaire de sessions MCP.

    Un sous-app monté ne voit pas son lifespan exécuté : sans ce `session_manager.run()`,
    le premier appel MCP casse. Et FastAPI ignore les handlers @app.on_event dès qu'un
    lifespan est fourni — d'où le démarrage rapatrié ici.
    """
    print("🟢 CSV Plotter API starting (multi-tenant)")
    print(f"🟡 Upload dir: {UPLOAD_DIR}")
    print(f"🟡 Sessions dir: {SESSIONS_DIR}")
    print(f"🟡 Share path: {SHARE_PATH or '(not set)'}")
    metrics.init_metrics(METRICS_DB)  # connection-tracking DB
    print(f"🟡 Metrics DB: {METRICS_DB}")
    cleanup_expired()  # purge abandoned sessions from disk on boot
    async with mcp.session_manager.run():
        print("🟢 MCP endpoint ready on /mcp")
        yield


app = FastAPI(title="CSV Plotter API", version="0.3.0", lifespan=lifespan)

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
app.include_router(extract_router, prefix="/api", tags=["extract"])
app.include_router(pool_router, prefix="/api", tags=["pool"])
app.include_router(metrics_router, prefix="/api", tags=["metrics"])
app.include_router(watch_router, prefix="/api", tags=["watch"])

# Endpoints exclus du suivi de connexion (polling / auto-refresh → pas de bruit).
_METRICS_SKIP = ("/api/health", "/api/metrics", "/api/watch/poll")


@app.middleware("http")
async def track_connection(request: Request, call_next):
    """Compte les hits par endpoint + IPs uniques (suivi de connexion, best-effort)."""
    response = await call_next(request)
    try:
        path = request.url.path
        if (
            request.method != "OPTIONS"
            and path.startswith("/api/")
            and not path.startswith(_METRICS_SKIP)
        ):
            # IP réelle derrière nginx (X-Forwarded-For), sinon connexion directe.
            xff = request.headers.get("x-forwarded-for")
            ip = xff.split(",")[0].strip() if xff else (
                request.client.host if request.client else "?"
            )
            # Endpoint normalisé via le template de route (cardinalité bornée).
            route = request.scope.get("route")
            endpoint = getattr(route, "path", path)
            await run_in_threadpool(metrics.record, endpoint, ip)
    except Exception as exc:  # le suivi ne doit jamais casser une requête
        print(f"❌ track_connection failed: {exc}")
    return response


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


# MCP avant le StaticFiles sur "/" : Starlette résout les mounts dans l'ordre.
app.mount("/mcp", _mcp_app)

# Serve the built frontend (npm run build → dist/) same-origin at "/".
# Mounted LAST so /api/* routes take precedence. Skipped if not built yet (dev).
_dist = os.path.abspath(FRONTEND_DIST)
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
    print(f"🟢 Serving frontend from {_dist}")
else:
    print(f"🟡 Frontend dist not found ({_dist}) — run 'npm run build' to serve UI same-origin")
