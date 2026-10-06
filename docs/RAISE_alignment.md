# Alignment with HORIZON-RAISE-2027-01-01 — Automated Scientific Discovery

This page maps the call's expectations onto **what this repository already does** (with the
file that proves it) and **what is planned**. It deliberately separates the two: everything in
the *Today* column can be checked in the code.

Plotter is one component of Materia Nova's lab-retrofit approach: existing instruments are
kept, and are driven, read and analysed through vendor-neutral, open-source software instead
of closed vendor tools.

## Where Plotter sits in the closed loop

```
 plan ──► execute ──► acquire ──► process & analyse ──► decide ──► (next experiment)
  ▲        (instrument drivers,     (Plotter: ingest,      (AI agent via MCP,
  │         robotic cells — sibling  denoise, baseline,     human review in UI)
  │         Materia Nova projects)   extract, statistics)          │
  └───────────────────────────────────────────────────────────────┘
```

Plotter covers the **analyse** step and exposes it to an AI agent. It is the part of the loop
that turns raw instrument files into the numbers a decision layer needs.

## Mapping

| Call expectation | Today (in this repository) | Planned (project) |
|---|---|---|
| **Intelligence layer** that lets instrumentation plan, run and **analyse** experiments semi- or fully autonomously | An AI agent can already run the full analysis chain (open → describe → plot → extract → stats → save) through the MCP server — `web/backend/mcp_server.py` | Connect the analysis output to a planning agent (e.g. Bayesian optimisation / agentic planner from AI partners) to close the loop |
| **Retrofit** an existing lab without redesigning it | Vendor-agnostic ingestion of instrument exports (auto-detected delimiter, header and units line; European decimals) — `web/backend/core/data_loader.py`, `core/data_utils.py`. Already used on potentiostat, tribometer, UV-vis and XRD exports | Live ingestion from retrofitted benches (PEO, electroplating, electroless lines) |
| **Comprehensive data management**: collection, storage, processing, sharing | Each session is a self-contained, documented SQLite pool (raw data, processing settings, extracted values, plot style); inspectable with standard tools — `web/backend/core/db_schema.py` | Pivot data model shared with partner labs; columnar export (Apache Parquet) for large datasets; experiment metadata travelling with the data |
| **Efficient (near-)real-time processing and analysis** | Processing applied on the read path with a per-session cache, bounded CPU concurrency — `core/processing.py`, `state.py` | Streaming / live updates during acquisition |
| **Reproducibility** | Processing settings and extraction "recipes" are stored with the data and can be replayed on new files; non-destructive processing; tests — `tests/`, `web/frontend/src/**/*.test.ts` | Provenance metadata (instrument, operator, software version) in every pool |
| **Human oversight and interaction** | The agent's output is a pool the scientist reopens in the browser to inspect every curve, setting and value; agents cannot delete work (no reset tool) and see only a dedicated shared folder — `mcp_server.py` | Approval step before an agent-proposed experiment is executed |
| **Intuitive user interfaces** | React UI with a step-by-step tutorial, keyboard shortcuts, publication-grade figure export — `web/frontend/` | — |
| **Interoperability standards and protocols** | Open protocol for AI ↔ tool interaction (MCP, streamable HTTP); open formats (CSV, SQLite) | Common exchange format with partner labs |
| **Security and robustness by design** | Session isolation, file-type/size limits, UUID file IDs, same-origin deployment behind a reverse proxy — see `web/deploy/DEPLOY.md` | Authentication on the MCP endpoint, audit log of agent actions |
| **Transfer to other disciplines** | Nothing in the code is specific to surface treatment: any tabular instrument export works | Documented reuse cases outside materials science |
| **Priority on software development** | Fully open-source software stack (Python, React) | — |

## Materia Nova components outside this repository

These belong to the same retrofit approach and are maintained separately:

- **PEO bench control** (plasma electrolytic oxidation): runs, tags, processes, analyses and
  archives an experiment in a single run, with live plotting of voltage/current and secure
  file sync (Syncthing). Projects: [CRISTAL](https://www.materianova.be/fr/nos-projets/cristal/),
  [SAFE (Interreg)](https://safe-interreg.eu/partenaires/materia-nova/).
  *TODO: public repository link.*
- **Low-cost robotic cells** (LeRobot ecosystem, SO-101 arms, Raspberry Pi controllers) for
  repetitive wet-chemistry sample preparation, with declaratively specified environments.
  *TODO: public repository link.*
- **Power-supply control platform** for electroplating and electrochemistry.
  *TODO: public repository link.*

## Flagship scientific case

**Internal stress in electroless Ni-P deposits.** This multi-parameter phenomenon has been
observed for decades, but it remains poorly reproducible and is documented mostly through
empirical rules. Plotter provides the analysis step: extracting the stress indicators from
each measurement and aggregating them per process condition. The AI partners' planning layer
needs exactly this to choose the next experiment.

## Licensing

The code will be released under an open-source licence to be confirmed by Materia Nova
(candidates: Apache-2.0, EUPL-1.2).
