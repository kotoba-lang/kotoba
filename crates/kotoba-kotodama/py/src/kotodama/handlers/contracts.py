"""
ADR-0049 contracts pilot — contracts.etzhayyim.com on shared Python UDF pool.

Projects the existing `vertex_legal_entity` (123.5M rows, ingested by
`legal-entity.etzhayyim.com`) into a DID-addressed view under
`social-contract.etzhayyim.com:entity:*` per the 3-layer DID pattern in
`60-apps/etzhayyim-project-social-contract/CLAUDE.md`.

Phase 1 surface:
- `com.etzhayyim.apps.contracts.mintOrganizationDid`      (procedure, DB-only)
- `com.etzhayyim.apps.contracts.projectFromLegalEntity`    (procedure, batch / per-row)
- `com.etzhayyim.apps.contracts.ingestSocialContract`      (procedure, fresh HTTP crawl)
- `com.etzhayyim.apps.contracts.resolveOrganization`       (query)

Law full-text corpus (statute / article / treaty full-text) is scope of
the `houbun.etzhayyim.com` actor, not this handler — see ADR-0052.

Write path: Hyperdrive-direct (ADR-0036). The UDF pod sits inside the
same Vultr VKE cluster as RisingWave (ADR-0048) so we talk to the RW
postgres wire on :4566 via asyncpg rather than the CF Hyperdrive hop.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from kotodama import udf
from kotodama.context import Context

ACTOR_NAME = "contracts"
ACTOR_DID = f"did:web:{ACTOR_NAME}.etzhayyim.com"
SC_DID_PREFIX = "did:web:social-contract.etzhayyim.com:entity"

# ---------------------------------------------------------------------------
# DID mint — deterministic BLAKE3-12 (ADR-0019 + social-contract CLAUDE.md)
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")
# Collapse anything that is not a Unicode "word character" to '-'. In
# Python `\w` (Unicode mode, default) covers `[A-Za-z0-9_]` plus every
# non-ASCII letter / digit — CJK ideographs, hiragana, katakana, Hangul,
# Cyrillic, etc. Stripping to ASCII would hash JP / ZH / KR legal names
# to empty, collapsing their DID onto country+national_id alone.
_NON_ALNUM = re.compile(r"[\W_]+", re.UNICODE)


def _normalize_name(name: str | None) -> str:
    """Strip legal suffixes and whitespace for stable hashing."""
    if not name:
        return ""
    s = name.strip().lower()
    for suffix in (
        " inc.",
        " inc",
        " ltd.",
        " ltd",
        " llc",
        " l.l.c.",
        " corp.",
        " corp",
        " corporation",
        " k.k.",
        " 株式会社",
        " 合同会社",
    ):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    s = _WS.sub(" ", s).strip()
    return _NON_ALNUM.sub("-", s).strip("-")


def _entity_hash(country: str, national_id: str, name: str, incorporated: str) -> str:
    """
    12-char hex BLAKE3 prefix. We use hashlib.blake2b with digest_size=6
    (12 hex chars) as a portable stand-in — the value is used only as a
    deterministic identifier, not a cryptographic commitment.
    """
    payload = "|".join((country or "", national_id or "", name or "", incorporated or ""))
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=6).hexdigest()


def _mint_did(country_alpha3: str, national_id: str, name: str, incorporated: str) -> str:
    alpha3 = (country_alpha3 or "").lower()[:3] or "unk"
    h = _entity_hash(alpha3, national_id or "", _normalize_name(name), incorporated or "")
    return f"{SC_DID_PREFIX}:{alpha3}:{h}"


# ---------------------------------------------------------------------------
# Projection insert — vertex_contracts_organization (ADR-0036, Hyperdrive direct)
# ---------------------------------------------------------------------------

_INSERT_ORGANIZATION = """
    INSERT INTO vertex_contracts_organization (
        vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo,
        did, legal_entity_ref,
        country, lei, national_id, name, legal_name, entity_type, isic,
        duns, wikidata_qid, opencorporates_id, status,
        source, source_record_id, confidence, last_verified,
        created_at, org_id, user_id, actor_id
    ) VALUES (
        $1, NULL, $2, 1, $3, $4, $3,
        $5, $6,
        $7, $8, $9, $10, $11, $12, $13,
        $14, $15, $16, $17,
        $18, $19, $20, $21,
        $22, 'etzhayyim', 'system', $23
    )
    ON CONFLICT (vertex_id) DO NOTHING
    RETURNING vertex_id
"""


def _rkey_for_org_did(did: str) -> str:
    """rkey = 12-char hash portion of the entity DID (content-addressed)."""
    return did.rsplit(":", 1)[-1] or "unknown"


async def _insert_organization_row(pool: Any, row: dict[str, Any]) -> bool:
    """Returns True if a new row was inserted (False on ON CONFLICT)."""
    did = row["did"]
    rkey = _rkey_for_org_did(did)
    vertex_id = f"at://{did}/com.etzhayyim.apps.contracts.organization/{rkey}"
    now_iso = datetime.now(timezone.utc).isoformat()
    result = await pool.fetchval(
        _INSERT_ORGANIZATION,
        vertex_id,  # $1
        now_iso[:10],  # $2  created_date
        did,  # $3  owner_did / repo (controller = entity DID)
        rkey,  # $4
        did,  # $5
        row.get("legal_entity_ref"),  # $6
        row.get("country"),  # $7
        row.get("lei"),  # $8
        row.get("national_id"),  # $9
        row.get("name"),  # $10
        row.get("legal_name"),  # $11
        row.get("entity_type"),  # $12
        row.get("isic"),  # $13
        row.get("duns"),  # $14
        row.get("wikidata_qid"),  # $15
        row.get("opencorporates_id"),  # $16
        row.get("status"),  # $17
        row.get("source"),  # $18
        row.get("source_record_id"),  # $19
        float(row.get("confidence") or 1.0),  # $20
        row.get("last_verified") or now_iso,  # $21
        now_iso,  # $22
        f"sys.{ACTOR_NAME}",  # $23
    )
    return result is not None


# ---------------------------------------------------------------------------
# vertex_legal_entity row loader
# ---------------------------------------------------------------------------

_SELECT_LEGAL_ENTITY_BY_VID = """
    SELECT vertex_id, country, lei, national_id, name, legal_name, entity_type, isic,
           duns, wikidata_qid, opencorporates_id, status, source, source_record_id,
           last_verified, incorporated_date
      FROM vertex_legal_entity
     WHERE vertex_id = $1
     LIMIT 1
"""

_SELECT_LEGAL_ENTITY_BY_SOURCE_RECORD = """
    SELECT vertex_id, country, lei, national_id, name, legal_name, entity_type, isic,
           duns, wikidata_qid, opencorporates_id, status, source, source_record_id,
           last_verified, incorporated_date
      FROM vertex_legal_entity
     WHERE source_record_id = $1
     LIMIT 1
"""

_SELECT_LEGAL_ENTITY_BY_LEI = """
    SELECT vertex_id, country, lei, national_id, name, legal_name, entity_type, isic,
           duns, wikidata_qid, opencorporates_id, status, source, source_record_id,
           last_verified, incorporated_date
      FROM vertex_legal_entity
     WHERE lei = $1
     LIMIT 1
"""

_SELECT_UNPROJECTED_LEGAL_ENTITIES = """
    SELECT le.vertex_id, le.country, le.lei, le.national_id, le.name, le.legal_name,
           le.entity_type, le.isic, le.duns, le.wikidata_qid, le.opencorporates_id,
           le.status, le.source, le.source_record_id, le.last_verified, le.incorporated_date
      FROM vertex_legal_entity le
      LEFT JOIN vertex_contracts_organization co
             ON co.legal_entity_ref = le.vertex_id
     WHERE co.vertex_id IS NULL
       AND le.country IS NOT NULL
     LIMIT $1
"""


def _row_to_projection(le_row: dict[str, Any] | Any) -> dict[str, Any]:
    """
    Build the vertex_contracts_organization insert payload from a
    vertex_legal_entity row. Both dict and asyncpg Record are accepted.
    """
    g = le_row.get if isinstance(le_row, dict) else le_row.__getitem__  # type: ignore[union-attr]
    country = str(g("country") or "").strip()
    national_id = str(g("national_id") or "").strip()
    name = str(g("name") or "").strip()
    incorporated = str(g("incorporated_date") or "").strip()

    did = _mint_did(country, national_id, name, incorporated)
    return {
        "did": did,
        "legal_entity_ref": g("vertex_id"),
        "country": country or None,
        "lei": g("lei"),
        "national_id": national_id or None,
        "name": name or None,
        "legal_name": g("legal_name"),
        "entity_type": g("entity_type"),
        "isic": g("isic"),
        "duns": g("duns"),
        "wikidata_qid": g("wikidata_qid"),
        "opencorporates_id": g("opencorporates_id"),
        "status": g("status"),
        "source": g("source"),
        "source_record_id": g("source_record_id"),
        "last_verified": str(g("last_verified") or "") or None,
    }


# ---------------------------------------------------------------------------
# mintOrganizationDid — single-row mint + optional projection write
# ---------------------------------------------------------------------------


@udf(
    nsid="com.etzhayyim.apps.contracts.mintOrganizationDid",
    io_threads=50,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("contracts", "did", "mint"),
    agent_tool=(
        "Mint a deterministic social-contract:entity DID from a "
        "vertex_legal_entity row. Idempotent (same input → same DID). "
        "Optionally inserts the vertex_contracts_organization projection."
    ),
)
async def mint_organization_did(params_json: str) -> str:
    """
    Input JSON: {legalEntityVertexId, projectRow?}
    Output JSON: {ok, did, inserted, legalEntityVertexId} | {error}
    """
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    le_vid = params.get("legalEntityVertexId")
    if not le_vid:
        return json.dumps({"error": "legalEntityVertexId required"})
    project_row = bool(params.get("projectRow", True))

    ctx = Context(nsid="com.etzhayyim.apps.contracts.mintOrganizationDid")
    row = await ctx.db.fetchrow(_SELECT_LEGAL_ENTITY_BY_VID, le_vid)
    if row is None:
        return json.dumps({"error": f"legal entity not found: {le_vid}"})

    payload = _row_to_projection(row)
    did = payload["did"]

    inserted = False
    if project_row:
        inserted = await _insert_organization_row(ctx.db, payload)

    return json.dumps(
        {
            "ok": True,
            "did": did,
            "inserted": inserted,
            "legalEntityVertexId": le_vid,
        }
    )


# ---------------------------------------------------------------------------
# projectFromLegalEntity — per-row lookup OR bounded backfill
# ---------------------------------------------------------------------------


@udf(
    nsid="com.etzhayyim.apps.contracts.projectFromLegalEntity",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("contracts", "projection", "backfill"),
    agent_tool=(
        "Project rows from vertex_legal_entity into "
        "vertex_contracts_organization. Accepts sourceRecordId / lei / "
        "vertexId for a single row, or runs a bounded backfill of "
        "unprojected rows."
    ),
)
async def project_from_legal_entity(params_json: str) -> str:
    """
    Input JSON: {sourceRecordId?} | {lei?} | {vertexId?} | {batchLimit?}
    Output JSON: {ok, scanned, inserted, skipped, dids[]} | {error}
    """
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    ctx = Context(nsid="com.etzhayyim.apps.contracts.projectFromLegalEntity")
    scanned = 0
    inserted = 0
    skipped = 0
    dids: list[str] = []

    async def _project_one(row: Any) -> None:
        nonlocal scanned, inserted, skipped
        scanned += 1
        payload = _row_to_projection(row)
        if await _insert_organization_row(ctx.db, payload):
            inserted += 1
            dids.append(payload["did"])
        else:
            skipped += 1

    # Single-row lookup paths — mutually exclusive, first match wins.
    vertex_id = params.get("vertexId")
    source_record_id = params.get("sourceRecordId")
    lei = params.get("lei")

    if vertex_id:
        row = await ctx.db.fetchrow(_SELECT_LEGAL_ENTITY_BY_VID, vertex_id)
        if row is None:
            return json.dumps({"error": f"legal entity not found: {vertex_id}"})
        await _project_one(row)
    elif source_record_id:
        row = await ctx.db.fetchrow(_SELECT_LEGAL_ENTITY_BY_SOURCE_RECORD, source_record_id)
        if row is None:
            return json.dumps({"error": f"no legal entity with source_record_id={source_record_id}"})
        await _project_one(row)
    elif lei:
        row = await ctx.db.fetchrow(_SELECT_LEGAL_ENTITY_BY_LEI, lei)
        if row is None:
            return json.dumps({"error": f"no legal entity with lei={lei}"})
        await _project_one(row)
    else:
        # Bounded backfill — clamped to [1, 5000], default 500.
        raw_limit = int(params.get("batchLimit") or 500)
        batch_limit = max(1, min(5000, raw_limit))
        rows = await ctx.db.fetch(_SELECT_UNPROJECTED_LEGAL_ENTITIES, batch_limit)
        for row in rows:
            await _project_one(row)

    return json.dumps(
        {
            "ok": True,
            "scanned": scanned,
            "inserted": inserted,
            "skipped": skipped,
            "dids": dids,
        }
    )


# ---------------------------------------------------------------------------
# ingestSocialContract — fresh HTTP crawl (UN Treaty / Constitute Project)
# ---------------------------------------------------------------------------

_INSERT_SOCIAL_CONTRACT = """
    INSERT INTO vertex_contracts_social_contract (
        vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo,
        name, constitutional_type, jurisdiction,
        adopted_date, effective_date, scope, url, un_reg_no,
        source, source_record_id, confidence, last_verified,
        created_at, org_id, user_id, actor_id
    ) VALUES (
        $1, NULL, $2, 1, $3, $4, $3,
        $5, $6, $7,
        $8, $9, $10, $11, $12,
        $13, $14, $15, $16,
        $17, 'etzhayyim', 'system', $18
    )
    ON CONFLICT (vertex_id) DO NOTHING
    RETURNING vertex_id
"""


async def _insert_social_contract_row(pool: Any, row: dict[str, Any]) -> bool:
    source = row["source"]
    source_record_id = row["source_record_id"]
    # rkey = source:source_record_id keeps the row address stable across re-ingests.
    rkey = f"{source}-{source_record_id}".lower()
    rkey = _NON_ALNUM.sub("-", rkey).strip("-")[:64] or "unknown"
    vertex_id = f"at://{ACTOR_DID}/com.etzhayyim.apps.contracts.socialContract/{rkey}"
    now_iso = datetime.now(timezone.utc).isoformat()
    result = await pool.fetchval(
        _INSERT_SOCIAL_CONTRACT,
        vertex_id,  # $1
        now_iso[:10],  # $2
        ACTOR_DID,  # $3
        rkey,  # $4
        row.get("name"),  # $5
        row.get("constitutional_type"),  # $6
        row.get("jurisdiction"),  # $7
        row.get("adopted_date"),  # $8
        row.get("effective_date"),  # $9
        row.get("scope"),  # $10
        row.get("url"),  # $11
        row.get("un_reg_no"),  # $12
        source,  # $13
        source_record_id,  # $14
        float(row.get("confidence") or 0.8),  # $15
        row.get("last_verified") or now_iso,  # $16
        now_iso,  # $17
        f"sys.{ACTOR_NAME}",  # $18
    )
    return result is not None


async def _fetch_un_treaty_delta(since: str | None, limit: int) -> list[dict[str, Any]]:
    """
    Fetch recent UN Treaty Collection entries. Phase 1 stub: the full
    scraper (HTML + JSON endpoint + pagination) lands in the next PR —
    the interface is pinned here so downstream callers can stabilize.
    """
    # TODO (phase-1-post-pilot): wire aiohttp + HTML parser + delta cursor.
    # Guarded so the handler does not crash on early invocation; returns
    # empty set so the pilot smoke run is a clean no-op.
    _ = (since, limit)
    return []


async def _fetch_constitute_delta(since: str | None, limit: int) -> list[dict[str, Any]]:
    """Same shape as the UN Treaty fetcher; Constitute Project implementation follows."""
    _ = (since, limit)
    return []


@udf(
    nsid="com.etzhayyim.apps.contracts.ingestSocialContract",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("contracts", "socialContract", "ingest"),
    agent_tool=(
        "Fresh crawl of SocialContract records (constitutions / "
        "treaties). Writes vertex_contracts_social_contract directly. "
        "Law full-text corpus is out of scope — see houbun.etzhayyim.com."
    ),
)
async def ingest_social_contract(params_json: str) -> str:
    """
    Input JSON: {source, docId?, since?, limit?}
    Output JSON: {ok, source, fetched, inserted, skipped, errors} | {error}
    """
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    source = params.get("source")
    if source not in ("un-treaty", "constitute-project"):
        return json.dumps({"error": "source must be 'un-treaty' or 'constitute-project'"})

    since = params.get("since")
    raw_limit = int(params.get("limit") or 100)
    limit = max(1, min(1000, raw_limit))

    ctx = Context(nsid="com.etzhayyim.apps.contracts.ingestSocialContract")

    if source == "un-treaty":
        records = await _fetch_un_treaty_delta(since, limit)
    else:
        records = await _fetch_constitute_delta(since, limit)

    fetched = len(records)
    inserted = 0
    skipped = 0
    errors = 0
    for rec in records:
        try:
            if await _insert_social_contract_row(ctx.db, rec):
                inserted += 1
            else:
                skipped += 1
        except Exception:  # noqa: BLE001 — per-row isolation, full trace in logger
            ctx.logger().exception("ingestSocialContract row failed", source=source)
            errors += 1

    return json.dumps(
        {
            "ok": True,
            "source": source,
            "fetched": fetched,
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }
    )


# ---------------------------------------------------------------------------
# resolveOrganization — read path (XRPC query)
# ---------------------------------------------------------------------------

_SELECT_ORG_BY_DID = """
    SELECT vertex_id, did, legal_entity_ref, country, lei, national_id, name,
           isic, status, source, confidence, last_verified
      FROM vertex_contracts_organization
     WHERE did = $1
     LIMIT 1
"""

_SELECT_ORG_BY_LEI = """
    SELECT vertex_id, did, legal_entity_ref, country, lei, national_id, name,
           isic, status, source, confidence, last_verified
      FROM vertex_contracts_organization
     WHERE lei = $1
     LIMIT 1
"""

_SELECT_ORG_BY_NATIONAL_ID = """
    SELECT vertex_id, did, legal_entity_ref, country, lei, national_id, name,
           isic, status, source, confidence, last_verified
      FROM vertex_contracts_organization
     WHERE national_id = $1
     LIMIT 1
"""

_SELECT_ORG_BY_COUNTRY = """
    SELECT vertex_id, did, legal_entity_ref, country, lei, national_id, name,
           isic, status, source, confidence, last_verified
      FROM vertex_contracts_organization
     WHERE country = $1
     ORDER BY name
     OFFSET $2 LIMIT $3
"""


def _row_to_resolve_dto(r: Any) -> dict[str, Any]:
    g = r.get if isinstance(r, dict) else r.__getitem__  # type: ignore[union-attr]
    return {
        "did": g("did"),
        "vertexId": g("vertex_id"),
        "legalEntityRef": g("legal_entity_ref"),
        "country": g("country"),
        "lei": g("lei"),
        "nationalId": g("national_id"),
        "name": g("name"),
        "isic": g("isic"),
        "status": g("status"),
        "source": g("source"),
        "confidence": g("confidence"),
        "lastVerified": g("last_verified"),
    }


@udf(
    nsid="com.etzhayyim.apps.contracts.resolveOrganization",
    io_threads=50,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("contracts", "resolve"),
    agent_tool=(
        "Resolve an organization from vertex_contracts_organization by "
        "DID / LEI / nationalId, or list by country."
    ),
)
async def resolve_organization(params_json: str) -> str:
    """
    Input JSON: {did? | lei? | nationalId? | country?, limit?, offset?}
    Output JSON: {total, offset, limit, organizations: [...]}
    """
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    raw_limit = int(params.get("limit") or 20)
    limit = max(1, min(100, raw_limit))
    offset = max(0, int(params.get("offset") or 0))

    ctx = Context(nsid="com.etzhayyim.apps.contracts.resolveOrganization")

    did = params.get("did")
    lei = params.get("lei")
    national_id = params.get("nationalId")
    country = params.get("country")

    organizations: list[dict[str, Any]] = []

    if did:
        row = await ctx.db.fetchrow(_SELECT_ORG_BY_DID, did)
        if row is not None:
            organizations.append(_row_to_resolve_dto(row))
    elif lei:
        row = await ctx.db.fetchrow(_SELECT_ORG_BY_LEI, lei)
        if row is not None:
            organizations.append(_row_to_resolve_dto(row))
    elif national_id:
        row = await ctx.db.fetchrow(_SELECT_ORG_BY_NATIONAL_ID, national_id)
        if row is not None:
            organizations.append(_row_to_resolve_dto(row))
    elif country:
        rows = await ctx.db.fetch(_SELECT_ORG_BY_COUNTRY, country, offset, limit)
        organizations.extend(_row_to_resolve_dto(r) for r in rows)
    else:
        return json.dumps({"error": "one of did / lei / nationalId / country required"})

    return json.dumps(
        {
            "total": len(organizations),
            "offset": offset,
            "limit": limit,
            "organizations": organizations,
        }
    )
