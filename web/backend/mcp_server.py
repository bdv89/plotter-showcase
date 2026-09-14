"""Serveur MCP monté dans le backend CSV Plotter.

Permet à une LLM de piloter l'outil en HTTP (`claude mcp add --transport http …`)
sans rien installer côté client. Les données entrent par SHARE_PATH ; l'artefact
durable est un pool `.db` que l'utilisateur rouvre dans son navigateur.

Tout ce qui touche aux données passe par les **handlers de routes existants**
(ce sont des fonctions ordinaires) : le traitement reste ainsi sur le chemin de
lecture des données — cf. PITFALLS.md « Le traitement s'appliquait à côté du
chemin de plot ». On reproduit exactement la façon dont FastAPI les exécute :
`await` pour les routes async, threadpool pour les routes sync (un tool MCP
synchrone tournerait SUR l'event loop et gèlerait le backend, qui n'a qu'un
seul worker uvicorn).

Deux duplications assumées, documentées parce qu'elles ne seront jamais resynchronisées :

1. **Les statistiques de population** sont un portage de
   `web/frontend/src/utils/stats.ts` (+ `seriesKey`/`seriesLabel` de
   `utils/coloring.ts`). Le frontend les calcule dans le navigateur à partir de
   valeurs déjà présentes dans son store : il n'y a aucun endpoint à réutiliser.
   SD **échantillon** (÷ n−1, None si n < 2 — jamais 0), CV% = sd/mean×100,
   n compté **par colonne**. La fidélité se vérifie en comparant avec StatsTable
   dans le navigateur, pas par un test unitaire.

2. **La figure PNG est une figure DE LECTURE**, dessinée avec matplotlib. Ce n'est
   délibérément PAS la figure de publication : celle-là est la figure Plotly du
   navigateur, réglée dans PlotSettings et exportée en SVG/PNG ×4. Porter les
   ~170 lignes de layout de PlotView.tsx ici serait le piège n°4 (duplication de
   DEFAULT_STYLE) à grande échelle, sur du code qui bouge à chaque réglage ajouté.
   Rien ici ne lit `plot_style`, volontairement — il n'y a donc rien à synchroniser.
"""

import io
import math
import os
import re
import uuid
from contextlib import contextmanager

import anyio
import matplotlib

matplotlib.use("Agg")  # avant tout import de pyplot : pas de backend graphique sur un serveur

import matplotlib.pyplot as plt  # noqa: E402
from api.extract import extract_single  # noqa: E402
from api.plot import get_plot_data  # noqa: E402
from api.pool import load_pool  # noqa: E402
from api.upload import ALLOWED_EXTENSIONS, upload_files  # noqa: E402
from config import SHARE_PATH  # noqa: E402
from core.db_schema import save_to_sqlite  # noqa: E402
from core.extraction import OPERATIONS  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from mcp.server.fastmcp import Context, FastMCP, Image  # noqa: E402
from models.schemas import ExtractRequest, PlotRequest  # noqa: E402
from sessions import build_data_pool, manager  # noqa: E402
from starlette.datastructures import UploadFile  # noqa: E402
from state import AppState  # noqa: E402

mcp = FastMCP("csv-plotter", streamable_http_path="/")

POOL_EXTENSIONS = {".db", ".dpool"}

# Alias courants -> label backend. Le reste est apparié directement sur OPERATIONS.
OPERATION_ALIASES = {"std": "Std Dev", "stddev": "Std Dev", "average": "Mean", "avg": "Mean"}

# Repli si le header mcp-session-id manque. Jamais "default" : ce serait la
# session bac-à-sable partagée avec les navigateurs dont le header a échoué.
_FALLBACK_SID = f"mcp-{uuid.uuid4().hex[:12]}"


def _sid(ctx: Context) -> str:
    """Session Plotter dérivée de la session MCP : autonome, stable par connexion."""
    request = getattr(ctx.request_context, "request", None)
    raw = request.headers.get("mcp-session-id") if request is not None else None
    return f"mcp-{raw}" if raw else _FALLBACK_SID


@contextmanager
def _session(sid: str):
    """Même contrat que la dépendance get_session : l'état + son verrou."""
    state = manager.get(sid)
    with state.lock:
        yield state


def _file_id(state: AppState, filename: str) -> str | None:
    for fid, info in state.files.items():
        if info["filename"] == filename:
            return fid
    return None


def _file_ids(state: AppState, names: list[str] | None) -> tuple[list[str], list[str]]:
    """(file_ids trouvés, noms introuvables). Liste vide -> tous les fichiers."""
    if not names:
        return list(state.files.keys()), []
    found, missing = [], []
    for name in names:
        fid = _file_id(state, name)
        found.append(fid) if fid else missing.append(name)
    return found, missing


def _resolve_column(state: AppState, file_ids: list[str], name: str | None) -> str | None:
    """Retrouve le nom EXACT d'une colonne à partir d'un nom approchant.

    Beaucoup de CSV exportés commencent par un BOM, qui devient alors partie du
    nom de la première colonne ('﻿Position (mm)'). Le navigateur s'en sort
    parce qu'il renvoie la chaîne qu'il a reçue ; une LLM, elle, écrit le nom
    qu'un humain lirait. On apparie donc en ignorant BOM, espaces et casse.
    """
    if not name:
        return name
    for fid in file_ids:  # correspondance exacte d'abord
        if name in state.files[fid]["data"].columns:
            return name
    wanted = name.strip().lstrip("﻿").lower()
    for fid in file_ids:
        for column in state.files[fid]["data"].columns:
            if str(column).strip().lstrip("﻿").lower() == wanted:
                return str(column)
    return name


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _operation(name: str) -> str | None:
    """Apparie un nom libre au label backend exact (Max, Std Dev, Y at max(X)…).

    Les labels viennent de core.extraction.OPERATIONS : une opération ajoutée au
    backend est donc connue d'ici sans rien changer. C'est pour ça qu'on ne porte
    PAS l'OPERATION_MAP du frontend.
    """
    target = _normalize(name)
    for label in OPERATIONS:
        if _normalize(label) == target:
            return label
    for alias, label in OPERATION_ALIASES.items():
        if alias == target:
            return label
    return None


# --------------------------------------------------------------------------
# Statistiques de population — portage de utils/stats.ts + utils/coloring.ts
# --------------------------------------------------------------------------

def _tokens(filename: str) -> list[str]:
    """displayTokens() : extension retirée, découpe sur [\\s_;-]+, casse conservée."""
    bare = re.sub(r"\.[^.]+$", "", filename)
    return [t for t in re.split(r"[\s_;-]+", bare) if t]


def _series_key(filename: str, group_by: list[int]) -> str:
    """seriesKey() : tokens choisis, en minuscules, triés, joints par '|'."""
    if not group_by:
        return ""
    toks = [t.lower() for t in _tokens(filename)]
    return "|".join(toks[i] if i < len(toks) else "" for i in sorted(group_by))


def _series_label(filename: str, group_by: list[int]) -> str:
    """seriesLabel() : mêmes tokens, casse d'origine, joints par un espace."""
    bare = re.sub(r"\.[^.]+$", "", filename)
    if not group_by:
        return bare
    toks = _tokens(filename)
    picked = [toks[i] for i in sorted(group_by) if i < len(toks) and toks[i]]
    return " ".join(picked) or bare


def _stats_of(values: list[float]) -> dict:
    """statsOf() : SD échantillon (n−1), None si n < 2 — jamais 0."""
    n = len(values)
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n >= 2 else None
    ordered = sorted(values)
    mid = n // 2
    median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return {
        "n": n,
        "mean": mean,
        "sd": sd,
        "cv": (sd / mean * 100) if (sd is not None and mean != 0) else None,
        "min": ordered[0],
        "max": ordered[-1],
        "median": median,
    }


def _extracted_names(state: AppState) -> list[str]:
    """Colonnes extraites présentes, dans l'ordre de première apparition."""
    names: list[str] = []
    for fid in state.files:
        for name in state.extracted_columns.get(fid, {}):
            if name not in names:
                names.append(name)
    return names


def _populations(state: AppState, group_by: list[int]) -> list[dict]:
    """computePopulations() — le n est PAR COLONNE : un fichier sans cette
    extraction ne compte pas pour elle."""
    groups: dict[str, dict] = {}
    for fid, info in state.files.items():
        key = _series_key(info["filename"], group_by)
        label = _series_label(info["filename"], group_by) if group_by else "Tous les fichiers"
        groups.setdefault(key, {"label": label, "members": []})["members"].append(fid)

    rows = []
    for key in sorted(groups):
        members = groups[key]["members"]
        stats = {}
        for name in _extracted_names(state):
            values = []
            for fid in members:
                cell = state.extracted_columns.get(fid, {}).get(name)
                value = cell.get("value") if cell else None
                if isinstance(value, (int, float)) and math.isfinite(value):
                    values.append(float(value))
            if values:
                stats[name] = _stats_of(values)
        rows.append({"label": groups[key]["label"], "files": len(members), "columns": stats})
    return rows


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@mcp.tool()
async def list_share() -> dict:
    """Liste les fichiers du dossier partagé (SHARE_PATH) : c'est par là que les
    données entrent. Le serveur ne voit PAS le disque de l'utilisateur — pour
    faire analyser des fichiers, il faut d'abord les déposer sur ce partage."""

    def impl() -> dict:
        if not SHARE_PATH or not os.path.isdir(SHARE_PATH):
            return {
                "error": "SHARE_PATH n'est pas configuré ou n'existe pas sur le serveur.",
                "share_path": SHARE_PATH or "(non défini)",
            }
        data, pools = [], []
        for name in sorted(os.listdir(SHARE_PATH)):
            path = os.path.join(SHARE_PATH, name)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(name)[1].lower()
            entry = {"name": name, "size_kb": round(os.path.getsize(path) / 1024, 1)}
            if ext in ALLOWED_EXTENSIONS:
                data.append(entry)
            elif ext in POOL_EXTENSIONS:
                pools.append(entry)
        return {"share_path": SHARE_PATH, "data_files": data, "pools": pools}

    return await anyio.to_thread.run_sync(impl)


@mcp.tool()
async def open_files(names: list[str], ctx: Context) -> dict:
    """Charge des fichiers du partage dans la session.

    CSV/TSV/Excel s'ajoutent aux fichiers déjà chargés. Un pool .db/.dpool
    REMPLACE toute la session (fichiers, styles, extractions) — c'est le
    comportement du bouton Load du navigateur.

    Un fichier rejeté (mauvaise extension, illisible) n'interrompt rien : il
    ressort dans `rejected`. Toujours vérifier cette liste avant de conclure.
    """
    sid = _sid(ctx)
    loaded, rejected, replaced = [], [], []

    with _session(sid) as state:
        uploads = []
        for name in names:
            path = os.path.join(SHARE_PATH, os.path.basename(name))  # pas d'échappée du partage
            if not SHARE_PATH or not os.path.isfile(path):
                rejected.append({"name": name, "error": "introuvable sur le partage"})
                continue
            payload = await anyio.to_thread.run_sync(_read_bytes, path)
            upload = UploadFile(file=io.BytesIO(payload), filename=os.path.basename(name))
            if os.path.splitext(name)[1].lower() in POOL_EXTENSIONS:
                try:
                    await load_pool(file=upload, state=state)
                    replaced.append(name)
                except HTTPException as exc:
                    rejected.append({"name": name, "error": str(exc.detail)})
            else:
                uploads.append(upload)

        if uploads:
            for info in await upload_files(files=uploads, state=state):
                if info.error:
                    rejected.append({"name": info.filename, "error": info.error})
                else:
                    loaded.append(
                        {"name": info.filename, "rows": info.row_count, "columns": info.columns}
                    )

        return {
            "loaded": loaded,
            "pools_loaded": replaced,
            "rejected": rejected,
            "files_in_session": len(state.files),
        }


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


@mcp.tool()
async def session(ctx: Context) -> dict:
    """État de la session : fichiers chargés, colonnes disponibles, valeurs extraites."""
    sid = _sid(ctx)

    def impl() -> dict:
        with _session(sid) as state:
            return {
                "files": [
                    {
                        "name": info["filename"],
                        "rows": len(info["data"]),
                        "columns": list(info["data"].columns),
                    }
                    for info in state.files.values()
                ],
                "extracted": {
                    state.files[fid]["filename"]: {k: v["value"] for k, v in cols.items()}
                    for fid, cols in state.extracted_columns.items()
                    if fid in state.files
                },
                "selection": {
                    "x_column": state.x_column,
                    "y_columns": state.y_columns,
                    "y2_columns": state.y2_columns,
                },
            }

    return await anyio.to_thread.run_sync(impl)


@mcp.tool()
async def describe(name: str, ctx: Context, rows: int = 5) -> dict:
    """Premières lignes d'un fichier — pour voir les unités et les ordres de
    grandeur avant de choisir les colonnes X et Y."""
    sid = _sid(ctx)

    def impl() -> dict:
        with _session(sid) as state:
            fid = _file_id(state, name)
            if not fid:
                return {"error": f"'{name}' n'est pas chargé. Voir session()."}
            df = state.files[fid]["data"]
            head = df.head(max(1, min(rows, 50)))
            return {
                "name": name,
                "rows": len(df),
                "columns": list(df.columns),
                "sample": head.astype(object).where(head.notna(), None).to_dict("records"),
            }

    return await anyio.to_thread.run_sync(impl)


@mcp.tool()
async def plot(
    x_column: str,
    y_columns: list[str],
    ctx: Context,
    files: list[str] | None = None,
    y2_columns: list[str] | None = None,
    processing: dict | None = None,
) -> list:
    """Trace les courbes et renvoie une IMAGE + un résumé chiffré.

    `files` vide = tous les fichiers de la session. `processing` applique le même
    traitement que l'onglet Process ; clés utiles :
    smoothing_enabled/smoothing_window · denoise_enabled/denoise_method
    ('savgol'|'median'|'wavelet'|'fft')/denoise_window/denoise_polyorder ·
    baseline_enabled/baseline_method ('snip'|'asls'|'arpls')/baseline_k ·
    normalize_enabled/normalize_method ('minmax'|'zscore') ·
    outlier_enabled/outlier_threshold. Une clé mal orthographiée est ignorée
    SANS erreur : vérifier que l'image change.

    ⚠️ Cette figure est une aide à la lecture, pas un livrable : la figure de
    publication se règle et s'exporte dans le navigateur.
    """
    sid = _sid(ctx)

    def impl() -> tuple[bytes, dict]:
        with _session(sid) as state:
            file_ids, missing_files = _file_ids(state, files)
            x_resolved = _resolve_column(state, file_ids, x_column)
            y_resolved = [_resolve_column(state, file_ids, c) for c in y_columns]
            y2_resolved = [_resolve_column(state, file_ids, c) for c in (y2_columns or [])]
            req = PlotRequest(
                file_ids=file_ids,
                x_column=x_resolved,
                y_columns=y_resolved,
                y2_columns=y2_resolved,
                processing=processing or {},
            )
            traces = get_plot_data(req, state).traces

            # Mémorise la sélection pour qu'un pool sauvegardé se rouvre déjà tracé.
            state.x_column = x_resolved
            state.y_columns = list(y_resolved)
            state.y2_columns = list(y2_resolved)

            # /plot-data met le file_id dans trace.name (c'est le frontend qui y
            # substitue le legend_label). On fait pareil, sinon la légende de la
            # figure et le résumé n'affichent que des UUID.
            filenames = {fid: state.files[fid]["filename"] for fid in file_ids}

        expected = len(file_ids) * (len(y_resolved) + len(y2_resolved))
        fig, ax = plt.subplots(figsize=(9, 6), dpi=100)
        ax2 = None
        summary = []
        for trace in traces:
            target = ax
            if trace.yaxis == "y2":
                ax2 = ax2 or ax.twinx()
                target = ax2
            label = trace.name.replace(
                trace.file_id, filenames.get(trace.file_id, trace.file_id)
            )
            target.plot(trace.x, trace.y, linewidth=1.2, label=label)
            summary.append(
                {
                    "trace": label,
                    "axis": trace.yaxis,
                    "points": len(trace.x),
                    "x_range": [min(trace.x), max(trace.x)] if trace.x else None,
                    "y_range": [min(trace.y), max(trace.y)] if trace.y else None,
                }
            )

        ax.set_xlabel(x_resolved)
        ax.set_ylabel(", ".join(y_resolved))
        if ax2 is not None:
            ax2.set_ylabel(", ".join(y2_resolved))
        ax.grid(alpha=0.3)
        handles, labels = ax.get_legend_handles_labels()
        if ax2 is not None:
            handles2, labels2 = ax2.get_legend_handles_labels()
            handles, labels = handles + handles2, labels + labels2
        if labels and len(labels) <= 20:
            ax.legend(handles, labels, fontsize=8)
        fig.tight_layout()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png")
        plt.close(fig)

        report = {"traces": summary, "traces_drawn": len(traces)}
        if missing_files:
            report["files_not_loaded"] = missing_files
        if len(traces) < expected:
            report["warning"] = (
                f"{expected - len(traces)} trace(s) manquante(s) : fichier ou colonne "
                "introuvable. Vérifier les noms exacts avec session()."
            )
        return buffer.getvalue(), report

    png, report = await anyio.to_thread.run_sync(impl)
    return [Image(data=png, format="png"), str(report)]


@mcp.tool()
async def extract(
    operation: str,
    column: str,
    ctx: Context,
    files: list[str] | None = None,
    x_column: str | None = None,
    x_value: float | None = None,
    x_min: float | None = None,
    x_max: float | None = None,
    condition_column: str | None = None,
    threshold: float | None = None,
    processing: dict | None = None,
) -> dict:
    """Extrait une valeur par fichier et la stocke dans la session.

    `operation` accepte un nom libre ('max', 'std', 'y at max(x)') apparié au
    label backend. Opérations : Max, Min, Mean, Median, Std Dev, Integral, Slope,
    Y at max(X), Value at X, Y when X > threshold, Y when X < threshold.
    Integral/Slope/Y at max(X) exigent `x_column` ; Value at X exige `x_value` ;
    les conditionnelles exigent `condition_column` + `threshold`.
    `x_min`/`x_max` restreignent l'intervalle X avant le calcul.

    Un fichier qui ne donne rien est listé dans `failed` sans interrompre les
    autres. Les valeurs ne sont PAS persistées : appeler save() pour les rendre
    durables.
    """
    sid = _sid(ctx)
    label = _operation(operation)
    if not label:
        return {"error": f"Opération inconnue : '{operation}'.", "available": list(OPERATIONS)}

    def impl() -> dict:
        with _session(sid) as state:
            file_ids, missing_files = _file_ids(state, files)
            target = _resolve_column(state, file_ids, column)
            x_col = _resolve_column(state, file_ids, x_column)
            cond_col = _resolve_column(state, file_ids, condition_column)
            values, failed = {}, {}
            for fid in file_ids:
                name = state.files[fid]["filename"]
                try:
                    result = extract_single(
                        ExtractRequest(
                            file_id=fid,
                            column=target,
                            operation=label,
                            x_column=x_col,
                            x_value=x_value,
                            x_min=x_min,
                            x_max=x_max,
                            condition_column=cond_col,
                            threshold=threshold,
                            processing=processing or {},
                        ),
                        state,
                    )
                    values[name] = result["value"]
                except HTTPException as exc:
                    failed[name] = str(exc.detail)
                except Exception as exc:  # une colonne absente ne doit pas tout casser
                    failed[name] = str(exc)

            out = {"column_name": f"{label}({target})", "values": values}
            if failed:
                out["failed"] = failed
            if missing_files:
                out["files_not_loaded"] = missing_files
            return out

    return await anyio.to_thread.run_sync(impl)


@mcp.tool()
async def stats(ctx: Context, group_by: list[int] | None = None) -> dict:
    """Statistiques par population sur les colonnes extraites :
    n · moyenne · SD · CV% · min · max · médiane.

    Une population = les fichiers partageant les mêmes tokens de nom de fichier.
    `group_by` donne les INDICES des tokens (le nom est découpé sur les espaces,
    '_', '-' et ';'). Exemple : 'Essai_70_c100.csv' -> tokens ['Essai','70','c100'],
    donc group_by=[1] regroupe par '70' / '71'. Liste vide = une seule population.
    Utiliser `tokens_example` de la réponse pour choisir les indices.

    SD = écart-type d'ÉCHANTILLON (÷ n−1), null si n < 2 (jamais 0). Le n est
    compté par colonne : un fichier sans cette extraction ne compte pas pour elle.
    """
    sid = _sid(ctx)
    picked = group_by or []

    def impl() -> dict:
        with _session(sid) as state:
            if not state.files:
                return {"error": "Aucun fichier chargé. Voir list_share() puis open_files()."}
            example = next(iter(state.files.values()))["filename"]
            return {
                "tokens_example": {"filename": example, "tokens": _tokens(example)},
                "group_by": picked,
                "populations": _populations(state, picked),
            }

    return await anyio.to_thread.run_sync(impl)


@mcp.tool()
async def save(name: str, ctx: Context) -> dict:
    """Sauvegarde la session en pool .db sur le partage.

    C'est l'artefact durable : l'utilisateur le glisse sur le bouton Load du
    navigateur et retrouve les fichiers, la sélection de colonnes et les
    extractions pour les mettre en forme.
    """
    sid = _sid(ctx)

    def impl() -> dict:
        if not SHARE_PATH or not os.path.isdir(SHARE_PATH):
            return {"error": "SHARE_PATH n'est pas configuré sur le serveur."}
        filename = os.path.basename(name)
        if not filename.endswith(".db"):
            filename += ".db"
        path = os.path.join(SHARE_PATH, filename)
        with _session(sid) as state:
            if not state.files:
                return {"error": "Session vide : rien à sauvegarder."}
            # build_data_pool + save_to_sqlite : ce que fait /pool/export, sans
            # passer par _sync_state qui écraserait x_column/y_columns avec ses
            # défauts Pydantic quand on ne les lui renvoie pas.
            save_to_sqlite(build_data_pool(state), path)
            count = len(state.files)
        return {
            "saved": filename,
            "path": path,
            "files": count,
            "size_kb": round(os.path.getsize(path) / 1024, 1),
        }

    return await anyio.to_thread.run_sync(impl)
