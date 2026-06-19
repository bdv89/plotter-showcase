"""
Baseline correction utilities for XRD and similar data.

Supported methods:
- 'snip': Statistics-sensitive Nonlinear Iterative Peak-clipping (recommended)
- 'asls': Asymmetric Least Squares (Eilers & Boelens)
- 'arpls': Asymmetrically Reweighted Penalized Least Squares
- 'polynomial': DEPRECATED - legacy method, will be removed

Performance optimizations:
- Sparse matrix operations (O(n) instead of O(n³))
- LRU cache for difference matrices
- Convergence criteria to avoid unnecessary iterations
"""

import numpy as np
from scipy.signal import find_peaks
from scipy.sparse import diags, csr_matrix
from scipy.sparse.linalg import spsolve
from functools import lru_cache


@lru_cache(maxsize=32)
def _get_difference_matrix(n):
    """Build sparse second-difference matrix D (cached by size n).

    D is (n-2) x n with pattern [1, -2, 1] on diagonals.
    Returns D and D.T @ D (both CSR sparse).
    """
    D = diags([1, -2, 1], [0, 1, 2], shape=(n - 2, n), format='csr')
    DT_D = D.T @ D
    return D, DT_D


def _snip_baseline(y, K=12, transform='sqrt', epsilon=1e-9, padding='reflect'):
    """Compute baseline via SNIP on a variance-stabilized transform.

    Args:
        y: 1D array-like signal (>= 0 recommended)
        K: number of iterations (related to minimum peak half-width in samples)
        transform: 'sqrt' | 'log' | 'none'
        epsilon: small constant for log transform
        padding: padding mode for edges ('reflect', 'edge', None)

    Returns:
        baseline array (same length as y)
    """
    y = np.asarray(y, dtype=float)

    # Clean input: handle NaN/Inf
    mask_valid = np.isfinite(y)
    if not np.all(mask_valid):
        y = y.copy()
        y[~mask_valid] = np.interp(np.where(~mask_valid)[0],
                                     np.where(mask_valid)[0],
                                     y[mask_valid])

    n = y.size
    if n == 0:
        return y.copy()

    K = int(max(1, K))

    # Apply padding if requested
    if padding and K > 0:
        y_padded = np.pad(y, pad_width=K, mode=padding)
    else:
        y_padded = y

    # Transform to stabilize variance (recommended for counting data)
    if transform == 'sqrt':
        yt = np.sqrt(np.maximum(y_padded, 0.0))
        inv = lambda s: np.square(s)
    elif transform == 'log':
        yt = np.log(np.maximum(y_padded, 0.0) + epsilon)
        inv = lambda s: np.exp(s) - epsilon
    else:
        yt = y_padded.copy()
        inv = lambda s: s

    s = yt.copy()
    n_padded = s.size

    for k in range(1, K + 1):
        # vectorized symmetric average where indices valid
        left = s[:-2 * k]
        right = s[2 * k:]
        avg = 0.5 * (left + right)
        center = s[k: n_padded - k]
        s[k: n_padded - k] = np.minimum(center, avg)
        # borders unchanged

    b = inv(s)

    # Remove padding if applied
    if padding and K > 0:
        b = b[K:-K]

    return b


def _asls_baseline(y, lam=1e6, p=1e-3, niter=20, tol=1e-4):
    """Asymmetric Least Squares (Eilers & Boelens) baseline.

    Minimizes (y - z)^T W (y - z) + lam * ||D z||^2 with asymmetric weights.
    Args:
        y: 1D array-like
        lam: smoothing parameter (higher -> smoother baseline)
        p: asymmetry (small for positive peaks; e.g., 1e-3)
        niter: maximum iterations
        tol: convergence tolerance (norm of z difference)
    Returns:
        baseline array z
    """
    y = np.asarray(y, dtype=float)

    # Clean input: handle NaN/Inf
    mask_valid = np.isfinite(y)
    if not np.all(mask_valid):
        y = y.copy()
        y[~mask_valid] = np.interp(np.where(~mask_valid)[0],
                                     np.where(mask_valid)[0],
                                     y[mask_valid])

    n = y.size
    if n == 0:
        return y.copy()
    if n < 3:
        return y.copy()  # Too small for second derivative

    # Get cached sparse difference matrix
    D, DT_D = _get_difference_matrix(n)

    z = y.copy()
    w = np.ones(n)
    lam_DT_D = lam * DT_D

    for iteration in range(max(1, int(niter))):
        z_prev = z.copy()

        # W as sparse diagonal
        W = diags(w, format='csr')
        A = W + lam_DT_D
        b = w * y

        # Solve A z = b with sparse solver
        try:
            z = spsolve(A, b)
        except Exception:
            # Fallback to iterative solver
            from scipy.sparse.linalg import cg
            z, info = cg(A, b, x0=z_prev, tol=1e-5)
            if info != 0:
                z = z_prev  # Keep previous if solver failed

        # Update weights (asymmetric): small weight where residual positive
        w = p * (y > z) + (1 - p) * (y <= z)

        # Check convergence
        if np.linalg.norm(z - z_prev) < tol * np.linalg.norm(z):
            break

    return z


def _arpls_baseline(y, lam=1e6, niter=15, tol=1e-4):
    """Asymmetrically Reweighted Penalized Least Squares (arPLS) baseline.

    Weight update depends on negative residual statistics (more stable than fixed p).
    Args:
        y: 1D array-like
        lam: smoothing parameter (higher -> smoother)
        niter: maximum iterations
        tol: convergence tolerance (norm of z difference)
    Returns:
        baseline array z
    """
    y = np.asarray(y, dtype=float)

    # Clean input: handle NaN/Inf
    mask_valid = np.isfinite(y)
    if not np.all(mask_valid):
        y = y.copy()
        y[~mask_valid] = np.interp(np.where(~mask_valid)[0],
                                     np.where(mask_valid)[0],
                                     y[mask_valid])

    n = y.size
    if n == 0:
        return y.copy()
    if n < 3:
        return y.copy()  # Too small for second derivative

    # Get cached sparse difference matrix
    D, DT_D = _get_difference_matrix(n)

    w = np.ones(n)
    z = y.copy()
    lam_DT_D = lam * DT_D

    for iteration in range(max(1, int(niter))):
        z_prev = z.copy()

        # W as sparse diagonal
        W = diags(w, format='csr')
        A = W + lam_DT_D
        b = w * y

        # Solve A z = b with sparse solver
        try:
            z = spsolve(A, b)
        except Exception:
            # Fallback to iterative solver
            from scipy.sparse.linalg import cg
            z, info = cg(A, b, x0=z_prev, tol=1e-5)
            if info != 0:
                z = z_prev  # Keep previous if solver failed

        r = y - z
        # Negative residual stats
        mask = r < 0
        if not np.any(mask):
            break
        mu = np.mean(r[mask])
        sigma = np.std(r[mask]) + 1e-12
        # Weight update (He et al.): weights small when r >> mu
        w = 1.0 / (1.0 + np.exp(2.0 * (r - (2.0 * sigma - mu)) / sigma))

        # Check convergence
        if np.linalg.norm(z - z_prev) < tol * np.linalg.norm(z):
            break

    return z


def _poly_masked_baseline(x, y, degree=3, prominence_factor=2.0):
    """DEPRECATED: Legacy masked polynomial baseline (obsolete).

    This method is no longer recommended. Use 'snip', 'asls', or 'arpls' instead.
    Kept temporarily for backward compatibility only.
    """
    import warnings
    warnings.warn(
        "Polynomial baseline method is deprecated and will be removed in a future version. "
        "Use 'snip', 'asls', or 'arpls' instead.",
        DeprecationWarning,
        stacklevel=3
    )

    x = np.asarray(x)
    y = np.asarray(y)
    if len(x) != len(y):
        raise ValueError(f"x and y must have same length (got {len(x)} and {len(y)})")
    if len(x) < degree + 1:
        raise ValueError(f"Need at least {degree + 1} points for degree {degree} polynomial")

    prominence_threshold = np.std(y) * prominence_factor
    peaks, _ = find_peaks(y, prominence=prominence_threshold)

    mask = np.ones(len(y), dtype=bool)
    peak_width = 5
    for peak in peaks:
        start = max(0, peak - peak_width)
        end = min(len(y), peak + peak_width + 1)
        mask[start:end] = False
    if np.sum(mask) < degree + 1:
        mask = np.ones(len(y), dtype=bool)

    p = np.polyfit(x[mask], y[mask], degree)
    baseline = np.polyval(p, x)
    return baseline


def subtract_baseline(x, y, method='snip', **kwargs):
    """Unified baseline subtraction dispatcher.

    Args:
        x: array of x values (used for 'polynomial'; ignored by other methods)
        y: array of y values
        method: 'snip' | 'asls' | 'arpls' | 'polynomial'
        kwargs: parameters per method
            snip: K (int), transform ('sqrt'|'log'|'none')
            asls: lam (float), p (float), niter (int)
            arpls: lam (float), niter (int)
            polynomial: degree (int), prominence_factor (float)

    Returns:
        (y_corrected, baseline)
    """
    y = np.asarray(y, dtype=float)
    method = (method or 'snip').lower()

    if method == 'snip':
        K = int(kwargs.get('K', 12))
        transform = kwargs.get('transform', 'sqrt')
        baseline = _snip_baseline(y, K=K, transform=transform)
    elif method == 'asls':
        lam = float(kwargs.get('lam', 1e6))
        p = float(kwargs.get('p', 1e-3))
        niter = int(kwargs.get('niter', 20))
        baseline = _asls_baseline(y, lam=lam, p=p, niter=niter)
    elif method == 'arpls':
        lam = float(kwargs.get('lam', 1e6))
        niter = int(kwargs.get('niter', 15))
        baseline = _arpls_baseline(y, lam=lam, niter=niter)
    elif method == 'polynomial':
        degree = int(kwargs.get('degree', 3))
        prominence_factor = float(kwargs.get('prominence_factor', 2.0))
        baseline = _poly_masked_baseline(np.asarray(x), y, degree=degree, prominence_factor=prominence_factor)
    else:
        # Default to SNIP if unknown
        K = int(kwargs.get('K', 12))
        transform = kwargs.get('transform', 'sqrt')
        baseline = _snip_baseline(y, K=K, transform=transform)

    y_corrected = y - baseline
    return y_corrected, baseline


def auto_correct_baseline(x, y):
    """Quick auto-correction with sensible defaults (SNIP, sqrt, K=12)."""
    y_corrected, _ = subtract_baseline(x, y, method='snip', K=12, transform='sqrt')
    return y_corrected
