"""
denoise_methods.py

Signal denoising methods for electrochemical and scientific data.
Provides multiple filtering approaches for noise reduction while preserving signal features.
"""

import numpy as np
import pandas as pd
from scipy import signal
from typing import Union, Optional, Literal


def _validate_data(data: Union[np.ndarray, pd.Series]) -> np.ndarray:
    """
    Validate and convert input data to numpy array.

    Args:
        data: Input data (numpy array or pandas Series)

    Returns:
        Validated numpy array

    Raises:
        ValueError: If data is empty or contains only NaN values
    """
    if isinstance(data, pd.Series):
        arr = data.values
    else:
        arr = np.asarray(data)

    if len(arr) == 0:
        raise ValueError("Input data is empty")

    if np.all(np.isnan(arr)):
        raise ValueError("Input data contains only NaN values")

    return arr


def _validate_window_size(window: int, data_length: int, name: str = "window") -> int:
    """
    Validate window size parameter.

    Args:
        window: Window size to validate
        data_length: Length of data array
        name: Parameter name for error messages

    Returns:
        Validated window size

    Raises:
        ValueError: If window is invalid
    """
    if window < 3:
        raise ValueError(f"{name} must be >= 3 (got {window})")

    if window % 2 == 0:
        window += 1  # Make odd

    if window > data_length:
        raise ValueError(f"{name} ({window}) exceeds data length ({data_length})")

    return window


# =============================================================================
# SAVITZKY-GOLAY FILTER
# =============================================================================

def savitzky_golay_denoise(
    data: Union[np.ndarray, pd.Series],
    window: int = 11,
    polyorder: int = 3
) -> np.ndarray:
    """
    Denoise data using Savitzky-Golay filter.

    The Savitzky-Golay filter smooths data by fitting successive sub-sets
    of adjacent data points with a polynomial via least squares.
    Preserves peak shapes and high-frequency features better than moving average.

    Args:
        data: Input signal (1D array or Series)
        window: Window length (must be odd, >= polyorder+2). Default: 11
        polyorder: Polynomial order for fitting. Default: 3

    Returns:
        Denoised signal as numpy array

    Raises:
        ValueError: If parameters are invalid

    Example:
        >>> noisy_signal = np.sin(np.linspace(0, 10, 100)) + np.random.normal(0, 0.1, 100)
        >>> clean_signal = savitzky_golay_denoise(noisy_signal, window=11, polyorder=3)
    """
    arr = _validate_data(data)
    window = _validate_window_size(window, len(arr), "window")

    if polyorder >= window:
        raise ValueError(f"polyorder ({polyorder}) must be < window ({window})")

    if polyorder < 0:
        raise ValueError(f"polyorder must be >= 0 (got {polyorder})")

    # Handle NaN values
    if np.any(np.isnan(arr)):
        result = arr.copy()
        valid_mask = ~np.isnan(arr)
        result[valid_mask] = signal.savgol_filter(arr[valid_mask], window, polyorder)
        return result

    return signal.savgol_filter(arr, window, polyorder)


# =============================================================================
# MEDIAN FILTER
# =============================================================================

def median_filter_denoise(
    data: Union[np.ndarray, pd.Series],
    kernel_size: int = 5
) -> np.ndarray:
    """
    Denoise data using median filter.

    Median filter replaces each point with the median of surrounding points.
    Highly effective at removing spike noise (salt-and-pepper) while preserving
    edges better than mean filters.

    Args:
        data: Input signal (1D array or Series)
        kernel_size: Size of the median filter kernel (must be odd). Default: 5

    Returns:
        Denoised signal as numpy array

    Raises:
        ValueError: If parameters are invalid

    Example:
        >>> spiky_signal = np.sin(np.linspace(0, 10, 100))
        >>> spiky_signal[20] = 10  # Add spike
        >>> clean_signal = median_filter_denoise(spiky_signal, kernel_size=5)
    """
    arr = _validate_data(data)
    kernel_size = _validate_window_size(kernel_size, len(arr), "kernel_size")

    # Handle NaN values
    if np.any(np.isnan(arr)):
        result = arr.copy()
        valid_mask = ~np.isnan(arr)
        result[valid_mask] = signal.medfilt(arr[valid_mask], kernel_size)
        return result

    return signal.medfilt(arr, kernel_size)


# =============================================================================
# WAVELET DENOISING
# =============================================================================

def wavelet_denoise(
    data: Union[np.ndarray, pd.Series],
    wavelet: str = 'db4',
    level: Optional[int] = None,
    mode: Literal['soft', 'hard'] = 'soft'
) -> np.ndarray:
    """
    Denoise data using wavelet transform thresholding.

    Wavelet denoising decomposes signal into different frequency scales,
    applies threshold to remove noise coefficients, then reconstructs.
    Effective for multi-scale noise patterns.

    Args:
        data: Input signal (1D array or Series)
        wavelet: Wavelet type. Options: 'db4' (Daubechies 4), 'sym8' (Symlet 8),
                 'coif5' (Coiflet 5). Default: 'db4'
        level: Decomposition level. If None, uses maximum possible level. Default: None
        mode: Thresholding mode ('soft' or 'hard'). Soft is smoother. Default: 'soft'

    Returns:
        Denoised signal as numpy array

    Raises:
        ValueError: If parameters are invalid
        ImportError: If pywt is not installed

    Example:
        >>> noisy_signal = np.sin(np.linspace(0, 10, 100)) + np.random.normal(0, 0.1, 100)
        >>> clean_signal = wavelet_denoise(noisy_signal, wavelet='db4', mode='soft')
    """
    try:
        import pywt
    except ImportError:
        raise ImportError(
            "PyWavelets (pywt) is required for wavelet denoising. "
            "Install with: pip install pywt"
        )

    arr = _validate_data(data)

    # Validate wavelet
    available_wavelets = pywt.wavelist(kind='discrete')
    if wavelet not in available_wavelets:
        raise ValueError(
            f"Unknown wavelet '{wavelet}'. "
            f"Available: {', '.join(available_wavelets[:10])}..."
        )

    # Validate mode
    if mode not in ['soft', 'hard']:
        raise ValueError(f"mode must be 'soft' or 'hard' (got '{mode}')")

    # Determine decomposition level
    if level is None:
        level = pywt.dwt_max_level(len(arr), wavelet)
    elif level < 1:
        raise ValueError(f"level must be >= 1 (got {level})")

    # Handle NaN values
    if np.any(np.isnan(arr)):
        result = arr.copy()
        valid_mask = ~np.isnan(arr)
        result[valid_mask] = _wavelet_denoise_core(
            arr[valid_mask], wavelet, level, mode
        )
        return result

    return _wavelet_denoise_core(arr, wavelet, level, mode)


def _wavelet_denoise_core(
    arr: np.ndarray,
    wavelet: str,
    level: int,
    mode: str
) -> np.ndarray:
    """
    Core wavelet denoising implementation (no NaN handling).

    Uses VisuShrink threshold: threshold = sigma * sqrt(2 * log(N))
    where sigma is estimated from the finest scale wavelet coefficients.
    """
    import pywt

    # Decompose signal
    coeffs = pywt.wavedec(arr, wavelet, level=level)

    # Estimate noise standard deviation from finest detail coefficients
    sigma = np.median(np.abs(coeffs[-1])) / 0.6745

    # Calculate threshold (VisuShrink)
    threshold = sigma * np.sqrt(2 * np.log(len(arr)))

    # Apply threshold to detail coefficients (skip approximation coeffs[0])
    coeffs_thresh = [coeffs[0]]  # Keep approximation unchanged
    for detail_coeff in coeffs[1:]:
        if mode == 'soft':
            thresh_coeff = pywt.threshold(detail_coeff, threshold, mode='soft')
        else:
            thresh_coeff = pywt.threshold(detail_coeff, threshold, mode='hard')
        coeffs_thresh.append(thresh_coeff)

    # Reconstruct signal
    denoised = pywt.waverec(coeffs_thresh, wavelet)

    # waverec may return slightly different length due to padding
    return denoised[:len(arr)]


# =============================================================================
# FFT LOW-PASS FILTER
# =============================================================================

def fft_lowpass_denoise(
    data: Union[np.ndarray, pd.Series],
    cutoff_freq: float = 0.1
) -> np.ndarray:
    """
    Denoise data using FFT-based low-pass filter.

    Transforms signal to frequency domain, removes high-frequency components
    above cutoff, then inverse transforms back to time domain.
    Simple and effective for removing high-frequency noise.

    Args:
        data: Input signal (1D array or Series)
        cutoff_freq: Cutoff frequency as fraction of Nyquist frequency (0 to 0.5).
                     Lower values = more aggressive filtering. Default: 0.1

    Returns:
        Denoised signal as numpy array

    Raises:
        ValueError: If parameters are invalid

    Example:
        >>> noisy_signal = np.sin(np.linspace(0, 10, 100)) + np.random.normal(0, 0.1, 100)
        >>> clean_signal = fft_lowpass_denoise(noisy_signal, cutoff_freq=0.1)
    """
    arr = _validate_data(data)

    if not 0 < cutoff_freq <= 0.5:
        raise ValueError(
            f"cutoff_freq must be in range (0, 0.5] (got {cutoff_freq})"
        )

    # Handle NaN values
    if np.any(np.isnan(arr)):
        result = arr.copy()
        valid_mask = ~np.isnan(arr)
        result[valid_mask] = _fft_lowpass_core(arr[valid_mask], cutoff_freq)
        return result

    return _fft_lowpass_core(arr, cutoff_freq)


def _fft_lowpass_core(arr: np.ndarray, cutoff_freq: float) -> np.ndarray:
    """Core FFT low-pass filter implementation (no NaN handling)."""
    # Compute FFT
    fft_data = np.fft.fft(arr)
    frequencies = np.fft.fftfreq(len(arr))

    # Create low-pass filter mask
    # cutoff_freq is fraction of Nyquist (0.5), so compare with abs(freq)
    filter_mask = np.abs(frequencies) <= cutoff_freq

    # Apply filter in frequency domain
    fft_filtered = fft_data * filter_mask

    # Inverse FFT to get denoised signal
    denoised = np.fft.ifft(fft_filtered).real

    return denoised


# =============================================================================
# HIGH-LEVEL DISPATCHER
# =============================================================================

def denoise(
    data: Union[np.ndarray, pd.Series, pd.DataFrame],
    method: Literal['savgol', 'median', 'wavelet', 'fft'] = 'savgol',
    **kwargs
) -> Union[np.ndarray, pd.Series, pd.DataFrame]:
    """
    High-level denoising dispatcher function.

    Automatically selects appropriate denoising method and applies to data.
    Handles both single arrays and DataFrames (applies to numeric columns).

    Args:
        data: Input data (array, Series, or DataFrame)
        method: Denoising method. Options:
                - 'savgol': Savitzky-Golay filter (kwargs: window, polyorder)
                - 'median': Median filter (kwargs: kernel_size)
                - 'wavelet': Wavelet denoising (kwargs: wavelet, level, mode)
                - 'fft': FFT low-pass (kwargs: cutoff_freq)
        **kwargs: Method-specific parameters (see individual functions)

    Returns:
        Denoised data (same type as input)

    Example:
        >>> # Single array
        >>> clean = denoise(noisy_array, method='savgol', window=11, polyorder=3)
        >>>
        >>> # DataFrame (applies to numeric columns)
        >>> df_clean = denoise(df, method='median', kernel_size=5)
    """
    # DataFrame handling
    if isinstance(data, pd.DataFrame):
        result = data.copy()
        numeric_cols = result.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            result[col] = denoise(result[col], method=method, **kwargs)

        return result

    # Select method (normalize to lowercase)
    method_lower = method.lower()

    method_map = {
        'savgol': savitzky_golay_denoise,
        'median': median_filter_denoise,
        'wavelet': wavelet_denoise,
        'fft': fft_lowpass_denoise
    }

    if method_lower not in method_map:
        raise ValueError(
            f"Unknown method '{method}'. "
            f"Available: {', '.join(method_map.keys())}"
        )

    denoiser = method_map[method_lower]
    denoised_arr = denoiser(data, **kwargs)

    # Preserve pandas Series if input was Series
    if isinstance(data, pd.Series):
        return pd.Series(denoised_arr, index=data.index, name=data.name)

    return denoised_arr
