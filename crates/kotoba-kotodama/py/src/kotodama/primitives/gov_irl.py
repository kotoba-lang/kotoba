"""IRL Government states actor primitives.

This module moves the `did:web:irl-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:irl-state.etzhayyim.com"
DOMAIN_CODE = "irl"
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
{"path":"taoiseach","name":"Roinn an Taoisigh","nameEn":"Department of the Taoiseach","website":"https://www.gov.ie/en/organisation/department-of-the-taoiseach/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:01","executive"],"orgTier":"ministry"}
{"path":"foreign-affairs","name":"An Roinn Gnóthaí Eachtracha","nameEn":"Department of Foreign Affairs","website":"https://www.dfa.ie/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:01.2","foreign-affairs"],"orgTier":"ministry"}
{"path":"defence","name":"An Roinn Cosanta","nameEn":"Department of Defence","website":"https://www.gov.ie/en/organisation/department-of-defence/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:02","defence"],"orgTier":"ministry"}
{"path":"finance","name":"An Roinn Airgeadais","nameEn":"Department of Finance","website":"https://www.gov.ie/en/organisation/department-of-finance/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:01.1","finance"],"orgTier":"ministry"}
{"path":"justice","name":"An Roinn Dlí agus Cirt","nameEn":"Department of Justice","website":"https://www.gov.ie/en/organisation/department-of-justice/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:03","justice","police"],"orgTier":"ministry"}
{"path":"housing-local-government","name":"An Roinn Tithíochta, Rialtais Áitiúil agus Oidhreachta","nameEn":"Department of Housing, Local Government and Heritage","website":"https://www.gov.ie/en/organisation/department-of-housing-local-government-and-heritage/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:06","housing","local-gov"],"orgTier":"ministry"}
{"path":"education","name":"An Roinn Oideachais","nameEn":"Department of Education","website":"https://www.gov.ie/en/organisation/department-of-education/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:09","education"],"orgTier":"ministry"}
{"path":"health","name":"An Roinn Sláinte","nameEn":"Department of Health","website":"https://www.gov.ie/en/organisation/department-of-health/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:07","health"],"orgTier":"ministry"}
{"path":"agriculture-food-marine","name":"An Roinn Talmhaíochta, Bia agus Mara","nameEn":"Department of Agriculture, Food and the Marine","website":"https://www.gov.ie/en/organisation/department-of-agriculture-food-and-the-marine/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:04.2","agriculture","food","marine"],"orgTier":"ministry"}
{"path":"transport","name":"An Roinn Iompair","nameEn":"Department of Transport","website":"https://www.gov.ie/en/organisation/department-of-transport/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:04","transport"],"orgTier":"ministry"}
{"path":"environment-climate-communications","name":"An Roinn Comhshaoil, Aeráide agus Cumarsáide","nameEn":"Department of the Environment, Climate and Communications","website":"https://www.gov.ie/en/organisation/department-of-the-environment-climate-and-communications/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:05","environment","climate","communications"],"orgTier":"ministry"}
{"path":"social-protection","name":"An Roinn Coimirce Sóisialaí","nameEn":"Department of Social Protection","website":"https://www.gov.ie/en/organisation/department-of-employment-affairs-and-social-protection/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:07","social-protection"],"orgTier":"ministry"}
{"path":"enterprise-trade-employment","name":"An Roinn Fiontar, Trádála agus Fostaíochta","nameEn":"Department of Enterprise, Trade and Employment","website":"https://www.gov.ie/en/organisation/department-of-enterprise-trade-and-employment/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:04","enterprise","trade","employment"],"orgTier":"ministry"}
{"path":"further-higher-education","name":"An Roinn Breisoideachais agus Ardoideachais","nameEn":"Department of Further and Higher Education, Research, Innovation and Science","website":"https://www.gov.ie/en/organisation/department-of-further-and-higher-education-research-innovation-and-science/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:09","higher-education","research","innovation"],"orgTier":"ministry"}
{"path":"children-equality-disability-integration","name":"An Roinn Leanaí, Comhionannais, Míchumais, Lánpháirtíochta agus Óige","nameEn":"Department of Children, Equality, Disability, Integration and Youth","website":"https://www.gov.ie/en/organisation/department-of-children-equality-disability-integration-and-youth/","contract":"Bunreacht na hÉireann Art. 28","tags":["cofog:07","children","equality","youth"],"orgTier":"ministry"}
"""

_STATE_NDJSON = """\
{"path":"county:carlow","name":"Contae Cheatharlach","nameEn":"County Carlow","website":"https://www.carlow.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:cavan","name":"Contae an Chabháin","nameEn":"County Cavan","website":"https://www.cavancoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:clare","name":"Contae an Chláir","nameEn":"County Clare","website":"https://www.clare.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:cork","name":"Contae Chorcaí","nameEn":"County Cork","website":"https://www.corkcoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:donegal","name":"Contae Dhún na nGall","nameEn":"County Donegal","website":"https://www.donegalcoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:dublin","name":"Contae Átha Cliath","nameEn":"County Dublin","website":"https://www.dlrcoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5","capital"],"orgTier":"state"}
{"path":"county:galway","name":"Contae na Gaillimhe","nameEn":"County Galway","website":"https://www.galwaycoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:kerry","name":"Contae Chiarraí","nameEn":"County Kerry","website":"https://www.kerrycoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:kildare","name":"Contae Chill Dara","nameEn":"County Kildare","website":"https://www.kildarecoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:kilkenny","name":"Contae Chill Chainnigh","nameEn":"County Kilkenny","website":"https://www.kilkennycoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:laois","name":"Contae Laoise","nameEn":"County Laois","website":"https://www.laois.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:leitrim","name":"Contae Liatroma","nameEn":"County Leitrim","website":"https://www.leitrimcoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:limerick","name":"Contae Luimnigh","nameEn":"County Limerick","website":"https://www.limerick.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:longford","name":"Contae an Longfoirt","nameEn":"County Longford","website":"https://www.longfordcoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:louth","name":"Contae Lú","nameEn":"County Louth","website":"https://www.louthcoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:mayo","name":"Contae Mhaigh Eo","nameEn":"County Mayo","website":"https://www.mayo.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:meath","name":"Contae na Mí","nameEn":"County Meath","website":"https://www.meath.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:monaghan","name":"Contae Mhuineacháin","nameEn":"County Monaghan","website":"https://www.monaghan.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:offaly","name":"Contae Uíbh Fhailí","nameEn":"County Offaly","website":"https://www.offaly.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:roscommon","name":"Contae Ros Comáin","nameEn":"County Roscommon","website":"https://www.roscommoncoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:sligo","name":"Contae Shligigh","nameEn":"County Sligo","website":"https://www.sligococo.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:tipperary","name":"Contae Thiobraid Árann","nameEn":"County Tipperary","website":"https://www.tipperarycoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:waterford","name":"Contae Phort Láirge","nameEn":"County Waterford","website":"https://www.waterfordcouncil.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:westmeath","name":"Contae na hIarmhí","nameEn":"County Westmeath","website":"https://www.westmeathcoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:wexford","name":"Contae Loch Garman","nameEn":"County Wexford","website":"https://www.wexfordcoco.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
{"path":"county:wicklow","name":"Contae Chill Mhantáin","nameEn":"County Wicklow","website":"https://www.wicklow.ie/","contract":"Local Government Act 2001","tags":["cofog:01","county","l5"],"orgTier":"state"}
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
    # R0: fetch with single equality, filter by domain/owner, then upsert
    rows = get_kotoba_client().select_where("vertex_gov_org", "path", path, limit=10)
    for row in rows:
        if row.get("domain_code") == DOMAIN_CODE and row.get("owner_did") == PRIMARY_DID:
            row.update(updates)
            get_kotoba_client().insert_row("vertex_gov_org", row)


def _get_org(path: str) -> dict[str, Any] | None:
    # R0: fetch with single equality, apply multi-predicate in Python
    rows = get_kotoba_client().select_where("vertex_gov_org", "path", path, limit=10)
    keys = [
        "path", "name", "name_en", "website", "contract", "tags", "org_tier",
        "site_domain_slug", "site_followed", "did_registered",
        "last_ingested_at", "last_content_hash", "last_kyumei_at",
        "last_shinka_at", "created_at",
    ]
    for r in rows:
        if r.get("domain_code") == DOMAIN_CODE and r.get("owner_did") == PRIMARY_DID:
            return {k: r.get(k) for k in keys}
    return None


def task_gov_irl_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: fetch by domain_code, filter by owner_did and name_en in Python
    db_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    existing = {
        str(r.get("path")) for r in db_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
    }
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_irl_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_irl_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: fetch by domain_code, apply filters, ordering, pagination and counting in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = []
    for r in all_rows:
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en"):
            if not org_tier or r.get("org_tier") == org_tier:
                filtered.append(r)
    total = len(filtered)
    filtered.sort(key=lambda x: str(x.get("path") or ""))
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


async def task_gov_irl_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: fetch by domain_code, apply filters, ordering and limit in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en") and r.get("did_registered") != "true"
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


async def task_gov_irl_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: fetch by domain_code, apply filters, ordering and limit in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID
        and r.get("site_followed") != "true"
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


async def task_gov_irl_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: fetch by domain_code, apply complex date filter, ordering and limit in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = []
    for r in all_rows:
        if r.get("owner_did") == PRIMARY_DID and r.get("site_domain_slug"):
            last_ingested = r.get("last_ingested_at")
            if not last_ingested or str(last_ingested) < cutoff_iso:
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
        if not path or not slug:
            continue
        checked += 1
        # R0: fetch by domain, order by crawled_at DESC in Python
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


async def task_gov_irl_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: fetch by domain_code, filter, order by last_shinka_at in Python
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("did_registered") == "true"
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


async def task_gov_irl_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_irl_seed_orgs, seedLimit)
    register = await task_gov_irl_register_dids(registerLimit)
    follow = await task_gov_irl_follow_site_deps(followLimit)
    ingest = await task_gov_irl_sync_wet_updates(ingestLimit)
    shinka = await task_gov_irl_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govIrl.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_irl_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIrl.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_irl_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIrl.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_irl_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIrl.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_irl_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIrl.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_irl_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIrl.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_irl_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIrl.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_irl_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIrl.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_irl_heartbeat_tick)
