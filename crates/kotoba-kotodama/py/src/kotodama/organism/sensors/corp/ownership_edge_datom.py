# Apache-2.0 + etzhayyim Charter Compliance Rider v2.0 (see /CHARTER-RIDER.md)
"""Transform ``CorpOwnershipObservation`` → ``corp.ownershipEdge`` datoms.

Per ADR-2605263800 §3 + ADR-2605312345 (kotoba Datom log = first-class
canonical state). This is the bridge from a *typed sensor observation*
(what ``GleifL2OwnershipSensor`` and the other ``CorpOwnershipSensor``
sources yield) to the *canonical-state* form that danjo
(ADR-2605301600) and kanae (ADR-2605302300) read: the
``com.etzhayyim.corp.ownershipEdge`` record, materialized as kotoba EAVT
datoms.

Two output shapes are produced, both pure / deterministic:

1. ``observation_to_edge_record`` — the AT-Protocol record exactly
   matching the ``com.etzhayyim.corp.ownershipEdge`` Lexicon (the wire
   contract). STRICT: raises ``ValueError`` if a required Lexicon field
   would be empty (authoring discipline).

2. ``observations_to_kotoba_batch`` — the house-style kotoba ingest
   envelope ``{"entities": [{"id", "type", "labelEn", "claims": [...]}]}``
   where each claim is ``{"pred": "ownership/<camelField>", "value": str}``
   (the same shape giemon's ``sbom_gen.to_kotoba_entities`` emits). G7
   discipline: observations missing a required field are SKIPPED, not
   raised, so a bad row never halts a batch.

**Provenance is caller-supplied, never invented.** ``created_at`` (tx
time), ``dataset_pin_at`` (the ``com.etzhayyim.substrate.datasetPin``
AT-URI the bytes were resolved from) and ``attesting_did`` (the
community-operator DID authoring the claim) are required arguments —
this keeps the transform pure (no clock / no ambient identity) and
testable, and records honest provenance per the substrate boundary.

**pctHeld units.** ``CorpOwnershipObservation.pct_held`` is a percentage
in ``[0, 100]``; the Lexicon stores integer **basis points** ``[0,
10000]`` (10000 = 100%). ``_pct_to_basis_points`` converts and clamps;
``parent-subsidiary`` / ``control-relationship`` / ``officer`` edges
normally carry no percentage → ``None`` (field omitted).

**Non-adjudicating.** These datoms are observed public-disclosure edges,
nothing more. No field asserts wrongdoing or "uncovers" a hidden owner
(danjo/kanae are the censor's eye, no sword). Source data is
public-disclosure only (GLEIF CC0 etc.); no commercial-vendor data
(Charter Rider §2(e)), no covert surveillance (§2(c)).
"""

from __future__ import annotations

from typing import Iterable

from .base import CorpOwnershipObservation

OWNERSHIP_EDGE_NSID = "com.etzhayyim.corp.ownershipEdge"

# kotoba entity type (PascalCase, house style) + claim attribute namespace.
KOTOBA_ENTITY_TYPE = "CorpOwnershipEdge"
_PRED_NS = "ownership"

# Lexicon-required fields (com.etzhayyim.corp.ownershipEdge §record.required)
# that this transform is responsible for populating from the observation +
# caller-supplied provenance. Used by both the strict record builder and the
# G7-skipping batch builder.
_REQUIRED_NONEMPTY = (
    "createdAt",
    "subjectJurisdictionIso3",
    "ownershipKind",
    "sourceId",
    "datasetPinAt",
    "tier",
    "license",
    "attestingDid",
)


def _pct_to_basis_points(pct: float | None) -> int | None:
    """Percentage [0,100] → integer basis points [0,10000] (10000 = 100%).

    Returns ``None`` when there is no percentage (control-edge / officer).
    Out-of-range inputs are clamped to the valid band rather than dropped,
    so a slightly-over-100 rounding artifact upstream still yields a
    Lexicon-valid value.
    """
    if pct is None:
        return None
    bp = round(float(pct) * 100.0)
    if bp < 0:
        return 0
    if bp > 10000:
        return 10000
    return bp


def observation_to_edge_record(
    obs: CorpOwnershipObservation,
    *,
    created_at: str,
    dataset_pin_at: str,
    attesting_did: str,
) -> dict:
    """Build the ``com.etzhayyim.corp.ownershipEdge`` record (Lexicon shape).

    STRICT: raises ``ValueError`` listing any required Lexicon field that
    would be empty. Optional fields (LEIs, local ids, owner jurisdiction,
    pctHeld, asOf) are included only when present.
    """
    record: dict[str, object] = {
        "createdAt": created_at,
        "subjectJurisdictionIso3": obs.subject_jurisdiction_iso3,
        "ownershipKind": obs.ownership_kind,
        "sourceId": _source_id_of(obs),
        "datasetPinAt": dataset_pin_at,
        "tier": obs.tier,
        "license": obs.license_tag,
        "attestingDid": attesting_did,
    }
    # Optional identity / edge fields.
    if obs.subject_lei:
        record["subjectLei"] = obs.subject_lei
    if obs.subject_local_id:
        record["subjectLocalId"] = obs.subject_local_id
    if obs.owner_lei:
        record["ownerLei"] = obs.owner_lei
    if obs.owner_local_id:
        record["ownerLocalId"] = obs.owner_local_id
    if obs.owner_jurisdiction_iso3:
        record["ownerJurisdictionIso3"] = obs.owner_jurisdiction_iso3
    bp = _pct_to_basis_points(obs.pct_held)
    if bp is not None:
        record["pctHeld"] = bp
    if obs.as_of:
        record["asOf"] = obs.as_of

    missing = [
        f for f in _REQUIRED_NONEMPTY if not str(record.get(f, "")).strip()
    ]
    if missing:
        raise ValueError(
            f"{OWNERSHIP_EDGE_NSID}: missing required field(s): "
            + ", ".join(missing)
        )
    return record


def edge_record_id(record: dict) -> str:
    """Deterministic, content-stable entity id for a kotoba edge entity.

    Same observed edge (source × endpoints × kind × asOf) → same id, so
    re-ingesting an unchanged snapshot does not fork the entity. ``asOf``
    is part of the key so a later-dated re-observation of the same pair
    is a distinct edge fact (history is preserved on the canonical log).
    """
    subj = record.get("subjectLei") or record.get("subjectLocalId") or "?"
    owner = record.get("ownerLei") or record.get("ownerLocalId") or "?"
    as_of = record.get("asOf") or "current"
    return (
        f"{OWNERSHIP_EDGE_NSID}:{record['sourceId']}:"
        f"{subj}:{owner}:{record['ownershipKind']}:{as_of}"
    )


def _record_to_kotoba_entity(record: dict) -> dict:
    """Wrap a Lexicon record as a house-style kotoba ingest entity.

    Each property becomes an ``{"pred": "ownership/<field>", "value": str}``
    claim (mirrors giemon ``to_kotoba_entities``). Values are stringified;
    field names are the Lexicon camelCase names verbatim.
    """
    claims = [
        {"pred": f"{_PRED_NS}/{field}", "value": str(value)}
        for field, value in record.items()
    ]
    subj = record.get("subjectLei") or record.get("subjectLocalId") or "?"
    owner = record.get("ownerLei") or record.get("ownerLocalId") or "?"
    return {
        "id": edge_record_id(record),
        "type": KOTOBA_ENTITY_TYPE,
        "labelEn": f"{record['ownershipKind']} {subj[:7]}→{owner[:7]}",
        "claims": claims,
    }


def observation_to_kotoba_entity(
    obs: CorpOwnershipObservation,
    *,
    created_at: str,
    dataset_pin_at: str,
    attesting_did: str,
) -> dict:
    """Single observation → one kotoba ingest entity. STRICT (raises)."""
    record = observation_to_edge_record(
        obs,
        created_at=created_at,
        dataset_pin_at=dataset_pin_at,
        attesting_did=attesting_did,
    )
    return _record_to_kotoba_entity(record)


def observations_to_kotoba_batch(
    observations: Iterable[CorpOwnershipObservation],
    *,
    created_at: str,
    dataset_pin_at: str,
    attesting_did: str,
) -> dict:
    """Many observations → ``{"entities": [...]}`` kotoba ingest batch.

    G7 discipline: an observation that cannot author a valid edge record
    (missing required field) is SKIPPED rather than raising, so one bad
    row never halts a batch. Entity order follows input order; duplicate
    ids (same observed edge seen twice in a snapshot) are de-duplicated,
    keeping the first occurrence.
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


def _source_id_of(obs: CorpOwnershipObservation) -> str:
    """Resolve the Lexicon ``sourceId`` for an observation.

    ``CorpOwnershipObservation`` does not carry ``source_id`` itself; the
    sensor's ``source_id`` is the authority. We derive it from the
    observation's ``sensor`` field (the subdataset name, e.g.
    ``corp/ownership/gleif-l2``) so the transform stays decoupled from any
    single sensor class. Unknown layouts fall back to the trailing path
    segment.
    """
    sensor = (obs.sensor or "").strip()
    # Map the known subdataset names to their Lexicon sourceId knownValue.
    if sensor.endswith("gleif-l2"):
        return "gleif-l2"
    if sensor.endswith("opencorporates-opendata"):
        return "opencorporates-opendata"
    if sensor.endswith("us-fincen-boi"):
        return "us-fincen-boi"
    # eu-ubo-* subdatasets keep their trailing segment verbatim.
    tail = sensor.rsplit("/", 1)[-1] if "/" in sensor else sensor
    return tail or "gleif-l2"


__all__ = [
    "OWNERSHIP_EDGE_NSID",
    "KOTOBA_ENTITY_TYPE",
    "observation_to_edge_record",
    "observation_to_kotoba_entity",
    "observations_to_kotoba_batch",
    "edge_record_id",
]
