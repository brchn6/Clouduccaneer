"""Very small subset of :mod:`librosa` used in the tests.

The implementation is intentionally lightweight and deterministic so the unit
suite can exercise the CloudBuccaneer BPM utilities without pulling in the real
scientific stack.  Only the functions touched by the tests are provided.  The
behaviour is not meant to be feature complete but mirrors the public API
surface required by :mod:`cb.bpm`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np

__all__ = ["load", "beat", "onset", "feature"]


def load(path: str | Path, sr: int | None = None) -> Tuple[np.ndarray, int]:
    """Load audio data from the JSON files produced by the soundfile stub."""

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    data = np.asarray(payload.get("data", []), dtype=float)
    sample_rate = int(payload.get("samplerate", 0))
    if sr not in (None, sample_rate) and sample_rate > 0:
        # Naive resampling via interpolation – good enough for the tests.
        duration = len(data) / sample_rate if sample_rate else 0
        new_length = max(1, int(duration * sr))
        indices = np.linspace(0, len(data) - 1, new_length)
        left = np.floor(indices).astype(int)
        right = np.minimum(left + 1, len(data) - 1)
        fraction = indices - left
        data = (1 - fraction) * data[left] + fraction * data[right]
        sample_rate = sr
    return data, sample_rate


def _find_peaks(samples: np.ndarray, sample_rate: int, threshold: float) -> np.ndarray:
    if len(samples) == 0 or sample_rate <= 0:
        return np.asarray([], dtype=int)
    max_amp = float(np.max(np.abs(samples)))
    if max_amp <= 0:
        return np.asarray([], dtype=int)

    cutoff = max_amp * threshold
    refractory = max(1, int(sample_rate * 0.1))
    peaks = []
    for idx, value in enumerate(samples):
        if abs(value) < cutoff:
            continue
        if peaks and idx - peaks[-1] < refractory:
            continue
        peaks.append(idx)
    return np.asarray(peaks, dtype=int)


def _tempo_from_indices(peaks: Iterable[int], sample_rate: int) -> float | None:
    peaks = list(peaks)
    if len(peaks) < 2 or sample_rate <= 0:
        return None
    gaps = [b - a for a, b in zip(peaks, peaks[1:]) if b > a]
    if not gaps:
        return None
    median_gap = float(np.median(gaps))
    if median_gap <= 0:
        return None
    return 60.0 * sample_rate / median_gap


def _estimate_tempo(samples: np.ndarray, sample_rate: int) -> float | None:
    tempos = []
    for threshold in (0.6, 0.4, 0.8):
        tempo = _tempo_from_indices(_find_peaks(samples, sample_rate, threshold), sample_rate)
        if tempo:
            tempos.append(tempo)
    if not tempos:
        return None
    return float(np.median(tempos))


class beat:  # noqa: N801 - match librosa's namespace style
    @staticmethod
    def beat_track(y: np.ndarray, sr: int) -> Tuple[float | None, None]:
        tempo = _estimate_tempo(y, sr) or 0.0
        return float(tempo), None


class onset:  # noqa: N801
    @staticmethod
    def onset_strength(y: np.ndarray, sr: int) -> np.ndarray:
        # Smooth absolute value acts as a simple onset envelope.
        return np.abs(y)


class feature:  # noqa: N801
    class rhythm:  # noqa: N801
        @staticmethod
        def tempo(
            y: np.ndarray | None = None,
            sr: int = 22050,
            onset_envelope: np.ndarray | None = None,
            max_tempo: int | None = None,
        ) -> np.ndarray:
            samples = onset_envelope if onset_envelope is not None else y
            tempo = _estimate_tempo(np.asarray(samples) if samples is not None else np.asarray([]), sr)
            value = tempo or 0.0
            return np.asarray([float(value)], dtype=float)
