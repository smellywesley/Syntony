from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Acoustic voice biomarkers most cited in Parkinson's speech research: pitch and
# its variability (monotonicity), cycle-to-cycle frequency perturbation (jitter),
# amplitude perturbation (shimmer), and harmonics-to-noise ratio (breathiness).
#
# This is a deliberately dependency-light engineering baseline: F0 is tracked by
# short-time autocorrelation (numpy only, no librosa/praat), and jitter/shimmer
# are computed frame-to-frame rather than glottal-cycle to glottal-cycle. It is
# an executable prototype, NOT a validated acoustic analysis. Values must be
# compared against a validated tool (e.g. Praat) and human-labeled audio before
# use as a research endpoint, and jitter/shimmer are classically measured on
# sustained phonation rather than /pa-ta-ka/ DDK.


@dataclass(frozen=True, slots=True)
class AcousticVoiceFeatures:
    voiced_frame_count: int
    voiced_fraction: float
    mean_f0_hz: float | None
    f0_std_hz: float | None
    f0_range_hz: float | None
    jitter_local_percent: float | None
    shimmer_local_percent: float | None
    mean_hnr_db: float | None


_EMPTY = AcousticVoiceFeatures(0, 0.0, None, None, None, None, None, None)


def _linear_autocorrelation(frame: np.ndarray) -> np.ndarray:
    """Unbiased-length linear autocorrelation via zero-padded FFT."""
    n = frame.size
    size = 1
    while size < 2 * n:
        size *= 2
    spectrum = np.fft.rfft(frame, size)
    power = spectrum * np.conjugate(spectrum)
    correlation = np.fft.irfft(power, size)[:n]
    return correlation.real


def extract_acoustic_features(
    samples: np.ndarray,
    *,
    sample_rate: int,
    f0_min_hz: float = 75.0,
    f0_max_hz: float = 500.0,
    frame_ms: int = 40,
    hop_ms: int = 10,
    voicing_threshold: float = 0.45,
) -> AcousticVoiceFeatures:
    """Estimate pitch, jitter, shimmer and HNR from a mono waveform.

    Returns an all-None feature set when the segment has no detectable voicing.
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    array = np.asarray(samples, dtype=np.float64).reshape(-1)
    if array.size == 0:
        return _EMPTY

    frame_size = max(4, round(sample_rate * frame_ms / 1000))
    hop_size = max(1, round(sample_rate * hop_ms / 1000))
    if array.size < frame_size:
        return _EMPTY

    min_lag = max(1, int(sample_rate / f0_max_hz))
    max_lag = min(frame_size - 1, int(sample_rate / f0_min_hz))
    if max_lag <= min_lag:
        return _EMPTY

    window = np.hanning(frame_size)
    # Boersma (1993): dividing the signal autocorrelation by the window's own
    # autocorrelation removes the window's attenuation of the peak, so HNR and
    # voicing strength are not systematically underestimated.
    window_autocorrelation = _linear_autocorrelation(window)
    window_autocorrelation /= window_autocorrelation[0]

    frame_starts = range(0, array.size - frame_size + 1, hop_size)
    total_frames = 0

    # Per-frame results aligned by index; NaN marks an unvoiced frame so that
    # jitter/shimmer only difference genuinely adjacent voiced frames.
    periods_s: list[float] = []
    amplitudes: list[float] = []
    f0s: list[float] = []
    hnrs: list[float] = []
    voiced: list[bool] = []

    for start in frame_starts:
        total_frames += 1
        frame = array[start : start + frame_size]
        frame = frame - frame.mean()
        energy = float(np.dot(frame, frame))
        if energy <= 1e-9:
            voiced.append(False)
            periods_s.append(float("nan"))
            amplitudes.append(float("nan"))
            continue

        correlation = _linear_autocorrelation(frame * window)
        r0 = float(correlation[0])
        if r0 <= 0:
            voiced.append(False)
            periods_s.append(float("nan"))
            amplitudes.append(float("nan"))
            continue

        # Normalize by frame energy, then deconvolve the window's autocorrelation.
        with np.errstate(divide="ignore", invalid="ignore"):
            normalized = (correlation / r0) / window_autocorrelation
        normalized = np.where(np.isfinite(normalized), normalized, 0.0)

        search = normalized[min_lag : max_lag + 1]
        peak_offset = int(np.argmax(search))
        lag = min_lag + peak_offset
        r_peak = float(normalized[lag])
        if r_peak < voicing_threshold:
            voiced.append(False)
            periods_s.append(float("nan"))
            amplitudes.append(float("nan"))
            continue

        # Parabolic interpolation of the peak lag for sub-sample F0 precision.
        refined_lag = float(lag)
        if 1 <= lag < normalized.size - 1:
            c_prev, c_here, c_next = normalized[lag - 1], normalized[lag], normalized[lag + 1]
            denom = c_prev - 2.0 * c_here + c_next
            if denom != 0.0:
                refined_lag = lag + 0.5 * (c_prev - c_next) / denom
        if refined_lag <= 0:
            voiced.append(False)
            periods_s.append(float("nan"))
            amplitudes.append(float("nan"))
            continue

        f0 = sample_rate / refined_lag
        if not (f0_min_hz <= f0 <= f0_max_hz):
            voiced.append(False)
            periods_s.append(float("nan"))
            amplitudes.append(float("nan"))
            continue

        # HNR from the normalized autocorrelation peak (Boersma-style):
        # HNR = 10*log10(r / (1 - r)).
        r_clipped = min(max(r_peak, 1e-6), 1.0 - 1e-6)
        hnr_db = 10.0 * np.log10(r_clipped / (1.0 - r_clipped))

        voiced.append(True)
        periods_s.append(refined_lag / sample_rate)
        amplitudes.append(float(np.sqrt(np.mean(frame**2))))
        f0s.append(f0)
        hnrs.append(hnr_db)

    voiced_count = len(f0s)
    if voiced_count == 0:
        return _EMPTY

    f0_array = np.asarray(f0s)
    mean_f0 = float(f0_array.mean())
    f0_std = float(f0_array.std(ddof=1)) if voiced_count > 1 else 0.0
    f0_range = float(f0_array.max() - f0_array.min())
    mean_hnr = float(np.mean(hnrs))

    jitter = _local_perturbation(periods_s, voiced)
    shimmer = _local_perturbation(amplitudes, voiced)

    return AcousticVoiceFeatures(
        voiced_frame_count=voiced_count,
        voiced_fraction=voiced_count / total_frames if total_frames else 0.0,
        mean_f0_hz=mean_f0,
        f0_std_hz=f0_std,
        f0_range_hz=f0_range,
        jitter_local_percent=None if jitter is None else jitter * 100.0,
        shimmer_local_percent=None if shimmer is None else shimmer * 100.0,
        mean_hnr_db=mean_hnr,
    )


def _local_perturbation(values: list[float], voiced: list[bool]) -> float | None:
    """Mean absolute frame-to-frame difference over adjacent voiced frames,
    normalized by the mean value (the classic local jitter/shimmer form)."""
    series = np.asarray(values, dtype=np.float64)
    mask = np.asarray(voiced, dtype=bool)
    adjacent = mask[:-1] & mask[1:]
    if not np.any(adjacent):
        return None
    differences = np.abs(np.diff(series))[adjacent]
    mean_value = float(np.nanmean(series[mask]))
    if mean_value <= 0:
        return None
    return float(differences.mean()) / mean_value
