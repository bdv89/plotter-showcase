"""
Test script for baseline correction functionality with all methods.
"""

import numpy as np
import matplotlib.pyplot as plt
import time
from baseline_correction import subtract_baseline


def generate_test_data(n=1000, add_hump=False):
    """Generate synthetic XRD-like data with peaks and background.

    Args:
        n: number of points
        add_hump: add a broad background hump if True
    """
    x = np.linspace(0, 100, n)

    # Background (polynomial + optional hump)
    background = 50 + 2*x + 0.01*x**2
    if add_hump:
        # Broad background feature
        hump = 200 * np.exp(-((x - 50) / 20) ** 2)
        background += hump

    # Add some Gaussian peaks (narrow for crystalline)
    def gaussian(x, center, amplitude, width):
        return amplitude * np.exp(-((x - center) / width) ** 2)

    peaks = (
        gaussian(x, 25, 150, 2) +
        gaussian(x, 40, 30, 1.5) +
        gaussian(x, 60, 40, 2) +
        gaussian(x, 80, 25, 1.8)
    )

    # Add Poisson-like noise (typical for XRD counting statistics)
    signal = background + peaks
    noise = np.random.normal(0, np.sqrt(np.maximum(signal / 10, 1)))
    signal += noise

    return x, signal, background


def test_all_methods():
    """Test all baseline correction methods."""
    print("=" * 60)
    print("Testing all baseline correction methods")
    print("=" * 60)

    # Generate test data
    print("\nGenerating test data (1000 points with hump)...")
    x, y_original, true_baseline = generate_test_data(n=1000, add_hump=True)

    methods = {
        'snip': {'K': 12, 'transform': 'sqrt', 'padding': 'reflect'},
        'asls': {'lam': 1e6, 'p': 1e-3, 'niter': 20, 'tol': 1e-4},
        'arpls': {'lam': 1e6, 'niter': 15, 'tol': 1e-4},
    }

    results = {}
    timings = {}

    for method_name, params in methods.items():
        print(f"\nTesting {method_name.upper()} method...")
        start = time.time()
        y_corrected, estimated_baseline = subtract_baseline(x, y_original, method=method_name, **params)
        elapsed = time.time() - start

        # Compute error metrics
        mae = np.mean(np.abs(estimated_baseline - true_baseline))
        peak_preservation = np.corrcoef(y_corrected, y_original - true_baseline)[0, 1]

        results[method_name] = (y_corrected, estimated_baseline, mae, peak_preservation)
        timings[method_name] = elapsed

        print(f"  Time: {elapsed:.3f}s")
        print(f"  MAE vs true baseline: {mae:.2f}")
        print(f"  Peak preservation (corr): {peak_preservation:.3f}")

    # Visualization
    print("\nCreating visualization...")
    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # Original data
    ax0 = fig.add_subplot(gs[0, :])
    ax0.plot(x, y_original, 'k-', label='Original Signal', linewidth=1, alpha=0.7)
    ax0.plot(x, true_baseline, 'g--', label='True Baseline', linewidth=2)
    ax0.set_xlabel('2θ (°)')
    ax0.set_ylabel('Intensity')
    ax0.set_title('Original XRD Data with True Baseline')
    ax0.legend()
    ax0.grid(True, alpha=0.3)

    # Each method
    colors = {'snip': 'blue', 'asls': 'red', 'arpls': 'orange'}
    for idx, (method_name, (y_corr, est_base, mae, corr)) in enumerate(results.items()):
        # Baseline comparison
        ax1 = fig.add_subplot(gs[1, idx])
        ax1.plot(x, y_original, 'k-', linewidth=0.5, alpha=0.5, label='Signal')
        ax1.plot(x, true_baseline, 'g--', linewidth=2, label='True')
        ax1.plot(x, est_base, color=colors[method_name], linestyle='--', linewidth=2, label='Estimated')
        ax1.set_title(f'{method_name.upper()}\nMAE={mae:.1f}, t={timings[method_name]:.3f}s')
        ax1.set_xlabel('2θ (°)')
        ax1.set_ylabel('Intensity')
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # Corrected signal
        ax2 = fig.add_subplot(gs[2, idx])
        ax2.plot(x, y_corr, color=colors[method_name], linewidth=1, label='Corrected')
        ax2.axhline(y=0, color='gray', linestyle=':', linewidth=1)
        ax2.set_title(f'Corrected (r={corr:.3f})')
        ax2.set_xlabel('2θ (°)')
        ax2.set_ylabel('Corrected Intensity')
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

    plt.savefig('baseline_test_all_methods.png', dpi=150, bbox_inches='tight')
    print("Saved result to: baseline_test_all_methods.png")
    plt.show()

    return results, timings


def test_performance():
    """Benchmark performance on large datasets."""
    print("\n" + "=" * 60)
    print("Performance benchmark")
    print("=" * 60)

    sizes = [1000, 5000, 10000, 20000]
    methods = ['snip', 'asls', 'arpls']

    print(f"\n{'Size':<10} {'SNIP (s)':<12} {'AsLS (s)':<12} {'arPLS (s)':<12}")
    print("-" * 50)

    for n in sizes:
        x, y, _ = generate_test_data(n=n, add_hump=False)
        times = {}

        for method in methods:
            start = time.time()
            _, _ = subtract_baseline(x, y, method=method)
            elapsed = time.time() - start
            times[method] = elapsed

        print(f"{n:<10} {times['snip']:<12.4f} {times['asls']:<12.4f} {times['arpls']:<12.4f}")

    print("\nTarget: < 0.3s for 10k points ✓" if times.get('asls', 999) < 0.3 else "\nTarget: < 0.3s for 10k points ✗")


def test_edge_cases():
    """Test edge cases and robustness."""
    print("\n" + "=" * 60)
    print("Edge cases and robustness tests")
    print("=" * 60)

    # Test 1: NaN values
    print("\nTest 1: Input with NaN values")
    x = np.linspace(0, 100, 100)
    y = 100 + 0.1 * x + np.random.randn(100)
    y[20:25] = np.nan
    try:
        y_corr, _ = subtract_baseline(x, y, method='snip')
        print("  ✓ Handled NaN gracefully")
    except Exception as e:
        print(f"  ✗ Failed: {e}")

    # Test 2: Very small dataset
    print("\nTest 2: Small dataset (n=5)")
    x = np.arange(5)
    y = np.array([10, 12, 15, 13, 11])
    try:
        y_corr, _ = subtract_baseline(x, y, method='asls')
        print("  ✓ Handled small dataset")
    except Exception as e:
        print(f"  ✗ Failed: {e}")

    # Test 3: All zeros
    print("\nTest 3: All zeros")
    x = np.linspace(0, 100, 100)
    y = np.zeros(100)
    try:
        y_corr, _ = subtract_baseline(x, y, method='arpls')
        print("  ✓ Handled all zeros")
    except Exception as e:
        print(f"  ✗ Failed: {e}")

    print("\nEdge case tests completed!")


if __name__ == "__main__":
    try:
        # Run all tests
        test_all_methods()
        test_performance()
        test_edge_cases()

        print("\n" + "=" * 60)
        print("✓ All baseline correction tests completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
