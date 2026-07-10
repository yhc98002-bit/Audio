"""Canonical ADSR detector thresholds shared by generation and analysis code."""

VOCAL_PRESENCE_THRESHOLD = 0.1791
NEAR_SILENT_RMS_THRESHOLD = 1e-3


def is_vocal_present(vocal_energy_ratio: float, near_silent: bool) -> bool:
    return vocal_energy_ratio >= VOCAL_PRESENCE_THRESHOLD and not near_silent
