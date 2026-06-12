"""AUS Government states actor primitives.

This module moves the `did:web:aus-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:aus-state.etzhayyim.com"
DOMAIN_CODE = "aus"
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
{"path":"pmc","name":"Department of the Prime Minister and Cabinet","nameEn":"Department of the Prime Minister and Cabinet","website":"https://www.pmc.gov.au/","contract":"Public Service Act 1999","tags":["cofog:01","executive","prime-minister"],"orgTier":"ministry"}
{"path":"defence","name":"Department of Defence","nameEn":"Department of Defence","website":"https://www.defence.gov.au/","contract":"Defence Act 1903","tags":["cofog:02","defence"],"orgTier":"ministry"}
{"path":"dfat","name":"Department of Foreign Affairs and Trade","nameEn":"Department of Foreign Affairs and Trade","website":"https://www.dfat.gov.au/","contract":"Foreign Affairs and Trade Act 1985","tags":["cofog:01.2","foreign-affairs","trade"],"orgTier":"ministry"}
{"path":"treasury","name":"The Treasury","nameEn":"The Treasury","website":"https://www.treasury.gov.au/","contract":"Charter of Budget Honesty Act 1998","tags":["cofog:01.1","finance","budget"],"orgTier":"ministry"}
{"path":"ag","name":"Attorney-General's Department","nameEn":"Attorney-General's Department","website":"https://www.ag.gov.au/","contract":"Judiciary Act 1903","tags":["cofog:03","justice","law"],"orgTier":"ministry"}
{"path":"homeaffairs","name":"Department of Home Affairs","nameEn":"Department of Home Affairs","website":"https://www.homeaffairs.gov.au/","contract":"Australian Border Force Act 2015","tags":["cofog:03","interior","immigration","border"],"orgTier":"ministry"}
{"path":"health","name":"Department of Health and Aged Care","nameEn":"Department of Health and Aged Care","website":"https://www.health.gov.au/","contract":"National Health Act 1953","tags":["cofog:07","health","aged-care"],"orgTier":"ministry"}
{"path":"education","name":"Department of Education","nameEn":"Department of Education","website":"https://www.education.gov.au/","contract":"Australian Education Act 2013","tags":["cofog:09","education"],"orgTier":"ministry"}
{"path":"infrastructure","name":"Department of Infrastructure, Transport, Regional Development and Communications","nameEn":"Department of Infrastructure, Transport","website":"https://www.infrastructure.gov.au/","contract":"EPBC Act 1999","tags":["cofog:04.5","infrastructure","transport"],"orgTier":"ministry"}
{"path":"agriculture","name":"Department of Agriculture, Fisheries and Forestry","nameEn":"Department of Agriculture, Fisheries and Forestry","website":"https://www.agriculture.gov.au/","contract":"Primary Industries and Energy Research and Development Act 1989","tags":["cofog:04.2","agriculture","fisheries"],"orgTier":"ministry"}
{"path":"industry","name":"Department of Industry, Science and Resources","nameEn":"Department of Industry, Science and Resources","website":"https://www.industry.gov.au/","contract":"Industry Research and Development Act 1986","tags":["cofog:04","industry","science","resources"],"orgTier":"ministry"}
{"path":"climate","name":"Department of Climate Change, Energy, the Environment and Water","nameEn":"Department of Climate Change, Energy, the Environment and Water","website":"https://www.dcceew.gov.au/","contract":"Climate Change Act 2022","tags":["cofog:05","environment","climate","energy","water"],"orgTier":"ministry"}
{"path":"socialservices","name":"Department of Social Services","nameEn":"Department of Social Services","website":"https://www.dss.gov.au/","contract":"Social Security Act 1991","tags":["cofog:10","social-services"],"orgTier":"ministry"}
{"path":"aec","name":"Australian Electoral Commission","nameEn":"Australian Electoral Commission","website":"https://www.aec.gov.au/","contract":"Commonwealth Electoral Act 1918","tags":["cofog:01","elections"],"orgTier":"agency"}
{"path":"ato","name":"Australian Taxation Office","nameEn":"Australian Taxation Office","website":"https://www.ato.gov.au/","contract":"Taxation Administration Act 1953","tags":["cofog:01.1","taxation"],"orgTier":"agency"}
{"path":"hca","name":"High Court of Australia","nameEn":"High Court of Australia","website":"https://www.hcourt.gov.au/","contract":"Judiciary Act 1903","tags":["cofog:03","judiciary","supreme-court"],"orgTier":"agency"}
"""

_STATE_NDJSON = """\
{"path":"state:nsw","name":"New South Wales","nameEn":"New South Wales","website":"https://www.nsw.gov.au/","contract":"Constitution Act 1902 (NSW)","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:vic","name":"Victoria","nameEn":"Victoria","website":"https://www.vic.gov.au/","contract":"Constitution Act 1975 (VIC)","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:qld","name":"Queensland","nameEn":"Queensland","website":"https://www.qld.gov.au/","contract":"Constitution of Queensland 2001","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:wa","name":"Western Australia","nameEn":"Western Australia","website":"https://www.wa.gov.au/","contract":"Constitution Act 1889 (WA)","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:sa","name":"South Australia","nameEn":"South Australia","website":"https://www.sa.gov.au/","contract":"Constitution Act 1934 (SA)","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:tas","name":"Tasmania","nameEn":"Tasmania","website":"https://www.tas.gov.au/","contract":"Constitution Act 1934 (TAS)","tags":["cofog:01","state","island"],"orgTier":"state"}
{"path":"state:act","name":"Australian Capital Territory","nameEn":"Australian Capital Territory","website":"https://www.act.gov.au/","contract":"Australian Capital Territory (Self-Government) Act 1988","tags":["cofog:01","territory","capital"],"orgTier":"state"}
{"path":"state:nt","name":"Northern Territory","nameEn":"Northern Territory","website":"https://nt.gov.au/","contract":"Northern Territory (Self-Government) Act 1978","tags":["cofog:01","territory"],"orgTier":"state"}
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


def _direct_fetch_hash(url: str, timeout: int = 10) -> tuple[str, str]:
    """Fetch url and return (md5_content_hash, text_snippet). Returns ('', '') on failure."""
    if not url or not url.startswith("http"):
        return "", ""
    try:
        req = _u_req.Request(url, headers={"User-Agent": "GovBot/1.0"})
        with _u_req.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
        content_hash = hashlib.md5(body).hexdigest()
        text = re.sub(r"<[^>]+>", " ", body.decode("utf-8", errors="replace"))
        text = re.sub(r"\s+", " ", text).strip()[:300]
        return content_hash, text
    except Exception:
        return "", ""


def _update_gov_org_fields(path: str, fields: dict[str, str]) -> None:
    allowed = {
        "site_followed",
        "did_registered",
        "last_ingested_at",
        "last_content_hash",
        "last_kyumei_at",
        "last_shinka_at",
    }
    updates = {k: str(v) for k, v in fields.items() if k in allowed}
    if not path or not updates:
        return
    # R0: fetch existing row to update
    row = get_kotoba_client().select_first_where(
        "vertex_gov_org", "path", path,
        columns=["vertex_id", "sensitivity_ord", "owner_did", "path", "name", "name_en", "website", "contract", "tags", "domain_code", "org_tier", "site_domain_slug", "site_followed", "did_registered", "last_ingested_at", "last_content_hash", "last_kyumei_at", "last_shinka_at", "created_at", "props"]
    )
    if row and row.get("domain_code") == DOMAIN_CODE and row.get("owner_did") == PRIMARY_DID:
        row.update(updates)
        get_kotoba_client().insert_row("vertex_gov_org", row)


def _get_org(path: str) -> dict[str, Any] | None:
    # R0: in-Python filter for domain_code and owner_did
    row = get_kotoba_client().select_first_where(
        "vertex_gov_org", "path", path,
        columns=["path", "name", "name_en", "website", "contract", "tags", "org_tier",
                 "site_domain_slug", "site_followed", "did_registered",
                 "last_ingested_at", "last_content_hash", "last_kyumei_at",
                 "last_shinka_at", "created_at", "domain_code", "owner_did"]
    )
    if not row or row.get("domain_code") != DOMAIN_CODE or row.get("owner_did") != PRIMARY_DID:
        return None
    keys = [
        "path", "name", "name_en", "website", "contract", "tags", "org_tier",
        "site_domain_slug", "site_followed", "did_registered",
        "last_ingested_at", "last_content_hash", "last_kyumei_at",
        "last_shinka_at", "created_at",
    ]
    return {k: row.get(k) for k in keys}


def task_gov_aus_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: in-Python filter for owner_did, name_en
    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    existing = {str(r.get("path") or "") for r in rows if r.get("owner_did") == PRIMARY_DID and str(r.get("name_en") or "") != ""}
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_aus_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_aus_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: in-Python filter, order, count, and offset
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [r for r in all_rows if r.get("owner_did") == PRIMARY_DID and str(r.get("name_en") or "") != ""]
    if org_tier:
        filtered = [r for r in filtered if r.get("org_tier") == org_tier]
    total = len(filtered)
    filtered.sort(key=lambda r: str(r.get("path") or ""))
    page = filtered[offset : offset + limit]
    return {
        "orgs": [
            {
                "path": str(r.get("path") or ""),
                "did": f"{PRIMARY_DID}:{str(r.get('path') or '')}",
                "name": str(r.get("name") or ""),
                "nameEn": str(r.get("name_en") or ""),
                "website": str(r.get("website") or ""),
                "didRegistered": str(r.get("did_registered") or "") == "true",
            }
            for r in page
        ],
        "total": total,
    }


async def task_gov_aus_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: in-Python filter and order
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [r for r in all_rows if r.get("owner_did") == PRIMARY_DID and str(r.get("name_en") or "") != "" and str(r.get("did_registered") or "") != "true"]
    filtered.sort(key=lambda r: str(r.get("path") or ""))
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


async def task_gov_aus_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: in-Python filter and order
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [r for r in all_rows if r.get("owner_did") == PRIMARY_DID and str(r.get("site_followed") or "") != "true" and str(r.get("site_domain_slug") or "") != ""]
    filtered.sort(key=lambda r: str(r.get("path") or ""))
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


async def task_gov_aus_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: in-Python filter and order
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = []
    for r in all_rows:
        if r.get("owner_did") == PRIMARY_DID and str(r.get("site_domain_slug") or "") != "":
            lia = str(r.get("last_ingested_at") or "")
            if not lia or lia < cutoff_iso:
                filtered.append(r)
    filtered.sort(key=lambda r: str(r.get("last_ingested_at") or ""))
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
        if not path or not slug:
            continue
        checked += 1
        # R0: in-Python limit/sort
        wet_rows = get_kotoba_client().select_where("vertex_wet_chunk", "domain", slug, limit=100)
        wet_rows.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
        wet = wet_rows[0] if wet_rows else None
        if not wet:
            fetch_hash, fetch_text = _direct_fetch_hash(website)
            if fetch_hash:
                fields: dict[str, str] = {"last_ingested_at": now, "last_content_hash": fetch_hash}
                _update_gov_org_fields(path, fields)
                if fetch_hash != last_hash:
                    updated += 1
                    text = f"{name_en} - official site updated\n{fetch_text[:200]}..."
                    org_did = f"{PRIMARY_DID}:{path}"
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
                _update_gov_org_fields(path, {"last_ingested_at": now})
            continue
        markdown = str(wet.get("markdown") or "")
        content_hash = str(wet.get("content_hash") or "")
        fields = {"last_ingested_at": now}
        if content_hash:
            fields["last_content_hash"] = content_hash
        _update_gov_org_fields(path, fields)
        if content_hash and content_hash != last_hash:
            updated += 1
            summary = re.sub(r"\s+", " ", markdown)[:200]
            text = f"{name_en} - official site updated\n{summary}..."
            org_did = f"{PRIMARY_DID}:{path}"
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


async def task_gov_aus_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: in-Python filter and order
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [r for r in all_rows if r.get("owner_did") == PRIMARY_DID and str(r.get("did_registered") or "") == "true"]
    filtered.sort(key=lambda r: str(r.get("last_shinka_at") or ""))
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


async def task_gov_aus_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_aus_seed_orgs, seedLimit)
    register = await task_gov_aus_register_dids(registerLimit)
    follow = await task_gov_aus_follow_site_deps(followLimit)
    ingest = await task_gov_aus_sync_wet_updates(ingestLimit)
    shinka = await task_gov_aus_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govAus.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_aus_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAus.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_aus_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAus.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_aus_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAus.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_aus_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAus.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_aus_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAus.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_aus_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAus.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_aus_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAus.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_aus_heartbeat_tick)
