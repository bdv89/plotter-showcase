"""
Test direct du traçage CSV sans passer par le GUI
Simule exactement le chemin de code de l'application
"""
import sys
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Backend non-interactif
import matplotlib.pyplot as plt
from data_manager import LazyDataFrame

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("="*70)
print("TEST DE TRAÇAGE CSV DIRECT")
print("="*70)

# Fichier à tester
csv_path = 'samples/Bain_Au_pour_IRE/Raw_data/KAu(CN)2 8g.L-1 ss agit 55°C 25mV b.s_02_CV_C04.csv'
print(f"\n[FILE] Fichier teste: {csv_path}")

if not os.path.exists(csv_path):
    print(f"[ERROR] Fichier introuvable!")
    sys.exit(1)

# Afficher les premières lignes brutes du CSV
print("\n" + "="*70)
print("CONTENU BRUT DU CSV (5 premières lignes)")
print("="*70)
with open(csv_path, 'r', encoding='utf-8') as f:
    for i in range(5):
        line = f.readline()
        print(f"Ligne {i}: {line.rstrip()}")

# ÉTAPE 1: Chargement avec LazyDataFrame (même que GUI)
print("\n" + "="*70)
print("ÉTAPE 1: CHARGEMENT AVEC LazyDataFrame")
print("="*70)
try:
    lazy_df = LazyDataFrame(csv_path, delimiter=';', header_line=0, units_line=None)
    print("[OK] LazyDataFrame cree avec succes")
    print(f"   Délimiteur: ';'")
    print(f"   Header line: 0")
except Exception as e:
    print(f"[ERROR] lors de la creation LazyDataFrame: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ÉTAPE 2: Chargement des données
print("\n" + "="*70)
print("ÉTAPE 2: CHARGEMENT DES DONNÉES")
print("="*70)
try:
    df = lazy_df.data
    print(f"[OK] Donnees chargees: {df.shape[0]} lignes x {df.shape[1]} colonnes")
    print(f"\nColonnes disponibles: {list(df.columns)}")
except Exception as e:
    print(f"[ERROR] lors du chargement des donnees: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ÉTAPE 3: Inspection des types de données
print("\n" + "="*70)
print("ÉTAPE 3: TYPES DE DONNÉES APRÈS CONVERSION")
print("="*70)
print(f"{'Colonne':<25} {'Type':<15} {'Exemple (ligne 1)'}")
print("-"*70)
for col in df.columns[:10]:  # Premières 10 colonnes
    dtype = df[col].dtype
    sample = df[col].iloc[0] if len(df) > 0 else 'N/A'
    print(f"{col:<25} {str(dtype):<15} {sample}")

# ÉTAPE 4: Test spécifique des colonnes de traçage
print("\n" + "="*70)
print("ÉTAPE 4: VÉRIFICATION DES COLONNES DE TRAÇAGE")
print("="*70)

# Pour une courbe CV (voltamétrie cyclique), on trace Courant vs Voltage
x_col = 'Ewe/V'      # Voltage (X axis)
y_col = '<I>/mA'     # Courant (Y axis)

print(f"\nColonne X: {x_col}")
print(f"  Type: {df[x_col].dtype}")
print(f"  Premières valeurs:")
for i in range(min(5, len(df))):
    val = df[x_col].iloc[i]
    print(f"    [{i}] {val} (type: {type(val).__name__})")

print(f"\nColonne Y: {y_col}")
print(f"  Type: {df[y_col].dtype}")
print(f"  Premières valeurs:")
for i in range(min(5, len(df))):
    val = df[y_col].iloc[i]
    print(f"    [{i}] {val} (type: {type(val).__name__})")

# Vérification: sont-ils numériques ?
x_is_numeric = pd.api.types.is_numeric_dtype(df[x_col])
y_is_numeric = pd.api.types.is_numeric_dtype(df[y_col])

print(f"\n  X est numerique: {'[OK] OUI' if x_is_numeric else '[FAIL] NON'}")
print(f"  Y est numerique: {'[OK] OUI' if y_is_numeric else '[FAIL] NON'}")

if not x_is_numeric or not y_is_numeric:
    print("\n[WARNING] PROBLEME DETECTE: Les colonnes ne sont pas numeriques!")
    print("\n  Tentative de conversion manuelle...")

    # Essai de conversion manuelle
    if not x_is_numeric:
        try:
            df[x_col] = pd.to_numeric(df[x_col].astype(str).str.replace(',', '.'), errors='coerce')
            print(f"  [OK] Colonne X convertie manuellement")
        except Exception as e:
            print(f"  [ERROR] Echec conversion X: {e}")

    if not y_is_numeric:
        try:
            df[y_col] = pd.to_numeric(df[y_col].astype(str).str.replace(',', '.'), errors='coerce')
            print(f"  [OK] Colonne Y convertie manuellement")
        except Exception as e:
            print(f"  [ERROR] Echec conversion Y: {e}")

# ÉTAPE 5: Test de traçage matplotlib
print("\n" + "="*70)
print("ÉTAPE 5: TEST DE TRAÇAGE MATPLOTLIB")
print("="*70)

try:
    # Créer le plot (même code que plot_canvas.py)
    fig, ax = plt.subplots(figsize=(10, 6))

    # Tracer les données (limite à 1000 points pour le test)
    n_points = min(1000, len(df))
    x_data = df[x_col].iloc[:n_points]
    y_data = df[y_col].iloc[:n_points]

    print(f"  Traçage de {n_points} points...")
    print(f"  Range X: {x_data.min()} à {x_data.max()}")
    print(f"  Range Y: {y_data.min()} à {y_data.max()}")

    ax.plot(x_data, y_data, linewidth=1.5)
    ax.set_xlabel(x_col + ' (Voltage)', fontsize=12)
    ax.set_ylabel(y_col + ' (Courant)', fontsize=12)
    ax.set_title('Courbe CV - Test de traçage CSV', fontsize=14)
    ax.grid(True, alpha=0.3)

    # Sauvegarder
    output_path = 'test_plot_output.png'
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"\n[SUCCESS] Plot sauvegarde: {output_path}")
    print(f"   Taille du fichier: {os.path.getsize(output_path)} bytes")

except Exception as e:
    print(f"\n[ERROR] lors du tracage matplotlib: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
print("TEST TERMINE AVEC SUCCES")
print("="*70)
print(f"\nVoir le resultat dans: test_plot_output.png")
