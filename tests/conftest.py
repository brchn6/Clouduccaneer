"""Pytest configuration that exposes lightweight stub modules.

The production package depends on libraries such as NumPy, librosa, PyYAML and
Typer.  Those are sizeable dependencies which are unnecessary for the tests in
this kata-style environment, so we provide small drop-in stubs.  They live under
``tests/_stubs`` and are injected into :data:`sys.path` before the test modules
import them.
"""

from __future__ import annotations

import sys
from pathlib import Path

STUB_ROOT = Path(__file__).resolve().parent / "_stubs"
if str(STUB_ROOT) not in sys.path:
    sys.path.insert(0, str(STUB_ROOT))
