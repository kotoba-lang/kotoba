"""junkan.flows — flow inference between society stocks (hypothesis-only).

ADR-2605290927. G5 (no causal overclaim): a flow edge is a *hypothesis* derived
from lagged correlation sign + confidence — never a claim of proven causation.
``FlowEdge.polarity`` is "pos"/"neg" and every edge carries a confidence.

Pure stdlib math (no SciPy): a sign-aware lagged Pearson correlation. With zero
variance or too-few points, confidence is 0.0 (we abstain rather than overclaim).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlowEdge:
    from_stock: str
    to_stock: str
    polarity: str  # "pos" | "neg"  (hypothesis)
    lag_ticks: int
    confidence: float  # 0.0 .. 1.0 (internal float; converted to int-percent at lexicon boundary)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0.0 or vy == 0.0:
        return 0.0
    return cov / (vx**0.5 * vy**0.5)


def infer_flow(
    from_id: str,
    to_id: str,
    series_from: list[int],
    series_to: list[int],
    lag: int = 1,
) -> FlowEdge | None:
    """Hypothesize a directional flow ``from_id -> to_id`` at ``lag`` ticks.

    Correlates ``series_from`` (shifted back by ``lag``) against ``series_to``.
    Returns None when there is not enough overlap to say anything (G5: abstain).
    """
    if lag < 0:
        raise ValueError("lag must be >= 0")
    a = series_from[: len(series_from) - lag] if lag else series_from
    b = series_to[lag:] if lag else series_to
    m = min(len(a), len(b))
    if m < 2:
        return None
    r = _pearson([float(x) for x in a[-m:]], [float(y) for y in b[-m:]])
    if r == 0.0:
        return None
    return FlowEdge(
        from_stock=from_id,
        to_stock=to_id,
        polarity="pos" if r > 0 else "neg",
        lag_ticks=lag,
        confidence=min(1.0, abs(r)),
    )
