"""IND Government states actor primitives.

This module moves the `did:web:ind-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:ind-state.etzhayyim.com"
DOMAIN_CODE = "ind"
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
{"path":"pmo","name":"प्रधान मंत्री कार्यालय","nameEn":"Prime Minister's Office","website":"https://www.pmindia.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:01","executive","pmo"],"orgTier":"ministry"}
{"path":"mod","name":"रक्षा मंत्रालय","nameEn":"Ministry of Defence","website":"https://mod.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:02","defence"],"orgTier":"ministry"}
{"path":"mea","name":"विदेश मंत्रालय","nameEn":"Ministry of External Affairs","website":"https://www.mea.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:01.2","foreign-affairs","diplomacy"],"orgTier":"ministry"}
{"path":"mof","name":"वित्त मंत्रालय","nameEn":"Ministry of Finance","website":"https://www.finmin.nic.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:01.1","finance","taxation","budget"],"orgTier":"ministry"}
{"path":"mha","name":"गृह मंत्रालय","nameEn":"Ministry of Home Affairs","website":"https://www.mha.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:03","home-affairs","police","border"],"orgTier":"ministry"}
{"path":"molaw","name":"कानून और न्याय मंत्रालय","nameEn":"Ministry of Law and Justice","website":"https://lawmin.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:03","justice","legal"],"orgTier":"ministry"}
{"path":"mohedu","name":"शिक्षा मंत्रालय","nameEn":"Ministry of Education","website":"https://www.education.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:09","education"],"orgTier":"ministry"}
{"path":"mohfw","name":"स्वास्थ्य और परिवार कल्याण मंत्रालय","nameEn":"Ministry of Health and Family Welfare","website":"https://www.mohfw.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:07","health"],"orgTier":"ministry"}
{"path":"moles","name":"श्रम और रोजगार मंत्रालय","nameEn":"Ministry of Labour and Employment","website":"https://labour.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:04","labour"],"orgTier":"ministry"}
{"path":"moind","name":"वाणिज्य और उद्योग मंत्रालय","nameEn":"Ministry of Commerce and Industry","website":"https://dpiit.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:04","commerce","industry","trade"],"orgTier":"ministry"}
{"path":"moagri","name":"कृषि और किसान कल्याण मंत्रालय","nameEn":"Ministry of Agriculture and Farmers Welfare","website":"https://agricoop.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:04.2","agriculture"],"orgTier":"ministry"}
{"path":"moenv","name":"पर्यावरण, वन और जलवायु परिवर्तन मंत्रालय","nameEn":"Ministry of Environment, Forest and Climate Change","website":"https://moef.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:05","environment","forest"],"orgTier":"ministry"}
{"path":"moit","name":"इलेक्ट्रॉनिक्स और सूचना प्रौद्योगिकी मंत्रालय","nameEn":"Ministry of Electronics and Information Technology","website":"https://meity.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:04","digital","it"],"orgTier":"ministry"}
{"path":"mopower","name":"विद्युत मंत्रालय","nameEn":"Ministry of Power","website":"https://powermin.gov.in/","contract":"Government of India (Allocation of Business) Rules 1961","tags":["cofog:04","power","energy"],"orgTier":"ministry"}
{"path":"molokh","name":"लोक सभा सचिवालय","nameEn":"Lok Sabha Secretariat","website":"https://sansad.in/ls/","contract":"Constitution of India Art. 79","tags":["cofog:01","legislature","lower-house"],"orgTier":"agency"}
{"path":"moryjj","name":"राज्य सभा सचिवालय","nameEn":"Rajya Sabha Secretariat","website":"https://sansad.in/rs/","contract":"Constitution of India Art. 79","tags":["cofog:01","legislature","upper-house"],"orgTier":"agency"}
{"path":"sci","name":"भारत का सर्वोच्च न्यायालय","nameEn":"Supreme Court of India","website":"https://main.sci.gov.in/","contract":"Constitution of India Art. 124","tags":["cofog:03","judiciary","supreme-court"],"orgTier":"agency"}
"""

_STATE_NDJSON = """\
{"path":"state:andhra-pradesh","name":"आंध्र प्रदेश","nameEn":"Andhra Pradesh","website":"https://www.ap.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:arunachal-pradesh","name":"अरुणाचल प्रदेश","nameEn":"Arunachal Pradesh","website":"https://arunachalpradesh.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:assam","name":"असम","nameEn":"Assam","website":"https://assam.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:bihar","name":"बिहार","nameEn":"Bihar","website":"https://state.bihar.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:chhattisgarh","name":"छत्तीसगढ़","nameEn":"Chhattisgarh","website":"https://cgstate.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:goa","name":"गोवा","nameEn":"Goa","website":"https://www.goa.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:gujarat","name":"गुजरात","nameEn":"Gujarat","website":"https://gujaratindia.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:haryana","name":"हरियाणा","nameEn":"Haryana","website":"https://haryana.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:himachal-pradesh","name":"हिमाचल प्रदेश","nameEn":"Himachal Pradesh","website":"https://himachal.nic.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:jharkhand","name":"झारखंड","nameEn":"Jharkhand","website":"https://jharkhand.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:karnataka","name":"कर्नाटक","nameEn":"Karnataka","website":"https://www.karnataka.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:kerala","name":"केरल","nameEn":"Kerala","website":"https://kerala.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:madhya-pradesh","name":"मध्य प्रदेश","nameEn":"Madhya Pradesh","website":"https://mp.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:maharashtra","name":"महाराष्ट्र","nameEn":"Maharashtra","website":"https://www.maharashtra.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:manipur","name":"मणिपुर","nameEn":"Manipur","website":"https://manipur.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:meghalaya","name":"मेघालय","nameEn":"Meghalaya","website":"https://meghalaya.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:mizoram","name":"मिज़ोरम","nameEn":"Mizoram","website":"https://mizoram.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:nagaland","name":"नागालैंड","nameEn":"Nagaland","website":"https://nagaland.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:odisha","name":"ओडिशा","nameEn":"Odisha","website":"https://odisha.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:punjab","name":"पंजाब","nameEn":"Punjab","website":"https://punjab.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:rajasthan","name":"राजस्थान","nameEn":"Rajasthan","website":"https://rajasthan.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:sikkim","name":"सिक्किम","nameEn":"Sikkim","website":"https://sikkim.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:tamil-nadu","name":"तमिलनाडु","nameEn":"Tamil Nadu","website":"https://www.tn.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:telangana","name":"तेलंगाना","nameEn":"Telangana","website":"https://www.telangana.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:tripura","name":"त्रिपुरा","nameEn":"Tripura","website":"https://tripura.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:uttar-pradesh","name":"उत्तर प्रदेश","nameEn":"Uttar Pradesh","website":"https://up.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:uttarakhand","name":"उत्तराखंड","nameEn":"Uttarakhand","website":"https://uk.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"state:west-bengal","name":"पश्चिम बंगाल","nameEn":"West Bengal","website":"https://wb.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","state","l5"],"orgTier":"state"}
{"path":"ut:delhi","name":"दिल्ली","nameEn":"Delhi (NCT)","website":"https://delhi.gov.in/","contract":"Government of NCT of Delhi Act 1991","tags":["cofog:01","union-territory","capital"],"orgTier":"state"}
{"path":"ut:jammu-kashmir","name":"जम्मू और कश्मीर","nameEn":"Jammu and Kashmir","website":"https://jkgov.nic.in/","contract":"Jammu and Kashmir Reorganisation Act 2019","tags":["cofog:01","union-territory"],"orgTier":"state"}
{"path":"ut:ladakh","name":"लद्दाख","nameEn":"Ladakh","website":"https://ladakh.gov.in/","contract":"Jammu and Kashmir Reorganisation Act 2019","tags":["cofog:01","union-territory"],"orgTier":"state"}
{"path":"ut:chandigarh","name":"चंडीगढ़","nameEn":"Chandigarh","website":"https://chandigarh.gov.in/","contract":"Punjab Reorganisation Act 1966","tags":["cofog:01","union-territory"],"orgTier":"state"}
{"path":"ut:dadra-nagar-haveli","name":"दादरा और नगर हवेली और दमन और दीव","nameEn":"Dadra and Nagar Haveli and Daman and Diu","website":"https://daman.nic.in/","contract":"Dadra and Nagar Haveli and Daman and Diu (Merger of Union Territories) Act 2019","tags":["cofog:01","union-territory"],"orgTier":"state"}
{"path":"ut:lakshadweep","name":"लक्षद्वीप","nameEn":"Lakshadweep","website":"https://lakshadweep.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","union-territory"],"orgTier":"state"}
{"path":"ut:puducherry","name":"पुदुच्चेरी","nameEn":"Puducherry","website":"https://py.gov.in/","contract":"Government of Union Territories Act 1963","tags":["cofog:01","union-territory"],"orgTier":"state"}
{"path":"ut:andaman-nicobar","name":"अंडमान और निकोबार द्वीप समूह","nameEn":"Andaman and Nicobar Islands","website":"https://andaman.gov.in/","contract":"States Reorganisation Act 1956","tags":["cofog:01","union-territory"],"orgTier":"state"}
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


def task_gov_ind_seed_orgs(limit: int = 30) -> dict[str, Any]:
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


def task_gov_ind_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_ind_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
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


async def task_gov_ind_register_dids(limit: int = 10) -> dict[str, Any]:
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


async def task_gov_ind_follow_site_deps(limit: int = 15) -> dict[str, Any]:
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


async def task_gov_ind_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
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


async def task_gov_ind_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
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


async def task_gov_ind_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_ind_seed_orgs, seedLimit)
    register = await task_gov_ind_register_dids(registerLimit)
    follow = await task_gov_ind_follow_site_deps(followLimit)
    ingest = await task_gov_ind_sync_wet_updates(ingestLimit)
    shinka = await task_gov_ind_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govInd.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ind_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govInd.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ind_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govInd.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ind_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govInd.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ind_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govInd.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ind_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govInd.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ind_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govInd.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ind_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govInd.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_ind_heartbeat_tick)
