"""
test_denoise_methods.py

Unit tests for denoising methods.
Tests can be run headless (no GUI required).

Run with: python -m pytest tests/test_denoise_methods.py -v
"""

import numpy as np
import pandas as pd
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from denoise_methods import (
    savitzky_golay_denoise,
    median_filter_denoise,
    wavelet_denoise,
    fft_lowpass_denoise,
    denoise
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def clean_signal():
    """Generate clean sinusoidal signal."""
    t = np.linspace(0, 4 * np.pi, 200)
    return np.sin(t) + 0.5 * np.sin(3 * t)


@pytest.fixture
def noisy_signal(clean_signal):
    """Generate noisy signal (Gaussian noise)."""
    np.random.seed(42)
    noise = np.random.normal(0, 0.2, len(clean_signal))
    return clean_signal + noise


@pytest.fixture
def spiky_signal(clean_signal):
    """Generate signal with spikes (impulse noise)."""
    signal_with_spikes = clean_signal.copy()
    spike_indices = [20, 50, 100, 150]
    for idx in spike_indices:
        signal_with_spikes[idx] += np.random.choice([-3, 3])
    return signal_with_spikes


@pytest.fixture
def signal_with_nan(noisy_signal):
    """Generate signal with NaN values."""
    signal_nan = noisy_signal.copy()
    signal_nan[[10, 50, 100]] = np.nan
    return signal_nan


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_snr(clean, noisy):
    """Calculate Signal-to-Noise Ratio in dB."""
    signal_power = np.mean(clean ** 2)
    noise_power = np.mean((noisy - clean) ** 2)
    if noise_power == 0:
        return np.inf
    return 10 * np.log10(signal_power / noise_power)


def calculate_mse(reference, denoised):
    """Calculate Mean Squared Error."""
    return np.mean((reference - denoised) ** 2)


# =============================================================================
# TEST SAVITZKY-GOLAY
# =============================================================================

class TestSavitzkyGolay:
    def test_basic_denoising(self, clean_signal, noisy_signal):
        """Test basic Savitzky-Golay denoising."""
        denoised = savitzky_golay_denoise(noisy_signal, window=11, polyorder=3)

        # Should reduce noise
        snr_before = calculate_snr(clean_signal, noisy_signal)
        snr_after = calculate_snr(clean_signal, denoised)
        assert snr_after > snr_before, "SNR should improve after denoising"

        # Should preserve signal length
        assert len(denoised) == len(noisy_signal)

    def test_preserves_peaks(self, clean_signal):
        """Test that Savitzky-Golay preserves peak shapes."""
        denoised = savitzky_golay_denoise(clean_signal, window=11, polyorder=3)

        # Peaks should be at same locations
        clean_peaks_idx = np.where(np.diff(np.sign(np.diff(clean_signal))) < 0)[0]
        denoised_peaks_idx = np.where(np.diff(np.sign(np.diff(denoised))) < 0)[0]

        # Should have similar number of peaks
        assert abs(len(clean_peaks_idx) - len(denoised_peaks_idx)) <= 1

    def test_invalid_parameters(self, noisy_signal):
        """Test parameter validation."""
        # Window too small
        with pytest.raises(ValueError):
            savitzky_golay_denoise(noisy_signal, window=2)

        # Polyorder >= window
        with pytest.raises(ValueError):
            savitzky_golay_denoise(noisy_signal, window=11, polyorder=11)

        # Negative polyorder
        with pytest.raises(ValueError):
            savitzky_golay_denoise(noisy_signal, window=11, polyorder=-1)

    def test_handles_nan(self, signal_with_nan):
        """Test NaN handling."""
        denoised = savitzky_golay_denoise(signal_with_nan, window=11, polyorder=3)

        # NaN positions should be preserved
        assert np.isnan(denoised[10])
        assert np.isnan(denoised[50])
        assert np.isnan(denoised[100])

        # Non-NaN values should be processed
        non_nan_mask = ~np.isnan(signal_with_nan)
        assert not np.all(np.isnan(denoised[non_nan_mask]))

    def test_pandas_series(self, noisy_signal):
        """Test with pandas Series input."""
        series = pd.Series(noisy_signal, name='test_signal')
        denoised = savitzky_golay_denoise(series, window=11)

        assert isinstance(denoised, np.ndarray)
        assert len(denoised) == len(series)


# =============================================================================
# TEST MEDIAN FILTER
# =============================================================================

class TestMedianFilter:
    def test_removes_spikes(self, clean_signal, spiky_signal):
        """Test median filter removes impulse noise."""
        denoised = median_filter_denoise(spiky_signal, kernel_size=5)

        # MSE should be much lower after removing spikes
        mse_before = calculate_mse(clean_signal, spiky_signal)
        mse_after = calculate_mse(clean_signal, denoised)
        assert mse_after < mse_before * 0.5, "Should significantly reduce spike noise"

    def test_preserves_edges(self):
        """Test that median filter preserves step edges."""
        # Create step signal
        step_signal = np.concatenate([np.zeros(50), np.ones(50)])
        noisy_step = step_signal + np.random.normal(0, 0.1, 100)

        denoised = median_filter_denoise(noisy_step, kernel_size=5)

        # Step should still be at ~index 50
        step_idx = np.where(np.diff(denoised) > 0.5)[0][0]
        assert 45 <= step_idx <= 55, "Step position should be preserved"

    def test_kernel_size_validation(self, noisy_signal):
        """Test kernel size validation."""
        # Too small
        with pytest.raises(ValueError):
            median_filter_denoise(noisy_signal, kernel_size=1)

        # Auto-correction to odd number
        denoised_even = median_filter_denoise(noisy_signal, kernel_size=6)
        denoised_odd = median_filter_denoise(noisy_signal, kernel_size=7)
        # Both should work (even gets corrected to 7)
        assert len(denoised_even) == len(noisy_signal)
        np.testing.assert_array_equal(denoised_even, denoised_odd)

    def test_handles_nan(self, signal_with_nan):
        """Test NaN handling."""
        denoised = median_filter_denoise(signal_with_nan, kernel_size=5)

        # NaN positions should be preserved
        assert np.isnan(denoised[10])
        assert np.isnan(denoised[50])
        assert np.isnan(denoised[100])


# =============================================================================
# TEST WAVELET DENOISING
# =============================================================================

class TestWaveletDenoise:
    def test_basic_denoising(self, clean_signal, noisy_signal):
        """Test basic wavelet denoising."""
        try:
            import pywt
        except ImportError:
            pytest.skip("PyWavelets not installed")

        denoised = wavelet_denoise(noisy_signal, wavelet='db4', mode='soft')

        # Should reduce noise
        snr_before = calculate_snr(clean_signal, noisy_signal)
        snr_after = calculate_snr(clean_signal, denoised)
        assert snr_after > snr_before, "SNR should improve"

        # Should preserve length
        assert len(denoised) == len(noisy_signal)

    def test_soft_vs_hard_thresholding(self, noisy_signal):
        """Test difference between soft and hard thresholding."""
        try:
            import pywt
        except ImportError:
            pytest.skip("PyWavelets not installed")

        soft_denoised = wavelet_denoise(noisy_signal, mode='soft')
        hard_denoised = wavelet_denoise(noisy_signal, mode='hard')

        # Results should be different
        assert not np.array_equal(soft_denoised, hard_denoised)

        # Both should have same length
        assert len(soft_denoised) == len(hard_denoised) == len(noisy_signal)

    def test_different_wavelets(self, noisy_signal):
        """Test different wavelet types."""
        try:
            import pywt
        except ImportError:
            pytest.skip("PyWavelets not installed")

        wavelets = ['db4', 'sym8', 'coif5']
        results = []

        for wav in wavelets:
            denoised = wavelet_denoise(noisy_signal, wavelet=wav)
            results.append(denoised)
            assert len(denoised) == len(noisy_signal)

        # Different wavelets should give slightly different results
        assert not np.array_equal(results[0], results[1])

    def test_invalid_wavelet(self, noisy_signal):
        """Test invalid wavelet name."""
        try:
            import pywt
        except ImportError:
            pytest.skip("PyWavelets not installed")

        with pytest.raises(ValueError):
            wavelet_denoise(noisy_signal, wavelet='invalid_wavelet')

    def test_invalid_mode(self, noisy_signal):
        """Test invalid thresholding mode."""
        try:
            import pywt
        except ImportError:
            pytest.skip("PyWavelets not installed")

        with pytest.raises(ValueError):
            wavelet_denoise(noisy_signal, mode='invalid_mode')

    def test_handles_nan(self, signal_with_nan):
        """Test NaN handling."""
        try:
            import pywt
        except ImportError:
            pytest.skip("PyWavelets not installed")

        denoised = wavelet_denoise(signal_with_nan, wavelet='db4')

        # NaN positions should be preserved
        assert np.isnan(denoised[10])
        assert np.isnan(denoised[50])
        assert np.isnan(denoised[100])


# =============================================================================
# TEST FFT LOW-PASS
# =============================================================================

class TestFFTLowpass:
    def test_removes_high_frequency_noise(self, clean_signal):
        """Test FFT low-pass removes high-frequency components."""
        # Add high-frequency noise
        np.random.seed(42)
        high_freq_noise = 0.5 * np.sin(50 * np.linspace(0, 4*np.pi, len(clean_signal)))
        noisy = clean_signal + high_freq_noise

        denoised = fft_lowpass_denoise(noisy, cutoff_freq=0.1)

        # Should be closer to clean signal
        mse_before = calculate_mse(clean_signal, noisy)
        mse_after = calculate_mse(clean_signal, denoised)
        assert mse_after < mse_before * 0.5

    def test_cutoff_frequency_effect(self, noisy_signal):
        """Test effect of different cutoff frequencies."""
        denoised_aggressive = fft_lowpass_denoise(noisy_signal, cutoff_freq=0.05)
        denoised_mild = fft_lowpass_denoise(noisy_signal, cutoff_freq=0.2)

        # More aggressive filtering should give smoother result
        diff_aggressive = np.sum(np.abs(np.diff(denoised_aggressive)))
        diff_mild = np.sum(np.abs(np.diff(denoised_mild)))
        assert diff_aggressive < diff_mild

    def test_invalid_cutoff(self, noisy_signal):
        """Test cutoff frequency validation."""
        # Too low
        with pytest.raises(ValueError):
            fft_lowpass_denoise(noisy_signal, cutoff_freq=0)

        # Too high
        with pytest.raises(ValueError):
            fft_lowpass_denoise(noisy_signal, cutoff_freq=0.6)

        # Negative
        with pytest.raises(ValueError):
            fft_lowpass_denoise(noisy_signal, cutoff_freq=-0.1)

    def test_preserves_length(self, noisy_signal):
        """Test output length preservation."""
        denoised = fft_lowpass_denoise(noisy_signal, cutoff_freq=0.1)
        assert len(denoised) == len(noisy_signal)

    def test_handles_nan(self, signal_with_nan):
        """Test NaN handling."""
        denoised = fft_lowpass_denoise(signal_with_nan, cutoff_freq=0.1)

        # NaN positions should be preserved
        assert np.isnan(denoised[10])
        assert np.isnan(denoised[50])
        assert np.isnan(denoised[100])


# =============================================================================
# TEST HIGH-LEVEL DISPATCHER
# =============================================================================

class TestDenoiseDispatcher:
    def test_savgol_method(self, noisy_signal):
        """Test dispatcher with Savitzky-Golay."""
        denoised = denoise(noisy_signal, method='savgol', window=11, polyorder=3)
        assert len(denoised) == len(noisy_signal)

    def test_median_method(self, noisy_signal):
        """Test dispatcher with median filter."""
        denoised = denoise(noisy_signal, method='median', kernel_size=5)
        assert len(denoised) == len(noisy_signal)

    def test_wavelet_method(self, noisy_signal):
        """Test dispatcher with wavelet."""
        try:
            import pywt
        except ImportError:
            pytest.skip("PyWavelets not installed")

        denoised = denoise(noisy_signal, method='wavelet', wavelet='db4')
        assert len(denoised) == len(noisy_signal)

    def test_fft_method(self, noisy_signal):
        """Test dispatcher with FFT."""
        denoised = denoise(noisy_signal, method='fft', cutoff_freq=0.1)
        assert len(denoised) == len(noisy_signal)

    def test_invalid_method(self, noisy_signal):
        """Test invalid method name."""
        with pytest.raises(ValueError):
            denoise(noisy_signal, method='invalid_method')

    def test_dataframe_processing(self, noisy_signal):
        """Test DataFrame processing (applies to numeric columns)."""
        df = pd.DataFrame({
            'x': np.arange(len(noisy_signal)),
            'y1': noisy_signal,
            'y2': noisy_signal * 2,
            'label': ['A'] * len(noisy_signal)  # Non-numeric column
        })

        df_denoised = denoise(df, method='median', kernel_size=5)

        # Should be DataFrame
        assert isinstance(df_denoised, pd.DataFrame)

        # Should have same shape
        assert df_denoised.shape == df.shape

        # Numeric columns should be denoised
        assert not np.array_equal(df_denoised['y1'].values, df['y1'].values)
        assert not np.array_equal(df_denoised['y2'].values, df['y2'].values)

        # Non-numeric column should be unchanged
        assert df_denoised['label'].equals(df['label'])
        assert df_denoised['x'].equals(df['x'])  # x unchanged (integers)

    def test_series_preservation(self, noisy_signal):
        """Test that Series is returned when input is Series."""
        series = pd.Series(noisy_signal, name='test_signal')
        denoised = denoise(series, method='median', kernel_size=5)

        assert isinstance(denoised, pd.Series)
        assert denoised.name == 'test_signal'
        assert len(denoised) == len(series)


# =============================================================================
# TEST EDGE CASES
# =============================================================================

class TestEdgeCases:
    def test_empty_array(self):
        """Test handling of empty arrays."""
        empty = np.array([])

        with pytest.raises(ValueError):
            savitzky_golay_denoise(empty)

        with pytest.raises(ValueError):
            median_filter_denoise(empty)

    def test_all_nan_array(self):
        """Test handling of all-NaN arrays."""
        all_nan = np.full(100, np.nan)

        with pytest.raises(ValueError):
            savitzky_golay_denoise(all_nan)

    def test_very_short_signal(self):
        """Test with very short signals."""
        short_signal = np.array([1.0, 2.0, 3.0, 2.0, 1.0])

        # Should work with appropriate window size
        denoised = savitzky_golay_denoise(short_signal, window=3, polyorder=1)
        assert len(denoised) == len(short_signal)

        denoised = median_filter_denoise(short_signal, kernel_size=3)
        assert len(denoised) == len(short_signal)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
