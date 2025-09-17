"""Tiny stub of :mod:`soundfile` used in the test-suite.

The real `soundfile` package offers comprehensive audio IO for NumPy arrays.
For the purposes of these tests we merely need to persist synthetic audio data
that is generated during the test run.  The :func:`write` helper below stores
samples as JSON alongside the sampling rate, which is sufficient for the
lightweight BPM detector implemented in :mod:`cb.bpm`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def _to_float_list(data: Iterable[float]) -> list[float]:
    values: list[float] = []
    for item in data:
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            continue
    return values


def write(file: str | Path, data: Iterable[float], samplerate: int) -> None:
    """Persist *data* and *samplerate* to *file*.

    Files are stored as UTF-8 encoded JSON documents to keep the implementation
    dependency free.  The directory containing *file* is created automatically
    if required.
    """

    path = Path(file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"samplerate": int(samplerate), "data": _to_float_list(data)}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)
