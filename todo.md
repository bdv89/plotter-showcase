# TODO

## Fait
- [x] **Tableau de stats OFF par défaut** (onglet Plot) — `DEFAULT_STATS.visible = false` dans
  `appStore.ts` : c'est un ornement de la figure, il ne doit pas s'inviter sur le plot dès qu'une
  valeur est extraite. La puce On/Off de `StatsBar` l'allume ; un pool garde son propre réglage.
- [x] **Couleur de légende dans l'onglet Extract** — pastille `.legend-dot` en tête de ligne dans
  Values **et** Populations, pour relier une ligne de chiffres à une courbe. Une population
  n'affiche la sienne que si tous ses membres partagent la couleur (sans « Group by », les
  cochés forment une population multicolore). Frontend seul, déployé en prod le 2026-08-19.
- [x] **Onglet Metrics** — suivi de connexion (IPs + hits/endpoint + activité/jour), calqué sur
  picture_to_CAS. Backend : middleware + `core/metrics.py` + `api/metrics.py` (SQLite `METRICS_DB`).
  Frontend : `MetricsView.tsx` (4ᵉ onglet). ⚠️ Nécessite un `Restart-Service CSVPlotter` (admin) pour
  charger le backend en prod.
