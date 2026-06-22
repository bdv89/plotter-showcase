"""Unit tests for baseline correction (core.baseline_correction.subtract_baseline).

Headless: no plotting. Verifies each method runs, preserves peaks, and is robust
to edge cases (NaN, tiny inputs, all-zeros).
"""

import numpy as np
import pytest
from core.baseline_correction import subtract_baseline


def generate_test_data(n=1000, add_hump=False, seed=0):
    """Synthetic XRD-like data: polynomial background (+ optional hump) + peaks + noise."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 100, n)

    background = 50 + 2 * x + 0.01 * x**2
    if add_hump:
        background += 200 * np.exp(-((x - 50) / 20) ** 2)

    def gaussian(center, amplitude, width):
        return amplitude * np.exp(-((x - center) / width) ** 2)

    peaks = gaussian(25, 150, 2) + gaussian(40, 30, 1.5) + gaussian(60, 40, 2) + gaussian(80, 25, 1.8)

    signal = background + peaks
    signal += rng.normal(0, np.sqrt(np.maximum(signal / 10, 1)))
    return x, signal, background


# min_corr differs by method: AsLS removes a broad Gaussian hump far less
# aggressively than SNIP/arPLS, so its peak correlation is genuinely lower.
@pytest.mark.parametrize("method,params,min_corr", [
    ("snip", {"K": 12, "transform": "sqrt", "padding": "reflect"}, 0.85),
    ("asls", {"lam": 1e6, "p": 1e-3, "niter": 20, "tol": 1e-4}, 0.45),
    ("arpls", {"lam": 1e6, "niter": 15, "tol": 1e-4}, 0.9),
])
def test_method_runs_and_preserves_peaks(method, params, min_corr):
    x, y, true_baseline = generate_test_data(n=1000, add_hump=True)
    y_corrected, estimated_baseline = subtract_baseline(x, y, method=method, **params)

    assert y_corrected.shape == y.shape
    assert estimated_baseline.shape == y.shape
    assert np.all(np.isfinite(estimated_baseline))

    # The corrected signal should correlate with the true peaks (background removed).
    true_peaks = y - true_baseline
    corr = np.corrcoef(y_corrected, true_peaks)[0, 1]
    assert corr > min_corr, f"{method}: weak peak preservation (corr={corr:.3f})"


@pytest.mark.parametrize("method", ["snip", "asls", "arpls"])
def test_edge_cases(method):
    # NaN values present
    x = np.linspace(0, 100, 100)
    y = 100 + 0.1 * x + np.random.default_rng(1).standard_normal(100)
    y[20:25] = np.nan
    yc, _ = subtract_baseline(x, y, method=method)
    assert yc.shape == y.shape

    # All zeros must not blow up
    yc0, _ = subtract_baseline(x, np.zeros(100), method=method)
    assert np.all(np.isfinite(yc0))


def test_small_dataset():
    x = np.arange(5)
    y = np.array([10.0, 12.0, 15.0, 13.0, 11.0])
    yc, _ = subtract_baseline(x, y, method="asls")
    assert yc.shape == y.shape
