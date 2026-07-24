# TODO

## Fait
- [x] **Onglet Metrics** — suivi de connexion (IPs + hits/endpoint + activité/jour), calqué sur
  picture_to_CAS. Backend : middleware + `core/metrics.py` + `api/metrics.py` (SQLite `METRICS_DB`).
  Frontend : `MetricsView.tsx` (4ᵉ onglet). ⚠️ Nécessite un `Restart-Service CSVPlotter` (admin) pour
  charger le backend en prod.
