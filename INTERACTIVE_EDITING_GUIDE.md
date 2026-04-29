# Guide d'édition interactive des graphiques

## Vue d'ensemble

Le système d'édition interactive permet de modifier les éléments du graphique directement en cliquant dessus avec le **clic droit**.

## Fonctionnalités

### 🖱️ Clic droit sur les éléments

| Élément cliqué | Dialogue ouvert | Options disponibles |
|----------------|-----------------|---------------------|
| **Titre du graphique** | Éditer le titre | - Texte du titre<br>- Police<br>- Taille de police |
| **Label axe X** | Éditer l'axe X | - Titre de l'axe<br>- Échelle (linéaire, log, etc.)<br>- Limites min/max personnalisées |
| **Label axe Y (gauche)** | Éditer l'axe Y | - Titre de l'axe<br>- Échelle<br>- Limites min/max |
| **Label axe Y2 (droite)** | Éditer l'axe Y2 | - Titre de l'axe<br>- Échelle<br>- Limites min/max |
| **Légende** | Éditer la légende | - Position<br>- Police<br>- Taille<br>- Nombre de colonnes |
| **Courbe (ligne)** | Éditer l'épaisseur | - Épaisseur globale de toutes les lignes |
| **Zone vide du graphique** | Éditer les grilles | - Grilles majeures/mineures X et Y<br>- Styles de lignes<br>- Opacité<br>- Couleur |

## Zones de clic

Les zones de clic sont **élargies à 15-20 pixels** autour des éléments pour faciliter l'interaction. Vous n'avez pas besoin de cliquer exactement sur le texte.

## Architecture technique

### Fichiers modifiés

1. **plot_interactive_edit.py** (nouveau)
   - Implémentation complète avec picker events matplotlib
   - 5 dialogues d'édition : TitleEditDialog, AxisEditDialog, LegendEditDialog, GridEditDialog, LineWidthEditDialog
   - Utilise l'approche recommandée par matplotlib (picker events)

2. **plot_canvas.py** (modifié)
   - Ajout de `_reapply_pickers_if_needed()` appelée après chaque draw
   - Garantit que les éléments restent cliquables après redessins

3. **plot_window.py** (modifié)
   - Appel de `setup_interactive_editing()` lors de l'initialisation

### Méthode utilisée : Picker Events

Au lieu d'utiliser la méthode `contains()` peu fiable, nous utilisons le système de **picker events** de matplotlib :

```python
# Configuration des pickers (une fois)
canvas.ax.title.set_picker(15)  # Rayon de 15 pixels
canvas.ax.xaxis.label.set_picker(15)
# ... pour tous les éléments

# Gestionnaire d'événements
def on_pick(event):
    artist = event.artist  # Élément cliqué identifié automatiquement
    if artist == canvas.ax.title:
        _edit_title(canvas, plot_window)
    # ...
```

**Avantages** :
- ✅ Détection fiable des clics
- ✅ Gestion automatique des transformations de coordonnées
- ✅ Zones de clic élargies configurables
- ✅ Méthode standard recommandée par matplotlib

### Pourquoi la version précédente ne marchait pas

L'implémentation initiale avait plusieurs problèmes :

1. **`if event.inaxes is None: return`** (ligne 309)
   - Bloquait TOUS les clics sur titre/axes/légende qui sont **en dehors** de la zone de données

2. **Utilisation de `contains()`** sans garantie de rendu
   - Nécessite que la figure soit dessinée
   - Zones de clic très petites
   - Problèmes de transformations de coordonnées

3. **Clic droit grilles dans code mort**
   - La logique était après le return, donc jamais exécutée

## Workflow d'utilisation

1. Créer un plot dans l'application CSV Plotter
2. Dans la fenêtre PLOT :
   - Clic droit sur titre → modifier le titre
   - Clic droit sur label "X axis" → modifier l'axe X
   - Clic droit sur label "Y axis" → modifier l'axe Y
   - Clic droit sur la légende → modifier position/style légende
   - Clic droit sur une courbe → modifier épaisseur globale
   - Clic droit dans zone vide → modifier les grilles

3. Les modifications sont appliquées immédiatement au graphique

## Notes de développement

- Les pickers sont **réappliqués automatiquement** après chaque `draw()` pour garantir que les éléments restent cliquables
- Import dynamique dans `_reapply_pickers_if_needed()` pour éviter les dépendances circulaires
- Gestion d'erreurs silencieuse pour ne pas casser le plotting si le module n'est pas disponible
- Tous les dialogues utilisent les mêmes composants que la fenêtre "Plot Style Options" existante
