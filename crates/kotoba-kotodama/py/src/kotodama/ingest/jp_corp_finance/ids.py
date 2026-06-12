from __future__ import annotations

import hashlib
import re

ACTOR_DID = "did:web:jp-corp-finance.etzhayyim.com"


def slug(value: object, *, max_len: int = 160) -> str:
    text = "" if value is None else str(value)
    out = re.sub(r"[^0-9A-Za-z]+", "-", text.strip().lower()).strip("-")
    return (out or "unknown")[:max_len]


def short_hash(*parts: object, size: int = 10) -> str:
    payload = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=size).hexdigest()


def disclosure_vid(source_id: str, source_record_id: str) -> str:
    return (
        f"at://{ACTOR_DID}/com.etzhayyim.apps.jpCorpFinance.disclosure/"
        f"{slug(source_id)}-{slug(source_record_id)}"
    )


def fact_vid(
    disclosure_vertex_id: str,
    statement_type: str,
    concept: str,
    source_location: str,
) -> str:
    digest = short_hash(disclosure_vertex_id, statement_type, concept, source_location, size=8)
    return f"at://{ACTOR_DID}/com.etzhayyim.apps.jpCorpFinance.financialFact/{digest}"


def coverage_vid(jcn: str) -> str:
    return f"at://{ACTOR_DID}/com.etzhayyim.apps.jpCorpFinance.coverage/jcn-{slug(jcn)}"
