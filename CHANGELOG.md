# Changelog

All notable changes to Plotter. Versions follow [Semantic Versioning](https://semver.org/);
the version number lives in `web/backend/main.py` (`FastAPI(version=...)`) and
`web/frontend/package.json`. Each version deployed to production is a git tag `vX.Y.Z`.

## [0.3.0] — 2026-10-06

First tagged release. It covers everything since the move from the desktop application to the
web application (0.2.0, June 2026).

### Added
- **Folder watch**: follow a folder of the shared drive. New files are loaded and plotted,
  files that grow are redrawn live (an incomplete last line is ignored), and extraction recipes
  are replayed on every change (`api/watch.py`, `FolderWatch.tsx`).
- **MCP server** at `/mcp`: an AI agent can list, open, describe, plot, extract, compute
  statistics and save, through the same code path as the UI.
- **Extract tab** with per-population statistics (n, mean, sample SD, CV %, min, max,
  median), legend colours, adjustable decimals, and replayable extraction recipes
  (**Re-extract**).
- **Statistics table inside the figure**, exported with SVG/PNG (off by default).
- **Drawing layer** on the plot (rectangles, lines, arrows, text), and high-resolution SVG and
  PNG export.
- **Metrics tab**: connection tracking (hits per endpoint, unique IPs, daily activity).
- Step-by-step **tutorial** (Tuto button), keyboard shortcuts, help panel.
- Data tab redesign: two-column layout, shared Group by / Palette / Legend controls.
- Showcase documentation, synthetic demo dataset, screenshots, benchmark script, third-party
  licence inventory; Apache-2.0 licence.

### Changed
- Processing is applied inline on the read path (`core/processing.py`); `/api/process` removed.
- Deployment: services are stopped before `pip install`, dependencies are always synced, and a
  post-build check rejects inconsistent frontend builds.

### Fixed
- Blank page in production (Plotly bundle import) and API 404 after a build without
  `VITE_API_URL`.
- Session lock freeze on concurrent requests.
- Plot title editable again without the ghost subtitle; header usable on mobile; long plots
  scroll.

### Known issues
See [TODO.md](TODO.md).

## [0.2.0] — 2026-06-21

Web application (FastAPI + React) replacing the PyQt5 desktop application, which is archived
under the tag `legacy-desktop-2026-06-21`.
