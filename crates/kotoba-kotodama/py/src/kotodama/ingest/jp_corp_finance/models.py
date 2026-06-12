from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .ids import ACTOR_DID


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


@dataclass(frozen=True)
class DisclosureRow:
    vertex_id: str
    jcn: str
    edinet_code: str
    company_name: str
    fiscal_year: int | None
    period_start: str
    period_end: str
    disclosure_kind: str
    statement_scope: str
    source_id: str
    source_record_id: str
    source_url: str
    artifact_uri: str
    source_published_at: str
    observed_at: str
    extraction_status: str
    confidence: float
    status: str = "active"
    actor_did: str = ACTOR_DID
    org_did: str = "anon"
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinancialFactRow:
    vertex_id: str
    disclosure_vid: str
    jcn: str
    edinet_code: str
    fiscal_year: int | None
    period_end: str
    statement_type: str
    concept: str
    label_ja: str
    value_jpy: float | None
    value_text: str
    unit: str
    source_location: str
    extraction_method: str
    confidence: float
    actor_did: str = ACTOR_DID
    org_did: str = "anon"
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
