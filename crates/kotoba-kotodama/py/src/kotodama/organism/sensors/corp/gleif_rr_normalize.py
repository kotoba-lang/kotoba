# Apache-2.0 + etzhayyim Charter Compliance Rider v2.0 (see /CHARTER-RIDER.md)
"""Normalize GLEIF Level-2 Relationship-Record (RR) golden-copy → sensor rows.

Per ADR-2605263800 §3. This is the pure normalizer half of the W1
``gleif_rr`` fetcher referenced by ``gleif_l2_ownership_sensor``: it maps a
GLEIF RR-CDF record (as published in the GLEIF Relationship-Record
golden-copy, CC0 1.0) into the NDJSON row shape that
``GleifL2OwnershipSensor`` consumes.

**Deliberately network-free.** Downloading the golden-copy bytes is an
operator action (``e7m-dataset add`` / DataLad / curl of the published
GLEIF concatenated file), kept OUT of this module so the
passive-only + no-active-probe invariants hold (this file lives under
``organism/sensors/`` which the ``sensor-no-active-probe`` lint scans).
This module only *parses* records already in hand. That keeps it pure and
fully unit-testable on fixtures, with no live GLEIF endpoint at any tick.

GLEIF RR-CDF record shape (the fields we read)::

    {
      "Relationship": {
        "StartNode": {"NodeID": "<LEI>", "NodeIDType": "LEI"},
        "EndNode":   {"NodeID": "<LEI>", "NodeIDType": "LEI"},
        "RelationshipType": "IS_DIRECTLY_CONSOLIDATED_BY",
        "RelationshipStatus": "ACTIVE",
        "RelationshipQuantifiers": [
          {"QuantifierAmount": "75.5", "MeasurementMethod": "..."}
        ]
      },
      "Registration": {"RegistrationStatus": "PUBLISHED",
                       "LastUpdateDate": "2025-04-01T00:00:00Z"}
    }

Direction (GLEIF semantics): for the consolidation relationship types,
``StartNode`` is the consolidated *child* and ``EndNode`` is the
consolidating *parent*. We therefore emit ``subjectLei = StartNode`` and
``ownerLei = EndNode``, matching the sensor's
``subject = child / owner = parent`` convention.

Output row keys are exactly what ``GleifL2OwnershipSensor`` expects:
``subjectLei``, ``ownerLei``, ``relationshipType``, ``relationshipStatus``,
and (optionally) ``pctHeld`` / ``asOf``. Subject/owner jurisdiction is NOT
present in RR records (it lives in the L1 entity file); the fetcher may
join it later, and the sensor tolerates its absence.

Vendor commercial-terminal data is CONSTITUTIONALLY PROHIBITED (Charter
Rider §2(e)+§2(c)); GLEIF RR is CC0 1.0 public-domain.
"""

from __future__ import annotations

from typing import Iterable, Iterator


def _lei(node: object) -> str | None:
    """Extract a 20-char LEI from a GLEIF {NodeID, NodeIDType} node."""
    if not isinstance(node, dict):
        return None
    if str(node.get("NodeIDType", "LEI")).strip().upper() != "LEI":
        return None
    lei = str(node.get("NodeID", "")).strip()
    return lei if len(lei) == 20 else None


def _pct_from_quantifiers(rel: dict) -> float | None:
    """First numeric ``QuantifierAmount`` (a percentage), if any.

    GLEIF RR consolidation edges usually carry no quantifier; ownership
    registers sometimes do. Non-numeric / out-of-[0,100] amounts are
    ignored (the downstream datom transform clamps, but here we only
    surface a clean percentage).
    """
    quantifiers = rel.get("RelationshipQuantifiers")
    if not isinstance(quantifiers, list):
        return None
    for q in quantifiers:
        if not isinstance(q, dict):
            continue
        raw = q.get("QuantifierAmount")
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if 0.0 <= val <= 100.0:
            return val
    return None


def normalize_gleif_rr_record(record: object) -> dict | None:
    """One GLEIF RR-CDF record → one sensor NDJSON row, or ``None`` to skip.

    Skips (returns ``None``) when the record is not a well-formed
    LEI↔LEI relationship: missing ``Relationship``, non-LEI / malformed
    endpoints, or no ``RelationshipType``. Status/quantifier/asOf are
    pass-through best-effort.
    """
    if not isinstance(record, dict):
        return None
    rel = record.get("Relationship")
    if not isinstance(rel, dict):
        return None

    subject_lei = _lei(rel.get("StartNode"))
    owner_lei = _lei(rel.get("EndNode"))
    if subject_lei is None or owner_lei is None:
        return None

    rel_type = str(rel.get("RelationshipType", "")).strip()
    if not rel_type:
        return None

    row: dict[str, object] = {
        "subjectLei": subject_lei,
        "ownerLei": owner_lei,
        "relationshipType": rel_type,
    }

    status = str(rel.get("RelationshipStatus", "")).strip()
    if status:
        row["relationshipStatus"] = status.upper()

    pct = _pct_from_quantifiers(rel)
    if pct is not None:
        row["pctHeld"] = pct

    reg = record.get("Registration")
    if isinstance(reg, dict):
        as_of = str(reg.get("LastUpdateDate", "")).strip()
        if as_of:
            row["asOf"] = as_of

    return row


def gleif_rr_records_to_rows(records: Iterable[object]) -> Iterator[dict]:
    """Stream GLEIF RR records → sensor rows, skipping malformed ones (G7)."""
    for record in records:
        row = normalize_gleif_rr_record(record)
        if row is not None:
            yield row


def gleif_rr_records_to_ndjson(records: Iterable[object]) -> str:
    """Render GLEIF RR records as the NDJSON shard the sensor reads.

    One JSON object per line; trailing newline. ``ensure_ascii=False`` to
    preserve any non-ASCII content faithfully (LEIs are ASCII, but keep
    the same convention as the test fixtures).
    """
    import json

    lines = [
        json.dumps(row, ensure_ascii=False)
        for row in gleif_rr_records_to_rows(records)
    ]
    return ("\n".join(lines) + "\n") if lines else ""


__all__ = [
    "normalize_gleif_rr_record",
    "gleif_rr_records_to_rows",
    "gleif_rr_records_to_ndjson",
]
