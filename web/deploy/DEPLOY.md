# Environnements : dev → beta → prod

| Env | URL | Port / service | Dossier code | Build / lancement |
|---|---|---|---|---|
| **dev** | `http://localhost:5174` | Vite 5174 + backend 9099 | `…\260324\web` | `start-plotter.ps1` (Vite + reload, **dev only**) |
| **beta** | `…/plotter-exp/` | 9199 · `CSVPlotter_Exp` | `…\260324-exp\web` | build `--base=/plotter-exp/` (§ Version expérimentale) |
| **prod** | `…/plotter/` | 9099 · `CSVPlotter` | `…\260324\web` | build `--base=/plotter/` (§1–4) |

**Flux** : développer/tester en **dev** (5174, dans `…\260324`) → propager vers **beta** (`…\260324-exp`, build `/plotter-exp/`) pour valider sans risque → promouvoir **beta → prod** via `promote-exp-to-prod.ps1` (§7). Un build ne propage jamais le source entre dossiers : voir « Mise à jour de l'exp » (Piège n°1).

---

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

> ⚠️ **Toujours depuis PowerShell.** Sous Git Bash (MSYS), un argument commençant
> par `/` est réécrit en chemin Windows : `--base=/plotter/` devient
> `--base=/Program Files/Git/plotter/`. Et comme `VITE_API_URL` subit la **même**
> réécriture, les deux valeurs restent cohérentes entre elles et `check-build.mjs`
> valide un `dist` pourtant inutilisable. Sinon, poser `MSYS_NO_PATHCONV=1`.

> ⚠️ **`dist/` est servi en direct par nginx et n'est pas versionné.** Un
> `npm run build` nu lancé pendant une session de dev (base `/`) écrase donc le
> `dist` de la prod et casse `/plotter/` — sans sauvegarde possible, il faut
> rebuilder aux flags ci-dessus. `check-build.mjs` détecte le cas et rappelle la
> commande. Voir [PITFALLS.md](../../PITFALLS.md) « `npm run build` nu écrase le
> dist ».

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
| `SHARE_PATH` | dossier partagé : pools listés par `/api/pool/list`, **seule porte d'entrée des données du MCP** et racine des dossiers proposés par **Watch** (suivi de dossier, `api/watch.py`) | *(vide)* — **à poser pour activer le MCP et Watch** |
| `MAX_FILES` | fichiers par session | `300` |
| `MAX_SESSIONS_IN_MEMORY` | sessions chaudes en RAM (LRU ; ≈ pic de concurrence) | `16` |
| `SESSION_TTL` | éviction RAM après inactivité (s) ; non destructif | `28800` (8 h) |
| `SESSION_RETENTION_DAYS` | purge disque (`.db` + uploads) des sessions abandonnées | `30` |
| `HEAVY_CONCURRENCY` | jobs CPU lourds simultanés (denoise/baseline) | `min(4, cpu-1)` |
| `PYTHONUTF8` | évite le crash des prints emoji | `1` |

Empreinte mesurée sur données réelles (~0,27 Mo/fichier) : pic RAM ≈ `MAX_SESSIONS_IN_MEMORY × MAX_FILES × 0,3 Mo` ≈ **1,4 Go** au pire, < 0,5 Go typique. Le NVMe est le magasin : seules les sessions actives restent en RAM, les autres sont rechargées du disque au retour.

## MCP : piloter l'app depuis une LLM

Le backend monte un serveur MCP sur `/mcp`, proxifié en `/plotter/mcp` (bloc dans
`services-plotter.conf`). Les utilisateurs le branchent **sans rien installer** — la commande
est affichée dans le panneau d'aide (`?`) de l'app :

```
claude mcp add --transport http plotter http://<serveur>/plotter/mcp
```

**Deux prérequis côté serveur :**

1. **`SHARE_PATH` doit pointer sur un dossier réel** — le serveur MCP tourne sur le serveur et
   ne voit pas le disque des utilisateurs. Sans partage, les tools répondent proprement mais
   aucune donnée ne peut entrer. Le compte du service NSSM doit y avoir accès en **lecture et
   écriture** (la LLM y réécrit les pools `.db`).
2. **`mcp` et `matplotlib` dans le venv du service.** Les `promote-*.ps1` s'en chargent
   désormais (étape `[2/4]`, `pip install -r requirements.txt` avant le restart). Pour une
   install manuelle : `.\venv_win\Scripts\python.exe -m pip install -r requirements.txt`.
   ⚠️ Sans ces paquets, `main.py` ne s'importe plus et **le backend ne démarre pas du tout**.
3. **Le bloc nginx `location /plotter/mcp`** : `proxy_buffering off` + `proxy_http_version 1.1`
   sont obligatoires (le transport streame), et le bloc doit rester plus spécifique que
   `location /plotter/` — nginx choisit la plus longue correspondance de préfixe.

⚠️ **Aucune authentification.** Exposer `/plotter/mcp` donne à quiconque atteint nginx le droit
de piloter le serveur et de lire/écrire `SHARE_PATH` — c'est le modèle LAN de confiance déjà
en place, mais avec une surface plus large. Ne pas publier ce chemin hors du LAN ; le retirer
du bloc nginx suffit à désactiver la fonctionnalité sans toucher au code.

Charge : le rendu des figures et les traitements tournent dans le backend de prod, qui n'a
**qu'un seul worker uvicorn**. Les tools s'exécutent hors de l'event loop et `HEAVY_CONCURRENCY`
continue de borner les jobs lourds, mais une extraction sur des dizaines de fichiers reste
sérialisée par le verrou de session.

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

---

# Version expérimentale (`/plotter-exp/` + backend 9199)

Instance **parallèle et indépendante** de la prod, pour tester sans risque. Code dans une **copie de dossier** séparée
(le dépôt est géré par jj ; une simple copie évite tout conflit VCS et isole totalement l'exp),
2ᵉ service NSSM `CSVPlotter_Exp` sur **9199**, données isolées (`C:\ProgramData\Plotter_Exp`), nginx sous-chemin `/plotter-exp/`.
La prod (`/plotter/`, 9099) n'est **jamais** touchée.

```
  Navigateur ──HTTP──> nginx :80
       /plotter/         ─> 127.0.0.1:9099  (CSVPlotter,     code ...\260324)       ← PROD, inchangée
       /plotter-exp/     ─> 127.0.0.1:9199  (CSVPlotter_Exp, code ...\260324-exp)   ← EXPÉRIMENTAL
```

### 1. Copie du code (indépendante de la prod)
On copie **web/** sans les artefacts lourds/régénérables (`venv_win`, `node_modules`, `dist`, caches) :
```powershell
$src = '<INSTALL_DIR>\260324\web'
$dst = '<INSTALL_DIR>\260324-exp\web'
robocopy $src $dst /MIR /R:1 /W:1 /XJ /XD venv venv_win node_modules dist __pycache__ uploads logs .git .jj /XF *.log
# → ...\260324-exp\web contient le code, à recréer ses dépendances ci-dessous
```

### 2. Dépendances de la copie (venv + npm, une seule fois)
```powershell
cd <INSTALL_DIR>\260324-exp\web\backend
python -m venv venv_win
.\venv_win\Scripts\Activate.ps1; pip install -r requirements.txt; deactivate
cd ..\frontend
npm install
```

### 3. Build frontend pour `/plotter-exp/`
```powershell
cd ..\260324-exp\web\frontend
$env:VITE_API_URL = '/plotter-exp/api'
npm run build -- --base=/plotter-exp/        # → dist\index.html doit référencer /plotter-exp/assets/…
```

### 4. Service backend 9199 (NSSM, admin) — réutilise install-service.ps1 avec d'autres paramètres
```powershell
cd ..\260324-exp\web\deploy        # ⚠️ lancer depuis le deploy DE LA COPIE (résout son venv_win)
powershell -ExecutionPolicy Bypass -File .\install-service.ps1 `
  -ServiceName CSVPlotter_Exp -Port 9199 -DataDir C:\ProgramData\Plotter_Exp
nssm status CSVPlotter_Exp                    # SERVICE_RUNNING
curl http://127.0.0.1:9199/api/health         # { "status": "ok", ... }
```
Désinstaller : `nssm stop CSVPlotter_Exp; nssm remove CSVPlotter_Exp confirm`

### 5. Route nginx
Ajoute le bloc de `web\deploy\services-plotter-exp.conf` dans `<NGINX_DIR>\conf\services.conf`, puis :
```powershell
<NGINX_DIR>\nginx.exe -t -p <NGINX_DIR>       # valide
Restart-Service Nginx                    # admin
```
→ accessible sur `http://<serveur>/plotter-exp/`.

### 6. Dashboard lab services — deux cartes (prod + beta)
La prod et la beta coexistent sur **deux URLs** (`/plotter/` et `/plotter-exp/`) ; ce **n'est pas** un
« mode exp » (bascule d'upstream comme InventoryServer). On les expose donc comme **deux entrées
distinctes** dans `…\services.yaml` (la prod a déjà la sienne ; ajoute la beta) :
```yaml
  - name: CSV Plotter
    slug: plotter
    prod_port: 9099
    health_path: /api/health
    task_name: CSVPlotter
    nginx_upstream: plotter
    url: /plotter/                  # bouton « Ouvrir » sur la carte

  - name: CSV Plotter (Beta)
    slug: plotter-exp
    prod_port: 9199
    health_path: /api/health
    task_name: CSVPlotter_Exp
    nginx_upstream: plotter-exp
    url: /plotter-exp/
```
Puis `Restart-Service Dashboard` (admin) → deux cartes, chacune avec santé, bouton **Relancer**
(→ son service NSSM) et lien **Ouvrir**. Le champ `url` est facultatif (ajouté au modèle dashboard) :
absent = pas de bouton Ouvrir.

### 7. Promotion beta → prod (une seule commande)
Une fois la beta validée sur `/plotter-exp/`, pousse son code vers la prod :
```powershell
cd web\deploy
powershell -ExecutionPolicy Bypass -File .\promote-exp-to-prod.ps1   # admin ; -Force pour sauter la confirmation
```
Le script : (1) `robocopy …\260324-exp\web → …\260324\web` (hors `venv_win/node_modules/dist/__pycache__/uploads/logs`),
(2) rebuild frontend prod `--base=/plotter/`, (3) `Restart-Service CSVPlotter` + health check.
Données prod (`C:\ProgramData\Plotter`) et beta (9199, `C:\ProgramData\Plotter_Exp`) **non touchées**.
Ensuite **Ctrl+Shift+R** sur `/plotter/`.

### Mise à jour de l'exp

> ⚠️ **Piège n°1** : on développe dans `…\260324`, mais `/plotter-exp/` sert le `dist/` **compilé de la copie `…\260324-exp`**.
> Éditer `…\260324` puis rebuilder n'a **aucun effet** tant que le code n'a pas été **propagé** vers `…\260324-exp`.
> Toujours faire : **(1) propager → (2) rebuild/redémarrer → (3) hard-refresh**.

**Raccourci (recommandé)** — le script `promote-dev-to-beta.ps1` enchaîne propagation + rebuild + restart + health check :
```powershell
cd web\deploy
powershell -ExecutionPolicy Bypass -File .\promote-dev-to-beta.ps1   # admin ; -Force pour sauter la confirmation
```
Puis **Ctrl+Shift+R** sur `/plotter-exp/`. Les étapes manuelles ci-dessous restent valables si tu veux propager/builder à la main.

**1. Propager le code dev → copie exp** (même robocopy qu'à l'install, exclut les artefacts régénérables) :
```powershell
$src = '<INSTALL_DIR>\260324\web'
$dst = '<INSTALL_DIR>\260324-exp\web'
robocopy $src $dst /MIR /R:1 /W:1 /XJ /XD venv venv_win node_modules dist __pycache__ uploads logs .git .jj /XF *.log
```

**2a. Changement frontend** (`.tsx`, `.css`, store…) — rebuild du `dist/`, **pas** de redémarrage de service :
```powershell
cd <INSTALL_DIR>\260324-exp\web\frontend
$env:VITE_API_URL = '/plotter-exp/api'; npm run build -- --base=/plotter-exp/
```

**2b. Changement backend** (`.py`) — redémarrer le service (admin) ; nginx sert l'API via proxy, aucun rebuild UI :
```powershell
Restart-Service CSVPlotter_Exp -Force        # PowerShell admin requis
```

**3. Hard-refresh navigateur** sur `http://<serveur>/plotter-exp/` → **Ctrl+Shift+R** (les anciens assets JS sont en cache ; un F5 simple ne suffit pas).

> ⚠️ **Piège n°2** (nom de service) : le service exp s'appelle **`CSVPlotter_Exp`**, pas `CSVPlotter`.
> `Restart-Service CSVPlotter` → *NoServiceFoundForGivenName*. Le bouton du services dashboard doit pointer sur
> `exp_task_name: CSVPlotter_Exp` (cf. §6) ; sinon son redémarrage échoue avec cette même erreur.

> ⚠️ **Piège n°3** (dépendances de la copie) : `promote-dev-to-beta.ps1` lance désormais `npm install` **systématiquement** avant le build.
> Auparavant il ne le faisait que si `node_modules` était **absent** : une dépendance ajoutée côté dev depuis la dernière promo n'était jamais
> installée côté beta et `tsc -b` cassait (vécu avec `vitest` : `error TS2307: Cannot find module 'vitest'`). `npm install` prend ~1 s quand rien
> ne change — le garder inconditionnel.

### ⚠️ Ne jamais builder la prod à la main

`--base=/plotter/` et `VITE_API_URL=/plotter/api` sont **deux** réglages, et l'oubli du second ne se voit pas : la page s'affiche parfaitement et **tous** les appels API partent en 404 (`GET /api/session` au lieu de `/plotter/api/session`). Arrivé le 10/08, prod cassée ~14 h. Toujours passer par `promote-exp-to-prod.ps1` (§7), qui pose les deux.

Depuis, `npm run build` lance automatiquement `scripts/check-build.mjs` (npm `postbuild`) : il compare la base écrite dans `dist/index.html` à l'URL d'API compilée dans le bundle et **rejette le build** (code 1) en cas d'écart, en affichant la commande correcte. Il vérifie aussi l'absence d'import nu (page blanche). ⚠️ Le rejet intervient **après** l'écriture du `dist/` : un build refusé laisse un `dist/` cassé — relancer immédiatement avec la commande affichée.

### ⚠️ Un uvicorn dev peut squatter le port de la prod

`start-plotter.ps1` (dev only) lance `uvicorn --reload --host 0.0.0.0 --port 9099` — **le port de la prod**. S'il tourne encore, le service NSSM
`CSVPlotter` ne peut pas prendre le port : il affiche `Running` mais c'est le processus **dev** qui sert `/plotter/api`, avec `--reload`, bindé sur
le LAN au lieu de `127.0.0.1`, et **sans les variables d'environnement du service** (donc les sessions atterrissent sous `/tmp/csv-plotter-uploads`
au lieu de `C:\ProgramData\Plotter\uploads`).

Diagnostic — comparer le `upload_dir` renvoyé par le health à celui attendu, puis identifier le propriétaire du port :
```powershell
Invoke-RestMethod 'http://127.0.0.1:9099/api/health'      # upload_dir doit être C:\ProgramData\Plotter\uploads
$c = Get-NetTCPConnection -LocalPort 9099 -State Listen
Get-CimInstance Win32_Process -Filter "ProcessId = $($c.OwningProcess)" | Select-Object CommandLine
```
Une ligne contenant `--reload` = c'est le dev. Le tuer demande **deux passes** : `uvicorn --reload` a un worker `multiprocessing` qui **hérite de la
socket d'écoute** du parent, donc la table TCP continue d'afficher le PID du parent mort tant que l'enfant vit.
```powershell
taskkill /PID <pid_parent> /T /F
taskkill /PID <pid_worker> /T /F     # celui dont la CommandLine contient spawn_main(parent_pid=<pid_parent>)
Start-Service CSVPlotter
```
