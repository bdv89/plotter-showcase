"""Test script to verify CSV comma-to-dot conversion"""
import pandas as pd
import sys
from data_manager import LazyDataFrame

# Test avec le fichier CSV problématique
csv_path = 'samples/Bain_Au_pour_IRE/Raw_data/KAu(CN)2 8g.L-1 ss agit 55°C 25mV b.s_02_CV_C04.csv'
print(f"Testing file: {csv_path}\n")

lazy_df = LazyDataFrame(csv_path, delimiter=';', header_line=0, units_line=None)

# Charge les données
df = lazy_df.data

# Affiche les types des colonnes
print('=== Types des colonnes ===')
for col in df.columns[:8]:  # Premières 8 colonnes
    print(f'{col:20s}: {df[col].dtype}')

# Affiche les premières valeurs de colonnes numériques pour vérifier
print('\n=== Premières valeurs de "time/s" ===')
print(df['time/s'].head(5))
print(f'\nType de la première valeur: {type(df["time/s"].iloc[0])}')
print(f'Valeur: {df["time/s"].iloc[0]}')

print('\n=== Premières valeurs de "Ewe/V" ===')
print(df['Ewe/V'].head(5))
print(f'\nType de la première valeur: {type(df["Ewe/V"].iloc[0])}')

# Test si on peut plotter (conversion en float)
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot(df['time/s'].head(100), df['Ewe/V'].head(100))
    print('\n✅ Plot test successful - data is numeric!')
    plt.close(fig)
except Exception as e:
    print(f'\n❌ Plot test failed: {e}')
