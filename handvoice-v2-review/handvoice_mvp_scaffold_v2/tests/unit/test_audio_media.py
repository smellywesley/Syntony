import numpy as np

from pipelines.audio.media import extract_energy_events


def test_energy_extractor_finds_separated_bursts():
    sample_rate = 16000
    samples = np.zeros(sample_rate * 2, dtype=float)
    for start_ms in (200, 600, 1000, 1400):
        start = round(start_ms * sample_rate / 1000)
        end = start + round(100 * sample_rate / 1000)
        t = np.arange(end - start) / sample_rate
        samples[start:end] = 0.7 * np.sin(2 * np.pi * 220 * t)
    result = extract_energy_events(samples, sample_rate=sample_rate)
    assert len(result.voiced_intervals) == 4
    assert len(result.onset_times_ms) == 4
