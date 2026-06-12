"""Wikidata SPARQL row → com.etzhayyim.maps.ownership bulk ingest (Python).

Python analog of TS
``60-apps/etzhayyim-project-maps/rw-free/src/registry/wikidata-ingest.ts``.

Used by the maps bulk-ingest pods (currently aismarine_wikidata_lei.py)
to write vessel ↔ legal-entity ownership / operator edges via the PDS
substrate instead of legacy psycopg2 → RisingWave INSERTs.

Each Wikidata triple (vessel IMO, owner LegalEntity, role) becomes one
``com.etzhayyim.maps.ownership`` record:

  - subjectUri = AT URI of the LegalEntity feature (owner / operator)
  - objectUri  = AT URI of the Vessel feature (typically created via
                 `registerFeature(label="Vessel" /* extension */, ...)`)
  - relation   = "OwnsProperty" (owners) | "Operates" (operators)
  - sourceDid  = did:web:maps.etzhayyim.com:registry:wikidata
  - effectiveDate = capture timestamp (or wd:P571 inception when available)

Per ADR-2605231400 + ADR-2605241500 (DataLad+IPFS dataset substrate +
Phase 3 Tier B ingest).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable, Optional

from . import Etzhayyim, WriteOpts


log = logging.getLogger(__name__)


WIKIDATA_SOURCE_DID = "did:web:maps.etzhayyim.com:registry:wikidata"
OWNERSHIP_COLLECTION = "com.etzhayyim.maps.ownership"

# Mirrors the TS-side OWNERSHIP_RELATIONS — extended per ADR-2605231400
# Phase 3 Tier B closure to include Operates + Manages (vessel operator
# edges from aismarine_wikidata_lei.py wd:P137).
KNOWN_RELATIONS = frozenset(
    [
        "OwnsProperty",
        "TransferredTo",
        "InheritedBy",
        "ForeclosedBy",
        "LeasedTo",
        "Operates",
        "Manages",
    ]
)


_QID_RE = re.compile(r"^https?://www\.wikidata\.org/entity/(Q\d+)$")


def qid_from_entity_uri(uri: Optional[str]) -> Optional[str]:
    """Wikidata entity URI → Q-number (e.g., ``Q486156``)."""
    if not uri:
        return None
    m = _QID_RE.match(uri)
    return m.group(1) if m else None


def _val(b: dict, key: str) -> Optional[str]:
    cell = b.get(key)
    if not cell:
        return None
    v = cell.get("value")
    return v if isinstance(v, str) and v else None


# ─── converter (pure) ───────────────────────────────────────────────


@dataclass
class OwnershipConverterOptions:
    source_did: str = WIKIDATA_SOURCE_DID
    """Override the provenance DID."""

    legal_entity_uri_for_lei: Optional[Callable[[str], str]] = None
    """Function `(lei) → at://...legalEntity/{rkey}`. Caller-supplied so
    the converter doesn't hardcode rkey scheme. Default constructs
    `at://did:web:maps.etzhayyim.com/com.etzhayyim.maps.legalEntity/corporation-{lei_lc}`."""

    legal_entity_uri_for_qid: Optional[Callable[[str], str]] = None
    """Fallback when no LEI: build URI from Wikidata QID."""

    vessel_uri_for_imo: Optional[Callable[[int], str]] = None
    """Function `(imo) → at://...feature/{rkey}` for the Vessel feature."""

    effective_date: Optional[str] = None
    """ISO timestamp for `effectiveDate`. Default `datetime.now(UTC).isoformat()`."""


def _default_legal_entity_uri_for_lei(lei: str) -> str:
    safe = lei.lower()
    return f"at://did:web:maps.etzhayyim.com/com.etzhayyim.maps.legalEntity/corporation-{safe}"


def _default_legal_entity_uri_for_qid(qid: str) -> str:
    safe = qid.lower()
    return f"at://did:web:maps.etzhayyim.com/com.etzhayyim.maps.legalEntity/corporation-wd-{safe}"


def _default_vessel_uri_for_imo(imo: int) -> str:
    return f"at://did:web:maps.etzhayyim.com/com.etzhayyim.maps.feature/vessel-imo-{imo}"


@dataclass
class ConvertedOwnership:
    """One ownership record + the synthetic IDs we used to build it."""
    record: dict
    imo: int
    lei: Optional[str]
    qid: Optional[str]


def wikidata_row_to_ownership(
    binding: dict,
    *,
    imo_key: str = "imo",
    entity_lei_key: str,
    entity_label_key: str,
    entity_uri_key: str,
    relation: str,
    opts: Optional[OwnershipConverterOptions] = None,
) -> Optional[ConvertedOwnership]:
    """Pure Wikidata SPARQL binding → ownership record.

    `entity_lei_key` / `entity_label_key` / `entity_uri_key` vary by query
    (owner_* vs operator_*). Caller picks the right set when iterating
    over QUERY_OWNERS vs QUERY_OPERATORS results.

    Returns None when the binding lacks both LEI and QID, or has no IMO.
    """
    if relation not in KNOWN_RELATIONS:
        raise ValueError(f"relation {relation!r} not in KNOWN_RELATIONS")
    opts = opts or OwnershipConverterOptions()

    imo_raw = _val(binding, imo_key)
    if not imo_raw:
        return None
    imo_clean = imo_raw.strip().upper().removeprefix("IMO").strip()
    try:
        imo = int(imo_clean)
    except (TypeError, ValueError):
        return None
    if imo <= 0:
        return None

    lei = _val(binding, entity_lei_key)
    qid = qid_from_entity_uri(_val(binding, entity_uri_key))
    if not lei and not qid:
        return None

    entity_uri_fn = opts.legal_entity_uri_for_lei or _default_legal_entity_uri_for_lei
    qid_fn = opts.legal_entity_uri_for_qid or _default_legal_entity_uri_for_qid
    vessel_uri_fn = opts.vessel_uri_for_imo or _default_vessel_uri_for_imo

    subject_uri = entity_uri_fn(lei) if lei else qid_fn(qid)  # type: ignore[arg-type]
    object_uri = vessel_uri_fn(imo)

    effective_date = opts.effective_date or datetime.now(tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    label = _val(binding, entity_label_key) or ""
    registry_ref_parts = [p for p in [qid, label, lei] if p]
    registry_ref = "|".join(registry_ref_parts)[:256] or None

    record = {
        "v": 1,
        "subjectUri": subject_uri,
        "objectUri": object_uri,
        "relation": relation,
        "effectiveDate": effective_date,
        "sourceDid": opts.source_did,
    }
    if registry_ref:
        record["registryRef"] = registry_ref

    return ConvertedOwnership(record=record, imo=imo, lei=lei, qid=qid)


# ─── bulk ingest ────────────────────────────────────────────────────


@dataclass
class BulkOwnershipStats:
    total_rows: int = 0
    skipped_no_imo: int = 0
    skipped_no_lei_or_qid: int = 0
    attempted: int = 0
    ok: int = 0
    failed: int = 0
    failures: list[dict] = field(default_factory=list)


async def ingest_ownership_from_wikidata(
    bindings: Iterable[dict],
    *,
    client: Etzhayyim,
    entity_lei_key: str,
    entity_label_key: str,
    entity_uri_key: str,
    relation: str,
    imo_key: str = "imo",
    converter_opts: Optional[OwnershipConverterOptions] = None,
    fail_fast_after: Optional[int] = None,
) -> BulkOwnershipStats:
    """Bulk write Wikidata owner/operator triples as ownership records.

    Skips rows missing IMO or any LegalEntity identifier (matches the
    legacy aismarine_wikidata_lei.py filters). Returns per-stage skip /
    ok / failed counts.
    """
    stats = BulkOwnershipStats()
    for b in bindings:
        stats.total_rows += 1
        conv = wikidata_row_to_ownership(
            b,
            imo_key=imo_key,
            entity_lei_key=entity_lei_key,
            entity_label_key=entity_label_key,
            entity_uri_key=entity_uri_key,
            relation=relation,
            opts=converter_opts,
        )
        if conv is None:
            # Detailed skip diagnostics so we can tell IMO-missing apart
            # from no-identifier-missing.
            if not _val(b, imo_key):
                stats.skipped_no_imo += 1
            else:
                stats.skipped_no_lei_or_qid += 1
            continue
        stats.attempted += 1
        try:
            await client.write(
                WriteOpts(collection=OWNERSHIP_COLLECTION, record=conv.record)
            )
            stats.ok += 1
        except Exception as caught:  # noqa: BLE001
            stats.failed += 1
            stats.failures.append(
                {
                    "imo": conv.imo,
                    "lei": conv.lei,
                    "qid": conv.qid,
                    "relation": relation,
                    "error": str(caught),
                }
            )
            if fail_fast_after is not None and stats.failed >= fail_fast_after:
                break
    return stats


__all__ = [
    "BulkOwnershipStats",
    "ConvertedOwnership",
    "KNOWN_RELATIONS",
    "OWNERSHIP_COLLECTION",
    "OwnershipConverterOptions",
    "WIKIDATA_SOURCE_DID",
    "ingest_ownership_from_wikidata",
    "qid_from_entity_uri",
    "wikidata_row_to_ownership",
]
