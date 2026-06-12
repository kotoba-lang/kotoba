"""Per-adherent ``PhenotypeAgent`` code-generated LangGraph fleet.

S2 of ADR-2605172300. Each adherent gets a personal LangGraph agent
file emitted into this package by
:mod:`kotodama.phenotype_agents._gen` (driven from
``scripts/gen_phenotype_agent.py``). The agent is a small graph that
ingests that adherent's signed event stream and emits a 0.5×–2.0×
multiplier each super-step — a digital twin of the adherent's
participation phenotype.

Pattern is inherited from ``unispsc_agents`` (ADR-2605171300): physical
``.py`` files rather than runtime-evaluated strings, so the fleet is
diffable, code-reviewable, and statically type-checked.

Conventions:
  - file name:  ``a<DID_SHORT_HASH>.py`` (12 hex chars, blake2b-128
    of the DID, lowercased — collision-resistant, fixed-length)
  - exported symbol:  ``graph`` (compiled LangGraph), plus a
    metadata dict ``META``
"""

from kotodama.phenotype_agents._registry import (
    did_short_hash,
    load_agent,
    list_agents,
    AGENT_PACKAGE,
)

__all__ = [
    "did_short_hash",
    "load_agent",
    "list_agents",
    "AGENT_PACKAGE",
]
