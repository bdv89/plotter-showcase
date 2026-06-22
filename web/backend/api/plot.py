"""Plot data endpoints - returns trace data for Plotly.js."""

from fastapi import APIRouter, Depends
from models.schemas import PlotDataResponse, PlotRequest, PlotTrace
from sessions import get_session
from state import AppState

router = APIRouter()


@router.post("/plot-data", response_model=PlotDataResponse)
def get_plot_data(req: PlotRequest, state: AppState = Depends(get_session)):
    """Return x/y arrays for Plotly.js traces.

    For each file_id + y_column combination, return a trace with x, y, name, yaxis.
    Uses processed data if available in cache, otherwise raw data.
    """
    print(f"🟢 Plot data request: {len(req.file_ids)} files, "
          f"{len(req.y_columns)} y-cols, {len(req.y2_columns)} y2-cols")

    traces = []

    for file_id in req.file_ids:
        if file_id not in state.files:
            print(f"⚠️ File '{file_id}' not found, skipping")
            continue

        # Use processed data if available, otherwise raw
        if file_id in state.processed_cache:
            df = state.processed_cache[file_id]
            print(f"🟡 Using processed data for {file_id}")
        else:
            df = state.files[file_id]['data']

        # Check x column exists
        if req.x_column not in df.columns:
            print(f"⚠️ X column '{req.x_column}' not found in {file_id}, skipping")
            continue

        x_data = df[req.x_column].tolist()

        # Y columns (primary axis)
        for y_col in req.y_columns:
            if y_col not in df.columns:
                print(f"⚠️ Y column '{y_col}' not found in {file_id}, skipping")
                continue

            y_data = df[y_col].tolist()
            trace_name = f"{file_id} - {y_col}" if len(req.y_columns) > 1 else file_id

            traces.append(PlotTrace(
                x=x_data,
                y=y_data,
                name=trace_name,
                yaxis="y",
                file_id=file_id,
            ))

        # Y2 columns (secondary axis)
        for y2_col in req.y2_columns:
            if y2_col not in df.columns:
                print(f"⚠️ Y2 column '{y2_col}' not found in {file_id}, skipping")
                continue

            y_data = df[y2_col].tolist()
            trace_name = f"{file_id} - {y2_col} (Y2)"

            traces.append(PlotTrace(
                x=x_data,
                y=y_data,
                name=trace_name,
                yaxis="y2",
                file_id=file_id,
            ))

    print(f"✅ Returning {len(traces)} traces")
    return PlotDataResponse(traces=traces)
