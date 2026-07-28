"""Extraction endpoints - compute statistical metrics from data."""

from core.extraction import OPERATIONS, compute_extraction
from fastapi import APIRouter, Depends, HTTPException
from models.schemas import ExtractRemoveRequest, ExtractRequest
from sessions import get_session, manager
from state import AppState

router = APIRouter()


@router.post("/extract")
def extract_single(req: ExtractRequest, state: AppState = Depends(get_session)):
    """Compute a single extraction for one file."""
    print(f"🟢 Extract request: {req.operation} on {req.column} for {req.file_id}")

    if req.file_id not in state.files:
        raise HTTPException(status_code=404, detail=f"File '{req.file_id}' not found")

    # Use processed data if available
    if req.file_id in state.processed_cache:
        df = state.processed_cache[req.file_id]
    else:
        df = state.files[req.file_id]['data']

    result = compute_extraction(
        df=df,
        column=req.column,
        operation=req.operation,
        x_column=req.x_column,
        x_value=req.x_value,
        condition_column=req.condition_column,
        threshold=req.threshold,
        operator=req.operator,
        fallback_type=req.fallback_type,
        fallback_value=req.fallback_value,
        x_min=req.x_min,
        x_max=req.x_max,
    )

    if result is not None:
        rounded = round(result, req.precision)

        # Store in session state
        if req.file_id not in state.extracted_columns:
            state.extracted_columns[req.file_id] = {}

        col_name = f"{req.operation}({req.column})"
        state.extracted_columns[req.file_id][col_name] = {
            'value': rounded,
            'precision': req.precision,
        }

        return {
            "file_id": req.file_id,
            "column": req.column,
            "operation": req.operation,
            "value": rounded,
            "precision": req.precision,
        }
    else:
        raise HTTPException(status_code=400, detail="Extraction returned no result")


@router.post("/extract/preview")
def extract_preview(req: ExtractRequest, state: AppState = Depends(get_session)):
    """Preview extraction for all loaded files (or a specific file)."""
    print(f"🟢 Extract preview: {req.operation} on {req.column}")

    results = []

    # If file_id specified, only preview that one; otherwise preview all
    file_ids = [req.file_id] if req.file_id else list(state.files.keys())

    for file_id in file_ids:
        if file_id not in state.files:
            results.append({"file_id": file_id, "value": None, "error": "File not found"})
            continue

        # Use processed data if available
        if file_id in state.processed_cache:
            df = state.processed_cache[file_id]
        else:
            df = state.files[file_id]['data']

        value = compute_extraction(
            df=df,
            column=req.column,
            operation=req.operation,
            x_column=req.x_column,
            x_value=req.x_value,
            condition_column=req.condition_column,
            threshold=req.threshold,
            operator=req.operator,
            fallback_type=req.fallback_type,
            fallback_value=req.fallback_value,
            x_min=req.x_min,
            x_max=req.x_max,
        )

        if value is not None:
            rounded = round(value, req.precision)
            results.append({"file_id": file_id, "value": rounded})
        else:
            results.append({"file_id": file_id, "value": None, "error": "Extraction failed"})

    print(f"✅ Preview complete: {len(results)} files")
    return {"results": results, "operation": req.operation, "column": req.column}


@router.post("/extract/remove")
def remove_extracted(req: ExtractRemoveRequest, state: AppState = Depends(get_session)):
    """Remove one extracted column (from every file) or clear them all, then persist
    once so the deletion survives a page reload / rehydrate."""
    if req.column_name:
        removed = 0
        for cols in state.extracted_columns.values():
            if req.column_name in cols:
                del cols[req.column_name]
                removed += 1
        print(f"🟡 Removed extracted column '{req.column_name}' from {removed} file(s)")
    else:
        state.extracted_columns.clear()
        print("🟡 Cleared all extracted columns")

    manager.persist(state.sid)
    return {"status": "ok"}


@router.get("/extract/operations")
def list_operations():
    """List available extraction operations."""
    ops = {}
    for name, (op_type, _) in OPERATIONS.items():
        ops[name] = op_type
    return {"operations": ops}
