"""EventManager — fires EventTerms at the right time (reset/interval/startup).

Mirrors `isaaclab.managers.EventManager`. Holds a list of EventTerms grouped
by mode. ManagerBasedRLEnv calls apply(mode="startup") once at construction,
apply(mode="reset") on each episode reset, and apply(mode="interval") on
each step (which fires the subset whose interval matches the current step).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EventManager:
    """Groups EventTerms by mode and fires them at the right cadence."""
    terms: Dict[str, Any] = field(default_factory=dict)
    _step_count: int = 0

    def apply(self, env, mode: str) -> int:
        """Fire all EventTerms whose mode matches. Returns count of terms fired.
        For 'interval' mode, only fires terms whose interval_steps divides
        the current step counter."""
        fired = 0
        for _name, term in self.terms.items():
            if term.mode == mode:
                if mode == "interval":
                    if term.interval_steps > 0 and self._step_count % term.interval_steps == 0:
                        term.evaluate(env)
                        fired += 1
                else:
                    term.evaluate(env)
                    fired += 1
        return fired

    def step(self) -> None:
        """Increment internal step counter (called by env on each step)."""
        self._step_count += 1

    def reset(self) -> None:
        """Reset step counter (called by env on episode reset)."""
        self._step_count = 0

    def add_term(self, name: str, term) -> "EventManager":
        self.terms[name] = term
        return self

    def num_terms(self) -> int:
        return len(self.terms)

    def num_by_mode(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for term in self.terms.values():
            out[term.mode] = out.get(term.mode, 0) + 1
        return out
