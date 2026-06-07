"""gov.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")

_ORGANISM_SQLITE_DIR = Path(
    os.getenv("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
)
_ACTOR = os.getenv("GOV_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"gov-{safe}.db"


_DDL = """
CREATE TABLE IF NOT EXISTS vertex_gov_official_agency (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    name_local      TEXT NOT NULL DEFAULT '',
    jurisdiction    TEXT NOT NULL DEFAULT '',
    branch          TEXT NOT NULL DEFAULT '',
    level           TEXT NOT NULL DEFAULT '',
    cofog           TEXT NOT NULL DEFAULT '',
    parent_agency_did TEXT NOT NULL DEFAULT '',
    established_at  TEXT NOT NULL DEFAULT '',
    legal_basis     TEXT NOT NULL DEFAULT '',
    website_uri     TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_gov_official (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    agency_did      TEXT NOT NULL DEFAULT '',
    person_did      TEXT NOT NULL DEFAULT '',
    role            TEXT NOT NULL DEFAULT '',
    appointed_at    TEXT NOT NULL DEFAULT '',
    term_ends_at    TEXT NOT NULL DEFAULT '',
    appointed_by_did TEXT NOT NULL DEFAULT '',
    confirmation_process TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_gov_consult (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    requester_did   TEXT NOT NULL DEFAULT '',
    domain          TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL DEFAULT '',
    query           TEXT NOT NULL DEFAULT '',
    municipality_code TEXT NOT NULL DEFAULT '',
    priority        TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_gov_municipality (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    municipality_code TEXT NOT NULL DEFAULT '',
    prefecture      TEXT NOT NULL DEFAULT '',
    city            TEXT NOT NULL DEFAULT '',
    site_url        TEXT NOT NULL DEFAULT '',
    coverage_pct    REAL NOT NULL DEFAULT 0.0,
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);
"""

def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


def _open(actor: str = _ACTOR) -> sqlite3.Connection:
    path = _db_path(actor)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _register_agency_sync(name: str, name_local: str, jurisdiction: str, branch: str, level: str, cofog: str, parent_agency_did: str, established_at: str, legal_basis: str, website_uri: str, actor: str) -> dict[str, Any]:
    agency_id = str(uuid.uuid4())
    actor_did = f"did:web:gov.etzhayyim.com:{jurisdiction.lower()}:{cofog}:{agency_id[:8]}"
    vertex_id = f"gov:agency:{agency_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_gov_official_agency
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, name, name_local, jurisdiction, branch, level, cofog,
                parent_agency_did, established_at, legal_basis, website_uri,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, actor_did,
             agency_id, name, name_local, jurisdiction, branch, level, cofog,
             parent_agency_did, established_at, legal_basis, website_uri,
             actor_did, "did:web:gov.etzhayyim.com", now, now)
        )
        conn.commit()

    return {"did": actor_did, "uri": f"at://{actor_did}/com.etzhayyim.apps.gov.agency/{agency_id}"}


def _record_official_sync(agency_did: str, person_did: str, role: str, appointed_at: str, term_ends_at: str, appointed_by_did: str, confirmation_process: str, actor: str) -> dict[str, Any]:
    official_id = str(uuid.uuid4())
    vertex_id = f"gov:official:{official_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_gov_official
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, agency_did, person_did, role, appointed_at,
                term_ends_at, appointed_by_did, confirmation_process,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, person_did,
             official_id, agency_did, person_did, role, appointed_at,
             term_ends_at, appointed_by_did, confirmation_process,
             "did:web:gov.etzhayyim.com", "did:web:gov.etzhayyim.com", now, now)
        )
        conn.commit()

    return {"uri": f"at://did:web:gov.etzhayyim.com/com.etzhayyim.apps.gov.official/{official_id}"}


def _submit_consult_sync(requester_did: str, domain: str, category: str, query: str, municipality_code: str, priority: str, actor: str) -> dict[str, Any]:
    consult_id = str(uuid.uuid4())
    vertex_id = f"gov:consult:{consult_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_gov_consult
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, requester_did, domain, category, query,
                municipality_code, priority, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 2, requester_did,
             consult_id, requester_did, domain, category, query,
             municipality_code, priority, "open",
             "did:web:gov.etzhayyim.com", "did:web:gov.etzhayyim.com", now, now)
        )
        conn.commit()

    return {"id": consult_id, "status": "open"}


def _list_agencies_sync(jurisdiction: str, branch: str, level: str, cofog: str, limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        conditions = []
        params = []
        if jurisdiction:
            conditions.append("jurisdiction = ?"); params.append(jurisdiction)
        if branch:
            conditions.append("branch = ?"); params.append(branch)
        if level:
            conditions.append("level = ?"); params.append(level)
        if cofog:
            conditions.append("cofog = ?"); params.append(cofog)
        
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        
        # limit, offset
        query = f"""SELECT id, name, name_local, jurisdiction, branch, cofog, actor_did, created_at 
                    FROM vertex_gov_official_agency {where} 
                    ORDER BY created_at DESC LIMIT ? OFFSET ?"""
        
        rows = conn.execute(query, tuple(params + [limit, offset])).fetchall()
        
        count_query = f"SELECT COUNT(*) as cnt FROM vertex_gov_official_agency {where}"
        total_row = conn.execute(count_query, tuple(params)).fetchone()

    return {"agencies": [dict(r) for r in rows], "total": total_row["cnt"] if total_row else 0, "offset": offset, "limit": limit}


def _get_agency_sync(agency_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute("SELECT * FROM vertex_gov_official_agency WHERE id = ?", (agency_id,)).fetchone()
        
        if not row:
            return {"error": "not found"}
            
        agency_actor_did = row["actor_did"] if row else ""
        officials = conn.execute(
            "SELECT * FROM vertex_gov_official WHERE agency_did = ? ORDER BY appointed_at DESC LIMIT 20",
            (agency_actor_did,)
        ).fetchall()

    return {"agency": dict(row), "officials": [dict(o) for o in officials]}


def _list_officials_sync(agency_did: str, role: str, limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        conditions = []
        params = []
        if agency_did:
            conditions.append("agency_did = ?"); params.append(agency_did)
        if role:
            conditions.append("role = ?"); params.append(role)
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        
        query = f"""SELECT id, agency_did, person_did, role, appointed_at, term_ends_at, confirmation_process 
                    FROM vertex_gov_official {where} 
                    ORDER BY appointed_at DESC LIMIT ? OFFSET ?"""
                    
        rows = conn.execute(query, tuple(params + [limit, offset])).fetchall()

    return {"officials": [dict(r) for r in rows], "offset": offset, "limit": limit}


def _list_municipalities_sync(prefecture: str, limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        conditions = []
        params = []
        if prefecture:
            conditions.append("prefecture = ?"); params.append(prefecture)
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        
        query = f"""SELECT municipality_code, prefecture, city, site_url, coverage_pct, status 
                    FROM vertex_gov_municipality {where} 
                    ORDER BY prefecture, city LIMIT ? OFFSET ?"""
                    
        rows = conn.execute(query, tuple(params + [limit, offset])).fetchall()

    return {"municipalities": [dict(r) for r in rows], "offset": offset, "limit": limit}


def _list_consults_sync(requester_did: str, domain: str, status: str, limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        conditions = []
        params = []
        if requester_did:
            conditions.append("requester_did = ?"); params.append(requester_did)
        if domain:
            conditions.append("domain = ?"); params.append(domain)
        if status:
            conditions.append("status = ?"); params.append(status)
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        
        query = f"""SELECT id, requester_did, domain, category, priority, status, created_at 
                    FROM vertex_gov_consult {where} 
                    ORDER BY created_at DESC LIMIT ? OFFSET ?"""
                    
        rows = conn.execute(query, tuple(params + [limit, offset])).fetchall()

    return {"consults": [dict(r) for r in rows], "offset": offset, "limit": limit}


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.gov.registerAgency")
    async def task_register_agency(**kwargs):
        return await asyncio.to_thread(
            _register_agency_sync,
            kwargs.get("name", ""),
            kwargs.get("nameLocal", ""),
            kwargs.get("jurisdiction", ""),
            kwargs.get("branch", ""),
            kwargs.get("level", "national"),
            kwargs.get("cofog", ""),
            kwargs.get("parentAgencyDid", ""),
            kwargs.get("establishedAt", ""),
            kwargs.get("legalBasis", ""),
            kwargs.get("websiteUri", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.gov.recordOfficial")
    async def task_record_official(**kwargs):
        return await asyncio.to_thread(
            _record_official_sync,
            kwargs.get("agencyDid", ""),
            kwargs.get("personDid", ""),
            kwargs.get("role", ""),
            kwargs.get("appointedAt", ""),
            kwargs.get("termEndsAt", ""),
            kwargs.get("appointedByDid", ""),
            kwargs.get("confirmationProcess", "appointment"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.gov.submitConsult")
    async def task_submit_consult(**kwargs):
        return await asyncio.to_thread(
            _submit_consult_sync,
            kwargs.get("requesterDid", ""),
            kwargs.get("domain", "healthcare"),
            kwargs.get("category", ""),
            kwargs.get("query", ""),
            kwargs.get("municipalityCode", ""),
            kwargs.get("priority", "normal"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.gov.listAgencies")
    async def task_list_agencies(**kwargs):
        return await asyncio.to_thread(
            _list_agencies_sync,
            kwargs.get("jurisdiction", ""),
            kwargs.get("branch", ""),
            kwargs.get("level", ""),
            kwargs.get("cofog", ""),
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.gov.getAgency")
    async def task_get_agency(**kwargs):
        return await asyncio.to_thread(
            _get_agency_sync,
            kwargs.get("id", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.gov.listOfficials")
    async def task_list_officials(**kwargs):
        return await asyncio.to_thread(
            _list_officials_sync,
            kwargs.get("agencyDid", ""),
            kwargs.get("role", ""),
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.gov.listMunicipalities")
    async def task_list_municipalities(**kwargs):
        return await asyncio.to_thread(
            _list_municipalities_sync,
            kwargs.get("prefecture", ""),
            int(kwargs.get("limit", 100)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.gov.listConsults")
    async def task_list_consults(**kwargs):
        return await asyncio.to_thread(
            _list_consults_sync,
            kwargs.get("requesterDid", ""),
            kwargs.get("domain", ""),
            kwargs.get("status", ""),
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
