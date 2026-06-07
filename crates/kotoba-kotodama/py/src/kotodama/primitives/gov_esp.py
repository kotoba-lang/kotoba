"""ESP Government states actor primitives.

This module moves the `did:web:esp-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:esp-state.etzhayyim.com"
DOMAIN_CODE = "esp"
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
{"path":"presidencia","name":"Presidencia del Gobierno","nameEn":"Presidency of the Government","website":"https://www.lamoncloa.gob.es/","contract":"Constitución Art. 98","tags":["cofog:01","executive","prime-minister"],"orgTier":"ministry"}
{"path":"maec","name":"Ministerio de Asuntos Exteriores, Unión Europea y Cooperación","nameEn":"Ministry of Foreign Affairs, European Union and Cooperation","website":"https://www.exteriores.gob.es/","contract":"Constitución Art. 97","tags":["cofog:01.2","foreign-affairs","eu","development"],"orgTier":"ministry"}
{"path":"defensa","name":"Ministerio de Defensa","nameEn":"Ministry of Defence","website":"https://www.defensa.gob.es/","contract":"Constitución Art. 8","tags":["cofog:02","defence","military"],"orgTier":"ministry"}
{"path":"hacienda","name":"Ministerio de Hacienda","nameEn":"Ministry of Finance","website":"https://www.hacienda.gob.es/","contract":"Constitución Art. 133","tags":["cofog:01.1","finance","budget","taxation"],"orgTier":"ministry"}
{"path":"justicia","name":"Ministerio de Justicia","nameEn":"Ministry of Justice","website":"https://www.mjusticia.gob.es/","contract":"Constitución Art. 117","tags":["cofog:03","justice","judiciary"],"orgTier":"ministry"}
{"path":"interior","name":"Ministerio del Interior","nameEn":"Ministry of the Interior","website":"https://www.interior.gob.es/","contract":"Constitución Art. 104","tags":["cofog:03","interior","police","security"],"orgTier":"ministry"}
{"path":"educacion","name":"Ministerio de Educación, Formación Profesional y Deportes","nameEn":"Ministry of Education, Vocational Training and Sports","website":"https://www.educacion.gob.es/","contract":"Constitución Art. 27","tags":["cofog:09","education","vocational","sports"],"orgTier":"ministry"}
{"path":"sanidad","name":"Ministerio de Sanidad","nameEn":"Ministry of Health","website":"https://www.sanidad.gob.es/","contract":"Constitución Art. 43","tags":["cofog:07","health","public-health"],"orgTier":"ministry"}
{"path":"trabajo","name":"Ministerio de Trabajo y Economía Social","nameEn":"Ministry of Labour and Social Economy","website":"https://www.mites.gob.es/","contract":"Constitución Art. 35","tags":["cofog:04","labour","employment","social-economy"],"orgTier":"ministry"}
{"path":"industria","name":"Ministerio de Industria y Turismo","nameEn":"Ministry of Industry and Tourism","website":"https://www.mincotur.gob.es/","contract":"Constitución Art. 38","tags":["cofog:04.3","industry","tourism","smes"],"orgTier":"ministry"}
{"path":"agricultura","name":"Ministerio de Agricultura, Pesca y Alimentación","nameEn":"Ministry of Agriculture, Fisheries and Food","website":"https://www.mapa.gob.es/","contract":"Constitución Art. 130","tags":["cofog:04.2","agriculture","fisheries","food"],"orgTier":"ministry"}
{"path":"transicion","name":"Ministerio para la Transición Ecológica y el Reto Demográfico","nameEn":"Ministry for Ecological Transition and Demographic Challenge","website":"https://www.miteco.gob.es/","contract":"Constitución Art. 45","tags":["cofog:05","environment","energy","climate"],"orgTier":"ministry"}
"""

_STATE_NDJSON = """\
{"path":"comunidad:andalucia","name":"Junta de Andalucía","nameEn":"Regional Government of Andalusia","website":"https://www.juntadeandalucia.es/","contract":"Estatuto de Autonomía de Andalucía","tags":["cofog:01","autonomous-community","south"],"orgTier":"state"}
{"path":"comunidad:aragon","name":"Gobierno de Aragón","nameEn":"Government of Aragon","website":"https://www.aragon.es/","contract":"Estatuto de Autonomía de Aragón","tags":["cofog:01","autonomous-community","northeast"],"orgTier":"state"}
{"path":"comunidad:asturias","name":"Gobierno del Principado de Asturias","nameEn":"Government of the Principality of Asturias","website":"https://www.asturias.es/","contract":"Estatuto de Autonomía de Asturias","tags":["cofog:01","autonomous-community","north","principality"],"orgTier":"state"}
{"path":"comunidad:baleares","name":"Govern de les Illes Balears","nameEn":"Government of the Balearic Islands","website":"https://www.caib.es/","contract":"Estatut d'Autonomia de les Illes Balears","tags":["cofog:01","autonomous-community","islands","mediterranean"],"orgTier":"state"}
{"path":"comunidad:canarias","name":"Gobierno de Canarias","nameEn":"Government of the Canary Islands","website":"https://www.gobiernodecanarias.org/","contract":"Estatuto de Autonomía de Canarias","tags":["cofog:01","autonomous-community","islands","atlantic"],"orgTier":"state"}
{"path":"comunidad:cantabria","name":"Gobierno de Cantabria","nameEn":"Government of Cantabria","website":"https://www.cantabria.es/","contract":"Estatuto de Autonomía para Cantabria","tags":["cofog:01","autonomous-community","north","coast"],"orgTier":"state"}
{"path":"comunidad:castilla-la-mancha","name":"Gobierno de Castilla-La Mancha","nameEn":"Government of Castilla-La Mancha","website":"https://www.castillalamancha.es/","contract":"Estatuto de Autonomía de Castilla-La Mancha","tags":["cofog:01","autonomous-community","central"],"orgTier":"state"}
{"path":"comunidad:castilla-y-leon","name":"Junta de Castilla y León","nameEn":"Regional Government of Castile and León","website":"https://www.jcyl.es/","contract":"Estatuto de Autonomía de Castilla y León","tags":["cofog:01","autonomous-community","central","largest"],"orgTier":"state"}
{"path":"comunidad:cataluna","name":"Generalitat de Catalunya","nameEn":"Government of Catalonia","website":"https://www.gencat.cat/","contract":"Estatut d'Autonomia de Catalunya","tags":["cofog:01","autonomous-community","northeast","catalan"],"orgTier":"state"}
{"path":"comunidad:extremadura","name":"Junta de Extremadura","nameEn":"Regional Government of Extremadura","website":"https://www.juntaex.es/","contract":"Estatuto de Autonomía de Extremadura","tags":["cofog:01","autonomous-community","west"],"orgTier":"state"}
{"path":"comunidad:galicia","name":"Xunta de Galicia","nameEn":"Government of Galicia","website":"https://www.xunta.gal/","contract":"Estatuto de Autonomía de Galicia","tags":["cofog:01","autonomous-community","northwest","galician"],"orgTier":"state"}
{"path":"comunidad:la-rioja","name":"Gobierno de La Rioja","nameEn":"Government of La Rioja","website":"https://www.larioja.org/","contract":"Estatuto de Autonomía de La Rioja","tags":["cofog:01","autonomous-community","north","wine"],"orgTier":"state"}
{"path":"comunidad:madrid","name":"Comunidad de Madrid","nameEn":"Community of Madrid","website":"https://www.comunidad.madrid/","contract":"Estatuto de Autonomía de Madrid","tags":["cofog:01","autonomous-community","capital","central"],"orgTier":"state"}
{"path":"comunidad:murcia","name":"Comunidad Autónoma de la Región de Murcia","nameEn":"Autonomous Community of the Region of Murcia","website":"https://www.carm.es/","contract":"Estatuto de Autonomía de Murcia","tags":["cofog:01","autonomous-community","southeast"],"orgTier":"state"}
{"path":"comunidad:navarra","name":"Gobierno de Navarra","nameEn":"Government of Navarre","website":"https://www.navarra.es/","contract":"Ley Orgánica de Reintegración y Amejoramiento del Régimen Foral","tags":["cofog:01","autonomous-community","north","foral"],"orgTier":"state"}
{"path":"comunidad:pais-vasco","name":"Gobierno Vasco","nameEn":"Basque Government","website":"https://www.euskadi.eus/","contract":"Estatuto de Autonomía del País Vasco","tags":["cofog:01","autonomous-community","north","basque","foral"],"orgTier":"state"}
{"path":"comunidad:valencia","name":"Generalitat Valenciana","nameEn":"Valencian Government","website":"https://www.gva.es/","contract":"Estatut d'Autonomia de la Comunitat Valenciana","tags":["cofog:01","autonomous-community","east","valencian"],"orgTier":"state"}
{"path":"ciudad:ceuta","name":"Ciudad Autónoma de Ceuta","nameEn":"Autonomous City of Ceuta","website":"https://www.ceuta.es/","contract":"Estatuto de Autonomía de Ceuta","tags":["cofog:01","autonomous-city","north-africa","enclave"],"orgTier":"state"}
{"path":"ciudad:melilla","name":"Ciudad Autónoma de Melilla","nameEn":"Autonomous City of Melilla","website":"https://www.melilla.es/","contract":"Estatuto de Autonomía de Melilla","tags":["cofog:01","autonomous-city","north-africa","enclave"],"orgTier":"state"}
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
    # R0: fetch full row to update specific fields
    full_row = get_kotoba_client().select_first_where("vertex_gov_org", "path", path)
    if full_row and full_row.get("domain_code") == DOMAIN_CODE and full_row.get("owner_did") == PRIMARY_DID:
        for k, v in updates.items():
            full_row[k] = v
        get_kotoba_client().insert_row("vertex_gov_org", full_row)


def _get_org(path: str) -> dict[str, Any] | None:
    # R0: fetch single by path, then filter by domain/owner
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


def task_gov_esp_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: using select_where and filtering in Python
    all_orgs = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    existing = {
        str(r.get("path", "")) for r in all_orgs
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
    }
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_esp_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_esp_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: fetch broader set, filter, count, sort, paginate in Python
    all_orgs = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_orgs
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
    ]
    if org_tier:
        filtered = [r for r in filtered if r.get("org_tier") == org_tier]
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


async def task_gov_esp_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: fetch broader set, filter and sort in Python
    all_orgs = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_orgs
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en") and r.get("did_registered") != "true"
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    page = filtered[:limit]
    registered: list[str] = []
    pds_results: list[dict[str, Any]] = []
    for r in page:
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


async def task_gov_esp_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: fetch broader set, filter and sort in Python
    all_orgs = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_orgs
        if r.get("owner_did") == PRIMARY_DID
        and r.get("site_followed") != "true"
        and r.get("site_domain_slug")
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    page = filtered[:limit]
    for r in page:
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


async def task_gov_esp_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: fetch broader set, filter, sort by ingested ASC
    all_orgs = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = []
    for r in all_orgs:
        if r.get("owner_did") == PRIMARY_DID and r.get("site_domain_slug"):
            last_ingested = r.get("last_ingested_at")
            if not last_ingested or str(last_ingested) < cutoff_iso:
                filtered.append(r)
    filtered.sort(key=lambda x: str(x.get("last_ingested_at") or ""))
    page = filtered[:limit]
    checked = 0
    updated = 0
    posted = 0
    now = _utc_now_iso()
    for r in page:
        path = str(r.get("path") or "")
        name_en = str(r.get("name_en") or "")
        website = str(r.get("website") or "")
        slug = str(r.get("site_domain_slug") or "")
        last_hash = str(r.get("last_content_hash") or "")
        if not path or not slug:
            continue
        checked += 1
        # R0: fetch single wet_chunk by domain, sort in Python to get latest
        wet_chunks = get_kotoba_client().select_where("vertex_wet_chunk", "domain", slug, limit=2000)
        wet_chunks.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
        wet = wet_chunks[0] if wet_chunks else None
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


async def task_gov_esp_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: fetch broader set, filter and sort by shinka ASC
    all_orgs = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    filtered = [
        r for r in all_orgs
        if r.get("owner_did") == PRIMARY_DID and r.get("did_registered") == "true"
    ]
    filtered.sort(key=lambda x: str(x.get("last_shinka_at") or ""))
    page = filtered[:limit]
    posted = 0
    now = _utc_now_iso()
    for r in page:
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
    return {"ok": True, "posted": posted, "touched": len(page)}


async def task_gov_esp_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_esp_seed_orgs, seedLimit)
    register = await task_gov_esp_register_dids(registerLimit)
    follow = await task_gov_esp_follow_site_deps(followLimit)
    ingest = await task_gov_esp_sync_wet_updates(ingestLimit)
    shinka = await task_gov_esp_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govEsp.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_esp_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govEsp.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_esp_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govEsp.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_esp_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govEsp.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_esp_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govEsp.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_esp_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govEsp.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_esp_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govEsp.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_esp_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govEsp.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_esp_heartbeat_tick)
