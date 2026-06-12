"""Deterministic per-code joucho personality.

Per ADR-2605240015. Maps a UNSPSC actor DID (or bare code) to a stable
5-axis ``JouchoScores`` baseline. Each of the 18,342 codes gets a
distinct, repeatable personality without any network round-trip.

Personality formula:
  base = hash(code) → 5 evenly-distributed integers in [25, 75]
  bias = segment_bias_table[code[:2]] (small ±15 per axis adjustment)
  result = clamp(base + bias, 0, 100) per axis
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from kotodama.organism.joucho import JouchoScores

# Per-segment ±15 bias. Keys are 2-char segment prefixes. Values are
# 5-tuples (joy, calm, stress, gratitude, focus).
_SEGMENT_BIAS: dict[str, tuple[int, int, int, int, int]] = {
    # Live Plant / Animal — life-affirming
    "10": (+15, +5, -5, +15, 0),
    # Mineral / Metal — solid, focused
    "11": (-5, +10, 0, 0, +10),
    # Chemicals — analytical, careful
    "12": (-5, +5, +5, 0, +15),
    # Rubber / Plastic — adaptive
    "13": (0, +10, 0, 0, +5),
    # Paper Products — calm, contemplative
    "14": (0, +15, -5, +5, +10),
    # Fuels / Lubricants — high-energy, riskier
    "15": (-5, -5, +15, -5, +5),
    # Industrial Manufacturing (20s)
    "20": (0, 0, +5, 0, +15),
    "21": (0, 0, +5, 0, +15),
    "22": (0, 0, +5, 0, +15),
    "23": (0, 0, +5, 0, +15),
    "24": (0, 0, +5, 0, +15),
    "25": (0, 0, +5, 0, +15),
    "26": (0, 0, +5, 0, +15),
    "27": (0, 0, +5, 0, +15),
    # Components / Structural (30s)
    "30": (0, +10, 0, 0, +10),
    "31": (0, +10, 0, 0, +10),
    "32": (0, +10, 0, 0, +10),
    "39": (0, +10, 0, 0, +10),
    # Distribution / Logistics (40s)
    "40": (0, +10, 0, +5, 0),
    "41": (0, +10, 0, +5, 0),
    "42": (0, +10, 0, +5, 0),
    "43": (0, +10, 0, +5, 0),
    "44": (0, +10, 0, +5, 0),
    # Food / Beverage / Health / Lab (50s)
    "45": (+5, +5, 0, +10, +5),
    "46": (+5, +5, 0, +10, +5),
    "47": (+5, +5, 0, +10, +5),
    "48": (+5, +5, 0, +10, +5),
    "49": (+5, +5, 0, +10, +5),
    "50": (+10, +5, 0, +15, 0),
    "51": (+5, +5, +5, +10, +10),  # pharma — focus + slight stress
    "52": (+10, +10, 0, +10, 0),
    "53": (+15, +5, 0, +10, 0),
    "54": (+10, +5, 0, +10, +5),
    "55": (+5, +10, 0, +5, +10),
    # Services / Office (56-60)
    "56": (+5, +10, 0, +5, +10),
    "60": (0, +15, 0, +5, +10),
}


def _hash_to_axes(code: str) -> tuple[int, int, int, int, int]:
    """5 evenly-distributed ints in [25, 75] derived from SHA-256(code)."""
    digest = hashlib.sha256(code.encode("utf-8")).digest()
    # Use 5 distinct byte windows so axes are independent.
    return (
        25 + (digest[0] * 50) // 255,
        25 + (digest[7] * 50) // 255,
        25 + (digest[14] * 50) // 255,
        25 + (digest[21] * 50) // 255,
        25 + (digest[28] * 50) // 255,
    )


def _clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))


def joucho_for_code(code: str) -> JouchoScores:
    """Deterministic personality for a UNSPSC code.

    Args:
        code: 8-digit UNSPSC code as string (e.g. ``"10101500"``).
              Shorter strings still hash; segment bias requires ≥2 chars.

    Returns:
        JouchoScores with each axis in [0, 100].
    """
    joy, calm, stress, gratitude, focus = _hash_to_axes(code)
    seg = code[:2] if len(code) >= 2 else ""
    bias = _SEGMENT_BIAS.get(seg, (0, 0, 0, 0, 0))
    return JouchoScores(
        joy=_clamp(joy + bias[0]),
        calm=_clamp(calm + bias[1]),
        stress=_clamp(stress + bias[2]),
        gratitude=_clamp(gratitude + bias[3]),
        focus=_clamp(focus + bias[4]),
    )


def _code_from_did(actor_did: str) -> str:
    """Extract the 8-digit UNSPSC code from ``did:web:...:actor:c{code}``."""
    if ":c" in actor_did:
        tail = actor_did.rsplit(":c", 1)[-1]
        # Tail may have query/fragment in pathological cases — strip non-digits.
        digits = "".join(ch for ch in tail if ch.isdigit())
        if digits:
            return digits
    return actor_did


def joucho_personality_provider(actor_did: str) -> JouchoScores:
    """Provider compatible with ``JouchoProvider`` (cadence.py)."""
    return joucho_for_code(_code_from_did(actor_did))


# ── Future hook (ADR-2605240015 Layer 2, deferred) ────────────────────


class MstJouchoProvider(Protocol):
    """Forward-compatible interface for the eventual MST-backed reader.

    Wave 3 implementation will read ``com.etzhayyim.apps.etzhayyim.joucho.score``
    records from the per-actor PDS collection, fall back to
    ``joucho_personality_provider`` on miss or error.
    """

    def __call__(self, actor_did: str) -> JouchoScores:  # pragma: no cover
        ...


__all__ = [
    "MstJouchoProvider",
    "joucho_for_code",
    "joucho_personality_provider",
]
