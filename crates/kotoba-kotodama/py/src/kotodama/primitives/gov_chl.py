"""CHL Government states actor primitives.

This module moves the `did:web:chl-state.etzhayyim.com` app actor off its
dedicated Cloudflare Worker path. The public edge keeps only XRPC/MCP
facade duties; these functions run as Zeebe jobs in Kubernetes and write
the same graph-visible state the Worker previously wrote via host-sdk.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error as _u_err
import urllib.request as _u_req
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives.gov_fetch_proxy import direct_then_proxy_fetch_hash_status


PRIMARY_DID = "did:web:chl-state.etzhayyim.com"
DOMAIN_CODE = "chl"
SITE_NANOID = "w3bpg001"
SITE_GOV_TOPIC_DID = "did:web:site.etzhayyim.com:topic:government"
PDS_BASE = os.environ.get("PDS_URL", "https://atproto.etzhayyim.com")
PDS_SERVICE_AUTH_TOKEN = os.environ.get("PDS_SERVICE_AUTH_TOKEN", "").strip()
PDS_SERVICE_AUTH_MINT_URL = os.environ.get(
    "PDS_SERVICE_AUTH_MINT_URL",
    f"{PDS_BASE}/_internal/mint-pds-bearer",
).strip()
PDS_SERVICE_AUTH_MINT_SECRET = os.environ.get("PDS_SERVICE_AUTH_MINT_SECRET", "").strip()
PDS_LEGACY_INTERNAL_TRUST = os.environ.get("PDS_LEGACY_INTERNAL_TRUST", "0") == "1"
try:
    PDS_SERVICE_AUTH_TTL_SEC = int(os.environ.get("PDS_SERVICE_AUTH_TTL_SEC", "600"))
except ValueError:
    PDS_SERVICE_AUTH_TTL_SEC = 600
PDS_SERVICE_AUTH_TTL_SEC = max(30, min(600, PDS_SERVICE_AUTH_TTL_SEC))
_PDS_SERVICE_AUTH_CACHE: dict[str, dict[str, Any]] = {}

_MINISTRY_NDJSON = """\
{"path":"presidencia","name":"Presidencia de la República","nameEn":"Presidency of the Republic","website":"https://www.gob.cl/","contract":"Constitución Política 1980/2005 Art. 24-45","tags":["cofog:01","executive","president"],"orgTier":"ministry"}
{"path":"defensa","name":"Ministerio de Defensa Nacional","nameEn":"Ministry of National Defence","website":"https://www.defensa.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:02","defense"],"orgTier":"ministry"}
{"path":"hacienda","name":"Ministerio de Hacienda","nameEn":"Ministry of Finance","website":"https://www.hacienda.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:01","finance"],"orgTier":"ministry"}
{"path":"rree","name":"Ministerio de Relaciones Exteriores","nameEn":"Ministry of Foreign Affairs","website":"https://www.minrel.gob.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:01.2","foreign-affairs"],"orgTier":"ministry"}
{"path":"justicia","name":"Ministerio de Justicia y Derechos Humanos","nameEn":"Ministry of Justice and Human Rights","website":"https://www.minjusticia.gob.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:03","justice"],"orgTier":"ministry"}
{"path":"interior","name":"Ministerio del Interior y Seguridad Pública","nameEn":"Ministry of Interior and Public Safety","website":"https://www.interior.gob.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:01","interior"],"orgTier":"ministry"}
{"path":"educacion","name":"Ministerio de Educación","nameEn":"Ministry of Education","website":"https://www.mineduc.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:09","education"],"orgTier":"ministry"}
{"path":"salud","name":"Ministerio de Salud","nameEn":"Ministry of Health","website":"https://www.minsal.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:07","health"],"orgTier":"ministry"}
{"path":"agricultura","name":"Ministerio de Agricultura","nameEn":"Ministry of Agriculture","website":"https://www.minagri.gob.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:04","agriculture"],"orgTier":"ministry"}
{"path":"obras","name":"Ministerio de Obras Públicas","nameEn":"Ministry of Public Works","website":"https://www.mop.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:04","infrastructure"],"orgTier":"ministry"}
{"path":"trabajo","name":"Ministerio del Trabajo y Previsión Social","nameEn":"Ministry of Labour and Social Welfare","website":"https://www.mintrab.gob.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:10","labour"],"orgTier":"ministry"}
{"path":"economia","name":"Ministerio de Economía, Fomento y Turismo","nameEn":"Ministry of Economy, Development and Tourism","website":"https://www.economia.gob.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:04","economy"],"orgTier":"ministry"}
{"path":"energia","name":"Ministerio de Energía","nameEn":"Ministry of Energy","website":"https://www.energia.gob.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:04","energy"],"orgTier":"ministry"}
{"path":"medioambiente","name":"Ministerio del Medio Ambiente","nameEn":"Ministry of the Environment","website":"https://www.mma.gob.cl/","contract":"Constitución Política 1980/2005","tags":["cofog:05","environment"],"orgTier":"ministry"}
"""

_STATE_NDJSON = """\
{"path":"region:tarapaca","name":"Gobierno Regional de Tarapacá","nameEn":"Regional Government of Tarapacá","website":"https://www.goretarapaca.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","tarapaca"],"orgTier":"state"}
{"path":"region:antofagasta","name":"Gobierno Regional de Antofagasta","nameEn":"Regional Government of Antofagasta","website":"https://www.goreantofagasta.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","antofagasta"],"orgTier":"state"}
{"path":"region:atacama","name":"Gobierno Regional de Atacama","nameEn":"Regional Government of Atacama","website":"https://www.goreatacama.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","atacama"],"orgTier":"state"}
{"path":"region:coquimbo","name":"Gobierno Regional de Coquimbo","nameEn":"Regional Government of Coquimbo","website":"https://www.gorecoquimbo.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","coquimbo"],"orgTier":"state"}
{"path":"region:valparaiso","name":"Gobierno Regional de Valparaíso","nameEn":"Regional Government of Valparaíso","website":"https://www.gorevalparaiso.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","valparaiso"],"orgTier":"state"}
{"path":"region:ohiggins","name":"Gobierno Regional de O'Higgins","nameEn":"Regional Government of O'Higgins","website":"https://www.goreohiggins.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","ohiggins"],"orgTier":"state"}
{"path":"region:maule","name":"Gobierno Regional del Maule","nameEn":"Regional Government of Maule","website":"https://www.goremaule.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","maule"],"orgTier":"state"}
{"path":"region:biobio","name":"Gobierno Regional del Biobío","nameEn":"Regional Government of Biobío","website":"https://www.gorebiobio.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","biobio"],"orgTier":"state"}
{"path":"region:araucania","name":"Gobierno Regional de La Araucanía","nameEn":"Regional Government of La Araucanía","website":"https://www.gorearaucania.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","araucania"],"orgTier":"state"}
{"path":"region:los-lagos","name":"Gobierno Regional de Los Lagos","nameEn":"Regional Government of Los Lagos","website":"https://www.goreloslagos.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","los-lagos"],"orgTier":"state"}
{"path":"region:aysen","name":"Gobierno Regional de Aysén","nameEn":"Regional Government of Aysén","website":"https://www.goreaysen.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","aysen"],"orgTier":"state"}
{"path":"region:magallanes","name":"Gobierno Regional de Magallanes","nameEn":"Regional Government of Magallanes","website":"https://www.goremagallanes.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","magallanes"],"orgTier":"state"}
{"path":"region:metropolitana","name":"Gobierno Regional Metropolitano de Santiago","nameEn":"Metropolitan Regional Government of Santiago","website":"https://www.goremetropolitano.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","metropolitana"],"orgTier":"state"}
{"path":"region:los-rios","name":"Gobierno Regional de Los Ríos","nameEn":"Regional Government of Los Ríos","website":"https://www.gorelosrios.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","los-rios"],"orgTier":"state"}
{"path":"region:arica-parinacota","name":"Gobierno Regional de Arica y Parinacota","nameEn":"Regional Government of Arica and Parinacota","website":"https://www.gorearica.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","arica-parinacota"],"orgTier":"state"}
{"path":"region:nuble","name":"Gobierno Regional de Ñuble","nameEn":"Regional Government of Ñuble","website":"https://www.goreniuble.gov.cl/","contract":"Constitución Política 1980/2005 + Ley 19.175","tags":["cofog:01","region","nuble"],"orgTier":"state"}
"""


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _url_to_domain_slug(url: str) -> str:
    try:
        host = re.sub(r"^https?://", "", url).split("/", 1)[0]
        host = re.sub(r"^(www|web)\.", "", host)
        return host.replace(".", "-")
    except Exception:
        return ""


def _load_seed_orgs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for blob in (_MINISTRY_NDJSON, _STATE_NDJSON):
        for line in blob.splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _vertex_id(path: str) -> str:
    return f"at://{PRIMARY_DID}/com.etzhayyim.apps.states.govOrg/{path}"


def _repo_rkey(prefix: str, key: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S%f")
    safe = re.sub(r"[^a-zA-Z0-9._~-]+", "-", key).strip("-")[:80] or "record"
    return f"{prefix}-{safe}-{stamp}"


def _http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    merged_headers = {
        "User-Agent": "etzhayyim-kotodama-gov-afg/0.1",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    merged_headers.update(headers)
    req = _u_req.Request(url, data=body, headers=merged_headers, method="POST")
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = int(resp.status)
    except _u_err.HTTPError as e:
        raw = e.read()
        status = int(e.code)
    except Exception as e:  # noqa: BLE001
        return {"status": -1, "body": {"error": f"transport: {e}"}}
    try:
        parsed: Any = json.loads(raw.decode("utf-8"))
    except Exception:
        parsed = {"raw": raw.decode("utf-8", errors="replace")[:500]}
    return {"status": status, "body": parsed}


def _mint_pds_service_auth(lxm: str) -> str:
    cached = _PDS_SERVICE_AUTH_CACHE.get(lxm)
    now = int(time.time())
    if cached and int(cached.get("expiresAt", 0)) > now + 30:
        token = str(cached.get("token") or "")
        if token:
            return token
    if not PDS_SERVICE_AUTH_MINT_URL or not PDS_SERVICE_AUTH_MINT_SECRET:
        return ""
    payload = {"lxm": lxm, "ttlSeconds": PDS_SERVICE_AUTH_TTL_SEC}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(PDS_SERVICE_AUTH_MINT_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    req = _u_req.Request(
        PDS_SERVICE_AUTH_MINT_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-bpmn-auth": sig,
        },
        method="POST",
    )
    try:
        with _u_req.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ""
    token = str(data.get("token") or "")
    expires_at = int(data.get("expiresAt") or (now + PDS_SERVICE_AUTH_TTL_SEC))
    if token:
        _PDS_SERVICE_AUTH_CACHE[lxm] = {"token": token, "expiresAt": expires_at}
    return token


async def _pds_xrpc(lxm: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = await asyncio.to_thread(_mint_pds_service_auth, lxm)
    bearer = token or PDS_SERVICE_AUTH_TOKEN
    headers: dict[str, str] = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    elif PDS_LEGACY_INTERNAL_TRUST:
        headers["x-kotoba-kotodama-verified"] = "true"
    else:
        return {"status": 401, "body": {"error": "PDS service auth unavailable"}}
    return await asyncio.to_thread(_http_post_json, f"{PDS_BASE}/xrpc/{lxm}", payload, headers)


def _insert_repo_record(repo: str, collection: str, rkey: str, record: dict[str, Any]) -> str:
    created_at = str(record.get("createdAt") or _utc_now_iso())
    uri = f"at://{repo}/{collection}/{rkey}"
    if collection != "app.bsky.feed.post":
        value_json = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
        if collection == "actorManifest":
            path = str(record.get("path") or rkey)
            params = {
                "vertex_id": uri,
                "record_key": rkey,
                "record_kind": collection,
                "path": path,
                "country": str(record.get("country") or DOMAIN_CODE),
                "display_name": str(record.get("displayName") or ""),
                "description": str(record.get("description") or ""),
                "performer_type": str(record.get("performerType") or ""),
                "agent_type": str(record.get("agentType") or ""),
                "is_bot": bool(record.get("isBot") or False),
                "value_json": value_json,
                "indexed_at": created_at,
                "created_at": created_at,
                "updated_at": str(record.get("updated_at") or created_at),
                "actor_did": repo,
                "org_did": repo,
                "owner_did": PRIMARY_DID,
                "sensitivity_ord": 2,
            }
            get_kotoba_client().insert_row("vertex_gov_actor_manifest", params)
            return uri
        if collection == "com.etzhayyim.apps.states.govOrgSiteDep":
            path = str(record.get("path") or "")
            site_did = str(record.get("siteDid") or "")
            params = {
                "edge_id": uri,
                "record_key": rkey,
                "from_vertex_id": _vertex_id(path) if path else repo,
                "to_vertex_id": site_did,
                "path": path,
                "site_nanoid": str(record.get("siteNanoid") or ""),
                "site_topic_did": str(record.get("siteTopicDid") or ""),
                "site_did": site_did,
                "value_json": value_json,
                "indexed_at": created_at,
                "created_at": created_at,
                "updated_at": str(record.get("updated_at") or created_at),
                "actor_did": repo,
                "org_did": str(record.get("orgId") or "anon"),
                "owner_did": repo,
                "sensitivity_ord": 2,
            }
            get_kotoba_client().insert_row("edge_gov_org_site_dependency", params)
            return uri
        raise ValueError(f"unsupported gov collection: {collection!r}")
    params = {
        "vertex_id": uri,
        "record_kind": collection,
        "record_key": rkey,
        "label": "GovRecord",
        "status": "active",
        "value_json": json.dumps(record, separators=(",", ":"), ensure_ascii=False),
        "indexed_at": created_at,
        "created_at": created_at,
        "updated_at": str(record.get("updated_at") or record.get("updatedAt") or created_at),
        "org_id": str(record.get("orgId") or "anon"),
        "user_id": str(record.get("userId") or "anon"),
        "actor_id": str(record.get("actorId") or repo),
        "actor_did": repo,
        "org_did": str(record.get("orgDid") or "anon"),
        "owner_did": repo,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row("vertex_gov_record", params)
    return uri


def _upsert_gov_org(row: dict[str, Any]) -> None:
    now = _utc_now_iso()
    path = str(row["path"])
    params = {
        "vertex_id": _vertex_id(path),
        "sensitivity_ord": 1,
        "owner_did": PRIMARY_DID,
        "path": path,
        "name": str(row.get("name") or ""),
        "name_en": str(row.get("nameEn") or row.get("name_en") or ""),
        "website": str(row.get("website") or ""),
        "contract": str(row.get("contract") or ""),
        "tags": json.dumps(row.get("tags") or [], separators=(",", ":"), ensure_ascii=False),
        "domain_code": DOMAIN_CODE,
        "org_tier": str(row.get("orgTier") or row.get("org_tier") or ""),
        "site_domain_slug": str(row.get("site_domain_slug") or _url_to_domain_slug(str(row.get("website") or ""))),
        "site_followed": str(row.get("site_followed") or "false"),
        "did_registered": str(row.get("did_registered") or "false"),
        "last_ingested_at": str(row.get("last_ingested_at") or ""),
        "last_content_hash": str(row.get("last_content_hash") or ""),
        "last_kyumei_at": str(row.get("last_kyumei_at") or ""),
        "last_shinka_at": str(row.get("last_shinka_at") or ""),
        "created_at": str(row.get("created_at") or now),
        "props": json.dumps(row.get("props") or {}, separators=(",", ":"), ensure_ascii=False),
    }
    get_kotoba_client().insert_row("vertex_gov_org", params)


def _direct_fetch_hash(url: str, timeout: int = 10) -> tuple[str, str, str, str]:
    """Fetch url and return (md5_content_hash, text_snippet, status, error).

    Direct network fetch is attempted first. If this VKE/Mac egress path is
    blocked, GOV_FETCH_PROXY_URL + GOV_FETCH_HMAC enables authenticated
    Cloudflare edge fallback for public government websites.
    """
    return direct_then_proxy_fetch_hash_status(url, timeout=timeout)

def _update_gov_org_fields(path: str, fields: dict[str, str], owner_did: str = PRIMARY_DID) -> None:
    allowed = {
        "site_followed",
        "did_registered",
        "last_ingested_at",
        "last_content_hash",
        "last_fetch_status",
        "last_fetch_error",
        "last_fetch_checked_at",
        "last_kyumei_at",
        "last_shinka_at",
    }
    updates = {k: str(v) for k, v in fields.items() if k in allowed}
    if not path or not updates:
        return
    set_sql = ", ".join(f"{key} = %({key})s" for key in updates)
    params: dict[str, Any] = {
        "domain_code": DOMAIN_CODE,
        "owner_did": owner_did or PRIMARY_DID,
        "path": path,
        **updates,
    }
    # R0: fetch first by vertex_id and update dict
    existing = get_kotoba_client().select_first_where("vertex_gov_org", "vertex_id", _vertex_id(path))
    if existing:
        for k, v in updates.items():
            existing[k] = v
        get_kotoba_client().insert_row("vertex_gov_org", existing)


def _get_org(path: str) -> dict[str, Any] | None:
    # R0: using _vertex_id(path) since it's deterministic and unique
    row = get_kotoba_client().select_first_where("vertex_gov_org", "vertex_id", _vertex_id(path))
    if not row or row.get("domain_code") != DOMAIN_CODE or row.get("owner_did") != PRIMARY_DID:
        return None
    keys = [
        "path", "name", "name_en", "website", "contract", "tags", "org_tier",
        "site_domain_slug", "site_followed", "did_registered",
        "last_ingested_at", "last_content_hash", "last_kyumei_at",
        "last_shinka_at", "created_at",
    ]
    return {k: row.get(k) for k in keys}


def task_gov_chl_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: fetchall by domain_code limit 10000, python filter
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    existing = {
        str(r.get("path") or "") for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
    }
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_chl_resolve_org_path(path: str = "") -> dict[str, Any]:
    path = str(path or "").strip()
    if not path:
        return {"error": "missing path"}
    row = _get_org(path)
    if not row:
        return {"error": f"not found: {path}"}
    return {
        "did": f"{PRIMARY_DID}:{path}",
        "name": str(row.get("name") or ""),
        "nameEn": str(row.get("name_en") or ""),
        "website": str(row.get("website") or ""),
    }


def task_gov_chl_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    params: list[Any] = [DOMAIN_CODE, PRIMARY_DID]
    where = "domain_code = %s AND owner_did = %s AND name_en != ''"
    if org_tier:
        where += " AND org_tier = %s"
        params.append(org_tier)
    # R0: fetchall by domain_code limit 2000, python filter and sort
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
    ]
    if org_tier:
        filtered = [r for r in filtered if r.get("org_tier") == org_tier]
    total = len(filtered)
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    rows = filtered[offset : offset + limit]
    return {
        "orgs": [
            {
                "path": str(r[0] or ""),
                "did": f"{PRIMARY_DID}:{str(r[0] or '')}",
                "name": str(r[1] or ""),
                "nameEn": str(r[2] or ""),
                "website": str(r[3] or ""),
                "didRegistered": str(r[4] or "") == "true",
            }
            for r in rows
        ],
        "total": total,
    }


async def task_gov_chl_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: fetchall by domain_code limit 2000, python filter and sort
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en") and str(r.get("did_registered") or "") != "true"
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    rows = filtered[:limit]
    registered: list[str] = []
    pds_results: list[dict[str, Any]] = []
    for r in rows:
        row = {
            "path": str(r.get("path") or ""),
            "name": str(r.get("name") or ""),
            "name_en": str(r.get("name_en") or ""),
            "website": str(r.get("website") or ""),
            "contract": str(r.get("contract") or ""),
            "tags": json.loads(str(r.get("tags") or "[]")),
            "org_tier": str(r.get("org_tier") or ""),
            "site_domain_slug": str(r.get("site_domain_slug") or ""),
            "site_followed": str(r.get("site_followed") or "false"),
            "last_ingested_at": str(r.get("last_ingested_at") or ""),
            "last_content_hash": str(r.get("last_content_hash") or ""),
            "last_kyumei_at": str(r.get("last_kyumei_at") or ""),
            "last_shinka_at": str(r.get("last_shinka_at") or ""),
            "created_at": str(r.get("created_at") or _utc_now_iso()),
            "did_registered": "true",
        }
        path = row["path"]
        org_did = f"{PRIMARY_DID}:{path}"
        display_name = f"{row['name']} ({row['name_en']})"
        description = (
            "[AI Agent - unofficial, not affiliated with the real organization] "
            f"{row['name_en']}"
        )
        pds_results.append(
            {
                "path": path,
                "identity": await _pds_xrpc(
                    "com.atproto.identity.create",
                    {
                        "path": path,
                        "documentJson": json.dumps(
                            {
                                "displayName": display_name,
                                "description": f"{description} - {row['website']}",
                            },
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                    },
                ),
            }
        )
        _insert_repo_record(
            org_did,
            "actorManifest",
            _repo_rkey("actor", path),
            {
                "$type": "actorManifest",
                "displayName": display_name,
                "description": description,
                "performerType": "service",
                "isBot": True,
                "agentType": "autonomous",
                "country": DOMAIN_CODE,
                "path": path,
                "createdAt": _utc_now_iso(),
            },
        )
        pds_results[-1]["post"] = await _pds_xrpc(
            "app.bsky.feed.post",
            {"did": org_did, "text": f"{row['name_en']} registered.\n{org_did}"},
        )
        _insert_repo_record(
            org_did,
            "app.bsky.feed.post",
            _repo_rkey("registered", path),
            {
                "$type": "app.bsky.feed.post",
                "text": f"{row['name_en']} registered.\n{org_did}",
                "createdAt": _utc_now_iso(),
            },
        )
        _upsert_gov_org(row)
        registered.append(org_did)
    pds_ok = sum(
        1
        for result in pds_results
        if int(result.get("identity", {}).get("status") or 0) in range(200, 300)
    )
    return {"ok": True, "registered": len(registered), "dids": registered, "pdsIdentityOk": pds_ok}


async def task_gov_chl_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: fetchall by domain_code limit 2000, python filter and sort
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID
        and str(r.get("site_followed") or "") != "true"
        and r.get("site_domain_slug")
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    rows = filtered[:limit]
    for r in rows:
        path = str(r.get("path") or "")
        slug = str(r.get("site_domain_slug") or "")
        await _pds_xrpc("app.bsky.graph.follow", {"did": f"did:web:site.etzhayyim.com:{slug}"})
        row = {
            "path": path,
            "name": str(r.get("name") or ""),
            "name_en": str(r.get("name_en") or ""),
            "website": str(r.get("website") or ""),
            "contract": str(r.get("contract") or ""),
            "tags": json.loads(str(r.get("tags") or "[]")),
            "org_tier": str(r.get("org_tier") or ""),
            "site_domain_slug": slug,
            "site_followed": "true",
            "did_registered": str(r.get("did_registered") or "false"),
            "last_ingested_at": str(r.get("last_ingested_at") or ""),
            "last_content_hash": str(r.get("last_content_hash") or ""),
            "last_kyumei_at": str(r.get("last_kyumei_at") or ""),
            "last_shinka_at": str(r.get("last_shinka_at") or ""),
            "created_at": str(r.get("created_at") or _utc_now_iso()),
        }
        _insert_repo_record(
            f"{PRIMARY_DID}:{path}",
            "com.etzhayyim.apps.states.govOrgSiteDep",
            _repo_rkey("site-dep", path),
            {
                "$type": "com.etzhayyim.apps.states.govOrgSiteDep",
                "path": path,
                "siteNanoid": SITE_NANOID,
                "siteTopicDid": SITE_GOV_TOPIC_DID,
                "siteDid": f"did:web:site.etzhayyim.com:{slug}",
                "updated_at": _utc_now_iso(),
            },
        )
        _upsert_gov_org(row)
        followed += 1
    return {"ok": True, "followed": followed}


async def task_gov_chl_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: fetchall by domain_code limit 2000, python filter and sort
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = []
    for r in all_rows:
        if not r.get("site_domain_slug"):
            continue
        last_hash = str(r.get("last_content_hash") or "")
        last_ingested = str(r.get("last_ingested_at") or "")
        if not last_hash or not last_ingested or last_ingested < cutoff_iso:
            filtered.append(r)
    filtered.sort(key=lambda x: str(x.get("last_ingested_at") or ""))
    rows = filtered[:limit]
    checked = 0
    updated = 0
    posted = 0
    now = _utc_now_iso()
    for r in rows:
        path = str(r.get("path") or "")
        name_en = str(r.get("name_en") or "")
        website = str(r.get("website") or "")
        slug = str(r.get("site_domain_slug") or "")
        last_hash = str(r.get("last_content_hash") or "")
        owner_did = str(r.get("owner_did") or PRIMARY_DID)
        if not path or not slug:
            continue
        checked += 1
        # R0: fetchall by domain limit 50, sort by crawled_at desc, take 1
        wet_rows = get_kotoba_client().select_where("vertex_wet_chunk", "domain", slug, limit=50)
        wet_rows.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
        wet = wet_rows[0] if wet_rows else None
        if not wet:
            fetch_hash, fetch_text, fetch_status, fetch_error = _direct_fetch_hash(website)
            if fetch_hash:
                fields: dict[str, str] = {
                    "last_ingested_at": now,
                    "last_content_hash": fetch_hash,
                    "last_fetch_status": fetch_status or "ok",
                    "last_fetch_error": "",
                    "last_fetch_checked_at": now,
                }
                _update_gov_org_fields(path, fields, owner_did=owner_did)
                if fetch_hash != last_hash:
                    updated += 1
                    text = f"{name_en} - official site updated\n{fetch_text[:200]}..."
                    org_did = f"{owner_did}:{path}"
                    if postUpdates:
                        result = await _pds_xrpc("app.bsky.feed.post", {"did": org_did, "text": text})
                        if int(result.get("status") or 0) in range(200, 300):
                            posted += 1
                    _insert_repo_record(
                        org_did,
                        "app.bsky.feed.post",
                        _repo_rkey("wet-update", path),
                        {"$type": "app.bsky.feed.post", "text": text, "createdAt": now},
                    )
            else:
                _update_gov_org_fields(
                    path,
                    {
                        "last_ingested_at": now,
                        "last_fetch_status": fetch_status or "error",
                        "last_fetch_error": fetch_error,
                        "last_fetch_checked_at": now,
                    },
                    owner_did=owner_did,
                )
            continue
        markdown = str(wet[0] or "")
        content_hash = str(wet[1] or "")
        fields = {"last_ingested_at": now, "last_fetch_status": "wet_chunk", "last_fetch_error": "", "last_fetch_checked_at": now}
        if content_hash:
            fields["last_content_hash"] = content_hash
        _update_gov_org_fields(path, fields, owner_did=owner_did)
        if content_hash and content_hash != last_hash:
            updated += 1
            summary = re.sub(r"\s+", " ", markdown)[:200]
            text = f"{name_en} - official site updated\n{summary}..."
            org_did = f"{owner_did}:{path}"
            if postUpdates:
                result = await _pds_xrpc("app.bsky.feed.post", {"did": org_did, "text": text})
                if int(result.get("status") or 0) in range(200, 300):
                    posted += 1
            _insert_repo_record(
                org_did,
                "app.bsky.feed.post",
                _repo_rkey("wet-update", path),
                {
                    "$type": "app.bsky.feed.post",
                    "text": text,
                    "createdAt": now,
                },
            )
    return {"ok": True, "checked": checked, "updated": updated, "posted": posted}


async def task_gov_chl_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: fetchall by domain_code limit 2000, python filter and sort
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and str(r.get("did_registered") or "") == "true"
    ]
    filtered.sort(key=lambda x: str(x.get("last_shinka_at") or ""))
    rows = filtered[:limit]
    posted = 0
    now = _utc_now_iso()
    for r in rows:
        path = str(r.get("path") or "")
        name_en = str(r.get("name_en") or "")
        if not path:
            continue
        org_did = f"{PRIMARY_DID}:{path}"
        text = f"{name_en} - government organization update"
        if postUpdates:
            result = await _pds_xrpc("app.bsky.feed.post", {"did": org_did, "text": text})
            if int(result.get("status") or 0) in range(200, 300):
                posted += 1
        _insert_repo_record(
            org_did,
            "app.bsky.feed.post",
            _repo_rkey("shinka", path),
            {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": now,
            },
        )
        _update_gov_org_fields(path, {"last_shinka_at": now})
    return {"ok": True, "posted": posted, "touched": len(rows)}


async def task_gov_chl_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_chl_seed_orgs, seedLimit)
    register = await task_gov_chl_register_dids(registerLimit)
    follow = await task_gov_chl_follow_site_deps(followLimit)
    ingest = await task_gov_chl_sync_wet_updates(ingestLimit)
    shinka = await task_gov_chl_shinka(shinkaLimit)
    return {
        "ok": True,
        "seeded": seed.get("seeded", 0),
        "registered": register.get("registered", 0),
        "followed": follow.get("followed", 0),
        "wetUpdated": ingest.get("updated", 0),
        "shinkaPosted": shinka.get("posted", 0),
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="xrpc.com.etzhayyim.govChl.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_chl_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govChl.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_chl_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govChl.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_chl_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govChl.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_chl_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govChl.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_chl_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govChl.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_chl_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govChl.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_chl_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govChl.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_chl_heartbeat_tick)
