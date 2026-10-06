# Plotter — open, AI-drivable analysis layer for laboratory data

**Plotter** turns raw instrument exports into processed curves, extracted metrics and
population statistics — from a web browser for the scientist, **or from an AI agent**
through a built-in [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server.

It is developed at **Materia Nova** (surface treatment & coatings R&D) as one building block
of a broader effort to retrofit existing laboratory equipment with open, vendor-neutral
software, so that experiments can be executed, recorded, analysed and archived in a single,
reproducible loop — and, ultimately, planned and steered by AI with a human in the loop.

> **Horizon Europe context** — this repository is part of Materia Nova's showcase for
> *HORIZON-RAISE-2027-01-01 — Automated Scientific Discovery (RAISE pilot)*.
> See **[docs/RAISE_alignment.md](docs/RAISE_alignment.md)** for how it maps onto the call
> and **[docs/ROADMAP.md](docs/ROADMAP.md)** for what comes next.

![Internal stress of Ni-P deposits, one colour per bath pH (synthetic demo data)](docs/screenshots/02-plot.png)

**→ [Plotter in pictures](docs/SHOWCASE.md)**: a guided tour with screenshots, why one central
tool keeps figures and statistics uniform across a lab, and the ongoing work on standard
experimental metadata (JSON-LD / RO-Crate).

## Highlights

- **Live folder watch**: point Plotter at the folder an instrument writes into. New files are
  loaded and plotted as they arrive, a file still being written is redrawn live, and the saved
  extractions are replayed, so population statistics update during the experiment.
- **One central tool for the whole lab**: nothing to install, one shared publication style,
  the same processing and statistics for everyone, and sessions that reopen identically.
- **Lightweight server**: about 240 MB of RAM and no CPU at rest. A 200,000-point signal is
  plotted in about 50 ms. It runs on an ordinary lab PC, with no GPU and no cloud
  ([figures below](#lightweight-by-design)).
- **AI-ready**: an AI agent can drive every analysis step through MCP, on the same code path
  as the user interface.

## What it does

| Step | Capability | Where |
|------|-----------|-------|
| **Ingest** | CSV / TSV with automatic delimiter, header and units-line detection; Excel (`.xlsx`, `.xls`). Works with heterogeneous instrument exports (potentiostat, tribometer, UV-vis, XRD…) without per-instrument code. | `web/backend/core/data_loader.py` |
| **Watch** | Follows a folder of the shared drive: new files are loaded and checked, growing files are reloaded in place (incomplete last line ignored), and extraction recipes are replayed on every change. | `web/backend/api/watch.py`, `web/frontend/src/components/FolderWatch.tsx` |
| **Process** | Smoothing, outlier removal, denoising (Savitzky-Golay, median, wavelet, FFT low-pass), baseline correction (SNIP, AsLS, arPLS, masked polynomial, auto), normalisation. Applied on the read path, non-destructive. | `web/backend/core/processing.py`, `denoise_methods.py`, `baseline_correction.py` |
| **Analyse** | Per-file metric extraction (max, min, slope, value at X, Y at max X, conditional values…) and **population statistics** (n, mean, sample SD, CV %) grouped by filename tokens. | `web/backend/core/extraction.py`, `web/frontend/src/utils/stats.ts` |
| **Store & share** | Each analysis session is a self-contained, documented SQLite pool (`.db`): raw data, processing settings, extracted values and plot style — reopenable and shareable. | `web/backend/core/db_schema.py` |
| **Supervise** | Interactive Plotly UI with step-by-step tutorial, publication-grade SVG/PNG export, annotation layer. | `web/frontend/` |
| **Automate** | MCP server: an LLM agent can list, open, describe, plot, extract, compute statistics and save — using the **same code path** as the UI. | `web/backend/mcp_server.py` |

## Live: watch an acquisition folder

![Watching PEO_bench: live_run.csv is still being written and is redrawn every 2 s](docs/screenshots/07-folder-watch.png)

Click **Watch** in the header and choose a folder of the server's shared drive (`SHARE_PATH`).
This is the folder an acquisition PC writes into, directly or through a synchronisation tool
such as Syncthing. Every 2 seconds, Plotter does the following:

1. **New files** are loaded, checked and plotted with the current X/Y columns and style.
2. **Files that grew** keep their colour and legend and are redrawn with the new data. In a
   text file, the last line is ignored until it is complete, so a half-written row is never
   parsed.
3. **Extraction recipes** already defined in the Extract tab are replayed on every new or
   changed file, so the per-file values and the population statistics follow the experiment.

This is the same idea as the incremental analysis of Materia Nova's PEO oscilloscope software
(PEOscillo), generalised to any instrument that writes tabular files. Watching keeps running
whichever tab is shown, and **● folder** in the header stops it. The folder is polled rather
than relying on file-system events: events are unreliable on network shares, and a poll of an
unchanged folder takes about 2 ms.

## Lightweight by design

Measured on the development workstation (AMD Ryzen 9 9900X, Python 3.12, a single uvicorn
worker), with [`tools/benchmark.py`](tools/benchmark.py) on a synthetic 200,000-row file (3.6 MB):

| Measure | Value |
|---|---|
| Backend memory, one session with this file loaded | ≈ 240 MB |
| CPU at rest (20 s sample) | 0 s |
| Upload + parse | ≈ 0.75 s |
| Plot request, raw / with Savitzky-Golay denoising | ≈ 50 ms / ≈ 50 ms |
| Extraction (max) | ≈ 7 ms |
| Folder-watch poll, nothing changed | ≈ 2 ms |

Memory is bounded by design: at most 16 sessions are kept in RAM (least recently used are
evicted to disk), there is a 50-entry cache of processed curves per session, and the number of
concurrent heavy computations is capped. A lab therefore needs no dedicated hardware: the
production instance runs as a Windows service next to other lab tools. *Figures from the
production server are to be added.*

## AI-ready: the MCP interface

The backend mounts an MCP server at `/mcp` (streamable HTTP). Nothing needs to be installed on
the client side; e.g. with Claude Code:

```
claude mcp add --transport http plotter http://<server>/plotter/mcp
```

Exposed tools: `list_share`, `open_files`, `session`, `describe`, `plot` (returns an image and
a numeric summary), `extract`, `stats`, `save`.

Design principles relevant to trustworthy automation:

- **One code path** — MCP tools call the existing API route handlers; an agent cannot
  obtain a result the scientist could not reproduce in the UI.
- **Human-verifiable output** — the agent's work is saved as a pool `.db` that the scientist
  reopens in the browser to inspect every curve, setting and extracted value.
- **Controlled data entry** — the agent only sees files placed in a dedicated shared folder
  (`SHARE_PATH`), never the users' disks.
- The MCP endpoint is currently **unauthenticated** and meant for a trusted LAN
  (see [ROADMAP](docs/ROADMAP.md)).

## Quick start (dev)

```powershell
# Prerequisites (once)
cd web\frontend; npm install
cd ..\backend;  python -m venv venv_win; .\venv_win\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

# Run backend (9099) + Vite (5174) and open the browser
cd web
.\start-plotter.ps1
```

→ http://localhost:5174

To try it on the synthetic demo dataset, load the files of
[`examples/demo-data/`](examples/demo-data/) (regenerated by `python examples/make_demo_data.py`).

**Stack**: FastAPI (Python 3.12, pandas, NumPy, SciPy, PyWavelets) + React 19 / TypeScript /
Vite / Zustand / Plotly.js. Multi-tenant: one isolated state per browser session, persisted
as `<sid>.db`.

## Repository layout

```
web/backend/    FastAPI: api/ (routers), core/ (processing), models/ (schemas), main.py, mcp_server.py
web/frontend/   React/Vite: src/components, src/store (Zustand), src/api
web/deploy/     Deployment scripts (Windows service via NSSM, nginx sub-path, promotion dev→beta→prod)
tests/          Backend tests (pytest)
docs/           Technical notes, showcase (SHOWCASE.md, screenshots/); docs/legacy/ = archived desktop app
examples/       Synthetic demo dataset and its generator
tools/          Maintenance scripts (third-party licence inventory, benchmark)
```

A former PyQt5 desktop version is archived under the git tag `legacy-desktop-2026-06-21`.

## Tests & quality

```powershell
python -m pytest                       # backend, from repo root
cd web\frontend; npm test              # frontend (Vitest: store + statistics)
cd web\backend; ruff check .; black .  # lint/format (config in pyproject.toml)
cd web\frontend; npm run lint          # ESLint
```

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — architecture overview (FR)
- **[PITFALLS.md](PITFALLS.md)** — known pitfalls and their fixes (FR/EN)
- **[web/deploy/DEPLOY.md](web/deploy/DEPLOY.md)** — deployment (nginx, Windows services) (FR)
- **[docs/SHOWCASE.md](docs/SHOWCASE.md)** — guided tour with screenshots
- **[docs/](docs/)** — denoising, baseline correction, performance notes

## Releases

Semantic versioning (`vX.Y.Z`); source of truth is `FastAPI(version=...)` in
`web/backend/main.py`.

## License

Copyright 2025-2026 Materia Nova. Licensed under the **[Apache License 2.0](LICENSE)** — see
[NOTICE](NOTICE). Third-party dependencies keep their own (permissive) licenses: see
[THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES), regenerated by `tools/gen_third_party_licenses.py`.

## Contact

Materia Nova — <https://www.materianova.be>
