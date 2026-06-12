"""junkan.datom — Datomic-isomorphic, append-only in-memory datom store.

ADR-2605290927 (junkan R0/R1). This is the *reference* realization of the
data model. The **canonical production binding is kotoba-kqe** (ADR-2605262130),
which provides content-addressed Datalog with EAVT/AEVT/AVET/VAET arrangements
over immutable blocks — the exact Datomic index set. **Proprietary Datomic is
NOT used** (substrate boundary + Charter Rider §2(e)+§2(c)).

Why a datom model: feedback-loop regime detection (好循環/悪循環) is only
readable from *how a stock moved over time*. Immutable facts ``[E A V T]`` with
tx-time give free ``as_of`` / ``history`` queries — the property that makes this
the right model for cycle analysis.

G9 (datom immutability): facts are append-only. There is intentionally **no
retraction API** — nothing is ever overwritten or removed (matches both Datomic
semantics and §1.15 trajectory-not-destination).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class Datom:
    """One immutable fact: entity ``e`` has attribute ``a`` with value ``v`` as
    of transaction ``t``. ``added`` is always True for junkan (G9: append-only).
    """

    e: str
    a: str
    v: Any
    t: int
    added: bool = True


class DatomStore:
    """Append-only EAVT store with as-of / history queries.

    Mirrors kotoba-kqe arrangement semantics:
      - ``entity``     ~ EAVT  ("all attributes of entity E")
      - ``find``       ~ AVET  ("all entities where A == V")
      - ``referencing``~ VAET  (reverse-ref: "entities whose A points at E")
      - ``history``    ~ tx-time scan (the time-travel core)
    """

    def __init__(self) -> None:
        self._datoms: list[Datom] = []
        self._t: int = 0

    # ── write (append-only; G9) ──────────────────────────────────────────
    def transact(self, facts: Iterable[tuple[str, str, Any]]) -> int:
        """Append ``(e, a, v)`` facts as one transaction. Returns the tx ``t``.

        There is no retraction parameter by design (G9).
        """
        self._t += 1
        for e, a, v in facts:
            self._datoms.append(Datom(e=e, a=a, v=v, t=self._t))
        return self._t

    @property
    def basis_t(self) -> int:
        """Latest transaction number (the current 'as-of now' basis)."""
        return self._t

    # ── read ─────────────────────────────────────────────────────────────
    def entity(self, e: str, as_of: int | None = None) -> dict[str, Any]:
        """Latest value of each attribute of ``e`` as of ``as_of`` (or now)."""
        t_max = self._t if as_of is None else as_of
        out: dict[str, Any] = {}
        last_t: dict[str, int] = {}
        for d in self._datoms:
            if d.e != e or d.t > t_max:
                continue
            if d.a not in last_t or d.t >= last_t[d.a]:
                out[d.a] = d.v
                last_t[d.a] = d.t
        return out

    def history(self, e: str, a: str) -> list[tuple[int, Any]]:
        """Full ``(t, v)`` history of attribute ``a`` on entity ``e``, ordered.

        This is the time-travel primitive regime detection relies on.
        """
        return [(d.t, d.v) for d in self._datoms if d.e == e and d.a == a]

    def find(self, a: str, v: Any, as_of: int | None = None) -> list[str]:
        """Entities whose latest value of ``a`` equals ``v`` (AVET-style)."""
        t_max = self._t if as_of is None else as_of
        latest: dict[str, tuple[int, Any]] = {}
        for d in self._datoms:
            if d.a != a or d.t > t_max:
                continue
            if d.e not in latest or d.t >= latest[d.e][0]:
                latest[d.e] = (d.t, d.v)
        return [e for e, (_, val) in latest.items() if val == v]

    def referencing(self, ref_attr: str, target_e: str, as_of: int | None = None) -> list[str]:
        """Entities whose ``ref_attr`` currently points at ``target_e`` (VAET)."""
        return self.find(ref_attr, target_e, as_of=as_of)

    def __len__(self) -> int:
        return len(self._datoms)
