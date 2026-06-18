# Déploiement Plotter (prod) — nginx sous-chemin `/plotter/` + backend en service NSSM

Intégration dans le reverse-proxy existant (**lab services portal**, `<NGINX_DIR>`), en **sous-chemin** `/plotter/`
comme les autres services (cf. `data_to_csv`). nginx sert le frontend buildé en statique
(`alias` direct sur `dist/`) et proxifie `/plotter/api/` vers le backend uvicorn
(1 worker, `127.0.0.1:9099`). La session est portée par le header `X-Session-Id`
(localStorage, pas de cookie) → pas de CORS, pas de cookie cross-site.

```
  Navigateur ──HTTP──> nginx :80
       /plotter/        ─ alias ───────> web/frontend/dist (statique, base=/plotter/)
       /plotter/api/    ─ proxy_pass ──> 127.0.0.1:9099/api  (uvicorn, service NSSM "CSVPlotter")
```

## 1. Builder le frontend pour le sous-chemin `/plotter/`
Le build DOIT fixer `base=/plotter/` (sinon les assets partent en `/assets/...` → page blanche)
et l'URL API en `/plotter/api`.
```powershell
cd web\frontend
npm install                                   # une seule fois
$env:VITE_API_URL = '/plotter/api'
npm run build -- --base=/plotter/             # → web\frontend\dist\
```
Vérif : `dist\index.html` doit référencer `/plotter/assets/…`.

## 2. Installer le backend en service (NSSM, admin)
Prérequis : venv backend (`web\backend\venv_win`) + NSSM (https://nssm.cc).
Le nom du service **doit** être `CSVPlotter` (= `task_name` attendu par le dashboard).
```powershell
cd web\deploy
powershell -ExecutionPolicy Bypass -File .\install-service.ps1
# options : -Port 9099 -DataDir C:\ProgramData\Plotter -NssmPath C:\tools\nssm.exe -SharePath \\srv\share
```
Vérifs :
```powershell
nssm status CSVPlotter                 # SERVICE_RUNNING
curl http://127.0.0.1:9099/api/health  # { "status": "ok", ... }
```
Désinstaller : `nssm stop CSVPlotter; nssm remove CSVPlotter confirm`

> ⚠️ Arrête d'abord tout backend **dev** sur 9099 (sinon conflit de port).

## 3. Route nginx (`services.conf`, manuel)
`<NGINX_DIR>\conf\services.conf` est **maintenu à la main** (≠ `upstreams.conf`, lui auto-généré).
Ajoute le bloc de `web\deploy\services-plotter.conf` (statique `alias` + proxy `/plotter/api/`
avec `client_max_body_size 600m`). nginx tourne en **service Windows** → recharge par redémarrage :
```powershell
<NGINX_DIR>\nginx.exe -t -p <NGINX_DIR>       # valide la conf (non-admin OK)
Restart-Service Nginx                    # admin (le -s reload échoue : nginx est un service)
```

## 4. Enregistrer dans le services dashboard (visibilité + health)
Ajoute l'entrée dans `…\06_unified_work\serveur_automate\dashboard\services.yaml` :
```yaml
  - name: CSV Plotter
    slug: plotter
    prod_port: 9099
    exp_port: null
    health_path: /api/health
    task_name: CSVPlotter
    exp_task_name: null
    nginx_upstream: plotter
```
Puis `Restart-Service Dashboard` (admin) → Plotter apparaît (health vert) et le dashboard
écrit `upstream plotter { server 127.0.0.1:9099; }` dans `upstreams.conf`.
**(Optionnel, convention)** une fois l'upstream présent, remplace dans `services.conf`
`proxy_pass http://127.0.0.1:9099/api/;` par `http://plotter/api/;`, puis `nginx -t` + `Restart-Service Nginx`.

## Variables d'environnement (posées par le service)
| Variable | Rôle | Défaut conseillé |
|---|---|---|
| `UPLOAD_DIR` | uploads + cache | `C:\ProgramData\Plotter\uploads` |
| `SESSIONS_DIR` | persistance session `<sid>.db` | `…\uploads\sessions` |
| `SHARE_PATH` | share réseau pour pools (optionnel) | *(vide)* |
| `MAX_FILES` | fichiers par session | `300` |
| `MAX_SESSIONS_IN_MEMORY` | sessions chaudes en RAM (LRU ; ≈ pic de concurrence) | `16` |
| `SESSION_TTL` | éviction RAM après inactivité (s) ; non destructif | `28800` (8 h) |
| `SESSION_RETENTION_DAYS` | purge disque (`.db` + uploads) des sessions abandonnées | `30` |
| `HEAVY_CONCURRENCY` | jobs CPU lourds simultanés (denoise/baseline) | `min(4, cpu-1)` |
| `PYTHONUTF8` | évite le crash des prints emoji | `1` |

Empreinte mesurée sur données réelles (~0,27 Mo/fichier) : pic RAM ≈ `MAX_SESSIONS_IN_MEMORY × MAX_FILES × 0,3 Mo` ≈ **1,4 Go** au pire, < 0,5 Go typique. Le NVMe est le magasin : seules les sessions actives restent en RAM, les autres sont rechargées du disque au retour.

## 🔒 Sécurité (modèle LAN de confiance)
- **`X-Session-Id` est fourni par le client** (UUID localStorage) → ce n'est **pas** une authentification : un utilisateur pourrait en théorie usurper l'id d'un autre. Acceptable sur un **LAN de confiance** (pas de données sensibles inter-utilisateurs). Pour une vraie isolation, il faudrait un id opaque émis serveur (cookie httpOnly) ou un SSO — hors périmètre.
- N'expose **pas** le port backend (9099) ; seul nginx (80/443) est ouvert. Le service bind `127.0.0.1`.
- `client_max_body_size 600m` côté nginx borne la taille d'upload (aligné sur les 500 Mo backend).

## ⚠️ Contraintes
- **1 seul worker uvicorn** (état sessions en mémoire + locks threads + sémaphore global).
  Ne PAS ajouter `--workers>1` ni `--reload`. Pour scaler un jour : sortir l'état en
  store partagé (Redis) — hors périmètre actuel (~50 users LAN suffisent en 1 worker).
- **Build lié au sous-chemin** : toujours rebuilder avec `--base=/plotter/` + `VITE_API_URL=/plotter/api`.
  Un build `base=/` servi sous `/plotter/` → assets 404 → page blanche.
- `upstreams.conf` est **auto-généré par le dashboard** — ne pas l'éditer à la main.
- Les scripts `start-plotter.ps1` / `start-lan.ps1` sont **dev only** (Vite + reload),
  à ne pas utiliser en prod.

## Mise à jour
```powershell
cd web\frontend
$env:VITE_API_URL = '/plotter/api'
npm run build -- --base=/plotter/      # rebuild UI (nginx la sert directement, pas de reload)
Restart-Service CSVPlotter             # admin, si le code backend a changé
```
