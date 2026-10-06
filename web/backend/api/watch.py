"""Folder watch: follow a sub-folder of SHARE_PATH and load what an instrument writes there.

The browser polls `POST /api/watch/poll` (every few seconds while watching is on). Each poll
scans the folder ONCE (non-recursive) and:

- loads every NEW data file into the session, exactly like an upload (same `upload_files`
  handler, so parsing and limits are identical);
- RELOADS a file already in the session when its size/mtime changed — an acquisition still
  writing into the same CSV shows up live. A text file that does not end with a newline is
  cut back to its last complete line, so a half-written row is never parsed.

The frontend then re-plots and replays the extraction recipes on the returned file ids
(the "LiveAnalysis" loop of PEOscillo, applied to any instrument writing files).

Watching is polling, not OS file events: events are unreliable on SMB shares and Syncthing
folders, a stat() per file every few seconds is cheap, and it needs no new dependency.
Files are matched by NAME within the session (a manual upload with the same name is updated
too); the (size, mtime) signatures live in RAM only — after a server restart each watched
file is re-read once, which is harmless.
"""

import io
import os
import time

from api.upload import ALLOWED_EXTENSIONS, upload_files
from config import SHARE_PATH
from core.data_loader import load_file
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from models.schemas import FileInfo
from pydantic import BaseModel
from sessions import get_session, manager
from state import AppState

router = APIRouter()

TEXT_EXTENSIONS = {".csv", ".tsv", ".txt"}
MAX_FOLDERS = 500
PERSIST_EVERY_S = 30  # a growing file must not rewrite the whole session .db every poll


class WatchRequest(BaseModel):
    folder: str = ""  # relative to SHARE_PATH; "" = the share itself


class WatchResult(BaseModel):
    folder: str
    added: list[FileInfo] = []
    updated: list[FileInfo] = []
    rejected: list[FileInfo] = []
    files_in_folder: int = 0


def _share_root() -> str:
    if not SHARE_PATH or not os.path.isdir(SHARE_PATH):
        raise HTTPException(status_code=503, detail="SHARE_PATH is not configured on the server")
    return os.path.realpath(SHARE_PATH)


def resolve_folder(folder: str) -> str:
    """Absolute path of a sub-folder of SHARE_PATH; refuses anything outside the share."""
    root = _share_root()
    path = os.path.realpath(os.path.join(root, folder or ""))
    if path != root and not path.startswith(root + os.sep):
        raise HTTPException(status_code=400, detail="Folder must be inside the shared folder")
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Folder '{folder}' not found on the share")
    return path


def read_complete(path: str) -> bytes:
    """File bytes, cut back to the last complete line for text formats (file being written)."""
    with open(path, "rb") as handle:
        data = handle.read()
    if os.path.splitext(path)[1].lower() in TEXT_EXTENSIONS and data and not data.endswith(b"\n"):
        data = data[: data.rfind(b"\n") + 1]
    return data


def scan(folder_path: str) -> dict[str, tuple[int, float]]:
    """{filename: (size, mtime)} for the data files directly inside the folder."""
    found = {}
    with os.scandir(folder_path) as entries:
        for entry in entries:
            if not entry.is_file() or entry.name.startswith((".", "~$")):
                continue  # hidden, Syncthing temp, Excel lock files
            if os.path.splitext(entry.name)[1].lower() not in ALLOWED_EXTENSIONS:
                continue
            st = entry.stat()
            found[entry.name] = (st.st_size, st.st_mtime)
    return found


def _replace_data(state: AppState, file_id: str, payload: bytes) -> FileInfo:
    """Reload an existing file in place: same id, so its colour, legend and checkbox stay."""
    entry = state.files[file_id]
    with open(entry["file_path"], "wb") as handle:
        handle.write(payload)
    parsed = load_file(entry["file_path"])
    entry.update(data=parsed["data"], headers=parsed["headers"], units=parsed["units"])
    for key in [k for k in state.processed_cache if k.startswith(f"{file_id}|")]:
        del state.processed_cache[key]
    df = parsed["data"]
    return FileInfo(file_id=file_id, filename=entry["filename"],
                    columns=list(df.columns), row_count=len(df))


@router.get("/watch/folders")
def list_folders():
    """Sub-folders of SHARE_PATH that can be watched ("" = the share itself)."""
    root = _share_root()
    folders = [""]
    for current, dirs, _files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for d in dirs:
            folders.append(os.path.relpath(os.path.join(current, d), root).replace(os.sep, "/"))
            if len(folders) >= MAX_FOLDERS:
                return {"folders": folders, "truncated": True}
    return {"folders": folders, "truncated": False}


@router.post("/watch/poll", response_model=WatchResult)
async def poll(req: WatchRequest, state: AppState = Depends(get_session)):
    """One watch cycle: load new files, reload changed ones. Safe to call repeatedly."""
    folder_path = resolve_folder(req.folder)
    seen = scan(folder_path)

    # Signatures are per session AND per folder: switching folder starts afresh.
    if state.watch_folder != folder_path:
        state.watch_folder = folder_path
        state.watch_sigs = {}
    sigs = state.watch_sigs
    by_name = {info["filename"]: fid for fid, info in state.files.items()}

    result = WatchResult(folder=req.folder, files_in_folder=len(seen))
    new_uploads = []
    for name, sig in sorted(seen.items()):
        if sigs.get(name) == sig:
            continue
        path = os.path.join(folder_path, name)
        try:
            payload = read_complete(path)
        except OSError as exc:  # locked by the writer: retry next poll
            print(f"⚠️ watch: cannot read {name} yet: {exc}")
            continue
        if not payload:
            continue  # nothing complete yet
        if name in by_name:
            # A failed attempt is not retried until the file changes again (a half-written
            # Excel file changes when its writer finishes).
            sigs[name] = sig
            try:
                result.updated.append(_replace_data(state, by_name[name], payload))
            except Exception as exc:
                print(f"⚠️ watch: reload of {name} failed, retried when it changes: {exc}")
        else:
            new_uploads.append((name, sig, payload))

    if new_uploads:
        uploads = [UploadFile(file=io.BytesIO(p), filename=n) for n, _s, p in new_uploads]
        infos = await upload_files(files=uploads, state=state)  # persists the session
        for (name, sig, _p), info in zip(new_uploads, infos):
            sigs[name] = sig  # a rejected file is retried when it changes
            (result.added if info.file_id else result.rejected).append(info)
        state.watch_persisted = time.monotonic()
    elif result.updated and time.monotonic() - state.watch_persisted > PERSIST_EVERY_S:
        manager.persist(state.sid)
        state.watch_persisted = time.monotonic()

    if result.added or result.updated:
        print(f"✅ watch [{state.sid}] {req.folder or '/'}: "
              f"+{len(result.added)} new, {len(result.updated)} reloaded")
    return result
