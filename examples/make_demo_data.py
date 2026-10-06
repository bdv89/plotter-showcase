"""Generate the SYNTHETIC demo dataset used for the README screenshots.

Scenario (illustrative only, not measured data): in-situ internal stress of
electroless Ni-P deposits at three bath pH values, three replicates each.
Low pH -> high phosphorus -> compressive stress; high pH -> tensile stress.

Two export styles are mixed on purpose, as with real instruments:
pH 4.5 files use ';' + decimal comma, the others ',' + decimal point.

    python examples/make_demo_data.py
"""

from pathlib import Path

import numpy as np

OUT = Path(__file__).parent / "demo-data"
BATHS = {"pH4.5": -45.0, "pH5.0": 10.0, "pH5.5": 60.0}  # steady-state stress (MPa)

rng = np.random.default_rng(42)
OUT.mkdir(exist_ok=True)
t = np.linspace(0, 60, 241)  # min

for bath, s_inf in BATHS.items():
    for rep in (1, 2, 3):
        s_end = s_inf + rng.normal(0, 6)
        tau = rng.uniform(6, 10)
        stress = s_end + (35 - s_end) * np.exp(-t / tau) + rng.normal(0, 3, t.size)
        rate = {"pH4.5": 0.20, "pH5.0": 0.25, "pH5.5": 0.30}[bath] * rng.uniform(0.95, 1.05)
        thickness = np.clip(rate * t + rng.normal(0, 0.05, t.size), 0, None)
        rows = zip(t, thickness, stress)
        if bath == "pH4.5":
            lines = ["Time (min);Thickness (µm);Stress (MPa)"]
            lines += [f"{a:.2f};{b:.3f};{c:.2f}".replace(".", ",") for a, b, c in rows]
        else:
            lines = ["Time (min),Thickness (µm),Stress (MPa)"]
            lines += [f"{a:.2f},{b:.3f},{c:.2f}" for a, b, c in rows]
        (OUT / f"NiP_{bath}_r{rep}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"OK: {len(list(OUT.glob('*.csv')))} files in {OUT}")
