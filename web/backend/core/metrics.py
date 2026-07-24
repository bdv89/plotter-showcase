"""Connection-tracking metrics (IP + endpoint hits, aggregated per day).

Calqué sur picture_to_CAS (server_display/metrics.py) : SQLite dédiée, agrégation
par UPSERT (pas de log d'événements bruts). Suivi = compteurs par jour + IPs uniques.

Un seul worker uvicorn (cf. PITFALLS #23) → un simple `threading.Lock` sérialise les
écritures ; connexions sqlite courtes ouvertes/fermées par appel.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime, timedelta
from typing import Any

_db_path: str | None = None
_lock = threading.Lock()


def init_metrics(db_path: str) -> None:
    """Create the metrics tables if needed and remember the DB path."""
    global _db_path
    _db_path = db_path
    with sqlite3.connect(_db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metrics_daily (
                date TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (date, endpoint)
            );
            CREATE TABLE IF NOT EXISTS metrics_ips (
                date TEXT NOT NULL,
                ip TEXT NOT NULL,
                first_seen TEXT,
                PRIMARY KEY (date, ip)
            );
            """
        )
        conn.commit()


def _today() -> str:
    return date.today().isoformat()


def record(endpoint: str, ip: str) -> None:
    """Increment the daily hit counter for `endpoint` and remember `ip`.

    Never raises: a tracking failure must not break the actual request.
    """
    if not _db_path:
        return
    today = _today()
    try:
        with _lock, sqlite3.connect(_db_path) as conn:
            conn.execute(
                """
                INSERT INTO metrics_daily (date, endpoint, count)
                VALUES (?, ?, 1)
                ON CONFLICT(date, endpoint) DO UPDATE SET count = count + 1
                """,
                (today, endpoint),
            )
            if ip:
                conn.execute(
                    """
                    INSERT INTO metrics_ips (date, ip, first_seen)
                    VALUES (?, ?, ?)
                    ON CONFLICT(date, ip) DO NOTHING
                    """,
                    (today, ip, datetime.now().isoformat()),
                )
            conn.commit()
    except Exception as exc:  # pragma: no cover - tracking is best-effort
        print(f"❌ metrics.record failed: {exc}")


def summary() -> dict[str, Any]:
    """Overall totals: requests, unique IPs (total / today), date range."""
    if not _db_path:
        return _empty_summary()
    with sqlite3.connect(_db_path) as conn:
        total_requests = conn.execute(
            "SELECT COALESCE(SUM(count), 0) FROM metrics_daily"
        ).fetchone()[0]
        unique_ips_total = conn.execute(
            "SELECT COUNT(DISTINCT ip) FROM metrics_ips"
        ).fetchone()[0]
        unique_ips_today = conn.execute(
            "SELECT COUNT(*) FROM metrics_ips WHERE date = ?", (_today(),)
        ).fetchone()[0]
        first_date, last_date = conn.execute(
            "SELECT MIN(date), MAX(date) FROM metrics_daily"
        ).fetchone()
    return {
        "total_requests": total_requests,
        "unique_ips_total": unique_ips_total,
        "unique_ips_today": unique_ips_today,
        "first_date": first_date,
        "last_date": last_date,
    }


def daily(days: int = 30) -> list[dict[str, Any]]:
    """Per-day totals (requests + unique IPs) over the last `days` days."""
    if not _db_path:
        return []
    cutoff = (date.today() - timedelta(days=max(days, 1) - 1)).isoformat()
    with sqlite3.connect(_db_path) as conn:
        rows = conn.execute(
            """
            SELECT date, SUM(count) AS requests,
                   (SELECT COUNT(*) FROM metrics_ips WHERE metrics_ips.date = metrics_daily.date) AS unique_ips
            FROM metrics_daily
            WHERE date >= ?
            GROUP BY date
            ORDER BY date DESC
            """,
            (cutoff,),
        ).fetchall()
    return [{"date": r[0], "requests": r[1], "unique_ips": r[2]} for r in rows]


def endpoints() -> list[dict[str, Any]]:
    """Per-endpoint hit totals + last activity date, busiest first."""
    if not _db_path:
        return []
    with sqlite3.connect(_db_path) as conn:
        rows = conn.execute(
            """
            SELECT endpoint, SUM(count) AS total, MAX(date) AS last_activity
            FROM metrics_daily
            GROUP BY endpoint
            ORDER BY total DESC
            """
        ).fetchall()
    return [{"endpoint": r[0], "total": r[1], "last_activity": r[2]} for r in rows]


def _empty_summary() -> dict[str, Any]:
    return {
        "total_requests": 0,
        "unique_ips_total": 0,
        "unique_ips_today": 0,
        "first_date": None,
        "last_date": None,
    }
