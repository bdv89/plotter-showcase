# Baseline Correction - Guide d'utilisation

## Fonctionnalité

La correction de baseline permet de soustraire le fond (background) d'un signal pour isoler les pics d'intérêt, typiquement utilisé en diffraction X (XRD).
Plusieurs méthodes sont disponibles:
- SNIP (Statistics-sensitive Nonlinear Iterative Peak-clipping)
- arPLS (Asymmetrically Reweighted Penalized Least Squares)
- AsLS (Asymmetric Least Squares)
- Polynomial (héritée, simple fit masqué)

## Comment l'utiliser

### 1. Dans la fenêtre de Plot (Processing)

1. **Charger et afficher les données** :
   - Sélectionnez vos fichiers et colonnes dans l'interface principale
   - Cliquez "Plot Selection" pour ouvrir la fenêtre de plot

2. **Ouvrir le menu Processing** :
   - Dans la fenêtre de plot, cliquez sur le bouton "Processing"
   - Une fenêtre flottante s'ouvre avec plusieurs options de traitement

3. **Activer la Baseline Correction** :
   - Cochez "Enable" dans la section "Baseline Correction"
   - Choisissez la méthode et ses paramètres:
     - SNIP: `K` (itérations/largeur minimale de pics), Transform (sqrt/log)
       - Preset XRD: K≈12, Transform=sqrt
     - arPLS: `λ` (1e6 par défaut)
     - AsLS: `λ` (lissage) + `p` (asymétrie, 1e-3 par défaut)
     - Polynomial (legacy): Degree + Peak Sensitivity

4. **Prévisualisation en direct** :
   - Le graphique se met à jour automatiquement quand vous modifiez les paramètres
   - Vous pouvez combiner avec d'autres traitements (Smoothing, Denoise, Normalize)

5. **Finaliser** :
   - Une fois satisfait du résultat, laissez la correction active
   - Utilisez "Reset" pour désactiver tous les traitements

## Exemple de workflow XRD

```
1. Charger fichier XRD brut (2theta vs Intensity)
2. Plot Selection → fenêtre de plot s'ouvre
3. Cliquer "Processing" → activer Baseline Correction
   - Degree: 3
   - Sensitivity: 2.0
4. Ajuster en temps réel jusqu'à résultat satisfaisant
5. Optionnel : ajouter Smoothing si signal bruité
6. Exporter ou analyser directement
```

## Méthodes (résumé maths)

- SNIP: travaille sur ỹ = sqrt(y) ou log(y+ε); à chaque itération k, s[i] = min(s[i], 0.5(s[i-k]+s[i+k])) pour i∈[k..N-k]; baseline = inv_transform(s(K)).
- AsLS: minimise (y−z)^T W (y−z) + λ||Dz||², avec poids asymétriques w = p si y>z sinon 1−p.
- arPLS: similaire à AsLS mais poids réestimés à partir des résidus négatifs (plus stable).
- Polynomial (legacy): détection de pics, masquage, fit polynomial, soustraction.

## Dépannage

**Problème : Baseline trop agressive (enlève des pics)**
- SNIP ↘ K
- AsLS ↗ p (moins asymétrique)
- arPLS/AsLS ↘ λ

**Problème : Baseline pas assez forte (reste du background)**
- SNIP ↗ K
- arPLS/AsLS ↗ λ

**Problème : Erreur "Need at least X points"**
- Votre signal est trop court ou a trop de pics
- ↘ Diminuer le degré polynomial
- ↘ Diminuer la sensibilité

## Avantages de l'intégration Processing

✓ **Prévisualisation en temps réel** : Voir l'effet immédiatement sans modifier les fichiers
✓ **Ajustement interactif** : Tester différents paramètres en live
✓ **Pipeline combinable** : Enchainer baseline + smoothing + normalize
✓ **Non-destructif** : Les fichiers CSV originaux ne sont jamais modifiés
✓ **Réversible** : Décocher "Enable" ou cliquer "Reset" pour annuler

## Code source

- `baseline_correction.py` : Méthodes SNIP, arPLS, AsLS, Polynomial
- `plot_processing_window.py` : Intégration Processing (méthode `_proc_baseline`)
- `test_baseline.py` : Script de test standalone

## Note technique

Implémentation POC : simple, directe, efficace.
- Pas de dépendances externes au-delà de numpy/scipy (déjà utilisés)
- Traitement en mémoire dans le pipeline de données (non-destructif)
- Reproductible : mêmes paramètres → mêmes résultats
- Live preview : mise à jour instantanée du graphique
