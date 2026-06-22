# Peak Fitting Feature - Guide d'utilisation

## 🎯 Vue d'ensemble

Le système de fitting multi-pics permet d'analyser automatiquement des spectres XRD/spectroscopie avec extraction de :
- **FWHM** (largeur à mi-hauteur)
- **Position du pic (2θ)**
- **Amplitude**
- **Aire sous le pic**
- **Paramètres de fit** (σ pour Gauss, σ + γ pour Voigt)

## 📋 Prérequis

### Dépendance requise : scipy
```bash
pip install scipy
```

Le module scipy est nécessaire pour :
- `scipy.signal.find_peaks` : détection automatique des pics
- `scipy.optimize.curve_fit` : fitting Gauss/Voigt
- `scipy.special.voigt_profile` : profil de Voigt

## 🚀 Utilisation

### 1. Charger vos données
- Sélectionner un dossier ou importer des fichiers CSV/Excel
- Cocher les fichiers à analyser
- Choisir les colonnes X (2θ) et Y (Intensité)

### 2. Ouvrir la fenêtre Processing
- Cliquer sur "Plot Selection" pour ouvrir la fenêtre de plot
- Dans la fenêtre de plot, cliquer sur "Processing" (ou équivalent)
- La fenêtre flottante "Processing" s'ouvre

### 3. Configurer le fitting
Dans la section **"Peak Fitting"** :

#### Paramètres principaux
- **Enable** : Activer le fitting
- **Method** :
  - `Gauss` : Fitting gaussien (rapide, bon pour pics symétriques)
  - `Voigt` : Profil de Voigt (plus précis, pics asymétriques)

#### Paramètres de détection
- **Prominence** (0.01-1.0) :
  - Sensibilité de détection (fraction du max)
  - **0.1** = détecte les pics > 10% du pic max
  - Augmenter si trop de faux positifs (bruit détecté)
  - Diminuer si pics manqués

- **Min dist** (points) :
  - Distance minimale entre deux pics (en nombre de points)
  - **10** = par défaut
  - Augmenter si pics séparés, diminuer si pics rapprochés

#### Indicateurs visuels
- **Show peak markers** : Affiche des **points rouges** sur chaque pic détecté
- **Show peak IDs** : Affiche les **numéros** des pics au-dessus des marqueurs

### 4. Lancer l'analyse
- Cliquer sur **"Apply"** ou modifier un paramètre (mise à jour live)
- Le nombre de pics détectés s'affiche :
  - **`Peaks: 12`** (en vert si pics détectés)
  - **`Peaks: 0 (none detected)`** (en orange si aucun pic)
- Les éléments visuels apparaissent sur le graphique :
  - **Courbes fittées** : lignes pointillées `--` (70% opacité)
  - **Points rouges** : marqueurs sur chaque pic
  - **Numéros** : ID des pics en rouge au-dessus des marqueurs

### 5. Consulter les résultats
- Cliquer sur **"View Table"** pour ouvrir la table des résultats
- Table affichant pour chaque pic :
  - **ID** : Numéro du pic
  - **2θ** : Position du pic (en degrés ou unités X)
  - **FWHM** : Largeur à mi-hauteur
  - **Amplitude** : Hauteur du pic
  - **Area** : Aire sous le pic (intégrale)
  - **Sigma** : Largeur gaussienne
  - **Gamma** : Largeur lorentzienne (Voigt uniquement)

### 6. Exporter les résultats
Dans la fenêtre de la table :
- Cliquer sur **"Export CSV"**
- Choisir l'emplacement
- Format : CSV avec séparateur `;`

Exemple de fichier exporté :
```csv
peak_id;2theta;fwhm;amplitude;area;sigma;gamma
1;28.4523;0.2341;1250.34;293.45;0.0994;
2;34.1234;0.1892;987.21;187.23;0.0803;
3;40.8345;0.3012;1543.12;465.78;0.1279;
```

## 💾 Sauvegarde dans .db (SQLite)

Les résultats de fitting sont **automatiquement sauvegardés** dans les fichiers `.db` (SQLite) :

> ✅ **Bug Fix** (Dec 2025): Les fit_results sont maintenant correctement **restaurés** après load. Auparavant, ils étaient sauvegardés mais jamais rechargés.

### Structure interne
```python
{
    'csv_files': [...],
    'processing_settings': {...},
    'fit_results': {
        'file1.csv': {
            'method': 'gauss',
            'n_peaks': 12,
            'peaks': [
                {'peak_id': 1, '2theta': 28.45, 'fwhm': 0.234, ...},
                {'peak_id': 2, '2theta': 34.12, 'fwhm': 0.189, ...},
                ...
            ],
            'x_column': '2theta',
            'y_column': 'Intensity'
        },
        'file2.csv': {...}
    }
}
```

### Workflow complet
1. Configurer le fitting → **Apply**
2. **Save Pool** : sauvegarde données + résultats fitting
3. **Load Pool** : restaure tout (données, settings, résultats)
4. Les résultats restent accessibles via **"View Table"**

## 🔧 Dépannage

### Aucun pic détecté (`Peaks: 0`)
**Causes possibles :**
- Prominence trop élevée → diminuer à 0.05 ou 0.01
- Données trop bruitées → activer **Smoothing** avant le fitting
- Baseline non corrigée → activer **Baseline** (SNIP ou arPLS)

**Solution :**
```
Order recommandé :
#1 Baseline (SNIP)
#2 Smoothing (window: 5-10)
#3 Peak Fitting
```

### Trop de pics détectés (faux positifs)
**Solution :**
- Augmenter **Prominence** à 0.2 ou 0.3
- Augmenter **Min dist** à 20-30 points
- Activer **Denoise** (Z-score outliers)

### Fitting échoue (`Peaks: --` après Apply)
**Causes possibles :**
- scipy non installé → `pip install scipy`
- Colonnes X/Y mal sélectionnées
- Données non numériques

**Vérifier :**
- Console Python pour messages d'erreur
- Colonnes X et Y bien sélectionnées dans l'UI principale

### Pics chevauchants mal fittés
**Solution :**
- Utiliser **Voigt** au lieu de Gauss (plus flexible)
- Diminuer **Min dist** pour permettre détection de pics proches
- Note : le fit actuel est *local* (un pic à la fois)

## 📊 Ordre de traitement recommandé

Pour des spectres XRD typiques :

```
1. Baseline Correction (SNIP, K=12)
2. Smoothing (window=5)
3. Peak Fitting (Gauss, prominence=0.1)
```

**Ordre modifiable** avec les boutons ↑↓ dans chaque section.

## 🎨 Affichage graphique

### Éléments visuels sur le plot

1. **Courbe brute** : Ligne continue (couleur d'origine)
2. **Courbe fittée** : Ligne pointillée `--` (même couleur, 70% opacité)
3. **Marqueurs de pics** : Points rouges (●) sur chaque pic détecté
4. **Numéros de pics** : ID en rouge dans des bulles blanches au-dessus des pics
5. **Légende** : Affiche "(fit)" après le nom du fichier

### Schéma visuel
```
Intensité
    |     ①           ②
    |     •           •       ← Bulles numérotées + points rouges
    |    /│\         /│\
    |   / │ \       / │ \
    |  /  │  \     /  │  \
    | /...│...\.../.  │   \   ← Ligne pointillée (fit)
    |/____|___\_/_____|____\__ 2θ

Légende:
■ Sample_1 ——————
┊ Sample_1 (fit) ┄┄┄
```

### Contrôle des indicateurs
Les checkboxes dans la section "Peak Fitting" permettent d'activer/désactiver :
- `[ ] Show peak markers` : Afficher/masquer les points rouges
- `[ ] Show peak IDs` : Afficher/masquer les numéros

Exemple :
```
Sample_1 ——————— (courbe brute)
Sample_1 (fit) - - - - - (courbe fittée)
```

## 📁 Fichiers modifiés

| Fichier | Rôle |
|---------|------|
| `data_pipeline.py` | Processor `create_fit_multi_peaks_processor()` |
| `plot_processing_window.py` | UI section Peak Fitting |
| `peak_results_dialog.py` | Dialog de visualisation des résultats |
| `storage_manager.py` | Sauvegarde/chargement fit_results |
| `main_app.py` | Collecte et persistance des résultats |
| `plot_canvas.py` | Affichage des courbes fittées |

## 🔬 Algorithme détaillé

### Étape 1 : Détection automatique
```python
scipy.signal.find_peaks(y, prominence=0.1*y_max, distance=10)
→ Liste d'indices des pics
```

### Étape 2 : Fit local par pic
Pour chaque pic détecté :
1. Fenêtre locale : ±4σ autour du pic
2. Guess initial : `[amplitude=y_max, center=x_peak, sigma=width/2.355]`
3. Fit avec `scipy.optimize.curve_fit`
4. Calcul FWHM = 2.355 × σ (Gauss) ou formule Voigt
5. Calcul aire = amplitude × σ × √(2π)

### Étape 3 : Agrégation
- Somme des courbes fittées → colonne `gauss_fit` ou `voigt_fit`
- Stockage résultats dans `df.attrs['fit_results']`

## ⚠️ Limitations actuelles

1. **Pics non chevauchants** : Le fit est local, pas global simultané
2. **1 fichier à la fois** : Les résultats affichés sont ceux du dernier fichier traité
3. **Pas de fit manuel** : Pas de sélection interactive des pics (automatique uniquement)

Ces limitations correspondent au cas d'usage typique (1-20 pics bien séparés).

## 🚀 Prochaines améliorations possibles

- [ ] Export multi-fichiers consolidé (tous les pics de tous les fichiers)
- [ ] Fit global pour pics chevauchants
- [ ] Mode picking manuel (clic sur le graphique)
- [ ] Contraintes sur FWHM min/max
- [ ] Profils supplémentaires (Lorentz, Pearson VII)

---

**Questions ou bugs ?** Voir `CLAUDE.md` pour les guidelines de développement.
