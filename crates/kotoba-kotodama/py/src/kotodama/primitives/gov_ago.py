"""Angola states actor primitives.

This module moves the `did:web:ago-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:ago-state.etzhayyim.com"
DOMAIN_CODE = "ago"
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
{"path":"defesa-veteranos","name":"Ministro da Defesa Nacional e Veteranos da Pátria","nameEn":"Ministry of National Defence and Veterans of the Homeland","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:02","defence","veterans"],"orgTier":"ministry"}
{"path":"interior","name":"Ministro do Interior","nameEn":"Ministry of Interior","website":"https://www.minint.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:03","interior","public-order"],"orgTier":"ministry"}
{"path":"relacoes-exteriores","name":"Ministro das Relações Exteriores","nameEn":"Ministry of External Relations","website":"https://www.mirex.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:01.2","foreign-affairs"],"orgTier":"ministry"}
{"path":"administracao-territorio","name":"Ministro da Administração do Território","nameEn":"Ministry of Territorial Administration","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:01","territorial-administration"],"orgTier":"ministry"}
{"path":"justica-direitos-humanos","name":"Ministro da Justiça e dos Direitos Humanos","nameEn":"Ministry of Justice and Human Rights","website":"https://www.mjdh.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:03","justice","human-rights"],"orgTier":"ministry"}
{"path":"financas","name":"Ministra das Finanças","nameEn":"Ministry of Finance","website":"https://www.minfin.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:01.1","finance","budget"],"orgTier":"ministry"}
{"path":"planeamento","name":"Ministro do Planeamento","nameEn":"Ministry of Planning","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:01","planning"],"orgTier":"ministry"}
{"path":"cultura","name":"Ministro da Cultura","nameEn":"Ministry of Culture","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:08","culture"],"orgTier":"ministry"}
{"path":"administracao-publica-trabalho-seguranca-social","name":"Ministra da Administração Pública, Trabalho e Segurança Social","nameEn":"Ministry of Public Administration, Labour and Social Security","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:04","labour","public-administration","social-security"],"orgTier":"ministry"}
{"path":"agricultura-florestas","name":"Ministro da Agricultura e Florestas","nameEn":"Ministry of Agriculture and Forests","website":"https://www.minagrif.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:04.2","agriculture","forests"],"orgTier":"ministry"}
{"path":"pescas-recursos-marinhos","name":"Ministra das Pescas e Recursos Marinhos","nameEn":"Ministry of Fisheries and Marine Resources","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:04","fisheries","marine-resources"],"orgTier":"ministry"}
{"path":"industria-comercio","name":"Ministro da Indústria e Comércio","nameEn":"Ministry of Industry and Commerce","website":"https://www.mindcom.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:04","industry","commerce"],"orgTier":"ministry"}
{"path":"recursos-minerais-petroleo-gas","name":"Ministro dos Recursos Minerais, Petróleo e Gás","nameEn":"Ministry of Mineral Resources, Petroleum and Gas","website":"https://www.minpetro.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:04","minerals","petroleum","gas"],"orgTier":"ministry"}
{"path":"transportes","name":"Ministro dos Transportes","nameEn":"Ministry of Transport","website":"https://www.mintrans.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:04.5","transport"],"orgTier":"ministry"}
{"path":"energia-aguas","name":"Ministro da Energia e Águas","nameEn":"Ministry of Energy and Water","website":"https://www.minea.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:04","energy","water"],"orgTier":"ministry"}
{"path":"telecomunicacoes-tecnologias-informacao-comunicacao-social","name":"Ministro das Telecomunicações, Tecnologias de Informação e Comunicação Social","nameEn":"Ministry of Telecommunications, Information Technologies and Social Communication","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:04","telecommunications","information-technology","media"],"orgTier":"ministry"}
{"path":"turismo","name":"Ministro do Turismo","nameEn":"Ministry of Tourism","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:04","tourism"],"orgTier":"ministry"}
{"path":"obras-publicas-urbanismo-habitacao","name":"Ministro das Obras Públicas, Urbanismo e Habitação","nameEn":"Ministry of Public Works, Urbanism and Housing","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:06","public-works","urbanism","housing"],"orgTier":"ministry"}
{"path":"ensino-superior-ciencia-tecnologia-inovacao","name":"Ministro do Ensino Superior, Ciência, Tecnologia e Inovação","nameEn":"Ministry of Higher Education, Science, Technology and Innovation","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:09","higher-education","science","technology","innovation"],"orgTier":"ministry"}
{"path":"educacao","name":"Ministra da Educação","nameEn":"Ministry of Education","website":"https://www.med.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:09","education"],"orgTier":"ministry"}
{"path":"saude","name":"Ministra da Saúde","nameEn":"Ministry of Health","website":"https://www.minsa.gov.ao/","contract":"Constituição da República de Angola","tags":["cofog:07","health"],"orgTier":"ministry"}
{"path":"accao-social-familia-promocao-mulher","name":"Ministra da Acção Social, Família e Promoção da Mulher","nameEn":"Ministry of Social Action, Family and Promotion of Women","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:10","social-action","family","women"],"orgTier":"ministry"}
{"path":"ambiente","name":"Ministra do Ambiente","nameEn":"Ministry of Environment","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:05","environment"],"orgTier":"ministry"}
{"path":"juventude-desportos","name":"Ministro da Juventude e Desportos","nameEn":"Ministry of Youth and Sports","website":"https://governo.gov.ao/ministro","contract":"Constituição da República de Angola","tags":["cofog:08","youth","sports"],"orgTier":"ministry"}
"""

_STATE_NDJSON = """\
{"path":"province:bengo","name":"Província do Bengo","nameEn":"Bengo Province","website":"https://governo.gov.ao/provincia/bengo","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:icolo-e-bengo","name":"Província do Icolo e Bengo","nameEn":"Icolo e Bengo Province","website":"https://governo.gov.ao/governador","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:moxico-leste","name":"Província do Moxico Leste","nameEn":"Moxico Leste Province","website":"https://governo.gov.ao/governador","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:cuando","name":"Província do Cuando","nameEn":"Cuando Province","website":"https://governo.gov.ao/governador","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:benguela","name":"Província de Benguela","nameEn":"Benguela Province","website":"https://governo.gov.ao/provincia/benguela","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:bie","name":"Província do Bié","nameEn":"Bié Province","website":"https://governo.gov.ao/provincia/bi%C3%A9","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:cabinda","name":"Província de Cabinda","nameEn":"Cabinda Province","website":"https://governo.gov.ao/provincia/cabinda","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:cunene","name":"Província do Cunene","nameEn":"Cunene Province","website":"https://governo.gov.ao/provincia/cunene","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:cubango","name":"Província do Cubango","nameEn":"Cubango Province","website":"https://governo.gov.ao/governador","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:cuanza-norte","name":"Província do Cuanza Norte","nameEn":"Cuanza Norte Province","website":"https://governo.gov.ao/provincia/cuanza-norte","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:cuanza-sul","name":"Província do Cuanza Sul","nameEn":"Cuanza Sul Province","website":"https://governo.gov.ao/provincia/cuanza-sul","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:huambo","name":"Província do Huambo","nameEn":"Huambo Province","website":"https://governo.gov.ao/provincia/huambo","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:huila","name":"Província da Huíla","nameEn":"Huíla Province","website":"https://governo.gov.ao/provincia/hu%C3%ADla","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:luanda","name":"Província de Luanda","nameEn":"Luanda Province","website":"https://governo.gov.ao/provincia/luanda","contract":"Constituição da República de Angola","tags":["cofog:01","province","capital"],"orgTier":"state"}
{"path":"province:lunda-norte","name":"Província da Lunda Norte","nameEn":"Lunda Norte Province","website":"https://governo.gov.ao/provincia/lunda-norte","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:lunda-sul","name":"Província da Lunda Sul","nameEn":"Lunda Sul Province","website":"https://governo.gov.ao/provincia/lunda-sul","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:malanje","name":"Província de Malanje","nameEn":"Malanje Province","website":"https://governo.gov.ao/provincia/malanje","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:moxico","name":"Província do Moxico","nameEn":"Moxico Province","website":"https://governo.gov.ao/provincia/moxico","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:namibe","name":"Província do Namibe","nameEn":"Namibe Province","website":"https://governo.gov.ao/provincia/namibe","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:uige","name":"Província do Uíge","nameEn":"Uíge Province","website":"https://governo.gov.ao/provincia/u%C3%ADge","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
{"path":"province:zaire","name":"Província do Zaire","nameEn":"Zaire Province","website":"https://governo.gov.ao/provincia/zaire","contract":"Constituição da República de Angola","tags":["cofog:01","province"],"orgTier":"state"}
"""

_OFFICIAL_SOURCE_URLS = [
    "https://governo.gov.ao/ministro",
    "https://governo.gov.ao/governador",
    "https://governo.gov.ao/angola/provincias",
]


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _url_to_domain_slug(url: str) -> str:
    try:
        host = re.sub(r"^https?://", "", url).split("/", 1)[0]
        host = re.sub(r"^(www|web)\.", "", host)
        return host.replace(".", "-")
    except Exception:
        return ""


def _url_to_hostname(url: str) -> str:
    try:
        return re.sub(r"^https?://", "", url).split("/", 1)[0].lower()
    except Exception:
        return ""


def _wet_domain_candidates(website: str, slug: str) -> list[str]:
    host = _url_to_hostname(website)
    stripped = re.sub(r"^(www|web)\.", "", host)
    candidates = [slug, host, stripped]
    return [candidate for idx, candidate in enumerate(candidates) if candidate and candidate not in candidates[:idx]]


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


def _load_seed_orgs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for blob in (_MINISTRY_NDJSON, _STATE_NDJSON):
        for line in blob.splitlines():
            line = line.strip()
            if line:
                row = json.loads(line)
                props = row.setdefault("props", {})
                props.setdefault(
                    "officialSourceUrls",
                    [_OFFICIAL_SOURCE_URLS[1], _OFFICIAL_SOURCE_URLS[2]]
                    if str(row.get("orgTier") or "") == "state"
                    else [_OFFICIAL_SOURCE_URLS[0]],
                )
                rows.append(row)
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
        "User-Agent": "etzhayyim-kotodama-gov-ago/0.1",
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
    vid = f"at://{PRIMARY_DID}/com.etzhayyim.apps.states.govOrg/{path}"
    get_kotoba_client().insert_row("vertex_gov_org", {"vertex_id": vid, **updates})


def _get_org(path: str) -> dict[str, Any] | None:
    vid = f"at://{PRIMARY_DID}/com.etzhayyim.apps.states.govOrg/{path}"
    row = get_kotoba_client().select_first_where("vertex_gov_org", "vertex_id", vid)
    if not row:
        return None
    return {
        "path": str(row.get("path") or ""),
        "name": str(row.get("name") or ""),
        "name_en": str(row.get("name_en") or ""),
        "website": str(row.get("website") or ""),
        "contract": str(row.get("contract") or ""),
        "tags": str(row.get("tags") or ""),
        "org_tier": str(row.get("org_tier") or ""),
        "site_domain_slug": str(row.get("site_domain_slug") or ""),
        "site_followed": str(row.get("site_followed") or ""),
        "did_registered": str(row.get("did_registered") or ""),
        "last_ingested_at": str(row.get("last_ingested_at") or ""),
        "last_content_hash": str(row.get("last_content_hash") or ""),
        "last_kyumei_at": str(row.get("last_kyumei_at") or ""),
        "last_shinka_at": str(row.get("last_shinka_at") or ""),
        "created_at": str(row.get("created_at") or ""),
    }


def task_gov_ago_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: in-Python filter for multi-predicate
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


def task_gov_ago_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_ago_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: in-Python filter, sort, count, pagination for multi-predicate
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
    ]
    if org_tier:
        filtered = [r for r in filtered if str(r.get("org_tier") or "") == org_tier]
    total = len(filtered)
    filtered.sort(key=lambda r: str(r.get("path") or ""))
    page_rows = filtered[offset : offset + limit]
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
            for r in page_rows
        ],
        "total": total,
    }


async def task_gov_ago_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: in-Python filter, sort, limit
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en") and str(r.get("did_registered") or "") != "true"
    ]
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


async def task_gov_ago_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: in-Python filter, sort, limit
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID
        and str(r.get("site_followed") or "") != "true"
        and str(r.get("site_domain_slug") or "") != ""
    ]
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


async def task_gov_ago_ingest_official_sources(
    limit: int = 10,
    processBatchSize: int = 10,
    includeOrgSites: bool = True,
) -> dict[str, Any]:
    """Queue official Angolan government sources through site.etzhayyim.com."""
    limit = max(1, min(int(limit or 10), 50))
    process_batch_size = max(1, min(int(processBatchSize or 10), 50))
    targets: list[dict[str, str]] = [
        {"kind": "page", "url": url}
        for url in _OFFICIAL_SOURCE_URLS
    ]
    if includeOrgSites:
        # R0: in-Python filter, sort, limit
        all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
        filtered_websites = {
            str(r.get("website") or "")
            for r in all_rows
            if r.get("owner_did") == PRIMARY_DID and str(r.get("website") or "") != ""
        }
        sorted_websites = sorted(list(filtered_websites))[:limit]
        for website in sorted_websites:
            host = _url_to_hostname(str(website or ""))
            if host:
                targets.append({"kind": "domain", "domain": host})

    enqueued = 0
    results: list[dict[str, Any]] = []
    for target in targets[: limit + len(_OFFICIAL_SOURCE_URLS)]:
        if target["kind"] == "page":
            result = await _pds_xrpc(
                "com.etzhayyim.apps.site.crawlPage",
                {"url": target["url"], "topics": ["government", "ago", "official-source"], "depth": 0},
            )
        else:
            result = await _pds_xrpc(
                "com.etzhayyim.apps.site.crawlDomain",
                {
                    "domain": target["domain"],
                    "topics": ["government", "ago", "official-source"],
                    "maxDepth": 1,
                    "maxPages": 25,
                },
            )
        status = int(result.get("status") or 0)
        if status in range(200, 300):
            enqueued += 1
        results.append({"target": target, "status": status, "body": result.get("body")})

    process_result = await _pds_xrpc(
        "com.etzhayyim.apps.site.processFrontier",
        {"batchSize": process_batch_size},
    )
    return {
        "ok": enqueued > 0,
        "enqueued": enqueued,
        "targets": len(targets),
        "processed": (process_result.get("body") or {}).get("processed", 0),
        "processStatus": process_result.get("status"),
        "results": results[:10],
    }


async def task_gov_ago_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: in-Python filter, sort, limit
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = []
    for r in all_rows:
        if r.get("owner_did") != PRIMARY_DID or str(r.get("site_domain_slug") or "") == "":
            continue
        last_ingested_at = str(r.get("last_ingested_at") or "")
        if not last_ingested_at or last_ingested_at < cutoff_iso:
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
        domains = _wet_domain_candidates(website, slug)
        # R0: in-Python sort, limit
        candidates = []
        for d in domains:
            candidates.extend(get_kotoba_client().select_where("vertex_wet_chunk", "domain", d, limit=100))
        wet = None
        if candidates:
            candidates.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
            wet = candidates[0]
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


async def task_gov_ago_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: in-Python filter, sort, limit
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and str(r.get("did_registered") or "") == "true"
    ]
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


async def task_gov_ago_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_ago_seed_orgs, seedLimit)
    official_sources = await task_gov_ago_ingest_official_sources(limit=ingestLimit)
    register = await task_gov_ago_register_dids(registerLimit)
    follow = await task_gov_ago_follow_site_deps(followLimit)
    ingest = await task_gov_ago_sync_wet_updates(ingestLimit)
    shinka = await task_gov_ago_shinka(shinkaLimit)
    return {
        "ok": True,
        "seeded": seed.get("seeded", 0),
        "officialSourcesEnqueued": official_sources.get("enqueued", 0),
        "registered": register.get("registered", 0),
        "followed": follow.get("followed", 0),
        "wetUpdated": ingest.get("updated", 0),
        "shinkaPosted": shinka.get("posted", 0),
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="xrpc.com.etzhayyim.govAgo.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ago_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAgo.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ago_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAgo.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ago_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAgo.ingestOfficialSources",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ago_ingest_official_sources)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAgo.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ago_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAgo.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ago_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAgo.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ago_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAgo.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ago_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govAgo.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ago_heartbeat_tick)
