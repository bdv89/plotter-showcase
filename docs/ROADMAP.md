# Roadmap

What exists today is described in the [README](../README.md). The items below are the steps
envisaged to turn Plotter into the analysis stage of a closed-loop, AI-assisted experimentation
pipeline (see [RAISE_alignment.md](RAISE_alignment.md)).

## ONGOING — Experimental metadata in a standard format

Attach the experimental context (sample, process parameters, instrument, operator, software
version, processing applied) to every file and session, as **JSON-LD following RO-Crate**,
with column units described by Frictionless Table Schema / CSVW and domain terms aligned with
EMMO. Details and status: [SHOWCASE.md § ONGOING](SHOWCASE.md#ongoing--experimental-metadata-in-a-standard-format).

## Data
- **Pivot data model** shared with partner labs, converting heterogeneous instrument outputs
  into a single documented structure.
- **Columnar export** (Apache Parquet) alongside SQLite pools, for large datasets and
  cross-lab analysis.

## Closing the loop

- **Live ingestion**: watch an acquisition folder (or a synchronised one) and update curves and
  metrics while the experiment runs.
- **Decision interface**: expose the extracted metrics and population statistics in a form a
  planning agent can consume directly (objective values and uncertainties).
- **Cost-aware planning hooks**: record duration, bath usage and manual interventions per run,
  so that resource optimisation can be part of the objective.

## Trust & safety

- **Authentication and authorisation** on the MCP endpoint (currently LAN-only, unauthenticated).
- **Audit log** of every agent action, linked to the resulting pool.
- **Human approval step** before any agent-proposed experiment reaches an instrument.

## Integration

- Connection to Materia Nova's PEO bench, electroplating and electroless lines, and to the
  SO-101 robotic sample-preparation cells.
- Deployment recipe that does not depend on Windows services (container image).

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
