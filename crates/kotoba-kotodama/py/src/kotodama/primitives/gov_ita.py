"""ITA Government states actor primitives.

This module moves the `did:web:ita-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:ita-state.etzhayyim.com"
DOMAIN_CODE = "ita"
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
{"path":"presidenza","name":"Presidenza del Consiglio dei Ministri","nameEn":"Presidency of the Council of Ministers","website":"https://www.governo.it/","contract":"Costituzione Art. 95","tags":["cofog:01","executive","prime-minister"],"orgTier":"ministry"}
{"path":"difesa","name":"Ministero della Difesa","nameEn":"Ministry of Defence","website":"https://www.difesa.it/","contract":"Costituzione Art. 87","tags":["cofog:02","defence","military"],"orgTier":"ministry"}
{"path":"maeci","name":"Ministero degli Affari Esteri e della Cooperazione Internazionale","nameEn":"Ministry of Foreign Affairs and International Cooperation","website":"https://www.esteri.it/","contract":"Costituzione Art. 80","tags":["cofog:01.2","foreign-affairs","diplomacy"],"orgTier":"ministry"}
{"path":"mef","name":"Ministero dell'Economia e delle Finanze","nameEn":"Ministry of Economy and Finance","website":"https://www.mef.gov.it/","contract":"Costituzione Art. 81","tags":["cofog:01.1","finance","economy","taxation"],"orgTier":"ministry"}
{"path":"giustizia","name":"Ministero della Giustizia","nameEn":"Ministry of Justice","website":"https://www.giustizia.it/","contract":"Costituzione Art. 110","tags":["cofog:03","justice","courts","prisons"],"orgTier":"ministry"}
{"path":"interno","name":"Ministero dell'Interno","nameEn":"Ministry of the Interior","website":"https://www.interno.gov.it/","contract":"Costituzione Art. 14","tags":["cofog:03","interior","police","immigration","civil-protection"],"orgTier":"ministry"}
{"path":"salute","name":"Ministero della Salute","nameEn":"Ministry of Health","website":"https://www.salute.gov.it/","contract":"Costituzione Art. 32","tags":["cofog:07","health","ssn"],"orgTier":"ministry"}
{"path":"istruzione","name":"Ministero dell'Istruzione e del Merito","nameEn":"Ministry of Education and Merit","website":"https://www.miur.gov.it/","contract":"Costituzione Art. 33","tags":["cofog:09","education","schools"],"orgTier":"ministry"}
{"path":"ricerca","name":"Ministero dell'Università e della Ricerca","nameEn":"Ministry of University and Research","website":"https://www.mur.gov.it/","contract":"Costituzione Art. 33","tags":["cofog:09","university","research"],"orgTier":"ministry"}
{"path":"lavoro","name":"Ministero del Lavoro e delle Politiche Sociali","nameEn":"Ministry of Labour and Social Policies","website":"https://www.lavoro.gov.it/","contract":"Costituzione Art. 35","tags":["cofog:04","labour","social"],"orgTier":"ministry"}
{"path":"ambiente","name":"Ministero dell'Ambiente e della Sicurezza Energetica","nameEn":"Ministry of Environment and Energy Security","website":"https://www.mase.gov.it/","contract":"Costituzione Art. 9","tags":["cofog:05","environment","energy","climate"],"orgTier":"ministry"}
{"path":"agricoltura","name":"Ministero dell'Agricoltura, della Sovranità alimentare e delle Foreste","nameEn":"Ministry of Agriculture","website":"https://www.masaf.gov.it/","contract":"Costituzione Art. 44","tags":["cofog:04.2","agriculture","food","forestry"],"orgTier":"ministry"}
{"path":"mit","name":"Ministero delle Infrastrutture e dei Trasporti","nameEn":"Ministry of Infrastructure and Transport","website":"https://www.mit.gov.it/","contract":"Costituzione Art. 117","tags":["cofog:04.5","infrastructure","transport"],"orgTier":"ministry"}
{"path":"camera","name":"Camera dei Deputati","nameEn":"Chamber of Deputies","website":"https://www.camera.it/","contract":"Costituzione Art. 56","tags":["cofog:01","legislature","lower-house"],"orgTier":"agency"}
{"path":"senato","name":"Senato della Repubblica","nameEn":"Senate of the Republic","website":"https://www.senato.it/","contract":"Costituzione Art. 57","tags":["cofog:01","legislature","upper-house"],"orgTier":"agency"}
{"path":"corte-costituzionale","name":"Corte Costituzionale","nameEn":"Constitutional Court","website":"https://www.cortecostituzionale.it/","contract":"Costituzione Art. 134","tags":["cofog:03","judiciary","constitutional-court"],"orgTier":"agency"}
"""

_STATE_NDJSON = """\
{"path":"regione:abruzzo","name":"Regione Abruzzo","nameEn":"Abruzzo","website":"https://www.regione.abruzzo.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:basilicata","name":"Regione Basilicata","nameEn":"Basilicata","website":"https://www.regione.basilicata.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:calabria","name":"Regione Calabria","nameEn":"Calabria","website":"https://www.regione.calabria.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:campania","name":"Regione Campania","nameEn":"Campania","website":"https://www.regione.campania.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:emilia-romagna","name":"Regione Emilia-Romagna","nameEn":"Emilia-Romagna","website":"https://www.regione.emilia-romagna.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:friuli-venezia-giulia","name":"Regione Friuli Venezia Giulia","nameEn":"Friuli Venezia Giulia","website":"https://www.regione.fvg.it/","contract":"Costituzione Art. 116 (speciale)","tags":["cofog:01","regione","l5","special-statute"],"orgTier":"state"}
{"path":"regione:lazio","name":"Regione Lazio","nameEn":"Lazio","website":"https://www.regione.lazio.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5","capital-region"],"orgTier":"state"}
{"path":"regione:liguria","name":"Regione Liguria","nameEn":"Liguria","website":"https://www.regione.liguria.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:lombardia","name":"Regione Lombardia","nameEn":"Lombardy","website":"https://www.regione.lombardia.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5","largest"],"orgTier":"state"}
{"path":"regione:marche","name":"Regione Marche","nameEn":"Marche","website":"https://www.regione.marche.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:molise","name":"Regione Molise","nameEn":"Molise","website":"https://www.regione.molise.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:piemonte","name":"Regione Piemonte","nameEn":"Piedmont","website":"https://www.regione.piemonte.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:puglia","name":"Regione Puglia","nameEn":"Apulia","website":"https://www.regione.puglia.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:sardegna","name":"Regione Sardegna","nameEn":"Sardinia","website":"https://www.regione.sardegna.it/","contract":"Costituzione Art. 116 (speciale)","tags":["cofog:01","regione","l5","special-statute","island"],"orgTier":"state"}
{"path":"regione:sicilia","name":"Regione Siciliana","nameEn":"Sicily","website":"https://www.regione.sicilia.it/","contract":"Costituzione Art. 116 (speciale)","tags":["cofog:01","regione","l5","special-statute","island"],"orgTier":"state"}
{"path":"regione:toscana","name":"Regione Toscana","nameEn":"Tuscany","website":"https://www.regione.toscana.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:trentino-alto-adige","name":"Regione Trentino-Alto Adige","nameEn":"Trentino-Alto Adige / Südtirol","website":"https://www.regione.taa.it/","contract":"Costituzione Art. 116 (speciale)","tags":["cofog:01","regione","l5","special-statute","bilingual"],"orgTier":"state"}
{"path":"regione:umbria","name":"Regione Umbria","nameEn":"Umbria","website":"https://www.regione.umbria.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
{"path":"regione:valle-d-aosta","name":"Regione Valle d'Aosta","nameEn":"Aosta Valley","website":"https://www.regione.vda.it/","contract":"Costituzione Art. 116 (speciale)","tags":["cofog:01","regione","l5","special-statute","bilingual"],"orgTier":"state"}
{"path":"regione:veneto","name":"Regione Veneto","nameEn":"Veneto","website":"https://www.regione.veneto.it/","contract":"Costituzione Art. 114-133","tags":["cofog:01","regione","l5"],"orgTier":"state"}
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
    set_sql = ", ".join(f"{key} = %({key})s" for key in updates)
    params: dict[str, Any] = {
        "domain_code": DOMAIN_CODE,
        "owner_did": PRIMARY_DID,
        "path": path,
        **updates,
    }
    # R0: fetch with single equality, filter by domain/owner, then upsert
    rows = get_kotoba_client().select_where("vertex_gov_org", "path", path, limit=10)
    for row in rows:
        if row.get("domain_code") == DOMAIN_CODE and row.get("owner_did") == PRIMARY_DID:
            row.update(updates)
            get_kotoba_client().insert_row("vertex_gov_org", row)


def _get_org(path: str) -> dict[str, Any] | None:
    rows = get_kotoba_client().select_where("vertex_gov_org", "path", path, limit=10)
    row = next((r for r in rows if r.get("domain_code") == DOMAIN_CODE and r.get("owner_did") == PRIMARY_DID), None)
    if not row:
        return None
    keys = [
        "path", "name", "name_en", "website", "contract", "tags", "org_tier",
        "site_domain_slug", "site_followed", "did_registered",
        "last_ingested_at", "last_content_hash", "last_kyumei_at",
        "last_shinka_at", "created_at",
    ]
    return {k: row.get(k) for k in keys}


def task_gov_ita_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: in-Python filter
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


def task_gov_ita_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_ita_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: in-Python filter
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
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
                "path": str(r.get("path") or ""),
                "did": f"{PRIMARY_DID}:{str(r.get('path') or '')}",
                "name": str(r.get("name") or ""),
                "nameEn": str(r.get("name_en") or ""),
                "website": str(r.get("website") or ""),
                "didRegistered": str(r.get("did_registered") or "") == "true",
            }
            for r in rows
        ],
        "total": total,
    }


async def task_gov_ita_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: in-Python filter
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID
        and r.get("name_en")
        and r.get("did_registered") != "true"
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    rows = filtered[:limit]
    registered: list[str] = []
    pds_results: list[dict[str, Any]] = []
    for r in rows:
        tags_raw = r.get("tags") or "[]"
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        row = {
            "path": str(r.get("path") or ""),
            "name": str(r.get("name") or ""),
            "name_en": str(r.get("name_en") or ""),
            "website": str(r.get("website") or ""),
            "contract": str(r.get("contract") or ""),
            "tags": tags,
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


async def task_gov_ita_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: in-Python filter
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
        tags_raw = r.get("tags") or "[]"
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        row = {
            "path": path,
            "name": str(r.get("name") or ""),
            "name_en": str(r.get("name_en") or ""),
            "website": str(r.get("website") or ""),
            "contract": str(r.get("contract") or ""),
            "tags": tags,
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


async def task_gov_ita_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: in-Python filter
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID
        and r.get("site_domain_slug")
        and (
            not r.get("last_ingested_at")
            or r.get("last_ingested_at") == ""
            or str(r.get("last_ingested_at") or "") < cutoff_iso
        )
    ]
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
        # R0: in-Python filter
        chunk_rows = get_kotoba_client().select_where("vertex_wet_chunk", "domain", slug, limit=100)
        chunk_rows.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
        wet = chunk_rows[0] if chunk_rows else None
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


async def task_gov_ita_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: in-Python filter
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID
        and r.get("did_registered") == "true"
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


async def task_gov_ita_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_ita_seed_orgs, seedLimit)
    register = await task_gov_ita_register_dids(registerLimit)
    follow = await task_gov_ita_follow_site_deps(followLimit)
    ingest = await task_gov_ita_sync_wet_updates(ingestLimit)
    shinka = await task_gov_ita_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govIta.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ita_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIta.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ita_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIta.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ita_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIta.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ita_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIta.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ita_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIta.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ita_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIta.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ita_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIta.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ita_heartbeat_tick)
