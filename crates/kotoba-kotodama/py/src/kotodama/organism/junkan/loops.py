"""junkan.loops — causal-loop assembly + virtuous/vicious regime read-off.

ADR-2605290927. The heart of "好循環/悪循環 が回っている箇所" analysis.

Loop polarity (classic System Dynamics rule): a loop is *reinforcing* (R) when
it contains an even number of negative links, *balancing* (B) when odd.

Regime read-off (好循環 / 悪循環 / neutral / transitioning) combines the loop
type with the recent trajectory of the loop's dominant stock and that stock's
Council-attested ``desirability`` (higher-is-better vs lower-is-better):

  - reinforcing + dominant stock moving in the *desirable* direction  → virtuous (好循環)
  - reinforcing + dominant stock moving in the *undesirable* direction → vicious (悪循環)
  - recent slope sign just flipped                                     → transitioning (遷移中)
  - |slope| below threshold (or balancing/stabilizing)                 → neutral (中立)

All outputs are hypotheses (G5); confidence is the min edge confidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from .flows import FlowEdge

REGIMES = ("virtuous", "vicious", "neutral", "transitioning")


@dataclass(frozen=True)
class CausalLoop:
    loop_id: str
    edges: tuple[FlowEdge, ...]
    loop_type: str  # "reinforcing" | "balancing"
    dominant_stock: str
    regime: str  # one of REGIMES
    confidence: float


@dataclass(frozen=True)
class RegimeShift:
    loop_id: str
    from_regime: str
    to_regime: str


def loop_polarity(edges: list[FlowEdge] | tuple[FlowEdge, ...]) -> str:
    """Reinforcing if an even number of edges are negative, else balancing."""
    if len(edges) < 2:
        raise ValueError("a loop needs >= 2 edges")
    negatives = sum(1 for e in edges if e.polarity == "neg")
    return "reinforcing" if negatives % 2 == 0 else "balancing"


def _slope(levels: list[int]) -> float:
    """Least-squares slope over the level series (sign + magnitude)."""
    n = len(levels)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(levels) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0.0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, levels)) / denom


def classify_regime(
    trajectory: list[tuple[int, int]],
    loop_type: str,
    desirability: int,
    *,
    slope_eps: float = 1e-9,
) -> str:
    """Read the current regime of a loop from its dominant-stock trajectory."""
    levels = [lvl for _, lvl in trajectory]
    if len(levels) < 2:
        return "neutral"

    # transitioning: recent half slope sign differs from earlier half
    if len(levels) >= 4:
        mid = len(levels) // 2
        s_early = _slope(levels[:mid])
        s_late = _slope(levels[mid:])
        if s_early * s_late < 0 and abs(s_late) > slope_eps:
            return "transitioning"

    slope = _slope(levels)
    if abs(slope) <= slope_eps:
        return "neutral"

    # Balancing loops stabilize toward equilibrium → treat as neutral here.
    if loop_type == "balancing":
        return "neutral"

    # Reinforcing loop: desirable direction = sign(slope) matches desirability.
    moving_desirably = (slope > 0) == (desirability > 0)
    return "virtuous" if moving_desirably else "vicious"


def build_loop(
    loop_id: str,
    edges: list[FlowEdge],
    dominant_stock: str,
    dominant_trajectory: list[tuple[int, int]],
    desirability: int,
) -> CausalLoop:
    ltype = loop_polarity(edges)
    regime = classify_regime(dominant_trajectory, ltype, desirability)
    conf = min((e.confidence for e in edges), default=0.0)
    return CausalLoop(
        loop_id=loop_id,
        edges=tuple(edges),
        loop_type=ltype,
        dominant_stock=dominant_stock,
        regime=regime,
        confidence=conf,
    )


def detect_regime_shift(loop_id: str, prev_regime: str, new_regime: str) -> RegimeShift | None:
    """Return a RegimeShift iff the regime changed (e.g. 好循環 → 悪循環)."""
    if prev_regime == new_regime:
        return None
    return RegimeShift(loop_id=loop_id, from_regime=prev_regime, to_regime=new_regime)
