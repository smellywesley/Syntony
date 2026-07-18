"""Synthetic-ground-truth tests for the acoustic voice feature baseline:
a clean tone recovers its F0 with low perturbation and high HNR; added noise
lowers HNR; frequency drift raises pitch variability; silence yields no voicing."""

import numpy as np

from pipelines.audio.acoustic import extract_acoustic_features

SAMPLE_RATE = 16000


def _tone(f0_hz: float, seconds: float = 1.0, amplitude: float = 0.5) -> np.ndarray:
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    return amplitude * np.sin(2 * np.pi * f0_hz * t)


def test_clean_tone_recovers_f0_with_low_perturbation_and_high_hnr():
    features = extract_acoustic_features(_tone(150.0), sample_rate=SAMPLE_RATE)
    assert features.mean_f0_hz is not None
    assert abs(features.mean_f0_hz - 150.0) < 3.0
    assert features.voiced_fraction > 0.9
    # A stationary tone has near-zero cycle-to-cycle perturbation.
    assert features.jitter_local_percent is not None and features.jitter_local_percent < 1.0
    assert features.shimmer_local_percent is not None and features.shimmer_local_percent < 2.0
    # A periodic signal is almost pure harmonics: HNR should be high.
    assert features.mean_hnr_db is not None and features.mean_hnr_db > 20.0


def test_added_noise_lowers_hnr():
    clean = _tone(160.0)
    rng = np.random.default_rng(7)
    noisy = clean + rng.normal(0.0, 0.25, size=clean.size)

    clean_features = extract_acoustic_features(clean, sample_rate=SAMPLE_RATE)
    noisy_features = extract_acoustic_features(noisy, sample_rate=SAMPLE_RATE)

    assert clean_features.mean_hnr_db is not None and noisy_features.mean_hnr_db is not None
    assert noisy_features.mean_hnr_db < clean_features.mean_hnr_db


def test_frequency_drift_raises_pitch_variability():
    steady = extract_acoustic_features(_tone(150.0), sample_rate=SAMPLE_RATE)
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    drift = 0.5 * np.sin(2 * np.pi * (140.0 + 40.0 * t) * t)  # sweeping F0
    swept = extract_acoustic_features(drift, sample_rate=SAMPLE_RATE)

    assert steady.f0_std_hz is not None and swept.f0_std_hz is not None
    assert swept.f0_std_hz > steady.f0_std_hz


def test_silence_yields_no_voicing():
    features = extract_acoustic_features(np.zeros(SAMPLE_RATE), sample_rate=SAMPLE_RATE)
    assert features.voiced_frame_count == 0
    assert features.mean_f0_hz is None
    assert features.jitter_local_percent is None
    assert features.mean_hnr_db is None


def test_empty_and_invalid_inputs():
    assert extract_acoustic_features(np.array([]), sample_rate=SAMPLE_RATE).voiced_frame_count == 0
    try:
        extract_acoustic_features(_tone(150.0), sample_rate=0)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for non-positive sample_rate")
