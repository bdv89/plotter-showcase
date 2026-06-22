"""Pool save/load/export endpoints — per session."""

import os
from uuid import uuid4

from config import SHARE_PATH, UPLOAD_DIR
from core.db_schema import load_from_sqlite, save_to_sqlite
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from models.schemas import PoolSaveRequest
from sessions import build_data_pool, get_session, manager, restore_from_data_pool
from state import AppState

router = APIRouter()


def _sync_state(req: PoolSaveRequest, state: AppState):
    """Sync a session's state from a frontend save/export payload."""
    if req.styles:
        state.styles.update(req.styles)
    if req.plot_style:
        state.plot_style = req.plot_style
    if req.processing:
        state.processing_settings = req.processing
    state.x_column = req.x_column
    state.y_columns = req.y_columns
    state.y2_columns = req.y2_columns


@router.post("/pool/export")
def export_pool(req: PoolSaveRequest = PoolSaveRequest(),
                state: AppState = Depends(get_session)):
    """Build the pool .db and return its bytes (frontend saves it via the browser)."""
    _sync_state(req, state)
    tmp = os.path.join(UPLOAD_DIR, f"_export_{uuid4().hex}.db")
    try:
        save_to_sqlite(build_data_pool(state), tmp)
        with open(tmp, "rb") as f:
            content = f.read()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    print(f"✅ Pool exported ({len(content)} bytes, {len(state.files)} files)")
    return Response(content=content, media_type="application/octet-stream")


@router.post("/pool/save")
def save_pool(req: PoolSaveRequest = PoolSaveRequest(),
              state: AppState = Depends(get_session)):
    """Save current session to a .db file on the server/share."""
    path = os.path.join(UPLOAD_DIR, os.path.basename(req.path)) if req.path else os.path.join(UPLOAD_DIR, "pool.db")
    _sync_state(req, state)
    if not path.endswith('.db'):
        path += '.db'
    print(f"🟢 Saving pool to {path}")
    try:
        save_to_sqlite(build_data_pool(state), path)
        print(f"✅ Pool saved to {path}")
        return {"status": "saved", "path": path, "files_count": len(state.files)}
    except Exception as e:
        print(f"❌ Pool save failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save pool: {str(e)}")


@router.post("/pool/load")
async def load_pool(file: UploadFile = File(...),
                    state: AppState = Depends(get_session)):
    """Load a .db file into the session, return full session state."""
    print(f"🟢 Loading pool from uploaded file: {file.filename}")
    temp_path = os.path.join(UPLOAD_DIR, f"_temp_{uuid4().hex}.db")
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        data_pool = load_from_sqlite(temp_path)
        restore_from_data_pool(state, data_pool)
        manager.persist(state.sid)
        return _session_payload(state)
    except Exception as e:
        print(f"❌ Pool load failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load pool: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/session")
def get_session_state(state: AppState = Depends(get_session)):
    """Return the current session's full state so the frontend can rehydrate."""
    return _session_payload(state)


def _session_payload(state: AppState) -> dict:
    files_info = [
        {"file_id": fid, "filename": fi['filename'],
         "columns": list(fi['data'].columns), "row_count": len(fi['data'])}
        for fid, fi in state.files.items()
    ]
    styles = {
        fid: {
            "line_color": s.get('line_color', ''),
            "line_color_y2": s.get('line_color_y2', ''),
            "line_style": s.get('line_style', 'solid'),
            "legend_label": s.get('legend_label', ''),
        }
        for fid, s in state.styles.items()
    }
    return {
        "files": files_info,
        "styles": styles,
        "extracted": dict(state.extracted_columns),
        "plot_style": state.plot_style,
        "processing": state.processing_settings,
        "plot_settings": {
            "x_column": state.x_column,
            "y_columns": state.y_columns,
            "y2_columns": state.y2_columns,
        },
    }


@router.get("/pool/list")
def list_pools():
    """List .db files on SHARE_PATH."""
    if not SHARE_PATH or not os.path.isdir(SHARE_PATH):
        return {"pools": [], "share_path": SHARE_PATH or "(not set)"}
    db_files = []
    for f in os.listdir(SHARE_PATH):
        if f.endswith('.db'):
            full_path = os.path.join(SHARE_PATH, f)
            db_files.append({"filename": f, "path": full_path, "size_bytes": os.path.getsize(full_path)})
    return {"pools": db_files, "share_path": SHARE_PATH}
