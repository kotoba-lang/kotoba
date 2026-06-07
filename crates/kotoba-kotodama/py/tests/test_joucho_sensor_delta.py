"""apply_sensor_delta unit cases (ADR-2605262400 §4.3 Wave-2 + R1 multi-modal).

Verifies the per-tick joucho 情緒 delta rules:
  - Tier-A observations raise `focus` (kyumei-koji)
  - Tier-C observations raise `focus` half as much
  - Leak attempts raise `stress` sharply (R9 pre-fire)
  - All deltas clamp to [0, 100]
  - **R1 multi-modal**: per-observation JouchoDelta(kankaku, kanjou,
    yokkyu, kakushin, seimei) maps onto focus/joy/stress/calm/gratitude
    respectively, capped at ±30 per single observation.

The multi-modal path uses a duck-typed ``_StubJouchoDelta`` here
because the canonical ``JouchoDelta`` lives in
``kotodama.organism.observation`` which depends on pydantic. The
delta object only needs 5 int attributes — no inheritance.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from kotodama.organism.joucho import (
    JouchoScores,
    apply_sensor_delta,
    determine_mood,
)


@dataclass
class _StubJouchoDelta:
    """Duck-typed JouchoDelta — same 5-int attributes as
    kotodama.organism.joucho_types.JouchoDelta, no pydantic dep."""
    kankaku: int = 0
    kanjou: int = 0
    yokkyu: int = 0
    kakushin: int = 0
    seimei: int = 0


def test_no_observations_no_delta():
    base = JouchoScores(joy=42, calm=55, stress=20, gratitude=50, focus=50)
    out = apply_sensor_delta(base)
    assert out.joy == 42
    assert out.calm == 55
    assert out.stress == 20
    assert out.gratitude == 50
    assert out.focus == 50


def test_tier_a_observations_raise_focus():
    base = JouchoScores(focus=50)
    out = apply_sensor_delta(base, tier_a_obs_count=8)
    # 8 // 4 = 2 focus boost.
    assert out.focus == 52


def test_tier_a_focus_delta_saturates_at_20():
    base = JouchoScores(focus=50)
    out = apply_sensor_delta(base, tier_a_obs_count=200)
    # Saturating at 20 obs ⇒ 20 // 4 = 5 max from tier-A alone.
    assert out.focus == 55


def test_tier_a_observations_mildly_raise_calm():
    base = JouchoScores(calm=50)
    out = apply_sensor_delta(base, tier_a_obs_count=16)
    # 16 // 8 = 2 calm boost.
    assert out.calm == 52


def test_tier_c_observations_focus_half_strength():
    base = JouchoScores(focus=50)
    out = apply_sensor_delta(base, tier_c_obs_count=10)
    # tier-C: min(10, count) // 5 = 2.
    assert out.focus == 52


def test_combined_tier_a_and_tier_c_focus():
    base = JouchoScores(focus=50)
    out = apply_sensor_delta(base, tier_a_obs_count=8, tier_c_obs_count=10)
    # 8//4 = 2 (tier-A) + 10//5 = 2 (tier-C) = +4.
    assert out.focus == 54


def test_single_leak_attempt_raises_stress_sharply():
    base = JouchoScores(stress=20)
    out = apply_sensor_delta(base, leak_attempts=1)
    assert out.stress == 30  # +10 per leak


def test_three_leak_attempts_stack():
    base = JouchoScores(stress=20)
    out = apply_sensor_delta(base, leak_attempts=3)
    assert out.stress == 50  # +30 capped, well under 100


def test_leak_attempt_stress_caps_at_40():
    base = JouchoScores(stress=10)
    out = apply_sensor_delta(base, leak_attempts=100)
    assert out.stress == 50  # 10 + min(40, 100*10) = 10 + 40


def test_stress_delta_can_push_into_stressed_mood():
    """A single leak attempt on a calm-but-borderline organism flips mood."""
    base = JouchoScores(stress=65)
    assert determine_mood(base) != "stressed"  # under 70 threshold
    out = apply_sensor_delta(base, leak_attempts=1)
    assert out.stress == 75
    assert determine_mood(out) == "stressed"


def test_clamps_to_100():
    base = JouchoScores(focus=99)
    out = apply_sensor_delta(base, tier_a_obs_count=200, tier_c_obs_count=200)
    assert out.focus == 100  # 99 + 5 + 2 = 106 → clamped


def test_joy_and_gratitude_unchanged_when_no_multi_modal_deltas():
    """Without multi_modal_deltas, joy + gratitude are untouched
    (Wave-2 invariant preserved even though the function now accepts
    per-axis deltas via the R1 multi-modal extension)."""
    base = JouchoScores(joy=70, gratitude=60)
    out = apply_sensor_delta(base, tier_a_obs_count=20, leak_attempts=2)
    assert out.joy == 70
    assert out.gratitude == 60


# ── R1 multi_modal_deltas extension ───────────────────────────────────


def test_multi_modal_kanjou_raises_joy():
    base = JouchoScores(joy=50)
    md = _StubJouchoDelta(kanjou=15)
    out = apply_sensor_delta(base, multi_modal_deltas=[md])
    assert out.joy == 65


def test_multi_modal_kakushin_raises_calm():
    base = JouchoScores(calm=50)
    md = _StubJouchoDelta(kakushin=12)
    out = apply_sensor_delta(base, multi_modal_deltas=[md])
    assert out.calm == 62


def test_multi_modal_yokkyu_raises_stress():
    base = JouchoScores(stress=30)
    md = _StubJouchoDelta(yokkyu=15)
    out = apply_sensor_delta(base, multi_modal_deltas=[md])
    assert out.stress == 45


def test_multi_modal_seimei_raises_gratitude():
    base = JouchoScores(gratitude=50)
    md = _StubJouchoDelta(seimei=8)
    out = apply_sensor_delta(base, multi_modal_deltas=[md])
    assert out.gratitude == 58


def test_multi_modal_kankaku_raises_focus():
    base = JouchoScores(focus=50)
    md = _StubJouchoDelta(kankaku=20)
    out = apply_sensor_delta(base, multi_modal_deltas=[md])
    assert out.focus == 70


def test_multi_modal_negative_delta_lowers_axis():
    base = JouchoScores(stress=40)
    md = _StubJouchoDelta(yokkyu=-15)  # calming observation
    out = apply_sensor_delta(base, multi_modal_deltas=[md])
    assert out.stress == 25


def test_multi_modal_caps_at_30_per_observation():
    """A single extreme observation can't push any axis by more
    than ±30 — protects against runaway from a single sample."""
    base = JouchoScores()
    md = _StubJouchoDelta(
        kanjou=100, kakushin=100, yokkyu=100, seimei=100, kankaku=100,
    )
    out = apply_sensor_delta(base, multi_modal_deltas=[md])
    assert out.joy == 80         # 50 + min(30, 100)
    assert out.calm == 80
    assert out.stress == 60      # 30 + min(30, 100)
    assert out.gratitude == 80
    assert out.focus == 80


def test_multi_modal_multiple_observations_additive():
    """Per-observation cap means N observations can sum past 30 if
    each individual one is at or near the cap."""
    base = JouchoScores(joy=50)
    md1 = _StubJouchoDelta(kanjou=30)
    md2 = _StubJouchoDelta(kanjou=30)
    out = apply_sensor_delta(base, multi_modal_deltas=[md1, md2])
    assert out.joy == 100  # 50 + 30 + 30 = 110, clamped to 100


def test_multi_modal_combines_with_tier_a():
    """tier_a focus (kyumei-koji) and multi-modal kankaku (sensory
    activation) both raise focus and stack additively before clamp."""
    base = JouchoScores(focus=50)
    md = _StubJouchoDelta(kankaku=10)
    out = apply_sensor_delta(
        base, tier_a_obs_count=16, multi_modal_deltas=[md],
    )
    # tier_a: 16//4=4 focus / multi-modal: +10 / total: +14
    assert out.focus == 64


def test_multi_modal_combines_with_leak_stress():
    """Leak attempts and multi-modal yokkyu both raise stress and
    stack additively before clamp."""
    base = JouchoScores(stress=20)
    md = _StubJouchoDelta(yokkyu=20)
    out = apply_sensor_delta(
        base, leak_attempts=1, multi_modal_deltas=[md],
    )
    # 1 leak: +10 / multi-modal: +20 / total: +30
    assert out.stress == 50
