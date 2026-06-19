"""Upload and file management endpoints (per session)."""

import os
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends

from config import MAX_FILES
from state import AppState
from sessions import get_session, manager, session_upload_dir
from models.schemas import FileInfo
from core.data_loader import load_file

router = APIRouter()

MAX_FILE_SIZE = 500_000_000  # 500 MB
ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.tsv'}


@router.post("/upload", response_model=list[FileInfo])
async def upload_files(files: list[UploadFile] = File(...),
                       state: AppState = Depends(get_session)):
    """Upload one or more files (CSV/Excel), parse them, return metadata."""
    print(f"🟢 Upload request [{state.sid}]: {len(files)} file(s)")
    results = []
    upload_dir = session_upload_dir(state.sid)

    for upload_file in files:
        filename = upload_file.filename or "unknown"

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            print(f"❌ Rejected {filename}: extension '{ext}' not allowed")
            results.append(FileInfo(
                file_id="", filename=filename, columns=[], row_count=0,
                error=f"Extension '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            ))
            continue

        content = await upload_file.read()
        if len(content) > MAX_FILE_SIZE:
            print(f"❌ Rejected {filename}: size {len(content)} exceeds limit {MAX_FILE_SIZE}")
            results.append(FileInfo(
                file_id="", filename=filename, columns=[], row_count=0,
                error=f"File too large ({len(content)} bytes). Max: {MAX_FILE_SIZE} bytes.",
            ))
            continue

        if len(state.files) >= MAX_FILES:
            print(f"❌ Rejected {filename}: max files limit ({MAX_FILES}) reached")
            results.append(FileInfo(
                file_id="", filename=filename, columns=[], row_count=0,
                error=f"Max files limit ({MAX_FILES}) reached. Delete some files first.",
            ))
            continue

        file_id = str(uuid4())
        disk_filename = file_id + ext
        file_path = os.path.join(upload_dir, disk_filename)

        with open(file_path, "wb") as f:
            f.write(content)
        print(f"🟡 Saved {filename} as {disk_filename}")

        try:
            parsed = load_file(file_path)
            df = parsed['data']
            state.files[file_id] = {
                'filename': filename,
                'file_path': file_path,
                'data': df,
                'headers': parsed['headers'],
                'units': parsed['units'],
            }
            results.append(FileInfo(
                file_id=file_id, filename=filename,
                columns=list(df.columns), row_count=len(df),
            ))
            print(f"✅ Uploaded {filename} (id={file_id}): {len(df)} rows, {len(df.columns)} cols")
        except Exception as e:
            print(f"❌ Failed to parse {filename}: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            results.append(FileInfo(
                file_id="", filename=filename, columns=[], row_count=0,
                error=f"Failed to parse: {str(e)}",
            ))

    manager.persist(state.sid)
    return results


@router.get("/files", response_model=list[FileInfo])
def list_files(state: AppState = Depends(get_session)):
    """List all uploaded files with their metadata."""
    results = []
    for file_id, file_info in state.files.items():
        df = file_info['data']
        results.append(FileInfo(
            file_id=file_id, filename=file_info['filename'],
            columns=list(df.columns), row_count=len(df),
        ))
    return results


@router.delete("/files/{file_id}")
def delete_file(file_id: str, state: AppState = Depends(get_session)):
    """Remove a file from session and disk."""
    if file_id not in state.files:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found")

    file_info = state.files[file_id]
    file_path = file_info.get('file_path', '')
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
        print(f"🟡 Deleted file from disk: {file_path}")

    del state.files[file_id]
    state.processed_cache.pop(file_id, None)
    state.styles.pop(file_id, None)
    state.processing_settings.pop(file_id, None)
    state.extracted_columns.pop(file_id, None)

    manager.persist(state.sid)
    print(f"✅ Deleted file: {file_id}")
    return {"status": "deleted", "file_id": file_id}


@router.get("/files/{file_id}/columns")
def get_columns(file_id: str, state: AppState = Depends(get_session)):
    """Get columns for a specific file."""
    if file_id not in state.files:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found")
    df = state.files[file_id]['data']
    return {"file_id": file_id, "columns": list(df.columns)}


@router.get("/files/{file_id}/data")
def get_file_data(file_id: str, limit: int = Query(default=1000, ge=1, le=100000),
                  offset: int = Query(default=0, ge=0),
                  state: AppState = Depends(get_session)):
    """Get raw data as JSON (paginated)."""
    if file_id not in state.files:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found")

    df = state.files[file_id]['data']
    total_rows = len(df)
    page = df.iloc[offset:offset + limit]
    records = page.where(page.notna(), None).to_dict(orient='records')

    return {
        "file_id": file_id, "total_rows": total_rows,
        "offset": offset, "limit": limit, "data": records,
    }
