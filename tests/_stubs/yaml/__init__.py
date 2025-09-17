"""Minimal YAML compatibility layer used for tests.

This lightweight implementation provides the small subset of the PyYAML
interface that the project requires: :func:`dump`, :func:`safe_load` and the
:class:`YAMLError` exception.  Internally we serialise data as JSON which is
perfectly adequate for the simple configuration structures used in the tests.
"""

from __future__ import annotations

import json
from typing import Any


class YAMLError(ValueError):
    """Raised when parsing fails."""


def dump(data: Any, **_: Any) -> str:
    """Serialise *data* to a human-readable string.

    The optional keyword arguments accepted by :mod:`yaml` are ignored to keep
    the implementation intentionally tiny.
    """

    return json.dumps(data, indent=2, sort_keys=True)


def safe_load(stream: Any) -> Any:
    """Parse a YAML document into Python data structures.

    ``None`` and empty strings return ``None`` which mirrors PyYAML's
    behaviour.  When parsing fails we raise :class:`YAMLError`.
    """

    if stream is None:
        return None
    if hasattr(stream, "read"):
        stream = stream.read()
    text = str(stream).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise YAMLError(str(exc)) from exc
