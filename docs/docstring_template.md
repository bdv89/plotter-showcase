# Gabarit de docstrings (Python, LLM‑friendly)

"""
Résumé en une ligne: que fait la fonction/méthode.

Parameters
----------
param1 : type
    Rôle, unités, contraintes (ex: non vide, UTC, Hz).
param2 : Optional[type]
    Valeur par défaut, sémantique si None.

Returns
-------
type
    Description précise; structure (colonnes DataFrame, schéma JSON), unités.

Raises
------
SpecificError
    Conditions déclenchantes, message attendu.

Preconditions
-------------
- Hypothèses vraies avant l’appel (fichier existant, colonnes présentes, etc.).

Postconditions
--------------
- Garanties après succès (idempotence, tri conservé, NA gérés, etc.).

Side Effects
------------
- I/O, cache, logs.

Performance
-----------
- Complexité attendue, limites (taille CSV, mémoire), vectorisation.

Thread-safety
-------------
- Sûr / non sûr; usage prévu (RLock par session, worker borné par HEAVY_SEM, etc.).

Examples
--------
>>> # df: pandas DataFrame prêt à tracer
>>> traces = build_plot_traces(df, x_col="time", y_cols=["value"])

See Also
--------
- web/backend/core/data_loader.py — parsing CSV/Excel (décimales européennes)
- web/backend/core/pipeline.py#DataPipeline.process_data
- web/backend/api/plot.py — construction des traces Plotly
"""

## Exemple minimal appliqué

def apply(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Applique les processeurs par défaut sur un DataFrame (immutability: ne modifie pas df en place).

    Parameters
    ----------
    df : pd.DataFrame
        Colonnes attendues: libre; NaN permis. Index préservé.

    Returns
    -------
    pd.DataFrame
        Nouveau DataFrame transformé; même index; colonnes normalisées.

    Raises
    ------
    ValueError
        Si df est vide et que 'require_non_empty' est activé.

    Postconditions
    --------------
    - Longueur identique ou réduite (filtres). Types stables.

    Side Effects
    ------------
    - Aucun (pas d’I/O).
    """
    ...
