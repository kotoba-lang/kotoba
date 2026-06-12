"""Locate a generic e7m robot fixture by walking up to the repo root.

The generic robot fixtures (cartpole / double_pendulum / arm3 / giemon_arm6)
are the source of truth INSIDE the kami-engine workspace as of
ADR-2606011500 stage 2:

    40-engine/kami-engine/fixtures/<robot>/<file>

The pre-move location (``70-tools/e7m-sim/scenes/<robot>/<file>``) is kept as
a fallback so older checkouts / detached usages keep resolving.
"""

from __future__ import annotations

from pathlib import Path

# Tried in order; first hit wins. Canonical kami-engine location first.
_FIXTURE_ROOTS = (
    ("40-engine", "kami-engine", "fixtures"),  # canonical (ADR-2606011500 §2)
    ("70-tools", "e7m-sim", "scenes"),  # legacy fallback (pre-move)
)


def load_fixture(robot: str, filename: str) -> str:
    """Return the text of ``<robot>/<filename>`` from the nearest fixture root.

    Walks up from this file to find the repo root, then probes the canonical
    kami-engine ``fixtures/`` dir before the legacy ``e7m-sim/scenes/`` dir.
    """
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        for root in _FIXTURE_ROOTS:
            candidate = ancestor.joinpath(*root, robot, filename)
            if candidate.exists():
                return candidate.read_text()
    raise FileNotFoundError(
        f"Could not locate {robot}/{filename} under "
        "kami-engine/fixtures or 70-tools/e7m-sim/scenes — repo layout changed?"
    )
