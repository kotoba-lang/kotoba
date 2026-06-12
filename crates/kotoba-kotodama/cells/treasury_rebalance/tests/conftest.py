"""Add the cell directory to sys.path so `from cell import ...` works
when pytest is invoked from anywhere in the repo."""

from __future__ import annotations

import sys
from pathlib import Path

_CELL_DIR = str(Path(__file__).resolve().parent.parent)
if _CELL_DIR not in sys.path:
    sys.path.insert(0, _CELL_DIR)
