"""Hanrei (判例) collection primitives (ADR-0056 BPMN-as-actor).

Implements 13 Zeebe task types for the hanrei.etzhayyim.com actor:
  hanrei.register.courtProfiles    — register 6 JP court + 2 source DIDs
  hanrei.register.jurisdictions    — register 75 national + 8 intl court jurisdiction DIDs
  hanrei.collect.cases             — create collection jobs for courts.go.jp (6 courts)
  hanrei.collect.caseDetail        — single case detail collection job
  hanrei.collect.casesBatch        — batch up to 50 case detail jobs
  hanrei.collect.gazette           — kanpo collection job
  hanrei.collect.legislation       — e-Gov API collection job
  hanrei.collect.egovLaws          — e-Gov法令API 4 categories (CC BY 4.0)
  hanrei.collect.wikidataCourts    — Wikidata SPARQL collection job (CC0)
  hanrei.collect.jurisdictionCases — per-jurisdiction case collection
  hanrei.collect.jurisdictionLegislation — per-jurisdiction legislation
  hanrei.collect.jurisdictionGazette     — per-jurisdiction gazette
  hanrei.seed.cases                — seed 5 landmark JP Supreme Court cases

All DB writes use sync_cursor (psycopg3 sync pool, RisingWave PG :4566).
Table: vertex_hanrei_collection_job / vertex_hanrei_case_record / vertex_hanrei_jurisdiction
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import json
import time
import uuid
from typing import Any



_OWNER_DID = "did:web:hanrei.etzhayyim.com"
_COL_JOB = "com.etzhayyim.apps.hanrei.collectionJob"
_COL_CASE = "com.etzhayyim.apps.hanrei.caseRecord"
_COL_JURISDICTION = "com.etzhayyim.apps.hanrei.jurisdiction"
_COL_COURT = "com.etzhayyim.apps.hanrei.court"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _job_vid(job_id: str) -> str:
    return f"at://{_OWNER_DID}/{_COL_JOB}/{job_id}"


def _case_vid(rkey: str) -> str:
    return f"at://{_OWNER_DID}/{_COL_CASE}/{rkey}"


def _jurisdiction_vid(iso3: str) -> str:
    h = hashlib.sha256(iso3.encode()).hexdigest()[:16]
    return f"at://{_OWNER_DID}/{_COL_JURISDICTION}/{h}"


def _court_vid(court_id: str) -> str:
    h = hashlib.sha256(court_id.encode()).hexdigest()[:16]
    return f"at://{_OWNER_DID}/{_COL_COURT}/{h}"


def _new_job_id() -> str:
    return uuid.uuid4().hex[:16]


# ---------------------------------------------------------------------------
# Embedded JP court + source data (mirrors app.ts jpCourts / jpSources)
# ---------------------------------------------------------------------------

_JP_COURTS = [
    {"courtId": "supreme", "name": "最高裁判所", "did": f"{_OWNER_DID}:court:supreme",
     "searchUrl": "https://courts.go.jp/app/hanrei_jp/search2"},
    {"courtId": "ip_high", "name": "知的財産高等裁判所", "did": f"{_OWNER_DID}:court:ip_high",
     "searchUrl": "https://courts.go.jp/app/hanrei_jp/search5"},
    {"courtId": "high", "name": "高等裁判所", "did": f"{_OWNER_DID}:court:high",
     "searchUrl": "https://courts.go.jp/app/hanrei_jp/search3"},
    {"courtId": "district", "name": "地方裁判所", "did": f"{_OWNER_DID}:court:district",
     "searchUrl": "https://courts.go.jp/app/hanrei_jp/search4"},
    {"courtId": "family", "name": "家庭裁判所", "did": f"{_OWNER_DID}:court:family",
     "searchUrl": "https://courts.go.jp/app/hanrei_jp/search6"},
    {"courtId": "summary_court", "name": "簡易裁判所", "did": f"{_OWNER_DID}:court:summary_court",
     "searchUrl": "https://courts.go.jp/app/hanrei_jp/search7"},
]

_JP_SOURCES = [
    {"sourceId": "kanpo", "name": "官報", "did": f"{_OWNER_DID}:source:kanpo",
     "url": "https://kanpou.npb.go.jp"},
    {"sourceId": "egov", "name": "e-Gov法令API", "did": f"{_OWNER_DID}:source:egov",
     "url": "https://laws.e-gov.go.jp/api/1/"},
]

_EGOV_CATEGORIES = [
    {"id": 1, "name": "憲法", "url": "https://laws.e-gov.go.jp/api/1/lawdata?category=1"},
    {"id": 2, "name": "法律", "url": "https://laws.e-gov.go.jp/api/1/lawdata?category=2"},
    {"id": 3, "name": "政令", "url": "https://laws.e-gov.go.jp/api/1/lawdata?category=3"},
    {"id": 4, "name": "勅令", "url": "https://laws.e-gov.go.jp/api/1/lawdata?category=4"},
]

_WIKIDATA_SPARQL_QUERIES = [
    {"queryId": "courts", "name": "Courts", "url": "https://query.wikidata.org/sparql",
     "sparql": "SELECT ?court ?courtLabel WHERE { ?court wdt:P31 wd:Q1229605 . SERVICE wikibase:label { bd:serviceParam wikibase:language 'ja,en'. } } LIMIT 500"},
    {"queryId": "legal_systems", "name": "Legal Systems", "url": "https://query.wikidata.org/sparql",
     "sparql": "SELECT ?ls ?lsLabel WHERE { ?ls wdt:P31 wd:Q3907330 . SERVICE wikibase:label { bd:serviceParam wikibase:language 'ja,en'. } } LIMIT 200"},
    {"queryId": "intl_courts", "name": "International Courts", "url": "https://query.wikidata.org/sparql",
     "sparql": "SELECT ?court ?courtLabel WHERE { ?court wdt:P31 wd:Q56895574 . SERVICE wikibase:label { bd:serviceParam wikibase:language 'ja,en'. } } LIMIT 100"},
]

_SEED_CASES = [
    {"rkey": "supreme-1973-jp-paternalism",
     "title": "尊属殺重罰規定違憲判決", "caseNumber": "昭和45年(あ)第1310号",
     "court": "supreme", "decisionDate": "1973-04-04",
     "summary": "刑法200条（尊属殺重罰規定）を憲法14条1項に違反し無効と判示。"},
    {"rkey": "supreme-1969-jp-chizai",
     "title": "京都府知事選挙無効訴訟", "caseNumber": "昭和43年(行ツ)第120号",
     "court": "supreme", "decisionDate": "1969-06-25",
     "summary": "行政訴訟における原告適格の解釈に関するリーディングケース。"},
    {"rkey": "supreme-2013-jp-inheritance",
     "title": "婚外子相続分差別違憲決定", "caseNumber": "平成24年(許)第984号",
     "court": "supreme", "decisionDate": "2013-09-04",
     "summary": "婚外子の法定相続分を嫡出子の2分の1とした民法900条4号ただし書きを違憲と判示。"},
    {"rkey": "supreme-2015-jp-anpo",
     "title": "女性再婚禁止期間違憲判決", "caseNumber": "平成25年(オ)第1079号",
     "court": "supreme", "decisionDate": "2015-12-16",
     "summary": "女性に6か月の再婚禁止期間を設ける民法733条を100日超過部分について違憲と判示。"},
    {"rkey": "supreme-2019-jp-residency",
     "title": "国籍法3条1項違憲判決", "caseNumber": "平成19年(行ツ)第164号",
     "court": "supreme", "decisionDate": "2019-09-25",
     "summary": "非嫡出子の国籍取得を婚姻認知に限定した国籍法3条1項を憲法14条1項に違反と判示。"},
]


# ---------------------------------------------------------------------------
# hanrei.register.courtProfiles
# ---------------------------------------------------------------------------

def task_hanrei_register_court_profiles() -> dict:
    """Register 6 JP court DIDs and 2 source DIDs as vertex_hanrei_court rows."""
    now = _utc_now()
    registered = []
    errors = []
    for court in _JP_COURTS:
        vid = _court_vid(court["courtId"])
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "INSERT INTO vertex_hanrei_court "
                    "(vertex_id, court_id, name, court_did, search_url, "
                    "actor_did, org_did, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (vid, court["courtId"], court["name"], court["did"],
                     court["searchUrl"], _OWNER_DID, "anon", now),
                )
            registered.append({"courtId": court["courtId"], "vertexId": vid})
        except Exception as e:  # noqa: BLE001
            errors.append({"courtId": court["courtId"], "error": str(e)})
    for source in _JP_SOURCES:
        vid = _court_vid(f"source:{source['sourceId']}")
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "INSERT INTO vertex_hanrei_court "
                    "(vertex_id, court_id, name, court_did, search_url, "
                    "actor_did, org_did, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (vid, f"source:{source['sourceId']}", source["name"],
                     source["did"], source["url"], _OWNER_DID, "anon", now),
                )
            registered.append({"courtId": f"source:{source['sourceId']}", "vertexId": vid})
        except Exception as e:  # noqa: BLE001
            errors.append({"courtId": f"source:{source['sourceId']}", "error": str(e)})
    return {"registered": len(registered), "errors": len(errors), "profiles": registered}


# ---------------------------------------------------------------------------
# hanrei.register.jurisdictions
# ---------------------------------------------------------------------------

def task_hanrei_register_jurisdictions(
    offset: int = 0,
    limit: int = 100,
) -> dict:
    """Register jurisdiction DIDs by reading from vertex_hanrei_jurisdiction_def or seed minimal rows."""
    # Minimal jurisdiction seed — iso3 codes for all 75 national + 8 intl courts
    # Full data lives in app.ts; here we register vertex_id rows for graph linkage
    _iso3_list = [
        "jpn", "kor", "chn", "twn", "hkg", "mng",
        "sgp", "mys", "idn", "tha", "vnm", "phl", "mmr", "khm",
        "ind", "pak", "bgd", "lka",
        "aus", "nzl",
        "usa", "can", "mex",
        "bra", "arg", "col", "chl", "per",
        "gbr", "fra", "deu", "ita", "esp", "nld", "bel", "che", "aut", "irl", "prt",
        "swe", "nor", "dnk", "fin", "isl",
        "pol", "cze", "svk", "hun", "rou", "bgr", "hrv", "srb", "svn", "est", "lva", "ltu",
        "grc", "cyp", "mlt",
        "rus", "ukr", "blr", "geo",
        "tur", "isr", "jor", "qat", "are", "sau",
        "zaf", "ken", "gha", "nga", "egy", "mar", "eth",
        # international courts (8)
        "icj", "icc", "echr", "cjeu", "iachr", "achpr", "itlos", "wto_ab",
    ]
    off = max(0, int(offset or 0))
    lim = max(1, min(int(limit or 100), 200))
    batch = _iso3_list[off: off + lim]
    now = _utc_now()
    registered = []
    errors = []
    for iso3 in batch:
        vid = _jurisdiction_vid(iso3)
        did = f"{_OWNER_DID}:jurisdiction:{iso3}"
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "INSERT INTO vertex_hanrei_jurisdiction "
                    "(vertex_id, iso3, jurisdiction_did, actor_did, org_did, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (vid, iso3, did, _OWNER_DID, "anon", now),
                )
            registered.append({"iso3": iso3, "vertexId": vid})
        except Exception as e:  # noqa: BLE001
            errors.append({"iso3": iso3, "error": str(e)})
    return {
        "registered": len(registered),
        "errors": len(errors),
        "offset": off,
        "limit": lim,
        "total": len(_iso3_list),
    }


# ---------------------------------------------------------------------------
# hanrei.collect.cases
# ---------------------------------------------------------------------------

def task_hanrei_collect_cases(
    court: str = "",
    maxPages: int = 10,
) -> dict:
    """Create collection jobs for courts.go.jp search pages."""
    now = _utc_now()
    courts = (
        [c for c in _JP_COURTS if c["courtId"] == court]
        if court
        else _JP_COURTS
    )
    if not courts:
        return {"error": f"court '{court}' not found", "jobs": 0}

    lim = max(1, min(int(maxPages or 10), 100))
    created = []
    for c in courts:
        for page in range(1, lim + 1):
            job_id = _new_job_id()
            vid = _job_vid(job_id)
            url = f"{c['searchUrl']}?page={page}"
            try:
                if True:
                    client = get_kotoba_client()
                    _res = client.q(
                        "INSERT INTO vertex_hanrei_collection_job "
                        "(vertex_id, job_id, job_type, court_id, target_url, page, "
                        "status, actor_did, org_did, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (vid, job_id, "cases", c["courtId"], url, page,
                         "queued", _OWNER_DID, "anon", now),
                    )
                created.append({"jobId": job_id, "court": c["courtId"], "page": page})
            except Exception as e:  # noqa: BLE001
                created.append({"jobId": job_id, "court": c["courtId"], "page": page,
                                 "error": str(e)})
    return {"jobs": len(created), "maxPages": lim, "created": created}


# ---------------------------------------------------------------------------
# hanrei.collect.caseDetail
# ---------------------------------------------------------------------------

def task_hanrei_collect_case_detail(
    detailUrl: str = "",
    court: str = "supreme",
) -> dict:
    """Create a single collection job for a case detail page."""
    if not detailUrl:
        return {"error": "detailUrl is required"}
    job_id = _new_job_id()
    vid = _job_vid(job_id)
    now = _utc_now()
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_hanrei_collection_job "
                "(vertex_id, job_id, job_type, court_id, target_url, "
                "status, actor_did, org_did, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (vid, job_id, "case_detail", str(court), str(detailUrl),
                 "queued", _OWNER_DID, "anon", now),
            )
    except Exception as e:  # noqa: BLE001
        return {"error": f"hanrei.collect.caseDetail failed: {e}",
                "jobId": job_id, "vertexId": vid}
    return {"jobId": job_id, "vertexId": vid, "status": "queued", "detailUrl": detailUrl}


# ---------------------------------------------------------------------------
# hanrei.collect.casesBatch
# ---------------------------------------------------------------------------

def task_hanrei_collect_cases_batch(
    detailUrls: list | None = None,
    court: str = "supreme",
) -> dict:
    """Create up to 50 collection jobs for case detail pages."""
    urls = detailUrls if isinstance(detailUrls, list) else []
    urls = [str(u) for u in urls[:50] if isinstance(u, str) and u.startswith("http")]
    if not urls:
        return {"error": "detailUrls list is empty or invalid", "jobs": 0}
    now = _utc_now()
    created = []
    errors = []
    for url in urls:
        job_id = _new_job_id()
        vid = _job_vid(job_id)
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "INSERT INTO vertex_hanrei_collection_job "
                    "(vertex_id, job_id, job_type, court_id, target_url, "
                    "status, actor_did, org_did, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (vid, job_id, "case_detail", str(court), url,
                     "queued", _OWNER_DID, "anon", now),
                )
            created.append({"jobId": job_id, "url": url})
        except Exception as e:  # noqa: BLE001
            errors.append({"url": url, "error": str(e)})
    return {"jobs": len(created), "errors": len(errors), "created": created}


# ---------------------------------------------------------------------------
# hanrei.collect.gazette
# ---------------------------------------------------------------------------

def task_hanrei_collect_gazette(
    startDate: str = "",
    endDate: str = "",
) -> dict:
    """Create a collection job for 官報 (kanpo.npb.go.jp)."""
    job_id = _new_job_id()
    vid = _job_vid(job_id)
    now = _utc_now()
    base_url = "https://kanpou.npb.go.jp"
    target_url = base_url
    if startDate:
        target_url = f"{base_url}?from={startDate}"
        if endDate:
            target_url += f"&to={endDate}"
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_hanrei_collection_job "
                "(vertex_id, job_id, job_type, source_id, target_url, "
                "start_date, end_date, status, actor_did, org_did, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (vid, job_id, "gazette", "kanpo", target_url,
                 str(startDate) or None, str(endDate) or None,
                 "queued", _OWNER_DID, "anon", now),
            )
    except Exception as e:  # noqa: BLE001
        return {"error": f"hanrei.collect.gazette failed: {e}",
                "jobId": job_id, "vertexId": vid}
    return {"jobId": job_id, "vertexId": vid, "status": "queued", "targetUrl": target_url}


# ---------------------------------------------------------------------------
# hanrei.collect.legislation
# ---------------------------------------------------------------------------

def task_hanrei_collect_legislation(
    lawId: str = "",
    query: str = "",
) -> dict:
    """Create a collection job for e-Gov法令API."""
    job_id = _new_job_id()
    vid = _job_vid(job_id)
    now = _utc_now()
    base_url = "https://laws.e-gov.go.jp/api/1/"
    if lawId:
        target_url = f"{base_url}lawdata/{lawId}"
    elif query:
        target_url = f"{base_url}articles;{query}"
    else:
        target_url = f"{base_url}lawlists/1"
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_hanrei_collection_job "
                "(vertex_id, job_id, job_type, source_id, target_url, "
                "law_id, status, actor_did, org_did, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (vid, job_id, "legislation", "egov", target_url,
                 str(lawId) or None, "queued", _OWNER_DID, "anon", now),
            )
    except Exception as e:  # noqa: BLE001
        return {"error": f"hanrei.collect.legislation failed: {e}",
                "jobId": job_id, "vertexId": vid}
    return {"jobId": job_id, "vertexId": vid, "status": "queued", "targetUrl": target_url}


# ---------------------------------------------------------------------------
# hanrei.collect.egovLaws
# ---------------------------------------------------------------------------

def task_hanrei_collect_egov_laws(
    categories: list | None = None,
) -> dict:
    """Create collection jobs for e-Gov法令API categories (CC BY 4.0)."""
    cats = [int(c) for c in (categories or [1, 2, 3, 4]) if str(c).isdigit()]
    cats = [c for c in cats if 1 <= c <= 4]
    if not cats:
        cats = [1, 2, 3, 4]
    now = _utc_now()
    created = []
    errors = []
    for cat in _EGOV_CATEGORIES:
        if cat["id"] not in cats:
            continue
        job_id = _new_job_id()
        vid = _job_vid(job_id)
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "INSERT INTO vertex_hanrei_collection_job "
                    "(vertex_id, job_id, job_type, source_id, target_url, "
                    "category_id, category_name, status, actor_did, org_did, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (vid, job_id, "egov_laws", "egov", cat["url"],
                     cat["id"], cat["name"], "queued", _OWNER_DID, "anon", now),
                )
            created.append({"jobId": job_id, "categoryId": cat["id"], "name": cat["name"]})
        except Exception as e:  # noqa: BLE001
            errors.append({"categoryId": cat["id"], "error": str(e)})
    return {"jobs": len(created), "errors": len(errors), "created": created}


# ---------------------------------------------------------------------------
# hanrei.collect.wikidataCourts
# ---------------------------------------------------------------------------

def task_hanrei_collect_wikidata_courts(
    queries: list | None = None,
) -> dict:
    """Create collection jobs for Wikidata SPARQL (CC0)."""
    query_ids = set(queries) if isinstance(queries, list) else set()
    now = _utc_now()
    created = []
    errors = []
    for q in _WIKIDATA_SPARQL_QUERIES:
        if query_ids and q["queryId"] not in query_ids:
            continue
        job_id = _new_job_id()
        vid = _job_vid(job_id)
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "INSERT INTO vertex_hanrei_collection_job "
                    "(vertex_id, job_id, job_type, source_id, target_url, "
                    "query_id, sparql, status, actor_did, org_did, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (vid, job_id, "wikidata_sparql", "wikidata", q["url"],
                     q["queryId"], q["sparql"], "queued", _OWNER_DID, "anon", now),
                )
            created.append({"jobId": job_id, "queryId": q["queryId"]})
        except Exception as e:  # noqa: BLE001
            errors.append({"queryId": q["queryId"], "error": str(e)})
    return {"jobs": len(created), "errors": len(errors), "created": created}


# ---------------------------------------------------------------------------
# hanrei.collect.jurisdictionCases
# ---------------------------------------------------------------------------

def task_hanrei_collect_jurisdiction_cases(
    iso3: str = "",
    caseDbUrl: str = "",
) -> dict:
    """Create a collection job for a jurisdiction's case database."""
    if not iso3:
        return {"error": "iso3 is required"}
    target_url = str(caseDbUrl or "").strip()
    if not target_url:
        # Attempt lookup from vertex_hanrei_jurisdiction
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "SELECT case_db_url FROM vertex_hanrei_jurisdiction "
                    "WHERE iso3 = %s LIMIT 1",
                    (iso3,),
                )
                row = (_res[0] if _res else None)
                if row and row[0]:
                    target_url = row[0]
        except Exception:  # noqa: BLE001
            pass
    if not target_url:
        return {"error": f"no caseDbUrl for jurisdiction {iso3}", "iso3": iso3}
    job_id = _new_job_id()
    vid = _job_vid(job_id)
    now = _utc_now()
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_hanrei_collection_job "
                "(vertex_id, job_id, job_type, iso3, target_url, "
                "status, actor_did, org_did, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (vid, job_id, "jurisdiction_cases", iso3, target_url,
                 "queued", _OWNER_DID, "anon", now),
            )
    except Exception as e:  # noqa: BLE001
        return {"error": f"hanrei.collect.jurisdictionCases failed: {e}",
                "jobId": job_id, "iso3": iso3}
    return {"jobId": job_id, "vertexId": vid, "iso3": iso3, "targetUrl": target_url, "status": "queued"}


# ---------------------------------------------------------------------------
# hanrei.collect.jurisdictionLegislation
# ---------------------------------------------------------------------------

def task_hanrei_collect_jurisdiction_legislation(
    iso3: str = "",
    legislationUrl: str = "",
) -> dict:
    """Create a collection job for a jurisdiction's legislation database."""
    if not iso3:
        return {"error": "iso3 is required"}
    target_url = str(legislationUrl or "").strip()
    if not target_url:
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "SELECT legislation_url FROM vertex_hanrei_jurisdiction "
                    "WHERE iso3 = %s LIMIT 1",
                    (iso3,),
                )
                row = (_res[0] if _res else None)
                if row and row[0]:
                    target_url = row[0]
        except Exception:  # noqa: BLE001
            pass
    if not target_url:
        return {"error": f"no legislationUrl for jurisdiction {iso3}", "iso3": iso3}
    job_id = _new_job_id()
    vid = _job_vid(job_id)
    now = _utc_now()
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_hanrei_collection_job "
                "(vertex_id, job_id, job_type, iso3, target_url, "
                "status, actor_did, org_did, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (vid, job_id, "jurisdiction_legislation", iso3, target_url,
                 "queued", _OWNER_DID, "anon", now),
            )
    except Exception as e:  # noqa: BLE001
        return {"error": f"hanrei.collect.jurisdictionLegislation failed: {e}",
                "jobId": job_id, "iso3": iso3}
    return {"jobId": job_id, "vertexId": vid, "iso3": iso3, "targetUrl": target_url, "status": "queued"}


# ---------------------------------------------------------------------------
# hanrei.collect.jurisdictionGazette
# ---------------------------------------------------------------------------

def task_hanrei_collect_jurisdiction_gazette(
    iso3: str = "",
    gazetteUrl: str = "",
) -> dict:
    """Create a collection job for a jurisdiction's official gazette."""
    if not iso3:
        return {"error": "iso3 is required"}
    target_url = str(gazetteUrl or "").strip()
    if not target_url:
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "SELECT gazette_url FROM vertex_hanrei_jurisdiction "
                    "WHERE iso3 = %s LIMIT 1",
                    (iso3,),
                )
                row = (_res[0] if _res else None)
                if row and row[0]:
                    target_url = row[0]
        except Exception:  # noqa: BLE001
            pass
    if not target_url:
        return {"error": f"no gazetteUrl for jurisdiction {iso3}", "iso3": iso3}
    job_id = _new_job_id()
    vid = _job_vid(job_id)
    now = _utc_now()
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_hanrei_collection_job "
                "(vertex_id, job_id, job_type, iso3, target_url, "
                "status, actor_did, org_did, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (vid, job_id, "jurisdiction_gazette", iso3, target_url,
                 "queued", _OWNER_DID, "anon", now),
            )
    except Exception as e:  # noqa: BLE001
        return {"error": f"hanrei.collect.jurisdictionGazette failed: {e}",
                "jobId": job_id, "iso3": iso3}
    return {"jobId": job_id, "vertexId": vid, "iso3": iso3, "targetUrl": target_url, "status": "queued"}


# ---------------------------------------------------------------------------
# hanrei.seed.cases
# ---------------------------------------------------------------------------

def task_hanrei_seed_cases(
    dryRun: bool = False,
) -> dict:
    """Seed 5 landmark JP Supreme Court cases into vertex_hanrei_case_record."""
    now = _utc_now()
    seeded = []
    errors = []
    for case in _SEED_CASES:
        vid = _case_vid(case["rkey"])
        if dryRun:
            seeded.append({"rkey": case["rkey"], "title": case["title"], "dryRun": True})
            continue
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "INSERT INTO vertex_hanrei_case_record "
                    "(vertex_id, rkey, title, case_number, court_id, decision_date, "
                    "summary, iso3, status, actor_did, org_did, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (vid, case["rkey"], case["title"], case["caseNumber"],
                     case["court"], case["decisionDate"], case["summary"],
                     "jpn", "seeded", _OWNER_DID, "anon", now),
                )
            seeded.append({"rkey": case["rkey"], "title": case["title"], "vertexId": vid})
        except Exception as e:  # noqa: BLE001
            errors.append({"rkey": case["rkey"], "error": str(e)})
    return {"seeded": len(seeded), "errors": len(errors), "cases": seeded, "dryRun": bool(dryRun)}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire hanrei primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    t("hanrei.register.courtProfiles", task_hanrei_register_court_profiles)
    t("hanrei.register.jurisdictions", task_hanrei_register_jurisdictions)
    t("hanrei.collect.cases", task_hanrei_collect_cases)
    t("hanrei.collect.caseDetail", task_hanrei_collect_case_detail)
    t("hanrei.collect.casesBatch", task_hanrei_collect_cases_batch)
    t("hanrei.collect.gazette", task_hanrei_collect_gazette)
    t("hanrei.collect.legislation", task_hanrei_collect_legislation)
    t("hanrei.collect.egovLaws", task_hanrei_collect_egov_laws)
    t("hanrei.collect.wikidataCourts", task_hanrei_collect_wikidata_courts)
    t("hanrei.collect.jurisdictionCases", task_hanrei_collect_jurisdiction_cases)
    t("hanrei.collect.jurisdictionLegislation", task_hanrei_collect_jurisdiction_legislation)
    t("hanrei.collect.jurisdictionGazette", task_hanrei_collect_jurisdiction_gazette)
    t("hanrei.seed.cases", task_hanrei_seed_cases)


__all__ = [
    "register",
    "task_hanrei_register_court_profiles",
    "task_hanrei_register_jurisdictions",
    "task_hanrei_collect_cases",
    "task_hanrei_collect_case_detail",
    "task_hanrei_collect_cases_batch",
    "task_hanrei_collect_gazette",
    "task_hanrei_collect_legislation",
    "task_hanrei_collect_egov_laws",
    "task_hanrei_collect_wikidata_courts",
    "task_hanrei_collect_jurisdiction_cases",
    "task_hanrei_collect_jurisdiction_legislation",
    "task_hanrei_collect_jurisdiction_gazette",
    "task_hanrei_seed_cases",
]
