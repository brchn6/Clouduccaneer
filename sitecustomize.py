"""Project specific site customisation.

Pytest executes directly from the repository root without installing the
package.  Adding the ``src`` directory to :data:`sys.path` keeps imports such as
``cb`` or the lightweight stub modules (``typer``, ``numpy`` and friends)
resolvable during tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))
