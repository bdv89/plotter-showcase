"""Response-time benchmark of a running Plotter backend (dev or prod), for the README figures.

    python tools/benchmark.py [API_URL] [ROWS]      # default http://127.0.0.1:9299/api 200000

Uploads one synthetic signal (ROWS rows) in a dedicated session, then times the main calls
(median of several runs). Memory and idle CPU are read on the server with the OS tools
(Task Manager / Get-Process): this script only measures what a user waits for.
The benchmark session is deleted at the end.
"""

import statistics
import sys
import time

import httpx
import numpy as np

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9299/api"
ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 200_000


def median_time(call, runs=5) -> float:
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        call().raise_for_status()
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def main():
    client = httpx.Client(timeout=300, headers={"X-Session-Id": f"benchmark-{int(time.time())}"})
    t = np.linspace(0, 3600, ROWS)
    y = np.sin(t / 50) + np.random.default_rng(0).normal(0, 0.1, ROWS)
    csv = ("t (s),U (V)\n" + "\n".join(f"{a:.4f},{b:.5f}" for a, b in zip(t, y))).encode()

    t0 = time.perf_counter()
    res = client.post(f"{API}/upload", files={"files": ("benchmark.csv", csv, "text/csv")})
    res.raise_for_status()
    upload = time.perf_counter() - t0
    fid = res.json()[0]["file_id"]

    plot = {"file_ids": [fid], "x_column": "t (s)", "y_columns": ["U (V)"], "y2_columns": []}
    denoise = dict(plot, processing={"denoise_enabled": True, "denoise_method": "savgol",
                                     "denoise_window": 11, "denoise_polyorder": 3})
    rows = [
        ("Upload + parse", upload),
        ("Plot (raw)", median_time(lambda: client.post(f"{API}/plot-data", json=plot))),
        ("Plot (Savitzky-Golay, cached)", median_time(lambda: client.post(f"{API}/plot-data", json=denoise))),
        ("Extract (max)", median_time(lambda: client.post(
            f"{API}/extract", json={"file_id": fid, "column": "U (V)", "operation": "Max"}))),
    ]
    client.delete(f"{API}/reset")

    print(f"Synthetic file: {ROWS:,} rows, {len(csv) / 1e6:.1f} MB - {API}\n")
    print("| Operation | Time |\n|---|---|")
    for name, seconds in rows:
        print(f"| {name} | {seconds * 1000:.0f} ms |")


if __name__ == "__main__":
    main()
