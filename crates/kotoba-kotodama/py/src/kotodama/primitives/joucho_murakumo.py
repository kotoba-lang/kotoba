"""joucho_murakumo — Religious-corp variant of joucho (5-axis emotional state) aggregator.

Per JOUCHO-MIGRATION-DESIGN.md + ADR-2605215200. Replaces vendor vertex_joucho RW table
with MST-backed com.etzhayyim.joucho.joucho records, aggregated hourly from kyumeiSignal.

Pregel cell: JouchoAggregationCell on levi. Trigger: cron 0 * * * * (hourly).

Aggregation algorithm (per design doc):
  joy       ← ritual (×0.8) + kuniUmi-witness (×0.6) signals
  calm      ← oath (×0.9) + governance-participation (×0.8) signals
  stress    ← inhibitor (absence of positive signals) — inverse of positive mean
  gratitude ← contribution (×1.0) signals
  focus     ← oath (×0.7) + contribution (×0.5) signals (deep practice)

Normalisation: accumulate per signal-kind, then divide by total signal count, clamp 0-1000.

Substrate-fit: forbidden RW/RunPod/Stripe (per ADR-2605172000/2605215000).
"""

from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass, field
from typing import Any

try:
    from etzhayyim_sdk import pds as _pds_mod
    from etzhayyim_sdk import mst as _mst_mod
    from etzhayyim_sdk.errors import PdsNotFoundError as _PdsNotFoundError
except ImportError:
    _pds_mod = None  # type: ignore[assignment]
    _mst_mod = None  # type: ignore[assignment]
    _PdsNotFoundError = None  # type: ignore[assignment, misc]

try:
    from etzhayyim_sdk import mst_projector as _projector_mod
except ImportError:
    _projector_mod = None  # type: ignore[assignment]

_log = logging.getLogger(__name__)

# ── Substrate-fit invariant ────────────────────────────────────────────────────
# Fail loudly if imported in a RisingWave or RunPod environment.
# Mirrors shinka_murakumo.py pattern (ADR-2605172000 / ADR-2605215000).
if "runpod" in os.environ.get("PATH", "").lower() or os.environ.get("RW_URL"):
    raise ImportError(
        "joucho_murakumo religious-corp-only — RUNPOD/RW environment detected. "
        "Use vendor vertex_joucho for paid SaaS workloads."
    )


# ── Constants (per JOUCHO-MIGRATION-DESIGN.md aggregation algorithm) ──────────

JOUCHO_AGGREGATION_WINDOW_DAYS: int = 7  # 7-day kyumeiSignal lookback

# Permille (0-1000) mood thresholds. Vendor used 0-100; religious-corp scales ×10
# for permille precision. Mood gates match JOUCHO-MIGRATION-DESIGN.md §Vendor Mechanism.
JOY_MOOD_THRESHOLD_PERMILLE: int = 600       # joy ≥ 600‰ → joyful (vendor: ≥ 60%)
CALM_MOOD_THRESHOLD_PERMILLE: int = 600      # calm ≥ 600‰ → calm
STRESS_MOOD_THRESHOLD_PERMILLE: int = 700    # stress ≥ 700‰ → stressed (priority gate)
GRATITUDE_MOOD_THRESHOLD_PERMILLE: int = 600 # gratitude ≥ 600‰ → grateful
FOCUS_MOOD_THRESHOLD_PERMILLE: int = 600     # focus ≥ 600‰ → focused

# New-adherent defaults in permille (×10 from vendor: joy=40, calm=40, stress=20,
# gratitude=30, focus=40 → all × 10).
NEW_ADHERENT_DEFAULTS: dict[str, int] = {
    "joy": 400,
    "calm": 400,
    "stress": 200,
    "gratitude": 300,
    "focus": 400,
}

# Signal-kind × axis weight mapping (JOUCHO-MIGRATION-DESIGN.md §Aggregation Algorithm).
# Values are fixed-point permille multipliers: axis_acc += signal.weight * factor // 1000.
# See design doc table for derivation.
#
# | signalKind              | joy  | calm | gratitude | focus | Notes                   |
# |-------------------------|------|------|-----------|-------|-------------------------|
# | ritual                  | 800  | -    | -         | 300   | ×0.8 joy, ×0.3 focus   |
# | oath                    | -    | 900  | -         | 700   | ×0.9 calm, ×0.7 focus  |
# | contribution            | -    | -    | 1000      | 500   | ×1.0 grat, ×0.5 focus  |
# | governance-participation| -    | 800  | -         | -     | ×0.8 calm               |
# | kuniUmi-witness         | 600  | -    | -         | -     | ×0.6 joy                |
SIGNAL_KIND_TO_AXIS_WEIGHTS: dict[str, dict[str, int]] = {
    "ritual":                  {"joy": 800, "focus": 300},
    "oath":                    {"calm": 900, "focus": 700},
    "contribution":            {"gratitude": 1000, "focus": 500},
    "governance-participation": {"calm": 800},
    "kuniUmi-witness":         {"joy": 600},
}


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class JouchoRecord:
    """com.etzhayyim.joucho.joucho record — matches lexicon wire shape byte-for-byte.

    All 5 axes are permille integers (0-1000).  Required fields: adherentDid,
    joy, calm, stress, gratitude, focus, computed_at, from_signal_count.
    Optional: from_signals_since, aggregator_node, from_signal_days.

    New-adherent defaults (from_signal_count == 0):
      joy=400, calm=400, stress=200, gratitude=300, focus=400 → neutral mood.
    """

    adherentDid: str
    joy: int = 0           # permille 0-1000; driven by ritual + kuniUmi-witness
    calm: int = 0          # permille; driven by oath + governance-participation
    stress: int = 0        # permille; inhibitor — inverse of positive mean
    gratitude: int = 0     # permille; driven by contribution
    focus: int = 0         # permille; driven by oath + contribution (deep practice)
    computed_at: str = ""  # ISO 8601 datetime
    from_signal_count: int = 0    # 0 = new-adherent defaults applied
    from_signals_since: str = ""  # optional: start of aggregation window (ISO 8601)
    aggregator_node: str = ""     # optional: Murakumo node name (e.g. "levi")
    from_signal_days: int = 7     # optional: recency window in days (default 7)


# ── Pure functions ─────────────────────────────────────────────────────────────


def aggregate_signals(
    signals: list[dict[str, Any]],
) -> dict[str, int]:
    """Pure function: list of kyumeiSignal records → 5-axis permille dict.

    Algorithm (per JOUCHO-MIGRATION-DESIGN.md §Pseudocode):
      1. Accumulate: for each signal, axis_acc += signal.weight * axis_factor // 1000
      2. Normalise: axis = clamp(0, 1000, axis_acc / signal_count)
      3. Stress (inhibitor): 1000 - average(joy, calm, gratitude, focus), clamped 0-1000

    Empty signals list → new-adherent defaults (joy=400, calm=400, stress=200,
    gratitude=300, focus=400).  Signals with unknown signalKind are silently skipped.

    Args:
        signals: list of kyumeiSignal record dicts.  Expected keys: signalKind (str),
                 weight (int 0-1000).  Unknown keys are ignored.

    Returns:
        dict with keys: joy, calm, stress, gratitude, focus — all int 0-1000.
    """
    if not signals:
        return dict(NEW_ADHERENT_DEFAULTS)

    signal_count = len(signals)
    # Accumulate weighted sums per axis (raw, before normalisation).
    acc: dict[str, int] = {"joy": 0, "calm": 0, "gratitude": 0, "focus": 0}

    for signal in signals:
        kind = signal.get("signalKind", "")
        weight = int(signal.get("weight", 0))
        for axis, factor in SIGNAL_KIND_TO_AXIS_WEIGHTS.get(kind, {}).items():
            if axis in acc:
                acc[axis] += (weight * factor) // 1000

    # Normalise: divide by signal count, then clamp 0-1000.
    result: dict[str, int] = {}
    for axis in ("joy", "calm", "gratitude", "focus"):
        result[axis] = min(1000, max(0, acc[axis] // signal_count))

    # Stress (inhibitor): 1000 - mean(positive axes), clamped 0-1000.
    # Per design doc: "stress = clamp(0, 1000, 1000 - positive_mood)"
    # where positive_mood = (joy + calm + gratitude + focus) / 4.
    positive_mean = (
        result["joy"] + result["calm"] + result["gratitude"] + result["focus"]
    ) // 4
    result["stress"] = max(0, min(1000, 1000 - positive_mean))

    return result


def classify_mood(record: JouchoRecord) -> str:
    """Pure function: 5-axis JouchoRecord → mood string.

    Priority order (M1-confirmed from vendor _classify_mood; permille ×10 scale):
      stress ≥ 700 → "stressed"  (inhibitor, always checked first)
      joy    ≥ 600 → "joyful"
      calm   ≥ 600 → "calm"
      gratitude ≥ 600 → "grateful"
      focus  ≥ 600 → "focused"
      otherwise   → "neutral"

    Matches vendor mood classification rescaled to permille.
    """
    if record.stress >= STRESS_MOOD_THRESHOLD_PERMILLE:
        return "stressed"
    if record.joy >= JOY_MOOD_THRESHOLD_PERMILLE:
        return "joyful"
    if record.calm >= CALM_MOOD_THRESHOLD_PERMILLE:
        return "calm"
    if record.gratitude >= GRATITUDE_MOOD_THRESHOLD_PERMILLE:
        return "grateful"
    if record.focus >= FOCUS_MOOD_THRESHOLD_PERMILLE:
        return "focused"
    return "neutral"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _safe_rkey(did: str) -> str:
    """Convert a DID to a PDS-safe record key (rkey).

    AT Protocol rkey characters are restricted to ``[a-zA-Z0-9._~-]``.  DID
    strings contain ``:`` as a separator (e.g. ``did:plc:abc123`` or
    ``did:web:foo.com``), which is forbidden in rkeys.  This helper replaces
    every ``:`` with ``_``, producing a deterministic, reversible encoding.

    Examples:
        ``did:plc:abc123``   → ``did_plc_abc123``
        ``did:web:foo.com``  → ``did_web_foo.com``

    The transformation is deterministic: same DID always maps to the same rkey.
    Writing a joucho record for the same adherent on successive ticks uses the
    same rkey, so ``pds.put_record`` performs an **upsert** (overwrite) rather
    than appending a new record.  This is the intended behaviour: one joucho
    record per adherent, updated hourly.

    Args:
        did: An AT Protocol DID string (``did:method:specific``).

    Returns:
        rkey-safe string with ``:`` replaced by ``_``.
    """
    return did.replace(":", "_")


def _now_utc() -> datetime.datetime:
    """Return current UTC datetime (extracted for testability)."""
    return datetime.datetime.now(tz=datetime.timezone.utc)


def _build_joucho_record(
    adherent_did: str,
    signals: list[dict[str, Any]],
    *,
    window_days: int,
    now: datetime.datetime,
) -> JouchoRecord:
    """Build a JouchoRecord from raw kyumeiSignal dicts.

    Pure function used by joucho_aggregation_cell.
    """
    axes = aggregate_signals(signals)
    since_dt = now - datetime.timedelta(days=window_days)
    node_name = os.environ.get("ETZHAYYIM_NODE_NAME") or os.uname().nodename
    return JouchoRecord(
        adherentDid=adherent_did,
        joy=axes["joy"],
        calm=axes["calm"],
        stress=axes["stress"],
        gratitude=axes["gratitude"],
        focus=axes["focus"],
        computed_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        from_signal_count=len(signals),
        from_signals_since=since_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        aggregator_node=node_name,
        from_signal_days=window_days,
    )


# ── mst-projector helper ───────────────────────────────────────────────────────


async def _query_kyumei_signals(
    *,
    adherent_did: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Query kyumeiSignal records via mst-projector, falling back to mst.query.

    Args:
        adherent_did: If provided, query records for this DID only (single-adherent
                      path). If None, query the full collection (multi-adherent discovery).
        limit: Maximum records to return. Projector supports up to 10 000; mst.query
               falls back to 100 (cap enforced by PDS listRecords).

    Returns:
        list of raw record dicts (wire shape: {uri, cid, value}).
    """
    collection = "com.etzhayyim.shinka.kyumeiSignal"
    if _projector_mod is not None:
        try:
            if adherent_did is not None:
                result = await _projector_mod.query_by_did(
                    adherent_did, collection=collection, limit=limit,
                )
            else:
                result = await _projector_mod.query_by_collection(
                    collection, limit=limit,
                )
            return result.get("records", [])
        except Exception as e:
            _log.warning(
                "_query_kyumei_signals: mst-projector unreachable, falling back to "
                "client-side mst.query: %s", e,
            )
    # Fallback: client-side mst.query (100-record cap per call).
    if _mst_mod is None:
        return []
    records: list[dict[str, Any]] = await _mst_mod.query(
        collection,
        filter={"adherentDid": adherent_did} if adherent_did else None,
        limit=100,
    )
    return records


# ── Cell implementation ────────────────────────────────────────────────────────


async def joucho_aggregation_cell(
    adherent_did: str | None = None,
    *,
    window_days: int = JOUCHO_AGGREGATION_WINDOW_DAYS,
) -> list[JouchoRecord]:
    """JouchoAggregationCell — aggregate kyumeiSignal → joucho records.

    Placement: levi (port 13027). Cron 0 * * * * (hourly) + optional MST listener
    on com.etzhayyim.shinka.kyumeiSignal (Phase C, off in M5).

    Write path (per design doc):
      1. Query MST for com.etzhayyim.shinka.kyumeiSignal (last window_days days).
      2. Group by adherentDid → aggregate_signals() per adherent.
      3. Upsert com.etzhayyim.joucho.joucho record to MST via pds.put_record().
      4. Log result and latency.

    Error handling: missing kyumeiSignal → new-adherent defaults (from_signal_count=0).
    MST write failure → log and retry next cron. No alert cascade.

    Args:
        adherent_did: if None, aggregate for all adherents with recent activity.
                      Queries kyumeiSignal records and collects unique adherentDid
                      values as the target set.
                      If provided, aggregate for the named adherent only.
        window_days: kyumeiSignal lookback window in days (default 7).

    Returns:
        list[JouchoRecord] — one entry per adherent processed.

    Replaces vendor vertex_joucho write path (SELECT FROM vertex_joucho WHERE ...).
    Per JOUCHO-MIGRATION-DESIGN.md + ADR-2605215200 §4 successor roadmap.
    """
    if _mst_mod is None or _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not available — install etzhayyim-sdk-py to use "
            "joucho_aggregation_cell."
        )

    pds = _pds_mod

    now = _now_utc()
    written: list[JouchoRecord] = []

    if adherent_did is not None:
        # ── Single-adherent path ────────────────────────────────────────────
        target_dids: list[str] = [adherent_did]
    else:
        # ── Multi-adherent path ─────────────────────────────────────────────
        # Discover adherents who have recent kyumeiSignal activity by querying
        # the collection and collecting unique adherentDid values.
        try:
            all_signals: list[dict[str, Any]] = await _query_kyumei_signals(
                adherent_did=None, limit=10000,
            )
        except Exception:
            _log.exception(
                "joucho_aggregation_cell: failed to list kyumeiSignal records "
                "for adherent discovery; aborting tick"
            )
            return written

        seen: set[str] = set()
        for rec in all_signals:
            did_val: str = rec.get("value", {}).get("adherentDid", "")
            if did_val and did_val not in seen:
                seen.add(did_val)
        target_dids = list(seen)
        _log.info(
            "joucho_aggregation_cell: discovered %d adherents from kyumeiSignal",
            len(target_dids),
        )

    for did in target_dids:
        try:
            # a. Query kyumeiSignal records for this adherent.
            # mst.query returns {uri, cid, value} wrappers; extract "value" dicts
            # for aggregate_signals which expects flat {signalKind, weight, ...}.
            raw_records: list[dict[str, Any]] = await _query_kyumei_signals(
                adherent_did=did, limit=500,
            )
            signals: list[dict[str, Any]] = [r.get("value", r) for r in raw_records]

            # b. Aggregate → 5-axis permille dict (pure function).
            # Build JouchoRecord with all metadata.
            record = _build_joucho_record(did, signals, window_days=window_days, now=now)

            # c. Write to MST via pds.put_record (upsert — same rkey per adherent).
            rkey = _safe_rkey(did)
            await pds.put_record(
                "com.etzhayyim.joucho.joucho",
                {
                    "$type": "com.etzhayyim.joucho.joucho",
                    "adherentDid": record.adherentDid,
                    "joy": record.joy,
                    "calm": record.calm,
                    "stress": record.stress,
                    "gratitude": record.gratitude,
                    "focus": record.focus,
                    "computed_at": record.computed_at,
                    "from_signal_count": record.from_signal_count,
                    "from_signals_since": record.from_signals_since,
                    "aggregator_node": record.aggregator_node,
                    "from_signal_days": record.from_signal_days,
                },
                rkey=rkey,
            )
            _log.info(
                "joucho_aggregation_cell: wrote joucho for %s "
                "(signals=%d, mood=%s, rkey=%s)",
                did, len(signals), classify_mood(record), rkey,
            )
            written.append(record)

        except Exception:
            # One bad adherent must not kill the whole tick.
            _log.exception(
                "joucho_aggregation_cell: error processing adherent %s — skipping",
                did,
            )

    return written


async def fetch_joucho(adherent_did: str) -> JouchoRecord | None:
    """Read latest joucho record for an adherent from MST.

    Used by ShinkaHeartbeatCell and other mood-aware agents as a drop-in
    replacement for vendor:
      SELECT mood, joy, calm, stress, gratitude, focus
      FROM vertex_joucho WHERE owner_did = %s ORDER BY created_at DESC LIMIT 1

    Reads from com.etzhayyim.joucho.joucho via pds.get_record() using the
    deterministic rkey produced by _safe_rkey().

    Returns None if no record exists yet for the adherent (caller should apply
    new-adherent defaults from NEW_ADHERENT_DEFAULTS).

    Args:
        adherent_did: DID of the adherent to look up.

    Returns:
        JouchoRecord if found, None if the record doesn't exist (PDS 404).

    Per JOUCHO-MIGRATION-DESIGN.md + ADR-2605215200.
    """
    if _pds_mod is None or _PdsNotFoundError is None:
        raise ImportError(
            "etzhayyim_sdk not available — install etzhayyim-sdk-py to use "
            "fetch_joucho."
        )

    pds = _pds_mod
    rkey = _safe_rkey(adherent_did)
    uri = f"at://{adherent_did}/com.etzhayyim.joucho.joucho/{rkey}"

    try:
        raw = await pds.get_record(uri)
    except _PdsNotFoundError:
        _log.debug("fetch_joucho: no joucho record for %s (404)", adherent_did)
        return None

    value: dict[str, Any] = raw.get("value", {})
    return JouchoRecord(
        adherentDid=value.get("adherentDid", adherent_did),
        joy=int(value.get("joy", 0)),
        calm=int(value.get("calm", 0)),
        stress=int(value.get("stress", 0)),
        gratitude=int(value.get("gratitude", 0)),
        focus=int(value.get("focus", 0)),
        computed_at=value.get("computed_at", ""),
        from_signal_count=int(value.get("from_signal_count", 0)),
        from_signals_since=value.get("from_signals_since", ""),
        aggregator_node=value.get("aggregator_node", ""),
        from_signal_days=int(value.get("from_signal_days", 7)),
    )
