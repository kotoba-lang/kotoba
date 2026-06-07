"""South Korea states actor primitives.

This module moves the `did:web:kor-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:kor-state.etzhayyim.com"
DOMAIN_CODE = "kor"
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
{"path":"daetongnyeongshil","name":"대통령실","nameEn":"Office of the President","website":"https://www.president.go.kr/","contract":"정부조직법","tags":["cofog:01","executive","president"],"orgTier":"ministry"}
{"path":"gukhoe","name":"국회","nameEn":"National Assembly","website":"https://www.assembly.go.kr/","contract":"헌법 제40조","tags":["cofog:01","legislature"],"orgTier":"agency"}
{"path":"daebeopwon","name":"대법원","nameEn":"Supreme Court","website":"https://www.scourt.go.kr/","contract":"법원조직법","tags":["cofog:03","judiciary"],"orgTier":"agency"}
{"path":"hunsepeo","name":"헌법재판소","nameEn":"Constitutional Court","website":"https://www.ccourt.go.kr/","contract":"헌법재판소법","tags":["cofog:03","constitutional-court"],"orgTier":"agency"}
{"path":"gukmubeomuicheong","name":"국무조정실","nameEn":"Office for Government Policy Coordination","website":"https://www.opm.go.kr/","contract":"정부조직법","tags":["cofog:01","coordination"],"orgTier":"ministry"}
{"path":"gukbangbu","name":"국방부","nameEn":"Ministry of National Defense","website":"https://www.mnd.go.kr/","contract":"정부조직법","tags":["cofog:02","defence"],"orgTier":"ministry"}
{"path":"oegyobu","name":"외교부","nameEn":"Ministry of Foreign Affairs","website":"https://www.mofa.go.kr/","contract":"정부조직법","tags":["cofog:01.2","foreign-affairs"],"orgTier":"ministry"}
{"path":"beommubu","name":"법무부","nameEn":"Ministry of Justice","website":"https://www.moj.go.kr/","contract":"정부조직법","tags":["cofog:03","justice"],"orgTier":"ministry"}
{"path":"gihoekjaejongbu","name":"기획재정부","nameEn":"Ministry of Economy and Finance","website":"https://www.moef.go.kr/","contract":"정부조직법","tags":["cofog:01.1","finance","economy","budget"],"orgTier":"ministry"}
{"path":"haenganganjeongbu","name":"행정안전부","nameEn":"Ministry of the Interior and Safety","website":"https://www.mois.go.kr/","contract":"정부조직법","tags":["cofog:01","interior","safety"],"orgTier":"ministry"}
{"path":"gyoyukbu","name":"교육부","nameEn":"Ministry of Education","website":"https://www.moe.go.kr/","contract":"정부조직법","tags":["cofog:09","education"],"orgTier":"ministry"}
{"path":"gwahakgisuljeongbotongsinbu","name":"과학기술정보통신부","nameEn":"Ministry of Science and ICT","website":"https://www.msit.go.kr/","contract":"정부조직법","tags":["cofog:09","science","ict"],"orgTier":"ministry"}
{"path":"munhwacheoyukgwangwangbu","name":"문화체육관광부","nameEn":"Ministry of Culture, Sports and Tourism","website":"https://www.mcst.go.kr/","contract":"정부조직법","tags":["cofog:08","culture","sports","tourism"],"orgTier":"ministry"}
{"path":"nongnimsikpumbu","name":"농림축산식품부","nameEn":"Ministry of Agriculture, Food and Rural Affairs","website":"https://www.mafra.go.kr/","contract":"정부조직법","tags":["cofog:04.2","agriculture","food"],"orgTier":"ministry"}
{"path":"saneobtongsangjaewonbu","name":"산업통상자원부","nameEn":"Ministry of Trade, Industry and Energy","website":"https://www.motie.go.kr/","contract":"정부조직법","tags":["cofog:04","trade","industry","energy"],"orgTier":"ministry"}
{"path":"bogeonfujibu","name":"보건복지부","nameEn":"Ministry of Health and Welfare","website":"https://www.mohw.go.kr/","contract":"정부조직법","tags":["cofog:07","health","welfare"],"orgTier":"ministry"}
{"path":"hwangyeongbu","name":"환경부","nameEn":"Ministry of Environment","website":"https://www.me.go.kr/","contract":"정부조직법","tags":["cofog:05","environment"],"orgTier":"ministry"}
{"path":"guktogyotongbu","name":"국토교통부","nameEn":"Ministry of Land, Infrastructure and Transport","website":"https://www.molit.go.kr/","contract":"정부조직법","tags":["cofog:04.5","land","transport","infrastructure"],"orgTier":"ministry"}
{"path":"haeyangsusan","name":"해양수산부","nameEn":"Ministry of Oceans and Fisheries","website":"https://www.mof.go.kr/","contract":"정부조직법","tags":["cofog:04.2","oceans","fisheries"],"orgTier":"ministry"}
{"path":"jungsobenchangeop","name":"중소벤처기업부","nameEn":"Ministry of SMEs and Startups","website":"https://www.mss.go.kr/","contract":"정부조직법","tags":["cofog:04","smes","startups"],"orgTier":"ministry"}
{"path":"yeoseongbu","name":"여성가족부","nameEn":"Ministry of Gender Equality and Family","website":"https://www.mogef.go.kr/","contract":"정부조직법","tags":["cofog:10","gender","family"],"orgTier":"ministry"}
"""

_STATE_NDJSON = """\
{"path":"gwangyeok:seoul","name":"서울특별시","nameEn":"Seoul Metropolitan City","website":"https://www.seoul.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok","capital"],"orgTier":"state"}
{"path":"gwangyeok:busan","name":"부산광역시","nameEn":"Busan Metropolitan City","website":"https://www.busan.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok"],"orgTier":"state"}
{"path":"gwangyeok:incheon","name":"인천광역시","nameEn":"Incheon Metropolitan City","website":"https://www.incheon.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok"],"orgTier":"state"}
{"path":"gwangyeok:daegu","name":"대구광역시","nameEn":"Daegu Metropolitan City","website":"https://www.daegu.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok"],"orgTier":"state"}
{"path":"gwangyeok:gwangju","name":"광주광역시","nameEn":"Gwangju Metropolitan City","website":"https://www.gwangju.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok"],"orgTier":"state"}
{"path":"gwangyeok:daejeon","name":"대전광역시","nameEn":"Daejeon Metropolitan City","website":"https://www.daejeon.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok"],"orgTier":"state"}
{"path":"gwangyeok:ulsan","name":"울산광역시","nameEn":"Ulsan Metropolitan City","website":"https://www.ulsan.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok"],"orgTier":"state"}
{"path":"gwangyeok:sejong","name":"세종특별자치시","nameEn":"Sejong Special Autonomous City","website":"https://www.sejong.go.kr/","contract":"세종특별자치시 설치 등에 관한 특별법","tags":["cofog:01","gwangyeok","administrative-capital"],"orgTier":"state"}
{"path":"gwangyeok:gyeonggi","name":"경기도","nameEn":"Gyeonggi Province","website":"https://www.gg.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok","do"],"orgTier":"state"}
{"path":"gwangyeok:gangwon","name":"강원도","nameEn":"Gangwon Province","website":"https://www.gwd.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok","do"],"orgTier":"state"}
{"path":"gwangyeok:chungbuk","name":"충청북도","nameEn":"North Chungcheong Province","website":"https://www.chungbuk.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok","do"],"orgTier":"state"}
{"path":"gwangyeok:chungnam","name":"충청남도","nameEn":"South Chungcheong Province","website":"https://www.chungnam.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok","do"],"orgTier":"state"}
{"path":"gwangyeok:jeonbuk","name":"전라북도","nameEn":"North Jeolla Province","website":"https://www.jeonbuk.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok","do"],"orgTier":"state"}
{"path":"gwangyeok:jeonnam","name":"전라남도","nameEn":"South Jeolla Province","website":"https://www.jeonnam.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok","do"],"orgTier":"state"}
{"path":"gwangyeok:gyeongbuk","name":"경상북도","nameEn":"North Gyeongsang Province","website":"https://www.gb.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok","do"],"orgTier":"state"}
{"path":"gwangyeok:gyeongnam","name":"경상남도","nameEn":"South Gyeongsang Province","website":"https://www.gyeongnam.go.kr/","contract":"지방자치법","tags":["cofog:01","gwangyeok","do"],"orgTier":"state"}
{"path":"gwangyeok:jeju","name":"제주특별자치도","nameEn":"Jeju Special Autonomous Province","website":"https://www.jeju.go.kr/","contract":"제주특별자치도 설치 및 국제자유도시 조성을 위한 특별법","tags":["cofog:01","gwangyeok","autonomous"],"orgTier":"state"}
"""

_OFFICIAL_SOURCE_URLS = [
    "https://www.gov.kr/",
    "https://www.president.go.kr/",
    "https://www.assembly.go.kr/",
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
                    [_OFFICIAL_SOURCE_URLS[0]],
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
        "User-Agent": "etzhayyim-kotodama-gov-kor/0.1",
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
    params: dict[str, Any] = {
        "vertex_id": _vertex_id(path),
        **updates,
    }
    get_kotoba_client().insert_row("vertex_gov_org", params)


def _get_org(path: str) -> dict[str, Any] | None:
    row = get_kotoba_client().select_first_where("vertex_gov_org", "path", path)
    if row and row.get("domain_code") == DOMAIN_CODE and row.get("owner_did") == PRIMARY_DID:
        keys = [
            "path", "name", "name_en", "website", "contract", "tags", "org_tier",
            "site_domain_slug", "site_followed", "did_registered",
            "last_ingested_at", "last_content_hash", "last_kyumei_at",
            "last_shinka_at", "created_at",
        ]
        return {k: row.get(k) for k in keys}
    return None


def task_gov_kor_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=10000)
    # R0: in-Python filter for owner_did and name_en != ''
    existing = {
        str(r.get("path")) for r in rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
    }
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_kor_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_kor_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))

    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    # R0: in-Python filter for owner_did, name_en != '', org_tier, sort by path
    filtered = [
        r for r in rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en")
        and (not org_tier or r.get("org_tier") == org_tier)
    ]
    total = len(filtered)
    filtered.sort(key=lambda x: str(x.get("path") or ""))
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


async def task_gov_kor_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))

    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    # R0: in-Python filter for owner_did, name_en != '', did_registered != 'true', sort by path
    filtered = [
        r for r in rows
        if r.get("owner_did") == PRIMARY_DID and r.get("name_en") and str(r.get("did_registered")) != "true"
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    page_rows = filtered[:limit]

    registered: list[str] = []
    pds_results: list[dict[str, Any]] = []
    for r in page_rows:
        try:
            tags_parsed = json.loads(str(r.get("tags") or "[]"))
        except Exception:
            tags_parsed = []
        row = {
            "path": str(r.get("path") or ""),
            "name": str(r.get("name") or ""),
            "name_en": str(r.get("name_en") or ""),
            "website": str(r.get("website") or ""),
            "contract": str(r.get("contract") or ""),
            "tags": tags_parsed,
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


async def task_gov_kor_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0

    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    # R0: in-Python filter for owner_did, site_followed != 'true', site_domain_slug != '', sort by path
    filtered = [
        r for r in rows
        if r.get("owner_did") == PRIMARY_DID
        and str(r.get("site_followed")) != "true"
        and r.get("site_domain_slug")
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    page_rows = filtered[:limit]

    for r in page_rows:
        path = str(r.get("path") or "")
        slug = str(r.get("site_domain_slug") or "")
        await _pds_xrpc("app.bsky.graph.follow", {"did": f"did:web:site.etzhayyim.com:{slug}"})
        try:
            tags_parsed = json.loads(str(r.get("tags") or "[]"))
        except Exception:
            tags_parsed = []
        row = {
            "path": path,
            "name": str(r.get("name") or ""),
            "name_en": str(r.get("name_en") or ""),
            "website": str(r.get("website") or ""),
            "contract": str(r.get("contract") or ""),
            "tags": tags_parsed,
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


async def task_gov_kor_ingest_official_sources(
    limit: int = 10,
    processBatchSize: int = 10,
    includeOrgSites: bool = True,
) -> dict[str, Any]:
    """Queue official South Korean government sources through site.etzhayyim.com."""
    limit = max(1, min(int(limit or 10), 50))
    process_batch_size = max(1, min(int(processBatchSize or 10), 50))
    targets: list[dict[str, str]] = [
        {"kind": "page", "url": url}
        for url in _OFFICIAL_SOURCE_URLS
    ]
    if includeOrgSites:
        rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
        # R0: in-Python filter for owner_did, website != '', sort by website, distinct
        filtered = [
            r for r in rows
            if r.get("owner_did") == PRIMARY_DID and r.get("website")
        ]
        seen_websites = set()
        distinct_filtered = []
        for r in filtered:
            w = str(r.get("website") or "")
            if w not in seen_websites:
                seen_websites.add(w)
                distinct_filtered.append(r)
        distinct_filtered.sort(key=lambda x: str(x.get("website") or ""))
        for r in distinct_filtered[:limit]:
            host = _url_to_hostname(str(r.get("website") or ""))
            if host:
                targets.append({"kind": "domain", "domain": host})

    enqueued = 0
    results: list[dict[str, Any]] = []
    for target in targets[: limit + len(_OFFICIAL_SOURCE_URLS)]:
        if target["kind"] == "page":
            result = await _pds_xrpc(
                "com.etzhayyim.apps.site.crawlPage",
                {"url": target["url"], "topics": ["government", "kor", "official-source"], "depth": 0},
            )
        else:
            result = await _pds_xrpc(
                "com.etzhayyim.apps.site.crawlDomain",
                {
                    "domain": target["domain"],
                    "topics": ["government", "kor", "official-source"],
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


async def task_gov_kor_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")

    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    # R0: in-Python filter for owner_did, site_domain_slug != '', last_ingested_at < cutoff, sort by last_ingested_at
    def _needs_ingest(r: dict[str, Any]) -> bool:
        if r.get("owner_did") != PRIMARY_DID or not r.get("site_domain_slug"):
            return False
        lia = r.get("last_ingested_at")
        return not lia or str(lia) < cutoff_iso
    filtered = [r for r in rows if _needs_ingest(r)]
    filtered.sort(key=lambda x: str(x.get("last_ingested_at") or ""))
    page_rows = filtered[:limit]

    checked = 0
    updated = 0
    posted = 0
    now = _utc_now_iso()
    for r in page_rows:
        path = str(r.get("path") or "")
        name_en = str(r.get("name_en") or "")
        website = str(r.get("website") or "")
        slug = str(r.get("site_domain_slug") or "")
        last_hash = str(r.get("last_content_hash") or "")
        if not path or not slug:
            continue
        checked += 1

        domains = _wet_domain_candidates(website, slug)

        wet_rows = []
        for d in domains:
            wet_rows.extend(get_kotoba_client().select_where("vertex_wet_chunk", "domain", d, limit=2000))
        # R0: in-Python filter to find wet chunk matching any domain, sort by crawled_at DESC, limit 1
        wet = None
        if wet_rows:
            wet_rows.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
            wet = wet_rows[0]

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


async def task_gov_kor_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))

    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, limit=2000)
    # R0: in-Python filter for owner_did, did_registered == 'true', sort by last_shinka_at
    filtered = [
        r for r in rows
        if r.get("owner_did") == PRIMARY_DID and str(r.get("did_registered")) == "true"
    ]
    filtered.sort(key=lambda x: str(x.get("last_shinka_at") or ""))
    page_rows = filtered[:limit]

    posted = 0
    now = _utc_now_iso()
    for r in page_rows:
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
    return {"ok": True, "posted": posted, "touched": len(page_rows)}


async def task_gov_kor_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_kor_seed_orgs, seedLimit)
    official_sources = await task_gov_kor_ingest_official_sources(limit=max(1, min(seedLimit, 10)))
    register = await task_gov_kor_register_dids(registerLimit)
    follow = await task_gov_kor_follow_site_deps(followLimit)
    ingest = await task_gov_kor_sync_wet_updates(ingestLimit)
    shinka = await task_gov_kor_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govKor.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_kor_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govKor.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_kor_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govKor.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_kor_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govKor.ingestOfficialSources",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_kor_ingest_official_sources)
    worker.task(
        task_type="xrpc.com.etzhayyim.govKor.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_kor_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govKor.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_kor_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govKor.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_kor_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govKor.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_kor_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govKor.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_kor_heartbeat_tick)
