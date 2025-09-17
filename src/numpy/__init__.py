"""Very small subset of NumPy used by the tests.

The goal is not to be feature complete but merely to support the handful of
helpers exercised during the unit tests: array creation, ``zeros`` and
``arange`` constructors as well as ``abs``/``max``/``median`` helpers and basic
arithmetic.  The implementation operates on Python lists which keeps it easy to
reason about and removes the heavy dependency on the real NumPy package.
"""

from __future__ import annotations

from builtins import abs as _abs
from builtins import max as _max
from typing import Iterable, Iterator, Sequence


class ndarray:
    """Lightweight 1-D array wrapper supporting a subset of NumPy semantics."""

    def __init__(self, data: Iterable[float]):
        self._data = [float(value) for value in data]

    def __iter__(self) -> Iterator[float]:
        return iter(self._data)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._data)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"ndarray({self._data!r})"

    def __getitem__(self, item):
        if isinstance(item, slice):
            return ndarray(self._data[item])
        return self._data[item]

    def __setitem__(self, item, value) -> None:
        if isinstance(item, slice):
            index_list = list(range(*item.indices(len(self._data))))
            values: Sequence[float]
            if isinstance(value, ndarray):
                values = list(value._data)
            elif isinstance(value, Sequence):
                values = [float(v) for v in value]
            else:
                values = [float(value)] * len(index_list)
            for idx, val in zip(index_list, values):
                self._data[idx] = float(val)
            return
        self._data[item] = float(value)

    # Arithmetic ---------------------------------------------------------
    def _binary_op(self, other, operator):
        if isinstance(other, ndarray):
            iterable = other._data
        else:
            iterable = [other] * len(self._data)
        return ndarray(operator(a, b) for a, b in zip(self._data, iterable))

    def __mul__(self, other):
        return self._binary_op(other, lambda a, b: a * float(b))

    __rmul__ = __mul__

    def __truediv__(self, other):
        if isinstance(other, ndarray):
            return ndarray(a / float(b) if b else 0.0 for a, b in zip(self._data, other._data))
        return ndarray(a / float(other) if other else 0.0 for a in self._data)

    def __add__(self, other):
        return self._binary_op(other, lambda a, b: a + float(b))

    __radd__ = __add__

    def __sub__(self, other):
        return self._binary_op(other, lambda a, b: a - float(b))

    def to_list(self) -> list[float]:
        return list(self._data)


def array(values: Iterable[float] | float | int) -> ndarray:
    if isinstance(values, ndarray):
        return ndarray(values._data)
    if isinstance(values, (int, float)):
        return ndarray([values])
    return ndarray(values)


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
