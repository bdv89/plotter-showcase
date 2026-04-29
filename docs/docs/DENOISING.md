# Signal Denoising Methods

This document describes the advanced denoising methods available in the CSV-to-Plot application for cleaning electrochemical and scientific data.

## Overview

The application provides **4 denoising algorithms**, each optimized for different types of noise:

1. **Savitzky-Golay Filter** - Preserves peak shapes
2. **Median Filter** - Removes impulse noise (spikes)
3. **Wavelet Denoising** - Multi-scale noise removal
4. **FFT Low-pass Filter** - Removes high-frequency noise

## When to Use Each Method

| Noise Type | Recommended Method | Why |
|------------|-------------------|-----|
| Gaussian white noise | Savitzky-Golay | Smooth while preserving peaks |
| Impulse noise (spikes) | Median Filter | Robust to outliers |
| Multi-scale noise | Wavelet | Handles different frequency components |
| High-frequency oscillations | FFT Low-pass | Direct frequency filtering |

## Method Details

### 1. Savitzky-Golay Filter

**Best for:** Electrochemical data (CV, chronoamperometry) where peak shapes must be preserved.

**How it works:**
Fits a polynomial to successive sub-windows of data points. Smoother than moving average while preserving peak features.

**Parameters:**
- **Window size** (5-51, odd numbers): Larger = smoother, but may distort sharp peaks
  - Recommended: 11 for most CV data
  - Use 7-9 for high-resolution data
  - Use 15-21 for very noisy data

- **Polynomial order** (1-5): Higher = better peak preservation
  - Recommended: 3 for most data
  - Use 2 for very noisy data (more aggressive smoothing)
  - Use 4-5 for clean data with complex features

**Example use case:**
Cyclic voltammetry data with redox peaks that must maintain their shape and position.

**Code example:**
```python
from denoise_methods import denoise

# Apply Savitzky-Golay filter
clean_data = denoise(noisy_cv_data, method='savgol', window=11, polyorder=3)
```

---

### 2. Median Filter

**Best for:** Data with sporadic spikes or impulse noise (salt-and-pepper noise).

**How it works:**
Replaces each data point with the median of its surrounding neighbors. Highly effective at removing isolated outliers while preserving edges.

**Parameters:**
- **Kernel size** (3-21, odd numbers): Number of points in neighborhood
  - Recommended: 5 for most data
  - Use 3 for minimal smoothing
  - Use 7-11 for aggressive spike removal

**Example use case:**
Electrochemical impedance spectroscopy (EIS) data with occasional measurement artifacts.

**Code example:**
```python
# Remove spikes while preserving step edges
clean_data = denoise(spiky_data, method='median', kernel_size=5)
```

---

### 3. Wavelet Denoising

**Best for:** Complex signals with noise across multiple frequency scales.

**How it works:**
Decomposes signal into wavelet coefficients, applies threshold to remove noise components, then reconstructs. Uses VisuShrink thresholding.

**Parameters:**
- **Wavelet type**:
  - `db4` (Daubechies 4) - Default, good general-purpose wavelet
  - `sym8` (Symlet 8) - More symmetric, better for signals with symmetry
  - `coif5` (Coiflet 5) - Better time-frequency localization

- **Thresholding mode**:
  - `soft` (default) - Smoother result, continuous denoising
  - `hard` - Sharper features, but may introduce discontinuities

**Example use case:**
Spectroscopy data with baseline drift + high-frequency noise.

**Code example:**
```python
# Multi-scale denoising with soft thresholding
clean_data = denoise(noisy_data, method='wavelet', wavelet='db4', mode='soft')
```

**Note:** Requires PyWavelets (`pywt`) library. Install with:
```bash
pip install pywt>=1.4.1
```

---

### 4. FFT Low-pass Filter

**Best for:** Data dominated by high-frequency noise components.

**How it works:**
Transforms signal to frequency domain via FFT, removes frequencies above cutoff, then inverse transforms back to time domain.

**Parameters:**
- **Cutoff frequency** (0.01-0.5): Fraction of Nyquist frequency
  - Lower values = more aggressive filtering
  - Recommended: 0.1 for typical electrochemical data
  - Use 0.05 for very smooth output
  - Use 0.2-0.3 for minimal filtering

**Example use case:**
Amperometric data with 50/60 Hz electrical noise.

**Code example:**
```python
# Remove high-frequency noise above 10% of Nyquist
clean_data = denoise(noisy_amperometry, method='fft', cutoff_freq=0.1)
```

---

## Usage in GUI

### Accessing Denoising Controls

1. Open plot window
2. Click **Processing** button (or press `P`)
3. Locate **"Advanced Denoising"** section
4. Check **"Enable"** checkbox
5. Select desired method from dropdown
6. Adjust method-specific parameters
7. Use **↑↓** buttons to adjust processing order

### Processing Order

The default order is:
1. Baseline Correction
2. **Advanced Denoising** ← You can move this
3. Smoothing (rolling mean)
4. Outliers (Z-score removal)
5. Normalize
6. Peak Fitting

**Recommendation:** Apply denoising **before** baseline correction to avoid noise artifacts affecting the baseline estimate.

---

## Programmatic Usage

### Basic Usage

```python
from denoise_methods import denoise
import pandas as pd

# Load data
df = pd.read_csv('noisy_data.csv')

# Denoise with Savitzky-Golay
df_clean = denoise(df, method='savgol', window=11, polyorder=3)

# Export
df_clean.to_csv('clean_data.csv', index=False)
```

### Using with DataPipeline

```python
from data_pipeline import DataPipeline, register_default_processors

# Initialize pipeline
pipeline = DataPipeline()
register_default_processors(pipeline)

# Apply denoising
clean_df = pipeline.process_data(
    noisy_df,
    processors=['denoise_savgol', 'baseline_snip']
)
```

### Custom Processor

```python
from plot_processing_window import create_denoise_processor

# Create custom denoising processor
denoise_proc = create_denoise_processor('median', {'kernel_size': 7})

# Apply to data
clean_df = denoise_proc(noisy_df)
```

---

## Comparison of Methods

### Computational Complexity

| Method | Complexity | Speed |
|--------|------------|-------|
| Median | O(n log k) | Fast |
| Savitzky-Golay | O(nk) | Fast |
| FFT Low-pass | O(n log n) | Very Fast |
| Wavelet | O(n log n) | Moderate |

Where `n` = data length, `k` = window/kernel size

### Effect on Signal Features

| Feature | Savitzky-Golay | Median | Wavelet | FFT |
|---------|----------------|--------|---------|-----|
| **Peak height** | Minimal change | Preserved | Slight reduction | Preserved |
| **Peak position** | Preserved | Preserved | Preserved | Preserved |
| **Peak width** | Minimal broadening | Preserved | Slight broadening | Broadening |
| **Edges/Steps** | Slight rounding | Preserved | Preserved | Significant rounding |

---

## Best Practices

### 1. Start Conservative
- Begin with gentle parameters (small windows, high cutoffs)
- Gradually increase filtering strength
- Always compare with original data

### 2. Visual Inspection
- Plot before/after comparison
- Check that peaks haven't shifted
- Verify baseline hasn't been distorted

### 3. Method Selection Flow

```
┌─────────────────────┐
│ What type of noise? │
└──────────┬──────────┘
           │
      ┌────┴────┐
      │         │
   Spikes?   Gaussian?
      │         │
   Median   Savitzky-Golay
                │
         ┌──────┴──────┐
         │             │
    High-freq?   Multi-scale?
         │             │
       FFT          Wavelet
```

### 4. Avoid Over-filtering
**Symptoms of over-filtering:**
- Peaks become rounded or disappear
- Fine structure is lost
- Baseline becomes artificially smooth

**Solution:**
Reduce window size, increase cutoff frequency, or use lower polynomial order.

---

## Technical References

### Savitzky-Golay
- Savitzky, A.; Golay, M.J.E. (1964). "Smoothing and Differentiation of Data by Simplified Least Squares Procedures". *Analytical Chemistry*. **36** (8): 1627–1639.

### Wavelet Denoising
- Donoho, D.L. (1995). "De-noising by soft-thresholding". *IEEE Transactions on Information Theory*. **41** (3): 613–627.

### Median Filter
- Tukey, J.W. (1977). *Exploratory Data Analysis*. Addison-Wesley.

---

## Troubleshooting

### "ImportError: No module named 'pywt'"
**Solution:** Install PyWavelets:
```bash
pip install pywt>=1.4.1
```

### Denoising makes data worse
**Possible causes:**
1. Window/kernel too large → Reduce size
2. Wrong method for noise type → Try different method
3. Data already clean → Disable denoising

### Processing is slow
**Solutions:**
1. Use FFT or Median (faster methods)
2. Reduce window/kernel size
3. Downsample data before denoising
4. Process smaller subsets

### NaN values after denoising
**Cause:** Some methods can't handle existing NaN values
**Solution:** Remove NaN rows before denoising, or use forward-fill:
```python
df_filled = df.fillna(method='ffill')
df_clean = denoise(df_filled, ...)
```

---

## See Also

- [BASELINE_CORRECTION.md](BASELINE_CORRECTION.md) - Baseline removal methods
- [data_pipeline.py](../data_pipeline.py) - Processing pipeline implementation
- [denoise_methods.py](../denoise_methods.py) - Source code with detailed docstrings
- [test_denoise_methods.py](../tests/test_denoise_methods.py) - Unit tests and examples
