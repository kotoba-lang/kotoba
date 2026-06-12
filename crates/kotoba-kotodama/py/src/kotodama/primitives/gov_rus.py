"""Russia states actor primitives.

This module moves the `did:web:rus-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:rus-state.etzhayyim.com"
DOMAIN_CODE = "rus"
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
{"path":"president","name":"Администрация Президента","nameEn":"Presidential Administration","website":"http://www.kremlin.ru/","contract":"Конституция Ст. 80-93","tags":["cofog:01","executive","president"],"orgTier":"ministry"}
{"path":"pravitelstvo","name":"Правительство Российской Федерации","nameEn":"Government of the Russian Federation","website":"https://government.ru/","contract":"Конституция Ст. 110-117","tags":["cofog:01","executive","cabinet"],"orgTier":"ministry"}
{"path":"mid","name":"Министерство иностранных дел","nameEn":"Ministry of Foreign Affairs","website":"https://www.mid.ru/","contract":"Конституция Ст. 80","tags":["cofog:01.2","foreign-affairs"],"orgTier":"ministry"}
{"path":"minoborony","name":"Министерство обороны","nameEn":"Ministry of Defence","website":"https://function.mil.ru/","contract":"Конституция Ст. 59","tags":["cofog:02","defence"],"orgTier":"ministry"}
{"path":"minfin","name":"Министерство финансов","nameEn":"Ministry of Finance","website":"https://minfin.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:01.1","finance","budget"],"orgTier":"ministry"}
{"path":"minjust","name":"Министерство юстиции","nameEn":"Ministry of Justice","website":"https://minjust.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:03","justice"],"orgTier":"ministry"}
{"path":"mvd","name":"Министерство внутренних дел","nameEn":"Ministry of Internal Affairs","website":"https://мвд.рф/","contract":"Конституция Ст. 114","tags":["cofog:03","interior","police"],"orgTier":"ministry"}
{"path":"minzdrav","name":"Министерство здравоохранения","nameEn":"Ministry of Health","website":"https://minzdrav.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:07","health"],"orgTier":"ministry"}
{"path":"minprosveshenia","name":"Министерство просвещения","nameEn":"Ministry of Education","website":"https://edu.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:09","education"],"orgTier":"ministry"}
{"path":"minekonomiki","name":"Министерство экономического развития","nameEn":"Ministry of Economic Development","website":"https://www.economy.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:04","economy","development"],"orgTier":"ministry"}
{"path":"minpromtorg","name":"Министерство промышленности и торговли","nameEn":"Ministry of Industry and Trade","website":"https://minpromtorg.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:04","industry","trade"],"orgTier":"ministry"}
{"path":"minenergo","name":"Министерство энергетики","nameEn":"Ministry of Energy","website":"https://minenergo.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:04","energy"],"orgTier":"ministry"}
{"path":"mintrans","name":"Министерство транспорта","nameEn":"Ministry of Transport","website":"https://mintrans.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:04.5","transport"],"orgTier":"ministry"}
{"path":"minselhoz","name":"Министерство сельского хозяйства","nameEn":"Ministry of Agriculture","website":"https://mcx.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:04.2","agriculture"],"orgTier":"ministry"}
{"path":"minprirody","name":"Министерство природных ресурсов и экологии","nameEn":"Ministry of Natural Resources and Ecology","website":"https://www.mnr.gov.ru/","contract":"Конституция Ст. 114","tags":["cofog:05","environment","natural-resources"],"orgTier":"ministry"}
{"path":"gosduma","name":"Государственная Дума","nameEn":"State Duma","website":"https://www.duma.gov.ru/","contract":"Конституция Ст. 95-103","tags":["cofog:01","legislature","lower-house"],"orgTier":"agency"}
{"path":"sovfed","name":"Совет Федерации","nameEn":"Federation Council","website":"https://www.council.gov.ru/","contract":"Конституция Ст. 95-101","tags":["cofog:01","legislature","upper-house"],"orgTier":"agency"}
{"path":"ksrf","name":"Конституционный Суд","nameEn":"Constitutional Court","website":"https://ksrf.ru/","contract":"Конституция Ст. 125","tags":["cofog:03","judiciary","constitutional-court"],"orgTier":"agency"}
"""

_STATE_NDJSON = """\
{"path":"subject:moskva","name":"Москва","nameEn":"Moscow","website":"https://www.mos.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","gorod-federalnogo-znacheniia","capital"],"orgTier":"state"}
{"path":"subject:spb","name":"Санкт-Петербург","nameEn":"Saint Petersburg","website":"https://www.gov.spb.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","gorod-federalnogo-znacheniia"],"orgTier":"state"}
{"path":"subject:sevastopol","name":"Севастополь","nameEn":"Sevastopol","website":"https://sevastopol.gov.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","gorod-federalnogo-znacheniia","disputed"],"orgTier":"state"}
{"path":"subject:tatarstan","name":"Республика Татарстан","nameEn":"Republic of Tatarstan","website":"https://tatarstan.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","respublika"],"orgTier":"state"}
{"path":"subject:bashkortostan","name":"Республика Башкортостан","nameEn":"Republic of Bashkortostan","website":"https://www.bashkortostan.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","respublika"],"orgTier":"state"}
{"path":"subject:chechnya","name":"Чеченская Республика","nameEn":"Chechen Republic","website":"https://www.chechnya.gov.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","respublika"],"orgTier":"state"}
{"path":"subject:dagestan","name":"Республика Дагестан","nameEn":"Republic of Dagestan","website":"https://dagestan.gov.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","respublika"],"orgTier":"state"}
{"path":"subject:sakha","name":"Республика Саха (Якутия)","nameEn":"Republic of Sakha (Yakutia)","website":"https://sakha.gov.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","respublika","largest-by-area"],"orgTier":"state"}
{"path":"subject:krasnodar","name":"Краснодарский край","nameEn":"Krasnodar Krai","website":"https://www.krasnodar.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","krai"],"orgTier":"state"}
{"path":"subject:krasnoyarsk","name":"Красноярский край","nameEn":"Krasnoyarsk Krai","website":"https://www.krskstate.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","krai"],"orgTier":"state"}
{"path":"subject:primorsky","name":"Приморский край","nameEn":"Primorsky Krai","website":"https://www.primorsky.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","krai"],"orgTier":"state"}
{"path":"subject:stavropol","name":"Ставропольский край","nameEn":"Stavropol Krai","website":"https://www.stavregion.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","krai"],"orgTier":"state"}
{"path":"subject:moskovskaya","name":"Московская область","nameEn":"Moscow Oblast","website":"https://mosreg.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:sverdlovsk","name":"Свердловская область","nameEn":"Sverdlovsk Oblast","website":"https://www.midural.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:novosibirsk","name":"Новосибирская область","nameEn":"Novosibirsk Oblast","website":"https://www.nso.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:chelyabinsk","name":"Челябинская область","nameEn":"Челябинская область","website":"https://www.chelregion.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:tyumen","name":"Тюменская область","nameEn":"Tyumen Oblast","website":"https://admtyumen.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast","oil-gas"],"orgTier":"state"}
{"path":"subject:nizhny-novgorod","name":"Нижегородская область","nameEn":"Nizhny Novgorod Oblast","website":"https://www.government-nnov.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:samara","name":"Самарская область","nameEn":"Samara Oblast","website":"https://www.samregion.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:rostov","name":"Ростовская область","nameEn":"Rostov Oblast","website":"https://www.donland.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:perm","name":"Пермский край","nameEn":"Perm Krai","website":"https://www.permkrai.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","krai"],"orgTier":"state"}
{"path":"subject:khanty-mansiysk","name":"Ханты-Мансийский АО","nameEn":"Khanty-Mansiysk Autonomous Okrug","website":"https://depeconom.admhmao.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","avtonomny-okrug","oil-rich"],"orgTier":"state"}
{"path":"subject:yamalo-nenets","name":"Ямало-Ненецкий АО","nameEn":"Yamalo-Nenets Autonomous Okrug","website":"https://www.yanao.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","avtonomny-okrug","gas-rich"],"orgTier":"state"}
{"path":"subject:crimea","name":"Республика Крым","nameEn":"Republic of Crimea","website":"https://rk.gov.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","respublika","disputed"],"orgTier":"state"}
{"path":"subject:leningrad","name":"Ленинградская область","nameEn":"Leningrad Oblast","website":"https://lenobl.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:saratov","name":"Саратовская область","nameEn":"Saratov Oblast","website":"https://www.saratov.gov.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:voronezh","name":"Воронежская область","nameEn":"Voronezh Oblast","website":"https://www.govvrn.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:buryatia","name":"Республика Бурятия","nameEn":"Republic of Buryatia","website":"https://egov-buryatia.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","respublika"],"orgTier":"state"}
{"path":"subject:omsk","name":"Омская область","nameEn":"Omsk Oblast","website":"https://omskportal.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
{"path":"subject:volgograd","name":"Волгоградская область","nameEn":"Volgograd Oblast","website":"https://www.volgograd.ru/","contract":"Конституция Ст. 65","tags":["cofog:01","oblast"],"orgTier":"state"}
"""

_OFFICIAL_SOURCE_URLS = [
    "https://government.ru/",
    "https://www.kremlin.ru/",
    "https://www.duma.gov.ru/",
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


def _direct_fetch_hash(url: str, timeout: int = 10) -> tuple[str, str, str, str]:
    """Fetch url and return (md5_content_hash, text_snippet, status, error).

    Direct network fetch is attempted first. If this VKE/Mac egress path is
    blocked, GOV_FETCH_PROXY_URL + GOV_FETCH_HMAC enables authenticated
    Cloudflare edge fallback for public government websites.
    """
    return direct_then_proxy_fetch_hash_status(url, timeout=timeout)

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
                    [_OFFICIAL_SOURCE_URLS[0]]
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
        "User-Agent": "etzhayyim-kotodama-gov-rus/0.1",
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
    # R0: read-modify-write for update
    row = get_kotoba_client().select_first_where("vertex_gov_org", "path", path)
    if row and row.get("domain_code") == DOMAIN_CODE and row.get("owner_did") == (owner_did or PRIMARY_DID):
        row.update(updates)
        get_kotoba_client().insert_row("vertex_gov_org", row)


def _get_org(path: str) -> dict[str, Any] | None:
    # R0: fetch by path, filter in python
    row = get_kotoba_client().select_first_where("vertex_gov_org", "path", path)
    if not row or row.get("domain_code") != DOMAIN_CODE or row.get("owner_did") != PRIMARY_DID:
        return None
    return {
        "path": row.get("path"),
        "name": row.get("name"),
        "name_en": row.get("name_en"),
        "website": row.get("website"),
        "contract": row.get("contract"),
        "tags": row.get("tags"),
        "org_tier": row.get("org_tier"),
        "site_domain_slug": row.get("site_domain_slug"),
        "site_followed": row.get("site_followed"),
        "did_registered": row.get("did_registered"),
        "last_ingested_at": row.get("last_ingested_at"),
        "last_content_hash": row.get("last_content_hash"),
        "last_kyumei_at": row.get("last_kyumei_at"),
        "last_shinka_at": row.get("last_shinka_at"),
        "created_at": row.get("created_at"),
    }


def task_gov_rus_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: fetch all by domain_code, filter by owner_did and name_en
    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    existing = {
        str(r.get("path") or "") for r in rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
    }
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_rus_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_rus_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: fetch all by domain_code, filter in python, apply sort/limit/offset
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
        and (not org_tier or r.get("org_tier") == org_tier)
    ]
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


async def task_gov_rus_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: fetch all by domain_code, filter in python, apply sort and limit
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
            "tags": json.loads(str(r.get("tags") or "[]")) if isinstance(r.get("tags"), str) else r.get("tags") or [],
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


async def task_gov_rus_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: fetch all by domain_code, filter in python, apply sort and limit
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("owner_did") == PRIMARY_DID
        and str(r.get("site_followed") or "") != "true"
        and str(r.get("site_domain_slug") or "") != ""
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
            "tags": json.loads(str(r.get("tags") or "[]")) if isinstance(r.get("tags"), str) else r.get("tags") or [],
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


async def task_gov_rus_ingest_official_sources(
    limit: int = 10,
    processBatchSize: int = 10,
    includeOrgSites: bool = True,
) -> dict[str, Any]:
    """Queue official Russian government sources through site.etzhayyim.com."""
    limit = max(1, min(int(limit or 10), 50))
    process_batch_size = max(1, min(int(processBatchSize or 10), 50))
    targets: list[dict[str, str]] = [
        {"kind": "page", "url": url}
        for url in _OFFICIAL_SOURCE_URLS
    ]
    if includeOrgSites:
        # R0: fetch all by domain_code, extract unique websites
        all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
        websites = list({
            str(r.get("website"))
            for r in all_rows
            if r.get("owner_did") == PRIMARY_DID and r.get("website")
        })
        websites.sort()
        for website in websites[:limit]:
            host = _url_to_hostname(website)
            if host:
                targets.append({"kind": "domain", "domain": host})

    enqueued = 0
    results: list[dict[str, Any]] = []
    for target in targets[: limit + len(_OFFICIAL_SOURCE_URLS)]:
        if target["kind"] == "page":
            result = await _pds_xrpc(
                "com.etzhayyim.apps.site.crawlPage",
                {"url": target["url"], "topics": ["government", "rus", "official-source"], "depth": 0},
            )
        else:
            result = await _pds_xrpc(
                "com.etzhayyim.apps.site.crawlDomain",
                {
                    "domain": target["domain"],
                    "topics": ["government", "rus", "official-source"],
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


async def task_gov_rus_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: fetch all by domain_code, filter in python, apply sort and limit
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    filtered = []
    for r in all_rows:
        if not str(r.get("site_domain_slug") or ""):
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
        domains = _wet_domain_candidates(website, slug)
        # R0: fetch chunks for domain candidates, sort by crawled_at desc
        wet_chunks = []
        for d in domains:
            wet_chunks.extend(get_kotoba_client().select_where("vertex_wet_chunk", "domain", d, limit=100))
        wet_chunks.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
        wet = wet_chunks[0] if wet_chunks else None
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


async def task_gov_rus_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: fetch all by domain_code, filter in python, apply sort and limit
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


async def task_gov_rus_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_rus_seed_orgs, seedLimit)
    official_sources = await task_gov_rus_ingest_official_sources(limit=max(1, min(seedLimit, 10)))
    register = await task_gov_rus_register_dids(registerLimit)
    follow = await task_gov_rus_follow_site_deps(followLimit)
    ingest = await task_gov_rus_sync_wet_updates(ingestLimit)
    shinka = await task_gov_rus_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govRus.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_rus_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govRus.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_rus_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govRus.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_rus_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govRus.ingestOfficialSources",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_rus_ingest_official_sources)
    worker.task(
        task_type="xrpc.com.etzhayyim.govRus.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_rus_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govRus.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_rus_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govRus.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_rus_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govRus.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_rus_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govRus.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_rus_heartbeat_tick)
