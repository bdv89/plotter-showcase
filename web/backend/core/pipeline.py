"""
Data processing pipeline - adapted from data_pipeline.py (NO PyQt).

Pure Python pipeline system for processing and transforming data between components.
"""

import pandas as pd
import numpy as np
from core.denoise_methods import denoise


class DataPipeline:
    """A pipeline system for processing and transforming data between components"""

    def __init__(self):
        self.processors = {}
        self.pipelines = {}
        # Cache for processed data: {(source_id, pipeline_hash): DataFrame}
        self._processed_cache = {}

    def _get_pipeline_hash(self, pipeline_id):
        """Calculate hash for a pipeline configuration"""
        steps = self.pipelines.get(pipeline_id, [])
        return hash(tuple(steps))

    def invalidate_cache(self, source_id=None):
        """Invalidate processed data cache

        Args:
            source_id: If provided, only invalidate cache for this source.
                      If None, clear entire cache.
        """
        if source_id:
            self._processed_cache = {
                k: v for k, v in self._processed_cache.items()
                if k[0] != source_id
            }
            print(f"🟡 Cache invalidated for source: {source_id}")
        else:
            self._processed_cache.clear()
            print("🟡 Cache cleared entirely")

    def register_processor(self, name, processor_function):
        """Register a data processor function"""
        self.processors[name] = processor_function

    def create_pipeline(self, pipeline_id, steps):
        """Create a processing pipeline with multiple steps

        Args:
            pipeline_id (str): Unique identifier for the pipeline
            steps (list): List of processor names to apply in sequence
        """
        self.pipelines[pipeline_id] = steps

    def process_data(self, data, pipeline_id=None, processors=None, source_id=None):
        """Process data through registered processors

        Args:
            data: Input data (usually DataFrame)
            pipeline_id (str, optional): ID of a predefined pipeline to use
            processors (list, optional): List of processor names for one-time use
            source_id (str, optional): Identifier for the data source

        Returns:
            Processed data
        """
        if not pipeline_id and not processors:
            return data

        # Check cache first (only for pipeline_id with source_id)
        if pipeline_id and source_id:
            cache_key = (source_id, self._get_pipeline_hash(pipeline_id))
            if cache_key in self._processed_cache:
                print(f"🟢 Cache hit: {source_id}")
                return self._processed_cache[cache_key]

        # Determine which processors to use
        process_list = []
        if pipeline_id and pipeline_id in self.pipelines:
            process_list = self.pipelines[pipeline_id]
        elif processors:
            process_list = processors

        # Apply processors in sequence
        processed_data = data
        for processor_name in process_list:
            if processor_name in self.processors:
                try:
                    print(f"🟡 Applying {processor_name}...")
                    processed_data = self.processors[processor_name](processed_data)
                except Exception as e:
                    error_msg = f"❌ Pipeline error in {processor_name}: {str(e)}"
                    print(error_msg)
                    break
            else:
                warning_msg = f"⚠️ Processor '{processor_name}' not found in registry"
                print(warning_msg)

        # Cache the result (only for pipeline_id with source_id)
        if pipeline_id and source_id:
            cache_key = (source_id, self._get_pipeline_hash(pipeline_id))
            self._processed_cache[cache_key] = processed_data
            print(f"🟡 Cached processed data for: {source_id}")

        return processed_data


# Default processors for common tasks
def register_default_processors(pipeline):
    """Register a set of standard data processors"""

    def remove_outliers(df, column=None, threshold=3):
        """Remove outliers using z-score"""
        if column is None:
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            result = df.copy()
            for col in numeric_cols:
                z_scores = np.abs((result[col] - result[col].mean()) / result[col].std())
                result = result[z_scores < threshold]
        else:
            z_scores = np.abs((df[column] - df[column].mean()) / df[column].std())
            result = df[z_scores < threshold]
        return result

    def smooth_data(df, columns=None, window=5):
        """Apply rolling average smoothing"""
        result = df.copy()
        cols_to_smooth = columns if columns else df.select_dtypes(include=[np.number]).columns
        for col in cols_to_smooth:
            if col in result.columns:
                result[col] = result[col].rolling(window=window, center=True).mean()
        return result

    def normalize_data(df, columns=None, method='minmax'):
        """Normalize numeric columns"""
        result = df.copy()
        cols_to_normalize = columns if columns else df.select_dtypes(include=[np.number]).columns

        for col in cols_to_normalize:
            if col in result.columns:
                if method == 'minmax':
                    min_val = result[col].min()
                    max_val = result[col].max()
                    if max_val > min_val:
                        result[col] = (result[col] - min_val) / (max_val - min_val)
                elif method == 'zscore':
                    mean = result[col].mean()
                    std = result[col].std()
                    if std > 0:
                        result[col] = (result[col] - mean) / std
        return result

    def filter_range(df, column, min_val=None, max_val=None):
        """Filter data within a specified range"""
        result = df.copy()
        if min_val is not None:
            result = result[result[column] >= min_val]
        if max_val is not None:
            result = result[result[column] <= max_val]
        return result

    def resample_data(df, time_col, rule='1S', agg='mean'):
        """Resample time series data"""
        if df[time_col].dtype != 'datetime64[ns]':
            try:
                df = df.copy()
                df[time_col] = pd.to_datetime(df[time_col])
            except (ValueError, TypeError, pd.errors.ParserError):
                return df
        df_indexed = df.set_index(time_col)
        resampled = df_indexed.resample(rule).agg(agg)
        return resampled.reset_index()

    def baseline_snip(df, y_col='Intensity', x_col=None, K=12, transform='sqrt', padding='reflect'):
        """Apply SNIP baseline correction to specified column(s)."""
        from core.baseline_correction import subtract_baseline
        result = df.copy()
        y_cols = [y_col] if isinstance(y_col, str) else y_col
        for col in y_cols:
            if col not in result.columns:
                continue
            x = result[x_col].values if x_col and x_col in result.columns else result.index.values
            y = result[col].values
            y_corrected, _ = subtract_baseline(x, y, method='snip', K=K, transform=transform, padding=padding)
            result[col] = y_corrected
        return result

    def baseline_asls(df, y_col='Intensity', x_col=None, lam=1e6, p=1e-3, niter=20, tol=1e-4):
        """Apply AsLS baseline correction to specified column(s)."""
        from core.baseline_correction import subtract_baseline
        result = df.copy()
        y_cols = [y_col] if isinstance(y_col, str) else y_col
        for col in y_cols:
            if col not in result.columns:
                continue
            x = result[x_col].values if x_col and x_col in result.columns else result.index.values
            y = result[col].values
            y_corrected, _ = subtract_baseline(x, y, method='asls', lam=lam, p=p, niter=niter, tol=tol)
            result[col] = y_corrected
        return result

    def baseline_arpls(df, y_col='Intensity', x_col=None, lam=1e6, niter=15, tol=1e-4):
        """Apply arPLS baseline correction to specified column(s)."""
        from core.baseline_correction import subtract_baseline
        result = df.copy()
        y_cols = [y_col] if isinstance(y_col, str) else y_col
        for col in y_cols:
            if col not in result.columns:
                continue
            x = result[x_col].values if x_col and x_col in result.columns else result.index.values
            y = result[col].values
            y_corrected, _ = subtract_baseline(x, y, method='arpls', lam=lam, niter=niter, tol=tol)
            result[col] = y_corrected
        return result

    # Denoising processors
    def denoise_savgol(df, window=11, polyorder=3):
        """Savitzky-Golay filter denoising"""
        return denoise(df, method='savgol', window=window, polyorder=polyorder)

    def denoise_median(df, kernel_size=5):
        """Median filter denoising"""
        return denoise(df, method='median', kernel_size=kernel_size)

    def denoise_wavelet(df, wavelet='db4', level=None, mode='soft'):
        """Wavelet denoising"""
        return denoise(df, method='wavelet', wavelet=wavelet, level=level, mode=mode)

    def denoise_fft(df, cutoff_freq=0.1):
        """FFT low-pass filter denoising"""
        return denoise(df, method='fft', cutoff_freq=cutoff_freq)

    # Register the processors
    pipeline.register_processor('remove_outliers', remove_outliers)
    pipeline.register_processor('smooth_data', smooth_data)
    pipeline.register_processor('normalize_data', normalize_data)
    pipeline.register_processor('filter_range', filter_range)
    pipeline.register_processor('resample_data', resample_data)
    pipeline.register_processor('baseline_snip', baseline_snip)
    pipeline.register_processor('baseline_asls', baseline_asls)
    pipeline.register_processor('baseline_arpls', baseline_arpls)

    # Register denoising processors
    pipeline.register_processor('denoise_savgol', denoise_savgol)
    pipeline.register_processor('denoise_median', denoise_median)
    pipeline.register_processor('denoise_wavelet', denoise_wavelet)
    pipeline.register_processor('denoise_fft', denoise_fft)


def create_fit_multi_peaks_processor(x_col, y_col, method='gauss', **params):
    """
    Multi-peak fitting processor for XRD/spectroscopy data.

    Args:
        x_col: X column name (e.g., '2theta')
        y_col: Y column name (e.g., 'Intensity')
        method: 'gauss' or 'voigt'
        params: Detection parameters
            - prominence: 0.01-1.0 (fraction of max, default 0.1)
            - min_distance: minimum points between peaks (default 10)
            - width_range: (min_width, max_width) in data units (optional)

    Returns:
        Processor function that adds:
        - Column '{method}_fit' with fitted curve
        - df.attrs['fit_results'] with peak details (FWHM, 2theta, area, etc.)
    """
    from scipy.signal import find_peaks
    from scipy.optimize import curve_fit

    prominence = params.get('prominence', 0.1)
    min_distance = params.get('min_distance', 10)
    width_range = params.get('width_range', None)

    def gauss(x, amp, cen, sigma):
        """Gaussian function"""
        return amp * np.exp(-(x - cen)**2 / (2 * sigma**2))

    def voigt(x, amp, cen, sigma, gamma):
        """Voigt profile (Gauss-Lorentz convolution)"""
        from scipy.special import voigt_profile
        return amp * voigt_profile(x - cen, sigma, gamma)

    def _fn(df: pd.DataFrame):
        if x_col not in df.columns or y_col not in df.columns:
            return df

        result = df.copy()
        x = df[x_col].values
        y = df[y_col].values

        # 1. Automatic peak detection
        peak_kwargs = {
            'prominence': prominence * y.max(),
            'distance': min_distance
        }
        if width_range:
            dx = np.median(np.diff(x)) if len(x) > 1 else 1.0
            width_pts = (width_range[0] / dx, width_range[1] / dx)
            peak_kwargs['width'] = width_pts

        peaks_idx, properties = find_peaks(y, **peak_kwargs)

        if len(peaks_idx) == 0:
            result[f'{method}_fit'] = np.zeros_like(y)
            result.attrs['fit_results'] = {
                'method': method,
                'n_peaks': 0,
                'peaks': [],
                'x_column': x_col,
                'y_column': y_col
            }
            return result

        # 2. Local fit for each peak
        y_fit_total = np.zeros_like(y, dtype=float)
        peaks_data = []

        for i, peak_idx in enumerate(peaks_idx):
            center_guess = x[peak_idx]
            amp_guess = y[peak_idx]

            widths = properties.get('widths', [5] * len(peaks_idx))
            dx = np.median(np.diff(x)) if len(x) > 1 else 1.0
            sigma_guess = widths[i] * dx / 2.355
            if sigma_guess <= 0:
                sigma_guess = 1.0

            half_window = 4 * sigma_guess
            mask = (x >= center_guess - half_window) & (x <= center_guess + half_window)

            if np.sum(mask) < 5:
                continue

            x_local = x[mask]
            y_local = y[mask]

            try:
                if method == 'gauss':
                    popt, _ = curve_fit(
                        gauss, x_local, y_local,
                        p0=[amp_guess, center_guess, sigma_guess],
                        bounds=([0, x_local.min(), 0],
                               [np.inf, x_local.max(), half_window]),
                        maxfev=2000
                    )
                    amp, center, sigma = popt
                    fwhm = 2.355 * sigma
                    area = amp * sigma * np.sqrt(2 * np.pi)
                    y_fit_total += gauss(x, *popt)
                    peaks_data.append({
                        'peak_id': i + 1,
                        '2theta': float(center),
                        'fwhm': float(fwhm),
                        'amplitude': float(amp),
                        'area': float(area),
                        'sigma': float(sigma)
                    })

                elif method == 'voigt':
                    gamma_guess = sigma_guess
                    popt, _ = curve_fit(
                        voigt, x_local, y_local,
                        p0=[amp_guess, center_guess, sigma_guess, gamma_guess],
                        bounds=([0, x_local.min(), 0, 0],
                               [np.inf, x_local.max(), half_window, half_window]),
                        maxfev=2000
                    )
                    amp, center, sigma, gamma = popt
                    fwhm_gauss = 2.355 * sigma
                    fwhm_lorentz = 2 * gamma
                    fwhm = 0.5346 * fwhm_lorentz + np.sqrt(0.2166 * fwhm_lorentz**2 + fwhm_gauss**2)
                    area = amp * sigma * np.sqrt(2 * np.pi)
                    y_fit_total += voigt(x, *popt)
                    peaks_data.append({
                        'peak_id': i + 1,
                        '2theta': float(center),
                        'fwhm': float(fwhm),
                        'amplitude': float(amp),
                        'area': float(area),
                        'sigma': float(sigma),
                        'gamma': float(gamma)
                    })

            except (RuntimeError, ValueError, TypeError):
                continue

        result[f'{method}_fit'] = y_fit_total
        result.attrs['fit_results'] = {
            'method': method,
            'n_peaks': len(peaks_data),
            'peaks': peaks_data,
            'x_column': x_col,
            'y_column': y_col
        }

        return result

    return _fn
