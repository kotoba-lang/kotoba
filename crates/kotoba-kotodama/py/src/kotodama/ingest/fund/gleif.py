from __future__ import annotations

from typing import Any

from .ids import clean, slug


def legal_entity_did_from_lei(lei: Any) -> str:
    value = clean(lei).upper()
    if not value:
        return ""
    return f"at://did:web:legal-entity.etzhayyim.com/com.etzhayyim.apps.legalEntity.legalEntity/{slug(value)}"


def apply_gleif_enrichment(entity: dict[str, Any], gleif_payload: dict[str, Any]) -> dict[str, Any]:
    """Merge a GLEIF hit into a normalized fund entity without inventing facts."""
    lei = clean(gleif_payload.get("lei"))
    if not lei:
        return dict(entity)
    enriched = dict(entity)
    enriched["legal_entity_did"] = legal_entity_did_from_lei(lei)
    if gleif_payload.get("jurisdiction") and not enriched.get("jurisdiction"):
        enriched["jurisdiction"] = str(gleif_payload["jurisdiction"])
    if gleif_payload.get("country") and not enriched.get("domicile"):
        enriched["domicile"] = str(gleif_payload["country"])
    enriched["confidence"] = max(float(enriched.get("confidence") or 0.0), 0.8)
    return enriched
