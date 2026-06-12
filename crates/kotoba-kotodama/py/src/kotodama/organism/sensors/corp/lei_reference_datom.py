# Apache-2.0 + etzhayyim Charter Compliance Rider v2.0 (see /CHARTER-RIDER.md)
"""Transform ``LeiObservation`` → ``corp.leiReference`` datoms.

Per ADR-2605263800 §3 + ADR-2605312345. The entity-resolution sibling of
``ownership_edge_datom``: turns a ``LeiObservation`` (what ``GleifLeiSensor``
yields) into the ``com.etzhayyim.corp.leiReference`` record, materialized as
kotoba EAVT datoms.

``corp.leiReference`` is the **canonical cross-jurisdiction entity node** —
the LEI resolves to a legal name + incorporation jurisdiction + registration
status (+ GLEIF L2 direct/ultimate parent pointers when published). danjo
(ADR-2605301600) and kanae (ADR-2605302300) read ``corp.{leiReference,
ownershipEdge}`` together: ownershipEdge supplies the control edges, and
leiReference resolves each edge endpoint LEI to an entity. The CID of a
leiReference record is exactly what ``ownership_crossref``'s
``lei_reference_cids`` basis map cites.

Two output shapes, both pure / deterministic (mirrors ``ownership_edge_datom``):

1. ``observation_to_lei_record`` — the AT-Protocol record matching the
   ``com.etzhayyim.corp.leiReference`` Lexicon. STRICT: raises ``ValueError``
   if a required field would be empty.
2. ``observation_to_kotoba_entity`` / ``observations_to_kotoba_batch`` — the
   house-style kotoba ingest envelope ``{"entities": [{"id","type","labelEn",
   "claims":[{"pred":"lei/<camelField>","value":str}]}]}``.

**Entity id is the LEI itself** (``com.etzhayyim.corp.leiReference:<LEI>``):
the LEI is the canonical unique key, so re-ingesting an updated golden-copy
appends new facts (legalName / status changes) onto the same entity rather
than forking it — the append-only log preserves the history.

**Provenance is caller-supplied** (``created_at`` / ``dataset_pin_at`` /
``attesting_did``) — pure transform, honest provenance, no platform-held
identity (substrate boundary).

**Non-adjudicating.** A leiReference is a published registry fact (LEI X is
"Sony Group Corporation", JPN, ISSUED), nothing more. GLEIF is CC0 1.0
public-domain; no commercial-vendor data (Charter Rider §2(e)); no covert
surveillance (§2(c)).
"""

from __future__ import annotations

from typing import Iterable

from .base import LeiObservation

LEI_REFERENCE_NSID = "com.etzhayyim.corp.leiReference"

KOTOBA_ENTITY_TYPE = "CorpLeiReference"
_PRED_NS = "lei"

# com.etzhayyim.corp.leiReference §record.required.
_REQUIRED_NONEMPTY = (
    "createdAt",
    "entityLei",
    "legalName",
    "jurisdictionIso3",
    "registrationStatus",
    "datasetPinAt",
    "tier",
    "license",
    "attestingDid",
)


def observation_to_lei_record(
    obs: LeiObservation,
    *,
    created_at: str,
    dataset_pin_at: str,
    attesting_did: str,
) -> dict:
    """Build the ``com.etzhayyim.corp.leiReference`` record (Lexicon shape).

    STRICT: raises ``ValueError`` listing any required field that would be
    empty. Optional parent pointers are included only when published.
    """
    record: dict[str, object] = {
        "createdAt": created_at,
        "entityLei": obs.entity_lei,
        "legalName": obs.legal_name,
        "jurisdictionIso3": obs.jurisdiction_iso3,
        "registrationStatus": obs.registration_status,
        "datasetPinAt": dataset_pin_at,
        "tier": obs.tier,
        "license": obs.license_tag,
        "attestingDid": attesting_did,
    }
    if obs.parent_lei:
        record["parentLei"] = obs.parent_lei
    if obs.ultimate_parent_lei:
        record["ultimateParentLei"] = obs.ultimate_parent_lei

    missing = [
        f for f in _REQUIRED_NONEMPTY if not str(record.get(f, "")).strip()
    ]
    if missing:
        raise ValueError(
            f"{LEI_REFERENCE_NSID}: missing required field(s): "
            + ", ".join(missing)
        )
    return record


def lei_record_id(record: dict) -> str:
    """Deterministic entity id — the LEI is the canonical unique key."""
    return f"{LEI_REFERENCE_NSID}:{record['entityLei']}"


def _record_to_kotoba_entity(record: dict) -> dict:
    claims = [
        {"pred": f"{_PRED_NS}/{field}", "value": str(value)}
        for field, value in record.items()
    ]
    return {
        "id": lei_record_id(record),
        "type": KOTOBA_ENTITY_TYPE,
        "labelEn": f"{record['entityLei']} {str(record['legalName'])[:48]}",
        "claims": claims,
    }


def observation_to_kotoba_entity(
    obs: LeiObservation,
    *,
    created_at: str,
    dataset_pin_at: str,
    attesting_did: str,
) -> dict:
    """Single observation → one kotoba ingest entity. STRICT (raises)."""
    record = observation_to_lei_record(
        obs,
        created_at=created_at,
        dataset_pin_at=dataset_pin_at,
        attesting_did=attesting_did,
    )
    return _record_to_kotoba_entity(record)


def observations_to_kotoba_batch(
    observations: Iterable[LeiObservation],
    *,
    created_at: str,
    dataset_pin_at: str,
    attesting_did: str,
) -> dict:
    """Many observations → ``{"entities": [...]}`` kotoba ingest batch.

    G7 discipline: an observation that cannot author a valid record
    (missing required field) is SKIPPED rather than raising. Duplicate LEIs
    in one batch are de-duplicated, keeping the first occurrence (the LEI is
    the entity key; later golden-copy snapshots append new facts instead).
    """
    entities: list[dict] = []
    seen: set[str] = set()
    for obs in observations:
        try:
            entity = observation_to_kotoba_entity(
                obs,
                created_at=created_at,
                dataset_pin_at=dataset_pin_at,
                attesting_did=attesting_did,
            )
        except ValueError:
            continue
        if entity["id"] in seen:
            continue
        seen.add(entity["id"])
        entities.append(entity)
    return {"entities": entities}


__all__ = [
    "LEI_REFERENCE_NSID",
    "KOTOBA_ENTITY_TYPE",
    "observation_to_lei_record",
    "observation_to_kotoba_entity",
    "observations_to_kotoba_batch",
    "lei_record_id",
]
