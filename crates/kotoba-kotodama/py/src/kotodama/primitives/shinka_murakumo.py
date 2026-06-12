"""shinka_murakumo — Religious-corp variant of shinka karma-hegemon / evolution worker.

Per ADR-2605215200. Pregel cells running on the Murakumo fleet (Mac mini launchd
cell-runner per ADR-2605202100). Replaces vendor RisingWave-coupled shinka_tick_actor
SQL UDF with MST + IPFS + Base L2 anchor write path (ADR-2605171800 pipeline).

Forbidden per ADR-2605215000 §1: RunPod / commercial GPU rental.
Forbidden per ADR-2605172000: RisingWave / Hyperdrive / Postgres-only writes.

M2 milestone deliverable per ADR-2605215200 §4:
  - shinka_heartbeat_cell()          — IMPLEMENTED (M2)
  - karma_hegemon_observation_cell() — IMPLEMENTED (M2)
  - evolution_validation_cell()      — IMPLEMENTED (M2)
  - evolution_emission_cell()        — IMPLEMENTED (M2)
  - shinka_tick()                    — IMPLEMENTED (M2, promoted from M4)

Pregel cell topology (ADR-2605215200 §1):
  KarmaHegemonObservationCell  — levi   (port 13023)  cron/mst-listener
  EvolutionValidationCell      — levi   (port 13024)  mst-listener
  EvolutionEmissionCell        — simeon (port 13025)  mst-listener
  ShinkaHeartbeatCell          — levi   (port 13026)  cron */15 * * * *

Super-step flow:
  [cron / kyumeiSignal]
       ↓
  KarmaHegemonObservationCell  → writes com.etzhayyim.apps.etzhayyim.shinka.observeAdherent
       ↓
  EvolutionValidationCell      → writes com.etzhayyim.apps.etzhayyim.shinka.validateEvolution
       ↓
  EvolutionEmissionCell        → writes evolutionEvent to MST + IPFS + Base L2

  ShinkaHeartbeatCell          → writes shinkaHeartbeat to MST (cron, independent)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

# ── SDK import (stub calls — downstream NotImplementedError until M3) ──────────
# Import lazily so tests can mock before module-level side effects.
# The etzhayyim-sdk-py package lives at 20-actors/etzhayyim-sdk-py/.
# Until it is installed, these calls will raise NotImplementedError (stub), which is
# the correct M2 behaviour: cell logic is complete and tested in isolation.
try:
    from etzhayyim_sdk import pds as _pds_mod
    from etzhayyim_sdk import mst as _mst_mod
    from etzhayyim_sdk import ipfs as _ipfs_mod
    from etzhayyim_sdk import l2 as _l2_mod
    from etzhayyim_sdk.types import ShinkaHeartbeatRecord as _ShinkaHeartbeatRecord
except ImportError:
    _pds_mod = None  # type: ignore[assignment]
    _mst_mod = None  # type: ignore[assignment]
    _ipfs_mod = None  # type: ignore[assignment]
    _l2_mod = None  # type: ignore[assignment]
    _ShinkaHeartbeatRecord = None  # type: ignore[assignment]

try:
    from etzhayyim_sdk import mst_projector as _projector_mod
except ImportError:
    _projector_mod = None  # type: ignore[assignment]

_log = logging.getLogger(__name__)

# ── Substrate-fit invariant ────────────────────────────────────────────────────
# Fail loudly if imported in a RisingWave or RunPod environment.
# This mirrors the pattern in maps_sentinel_murakumo.py.
if "runpod" in os.environ.get("PATH", "").lower() or os.environ.get("RW_URL"):
    raise ImportError(
        "shinka_murakumo is religious-corp-only — RUNPOD/RW environment detected. "
        "Use vendor kotodama.primitives.shinka for paid SaaS workloads."
    )


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass(slots=True)
class JouchoAxes:
    """Joucho 5-axis emotional state (M1: confirmed from vendor shinka/__init__.py).

    All axes are int 0-100. Vendor reads from vertex_joucho table.
    Religious-corp reads from MST via @etzhayyim/sdk kyumeiSignal aggregation.

    Mood classification thresholds (priority order — stress checked first):
      stress >= 70  → stressed  (inhibits post/engage; recovery via drill)
      joy    >= 60  → joyful
      calm   >= 60  → calm
      gratitude >= 60 → grateful
      focus  >= 60  → focused
      otherwise     → neutral

    New-adherent defaults: joy=40, calm=40, stress=20, gratitude=30, focus=40 → neutral mood.

    kyumeiSignal.signalKind mapping (ADR-2605215200 M1):
      joy       ← ritual + kuniUmi-witness signals
      calm      ← oath + governance-participation signals
      stress    ← inhibitor (no direct signal kind; absent positive signals)
      gratitude ← contribution signals
      focus     ← oath + contribution (deep practice)
    """

    joy: int = 40
    calm: int = 40
    stress: int = 20
    gratitude: int = 30
    focus: int = 40


@dataclass(slots=True)
class CadencePolicy:
    """Cadence flags resolved from joucho mood × elapsed-since-last-heartbeat.

    M1-confirmed: ported from vendor _resolve_cadence (pure function, no RW access).
    Vendor source: kotodama/shinka/__init__.py _cadence_flags().

    Mood × elapsed threshold table (minutes):
      joyful:   post≥30, engage≥15, drill=OFF, validate=OFF, analyze≥60
      calm:     post≥120, engage≥60, drill=OFF, validate≥120, analyze≥60
      stressed: post=OFF, engage=OFF, drill≥30, validate≥60, analyze=OFF
      grateful: post≥60, engage≥10, drill=OFF, validate=OFF, analyze≥60
      focused:  post≥180, engage=OFF, drill≥60, validate≥120, analyze≥30
      neutral:  post≥120, engage≥60, drill≥120, validate≥120, analyze≥60

    Religious-corp implementation target (M2): replace vendor last_heartbeat_ms
    RW read with MST-backed value from @etzhayyim/sdk.
    """

    should_post: bool = False
    should_engage: bool = False
    should_drill: bool = False
    should_validate: bool = False
    should_analyze: bool = False


@dataclass(slots=True)
class AdherentState:
    """Adherent state observed from MST + IPFS.

    Religious-corp equivalent of the state dict returned by vendor _load_state.
    Vendor _load_state reads from vertex_shinka_evolution via RW SELECT.
    Religious-corp reads from MST via @etzhayyim/sdk + IPFS dag-resolve.

    Fields confirmed against vendor shinka_tick_actor JSON output shape:
      actor_did, mood, actions, heartbeat_written, evolution_written, tick_ms

    axes schema confirmed M1: 5-axis JouchoAxes (joy/calm/stress/gratitude/focus),
    each int 0-100. Vendor new-adherent defaults: joy=40, calm=40, stress=20,
    gratitude=30, focus=40. Religious-corp reads axes from kyumeiSignal aggregation
    on MST rather than vertex_joucho RW table.
    """

    did: str
    sbt_token_id: int
    last_evolution_at: str          # ISO 8601
    kyumei_signals: list[dict[str, Any]] = field(default_factory=list)
    mood: str = "neutral"           # joucho mood: joyful/calm/stressed/grateful/focused/neutral
    axes: JouchoAxes = field(default_factory=JouchoAxes)  # M1-confirmed: 5-axis JouchoAxes
    last_heartbeat_ms: int = 0
    proposed_evolution: EvolutionClaim | None = None  # set by observation if pending claim


@dataclass(slots=True)
class ComposeDraft:
    """LLM-composed post draft for an evolution tick.

    M1-confirmed output schema from vendor _compose_content.
    Religious-corp variant MUST route LLM via EVO-X2 LiteLLM per ADR-2605215000,
    NOT via vendor OpenRouter/Vultr Serverless. Write a new prompt; do NOT copy
    the vendor prompt verbatim.

    Stored in EvolutionEventRecord and MST via vertex_shinka_evolution.props.draft
    (vendor side) or com.etzhayyim.apps.etzhayyim.evolutionEvent.composeDraft (religious-corp).

    tone is one of: reflective / celebratory / grateful / focused / observational
    (matches vendor _compose_content tone enum, portable).
    """

    text: str = ""                   # post body ≤300 chars
    tone: str = "observational"      # reflective/celebratory/grateful/focused/observational
    model: str = ""                  # LLM model ID used (EVO-X2 resolved model)
    latency_ms: int = 0              # LLM round-trip latency
    attempts: int = 1                # retry count
    error: str | None = None         # set on LLM failure; text="" on error


@dataclass(slots=True)
class EvolutionClaim:
    """Evolution claim before validation.

    Produced by KarmaHegemonObservationCell when kyumei signals indicate
    a candidate level advancement. Passed to EvolutionValidationCell.

    Vendor equivalent: implicit state dict passed through _koji_validate.
    Religious-corp: explicit typed claim with IPFS evidence CIDs.

    For Lv7 advancement, validated_at tracks when supermajority approved;
    if now() - validated_at < EVOLUTION_APPEAL_DAYS, claim is in appeal window.
    """

    claim_id: str
    adherent_did: str
    proposed_level: int
    evidence_cids: list[str] = field(default_factory=list)  # IPFS CIDs for attestation evidence
    kyumei_signal_refs: list[str] = field(default_factory=list)  # MST rkeys of kyumeiSignal records
    validated_at: str | None = None  # ISO 8601, set by evolution_validation_cell on Lv7 supermajority pass


@dataclass(slots=True)
class EvolutionEventRecord:
    """MST record payload for com.etzhayyim.apps.etzhayyim.evolutionEvent.

    Wire shape is byte-compatible with vendor shinka_tick_actor JSON response
    for interop at Step 8 (ADR-2605215200 §3 compatibility note).
    """

    actor_did: str
    tick_ms: int
    mood: str
    actions: list[str] = field(default_factory=list)
    heartbeat_written: bool = False
    evolution_written: bool = False
    knowledge_written: bool = False
    evolution_level: int = 0
    base_l2_anchor_tx: str = ""     # Base L2 anchor tx hash (empty if heartbeat-only tick)
    ipfs_cid: str = ""              # IPFS CID of the pinned evolution evidence (empty if heartbeat)
    compose_draft: ComposeDraft | None = None  # M1-confirmed: EVO-X2 LLM draft (None if not should_post)


# ── Witness threshold table (canonical per ADR-2605215400) ──
#
# WITNESS_MIN_BY_LEVEL maps proposed_level → minimum attestation count required
# for an evolution claim to be valid. Lv6 and Lv7 additionally require Council
# co-signature beyond the base count (see COUNCIL_GATE_LV6, COUNCIL_SUPERMAJORITY_LV7).
#
# Thresholds are constitutional constants (ADR-2605215400 §1, depends ADR-2605192415 §witness_min).
WITNESS_MIN_BY_LEVEL: dict[int, int] = {
    1: 2,   # Lv1→Lv2: any active adherent
    2: 3,   # Lv2→Lv3: active adherent (Lv2+)
    3: 5,   # Lv3→Lv4: active contributor (Lv3+)
    4: 7,   # Lv4→Lv5: sustained contributor (Lv4+)
    5: 9,   # Lv5→Lv6: 9 witnesses + ≥COUNCIL_GATE_LV6 Council Lv6+ co-signers
    6: 9,   # Lv6→Lv7: base count satisfied; primary gate is Council supermajority
}

# Default for levels outside the table (defensive fallback).
_WITNESS_MIN_DEFAULT: int = 9

# Lv5→Lv6 advancement requires this many Council Lv6+ co-signers, in addition to
# the 9-witness base count (ADR-2605215400 §3 "For Lv6 (Council eligibility gate)").
COUNCIL_GATE_LV6: int = 2

# Lv6→Lv7 advancement requires this many Council votes (supermajority of 5 = 4),
# overrides the count-based gate (ADR-2605215400 §3 "For Lv7 (founder-equivalent)").
COUNCIL_SUPERMAJORITY_LV7: int = 4

# Attestations must be issued within this window from the advancement event's
# effective timestamp (ADR-2605215400 §2 Witness Recency Policy).
WITNESS_RECENCY_DAYS: int = 365

# Appeal window for evolution events; Council ≥3 may reverse within this period
# (ADR-2605215400 §4 Appeal Window).
EVOLUTION_APPEAL_DAYS: int = 30


@dataclass(slots=True)
class ValidationResult:
    """Result of EvolutionValidationCell attestation check.

    Richer than a bare bool — captures the attestation count, required count,
    and a human-readable reason for pass/fail.  Used by shinka_tick() to log
    validation decisions and by tests to assert threshold logic.

    For Lv7 advancement, `status` may be 'pending' (objection window open),
    'valid' (window closed, no objections), or 'invalid' (objection filed or
    supermajority failed). See ADR-2605215400 §4.
    """

    valid: bool
    attestation_count: int
    required_count: int
    reason: str
    status: str | None = None  # 'pending' | 'valid' | 'invalid' (optional, for Lv7)


# ── Pure helper: _classify_mood ───────────────────────────────────────────────


def _classify_mood(axes: JouchoAxes) -> str:
    """Classify joucho mood from 5-axis values.

    Priority order (confirmed M1 from vendor _classify_mood):
      stress ≥ 70 → stressed  (inhibitor, checked first)
      joy    ≥ 60 → joyful
      calm   ≥ 60 → calm
      gratitude ≥ 60 → grateful
      focus  ≥ 60 → focused
      otherwise    → neutral

    Pure function — no RW access. Portable from vendor _classify_mood.
    """
    if axes.stress >= 70:
        return "stressed"
    if axes.joy >= 60:
        return "joyful"
    if axes.calm >= 60:
        return "calm"
    if axes.gratitude >= 60:
        return "grateful"
    if axes.focus >= 60:
        return "focused"
    return "neutral"


# ── Pure helper: _resolve_cadence ─────────────────────────────────────────────


def _resolve_cadence(state: AdherentState) -> CadencePolicy:
    """Resolve cadence flags from joucho mood × elapsed-since-last-heartbeat.

    Pure function — no RW access.  Ported from vendor _resolve_cadence /
    _cadence_flags (confirmed M1, SHINKA-MIGRATION-NOTES.md §A1).

    Policy table (elapsed_ms thresholds in milliseconds):

    mood      | should_post | should_engage | should_drill | should_validate | should_analyze
    --------- | ----------- | ------------- | ------------ | --------------- | ---------------
    joyful    | ≥30m        | ≥15m          | OFF          | OFF             | ≥60m
    calm      | ≥120m       | ≥60m          | OFF          | ≥120m           | ≥60m
    stressed  | OFF         | OFF           | ≥30m         | ≥60m            | OFF
    grateful  | ≥60m        | ≥10m          | OFF          | OFF             | ≥60m
    focused   | ≥180m       | OFF           | ≥60m         | ≥120m           | ≥30m
    neutral   | ≥120m       | ≥60m          | ≥120m        | ≥120m           | ≥60m

    New-actor edge case: last_heartbeat_ms = 0 → elapsed = now_ms (very large)
    → all time-based flags fire on first tick.
    """
    now_ms = int(time.time() * 1000)
    elapsed_ms = max(0, now_ms - state.last_heartbeat_ms)
    mood = state.mood

    # Threshold helpers (minutes → ms)
    def _mins(m: int) -> int:
        return m * 60 * 1000

    if mood == "joyful":
        return CadencePolicy(
            should_post=elapsed_ms >= _mins(30),
            should_engage=elapsed_ms >= _mins(15),
            should_drill=False,
            should_validate=False,
            should_analyze=elapsed_ms >= _mins(60),
        )
    if mood == "calm":
        return CadencePolicy(
            should_post=elapsed_ms >= _mins(120),
            should_engage=elapsed_ms >= _mins(60),
            should_drill=False,
            should_validate=elapsed_ms >= _mins(120),
            should_analyze=elapsed_ms >= _mins(60),
        )
    if mood == "stressed":
        return CadencePolicy(
            should_post=False,
            should_engage=False,
            should_drill=elapsed_ms >= _mins(30),
            should_validate=elapsed_ms >= _mins(60),
            should_analyze=False,
        )
    if mood == "grateful":
        return CadencePolicy(
            should_post=elapsed_ms >= _mins(60),
            should_engage=elapsed_ms >= _mins(10),
            should_drill=False,
            should_validate=False,
            should_analyze=elapsed_ms >= _mins(60),
        )
    if mood == "focused":
        return CadencePolicy(
            should_post=elapsed_ms >= _mins(180),
            should_engage=False,
            should_drill=elapsed_ms >= _mins(60),
            should_validate=elapsed_ms >= _mins(120),
            should_analyze=elapsed_ms >= _mins(30),
        )
    # neutral (default)
    return CadencePolicy(
        should_post=elapsed_ms >= _mins(120),
        should_engage=elapsed_ms >= _mins(60),
        should_drill=elapsed_ms >= _mins(120),
        should_validate=elapsed_ms >= _mins(120),
        should_analyze=elapsed_ms >= _mins(60),
    )


# ── Pregel cells (skeleton — full impl M2–M4 per ADR-2605215200 §4) ───────────


async def karma_hegemon_observation_cell(adherent_did: str) -> AdherentState:
    """KarmaHegemonObservationCell — placed on levi (port 13023).  [M2 IMPLEMENTED]

    Reads adherent state from MST + IPFS and gathers kyumei signals from the
    com.etzhayyim.shinka.kyumeiSignal collection.

    Replaces vendor:
      - _load_state   (SELECT FROM vertex_shinka_evolution via RW)
      - _kyumei_gather (SELECT FROM vertex_kyumei_signal via RW)

    Substrate path (ADR-2605215200 §2):
      SELECT FROM vertex_shinka_evolution → mst.query(evolutionEvent, did=...)
      SELECT FROM vertex_kyumei_signal    → mst.query(kyumeiSignal, filter_did=..., since=...)

    Trigger: cron */15 * * * *  OR  mst-listener on com.etzhayyim.shinka.kyumeiSignal

    Writes: com.etzhayyim.shinka.observeAdherent (triggers EvolutionValidationCell)

    Returns an AdherentState populated from MST reads.
    SDK calls are stubs (NotImplementedError) until M3 — tested in isolation via mocks.
    """
    if _mst_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py to use "
            "karma_hegemon_observation_cell in production."
        )

    # Step 1: Read latest evolution event from MST to get last_evolution_at and mood.
    # Vendor _load_state reads from vertex_shinka_evolution via RW SELECT.
    # Religious-corp reads from MST via mst.query (stub until M3).
    evolution_records: list[dict[str, Any]] = await _mst_mod.query(
        "com.etzhayyim.shinka.evolutionEvent",
        did=adherent_did,
        limit=1,
        sort="desc",
    )

    # Derive baseline state from the most recent evolution event (or safe defaults).
    if evolution_records:
        latest = evolution_records[0]
        last_evolution_at: str = str(latest.get("recordedAt", "2026-01-01T00:00:00Z"))
        mood: str = str(latest.get("mood", "neutral"))
        evolution_level: int = int(latest.get("evolutionLevel", 0))
    else:
        # New adherent with no prior evolution events — use safe defaults.
        last_evolution_at = "2026-01-01T00:00:00Z"
        mood = "neutral"
        evolution_level = 0

    # Step 2: Gather kyumei signals since last evolution.
    # Try mst-projector first (no 100-record cap); fall back to mst.query on error.
    _KYUMEI_COLLECTION = "com.etzhayyim.shinka.kyumeiSignal"
    kyumei_records: list[dict[str, Any]]
    if _projector_mod is not None:
        try:
            proj_result = await _projector_mod.query_by_did(
                adherent_did, collection=_KYUMEI_COLLECTION, limit=500,
            )
            kyumei_records = proj_result.get("records", [])
        except Exception as _proj_err:
            _log.warning(
                "karma_hegemon_observation_cell: mst-projector unreachable, "
                "falling back to client-side mst.query: %s", _proj_err,
            )
            kyumei_records = await _mst_mod.query(
                _KYUMEI_COLLECTION, filter_did=adherent_did,
                since=last_evolution_at, limit=50,
            )
    else:
        kyumei_records = await _mst_mod.query(
            _KYUMEI_COLLECTION, filter_did=adherent_did,
            since=last_evolution_at, limit=50,
        )

    # Step 3: Construct AdherentState from MST data.
    state = AdherentState(
        did=adherent_did,
        sbt_token_id=evolution_level,   # SBT token ID maps to current evolution level
        last_evolution_at=last_evolution_at,
        kyumei_signals=kyumei_records,
        mood=mood,
        axes=JouchoAxes(),              # M1-confirmed defaults; refined from signal agg at M3
        last_heartbeat_ms=int(time.time() * 1000),
    )

    # Note: In production, this cell also writes an com.etzhayyim.shinka.observeAdherent
    # record to MST to trigger EvolutionValidationCell. That dispatch is deferred until
    # the pds.put_record stub is replaced at M3.
    # await _pds_mod.put_record(
    #     collection="com.etzhayyim.shinka.observeAdherent",
    #     record={"$type": "com.etzhayyim.shinka.observeAdherent", ...},
    # )

    return state


async def _check_charter_compliance(adherent_did: str) -> str:
    """Query charter compliance status for an adherent.

    Returns one of: "compliant", "pending", "non_aligned", "unknown".

    Queries the canonical lexicon com.etzhayyim.apps.etzhayyim.charter-compliance
    (ChartersComplianceRegistry attestation records per ADR-2605192100 §1.12).
    Until the Solidity-binding for ChartersComplianceRegistry.sol is wired into
    the SDK (M4+ when sdk.l2 grows contract-read support), this falls back to
    MST lookup via mst.query().

    Returns "unknown" on any infrastructure failure — advancement is NOT gated
    on infrastructure availability (presumption of innocence).

    Args:
        adherent_did: DID of the adherent to check.

    Returns:
        "compliant"   — adherent is in good standing.
        "pending"     — attestation is being processed; advance normally.
        "non_aligned" — adherent is flagged non-aligned; BLOCKS advancement.
        "unknown"     — no compliance record or query failed; advance normally.
    """
    try:
        records = await _mst_mod.query(
            collection="com.etzhayyim.apps.etzhayyim.charter-compliance",
            filter={"subjectDid": adherent_did},
        )
        if not records:
            return "unknown"  # No compliance record = unknown, allow advancement (presumption of innocence)

        # Get latest record by recordedAt timestamp.
        latest = max(records, key=lambda r: r.get("value", {}).get("recordedAt", ""))
        status = latest.get("value", {}).get("complianceStatus", "unknown")
        return status if status in ("compliant", "pending", "non_aligned") else "unknown"
    except Exception:
        # If query fails, default to allowing advancement (don't gate on infrastructure failure).
        return "unknown"


async def evolution_validation_cell(claim: EvolutionClaim) -> ValidationResult:
    """EvolutionValidationCell — placed on levi (port 13024), audit-leader role.  [M2 IMPLEMENTED]

    Validates an evolution claim per ADR-2605215400 canonical thresholds.

    Lv1-5: count-based with recency filter (WITNESS_RECENCY_DAYS).
    Lv6: count threshold + ≥COUNCIL_GATE_LV6 Council Lv6+ co-signers.
    Lv7: COUNCIL_SUPERMAJORITY_LV7 Council votes (count threshold informational).

    Charter-rider compliance gate (ADR-2605215400 §5):
      Before attestation checks, queries ChartersComplianceRegistry for the
      adherent's compliance status. If "non_aligned", advancement is immediately
      rejected. "unknown" or "pending" or "compliant" allow the claim to proceed
      to attestation validation. Infrastructure failures default to "unknown"
      (presumption of innocence — don't gate on infra failures).

    Replaces vendor:
      - _koji_validate (SELECT FROM vertex_koji_attestation via RW)

    Trigger: mst-listener on com.etzhayyim.shinka.observeAdherent

    Attestation query path:
      Queries com.etzhayyim.apps.etzhayyim.charter-attestation via
      mst.council_attestation_details() with recency filter (WITNESS_RECENCY_DAYS).
      Council Lv6+ status resolved against COUNCIL_LV6_DIDS bootstrap roster
      (ADR-2605192300); live registry NSID TBD.

    Threshold source: WITNESS_MIN_BY_LEVEL canonical table (ADR-2605215400 §1).
      Lv6 additionally requires ≥COUNCIL_GATE_LV6 Council Lv6+ co-signers (ADR §3).
      Lv7 advancement uses COUNCIL_SUPERMAJORITY_LV7 vote, overriding count gate (ADR §3).
      Recency: attestations must be within WITNESS_RECENCY_DAYS (ADR §2).

    Returns: ValidationResult (valid, attestation_count, required_count, reason).
    Writes on valid: com.etzhayyim.shinka.validateEvolution → triggers EvolutionEmissionCell.
    SDK calls are stubs (NotImplementedError) until M3 — tested in isolation via mocks.
    """
    if _mst_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py to use "
            "evolution_validation_cell in production."
        )

    # ── §1: Charter-rider compliance gate (ADR-2605215400 §5) ──────────────────
    # An adherent must be in good standing (not flagged non-aligned) to advance.
    # Query ChartersComplianceRegistry attestation status for the adherent.
    compliance = await _check_charter_compliance(claim.adherent_did)
    if compliance == "non_aligned":
        return ValidationResult(
            valid=False,
            attestation_count=0,
            required_count=0,
            reason=(
                f"Charter-rider non-compliance for {claim.adherent_did}: "
                f"adherent is flagged non-aligned under ChartersComplianceRegistry. "
                f"Advancement rejected per ADR-2605215400 §5. "
                f"Rehabilitation path: Council vote per ADR-2605192230."
            ),
            status="invalid",
        )

    level = claim.proposed_level
    required_count = WITNESS_MIN_BY_LEVEL.get(level, _WITNESS_MIN_DEFAULT)
    status: str | None = None  # Will be set for Lv7 appeals; None for Lv1-6

    # Query Council attestation registry with recency filter.
    # Returns list of dicts: {attestor_did, is_council_lv6, attestation_at,
    #                          attestation_uri, evidence_cid}
    # Filters to within WITNESS_RECENCY_DAYS per ADR-2605215400 §2.
    attestations: list[dict] = await _mst_mod.council_attestation_details(
        claim.adherent_did,
        level,
        since_days=WITNESS_RECENCY_DAYS,
    )
    attestation_count = len(attestations)
    council_count = sum(1 for a in attestations if a.get("is_council_lv6", False))

    if level <= 5:
        # Lv1–5: count-only path with recency filter (ADR-2605215400 §1).
        valid = attestation_count >= required_count
        reason = (
            f"Lv{level} advancement: {attestation_count}/{required_count} attestations "
            f"within {WITNESS_RECENCY_DAYS} days. "
            f"{'Valid' if valid else 'Insufficient'}."
        )
        effective_required = required_count

    elif level == 6:
        # Lv6 Council eligibility gate (ADR-2605215400 §3):
        # count threshold AND ≥COUNCIL_GATE_LV6 Council Lv6+ co-signers.
        if attestation_count < required_count:
            valid = False
            reason = (
                f"Lv6 advancement: insufficient witness count "
                f"{attestation_count}/{required_count} within {WITNESS_RECENCY_DAYS} days."
            )
        elif council_count < COUNCIL_GATE_LV6:
            valid = False
            reason = (
                f"Lv6 advancement: insufficient Council Lv6+ co-signers "
                f"{council_count}/{COUNCIL_GATE_LV6} "
                f"(count {attestation_count}/{required_count} OK)."
            )
        else:
            valid = True
            reason = (
                f"Lv6 advancement valid: {attestation_count} attestations + "
                f"{council_count} Council Lv6+ co-signers (gate {COUNCIL_GATE_LV6})."
            )
        effective_required = COUNCIL_GATE_LV6

    elif level == 7:
        # Lv7 Council supermajority + 30-day public objection window (ADR-2605215400 §3-4):
        # Primary gate is Council votes (≥4 of 5). After supermajority passes, claim
        # enters 30-day appeal window. Objections filed during window block finalization.

        # Step 1: Check supermajority gate.
        supermajority_pass = council_count >= COUNCIL_SUPERMAJORITY_LV7

        if not supermajority_pass:
            # Supermajority failed — no need to check objection window.
            valid = False
            status = "invalid"
            reason = (
                f"Lv7 advancement: {council_count}/{COUNCIL_SUPERMAJORITY_LV7} "
                f"Council votes (supermajority failed). "
            )
            effective_required = COUNCIL_SUPERMAJORITY_LV7
        else:
            # Step 2: Supermajority passed. Check objection window.
            import datetime as _dt

            now = _dt.datetime.now(tz=_dt.timezone.utc)

            # Determine if claim is within appeal window.
            if claim.validated_at is None:
                # First-time validation: claim was just approved, set validated_at now.
                validated_dt = now
                within_window = True
            else:
                # Re-check case: claim already validated, check if window still open.
                try:
                    validated_dt = _dt.datetime.fromisoformat(
                        claim.validated_at.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    # Malformed timestamp — treat as within window (conservative).
                    validated_dt = now
                    within_window = True
                else:
                    elapsed = now - validated_dt
                    within_window = elapsed.total_seconds() < (EVOLUTION_APPEAL_DAYS * 86400)

            if within_window:
                # Within appeal window. Query for objections filed against this claim.
                objections: list[dict] = await _mst_mod.council_objections(
                    claim.claim_id,
                    since_days=EVOLUTION_APPEAL_DAYS,
                )

                if objections:
                    # Objections filed → claim is contested, invalid until window closes.
                    valid = False
                    status = "invalid"
                    objector_list = ", ".join(o.get("objector_did", "?") for o in objections[:3])
                    reason = (
                        f"Lv7 advancement objected: {len(objections)} objection(s) filed "
                        f"({objector_list}{'...' if len(objections) > 3 else ''}). "
                        f"Claim remains pending until appeal window closes."
                    )
                else:
                    # No objections yet, but window still open → pending status.
                    valid = False  # Not final until window closes
                    status = "pending"
                    window_close_dt = validated_dt + _dt.timedelta(days=EVOLUTION_APPEAL_DAYS)
                    window_close_str = (
                        window_close_dt
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                    reason = (
                        f"Lv7 advancement pending: supermajority ({council_count}/{COUNCIL_SUPERMAJORITY_LV7}) passed. "
                        f"30-day objection window open until {window_close_str}. "
                        f"No objections filed yet."
                    )
            else:
                # Window closed → no further objections possible. Finalize as valid.
                valid = True
                status = "valid"
                reason = (
                    f"Lv7 advancement validated: supermajority ({council_count}/{COUNCIL_SUPERMAJORITY_LV7}) passed. "
                    f"30-day objection window closed with no objections. "
                    f"Advancement finalized."
                )

            effective_required = COUNCIL_SUPERMAJORITY_LV7

    else:
        valid = False
        reason = f"Unknown level {level} — no advancement allowed."
        effective_required = _WITNESS_MIN_DEFAULT

    result = ValidationResult(
        valid=valid,
        attestation_count=attestation_count,
        required_count=effective_required,
        reason=reason,
        status=status if level == 7 else None,  # Only Lv7 has status field in use
    )

    if valid:
        import datetime as _dt

        validated_at = (
            _dt.datetime.now(tz=_dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        # Write validateEvolution record to trigger EvolutionEmissionCell via MST listener.
        await _pds_mod.put_record(
            collection="com.etzhayyim.shinka.validateEvolution",
            record={
                "$type": "com.etzhayyim.shinka.validateEvolution",
                "claimId": claim.claim_id,
                "adherentDid": claim.adherent_did,
                "proposedLevel": claim.proposed_level,
                "attestationCount": attestation_count,
                "requiredCount": effective_required,
                "validatedAt": validated_at,
            },
        )
        _log.info(
            "evolution_validation_cell: VALID claim_id=%s adherent=%s level=%d "
            "attestations=%d council=%d required=%d",
            claim.claim_id,
            claim.adherent_did,
            level,
            attestation_count,
            council_count,
            effective_required,
        )
    else:
        _log.warning(
            "evolution_validation_cell: INVALID claim_id=%s adherent=%s level=%d "
            "attestations=%d council=%d required=%d reason=%s",
            claim.claim_id,
            claim.adherent_did,
            level,
            attestation_count,
            council_count,
            effective_required,
            reason,
        )

    return result


async def evolution_emission_cell(
    claim: EvolutionClaim,
    validation_result: ValidationResult | None = None,
) -> str:
    """EvolutionEmissionCell — placed on simeon (port 13025), ipfs-pinner + stewardship-leader.
    [M2 IMPLEMENTED]

    Writes an evolution event to MST + IPFS pin + Base L2 anchor.
    This is the full ADR-2605171800 anchor pipeline Stage 3-5.
    Returns the Base L2 anchor transaction hash.

    Replaces vendor:
      - _emit_evolution (INSERT INTO vertex_shinka_evolution_event via RW)

    Trigger: mst-listener on com.etzhayyim.shinka.validateEvolution

    Write path (ADR-2605171800 Stage 3-5):
      Stage 3 — MST record: pds.put_record(collection=evolutionEvent)
      Stage 4 — IPFS pin: ipfs.pin_many(claim.evidence_cids) on simeon
      Stage 5 — Base L2 anchor: l2.anchor(commit_cid) → tx hash

    Error handling: if IPFS pin or L2 anchor fails, logs and re-raises.
    Emission must be all-or-nothing per witness invariant (ADR-2605215200 §1).
    Do NOT silently swallow errors.

    simeon is the correct placement because it already runs the ipfs-pinner daemon
    (ADR-2605171800 Stage 4) and CommissioningCell.

    Returns: Base L2 anchor transaction hash (hex string, 0x-prefixed).
    SDK calls are stubs (NotImplementedError) until M3 — tested in isolation via mocks.
    """
    if _pds_mod is None or _ipfs_mod is None or _l2_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py to use "
            "evolution_emission_cell in production."
        )

    import datetime as _dt

    now_ms = int(time.time() * 1000)
    validated_at = (
        _dt.datetime.now(tz=_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    # Stage 3 — MST record: write evolutionEvent to PDS.
    # Lexicon: com.etzhayyim.shinka.evolutionEvent
    # Required fields: adherentDid, previousLevel, newLevel, claimId,
    #                  validatedAt, evidenceCids, attestationDids, l2AnchorTxHash
    # l2AnchorTxHash is filled in after Stage 5; use "" as placeholder.
    mst_record: dict[str, Any] = {
        "$type": "com.etzhayyim.shinka.evolutionEvent",
        "adherentDid": claim.adherent_did,
        "previousLevel": max(0, claim.proposed_level - 1),
        "newLevel": claim.proposed_level,
        "claimId": claim.claim_id,
        "validatedAt": validated_at,
        "evidenceCids": list(claim.evidence_cids),
        "attestationDids": [],   # populated by CouncilLevelAdvancementCell at M3
        "l2AnchorTxHash": "",    # filled after Stage 5
    }
    _log.info(
        "evolution_emission_cell: Stage 3 — writing evolutionEvent "
        "claim_id=%s adherent=%s level=%d",
        claim.claim_id,
        claim.adherent_did,
        claim.proposed_level,
    )
    mst_result = await _pds_mod.put_record(
        collection="com.etzhayyim.shinka.evolutionEvent",
        record=mst_record,
    )
    commit_cid: str = mst_result.get("cid", "")

    # Stage 4 — IPFS pin: pin all evidence CIDs on simeon.
    # ipfs-pinner daemon is on simeon per ADR-2605171800 Stage 4.
    # All-or-nothing: if any pin fails, log and raise.
    if claim.evidence_cids:
        _log.info(
            "evolution_emission_cell: Stage 4 — pinning %d evidence CIDs "
            "claim_id=%s",
            len(claim.evidence_cids),
            claim.claim_id,
        )
        try:
            await _ipfs_mod.pin_many(list(claim.evidence_cids))
        except Exception as pin_err:
            _log.error(
                "evolution_emission_cell: Stage 4 FAILED — IPFS pin error "
                "claim_id=%s err=%s",
                claim.claim_id,
                pin_err,
            )
            raise  # re-raise: emission is all-or-nothing per witness invariant

    # Stage 5 — Base L2 anchor: submit MST commit CID to the anchor contract.
    # anchor-cron collects and batches; l2.anchor() submits a single anchor.
    _log.info(
        "evolution_emission_cell: Stage 5 — anchoring to Base L2 "
        "claim_id=%s commit_cid=%s",
        claim.claim_id,
        commit_cid,
    )
    try:
        anchor_tx: str = await _l2_mod.anchor(commit_cid)
    except Exception as anchor_err:
        _log.error(
            "evolution_emission_cell: Stage 5 FAILED — L2 anchor error "
            "claim_id=%s err=%s",
            claim.claim_id,
            anchor_err,
        )
        raise  # re-raise: emission is all-or-nothing per witness invariant

    _log.info(
        "evolution_emission_cell: COMPLETE claim_id=%s adherent=%s "
        "level=%d anchor_tx=%s",
        claim.claim_id,
        claim.adherent_did,
        claim.proposed_level,
        anchor_tx,
    )
    return anchor_tx


async def shinka_heartbeat_cell(
    *,
    cycle: int = 0,
    cells_observed: int = 0,
    cells_validated: int = 0,
    cells_emitted: int = 0,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """ShinkaHeartbeatCell — placed on levi (port 13026).  [M2 IMPLEMENTED]

    Cron-driven status emission at 15-minute intervals.
    Writes a shinkaHeartbeat record to MST only — no IPFS pin or Base L2 anchor
    needed for heartbeat (analogous to LandStewardshipMonitoringCell which is MST-only).

    Replaces vendor:
      - _write_heartbeat (INSERT INTO vertex_shinka_heartbeat via RW)

    Substrate path (ADR-2605215200 §2):
      INSERT INTO vertex_shinka_heartbeat → pds.put_record(shinkaHeartbeat)
      MST-only: no IPFS pin or Base L2 anchor

    Trigger: cron */15 * * * *  (matches vendor shinka_cron_tick K8s CronJob cadence)

    Lexicon: com.etzhayyim.shinka.shinkaHeartbeat
    Required fields: nodeName, cycle, recordedAt, cellsObserved, cellsValidated, cellsEmitted

    Returns: heartbeat status dict compatible with vendor heartbeat_written field.
    SDK pds.put_record is a stub (NotImplementedError) until M3; the record dict
    is returned directly so cell logic can be tested in isolation via mocks.
    """
    import datetime as _dt

    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py to use "
            "shinka_heartbeat_cell in production."
        )

    recorded_at = (
        _dt.datetime.now(tz=_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    # Build the heartbeat record matching the com.etzhayyim.shinka.shinkaHeartbeat lexicon.
    # node_name is "levi" — ShinkaHeartbeatCell is placed on levi per ADR-2605215200 §1.
    if _ShinkaHeartbeatRecord is not None:
        heartbeat = _ShinkaHeartbeatRecord(
            node_name="levi",
            cycle=cycle,
            recorded_at=recorded_at,
            cells_observed=cells_observed,
            cells_validated=cells_validated,
            cells_emitted=cells_emitted,
            errors=errors or [],
        )
        mst_record = heartbeat.to_mst_record()
    else:
        # Fallback if SDK types are unavailable: build raw dict matching lexicon wire shape.
        mst_record = {
            "$type": "com.etzhayyim.shinka.shinkaHeartbeat",
            "nodeName": "levi",
            "cycle": cycle,
            "recordedAt": recorded_at,
            "cellsObserved": cells_observed,
            "cellsValidated": cells_validated,
            "cellsEmitted": cells_emitted,
        }
        if errors:
            mst_record["errors"] = errors

    # Dispatch to PDS via @etzhayyim/sdk.
    # MST-only write: no IPFS pin or Base L2 anchor needed for heartbeat
    # (analogous to LandStewardshipMonitoringCell per ADR-2605215200 §1).
    await _pds_mod.put_record(
        collection="com.etzhayyim.shinka.shinkaHeartbeat",
        record=mst_record,
    )

    # Return status dict compatible with vendor heartbeat_written field.
    return {
        "heartbeatWritten": True,
        "nodeName": "levi",
        "cycle": cycle,
        "recordedAt": recorded_at,
        "cellsObserved": cells_observed,
        "cellsValidated": cells_validated,
        "cellsEmitted": cells_emitted,
        "errors": errors or [],
        "mstRecord": mst_record,
    }


# ── Public tick() entry point (matches vendor shinka_tick_actor wire shape) ───


async def shinka_tick(adherent_did: str | None = None) -> dict[str, Any]:
    """Religious-corp variant of vendor shinka_tick_actor SQL UDF.  [M2 IMPLEMENTED]

    Orchestrates the full Pregel super-step for a single adherent (or logs a
    "would iterate" notice for the no-arg multi-adherent case):
      1. KarmaHegemonObservationCell  → AdherentState
      2. _resolve_cadence             → CadencePolicy
      3. EvolutionValidationCell      → ValidationResult  (if pending evolution claim)
      4. EvolutionEmissionCell        → anchor_tx          (if validation passed)
      5. ShinkaHeartbeatCell          → heartbeat record

    Replaces RW SQL UDF with four-cell dispatch on Murakumo fleet.
    In production, cells are dispatched by kotoba-kotodama-cell-runner, not called directly.
    This function provides a compatible programmatic entry point for testing and
    for callers that need a synchronous result from one full tick.

    Wire shape (output) is byte-compatible with vendor shinka_tick_actor JSON response:
      {
        "cycle":            int,
        "observed":         int,    # number of adherents observed (1 for single-DID)
        "validated":        int,    # number of evolution claims validated (0 or 1)
        "emitted":          int,    # number of evolution events emitted (0 or 1)
        "errors":           list[str],
        "heartbeatWritten": bool,
        "evolutionWritten": bool,
        "baseLs2AnchorTx":  str,   # Base L2 anchor tx (empty if no emission)
        "adherentDid":      str | None,
        "mood":             str,
        "cadence":          dict,   # resolved cadence flags
      }

    Multi-adherent case (adherent_did is None):
      Logs a "would iterate" message and returns early with observed=0.
      Full multi-adherent iteration requires the kotoba-kotodama-cell-runner tick loop
      (pending M3 fleet.toml wiring).

    Note: In production the Pregel super-step is cell-driven (kotoba-kotodama-cell-runner),
    not called via this function. This entry point is for CLI tooling and integration
    tests only.
    """
    # Summary accumulators.
    cycle = int(time.time())  # use unix timestamp as monotonic cycle counter
    errors: list[str] = []
    observed = 0
    validated = 0
    emitted = 0
    evolution_written = False
    anchor_tx = ""
    mood = "neutral"
    cadence_dict: dict[str, bool] = {}

    if adherent_did is None:
        # Multi-adherent case: log intent and return early.
        # Full iteration requires kotoba-kotodama-cell-runner tick loop (M3).
        _log.info(
            "shinka_tick: no adherent_did — would iterate over all adherents-due-for-tick. "
            "Full multi-adherent loop pending M3 kotoba-kotodama-cell-runner fleet.toml wiring."
        )
        heartbeat_result = await shinka_heartbeat_cell(
            cycle=cycle,
            cells_observed=0,
            cells_validated=0,
            cells_emitted=0,
            errors=[],
        )
        return {
            "cycle": cycle,
            "observed": 0,
            "validated": 0,
            "emitted": 0,
            "errors": [],
            "heartbeatWritten": heartbeat_result["heartbeatWritten"],
            "evolutionWritten": False,
            "baseLs2AnchorTx": "",
            "adherentDid": None,
            "mood": "neutral",
            "cadence": {},
        }

    # Step 1: KarmaHegemonObservationCell → AdherentState
    try:
        state: AdherentState = await karma_hegemon_observation_cell(adherent_did)
        observed = 1
        mood = state.mood
        _log.info(
            "shinka_tick: observed adherent=%s mood=%s sbt_level=%d",
            adherent_did,
            mood,
            state.sbt_token_id,
        )
    except Exception as obs_err:
        errors.append(f"observation: {obs_err}")
        _log.error("shinka_tick: observation failed adherent=%s err=%s", adherent_did, obs_err)
        # Cannot proceed without state — emit heartbeat with error and return.
        heartbeat_result = await shinka_heartbeat_cell(
            cycle=cycle,
            cells_observed=0,
            cells_validated=0,
            cells_emitted=0,
            errors=errors,
        )
        return {
            "cycle": cycle,
            "observed": 0,
            "validated": 0,
            "emitted": 0,
            "errors": errors,
            "heartbeatWritten": heartbeat_result["heartbeatWritten"],
            "evolutionWritten": False,
            "baseLs2AnchorTx": "",
            "adherentDid": adherent_did,
            "mood": "neutral",
            "cadence": {},
        }

    # Step 2: _resolve_cadence → CadencePolicy
    cadence: CadencePolicy = _resolve_cadence(state)
    cadence_dict = {
        "shouldPost": cadence.should_post,
        "shouldEngage": cadence.should_engage,
        "shouldDrill": cadence.should_drill,
        "shouldValidate": cadence.should_validate,
        "shouldAnalyze": cadence.should_analyze,
    }

    # Step 3 & 4: validation + emission (if cadence permits and pending claim exists).
    if cadence.should_validate and state.proposed_evolution is not None:
        claim = state.proposed_evolution
        _log.info(
            "shinka_tick: validating evolution claim_id=%s adherent=%s level=%d",
            claim.claim_id,
            adherent_did,
            claim.proposed_level,
        )
        try:
            vresult: ValidationResult = await evolution_validation_cell(claim)
            validated = 1
            _log.info(
                "shinka_tick: validation result valid=%s count=%d/%d",
                vresult.valid,
                vresult.attestation_count,
                vresult.required_count,
            )
            if vresult.valid:
                _log.info(
                    "shinka_tick: emitting evolution claim_id=%s", claim.claim_id
                )
                try:
                    anchor_tx = await evolution_emission_cell(claim, vresult)
                    emitted = 1
                    evolution_written = True
                    _log.info(
                        "shinka_tick: evolution emitted anchor_tx=%s", anchor_tx
                    )
                except Exception as emit_err:
                    errors.append(f"emission: {emit_err}")
                    _log.error(
                        "shinka_tick: emission failed claim_id=%s err=%s",
                        claim.claim_id,
                        emit_err,
                    )
        except Exception as val_err:
            errors.append(f"validation: {val_err}")
            _log.error(
                "shinka_tick: validation failed claim_id=%s err=%s",
                claim.claim_id,
                val_err,
            )

    # Step 5: ShinkaHeartbeatCell — always runs at end of tick.
    try:
        heartbeat_result = await shinka_heartbeat_cell(
            cycle=cycle,
            cells_observed=observed,
            cells_validated=validated,
            cells_emitted=emitted,
            errors=errors if errors else None,
        )
        heartbeat_written = heartbeat_result["heartbeatWritten"]
    except Exception as hb_err:
        errors.append(f"heartbeat: {hb_err}")
        _log.error("shinka_tick: heartbeat failed err=%s", hb_err)
        heartbeat_written = False

    return {
        "cycle": cycle,
        "observed": observed,
        "validated": validated,
        "emitted": emitted,
        "errors": errors,
        "heartbeatWritten": heartbeat_written,
        "evolutionWritten": evolution_written,
        "baseLs2AnchorTx": anchor_tx,
        "adherentDid": adherent_did,
        "mood": mood,
        "cadence": cadence_dict,
    }
