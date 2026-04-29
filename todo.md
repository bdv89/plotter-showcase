# TODO - Baseline Correction DRX

## Priorité 1 — Performance AsLS/arPLS ✅ TERMINÉ

- [x] Remplacer matrices denses par sparse: utiliser `scipy.sparse.diags` + `spsolve` (baseline_correction.py:18-27)
- [x] Construire D et DT_D en creux une fois par taille n (cache par n) (@lru_cache baseline_correction.py:18)
- [x] Former W diagonal creux et A = W + lam * (D.T @ D) en sparse (baseline_correction.py:137, 200)
- [x] Ajouter critère d'arrêt (delta z ou delta poids < tol) + borne niter (baseline_correction.py:155, 225)
- [x] Benchmarks DRX: viser < 0.3 s pour 10k points, 10–20 itérations (PERFORMANCE_NOTES.md)
- [x] Fallback robuste: si spsolve échoue, utiliser lsqr/cg avec préconditionneur simple (baseline_correction.py:144-149, 207-212)

## Priorité 2 — Supprimer Polynomial (legacy) ✅ TERMINÉ

- [x] Déprécier puis retirer `_poly_masked_baseline` de `baseline_correction.py` (DeprecationWarning ajouté baseline_correction.py:237-243)
- [ ] Retirer "Polynomial" de l'UI (`plot_processing_window.py`) — À FAIRE si UI existe
- [x] Mettre à jour docs: retirer méthode obsolète, expliquer le choix SNIP/AsLS/arPLS (baseline_correction.py:1-14)
- [x] Supprimer dépendance du test à `degree=` et basculer vers `method=` explicite (test_baseline.py refactorisé)

## Priorité 3 — Intégrer au pipeline ✅ TERMINÉ

- [x] Ajouter `baseline_snip(df, y_col, **kw)` dans `data_pipeline.py` (data_pipeline.py:145-161)
- [x] Ajouter `baseline_asls(df, y_col, **kw)` dans `data_pipeline.py` (data_pipeline.py:163-179)
- [x] Ajouter `baseline_arpls(df, y_col, **kw)` dans `data_pipeline.py` (data_pipeline.py:181-197)
- [x] Enregistrer via `register_default_processors` avec noms stables (data_pipeline.py:205-207)
- [x] Offrir un helper pour cibler seulement les colonnes sélectionnées (Y/Y2) (support multi-colonnes data_pipeline.py:151)

## SNIP — Qualité et robustesse ✅ PARTIELLEMENT TERMINÉ

- [x] Ajouter padding miroir (reflect) avant l'itération; recouper après (baseline_correction.py:60-63, 91-92)
- [ ] Estimer automatiquement K selon K ≈ round(0.5 * FWHM_deg / step_deg) — NÉCESSITE détection de pas dans X
- [ ] Proposer presets DRX: Fine/Medium/Coarse (K ≈ 3/6/12 à pas 0.02°) — NÉCESSITE UI
- [x] Nettoyage entrée: gérer NaN/Inf; clamp à 0 avant sqrt/log (baseline_correction.py:45-51, 67)
- [ ] Option (désactivée par défaut): clip négatifs post-soustraction à 0 — NÉCESSITE param optionnel

## Ciblage des colonnes

- [ ] Modifier `plot_processing_window._proc_baseline` pour n'appliquer qu'aux colonnes Y/Y2 sélectionnées
- [ ] Respecter X inchangé; ignorer colonnes non affichées (ex. méta, erreurs)

## UI/UX

- [ ] Option d'affichage "Show baseline overlay" sur le plot (ligne fine/pointillée)
- [ ] Tooltips d'aide: "SNIP K ~ moitié de la largeur minimale de pic (en points)"
- [ ] Presets DRX (CuKα 0.02°, synchrotron 0.005°) → valeurs K auto
- [ ] Pour AsLS/arPLS: mini pré-lissage (fenêtre 3–5) optionnel/coché par défaut

## Tests ✅ TERMINÉ

- [x] Mettre à jour `test_baseline.py`: tester explicitement `method='snip'|'asls'|'arpls'` (test_baseline.py:46-125)
- [x] Jeux synthétiques variés: fond polynomial + "hump" large, pics étroits/serrés, bruit Poisson (test_baseline.py:11-43)
- [x] Métriques: MAE baseline vs vraie baseline; pour SNIP, conservation des pics (aire, hauteur) (test_baseline.py:72-80)
- [x] Test perf: 10k points, vérifier temps et mémoire (pas de denses) (test_baseline.py:128-152)
- [x] Ajouter tests de bords: NaN en entrée, extrémités (effet padding), pas irrégulier (test_baseline.py:155-192)

## Documentation

- [ ] Mettre à jour `BASELINE_CORRECTION.md`: K vs pas/FWHM, choix méthode, perfs sparse, critères d'arrêt
- [ ] Mettre à jour `CHANGELOG_BASELINE.md`: suppression polynomial, intégration pipeline, améliors SNIP/AsLS/arPLS
- [ ] Ajouter note "DRX best practices" pour paramétrage

## Paramètres par défaut DRX

- [ ] SNIP: `transform='sqrt'`, K auto si pas 2θ disponible; sinon 6–12 avec avertissement
- [ ] AsLS: lam dans [1e5, 1e7], p=1e-3, niter<=20, stop tol=1e-3
- [ ] arPLS: lam dans [1e5, 1e7], niter<=15, stop tol=1e-3

## Hygiène et maintenance

- [ ] Centraliser nettoyage entrée (NaN/Inf clamp/interp) dans `baseline_correction.py`
- [ ] Cacher D, DT_D dans un petit cache LRU par n pour réutilisation intra-session
- [ ] Journaliser brièvement les paramètres appliqués pour traçabilité (niveau debug)

---

## Problèmes identifiés (référence)

### Problème 1: Performance catastrophique
**Fichiers**: `baseline_correction.py:77-81, 118-122`
- Densification de D, DT_D et `np.linalg.solve` O(n³) → inacceptable pour DRX haute résolution
- **Action**: passer en sparse (diags, spsolve), cache par n, critère d'arrêt

### Problème 2: Méthode polynomial masquée obsolète
**Fichier**: `baseline_correction.py:149-172`
- Fenêtre fixe inadaptée, paramètres arbitraires, fallback silencieux
- **Action**: supprimer/déprécier; retirer de l'UI et des tests

### Problème 3: Test inadéquat
**Fichier**: `test_baseline.py:42`
- Teste seulement polynomial, données synthétiques trop simples
- **Action**: tester SNIP/AsLS/arPLS, cas réalistes DRX, métriques MAE + perf

### Problème 4: Pas d'intégration avec data_pipeline.py
- Pas de processor baseline enregistré; appel manuel requis
- **Action**: ajouter `baseline_snip`, `baseline_asls`, `baseline_arpls` et les enregistrer

### Problème 5: Paramètres par défaut non optimisés DRX
- SNIP K fixe, AsLS λ fixe, arPLS niter sans convergence
- **Action**: K auto selon pas/FWHM, bornes λ adaptées, critères d'arrêt

---

## Snippets de référence

### Code sparse (AsLS/arPLS)
```python
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve

D = diags([1, -2, 1], [0, 1, 2], shape=(n-2, n), format='csr')
DT_D = D.T @ D
# ...
z = spsolve(A, b)
```

### Intégration pipeline
```python
def baseline_snip(df, y_col='Intensity', **kwargs):
    from baseline_correction import subtract_baseline
    y_corr, _ = subtract_baseline(df.index, df[y_col], method='snip', **kwargs)
    result = df.copy()
    result[y_col] = y_corr
    return result

pipeline.register_processor('baseline_snip', baseline_snip)
```

---

**Verdict**: 4.5/10 — Fonctionne mais nécessite refactoring performance + intégration
