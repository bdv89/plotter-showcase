# TODO

## Known issues

- **Axis tick labels after rapid style edits**: when several figure settings change in quick
  succession (e.g. typing a title), Plotly can fall back to its default axis range (−1…6) for
  the tick labels while the curves stay correct. The labels come back as soon as the traces are
  recomputed (any data change). To fix in `PlotView.tsx`.
- **Axis unit suffix overlaps the axis title**: the *Unit* field adds a suffix to every tick
  label, but the plot margin does not account for its width. Workaround: put the unit in the
  axis title, e.g. `Internal stress (MPa)`.
- **Statistics table inside the figure**: the two-level header is misaligned and the last row
  can be clipped at the bottom of the figure. The statistics shown in the Extract tab are
  correct.

## Done
- [x] **Statistics table OFF by default** (Plot tab) — `DEFAULT_STATS.visible = false` in
  `appStore.ts`: it is a figure ornament and must not appear on the plot as soon as a value is
  extracted. The On/Off chip in `StatsBar` turns it on; a pool keeps its own setting.
- [x] **Legend colour in the Extract tab** — a `.legend-dot` marker at the start of each row in
  both Values **and** Populations, to link a row of numbers to a curve. A population only shows
  its marker if all its members share the same colour (without "Group by", the checked files
  form a single multicoloured population). Frontend only, deployed to production on 2026-08-19.
- [x] **Metrics tab** — connection tracking (IPs + hits per endpoint + daily activity), modelled
  on picture_to_CAS. Backend: middleware + `core/metrics.py` + `api/metrics.py` (SQLite
  `METRICS_DB`). Frontend: `MetricsView.tsx`. ⚠️ Requires a `Restart-Service CSVPlotter` (admin)
  to load the backend in production.
