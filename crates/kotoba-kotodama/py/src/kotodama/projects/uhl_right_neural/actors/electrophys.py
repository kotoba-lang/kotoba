"""V04 ElectrophysActor — ABR / eABR / OAE numerical fusion.

Reads audiometry measurements for the affected ear and emits the boolean
SubstrateEvidence fields consumed by V06 (`eabr_present`,
`eabr_latency_prolonged`, `dpoae_present`).

Thresholds are conservative defaults from common clinical practice; precise
values are clinician-tunable per the V12 plasticity gate. They are intentionally
documented inline rather than abstracted into a config layer so that any change
is reviewed in the same PR as the rule.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Thresholds (clinician-reviewable in PR) ──────────────────────────────────

# eABR wave V latency upper bound for "not prolonged" classification (ms).
# Normative pediatric range is roughly 3.5-4.5 ms; >4.5 ms is treated as
# prolonged for V06 SGN-degenerating routing.
_EABR_WAVE_V_LATENCY_MS_THRESHOLD = 4.5

# DPOAE amplitude signal-to-noise ratio (dB) above which OAE is "present".
_DPOAE_SNR_DB_THRESHOLD = 6.0

# ABR threshold (dB nHL) above which "no response" is recorded — relevant for
# severe-to-profound hearing loss classification (informational only here;
# V06 uses eABR not aABR).
_ABR_NO_RESPONSE_DB_NHL = 95.0


Ear = Literal["right", "left"]


# ── Input ────────────────────────────────────────────────────────────────────


class ElectrophysInput(BaseModel):
    """Audiometry measurements for one ear."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ear: Ear

    # Auditory brainstem response (acoustic, click or tone-burst)
    abr_threshold_db_nhl: Optional[float] = Field(default=None, ge=0.0, le=120.0)
    abr_wave_v_present: Optional[bool] = Field(default=None)

    # Electrically-evoked ABR (requires a stimulating electrode; recorded
    # intra-operatively or post-CI). Absent eABR with present nerve fibers is
    # the key signal for V06 rule 2 (SGN absent + nerve present).
    eabr_wave_v_present: Optional[bool] = Field(default=None)
    eabr_wave_v_latency_ms: Optional[float] = Field(default=None, ge=0.0, le=20.0)

    # Distortion-product otoacoustic emissions (DPOAE) — outer hair cell proxy.
    dpoae_snr_db: Optional[float] = Field(
        default=None,
        ge=-10.0,
        le=40.0,
        description="DPOAE amplitude minus noise floor (dB).",
    )


# ── Output ───────────────────────────────────────────────────────────────────


class ElectrophysResult(BaseModel):
    """V04 output. Mirrors the SubstrateEvidence shape consumed by V06."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ear: Ear
    eabr_present: Optional[bool]
    eabr_latency_prolonged: Optional[bool]
    dpoae_present: Optional[bool]
    notes: list[str] = Field(default_factory=list)


# ── Actor ────────────────────────────────────────────────────────────────────


class ElectrophysActor:
    """V04 — deterministic numerical fusion."""

    name = "V04_electrophys"

    @staticmethod
    def compute(state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("electrophys_input")
        if raw is None:
            return {
                "electrophys_result": ElectrophysResult(
                    ear="right",
                    eabr_present=None,
                    eabr_latency_prolonged=None,
                    dpoae_present=None,
                ).model_dump()
            }
        parsed = ElectrophysInput.model_validate(raw)
        result = ElectrophysActor._fuse(parsed)

        # Push V06-compatible evidence delta into shared substrate_evidence.
        delta_evidence: dict[str, Any] = dict(state.get("substrate_evidence") or {})
        if result.eabr_present is not None:
            delta_evidence["eabr_present"] = result.eabr_present
        if result.eabr_latency_prolonged is not None:
            delta_evidence["eabr_latency_prolonged"] = result.eabr_latency_prolonged
        if result.dpoae_present is not None:
            delta_evidence["dpoae_present"] = result.dpoae_present

        return {
            "electrophys_result": result.model_dump(),
            "substrate_evidence": delta_evidence,
            "requires_human_review": True,
        }

    @staticmethod
    def _fuse(parsed: ElectrophysInput) -> ElectrophysResult:
        notes: list[str] = []

        eabr_present: Optional[bool] = parsed.eabr_wave_v_present
        eabr_latency_prolonged: Optional[bool] = None
        if (
            parsed.eabr_wave_v_present is True
            and parsed.eabr_wave_v_latency_ms is not None
        ):
            eabr_latency_prolonged = (
                parsed.eabr_wave_v_latency_ms > _EABR_WAVE_V_LATENCY_MS_THRESHOLD
            )

        dpoae_present: Optional[bool] = None
        if parsed.dpoae_snr_db is not None:
            dpoae_present = parsed.dpoae_snr_db >= _DPOAE_SNR_DB_THRESHOLD

        # Informational ABR notes (not used by V06 directly).
        if (
            parsed.abr_threshold_db_nhl is not None
            and parsed.abr_threshold_db_nhl >= _ABR_NO_RESPONSE_DB_NHL
        ):
            notes.append(
                f"ABR no response at ≥{int(_ABR_NO_RESPONSE_DB_NHL)} dB nHL "
                f"(profound loss; consistent with severe SNHL)."
            )
        if (
            parsed.eabr_wave_v_present is True
            and eabr_latency_prolonged is True
        ):
            notes.append(
                f"eABR wave V latency "
                f"{parsed.eabr_wave_v_latency_ms} ms > "
                f"{_EABR_WAVE_V_LATENCY_MS_THRESHOLD} ms threshold "
                f"(SGN degeneration pattern)."
            )

        return ElectrophysResult(
            ear=parsed.ear,
            eabr_present=eabr_present,
            eabr_latency_prolonged=eabr_latency_prolonged,
            dpoae_present=dpoae_present,
            notes=notes,
        )
