"""TerminationManager — runs termination conditions against env each step.

Mirrors `isaaclab.managers.TerminationManager`. Holds a dict of named
TerminationTerm instances; compute() returns (terminated, info) where info
maps term name → contribution (True/False).

TerminationTerm is similar to RewTerm but the function returns a bool, and
there is no weight (just an optional "time_out" flag to distinguish
truncation from real termination).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict


@dataclass
class TerminationTerm:
    """One termination condition. `func` returns a bool; `time_out=True`
    marks this term as a "truncation" (vs hard termination)."""
    func: Callable
    time_out: bool = False
    params: dict = field(default_factory=dict)

    def evaluate(self, env) -> bool:
        return bool(self.func(env, **self.params))


@dataclass
class TerminationManager:
    """Holds termination terms; compute() returns (terminated, info_dict)."""
    terms: Dict[str, TerminationTerm] = field(default_factory=dict)

    def compute(self, env) -> tuple:
        """Returns (terminated, info) where:
          - terminated = OR over hard-termination terms (time_out=False)
          - truncated  = OR over time_out=True terms
          - info       = {term_name: bool} per term
        Returns the 3-tuple (terminated, truncated, info)."""
        terminated = False
        truncated = False
        info: Dict[str, bool] = {}
        for name, term in self.terms.items():
            v = term.evaluate(env)
            info[name] = v
            if v:
                if term.time_out:
                    truncated = True
                else:
                    terminated = True
        return (terminated, truncated, info)

    def add_term(self, name: str, term: TerminationTerm) -> "TerminationManager":
        self.terms[name] = term
        return self

    def num_terms(self) -> int:
        return len(self.terms)
