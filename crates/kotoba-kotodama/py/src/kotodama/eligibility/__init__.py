"""kotodama.eligibility — Pregel ``EligibilityCell``.

S2 of ADR-2605172300. The cell computes per-adherent kisha eligibility
from MST event attestations and submits two on-chain effects per
super-step:

  1. ``Phenotype.setMultiplier(tokenId, bps, ...)`` on geth-private —
     the per-adherent multiplier in basis points, signed by the cell
     key (registered via ``Phenotype.registerCell``).
  2. (Optional) ``KishaStream.claim(tokenId, recipient, max)`` — when
     the cell is also authorized to act as a relayer for adherents who
     opted into automatic claim (S2.5; out of scope for the v0 cell).

The cell is intentionally **deterministic**. An LLM call is permitted
only at two narrow seams:

  - new event-type classification (when an unknown ``eventType`` first
    appears, an LLM is used to bucket it into one of the canonical
    categories from ``Constitution``);
  - outlier-review (the cell flags adherents whose computed multiplier
    sits at the constitutional floor or ceiling; a human or LLM
    reviewer signs off before the next super-step's update lands).

Steady-state operation is a pure reducer over MST events — replayable
from the event log without external dependencies, per ADR-2605172000.
"""

from kotodama.eligibility.scoring import (
    AttestationEvent,
    EligibilityState,
    PhenotypeUpdate,
    score_participation,
    multiplier_from_score,
)
from kotodama.eligibility.cell import (
    EligibilityCell,
    EligibilityCellConfig,
    CellPorts,
    build_eligibility_graph,
)

__all__ = [
    "AttestationEvent",
    "EligibilityState",
    "PhenotypeUpdate",
    "score_participation",
    "multiplier_from_score",
    "EligibilityCell",
    "EligibilityCellConfig",
    "CellPorts",
    "build_eligibility_graph",
]
