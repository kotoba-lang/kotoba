"""PHL Government states actor primitives.

This module moves the `did:web:phl-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:phl-state.etzhayyim.com"
DOMAIN_CODE = "phl"
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
{"path":"opre","name":"Opisina ng Pangulo","nameEn":"Office of the President","website":"https://op.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987 Art. VII","tags":["cofog:01","executive","president"],"orgTier":"ministry"}
{"path":"dfa","name":"Kagawaran ng Ugnayang Panlabas","nameEn":"Department of Foreign Affairs","website":"https://www.dfa.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01.2","foreign-affairs"],"orgTier":"ministry"}
{"path":"dnd","name":"Kagawaran ng Pambansang Depensa","nameEn":"Department of National Defense","website":"https://www.dnd.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:02","defence"],"orgTier":"ministry"}
{"path":"dof","name":"Kagawaran ng Pananalapi","nameEn":"Department of Finance","website":"https://www.dof.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01.1","finance"],"orgTier":"ministry"}
{"path":"doj","name":"Kagawaran ng Katarungan","nameEn":"Department of Justice","website":"https://www.doj.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:03","justice"],"orgTier":"ministry"}
{"path":"dilg","name":"Kagawaran ng Interior at Pamahalaang Lokal","nameEn":"Department of the Interior and Local Government","website":"https://www.dilg.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:03","interior","local-government"],"orgTier":"ministry"}
{"path":"deped","name":"Kagawaran ng Edukasyon","nameEn":"Department of Education","website":"https://www.deped.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:09","education"],"orgTier":"ministry"}
{"path":"doh","name":"Kagawaran ng Kalusugan","nameEn":"Department of Health","website":"https://www.doh.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:07","health"],"orgTier":"ministry"}
{"path":"dole","name":"Kagawaran ng Paggawa at Empleyo","nameEn":"Department of Labor and Employment","website":"https://www.dole.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:04","labour","employment"],"orgTier":"ministry"}
{"path":"dti","name":"Kagawaran ng Kalakalan at Industriya","nameEn":"Department of Trade and Industry","website":"https://www.dti.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:04","trade","industry"],"orgTier":"ministry"}
{"path":"da","name":"Kagawaran ng Agrikultura","nameEn":"Department of Agriculture","website":"https://www.da.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:04.2","agriculture"],"orgTier":"ministry"}
{"path":"denr","name":"Kagawaran ng Kalikasan at Likas na Yaman","nameEn":"Department of Environment and Natural Resources","website":"https://www.denr.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:05","environment","natural-resources"],"orgTier":"ministry"}
"""

_STATE_NDJSON = """\
{"path":"region:ncr","name":"Pambansang Punong Rehiyon (NCR)","nameEn":"National Capital Region","website":"https://www.mmda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region","capital"],"orgTier":"state"}
{"path":"region:car","name":"Cordillera Administrative Region","nameEn":"Cordillera Administrative Region","website":"https://car.neda.gov.ph/","contract":"Republic Act 6766","tags":["cofog:01","region","autonomous"],"orgTier":"state"}
{"path":"region:region-1","name":"Ilocos Region","nameEn":"Ilocos Region (Region I)","website":"https://region1.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-2","name":"Cagayan Valley","nameEn":"Cagayan Valley (Region II)","website":"https://region2.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-3","name":"Gitnang Luzon","nameEn":"Central Luzon (Region III)","website":"https://region3.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-4a","name":"CALABARZON","nameEn":"CALABARZON (Region IV-A)","website":"https://region4a.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-4b","name":"MIMAROPA","nameEn":"MIMAROPA (Region IV-B)","website":"https://region4b.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-5","name":"Bicol Region","nameEn":"Bicol Region (Region V)","website":"https://region5.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-6","name":"Kanlurang Visayas","nameEn":"Western Visayas (Region VI)","website":"https://region6.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-7","name":"Gitnang Visayas","nameEn":"Central Visayas (Region VII)","website":"https://region7.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-8","name":"Silangang Visayas","nameEn":"Eastern Visayas (Region VIII)","website":"https://region8.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-9","name":"Tangway ng Zamboanga","nameEn":"Zamboanga Peninsula (Region IX)","website":"https://region9.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-10","name":"Hilagang Mindanao","nameEn":"Northern Mindanao (Region X)","website":"https://region10.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-11","name":"Davao Region","nameEn":"Davao Region (Region XI)","website":"https://region11.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-12","name":"SOCCSKSARGEN","nameEn":"SOCCSKSARGEN (Region XII)","website":"https://region12.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:region-13","name":"Caraga","nameEn":"Caraga (Region XIII)","website":"https://region13.neda.gov.ph/","contract":"Saligang Batas ng Pilipinas 1987","tags":["cofog:01","region"],"orgTier":"state"}
{"path":"region:barmm","name":"Bangsamoro Autonomous Region in Muslim Mindanao","nameEn":"Bangsamoro Autonomous Region in Muslim Mindanao","website":"https://www.barmm.gov.ph/","contract":"Republic Act 11054","tags":["cofog:01","region","autonomous"],"orgTier":"state"}
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
    # R0: fetch full row to apply partial updates
    row = get_kotoba_client().select_first_where("vertex_gov_org", "path", path)
    if row and row.get("domain_code") == DOMAIN_CODE and row.get("owner_did") == (owner_did or PRIMARY_DID):
        for key, val in updates.items():
            row[key] = val
        get_kotoba_client().insert_row("vertex_gov_org", row)


def _get_org(path: str) -> dict[str, Any] | None:
    # R0: Multi-predicate fetch and return subset
    row = get_kotoba_client().select_first_where("vertex_gov_org", "path", path)
    if not row or row.get("domain_code") != DOMAIN_CODE or row.get("owner_did") != PRIMARY_DID:
        return None
    keys = [
        "path", "name", "name_en", "website", "contract", "tags", "org_tier",
        "site_domain_slug", "site_followed", "did_registered",
        "last_ingested_at", "last_content_hash", "last_kyumei_at",
        "last_shinka_at", "created_at",
    ]
    return {k: row.get(k) for k in keys}


def task_gov_phl_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: fetch domain_code and filter in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    existing = {
        str(r.get("path"))
        for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
    }
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_phl_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_phl_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: fetch all domain_code rows and sort/page in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
        and (not org_tier or r.get("org_tier") == org_tier)
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    total = len(filtered)
    page_rows = filtered[offset : offset + limit]
    return {
        "orgs": [
            {
                "path": str(r.get("path") or ""),
                "did": f"{PRIMARY_DID}:{str(r.get("path") or '')}",
                "name": str(r.get("name") or ""),
                "nameEn": str(r.get("name_en") or ""),
                "website": str(r.get("website") or ""),
                "didRegistered": str(r.get("did_registered") or "") == "true",
            }
            for r in page_rows
        ],
        "total": total,
    }


async def task_gov_phl_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: fetch all domain_code rows, filter and cap in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en") and str(r.get("did_registered") or "") != "true"
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    rows = filtered[:limit]
    registered: list[str] = []
    pds_results: list[dict[str, Any]] = []
    for row_dict in rows:
        row = {
            "path": str(row_dict.get("path") or ""),
            "name": str(row_dict.get("name") or ""),
            "name_en": str(row_dict.get("name_en") or ""),
            "website": str(row_dict.get("website") or ""),
            "contract": str(row_dict.get("contract") or ""),
            "tags": json.loads(str(row_dict.get("tags") or "[]")),
            "org_tier": str(row_dict.get("org_tier") or ""),
            "site_domain_slug": str(row_dict.get("site_domain_slug") or ""),
            "site_followed": str(row_dict.get("site_followed") or "false"),
            "last_ingested_at": str(row_dict.get("last_ingested_at") or ""),
            "last_content_hash": str(row_dict.get("last_content_hash") or ""),
            "last_kyumei_at": str(row_dict.get("last_kyumei_at") or ""),
            "last_shinka_at": str(row_dict.get("last_shinka_at") or ""),
            "created_at": str(row_dict.get("created_at") or _utc_now_iso()),
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


async def task_gov_phl_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: fetch all domain_code rows, filter and cap in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and str(r.get("site_followed") or "") != "true" and r.get("site_domain_slug")
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    rows = filtered[:limit]
    for row_dict in rows:
        path = str(row_dict.get("path") or "")
        slug = str(row_dict.get("site_domain_slug") or "")
        await _pds_xrpc("app.bsky.graph.follow", {"did": f"did:web:site.etzhayyim.com:{slug}"})
        row = {
            "path": path,
            "name": str(row_dict.get("name") or ""),
            "name_en": str(row_dict.get("name_en") or ""),
            "website": str(row_dict.get("website") or ""),
            "contract": str(row_dict.get("contract") or ""),
            "tags": json.loads(str(row_dict.get("tags") or "[]")),
            "org_tier": str(row_dict.get("org_tier") or ""),
            "site_domain_slug": slug,
            "site_followed": "true",
            "did_registered": str(row_dict.get("did_registered") or "false"),
            "last_ingested_at": str(row_dict.get("last_ingested_at") or ""),
            "last_content_hash": str(row_dict.get("last_content_hash") or ""),
            "last_kyumei_at": str(row_dict.get("last_kyumei_at") or ""),
            "last_shinka_at": str(row_dict.get("last_shinka_at") or ""),
            "created_at": str(row_dict.get("created_at") or _utc_now_iso()),
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


async def task_gov_phl_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: filter wet updates in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = []
    for r in all_rows:
        if not r.get("site_domain_slug"):
            continue
        lch = str(r.get("last_content_hash") or "")
        lia = str(r.get("last_ingested_at") or "")
        if not lch or not lia or lia < cutoff_iso:
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
        # R0: fetch all domain chunks, sort in Python
        chunks = get_kotoba_client().select_where("vertex_wet_chunk", "domain", slug, limit=200)
        chunks.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
        wet = chunks[0] if chunks else None
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
        markdown = str(wet.get("markdown") or "")
        content_hash = str(wet.get("content_hash") or "")
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


async def task_gov_phl_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: fetch all domain_code rows, filter and sort in Python
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


async def task_gov_phl_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_phl_seed_orgs, seedLimit)
    register = await task_gov_phl_register_dids(registerLimit)
    follow = await task_gov_phl_follow_site_deps(followLimit)
    ingest = await task_gov_phl_sync_wet_updates(ingestLimit)
    shinka = await task_gov_phl_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govPhl.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_phl_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govPhl.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_phl_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govPhl.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_phl_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govPhl.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_phl_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govPhl.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_phl_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govPhl.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_phl_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govPhl.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_phl_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govPhl.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_phl_heartbeat_tick)
