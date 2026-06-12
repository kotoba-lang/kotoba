# Apache-2.0 + etzhayyim Charter Compliance Rider v2.0 (see /CHARTER-RIDER.md)
"""ownership edge → ``danjo.crossReferenceLink`` (the pure crossref core).

Per ADR-2605263800 §3 + ADR-2605301600 §3. This is the **pure, non-running
core** of ``danjo_crossref_engine``'s ownership-edge path: it turns a
``corp.ownershipEdge`` record (see ``ownership_edge_datom``) into a
``com.etzhayyim.danjo.crossReferenceLink`` record — a typed *factual*
edge between two LEI-identified entities, citing the public-record basis.

**This module does NOT run anything.** It is a deterministic library
function. Wiring it into a *continuous* ``danjo_crossref_engine`` cell,
and deriving any ``danjo.discrepancyObservation`` from these links, is
**R2-gated** (post-Bootstrap-Council ratify + 30-day public objection
per ADR-2605301600 §R-ladder) and is intentionally NOT done here. What is
in scope at R0/R1 is the substrate: the ``crossReferenceLink`` schema (an
R0 skeleton already in ``00-contracts/``) and its pure producer.

**Non-adjudicating (constitutional).** A ``crossReferenceLink`` asserts a
*factual relationship* the registry itself published (e.g. "owner LEI X is
the parent of subject LEI Y per GLEIF L2"), never wrongdoing. There is no
allegation, no named party as wrongdoer, no severity. danjo is the
censor's eye, no sword (ADR-2605301600).

``ownershipKind`` → ``linkType`` mapping (all five OwnershipKind values are
covered; ``entity-control-edge`` + ``entity-direct-shareholder-edge`` were
added to the ``crossReferenceLink`` Lexicon alongside this map). A kind with
no Lexicon ``linkType`` would be SKIPPED — we never invent a value outside
the Lexicon:

  - ``ubo``                  → ``entity-ubo-edge``
  - ``direct-shareholder``   → ``entity-direct-shareholder-edge``
  - ``parent-subsidiary``    → ``entity-parent-subsidiary-edge``
  - ``control-relationship`` → ``entity-control-edge``
  - ``officer``              → ``entity-officer-edge``

**Direction.** ``fromRef = owner`` (the controlling / parent / UBO
entity), ``toRef = subject`` (the controlled / child entity), so the link
reads "fromRef is the <kind> of toRef".

**Confidence.** GLEIF / registry relationship records are
``registry-asserted`` (the registrant asserted the edge), never the
``name-normalized-candidate`` fuzzy basis — both endpoints are exact LEIs.

**Provenance is caller-supplied** (``created_at`` / ``source_cell_did`` /
``attesting_did``) — pure transform, honest provenance, no platform-held
identity (substrate boundary).
"""

from __future__ import annotations

from typing import Iterable, Mapping

CROSSREF_LINK_NSID = "com.etzhayyim.danjo.crossReferenceLink"

# corp.ownershipEdge ownershipKind → crossReferenceLink linkType.
# Covers all five OwnershipKind values; each target is a Lexicon linkType
# knownValue (entity-control-edge + entity-direct-shareholder-edge were
# added to crossReferenceLink.json alongside this map). A kind with no
# mapped linkType would be skipped (we never invent a value outside the
# Lexicon).
_LINKTYPE_BY_KIND: dict[str, str] = {
    "ubo": "entity-ubo-edge",
    "direct-shareholder": "entity-direct-shareholder-edge",
    "parent-subsidiary": "entity-parent-subsidiary-edge",
    "control-relationship": "entity-control-edge",
    "officer": "entity-officer-edge",
}


def _endpoint(record: dict, lei_key: str, local_key: str) -> str | None:
    """Pick the LEI if present, else the local registry id, else None."""
    lei = str(record.get(lei_key, "")).strip()
    if lei:
        return lei
    local = str(record.get(local_key, "")).strip()
    return local or None


def ownership_edge_to_crossref_link(
    edge_record: dict,
    edge_record_cid: str,
    *,
    created_at: str,
    source_cell_did: str,
    attesting_did: str,
    lei_reference_cids: Mapping[str, str] | None = None,
) -> dict | None:
    """One ``corp.ownershipEdge`` record → one ``crossReferenceLink`` record.

    Returns ``None`` (skip) when the edge cannot ground a Lexicon-valid
    link: an ``ownershipKind`` with no mapped ``linkType``, or a missing
    endpoint, or a missing basis CID.

    ``lei_reference_cids`` optionally maps an endpoint LEI → its
    ``corp.leiReference`` record CID; when present those CIDs are added to
    ``basisRecordCids`` so the link cites the entity-resolution basis too.
    """
    kind = str(edge_record.get("ownershipKind", "")).strip()
    link_type = _LINKTYPE_BY_KIND.get(kind)
    if link_type is None:
        return None

    owner = _endpoint(edge_record, "ownerLei", "ownerLocalId")
    subject = _endpoint(edge_record, "subjectLei", "subjectLocalId")
    if owner is None or subject is None:
        return None

    edge_cid = str(edge_record_cid or "").strip()
    if not edge_cid:
        return None

    basis = [edge_cid]
    if lei_reference_cids:
        for ep in (owner, subject):
            cid = lei_reference_cids.get(ep)
            if cid and cid not in basis:
                basis.append(cid)

    link: dict[str, object] = {
        "createdAt": created_at,
        "linkType": link_type,
        "fromRef": owner,
        "toRef": subject,
        "basisRecordCids": basis,
        "confidence": "registry-asserted",
        "sourceCellDid": source_cell_did,
        "attestingDid": attesting_did,
    }
    juris = str(edge_record.get("subjectJurisdictionIso3", "")).strip()
    if juris:
        link["jurisdiction"] = juris[:8]

    missing = [
        f
        for f in (
            "createdAt",
            "linkType",
            "fromRef",
            "toRef",
            "sourceCellDid",
            "attestingDid",
        )
        if not str(link.get(f, "")).strip()
    ]
    if missing or not link["basisRecordCids"]:
        # Provenance incomplete — refuse to author a half-cited edge.
        return None
    return link


def ownership_edges_to_crossref_links(
    edges: Iterable[tuple[dict, str]],
    *,
    created_at: str,
    source_cell_did: str,
    attesting_did: str,
    lei_reference_cids: Mapping[str, str] | None = None,
) -> list[dict]:
    """Many ``(ownershipEdge record, its CID)`` → ``crossReferenceLink`` list.

    Unmappable / under-provenanced edges are skipped (never raised), so a
    single bad edge cannot halt a batch. Order follows input order.
    """
    out: list[dict] = []
    for edge_record, edge_cid in edges:
        link = ownership_edge_to_crossref_link(
            edge_record,
            edge_cid,
            created_at=created_at,
            source_cell_did=source_cell_did,
            attesting_did=attesting_did,
            lei_reference_cids=lei_reference_cids,
        )
        if link is not None:
            out.append(link)
    return out


__all__ = [
    "CROSSREF_LINK_NSID",
    "ownership_edge_to_crossref_link",
    "ownership_edges_to_crossref_links",
]
