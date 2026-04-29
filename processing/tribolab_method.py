"""
tribolab_method.py

Method for processing Tribolab tribometer oscillation data.
Performs time-window averaging to generate summary datasets.
Supports both .txt and .tst (Bruker UMT) file formats.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from method_protocol import MethodProtocol, ProcessInfo, ProcessResult, ProcessCallbacks

import csv
import re
import struct
import dataclasses
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Sequence
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFormLayout, QMessageBox
from PyQt5.QtCore import Qt

# Polars for high-performance data operations (preferred)
try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

# NumPy for vectorized operations and binary decoding (fallback)
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    if not HAS_POLARS:
        import warnings
        warnings.warn("Neither Polars nor NumPy available - using slower pure Python implementation")


# ===== TST File Parsing (adapted from umt_tst_convert.py) =====

SENTINEL = b"# 29##******************#$$\r\n"


def _parse_value(raw: str):
    text = raw.strip()
    if not text:
        return ""
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _line_to_kv(line: str) -> Optional[Tuple[str, str]]:
    if "$" not in line:
        return None
    try:
        before, after = line.split("$", 1)
        value, _ = after.split("$", 1)
    except ValueError:
        return None
    key = before.split("#")[-1].strip()
    return key, value


def _parse_block(block: bytes) -> Dict[str, object]:
    text = block.decode("ascii", errors="ignore")
    result: Dict[str, object] = {}
    for raw in text.splitlines():
        parsed = _line_to_kv(raw)
        if not parsed:
            continue
        key, value = parsed
        result[key] = _parse_value(value)
    return result


@dataclasses.dataclass
class Channel:
    name: str
    unit: str
    length: int
    dtype: str

    def decode(self, payload: bytes) -> float:
        if self.length == 8:
            return struct.unpack("<d", payload)[0]
        if self.length == 4:
            return struct.unpack("<f", payload)[0]
        if self.length == 2:
            return struct.unpack("<h", payload)[0]
        if self.length == 1:
            return struct.unpack("<b", payload)[0]
        raise ValueError(f"Unsupported channel width: {self.length}")


@dataclasses.dataclass
class StepData:
    run_no: int
    test_no: int
    global_index: int
    raw_step_no: int
    run_step_index: int
    metadata: Dict[str, object]
    descriptor: Dict[str, object]
    samples: int
    duration_seconds: float
    start_label: str
    rows: List[Tuple[float, ...]]


@dataclasses.dataclass
class TSTFile:
    path: Path
    header_meta: Dict[str, object]
    channels: List[Channel]
    runs: List[Dict[str, object]]
    steps: List[StepData]


def _parse_channels(header: bytes) -> Tuple[Dict[str, object], List[Channel]]:
    meta: Dict[str, object] = {}
    channels: List[Channel] = []
    current: Optional[Channel] = None
    text = header.decode("ascii", errors="ignore")
    for raw in text.splitlines():
        parsed = _line_to_kv(raw)
        if not parsed:
            continue
        key, value = parsed
        if key == "Name":
            current = Channel(name=value.strip(), unit="", length=0, dtype="")
            channels.append(current)
            continue
        if current:
            if key == "Unit" and not current.unit:
                current.unit = value.strip()
                continue
            if key == "LengthInBytes" and current.length == 0:
                current.length = int(value)
                continue
            if key == "Type" and not current.dtype:
                current.dtype = str(value).strip()
                current = None
                continue
        meta[key] = _parse_value(value)
    return meta, channels


def _decode_rows(
    chunk: bytes, samples: int, channels: Sequence[Channel], stride: int = 1
) -> List[Tuple[float, ...]]:
    """
    Decode binary data rows with optional stride sampling.

    Args:
        chunk: Binary data chunk
        samples: Total number of samples in chunk
        channels: Channel definitions
        stride: Keep every Nth sample (1 = all samples, 15 = every 15th)

    Returns:
        List of decoded rows (length = samples // stride)
    """
    if samples <= 0:
        return []

    stride = max(1, stride)

    # Use vectorized NumPy decoding if available
    if HAS_NUMPY:
        return _decode_rows_vectorized(chunk, samples, channels, stride)
    else:
        # Fallback to original implementation
        return _decode_rows_python(chunk, samples, channels, stride)


def _decode_rows_vectorized(
    chunk: bytes, samples: int, channels: Sequence[Channel], stride: int
) -> List[Tuple[float, ...]]:
    """
    Vectorized NumPy implementation of row decoding (10-50x faster).

    Decodes entire chunk at once using np.frombuffer, then applies stride via slicing.
    """
    record_len = len(chunk) // samples
    payload_len = sum(c.length for c in channels)
    padding = record_len - payload_len
    if padding < 0:
        raise ValueError("Chunk smaller than expected payload")

    # Build NumPy dtype from channels
    dtype_list = []
    for idx, channel in enumerate(channels):
        if channel.length == 8:
            dtype_list.append((f'ch{idx}', '<f8'))  # double
        elif channel.length == 4:
            dtype_list.append((f'ch{idx}', '<f4'))  # float
        elif channel.length == 2:
            dtype_list.append((f'ch{idx}', '<i2'))  # short
        elif channel.length == 1:
            dtype_list.append((f'ch{idx}', '<i1'))  # byte
        else:
            raise ValueError(f"Unsupported channel width: {channel.length}")

    # Add padding field if present
    if padding > 0:
        dtype_list.append(('padding', f'V{padding}'))  # Void bytes (ignored)

    # Create structured dtype
    dtype = np.dtype(dtype_list)

    # Decode entire chunk at once
    structured_array = np.frombuffer(chunk, dtype=dtype)

    # Apply stride by slicing (much faster than loop with modulo)
    strided_array = structured_array[::stride]

    # Convert to list of tuples (convert to float for consistency)
    rows = []
    for record in strided_array:
        row = tuple(float(record[f'ch{i}']) for i in range(len(channels)))
        rows.append(row)

    return rows


def _decode_rows_python(
    chunk: bytes, samples: int, channels: Sequence[Channel], stride: int
) -> List[Tuple[float, ...]]:
    """
    Pure Python fallback implementation (slower but no NumPy dependency).
    """
    record_len = len(chunk) // samples
    payload_len = sum(c.length for c in channels)
    padding = record_len - payload_len
    if padding < 0:
        raise ValueError("Chunk smaller than expected payload")

    rows: List[Tuple[float, ...]] = []
    offset = 0

    for i in range(samples):
        # Only decode if this row index is divisible by stride
        if i % stride == 0:
            values = []
            for channel in channels:
                end = offset + channel.length
                values.append(channel.decode(chunk[offset:end]))
                offset = end
            offset += padding
            rows.append(tuple(values))
        else:
            # Skip this row - just advance offset
            offset += record_len

    return rows


def parse_tst(path: Path, stride: int = 1) -> TSTFile:
    """
    Parse Bruker UMT .tst file with optional stride sampling.

    Args:
        path: Path to .tst file
        stride: Keep every Nth sample during decoding (default: 1 = all samples)

    Returns:
        TSTFile with parsed data
    """
    data = path.read_bytes()
    sections = data.split(SENTINEL)
    if not sections:
        raise ValueError("Unexpected file structure")
    header_meta, channels = _parse_channels(sections[0])
    runs: List[Dict[str, object]] = []
    steps: List[StepData] = []
    current_run: Optional[Dict[str, object]] = None
    pending_step: Optional[Dict[str, object]] = None
    pending_meta: Optional[Dict[str, object]] = None
    data_step_index = 0
    per_run_counts: Dict[int, int] = {}
    for block in sections[1:]:
        if not block:
            continue
        if b"\x00" in block:
            if not (pending_step and pending_meta and int(pending_step.get("IsData", 0))):
                continue
            samples = int(pending_meta.get("Samples", 0))
            duration_raw = float(pending_meta.get("Duration", 0))
            duration_seconds = duration_raw / 10000.0
            rows = _decode_rows(block, samples, channels, stride)
            data_step_index += 1
            run_no = int((current_run or {}).get("Run", 1))
            per_run_counts[run_no] = per_run_counts.get(run_no, 0) + 1
            step_obj = StepData(
                run_no=run_no,
                test_no=int(pending_step.get("Test", 0)),
                global_index=data_step_index,
                raw_step_no=int(pending_step.get("Step", data_step_index)),
                run_step_index=per_run_counts[run_no],
                metadata=dict(pending_meta),
                descriptor=dict(pending_step),
                samples=samples,
                duration_seconds=duration_seconds,
                start_label=str(pending_meta.get("Started at", "")),
                rows=rows,
            )
            steps.append(step_obj)
            pending_step = None
            pending_meta = None
            continue
        parsed = _parse_block(block)
        if "Run" in parsed and len(parsed) == 1:
            current_run = {"Run": parsed["Run"], "meta": {}}
            runs.append(current_run)
            continue
        if {"Test", "Step", "IsData"}.issubset(parsed.keys()):
            pending_step = parsed
            pending_meta = None
            continue
        if pending_step and pending_meta is None:
            pending_meta = parsed
            continue
        if current_run is None:
            current_run = {"Run": 1, "meta": {}}
            runs.append(current_run)
        current_run["meta"].update(parsed)
    return TSTFile(path=path, header_meta=header_meta, channels=channels, runs=runs, steps=steps)


def _display_name(name: str) -> str:
    mapping = {"Z1": "Z", "Z2": "Y"}
    return mapping.get(name.strip(), name.strip())


def _format_float(value: float, width: int = 12, decimals: int = 4) -> str:
    return f"{value:{width}.{decimals}f}"


def _write_txt_from_tst(tst: TSTFile, output_path: Path, stride: int = 1) -> None:
    """Convert TST file to TXT format (intermediate conversion)."""
    header = tst.header_meta
    steps_by_run: Dict[int, List[StepData]] = {}
    for step in tst.steps:
        steps_by_run.setdefault(step.run_no, []).append(step)
    total_runs = len(steps_by_run) or len(tst.runs) or int(header.get("Runs", 1)) or 1
    total_steps = len(tst.steps)
    umt_version = f"{header.get('UMT verHigh', '')}.{header.get('UMT verLow', '')}.{header.get('UMT Build', '')}".strip(".")
    viewer_line = "Created by tribolab_method (TST converter)"
    umt_date = header.get("DateTime", "")
    if not umt_date and tst.runs:
        umt_date = tst.runs[0].get("meta", {}).get("DateTime", "")
    umt_line = f"Created by Bruker UMT ver.{umt_version} {umt_date}".strip()
    tip_id = header.get("TipID", "")
    run_meta_map = {int(run.get("Run", idx + 1)): run.get("meta", {}) for idx, run in enumerate(tst.runs)}
    with output_path.open("w", encoding="ascii") as fh:
        fh.write(f"{viewer_line}\n")
        fh.write(f"{umt_line}\n")
        fh.write(f"Total number of runs - {total_runs}\n")
        fh.write(f"Total number of steps = {total_steps}\n")
        fh.write(f"Indenter tip ID: {tip_id}\n")
        fh.write(f"{tst.path}\n\n")
        for run_no in sorted(steps_by_run) or [1]:
            run_steps = steps_by_run.get(run_no, [])
            fh.write(f"Run # {run_no}\n")
            run_meta = run_meta_map.get(run_no, {})
            script_file = run_meta.get("ScriptFile", "")
            run_date = run_meta.get("DateTime", header.get("DateTime", ""))
            fh.write(f"Script file {script_file}\n")
            fh.write(f"Run date {run_date}\n")
            for step in run_steps:
                fh.write(f"Step No. {step.run_step_index}\n\n")
                radius = step.metadata.get("Radius", "")
                velocity = step.metadata.get("Velocity", "")
                force = step.metadata.get("Force", "")
                fh.write(f"\tStep Type Code: {step.descriptor.get('StepType', 0)}\n")
                fh.write(f"\tRadius       = {radius}\n")
                fh.write(f"\tVelocity     = {velocity}\n")
                fh.write(f"\tSet Force    = {force}\n")
                fh.write(f"\tDuration     = {step.duration_seconds:.2f}\n")
                fh.write(f"\tData Count   = {step.samples}\n")
                fh.write(f"\tStarted at: {step.start_label}\n\n")
                fx_index = next((i for i, c in enumerate(tst.channels) if c.name.strip() == "Fx"), None)
                fz_index = next((i for i, c in enumerate(tst.channels) if c.name.strip() == "Fz"), None)
                column_defs = [("T", "sec")]
                for ch in tst.channels:
                    column_defs.append((_display_name(ch.name), ch.unit.strip()))
                if fx_index is not None:
                    column_defs.append(("Ff", "N"))
                if fx_index is not None and fz_index is not None:
                    column_defs.append(("COF", ""))
                header_line = "".join(f"{name:>12}" for name, _ in column_defs)
                unit_line = "".join(f"{unit:>12}" for _, unit in column_defs)
                fh.write(f"{header_line}\n")
                fh.write(f"{unit_line}\n\n")
                step_stride = max(1, stride)
                dt = step.duration_seconds / max(step.samples - 1, 1)
                for row_idx, row in enumerate(step.rows):
                    if row_idx % step_stride != 0:
                        continue
                    cells: List[str] = [_format_float(row_idx * dt)]
                    for value in row:
                        cells.append(_format_float(value))
                    if fx_index is not None:
                        fx_value = row[fx_index]
                        cells.append(_format_float(abs(fx_value)))
                    if fx_index is not None and fz_index is not None:
                        fz_value = row[fz_index]
                        cof = abs(fx_value) / fz_value if fz_value else 0.0
                        cells.append(_format_float(cof))
                    fh.write("".join(cells) + "\n")
                fh.write("\n")


# ===== Parameter Dialog =====

class TribolabParametersDialog(QDialog):
    """Dialog for configuring Tribolab processing parameters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tribolab Processing Parameters")
        self.setModal(True)
        self.resize(500, 300)

        # Default values
        self.defaults = {
            "start_time": 0.03,
            "first_interval": 1.03,
            "regular_interval": 2.06,
            "window_size": 2.0,
            "window_offset": 0.75,
            "stride": 15
        }

        self.params = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Configure time-window averaging parameters:")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title_label)

        # Parameters form
        form_layout = QFormLayout()

        param_labels = {
            "start_time": "Start Time (seconds):",
            "first_interval": "First Interval (seconds):",
            "regular_interval": "Regular Interval (seconds):",
            "window_size": "Window Size (seconds):",
            "window_offset": "Window Offset (seconds):",
            "stride": "Stride for .tst files (1 point every X):"
        }

        for param, label_text in param_labels.items():
            line_edit = QLineEdit(str(self.defaults[param]))
            self.params[param] = line_edit
            form_layout.addRow(label_text, line_edit)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def _reset_to_defaults(self):
        for param, default_val in self.defaults.items():
            self.params[param].setText(str(default_val))

    def _validate_and_accept(self):
        """Validate input and accept if valid."""
        try:
            parsed = self.get_parameters()
            # Validate positive values (except window_offset can be negative)
            for param, value in parsed.items():
                if param == "stride":
                    # Stride must be positive integer
                    if value <= 0 or value != int(value):
                        raise ValueError(f"stride must be a positive integer (got {value})")
                elif param != "window_offset" and value <= 0:
                    raise ValueError(f"{param} must be positive")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Invalid parameter value:\n{str(e)}")

    def get_parameters(self) -> Dict[str, float]:
        """Return parsed parameters (stride will be int, others float)."""
        result = {}
        for param, line_edit in self.params.items():
            value = float(line_edit.text())
            # Convert stride to integer
            if param == "stride":
                result[param] = int(value)
            else:
                result[param] = value
        return result


# ===== Averaging Functions =====

def _average_data_windows(
    data_rows: List[List[float]],
    column_names: List[str],
    params: Dict[str, float],
    use_polars: bool = True
) -> List[List[float]]:
    """
    Perform time-window averaging on data rows.

    Fallback chain: Polars (fastest) → NumPy (fast) → Pure Python (baseline)

    Args:
        data_rows: List of data rows [Time, Fx, Fz, ...]
        column_names: Column names (first is Time)
        params: Processing parameters (start_time, first_interval, etc.)
        use_polars: Use Polars for high-performance operations if available

    Returns:
        List of averaged rows
    """
    if not data_rows:
        return []

    # Extract parameters
    start_time = params["start_time"]
    first_interval = params["first_interval"]
    regular_interval = params["regular_interval"]
    window_size = params["window_size"]
    window_offset = params["window_offset"]

    window_radius = window_size / 2
    max_time = max(row[0] for row in data_rows)

    # Generate time points
    time_points = [start_time]
    time_points.append(start_time + first_interval)
    current_time = time_points[-1]
    while current_time < max_time - regular_interval:
        current_time += regular_interval
        time_points.append(round(current_time, 4))

    # Fallback chain: Polars → NumPy → Python
    if use_polars and HAS_POLARS:
        return _average_with_polars(data_rows, column_names, time_points, window_radius, window_offset)
    elif HAS_NUMPY:
        return _average_with_numpy(data_rows, time_points, window_radius, window_offset)
    else:
        return _average_with_python(data_rows, time_points, window_radius, window_offset)


def _average_with_polars(
    data_rows: List[List[float]],
    column_names: List[str],
    time_points: List[float],
    window_radius: float,
    window_offset: float
) -> List[List[float]]:
    """
    High-performance averaging using Polars DataFrame operations.

    Expected speedup: 10-50x over NumPy on large datasets due to:
    - Rust-based implementation with SIMD
    - Query optimizer
    - Multi-threaded execution
    - Columnar data format (Apache Arrow)

    Args:
        data_rows: List of data rows [Time, Fx, Fz, ...]
        column_names: Column names (first must be "Time")
        time_points: Center times for averaging windows
        window_radius: Half-width of averaging window
        window_offset: Offset to shift window centers

    Returns:
        List of averaged rows with exact center times
    """
    if not data_rows:
        return []

    # Convert to Polars DataFrame
    df = pl.DataFrame(data_rows, schema=column_names, orient="row")

    # Ensure sorted by time (required for efficient filtering)
    df = df.sort("Time")

    result_rows = []

    for center_time in time_points:
        # Calculate window bounds
        window_start = max(0, center_time - window_radius + window_offset)
        window_end = center_time + window_radius + window_offset

        # Filter to window using Polars expressions (lazy evaluation + optimized)
        window_df = df.filter(
            (pl.col("Time") >= window_start) & (pl.col("Time") < window_end)
        )

        if window_df.height > 0:  # If rows exist in window
            # Compute mean across all columns (vectorized in Rust)
            avg_dict = window_df.mean().to_dicts()[0]

            # Override time with exact center time
            avg_dict["Time"] = center_time

            # Convert dict to list in correct column order
            avg_row = [avg_dict[col] for col in column_names]
            result_rows.append(avg_row)

    return result_rows


def _average_with_numpy(
    data_rows: List[List[float]],
    time_points: List[float],
    window_radius: float,
    window_offset: float
) -> List[List[float]]:
    """
    Vectorized averaging using NumPy with binary search optimization.

    Uses np.searchsorted for O(log n) window bounds lookup instead of O(n) boolean masking.
    """
    # Convert to NumPy array for vectorized operations
    data_array = np.array(data_rows)
    time_col = data_array[:, 0]

    result_rows = []

    for center_time in time_points:
        # Calculate window bounds
        window_start = max(0, center_time - window_radius + window_offset)
        window_end = center_time + window_radius + window_offset

        # Binary search for window boundaries (O(log n) vs O(n) for boolean mask)
        start_idx = np.searchsorted(time_col, window_start, side='left')
        end_idx = np.searchsorted(time_col, window_end, side='left')

        if end_idx > start_idx:
            # Slice array directly (faster than boolean indexing)
            window_data = data_array[start_idx:end_idx]
            # Vectorized mean across all columns
            avg_row = np.mean(window_data, axis=0).tolist()
            # Override time with exact center time
            avg_row[0] = center_time
            result_rows.append(avg_row)

    return result_rows


def _average_with_python(
    data_rows: List[List[float]],
    time_points: List[float],
    window_radius: float,
    window_offset: float
) -> List[List[float]]:
    """Fallback averaging using pure Python (slower)."""
    result_rows = []

    for center_time in time_points:
        window_start = max(0, center_time - window_radius + window_offset)
        window_end = center_time + window_radius + window_offset

        # Select rows within window
        window_rows = [row for row in data_rows if window_start <= row[0] < window_end]

        if window_rows:
            # Calculate average for each column
            num_cols = len(window_rows[0])
            avg_row = []
            for col_idx in range(num_cols):
                col_sum = sum(row[col_idx] for row in window_rows)
                avg_row.append(col_sum / len(window_rows))

            # Override time with exact center time
            avg_row[0] = center_time
            result_rows.append(avg_row)

    return result_rows


class TribolabMethod(MethodProtocol):
    """
    Tribolab oscillation data processor.

    Reads raw tribometer data files (.txt, .csv, .tst) and generates summary CSV files
    with time-window averaged data points at user-configurable intervals.
    """

    def get_name(self) -> str:
        """Return method display name."""
        return "Tribolab Oscillation"

    def get_processes(self) -> List[ProcessInfo]:
        """Return list of available processes."""
        return [
            ProcessInfo(
                name="Oscillation",
                description="Time-window averaging of tribometer oscillation data. Supports .txt, .csv, and .tst (Bruker UMT) formats.",
                file_extensions=[".txt", ".csv", ".tst"]
            )
        ]

    def process_folder(
        self,
        input_folder: str,
        selected_processes: List[str],
        callbacks: Optional[ProcessCallbacks] = None,
        params: Optional[Dict[str, float]] = None
    ) -> Dict[str, List[ProcessResult]]:
        """
        Process all .txt, .csv, and .tst files in the input folder.

        Args:
            input_folder: Path to folder containing Tribolab data files
            selected_processes: List of process names (should contain "Oscillation")
            callbacks: Optional callbacks for progress reporting
            params: Optional processing parameters. If None, will show dialog (not thread-safe!)

        Returns:
            Dictionary mapping "Oscillation" to list of ProcessResult objects
        """
        # Validate input folder
        if not os.path.exists(input_folder):
            raise FileNotFoundError(f"Input folder not found: {input_folder}")

        # Validate selected processes
        valid_processes = {p.name for p in self.get_processes()}
        for proc in selected_processes:
            if proc not in valid_processes:
                raise ValueError(f"Unknown process: {proc}")

        # Initialize results
        results = {process: [] for process in selected_processes}

        # Only process if "Oscillation" is selected
        if "Oscillation" not in selected_processes:
            return results

        # Get parameters (either from argument or show dialog)
        if params is None:
            # Show parameter dialog (should only happen if called from non-GUI context)
            # WARNING: This will fail if called from worker thread!
            dialog = TribolabParametersDialog()
            if dialog.exec_() != QDialog.Accepted:
                # User cancelled - raise exception
                raise ValueError("Processing cancelled by user")
            params = dialog.get_parameters()

        # Find all supported files
        files = [
            f for f in os.listdir(input_folder)
            if f.endswith(('.txt', '.csv', '.tst')) and os.path.isfile(os.path.join(input_folder, f))
        ]

        total_files = len(files)

        if callbacks and callbacks.on_log:
            callbacks.on_log(f"Found {total_files} file(s) to process")

        # Process each file
        for idx, filename in enumerate(files, start=1):
            filepath = os.path.join(input_folder, filename)

            if callbacks and callbacks.on_file_start:
                callbacks.on_file_start(filename)

            if callbacks and callbacks.on_progress:
                callbacks.on_progress(idx, total_files)

            # Process the file
            try:
                output_path = self._process_file_with_params(filepath, params)
                result = ProcessResult(
                    input_file=filepath,
                    success=True,
                    output_file=output_path
                )
            except Exception as e:
                result = ProcessResult(
                    input_file=filepath,
                    success=False,
                    error_message=str(e)
                )

            results["Oscillation"].append(result)

            if callbacks and callbacks.on_file_complete:
                callbacks.on_file_complete(result)

        return results

    def _process_file_with_params(self, file_path: str, params: Dict[str, float]) -> str:
        """
        Process a file (either .txt, .csv, or .tst) with given parameters.

        Args:
            file_path: Path to input file
            params: Dictionary of processing parameters

        Returns:
            Path to output file (_s.csv)
        """
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == '.tst':
            # Convert .tst to temporary .txt, then process
            return self._process_tst_file(file_path, params)
        else:
            # Process .txt or .csv directly
            return self._transform_file(file_path, params)

    def _process_tst_file(self, tst_path: str, params: Dict[str, float]) -> str:
        """
        Process a .tst file directly without intermediate .txt file (OPTIMIZED).

        Args:
            tst_path: Path to .tst file
            params: Processing parameters (includes 'stride' for sampling)

        Returns:
            Path to final _s.csv file
        """
        try:
            # Extract stride from params
            stride = int(params.get("stride", 1))

            # Step 1: Parse .tst file with stride (only decodes every Nth sample)
            tst_file = parse_tst(Path(tst_path), stride=stride)

            # Step 2: Extract data from first step (simplified - take first step only)
            if not tst_file.steps:
                raise ValueError("No data steps found in TST file")

            step = tst_file.steps[0]  # Process first step

            # Step 3: Convert StepData rows to data_rows format (OPTIMIZED - vectorized)
            # Calculate time column from duration and ORIGINAL sample count (before stride)
            dt = step.duration_seconds / max(step.samples - 1, 1)

            # Find Fx and Fz indices for derived columns (Ff and COF)
            fx_index = next((i for i, c in enumerate(tst_file.channels) if c.name.strip() == "Fx"), None)
            fz_index = next((i for i, c in enumerate(tst_file.channels) if c.name.strip() == "Fz"), None)

            # Use Polars for high-performance construction if available
            if HAS_POLARS:
                # Build channel names
                channel_names = [_display_name(ch.name) for ch in tst_file.channels]

                # Create DataFrame from rows (Polars optimized constructor)
                df = pl.DataFrame(step.rows, schema=channel_names, orient="row")

                # Add Time column (vectorized in Rust)
                num_rows = len(step.rows)
                df = df.with_row_count("row_idx").with_columns(
                    (pl.col("row_idx") * dt * stride).alias("Time")
                ).select(["Time"] + channel_names)

                # Add derived columns using Polars expressions
                if fx_index is not None:
                    # Ff = abs(Fx)
                    fx_col_name = channel_names[fx_index]
                    df = df.with_columns(
                        pl.col(fx_col_name).abs().alias("Ff")
                    )

                if fx_index is not None and fz_index is not None:
                    # COF = |Fx| / Fz (with null handling for division by zero)
                    fx_col_name = channel_names[fx_index]
                    fz_col_name = channel_names[fz_index]
                    df = df.with_columns(
                        (pl.col(fx_col_name).abs() / pl.col(fz_col_name)).fill_null(0.0).alias("COF")
                    )

                # Convert to list of lists for compatibility with averaging function
                data_rows = df.rows()

            # Fallback to NumPy if Polars unavailable
            elif HAS_NUMPY:
                # Convert rows to NumPy array directly (avoiding list intermediate)
                num_rows = len(step.rows)
                num_base_cols = len(tst_file.channels)
                num_derived_cols = (1 if fx_index is not None else 0) + \
                                  (1 if fx_index is not None and fz_index is not None else 0)
                total_cols = 1 + num_base_cols + num_derived_cols  # Time + channels + derived

                # Pre-allocate full array
                data_array = np.empty((num_rows, total_cols), dtype=np.float64)

                # Time column (vectorized)
                data_array[:, 0] = np.arange(num_rows) * dt * stride

                # Channel columns (convert all tuples to array in one operation - FAST)
                # Convert list of tuples to 2D array directly
                channels_array = np.array(step.rows, dtype=np.float64)
                data_array[:, 1:1+num_base_cols] = channels_array

                # Derived columns (vectorized)
                col_offset = 1 + num_base_cols
                if fx_index is not None:
                    # Ff = abs(Fx)
                    data_array[:, col_offset] = np.abs(data_array[:, 1 + fx_index])
                    col_offset += 1

                if fx_index is not None and fz_index is not None:
                    # COF = |Fx| / Fz (with division by zero protection)
                    fx_col = data_array[:, 1 + fx_index]
                    fz_col = data_array[:, 1 + fz_index]
                    data_array[:, col_offset] = np.divide(
                        np.abs(fx_col),
                        fz_col,
                        out=np.zeros_like(fx_col),
                        where=fz_col != 0
                    )

                # Convert to list of lists for compatibility with averaging function
                data_rows = data_array.tolist()

            # Fallback to pure Python
            else:
                data_rows = []
                for row_idx, row in enumerate(step.rows):
                    time_val = row_idx * dt * stride
                    data_row = [time_val] + list(row)

                    if fx_index is not None:
                        fx_value = row[fx_index]
                        ff_value = abs(fx_value)
                        data_row.append(ff_value)

                    if fx_index is not None and fz_index is not None:
                        fz_value = row[fz_index]
                        cof_value = abs(fx_value) / fz_value if fz_value != 0 else 0.0
                        data_row.append(cof_value)

                    data_rows.append(data_row)

            # Column names from channels + derived columns
            column_names = ["Time"] + [_display_name(ch.name) for ch in tst_file.channels]
            if fx_index is not None:
                column_names.append("Ff")
            if fx_index is not None and fz_index is not None:
                column_names.append("COF")

            # Step 4: Apply averaging directly (Polars → NumPy → Python fallback)
            result_rows = _average_data_windows(data_rows, column_names, params, use_polars=True)

            # Step 5: Build metadata column (empty for now - simplified)
            metadata_column = [""] * len(result_rows)

            # Step 6: Write CSV output
            base, _ = os.path.splitext(tst_path)
            output_csv_path = f"{base}.csv"

            with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')

                # Write header
                header = column_names + ["METADATA"]
                writer.writerow(header)

                # Write data rows
                for idx, row in enumerate(result_rows):
                    # Format numbers with comma as decimal separator
                    formatted_row = [self._format_number(val) for val in row]
                    formatted_row.append(metadata_column[idx])
                    writer.writerow(formatted_row)

            return output_csv_path

        except Exception as e:
            raise Exception(f"Error processing TST file: {str(e)}")

    def _transform_file(self, file_path: str, params: Dict[str, float]) -> str:
        """
        Transform a single Tribolab data file.

        Reads raw data, performs time-window averaging, and outputs summary CSV.

        Args:
            file_path: Path to input file
            params: Dictionary with keys: start_time, first_interval, regular_interval, window_size, window_offset

        Returns:
            Path to output file (original_name_s.csv)

        Raises:
            Exception: If file processing fails
        """
        try:
            # Extract parameters
            start_time = params["start_time"]
            first_interval = params["first_interval"]
            regular_interval = params["regular_interval"]
            window_size = params["window_size"]
            window_offset = params["window_offset"]

            # Step 1: Extract metadata and data
            metadata_lines = []
            data_lines = []
            columns_line = None

            with open(file_path, "r") as f:
                lines = f.readlines()

                # Find data section start
                data_section_started = False
                for line in lines:
                    line_stripped = line.strip()

                    # Check if this is a column header line
                    if re.search(r'\bT\b', line_stripped) and "Fx" in line_stripped and "Fz" in line_stripped:
                        columns_line = line_stripped
                        metadata_lines.append(line_stripped)
                        data_section_started = True
                        continue

                    # Skip empty lines or unit lines
                    if data_section_started and (len(line_stripped) == 0 or line_stripped.startswith('sec')):
                        continue

                    # Process data lines
                    if data_section_started:
                        # Look for lines that start with digits
                        if re.match(r'^\s*\d', line_stripped):
                            data_lines.append(line_stripped)
                        else:
                            metadata_lines.append(line_stripped)
                    else:
                        metadata_lines.append(line_stripped)

            if not data_lines:
                raise ValueError(f"No data found in file")

            # Step 2: Parse the fixed-width data
            data_rows = []
            for line in data_lines:
                # Extract numeric values
                values = re.findall(r'-?\d+\.\d+', line)
                if len(values) >= 8:  # Need at least 8 columns
                    try:
                        row = [float(val) for val in values[:8]]
                        data_rows.append(row)
                    except ValueError:
                        # Skip lines that can't be parsed
                        pass

            if not data_rows:
                raise ValueError("No valid data rows parsed")

            # Determine column names
            if columns_line:
                column_names = re.findall(r'\b[A-Za-z0-9]+\b', columns_line)
                # Ensure T is renamed to Time
                column_names = ["Time" if col == "T" else col for col in column_names]
            else:
                column_names = ["Time", "Fx", "Fz", "Z", "Y", "V2", "Ff", "COF"]

            column_names = column_names[:8]  # Keep only first 8

            # Step 3: Define exact time points based on parameters
            window_radius = window_size / 2

            # Find max time (first column is Time)
            max_time = max(row[0] for row in data_rows)

            # Generate the exact time points
            time_points = [start_time]
            time_points.append(start_time + first_interval)

            # Add subsequent points with regular interval
            current_time = time_points[-1]
            while current_time < max_time - regular_interval:
                current_time += regular_interval
                time_points.append(round(current_time, 4))

            # Step 4: Create summary data using these time points
            result_rows = []

            for center_time in time_points:
                # Calculate window bounds with specified offset
                window_start = max(0, center_time - window_radius + window_offset)
                window_end = center_time + window_radius + window_offset

                # Select rows within the window
                window_rows = [row for row in data_rows if window_start <= row[0] < window_end]

                if window_rows:
                    # Calculate average for each column
                    num_cols = len(window_rows[0])
                    avg_row = []
                    for col_idx in range(num_cols):
                        col_sum = sum(row[col_idx] for row in window_rows)
                        avg_row.append(col_sum / len(window_rows))

                    # Set Time to exact center time
                    avg_row[0] = center_time
                    result_rows.append(avg_row)

            # Step 5: Prepare metadata column
            # Pad or truncate metadata to match result rows
            metadata_length = len(metadata_lines)
            summary_length = len(result_rows)

            if metadata_length >= summary_length:
                metadata_column = metadata_lines[:summary_length]
            else:
                metadata_column = metadata_lines + [None] * (summary_length - metadata_length)

            # Step 6: Build output path
            base, ext = os.path.splitext(file_path)
            new_path = f"{base}.csv"

            # Step 7: Write CSV with semicolon delimiter and European decimal format
            with open(new_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')

                # Write header
                header = column_names + ["METADATA"]
                writer.writerow(header)

                # Write data rows
                for idx, row in enumerate(result_rows):
                    # Format numbers with comma as decimal separator
                    formatted_row = [self._format_number(val) for val in row]
                    # Add metadata
                    formatted_row.append(metadata_column[idx] if metadata_column[idx] is not None else "")
                    writer.writerow(formatted_row)

            return new_path

        except Exception as e:
            raise Exception(f"Error transforming {os.path.basename(file_path)}: {str(e)}")

    def _format_number(self, value: float) -> str:
        """
        Format a number with European decimal notation (comma).

        Args:
            value: Float value to format

        Returns:
            String with comma as decimal separator (4 decimal places)
        """
        return f"{value:.4f}".replace('.', ',')
