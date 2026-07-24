"""Connection-tracking metrics endpoints (read-only, all sessions).

Ouvert à tous (modèle LAN sans auth). Ces routes sont exclues du tracking par le
middleware de main.py (sinon l'auto-refresh du frontend gonflerait les compteurs).
"""

from core import metrics
from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/metrics/summary")
def metrics_summary():
    """Totaux : requêtes, IPs uniques (total / aujourd'hui), plage de dates."""
    return metrics.summary()


@router.get("/metrics/daily")
def metrics_daily(days: int = Query(30, ge=1, le=365)):
    """Activité par jour (requêtes + IPs uniques) sur les `days` derniers jours."""
    return {"rows": metrics.daily(days)}


@router.get("/metrics/endpoints")
def metrics_endpoints():
    """Hits par endpoint + dernière activité."""
    return {"rows": metrics.endpoints()}
