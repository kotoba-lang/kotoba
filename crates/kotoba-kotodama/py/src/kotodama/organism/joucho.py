"""joucho 情緒 5-axis mood + cooldown table.

Direct port of ``heartbeat-cadence.ts`` §Mood determination + §Mood→Cadence
mapping + §Stress scaling. Numbers match the TS source line-for-line so
both implementations stay observably equivalent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Mood = Literal["joyful", "calm", "stressed", "grateful", "focused", "neutral"]


@dataclass
class JouchoScores:
    """5-axis 情緒 scores (each 0-100).

    Defaults match the TS ``queryJouchoScores`` constant fallback:
    joy=50, calm=50, stress=30, gratitude=50, focus=50.
    """

    joy: int = 50
    calm: int = 50
    stress: int = 30
    gratitude: int = 50
    focus: int = 50


@dataclass
class MoodCadence:
    post_cooldown_ms: int
    analyze_cooldown_ms: int
    drill_cooldown_ms: int
    validate_cooldown_ms: int
    engage_cooldown_ms: int
    reward_cooldown_ms: int
    post_enabled: bool
    analyze_enabled: bool
    drill_enabled: bool
    validate_enabled: bool
    engage_enabled: bool


_HOUR_MS = 3_600_000
_MIN_MS = 60_000


def determine_mood(j: JouchoScores) -> Mood:
    """High stress trumps; otherwise the dominant axis ≥60 wins; else neutral."""
    if j.stress >= 70:
        return "stressed"
    axes: list[tuple[Mood, int]] = [
        ("joyful", j.joy),
        ("calm", j.calm),
        ("grateful", j.gratitude),
        ("focused", j.focus),
    ]
    axes.sort(key=lambda pair: pair[1], reverse=True)
    if axes[0][1] < 60:
        return "neutral"
    return axes[0][0]


def mood_to_cadence(mood: Mood) -> MoodCadence:
    """Cooldown table per mood — identical to TS source."""
    if mood == "joyful":
        return MoodCadence(
            post_cooldown_ms=30 * _MIN_MS,
            analyze_cooldown_ms=3 * _HOUR_MS,
            drill_cooldown_ms=4 * _HOUR_MS,
            validate_cooldown_ms=2 * _HOUR_MS,
            engage_cooldown_ms=15 * _MIN_MS,
            reward_cooldown_ms=10 * _MIN_MS,
            post_enabled=True,
            analyze_enabled=True,
            drill_enabled=False,
            validate_enabled=True,
            engage_enabled=True,
        )
    if mood == "calm":
        return MoodCadence(
            post_cooldown_ms=2 * _HOUR_MS,
            analyze_cooldown_ms=1 * _HOUR_MS,
            drill_cooldown_ms=2 * _HOUR_MS,
            validate_cooldown_ms=45 * _MIN_MS,
            engage_cooldown_ms=1 * _HOUR_MS,
            reward_cooldown_ms=30 * _MIN_MS,
            post_enabled=True,
            analyze_enabled=True,
            drill_enabled=True,
            validate_enabled=True,
            engage_enabled=True,
        )
    if mood == "stressed":
        return MoodCadence(
            post_cooldown_ms=6 * _HOUR_MS,
            analyze_cooldown_ms=4 * _HOUR_MS,
            drill_cooldown_ms=30 * _MIN_MS,
            validate_cooldown_ms=1 * _HOUR_MS,
            engage_cooldown_ms=3 * _HOUR_MS,
            reward_cooldown_ms=1 * _HOUR_MS,
            post_enabled=False,
            analyze_enabled=True,
            drill_enabled=True,
            validate_enabled=True,
            engage_enabled=False,
        )
    if mood == "grateful":
        return MoodCadence(
            post_cooldown_ms=1 * _HOUR_MS,
            analyze_cooldown_ms=2 * _HOUR_MS,
            drill_cooldown_ms=3 * _HOUR_MS,
            validate_cooldown_ms=2 * _HOUR_MS,
            engage_cooldown_ms=10 * _MIN_MS,
            reward_cooldown_ms=5 * _MIN_MS,
            post_enabled=True,
            analyze_enabled=True,
            drill_enabled=False,
            validate_enabled=True,
            engage_enabled=True,
        )
    if mood == "focused":
        return MoodCadence(
            post_cooldown_ms=3 * _HOUR_MS,
            analyze_cooldown_ms=45 * _MIN_MS,
            drill_cooldown_ms=1 * _HOUR_MS,
            validate_cooldown_ms=30 * _MIN_MS,
            engage_cooldown_ms=2 * _HOUR_MS,
            reward_cooldown_ms=1 * _HOUR_MS,
            post_enabled=True,
            analyze_enabled=True,
            drill_enabled=True,
            validate_enabled=True,
            engage_enabled=False,
        )
    return MoodCadence(
        post_cooldown_ms=2 * _HOUR_MS,
        analyze_cooldown_ms=3 * _HOUR_MS,
        drill_cooldown_ms=2 * _HOUR_MS,
        validate_cooldown_ms=90 * _MIN_MS,
        engage_cooldown_ms=1 * _HOUR_MS,
        reward_cooldown_ms=30 * _MIN_MS,
        post_enabled=True,
        analyze_enabled=True,
        drill_enabled=True,
        validate_enabled=True,
        engage_enabled=True,
    )


def apply_sensor_delta(
    scores: JouchoScores,
    *,
    tier_a_obs_count: int = 0,
    tier_c_obs_count: int = 0,
    leak_attempts: int = 0,
    multi_modal_deltas: list["JouchoDelta"] | None = None,
) -> JouchoScores:
    """Map a tick's sensor activity into a small joucho delta.

    Per ADR-2605262400 §4.3 Wave-2. The hot-path sensor poll yields
    SensorObservations into the organism's bounded ring; this function
    translates the per-tick *new* counts into incremental 5-axis
    deltas. Deltas are deliberately small (±1..6) so a single tick
    can't slam the organism into a non-neutral mood unilaterally —
    persistent perception over many ticks shifts the trajectory.

    Rules (Wave-2 minimum viable):
      - **tier-A observations** raise ``focus`` (kyumei-koji mode —
        the organism is engaged with public-domain world data) and
        very mildly raise ``calm`` (steady stream of facts grounds).
        Saturates after ~20 obs/tick to avoid runaway.
      - **tier-C observations** raise ``focus`` half as much (Tier C
        is more sensitive, the organism is "more careful").
      - **leak attempts** (R9 backstop pre-fires) raise ``stress``
        sharply (+10 each, capped). Even 1 leak is alarming.
      - **multi_modal_deltas** (R1 multi-modal): single observation
        deltas are capped at ±30 to prevent extreme emotion shifts.

    All deltas are clamped to [0, 100] per axis.
    """
    sat = min(20, tier_a_obs_count)  # saturating at 20 tier-A obs
    focus_delta = sat // 4  # 0..5
    focus_delta += min(10, tier_c_obs_count) // 5  # 0..2 from tier-C
    calm_delta = sat // 8  # 0..2
    joy_delta = 0
    gratitude_delta = 0

    stress_delta = min(40, leak_attempts * 10)  # +10/leak, cap 40

    if multi_modal_deltas:
        cap = 30
        for md in multi_modal_deltas:
            # kanjou -> joy
            joy_delta += max(-cap, min(cap, md.kanjou))
            # kakushin -> calm
            calm_delta += max(-cap, min(cap, md.kakushin))
            # yokkyu -> stress
            stress_delta += max(-cap, min(cap, md.yokkyu))
            # seimei -> gratitude
            gratitude_delta += max(-cap, min(cap, md.seimei))
            # kankaku -> focus
            focus_delta += max(-cap, min(cap, md.kankaku))

    def _clamp(v: int) -> int:
        return max(0, min(100, v))

    return JouchoScores(
        joy=_clamp(scores.joy + joy_delta),
        calm=_clamp(scores.calm + calm_delta),
        stress=_clamp(scores.stress + stress_delta),
        gratitude=_clamp(scores.gratitude + gratitude_delta),
        focus=_clamp(scores.focus + focus_delta),
    )


def apply_stress_scaling(cadence: MoodCadence, stress: int) -> MoodCadence:
    """Stress ≥50 stretches post + engage cooldowns linearly."""
    if stress < 50:
        return cadence
    scale = 1.0 + (stress - 50) / 50.0
    return MoodCadence(
        post_cooldown_ms=round(cadence.post_cooldown_ms * scale),
        analyze_cooldown_ms=cadence.analyze_cooldown_ms,
        drill_cooldown_ms=cadence.drill_cooldown_ms,
        validate_cooldown_ms=cadence.validate_cooldown_ms,
        engage_cooldown_ms=round(cadence.engage_cooldown_ms * scale),
        reward_cooldown_ms=cadence.reward_cooldown_ms,
        post_enabled=cadence.post_enabled,
        analyze_enabled=cadence.analyze_enabled,
        drill_enabled=cadence.drill_enabled,
        validate_enabled=cadence.validate_enabled,
        engage_enabled=cadence.engage_enabled,
    )


__all__ = [
    "JouchoScores",
    "Mood",
    "MoodCadence",
    "apply_sensor_delta",
    "apply_stress_scaling",
    "determine_mood",
    "mood_to_cadence",
]
