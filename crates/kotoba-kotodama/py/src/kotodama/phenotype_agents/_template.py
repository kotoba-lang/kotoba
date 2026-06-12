"""Reference template for a generated PhenotypeAgent file.

NOT itself an agent. The generator (``scripts/gen_phenotype_agent.py``)
emits files that follow this shape, parameterized per adherent DID.

The template is here in source so:
  - reviewers can see what a generated file looks like without scanning
    the agents directory after the first generation;
  - the generator's snapshot test compares its output to this template
    rendered with a stable example DID.
"""

# ─── Template source (Jinja-friendly placeholders) ───────────────────
# Generator substitutes {{did}}, {{short_hash}}, {{generated_at_iso}},
# {{event_weights_repr}}.

TEMPLATE = '''# AUTO-GENERATED — do not edit by hand.
# Re-run scripts/gen_phenotype_agent.py to regenerate.
# Per ADR-2605172300 §3.2. Apache-2.0.

from typing import Any
from langgraph.graph import StateGraph, END

from kotodama.eligibility.scoring import (
    AttestationEvent,
    EligibilityState,
    PhenotypeUpdate,
    collapse_events,
    multiplier_from_score,
    score_participation,
)

META: dict[str, Any] = {
    "did": "{{did}}",
    "short_hash": "{{short_hash}}",
    "generated_at": "{{generated_at_iso}}",
    "schema_version": 1,
    "event_weights": {{event_weights_repr}},
}


class _State(dict):
    """Minimal state bag for this adherent's super-step."""


def _load(state: _State) -> _State:
    """Load events for this adherent. Bound at runtime by the host SDK
    via ``EligibilityCell.ports.load_events``; this default raises so
    the generated file is unambiguous when imported standalone."""
    raise NotImplementedError(
        "load_events port not bound; use kotodama.eligibility.cell.EligibilityCell"
    )


def _score(state: _State) -> _State:
    es = EligibilityState(
        token_id=state["token_id"],
        window_start=state["window_start"],
        window_end=state["window_end"],
        events=tuple(state["events"]),
    )
    score, breakdown = score_participation(es, weights=META["event_weights"])
    bps = multiplier_from_score(score)
    state["update"] = PhenotypeUpdate(
        token_id=state["token_id"], bps=bps, score=score, breakdown=breakdown
    )
    return state


_g = StateGraph(_State)
_g.add_node("load", _load)
_g.add_node("score", _score)
_g.set_entry_point("load")
_g.add_edge("load", "score")
_g.add_edge("score", END)
graph = _g.compile()
'''
