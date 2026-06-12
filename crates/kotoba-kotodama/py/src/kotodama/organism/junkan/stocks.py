"""junkan.stocks — society-level stock observations (aggregate-only, immutable).

ADR-2605290927. G6 (aggregate-only): a stock is a society-level accumulation,
never an individual — there is no per-person field and ``record_stock`` rejects
any attempt to attach one. G9 (immutable): every observation is appended as
datoms; nothing is overwritten.

``desirability`` encodes whether a higher level is better (+1) or worse (-1) for
Wellbecoming — used by ``loops.classify_regime`` to read 好循環 vs 悪循環. It is a
property of the *stock*, attested by Council, not inferred by junkan.
"""

from __future__ import annotations

from dataclasses import dataclass

from .datom import DatomStore


@dataclass(frozen=True)
class StockObservation:
    """One observation of a society-level stock at a valid-time.

    ``level`` is an integer in the units of ``unit`` (lexicon convention:
    levels are integers — e.g. basis points / per-100k — so fractional
    precision is unnecessary).
    """

    stock_id: str
    level: int
    unit: str
    valid_time: str  # ISO-8601 (when the world was observed)
    source_cid: str  # G3: pre-published public archive provenance
    desirability: int = 1  # +1 higher-is-better, -1 lower-is-better

    def __post_init__(self) -> None:
        if self.desirability not in (1, -1):
            raise ValueError("desirability must be +1 (higher-is-better) or -1 (lower-is-better)")


def record_stock(store: DatomStore, obs: StockObservation, **forbidden: object) -> int:
    """Append a stock observation as :junkan.stock/* datoms. Returns tx ``t``.

    G6 STRUCTURAL: rejects any individual-level attribute. There is no code path
    that records a person — passing one is a programming error, not a runtime
    branch that could be toggled on.
    """
    if forbidden:
        raise ValueError(
            f"G6 aggregate-only: society-level stocks only; refused individual/extra fields {sorted(forbidden)}"
        )
    return store.transact(
        [
            (obs.stock_id, ":junkan.stock/id", obs.stock_id),
            (obs.stock_id, ":junkan.stock/level", obs.level),
            (obs.stock_id, ":junkan.stock/unit", obs.unit),
            (obs.stock_id, ":junkan.stock/valid-time", obs.valid_time),
            (obs.stock_id, ":junkan.stock/source-cid", obs.source_cid),
            (obs.stock_id, ":junkan.stock/desirability", obs.desirability),
        ]
    )


def trajectory(store: DatomStore, stock_id: str) -> list[tuple[int, int]]:
    """``(t, level)`` history of a stock — the input to flow/regime analysis."""
    return [(t, int(v)) for t, v in store.history(stock_id, ":junkan.stock/level")]
