# Docs legacy (app desktop PyQt5 archivée)

Ces documents décrivent l'**ancienne application desktop PyQt5**, retirée de
l'arbre et archivée sous le tag git **`legacy-desktop-2026-06-21`**.

Ils ne s'appliquent **pas** à la web app actuelle (`web/`). Conservés pour
référence historique uniquement. Pour le code correspondant :

```bash
git show legacy-desktop-2026-06-21        # voir l'archive
git checkout legacy-desktop-2026-06-21    # récupérer le code desktop
```

## Contenu

- `THINK.md` — réflexion de conception « Multi-Panel Grid View » (PyQt5/matplotlib), jamais portée sur le web.
- `dep.md` — diagramme Mermaid des dépendances entre modules desktop (`launcher.py`, `main_app.py`, `data_manager.py`, `plot_window.py`…).
- `seq-load-and-plot.md` — séquence Mermaid « charger → traiter → tracer » de l'app desktop (QThread/QMainWindow).
- `DENOISING_INTEGRATION.md`, `FITTING_GUIDE.md`, `INTERACTIVE_EDITING_GUIDE.md`, `RELEASE.md` — guides desktop.

> Architecture **web actuelle** : voir [`../../README.md`](../../README.md) et [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md).
