"""IDN Government states actor primitives.

This module moves the `did:web:idn-state.etzhayyim.com` app actor off its
dedicated Cloudflare Worker path. The public edge keeps only XRPC/MCP
facade duties; these functions run as Zeebe jobs in Kubernetes and write
the same graph-visible state the Worker previously wrote via the kotoba Datom log.
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


PRIMARY_DID = "did:web:idn-state.etzhayyim.com"
DOMAIN_CODE = "idn"
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
{"path":"setkab","name":"Sekretariat Kabinet","nameEn":"Cabinet Secretariat","website":"https://setkab.go.id/","contract":"UUD 1945 Pasal 17","tags":["cofog:01","executive","cabinet"],"orgTier":"ministry"}
{"path":"kemhan","name":"Kementerian Pertahanan","nameEn":"Ministry of Defence","website":"https://www.kemhan.go.id/","contract":"UUD 1945 Pasal 30","tags":["cofog:02","defence"],"orgTier":"ministry"}
{"path":"kemlu","name":"Kementerian Luar Negeri","nameEn":"Ministry of Foreign Affairs","website":"https://kemlu.go.id/","contract":"UUD 1945 Pasal 11","tags":["cofog:01.2","foreign-affairs"],"orgTier":"ministry"}
{"path":"kemkeu","name":"Kementerian Keuangan","nameEn":"Ministry of Finance","website":"https://www.kemenkeu.go.id/","contract":"UUD 1945 Pasal 23","tags":["cofog:01.1","finance","budget","taxation"],"orgTier":"ministry"}
{"path":"kemenkumham","name":"Kementerian Hukum dan HAM","nameEn":"Ministry of Law and Human Rights","website":"https://www.kemenkumham.go.id/","contract":"UUD 1945 Pasal 27-28","tags":["cofog:03","justice","human-rights"],"orgTier":"ministry"}
{"path":"kemendagri","name":"Kementerian Dalam Negeri","nameEn":"Ministry of Home Affairs","website":"https://www.kemendagri.go.id/","contract":"UU No. 39 Tahun 2008","tags":["cofog:01","interior","regional"],"orgTier":"ministry"}
{"path":"polri","name":"Kepolisian Negara Republik Indonesia","nameEn":"Indonesian National Police","website":"https://www.polri.go.id/","contract":"UU No. 2 Tahun 2002","tags":["cofog:03","police","public-order"],"orgTier":"ministry"}
{"path":"kemendikbud","name":"Kementerian Pendidikan, Kebudayaan, Riset, dan Teknologi","nameEn":"Ministry of Education, Culture, Research and Technology","website":"https://www.kemdikbud.go.id/","contract":"UU No. 20 Tahun 2003","tags":["cofog:09","education","culture","research"],"orgTier":"ministry"}
{"path":"kemenkes","name":"Kementerian Kesehatan","nameEn":"Ministry of Health","website":"https://www.kemkes.go.id/","contract":"UU No. 36 Tahun 2009","tags":["cofog:07","health"],"orgTier":"ministry"}
{"path":"kementan","name":"Kementerian Pertanian","nameEn":"Ministry of Agriculture","website":"https://www.pertanian.go.id/","contract":"UU No. 19 Tahun 2013","tags":["cofog:04.2","agriculture"],"orgTier":"ministry"}
{"path":"kemenperindag","name":"Kementerian Perindustrian","nameEn":"Ministry of Industry","website":"https://www.kemenperin.go.id/","contract":"UU No. 3 Tahun 2014","tags":["cofog:04","industry"],"orgTier":"ministry"}
{"path":"kemendag","name":"Kementerian Perdagangan","nameEn":"Ministry of Trade","website":"https://kemendag.go.id/","contract":"UU No. 7 Tahun 2014","tags":["cofog:04","trade","commerce"],"orgTier":"ministry"}
{"path":"esdm","name":"Kementerian Energi dan Sumber Daya Mineral","nameEn":"Ministry of Energy and Mineral Resources","website":"https://www.esdm.go.id/","contract":"UU No. 4 Tahun 2009","tags":["cofog:04","energy","minerals"],"orgTier":"ministry"}
{"path":"kemenhub","name":"Kementerian Perhubungan","nameEn":"Ministry of Transportation","website":"https://dephub.go.id/","contract":"UU No. 17 Tahun 2008","tags":["cofog:04.5","transport"],"orgTier":"ministry"}
{"path":"klhk","name":"Kementerian Lingkungan Hidup dan Kehutanan","nameEn":"Ministry of Environment and Forestry","website":"https://www.menlhk.go.id/","contract":"UU No. 41 Tahun 1999","tags":["cofog:05","environment","forestry"],"orgTier":"ministry"}
{"path":"kemenag","name":"Kementerian Agama","nameEn":"Ministry of Religious Affairs","website":"https://www.kemenag.go.id/","contract":"PP No. 48 Tahun 2014","tags":["cofog:08","religious"],"orgTier":"ministry"}
{"path":"kemensos","name":"Kementerian Sosial","nameEn":"Ministry of Social Affairs","website":"https://www.kemsos.go.id/","contract":"UU No. 11 Tahun 2009","tags":["cofog:10","social"],"orgTier":"ministry"}
{"path":"mahkamah","name":"Mahkamah Agung","nameEn":"Supreme Court","website":"https://www.mahkamahagung.go.id/","contract":"UUD 1945 Pasal 24","tags":["cofog:03","judiciary"],"orgTier":"agency"}
{"path":"dpr","name":"Dewan Perwakilan Rakyat","nameEn":"House of Representatives","website":"https://www.dpr.go.id/","contract":"UUD 1945 Pasal 19","tags":["cofog:01","legislature"],"orgTier":"agency"}
"""

_STATE_NDJSON = """\
{"path":"provinsi:aceh","name":"Aceh","nameEn":"Aceh","website":"https://www.acehprov.go.id/","contract":"UU No. 11 Tahun 2006","tags":["cofog:01","provinsi","special"],"orgTier":"state"}
{"path":"provinsi:sumut","name":"Sumatera Utara","nameEn":"North Sumatra","website":"https://www.sumutprov.go.id/","contract":"UU No. 24 Tahun 1956","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:sumbar","name":"Sumatera Barat","nameEn":"West Sumatra","website":"https://www.sumbarprov.go.id/","contract":"UU No. 61 Tahun 1958","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:riau","name":"Riau","nameEn":"Riau","website":"https://www.riau.go.id/","contract":"UU No. 61 Tahun 1958","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:kepri","name":"Kepulauan Riau","nameEn":"Riau Islands","website":"https://www.kepriprov.go.id/","contract":"UU No. 25 Tahun 2002","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:jambi","name":"Jambi","nameEn":"Jambi","website":"https://jambiprov.go.id/","contract":"UU No. 61 Tahun 1958","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:sumsel","name":"Sumatera Selatan","nameEn":"South Sumatra","website":"https://www.sumselprov.go.id/","contract":"UU No. 25 Tahun 1959","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:babel","name":"Bangka Belitung","nameEn":"Bangka Belitung Islands","website":"https://www.babelprov.go.id/","contract":"UU No. 27 Tahun 2000","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:bengkulu","name":"Bengkulu","nameEn":"Bengkulu","website":"https://bengkuluprov.go.id/","contract":"UU No. 9 Tahun 1967","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:lampung","name":"Lampung","nameEn":"Lampung","website":"https://www.lampungprov.go.id/","contract":"UU No. 14 Tahun 1964","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:banten","name":"Banten","nameEn":"Banten","website":"https://www.bantenprov.go.id/","contract":"UU No. 23 Tahun 2000","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:jabar","name":"Jawa Barat","nameEn":"West Java","website":"https://jabarprov.go.id/","contract":"UU No. 11 Tahun 1950","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:dki","name":"DKI Jakarta","nameEn":"DKI Jakarta","website":"https://www.jakarta.go.id/","contract":"UU No. 29 Tahun 2007","tags":["cofog:01","provinsi","capital","special"],"orgTier":"state"}
{"path":"provinsi:jateng","name":"Jawa Tengah","nameEn":"Central Java","website":"https://jatengprov.go.id/","contract":"UU No. 10 Tahun 1950","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:diy","name":"D.I. Yogyakarta","nameEn":"Yogyakarta Special Region","website":"https://www.jogjaprov.go.id/","contract":"UU No. 13 Tahun 2012","tags":["cofog:01","provinsi","special"],"orgTier":"state"}
{"path":"provinsi:jatim","name":"Jawa Timur","nameEn":"East Java","website":"https://www.jatimprov.go.id/","contract":"UU No. 2 Tahun 1950","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:bali","name":"Bali","nameEn":"Bali","website":"https://www.baliprov.go.id/","contract":"UU No. 64 Tahun 1958","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:ntb","name":"Nusa Tenggara Barat","nameEn":"West Nusa Tenggara","website":"https://www.ntbprov.go.id/","contract":"UU No. 64 Tahun 1958","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:ntt","name":"Nusa Tenggara Timur","nameEn":"East Nusa Tenggara","website":"https://www.nttprov.go.id/","contract":"UU No. 64 Tahun 1958","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:kalbar","name":"Kalimantan Barat","nameEn":"West Kalimantan","website":"https://www.kalbarprov.go.id/","contract":"UU No. 25 Tahun 1956","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:kalteng","name":"Kalimantan Tengah","nameEn":"Central Kalimantan","website":"https://www.kalteng.go.id/","contract":"UU No. 21 Tahun 1958","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:kalsel","name":"Kalimantan Selatan","nameEn":"South Kalimantan","website":"https://www.kalselprov.go.id/","contract":"UU No. 25 Tahun 1956","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:kaltim","name":"Kalimantan Timur","nameEn":"East Kalimantan","website":"https://www.kaltimprov.go.id/","contract":"UU No. 25 Tahun 1956","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:kaltara","name":"Kalimantan Utara","nameEn":"North Kalimantan","website":"https://www.kaltaraprov.go.id/","contract":"UU No. 20 Tahun 2012","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:sulut","name":"Sulawesi Utara","nameEn":"North Sulawesi","website":"https://www.sulutprov.go.id/","contract":"UU No. 13 Tahun 1964","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:gorontalo","name":"Gorontalo","nameEn":"Gorontalo","website":"https://www.gorontaloprov.go.id/","contract":"UU No. 38 Tahun 2000","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:sulteng","name":"Sulawesi Tengah","nameEn":"Central Sulawesi","website":"https://sultengprov.go.id/","contract":"UU No. 13 Tahun 1964","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:sulbar","name":"Sulawesi Barat","nameEn":"West Sulawesi","website":"https://sulbarprov.go.id/","contract":"UU No. 26 Tahun 2004","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:sulsel","name":"Sulawesi Selatan","nameEn":"South Sulawesi","website":"https://sulselprov.go.id/","contract":"UU No. 13 Tahun 1964","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:sultra","name":"Sulawesi Tenggara","nameEn":"Southeast Sulawesi","website":"https://www.sultraprov.go.id/","contract":"UU No. 13 Tahun 1964","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:maluku","name":"Maluku","nameEn":"Maluku","website":"https://malukuprov.go.id/","contract":"UU No. 20 Tahun 1958","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:malut","name":"Maluku Utara","nameEn":"North Maluku","website":"https://www.malutprov.go.id/","contract":"UU No. 46 Tahun 1999","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:papua","name":"Papua","nameEn":"Papua","website":"https://www.papua.go.id/","contract":"UU No. 2 Tahun 2021","tags":["cofog:01","provinsi","special"],"orgTier":"state"}
{"path":"provinsi:papbar","name":"Papua Barat","nameEn":"West Papua","website":"https://www.papuabaratprov.go.id/","contract":"UU No. 45 Tahun 1999","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:papsel","name":"Papua Selatan","nameEn":"South Papua","website":"https://papuaselatan.go.id/","contract":"UU No. 14 Tahun 2022","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:papteng","name":"Papua Tengah","nameEn":"Central Papua","website":"https://papuatengah.go.id/","contract":"UU No. 15 Tahun 2022","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:papeg","name":"Papua Pegunungan","nameEn":"Highland Papua","website":"https://papuapegunungan.go.id/","contract":"UU No. 16 Tahun 2022","tags":["cofog:01","provinsi"],"orgTier":"state"}
{"path":"provinsi:papbardaya","name":"Papua Barat Daya","nameEn":"Southwest Papua","website":"https://papuabaratdaya.go.id/","contract":"UU No. 29 Tahun 2022","tags":["cofog:01","provinsi"],"orgTier":"state"}
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
    params: dict[str, Any] = {
        "vertex_id": _vertex_id(path),
        "domain_code": DOMAIN_CODE,
        "owner_did": PRIMARY_DID,
        "path": path,
        **updates,
    }
    get_kotoba_client().insert_row("vertex_gov_org", params)


def _get_org(path: str) -> dict[str, Any] | None:
    keys = [
        "path", "name", "name_en", "website", "contract", "tags", "org_tier",
        "site_domain_slug", "site_followed", "did_registered",
        "last_ingested_at", "last_content_hash", "last_kyumei_at",
        "last_shinka_at", "created_at",
    ]
    row = get_kotoba_client().select_first_where(
        "vertex_gov_org", "vertex_id", _vertex_id(path), columns=keys + ["domain_code", "owner_did"]
    )
    if not row or str(row.get("domain_code", DOMAIN_CODE)) != DOMAIN_CODE or str(row.get("owner_did", PRIMARY_DID)) != PRIMARY_DID:
        return None
    return {k: row[k] for k in keys if k in row}


def task_gov_idn_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: in-Python filter for name_en != ''
    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, columns=["path", "owner_did", "name_en"], limit=10000)
    existing = {str(r["path"]) for r in rows if str(r.get("owner_did")) == PRIMARY_DID and str(r.get("name_en", ""))}
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_idn_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_idn_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: in-Python filter, ordering, and count over full domain list
    all_rows = get_kotoba_client().select_where(
        "vertex_gov_org", "domain_code", DOMAIN_CODE,
        columns=["path", "owner_did", "name", "name_en", "website", "did_registered", "org_tier"],
        limit=5000
    )
    filtered = [
        r for r in all_rows
        if str(r.get("owner_did")) == PRIMARY_DID
        and str(r.get("name_en", ""))
        and (not org_tier or str(r.get("org_tier")) == org_tier)
    ]
    filtered.sort(key=lambda x: str(x.get("path", "")))
    total = len(filtered)
    page_rows = filtered[offset : offset + limit]

    return {
        "orgs": [
            {
                "path": str(r.get("path", "")),
                "did": f"{PRIMARY_DID}:{str(r.get('path', ''))}",
                "name": str(r.get("name", "")),
                "nameEn": str(r.get("name_en", "")),
                "website": str(r.get("website", "")),
                "didRegistered": str(r.get("did_registered", "")) == "true",
            }
            for r in page_rows
        ],
        "total": total,
    }


async def task_gov_idn_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: in-Python filter and ordering for registration
    all_rows = get_kotoba_client().select_where(
        "vertex_gov_org", "domain_code", DOMAIN_CODE,
        columns=[
            "path", "name", "name_en", "website", "contract", "tags", "org_tier",
            "site_domain_slug", "site_followed", "last_ingested_at",
            "last_content_hash", "last_kyumei_at", "last_shinka_at", "created_at",
            "owner_did", "did_registered"
        ],
        limit=5000
    )
    filtered = [
        r for r in all_rows
        if str(r.get("owner_did")) == PRIMARY_DID
        and str(r.get("name_en", ""))
        and str(r.get("did_registered", "")) != "true"
    ]
    filtered.sort(key=lambda x: str(x.get("path", "")))
    rows = filtered[:limit]
    registered: list[str] = []
    pds_results: list[dict[str, Any]] = []
    for r in rows:
        row = {
            "path": str(r.get("path", "")),
            "name": str(r.get("name", "")),
            "name_en": str(r.get("name_en", "")),
            "website": str(r.get("website", "")),
            "contract": str(r.get("contract", "")),
            "tags": json.loads(str(r.get("tags") or "[]")),
            "org_tier": str(r.get("org_tier", "")),
            "site_domain_slug": str(r.get("site_domain_slug", "")),
            "site_followed": str(r.get("site_followed", "") or "false"),
            "last_ingested_at": str(r.get("last_ingested_at", "")),
            "last_content_hash": str(r.get("last_content_hash", "")),
            "last_kyumei_at": str(r.get("last_kyumei_at", "")),
            "last_shinka_at": str(r.get("last_shinka_at", "")),
            "created_at": str(r.get("created_at", "") or _utc_now_iso()),
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


async def task_gov_idn_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: in-Python filter and ordering for site deps
    all_rows = get_kotoba_client().select_where(
        "vertex_gov_org", "domain_code", DOMAIN_CODE,
        columns=[
            "path", "name", "name_en", "website", "contract", "tags", "org_tier",
            "site_domain_slug", "did_registered", "last_ingested_at",
            "last_content_hash", "last_kyumei_at", "last_shinka_at", "created_at",
            "owner_did", "site_followed"
        ],
        limit=5000
    )
    filtered = [
        r for r in all_rows
        if str(r.get("owner_did")) == PRIMARY_DID
        and str(r.get("site_followed", "")) != "true"
        and str(r.get("site_domain_slug", "")) != ""
    ]
    filtered.sort(key=lambda x: str(x.get("path", "")))
    rows = filtered[:limit]
    for r in rows:
        path = str(r.get("path", ""))
        slug = str(r.get("site_domain_slug", ""))
        await _pds_xrpc("app.bsky.graph.follow", {"did": f"did:web:site.etzhayyim.com:{slug}"})
        row = {
            "path": path,
            "name": str(r.get("name", "")),
            "name_en": str(r.get("name_en", "")),
            "website": str(r.get("website", "")),
            "contract": str(r.get("contract", "")),
            "tags": json.loads(str(r.get("tags") or "[]")),
            "org_tier": str(r.get("org_tier", "")),
            "site_domain_slug": slug,
            "site_followed": "true",
            "did_registered": str(r.get("did_registered", "") or "false"),
            "last_ingested_at": str(r.get("last_ingested_at", "")),
            "last_content_hash": str(r.get("last_content_hash", "")),
            "last_kyumei_at": str(r.get("last_kyumei_at", "")),
            "last_shinka_at": str(r.get("last_shinka_at", "")),
            "created_at": str(r.get("created_at", "") or _utc_now_iso()),
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


async def task_gov_idn_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: in-Python filter and ordering for wet updates sync
    all_rows = get_kotoba_client().select_where(
        "vertex_gov_org", "domain_code", DOMAIN_CODE,
        columns=["path", "name_en", "website", "site_domain_slug", "last_content_hash", "last_ingested_at", "owner_did"],
        limit=5000
    )
    filtered = [
        r for r in all_rows
        if str(r.get("owner_did")) == PRIMARY_DID
        and str(r.get("site_domain_slug", "")) != ""
        and (not str(r.get("last_ingested_at", "")) or str(r.get("last_ingested_at", "")) < cutoff_iso)
    ]
    filtered.sort(key=lambda x: str(x.get("last_ingested_at", "")))
    rows = filtered[:limit]
    checked = 0
    updated = 0
    posted = 0
    now = _utc_now_iso()
    for r in rows:
        path = str(r.get("path", ""))
        name_en = str(r.get("name_en", ""))
        website = str(r.get("website", ""))
        slug = str(r.get("site_domain_slug", ""))
        last_hash = str(r.get("last_content_hash", ""))
        if not path or not slug:
            continue
        checked += 1
        # R0: fetchone over wet chunks
        wet_rows = get_kotoba_client().select_where("vertex_wet_chunk", "domain", slug, columns=["markdown", "content_hash", "crawled_at"], limit=100)
        wet = max(wet_rows, key=lambda x: str(x.get("crawled_at", ""))) if wet_rows else None
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
        markdown = str(wet.get("markdown", ""))
        content_hash = str(wet.get("content_hash", ""))
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


async def task_gov_idn_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: in-Python filter and ordering for shinka
    all_rows = get_kotoba_client().select_where(
        "vertex_gov_org", "domain_code", DOMAIN_CODE,
        columns=["path", "name_en", "owner_did", "did_registered", "last_shinka_at"],
        limit=5000
    )
    filtered = [
        r for r in all_rows
        if str(r.get("owner_did")) == PRIMARY_DID
        and str(r.get("did_registered", "")) == "true"
    ]
    filtered.sort(key=lambda x: str(x.get("last_shinka_at", "")))
    rows = filtered[:limit]
    posted = 0
    now = _utc_now_iso()
    for r in rows:
        path = str(r.get("path", ""))
        name_en = str(r.get("name_en", ""))
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


async def task_gov_idn_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_idn_seed_orgs, seedLimit)
    register = await task_gov_idn_register_dids(registerLimit)
    follow = await task_gov_idn_follow_site_deps(followLimit)
    ingest = await task_gov_idn_sync_wet_updates(ingestLimit)
    shinka = await task_gov_idn_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govIdn.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_idn_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIdn.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_idn_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIdn.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_idn_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIdn.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_idn_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIdn.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_idn_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIdn.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_idn_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIdn.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_idn_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govIdn.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_idn_heartbeat_tick)
