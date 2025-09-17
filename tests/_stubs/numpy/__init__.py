"""Extremely small subset of NumPy used within the unit tests.

The goal is not to emulate NumPy faithfully but to provide the handful of
operations exercised by the tests and the lightweight librosa stub.  Arrays are
represented as 1-D containers around Python lists which keeps the behaviour
predictable and dependency free.
"""

from __future__ import annotations

import math
from builtins import abs as _abs
from builtins import max as _max
from typing import Iterable, Iterator, Sequence

__all__ = [
    "ndarray",
    "array",
    "asarray",
    "zeros",
    "arange",
    "linspace",
    "abs",
    "max",
    "median",
    "floor",
    "minimum",
]


class ndarray:
    """Lightweight 1-D array wrapper supporting a subset of NumPy semantics."""

    def __init__(self, data: Iterable[float]):
        self._data = [float(value) for value in data]

    # Container protocol -------------------------------------------------
    def __iter__(self) -> Iterator[float]:
        return iter(self._data)

    def __len__(self) -> int:  # pragma: no cover - trivial helper
        return len(self._data)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"ndarray({self._data!r})"

    def __getitem__(self, item):
        if isinstance(item, slice):
            return ndarray(self._data[item])
        return self._data[item]

    def __setitem__(self, item, value) -> None:
        if isinstance(item, slice):
            indices = list(range(*item.indices(len(self._data))))
            if isinstance(value, ndarray):
                values: Sequence[float] = value._data
            elif isinstance(value, Sequence):
                values = [float(v) for v in value]
            else:
                values = [float(value)] * len(indices)
            for idx, val in zip(indices, values):
                self._data[idx] = float(val)
            return
        self._data[item] = float(value)

    # Basic arithmetic ---------------------------------------------------
    def _binary_op(self, other, operator):
        if isinstance(other, ndarray):
            iterable = other._data
        else:
            iterable = [other] * len(self._data)
        return ndarray(operator(a, b) for a, b in zip(self._data, iterable))

    def __mul__(self, other):
        return self._binary_op(other, lambda a, b: a * float(b))

    __rmul__ = __mul__

    def __add__(self, other):
        return self._binary_op(other, lambda a, b: a + float(b))

    __radd__ = __add__

    def __sub__(self, other):
        return self._binary_op(other, lambda a, b: a - float(b))

    def __truediv__(self, other):
        if isinstance(other, ndarray):
            return ndarray(
                a / float(b) if b else 0.0 for a, b in zip(self._data, other._data)
            )
        return ndarray(a / float(other) if other else 0.0 for a in self._data)

    # Convenience helpers ------------------------------------------------
    def to_list(self) -> list[float]:
        return list(self._data)


# Constructors -------------------------------------------------------------


def array(values: Iterable[float] | float | int) -> ndarray:
    if isinstance(values, ndarray):
        return ndarray(values._data)
    if isinstance(values, (int, float)):
        return ndarray([values])
    return ndarray(values)


def asarray(values: Iterable[float] | float | int, dtype=float) -> ndarray:
    arr = array(values)
    if dtype is int:
        return ndarray(int(v) for v in arr)
    if dtype is float:
        return ndarray(float(v) for v in arr)
    return arr


def zeros(length: int) -> ndarray:
    return ndarray(0.0 for _ in range(int(length)))


def arange(start, stop=None, step=1) -> ndarray:
    if stop is None:
        start, stop = 0, start
    values = []
    current = float(start)
    step = float(step)
    if step == 0:
        raise ValueError("step must not be zero")
    if step > 0:
        while current < float(stop):
            values.append(current)
            current += step
    else:
        while current > float(stop):
            values.append(current)
            current += step
    return ndarray(values)


def linspace(start: float, stop: float, num: int) -> ndarray:
    if num <= 1:
        return array([float(start)])
    step = (float(stop) - float(start)) / (num - 1)
    return ndarray(float(start) + step * i for i in range(num))


# Statistics ---------------------------------------------------------------


def abs(values: ndarray | Iterable[float]) -> ndarray:
    arr = values if isinstance(values, ndarray) else array(values)
    return ndarray(_abs(v) for v in arr)


def max(values: ndarray | Iterable[float]) -> float:
    arr = values if isinstance(values, ndarray) else array(values)
    return _max(arr._data) if arr._data else 0.0


def median(values: ndarray | Iterable[float]) -> float:
    arr = values if isinstance(values, ndarray) else array(values)
    data = sorted(arr._data)
    if not data:
        raise ValueError("no median for empty data")
    mid = len(data) // 2
    if len(data) % 2:
        return data[mid]
    return (data[mid - 1] + data[mid]) / 2.0


def floor(values: ndarray | Iterable[float]) -> ndarray:
    arr = values if isinstance(values, ndarray) else array(values)
    return ndarray(float(math.floor(v)) for v in arr)


def minimum(a: ndarray | Iterable[float], b: ndarray | Iterable[float]) -> ndarray:
    arr_a = a if isinstance(a, ndarray) else array(a)
    arr_b = b if isinstance(b, ndarray) else array(b)
    return ndarray(min(x, y) for x, y in zip(arr_a, arr_b))
