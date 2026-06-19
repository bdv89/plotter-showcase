"""
tribolab_method.py

Method for processing Tribolab tribometer oscillation data.
Performs time-window averaging to generate summary datasets.
Supports both .txt and .tst (Bruker UMT) file formats.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csv
import re
import struct
import dataclasses
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Sequence

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
