"""Zeebe task handlers for houbun law ingest.

This is the production path for durable law ingestion.  It intentionally keeps
the first implementation narrow: Japanese e-Gov law bodies, one law id per
shard, deterministic writes to `vertex_houbun_*`, and cursor advancement only
after read-after-write verification.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from typing import Any

import sqlite3
from contextlib import contextmanager
from kotodama.ingest.core import (
    IngestArtifact,
    IngestRun,
    mark_run_finished,
    upsert_artifact,
    upsert_cursor,
    upsert_run,
)



@contextmanager
def sync_cursor():
    db_dir = os.environ.get("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "ingest_houbun.db")
    with sqlite3.connect(db_path) as conn:
        _res = client.q('PRAGMA journal_mode=WAL;')
        _res = client.q('''CREATE TABLE IF NOT EXISTS vertex_houbun_statute (
            vertex_id TEXT PRIMARY KEY, created_date TEXT, sensitivity_ord INTEGER, owner_did TEXT,
            rkey TEXT, repo TEXT, jurisdiction TEXT, statute_id TEXT, title TEXT, title_native TEXT,
            statute_type TEXT, enacted_date TEXT, effective_date TEXT, repealed_date TEXT, source TEXT,
            source_url TEXT, license TEXT, language TEXT, article_count INTEGER, last_verified TEXT,
            created_at TEXT, org_id TEXT, user_id TEXT, actor_id TEXT
        )''')
        _res = client.q('''CREATE TABLE IF NOT EXISTS vertex_houbun_article (
            vertex_id TEXT PRIMARY KEY, created_date TEXT, sensitivity_ord INTEGER, owner_did TEXT,
            rkey TEXT, repo TEXT, statute_ref TEXT, article_no TEXT, section TEXT, title TEXT,
            text TEXT, language TEXT, article_did TEXT, blake3_hash TEXT, amended_at TEXT,
            source_url TEXT, created_at TEXT, org_id TEXT, user_id TEXT, actor_id TEXT
        )''')
        _res = client.q('''CREATE TABLE IF NOT EXISTS edge_houbun_statute_article (
            edge_id TEXT PRIMARY KEY, src_vid TEXT, dst_vid TEXT, created_date TEXT,
            sensitivity_ord INTEGER, owner_did TEXT, article_no TEXT, order_key INTEGER,
            created_at TEXT, org_id TEXT, user_id TEXT, actor_id TEXT
        )''')
        yield conn.cursor()

ACTOR_DID = "did:web:houbun.etzhayyim.com"
JPN_PATH_DID = f"{ACTOR_DID}:jpn:e-gov"
EGOV_BASE = "https://laws.e-gov.go.jp/api/2"
EGOV_LAW_DATA = f"{EGOV_BASE}/law_data"
EGOV_LAW_LIST = f"{EGOV_BASE}/laws"
SOURCE_ID = "egov-jpn"

USA_CFR_PATH_DID = f"{ACTOR_DID}:usa:cfr"
USA_CFR_SOURCE_ID = "govinfo-cfr"
ECFR_BASE = "https://www.ecfr.gov/api"

CHN_NPC_PATH_DID = f"{ACTOR_DID}:chn:npc-fdb"
CHN_NPC_SOURCE_ID = "npc-fdb-chn"
NPC_FDB_BASE = "https://flk.npc.gov.cn"

INGEST_FAMILY = "houbun"
WS = re.compile(r"\s+")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> date:
    return datetime.now(timezone.utc).date()


def _clean(value: Any) -> str:
    return WS.sub(" ", str(value or "")).strip()


def _hash(*parts: Any, size: int = 6) -> str:
    payload = "|".join(_clean(x) for x in parts)
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=size).hexdigest()


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "etzhayyim-houbun-zeebe/0.1 (+https://houbun.etzhayyim.com)",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _flatten(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return WS.sub(" ", node).strip()
    if isinstance(node, (int, float)):
        return str(node)
    if isinstance(node, list):
        return " ".join(x for x in (_flatten(v) for v in node) if x).strip()
    if isinstance(node, dict):
        if "#text" in node:
            return _flatten(node["#text"])
        if "$" in node:
            return _flatten(node["$"])
        if "children" in node:
            return _flatten(node.get("children"))
        parts: list[str] = []
        for key, value in node.items():
            if str(key) in {"attr", "tag"} or str(key).startswith(("@", "_")):
                continue
            text = _flatten(value)
            if text:
                parts.append(text)
        return " ".join(parts).strip()
    return ""


def _children_with_tag(node: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    return [c for c in node.get("children", []) if isinstance(c, dict) and c.get("tag") == tag]


def _first_child(node: dict[str, Any], tag: str) -> dict[str, Any] | None:
    rows = _children_with_tag(node, tag)
    return rows[0] if rows else None


def _find_first_tag(node: Any, tag: str) -> dict[str, Any] | None:
    if isinstance(node, list):
        for item in node:
            found = _find_first_tag(item, tag)
            if found is not None:
                return found
        return None
    if not isinstance(node, dict):
        return None
    if node.get("tag") == tag:
        return node
    for child in node.get("children", []):
        found = _find_first_tag(child, tag)
        if found is not None:
            return found
    return None


def _iter_articles(root: Any) -> list[dict[str, Any]]:
    """Extract e-Gov v2 Article nodes from both tag/children and legacy dict shapes."""
    out: list[dict[str, Any]] = []
    section_tags = {
        "Part": "PartTitle",
        "Chapter": "ChapterTitle",
        "Section": "SectionTitle",
        "Subsection": "SubsectionTitle",
        "Division": "DivisionTitle",
    }

    def visit(node: Any, section: str | None) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item, section)
            return
        if not isinstance(node, dict):
            return

        tag = str(node.get("tag") or "")
        local_section = section
        title_tag = section_tags.get(tag)
        if title_tag:
            title = _flatten(_first_child(node, title_tag))
            if title:
                local_section = title

        if tag == "Article":
            title = _flatten(_first_child(node, "ArticleTitle"))
            caption = _flatten(_first_child(node, "ArticleCaption"))
            attr = node.get("attr") if isinstance(node.get("attr"), dict) else {}
            article_no = title or (f"第{attr.get('Num')}条" if attr.get("Num") else f"art-{len(out) + 1}")
            body_parts: list[str] = []
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("tag") in {"ArticleTitle", "ArticleCaption"}:
                    continue
                text = _flatten(child)
                if text:
                    body_parts.append(text)
            body = WS.sub(" ", " ".join(body_parts)).strip()
            if article_no or body:
                out.append(
                    {
                        "article_no": article_no,
                        "title": caption or None,
                        "section": local_section,
                        "text": body,
                    }
                )
            return

        article = node.get("Article")
        if article is not None:
            articles = article if isinstance(article, list) else [article]
            for item in articles:
                visit(_legacy_article_node(item), local_section)

        for child in node.get("children", []):
            visit(child, local_section)
        for key, value in node.items():
            if key in {"Article", "children", "attr", "tag"}:
                continue
            if isinstance(value, (dict, list)):
                visit(value, local_section)

    visit(root, None)
    return out


def _legacy_article_node(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"tag": "Article", "children": [{"tag": "Sentence", "children": [item]}]}
    children: list[dict[str, Any]] = []
    attr = item.get("@") if isinstance(item.get("@"), dict) else {}
    if item.get("ArticleTitle"):
        children.append({"tag": "ArticleTitle", "children": [item.get("ArticleTitle")]})
    if item.get("ArticleCaption"):
        children.append({"tag": "ArticleCaption", "children": [item.get("ArticleCaption")]})
    for key, value in item.items():
        if key in {"ArticleTitle", "ArticleCaption", "@"}:
            continue
        children.append({"tag": key, "children": [value]})
    return {"tag": "Article", "attr": attr, "children": children}


def _extract_law_payload(raw: dict[str, Any], law_id: str, *, max_articles: int) -> dict[str, Any]:
    law_info = raw.get("law_info") or raw.get("lawInfo") or raw.get("LawInfo") or {}
    revision = raw.get("revision_info") or raw.get("revisionInfo") or {}
    law_full = raw.get("law_full_text") or raw.get("lawFullText") or raw.get("LawFullText") or raw
    law_body = (
        law_full.get("law_body")
        or law_full.get("LawBody")
        or _find_first_tag(law_full, "LawBody")
        or raw.get("law_body")
        or raw.get("lawBody")
        or raw.get("Law", {}).get("LawBody")
    )
    title = (
        _flatten(revision.get("law_title"))
        or _flatten(law_info.get("law_title") or law_info.get("lawTitle"))
        or _flatten(law_full.get("LawTitle"))
        or law_id
    )
    articles = _iter_articles(law_body) if law_body is not None else []
    if max_articles > 0:
        articles = articles[:max_articles]
    return {
        "law_id": law_id,
        "title": title,
        "statute_type": _flatten(law_info.get("law_type") or law_info.get("lawType")) or "law",
        "enacted_date": law_info.get("promulgation_date") or law_info.get("promulgationDate"),
        "effective_date": revision.get("amendment_enforcement_date") or law_info.get("enforcement_date"),
        "repealed_date": revision.get("repeal_date"),
        "source_url": f"https://laws.e-gov.go.jp/law/{law_id}",
        "articles": articles,
    }


def _insert_ignore(cur: Any, table: str, id_col: str, values: dict[str, Any]) -> int:
    clean = {k: v for k, v in values.items() if v is not None}
    cols = list(clean)
    placeholders = ", ".join(["?"] * len(cols))
    _res = client.q(
        f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) "
        f"VALUES ({placeholders})",
        (*[clean[c] for c in cols],),
    )
    return int((len(_res) if isinstance(_res, list) else 1) or 0)


def _flush_rw() -> None:
    if not os.environ.get("RW_URL") or not shutil.which("psql"):
        return
    subprocess.run(
        ["psql", os.environ["RW_URL"], "-v", "ON_ERROR_STOP=1", "-Atc", "FLUSH;"],
        env={**os.environ, "PGCONNECT_TIMEOUT": os.environ.get("PGCONNECT_TIMEOUT", "10")},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=int(os.environ.get("RW_PSQL_TIMEOUT_SEC", "240")),
        check=True,
    )


def _fetch_ecfr_title_xml(title_num: int, date_str: str) -> str:
    url = f"{ECFR_BASE}/versioner/v1/full/{date_str}/title-{title_num}.xml"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/xml",
            "User-Agent": "etzhayyim-houbun-zeebe/0.1 (+https://houbun.etzhayyim.com)",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read().decode("utf-8")


def _parse_ecfr_xml(
    xml_str: str, title_num: int, title_name: str, year: int, *, max_articles: int
) -> dict[str, Any]:
    root = ET.fromstring(xml_str)
    articles: list[dict[str, Any]] = []

    def get_text(elem: ET.Element) -> str:
        parts: list[str] = []
        if elem.text:
            parts.append(elem.text)
        for child in elem:
            parts.append(get_text(child))
            if child.tail:
                parts.append(child.tail)
        return WS.sub(" ", " ".join(p for p in parts if p)).strip()

    def walk(node: ET.Element, part_heading: str | None = None) -> None:
        if max_articles > 0 and len(articles) >= max_articles:
            return
        node_type = node.get("TYPE", "")
        current_part = part_heading
        if node_type == "PART":
            head = node.find("HEAD")
            if head is not None:
                current_part = get_text(head)
        if node_type == "SECTION":
            section_no = node.get("N", "")
            head = node.find("HEAD")
            raw_title = get_text(head) if head is not None else ""
            clean_title = re.sub(r"^§\s*[\d.]+\s*", "", raw_title).strip() or None
            body_parts: list[str] = []
            for child in node:
                if child.tag == "HEAD":
                    continue
                body_parts.append(get_text(child))
            body = WS.sub(" ", " ".join(p for p in body_parts if p)).strip()
            articles.append({
                "article_no": f"§ {section_no}" if section_no else raw_title,
                "title": clean_title,
                "section": current_part,
                "text": body,
            })
            return
        for child in node:
            walk(child, current_part)

    walk(root)
    law_id = f"cfr-title-{title_num}-{year}"
    return {
        "law_id": law_id,
        "title": title_name or f"CFR Title {title_num}",
        "statute_type": "regulation",
        "enacted_date": None,
        "effective_date": f"{year}-01-01",
        "repealed_date": None,
        "source_url": f"https://www.ecfr.gov/current/title-{title_num}",
        "articles": articles,
    }


def _write_payload_usa(payload: dict[str, Any]) -> dict[str, int]:
    law_id = str(payload["law_id"])
    current = now_iso()
    statute_vid = f"at://{USA_CFR_PATH_DID}/com.etzhayyim.apps.houbun.statute/{law_id}"
    articles: list[dict[str, Any]] = list(payload.get("articles") or [])
    source_url = str(payload.get("source_url") or f"https://www.ecfr.gov/current/{law_id}")
    article_inserted = 0
    edge_inserted = 0
    if True:
        client = get_kotoba_client()
        statute_inserted = _insert_ignore(
            cur,
            "vertex_houbun_statute",
            "vertex_id",
            {
                "vertex_id": statute_vid,
                "created_date": today(),
                "sensitivity_ord": 1,
                "owner_did": USA_CFR_PATH_DID,
                "rkey": law_id,
                "repo": USA_CFR_PATH_DID,
                "jurisdiction": "usa",
                "statute_id": law_id,
                "title": payload.get("title") or law_id,
                "title_native": payload.get("title") or law_id,
                "statute_type": payload.get("statute_type") or "regulation",
                "enacted_date": payload.get("enacted_date"),
                "effective_date": payload.get("effective_date"),
                "repealed_date": payload.get("repealed_date"),
                "source": "ecfr",
                "source_url": source_url,
                "license": "public-domain",
                "language": "en",
                "article_count": len(articles),
                "last_verified": current,
                "created_at": current,
                "org_id": "etzhayyim",
                "user_id": "system",
                "actor_id": "sys.houbun",
            },
        )
        _res = client.q(
            """
            UPDATE vertex_houbun_statute
               SET title = ?,
                   title_native = ?,
                   article_count = ?,
                   last_verified = ?
             WHERE vertex_id = ?
            """,
            (payload.get("title") or law_id, payload.get("title") or law_id, len(articles), current, statute_vid),
        )
        for idx, article in enumerate(articles):
            article_no = str(article.get("article_no") or f"art-{idx + 1}")
            h = _hash("usa", law_id, article_no, payload.get("effective_date") or "")
            article_did = f"{ACTOR_DID}:article:{h}"
            article_vid = f"at://{article_did}/com.etzhayyim.apps.houbun.article/{h}"
            inserted = _insert_ignore(
                cur,
                "vertex_houbun_article",
                "vertex_id",
                {
                    "vertex_id": article_vid,
                    "created_date": today(),
                    "sensitivity_ord": 1,
                    "owner_did": article_did,
                    "rkey": h,
                    "repo": article_did,
                    "statute_ref": statute_vid,
                    "article_no": article_no,
                    "section": article.get("section"),
                    "title": article.get("title"),
                    "text": article.get("text") or "",
                    "language": "en",
                    "article_did": article_did,
                    "blake3_hash": h,
                    "amended_at": payload.get("effective_date"),
                    "source_url": source_url,
                    "created_at": current,
                    "org_id": "etzhayyim",
                    "user_id": "system",
                    "actor_id": "sys.houbun",
                },
            )
            article_inserted += inserted
            edge_inserted += _insert_ignore(
                cur,
                "edge_houbun_statute_article",
                "edge_id",
                {
                    "edge_id": f"{statute_vid}::{article_vid}",
                    "src_vid": statute_vid,
                    "dst_vid": article_vid,
                    "created_date": today(),
                    "sensitivity_ord": 1,
                    "owner_did": article_did,
                    "article_no": article_no,
                    "order_key": idx,
                    "created_at": current,
                    "org_id": "etzhayyim",
                    "user_id": "system",
                    "actor_id": "sys.houbun",
                },
            )
    _flush_rw()
    return {
        "statutesInserted": statute_inserted,
        "articlesInserted": article_inserted,
        "edgesInserted": edge_inserted,
        "recordsWritten": statute_inserted + article_inserted + edge_inserted,
        "statuteVertexId": statute_vid,
    }


def _write_payload(payload: dict[str, Any]) -> dict[str, int]:
    law_id = str(payload["law_id"])
    current = now_iso()
    statute_vid = f"at://{JPN_PATH_DID}/com.etzhayyim.apps.houbun.statute/{law_id}"
    articles: list[dict[str, Any]] = list(payload.get("articles") or [])
    source_url = str(payload.get("source_url") or f"https://laws.e-gov.go.jp/law/{law_id}")
    article_inserted = 0
    edge_inserted = 0
    if True:
        client = get_kotoba_client()
        statute_inserted = _insert_ignore(
            cur,
            "vertex_houbun_statute",
            "vertex_id",
            {
                "vertex_id": statute_vid,
                "created_date": today(),
                "sensitivity_ord": 1,
                "owner_did": JPN_PATH_DID,
                "rkey": law_id,
                "repo": JPN_PATH_DID,
                "jurisdiction": "jpn",
                "statute_id": law_id,
                "title": payload.get("title") or law_id,
                "title_native": payload.get("title") or law_id,
                "statute_type": payload.get("statute_type") or "law",
                "enacted_date": payload.get("enacted_date"),
                "effective_date": payload.get("effective_date"),
                "repealed_date": payload.get("repealed_date"),
                "source": "e-gov",
                "source_url": source_url,
                "license": "CC-BY-4.0",
                "language": "ja",
                "article_count": len(articles),
                "last_verified": current,
                "created_at": current,
                "org_id": "etzhayyim",
                "user_id": "system",
                "actor_id": "sys.houbun",
            },
        )
        _res = client.q(
            """
            UPDATE vertex_houbun_statute
               SET title = ?,
                   title_native = ?,
                   article_count = ?,
                   last_verified = ?
             WHERE vertex_id = ?
            """,
            (payload.get("title") or law_id, payload.get("title") or law_id, len(articles), current, statute_vid),
        )
        for idx, article in enumerate(articles):
            article_no = str(article.get("article_no") or f"art-{idx + 1}")
            h = _hash("jpn", law_id, article_no, payload.get("effective_date") or "")
            article_did = f"{ACTOR_DID}:article:{h}"
            article_vid = f"at://{article_did}/com.etzhayyim.apps.houbun.article/{h}"
            inserted = _insert_ignore(
                cur,
                "vertex_houbun_article",
                "vertex_id",
                {
                    "vertex_id": article_vid,
                    "created_date": today(),
                    "sensitivity_ord": 1,
                    "owner_did": article_did,
                    "rkey": h,
                    "repo": article_did,
                    "statute_ref": statute_vid,
                    "article_no": article_no,
                    "section": article.get("section"),
                    "title": article.get("title"),
                    "text": article.get("text") or "",
                    "language": "ja",
                    "article_did": article_did,
                    "blake3_hash": h,
                    "amended_at": payload.get("effective_date"),
                    "source_url": source_url,
                    "created_at": current,
                    "org_id": "etzhayyim",
                    "user_id": "system",
                    "actor_id": "sys.houbun",
                },
            )
            article_inserted += inserted
            edge_inserted += _insert_ignore(
                cur,
                "edge_houbun_statute_article",
                "edge_id",
                {
                    "edge_id": f"{statute_vid}::{article_vid}",
                    "src_vid": statute_vid,
                    "dst_vid": article_vid,
                    "created_date": today(),
                    "sensitivity_ord": 1,
                    "owner_did": article_did,
                    "article_no": article_no,
                    "order_key": idx,
                    "created_at": current,
                    "org_id": "etzhayyim",
                    "user_id": "system",
                    "actor_id": "sys.houbun",
                },
            )
    _flush_rw()
    return {
        "statutesInserted": statute_inserted,
        "articlesInserted": article_inserted,
        "edgesInserted": edge_inserted,
        "recordsWritten": statute_inserted + article_inserted + edge_inserted,
        "statuteVertexId": statute_vid,
    }


def _verify_visibility(law_id: str, statute_vertex_id: str, article_count: int) -> dict[str, int | bool]:
    if not statute_vertex_id and law_id:
        statute_vertex_id = f"at://{JPN_PATH_DID}/com.etzhayyim.apps.houbun.statute/{law_id}"
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT count(*) FROM vertex_houbun_statute WHERE vertex_id = ?", (statute_vertex_id,))
        statute_count = int(((_res[0] if _res else None) or [0])[0] or 0)
        _res = client.q("SELECT count(*) FROM vertex_houbun_article WHERE statute_ref = ?", (statute_vertex_id,))
        visible_articles = int(((_res[0] if _res else None) or [0])[0] or 0)
    expected_articles = max(0, int(article_count or 0))
    verified = statute_count == 1 and visible_articles >= expected_articles
    return {
        "verified": verified,
        "statuteVisible": statute_count,
        "visibleArticles": visible_articles,
    }


async def task_houbun_create_run(
    runId: str = "",
    sourceId: str = SOURCE_ID,
    mode: str = "delta",
    requestedBy: str = "zeebe",
    inputJson: str = "",
    **_: Any,
) -> dict[str, Any]:
    run = IngestRun(
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or SOURCE_ID,
        mode=mode or "delta",
        run_id=runId,
        status="running",
        bpmn_process_id="ingest_houbun_egov_jpn_delta",
        requested_by=requestedBy,
        input_json=inputJson,
    ).with_run_id()
    vid = await asyncio.to_thread(upsert_run, run)
    return {"ok": True, "runId": run.run_id, "runVertexId": vid, "sourceId": run.source_id}


async def task_houbun_plan_egov_jpn(
    lawId: str = "",
    limit: int = 1,
    offset: int = 0,
    since: str = "",
    maxArticles: int = 80,
    **_: Any,
) -> dict[str, Any]:
    if lawId:
        law_ids = [lawId]
    else:
        params: dict[str, Any] = {}
        if since:
            params["updateDate"] = since
        data = await asyncio.to_thread(_get_json, EGOV_LAW_LIST, params)
        laws = data.get("laws") if isinstance(data, dict) else []
        law_ids = [
            str((x.get("law_info") or {}).get("law_id") or x.get("law_id") or x.get("lawId") or x.get("LawId"))
            for x in laws[offset : offset + max(1, min(int(limit or 1), 100))]
            if isinstance(x, dict)
            and ((x.get("law_info") or {}).get("law_id") or x.get("law_id") or x.get("lawId") or x.get("LawId"))
        ]
    shards = [{"shardKey": x, "lawId": x, "maxArticles": maxArticles} for x in law_ids]
    return {
        "ok": True,
        "sourceId": SOURCE_ID,
        "plannedShards": len(shards),
        "shards": shards,
        "firstShard": shards[0] if shards else {},
        "lawId": law_ids[0] if law_ids else "",
    }


async def task_houbun_acquire_cursor(
    runId: str,
    sourceId: str = SOURCE_ID,
    firstShard: dict[str, Any] | None = None,
    lawId: str = "",
    **_: Any,
) -> dict[str, Any]:
    shard_key = str((firstShard or {}).get("shardKey") or lawId)
    if not shard_key:
        return {"ok": False, "error": "missing shard key"}
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor_vid = await asyncio.to_thread(
        upsert_cursor,
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or SOURCE_ID,
        shard_key=shard_key,
        locked_by_run_id=runId,
        lock_expires_at=expires,
        status="locked",
    )
    return {"ok": True, "shardKey": shard_key, "cursorVertexId": cursor_vid, "cursorValue": shard_key}


async def task_houbun_fetch_egov_jpn(
    runId: str,
    lawId: str = "",
    shardKey: str = "",
    maxArticles: int = 80,
    **_: Any,
) -> dict[str, Any]:
    target = lawId or shardKey
    if not target:
        return {"ok": False, "error": "lawId required"}
    raw = await asyncio.to_thread(_get_json, f"{EGOV_LAW_DATA}/{target}")
    raw_json = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sha = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
    artifact_uri = f"inline://houbun/egov-jpn/{target}/{sha}"
    await asyncio.to_thread(
        upsert_artifact,
        IngestArtifact(
            run_id=runId,
            artifact_kind="raw",
            source_id=SOURCE_ID,
            uri=artifact_uri,
            sha256=sha,
            byte_size=len(raw_json.encode("utf-8")),
            record_count=1,
            props={"lawId": target},
        ),
    )
    payload = _extract_law_payload(raw, target, max_articles=maxArticles)
    return {
        "ok": True,
        "lawId": target,
        "artifactUri": artifact_uri,
        "rawSha256": sha,
        "normalizedPayload": payload,
        "recordsRead": 1,
        "articleCount": len(payload.get("articles") or []),
    }


async def task_houbun_write_graph(
    sourceId: str = SOURCE_ID,
    normalizedPayload: dict[str, Any] | None = None,
    rwHealthy: bool = True,
    healthy: bool | None = None,
    **_: Any,
) -> dict[str, Any]:
    _supported = (SOURCE_ID, USA_CFR_SOURCE_ID, CHN_NPC_SOURCE_ID)
    if sourceId not in _supported:
        return {"ok": False, "error": f"unsupported sourceId: {sourceId}"}
    if healthy is not None:
        rwHealthy = healthy
    if not rwHealthy:
        return {"ok": False, "error": "rwHealthy required"}
    if not normalizedPayload:
        return {"ok": False, "error": "normalizedPayload required"}
    if sourceId == USA_CFR_SOURCE_ID:
        stats = await asyncio.to_thread(_write_payload_usa, normalizedPayload)
    elif sourceId == CHN_NPC_SOURCE_ID:
        stats = await asyncio.to_thread(_write_payload_chn, normalizedPayload)
    else:
        stats = await asyncio.to_thread(_write_payload, normalizedPayload)
    return {"ok": True, **stats}


async def task_houbun_verify_visibility(
    lawId: str = "",
    statuteVertexId: str = "",
    articleCount: int = 0,
    recordsWritten: int = 0,
    sourceId: str = SOURCE_ID,
    **_: Any,
) -> dict[str, Any]:
    if not statuteVertexId and lawId:
        if sourceId == USA_CFR_SOURCE_ID:
            path_did = USA_CFR_PATH_DID
        elif sourceId == CHN_NPC_SOURCE_ID:
            path_did = CHN_NPC_PATH_DID
        else:
            path_did = JPN_PATH_DID
        statuteVertexId = f"at://{path_did}/com.etzhayyim.apps.houbun.statute/{lawId}"
    visibility = await asyncio.to_thread(_verify_visibility, lawId, statuteVertexId, articleCount)
    verified = bool(visibility["verified"])
    return {
        "ok": verified,
        "verified": verified,
        "statuteVisible": visibility["statuteVisible"],
        "visibleArticles": visibility["visibleArticles"],
        "recordsWritten": recordsWritten,
    }


async def task_houbun_advance_cursor(
    runId: str,
    sourceId: str = SOURCE_ID,
    shardKey: str = "",
    rawSha256: str = "",
    verified: bool = False,
    **_: Any,
) -> dict[str, Any]:
    if not verified:
        return {"ok": False, "error": "verified=true required before cursor advance"}
    cursor_vid = await asyncio.to_thread(
        upsert_cursor,
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or SOURCE_ID,
        shard_key=shardKey,
        cursor_value=rawSha256 or shardKey,
        content_hash=rawSha256 or None,
        locked_by_run_id=runId,
        lock_expires_at=now_iso(),
        status="completed",
    )
    return {"ok": True, "cursorVertexId": cursor_vid}


async def task_houbun_complete_run(
    runId: str,
    recordsRead: int = 0,
    recordsWritten: int = 0,
    recordsSkipped: int = 0,
    errorCount: int = 0,
    verified: bool = False,
    **_: Any,
) -> dict[str, Any]:
    status = "completed" if verified and not errorCount else "degraded"
    await asyncio.to_thread(
        mark_run_finished,
        runId,
        status=status,
        records_read=recordsRead,
        records_written=recordsWritten,
        records_skipped=recordsSkipped,
        error_count=errorCount,
        output={"verified": verified},
    )
    return {"ok": True, "status": status}


# ── USA GovInfo CFR tasks ──────────────────────────────────────────────────────

async def task_houbun_plan_govinfo_usa(
    titleNum: int = 1,
    year: int = 0,
    maxArticles: int = 200,
    **_: Any,
) -> dict[str, Any]:
    if year <= 0:
        year = today().year
    date_str = f"{year}-01-01"
    shard_key = f"cfr-title-{titleNum}-{year}"
    title_name = ""
    try:
        data = await asyncio.to_thread(
            _get_json, f"{ECFR_BASE}/versioner/v1/titles"
        )
        for t in (data.get("titles") if isinstance(data, dict) else []) or []:
            if isinstance(t, dict) and t.get("number") == titleNum:
                title_name = _clean(t.get("name") or "")
                break
    except Exception:
        pass
    if not title_name:
        title_name = f"Title {titleNum}"
    shards = [{
        "shardKey": shard_key,
        "titleNum": titleNum,
        "titleName": title_name,
        "year": year,
        "dateStr": date_str,
        "maxArticles": maxArticles,
    }]
    return {
        "ok": True,
        "sourceId": USA_CFR_SOURCE_ID,
        "plannedShards": len(shards),
        "shards": shards,
        "firstShard": shards[0],
        "lawId": shard_key,
        "titleNum": titleNum,
        "titleName": title_name,
        "dateStr": date_str,
    }


async def task_houbun_fetch_govinfo_usa(
    runId: str,
    shardKey: str = "",
    titleNum: int = 1,
    titleName: str = "",
    year: int = 0,
    dateStr: str = "",
    maxArticles: int = 200,
    **_: Any,
) -> dict[str, Any]:
    if year <= 0:
        year = today().year
    if not dateStr:
        dateStr = f"{year}-01-01"
    if not shardKey:
        shardKey = f"cfr-title-{titleNum}-{year}"
    xml_str = await asyncio.to_thread(_fetch_ecfr_title_xml, titleNum, dateStr)
    sha = hashlib.sha256(xml_str.encode("utf-8")).hexdigest()
    artifact_uri = f"inline://houbun/govinfo-cfr/{shardKey}/{sha}"
    await asyncio.to_thread(
        upsert_artifact,
        IngestArtifact(
            run_id=runId,
            artifact_kind="raw",
            source_id=USA_CFR_SOURCE_ID,
            uri=artifact_uri,
            sha256=sha,
            byte_size=len(xml_str.encode("utf-8")),
            record_count=1,
            props={"shardKey": shardKey, "titleNum": titleNum},
        ),
    )
    payload = _parse_ecfr_xml(xml_str, titleNum, titleName, year, max_articles=maxArticles)
    return {
        "ok": True,
        "lawId": shardKey,
        "shardKey": shardKey,
        "artifactUri": artifact_uri,
        "rawSha256": sha,
        "normalizedPayload": payload,
        "sourceId": USA_CFR_SOURCE_ID,
        "recordsRead": 1,
        "articleCount": len(payload.get("articles") or []),
    }


# ---------------------------------------------------------------------------
# CHN — NPC FDB (全国人民代表大会法律法规数据库)
# ---------------------------------------------------------------------------

def _npc_fdb_search(page: int = 1, size: int = 10, law_type: str = "") -> dict[str, Any]:
    """POST /flfg/search — returns paginated law list."""
    url = f"{NPC_FDB_BASE}/flfg/search"
    body: dict[str, Any] = {"page": page, "size": size}
    if law_type:
        body["type"] = law_type
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "etzhayyim-houbun-zeebe/0.1 (+https://houbun.etzhayyim.com)",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _npc_fdb_detail(law_id: str) -> dict[str, Any]:
    """GET /flfg/detail?id={id} — returns full law body."""
    url = f"{NPC_FDB_BASE}/flfg/detail?id={urllib.parse.quote(law_id)}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "etzhayyim-houbun-zeebe/0.1 (+https://houbun.etzhayyim.com)",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_npc_fdb_html(
    html_body: str, law_id: str, title: str, publish_date: str, *, max_articles: int
) -> dict[str, Any]:
    """Extract articles from NPC FDB HTML body.

    Article HTML structure:
      <div class="law-article">
        <div class="title">第X条 …</div>
        <div class="content">…</div>
      </div>
    """
    try:
        # Use html.parser via stdlib to avoid lxml dependency
        import html
        from html.parser import HTMLParser

        class ArticleParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self._articles: list[dict[str, Any]] = []
                self._in_article = False
                self._in_title = False
                self._in_content = False
                self._cur_article_no = ""
                self._cur_text_parts: list[str] = []
                self._depth = 0

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                cls = dict(attrs).get("class", "") or ""
                if tag == "div" and "law-article" in cls:
                    self._in_article = True
                    self._depth = 0
                    self._cur_article_no = ""
                    self._cur_text_parts = []
                elif self._in_article and tag == "div" and cls == "title":
                    self._in_title = True
                elif self._in_article and tag == "div" and cls == "content":
                    self._in_content = True

            def handle_endtag(self, tag: str) -> None:
                if tag == "div":
                    if self._in_title:
                        self._in_title = False
                    elif self._in_content:
                        self._in_content = False
                    elif self._in_article:
                        text = WS.sub(" ", " ".join(self._cur_text_parts)).strip()
                        if self._cur_article_no or text:
                            self._articles.append({
                                "article_no": self._cur_article_no or f"art-{len(self._articles)+1}",
                                "title": None,
                                "section": None,
                                "text": text,
                            })
                        self._in_article = False

            def handle_data(self, data: str) -> None:
                if self._in_title:
                    self._cur_article_no += data.strip()
                elif self._in_content:
                    self._cur_text_parts.append(data.strip())

        parser = ArticleParser()
        parser.feed(html_body)
        articles = parser._articles
    except Exception:
        articles = []

    if max_articles > 0:
        articles = articles[:max_articles]

    return {
        "law_id": f"npc-fdb-{_hash(law_id, size=8)}",
        "npc_law_id": law_id,
        "title": title,
        "statute_type": "law",
        "enacted_date": publish_date or None,
        "effective_date": publish_date or None,
        "repealed_date": None,
        "source_url": f"{NPC_FDB_BASE}/flfg/detail?id={urllib.parse.quote(law_id)}",
        "articles": articles,
    }


def _write_payload_chn(payload: dict[str, Any]) -> dict[str, int]:
    law_id = str(payload["law_id"])
    current = now_iso()
    statute_vid = f"at://{CHN_NPC_PATH_DID}/com.etzhayyim.apps.houbun.statute/{law_id}"
    articles: list[dict[str, Any]] = list(payload.get("articles") or [])
    source_url = str(payload.get("source_url") or f"{NPC_FDB_BASE}/flfg/detail?id={law_id}")
    article_inserted = 0
    edge_inserted = 0
    if True:
        client = get_kotoba_client()
        statute_inserted = _insert_ignore(
            cur,
            "vertex_houbun_statute",
            "vertex_id",
            {
                "vertex_id": statute_vid,
                "created_date": today(),
                "sensitivity_ord": 1,
                "owner_did": CHN_NPC_PATH_DID,
                "rkey": law_id,
                "repo": CHN_NPC_PATH_DID,
                "jurisdiction": "chn",
                "statute_id": law_id,
                "title": payload.get("title") or law_id,
                "title_native": payload.get("title") or law_id,
                "statute_type": payload.get("statute_type") or "law",
                "enacted_date": payload.get("enacted_date"),
                "effective_date": payload.get("effective_date"),
                "repealed_date": payload.get("repealed_date"),
                "source": "npc-fdb",
                "source_url": source_url,
                "license": "public-domain",
                "language": "zh",
                "article_count": len(articles),
                "last_verified": current,
                "created_at": current,
                "org_id": "etzhayyim",
                "user_id": "system",
                "actor_id": "sys.houbun",
            },
        )
        _res = client.q(
            """
            UPDATE vertex_houbun_statute
               SET title = ?,
                   title_native = ?,
                   article_count = ?,
                   last_verified = ?
             WHERE vertex_id = ?
            """,
            (payload.get("title") or law_id, payload.get("title") or law_id, len(articles), current, statute_vid),
        )
        for idx, article in enumerate(articles):
            article_no = str(article.get("article_no") or f"art-{idx + 1}")
            h = _hash("chn", law_id, article_no, payload.get("effective_date") or "")
            article_did = f"{ACTOR_DID}:article:{h}"
            article_vid = f"at://{article_did}/com.etzhayyim.apps.houbun.article/{h}"
            inserted = _insert_ignore(
                cur,
                "vertex_houbun_article",
                "vertex_id",
                {
                    "vertex_id": article_vid,
                    "created_date": today(),
                    "sensitivity_ord": 1,
                    "owner_did": article_did,
                    "rkey": h,
                    "repo": article_did,
                    "statute_ref": statute_vid,
                    "article_no": article_no,
                    "section": article.get("section"),
                    "title": article.get("title"),
                    "text": article.get("text") or "",
                    "language": "zh",
                    "article_did": article_did,
                    "blake3_hash": h,
                    "amended_at": payload.get("effective_date"),
                    "source_url": source_url,
                    "created_at": current,
                    "org_id": "etzhayyim",
                    "user_id": "system",
                    "actor_id": "sys.houbun",
                },
            )
            article_inserted += inserted
            edge_inserted += _insert_ignore(
                cur,
                "edge_houbun_statute_article",
                "edge_id",
                {
                    "edge_id": f"{statute_vid}::{article_vid}",
                    "src_vid": statute_vid,
                    "dst_vid": article_vid,
                    "created_date": today(),
                    "sensitivity_ord": 1,
                    "owner_did": article_did,
                    "article_no": article_no,
                    "order_key": idx,
                    "created_at": current,
                    "org_id": "etzhayyim",
                    "user_id": "system",
                    "actor_id": "sys.houbun",
                },
            )
    _flush_rw()
    return {
        "statutesInserted": statute_inserted,
        "articlesInserted": article_inserted,
        "edgesInserted": edge_inserted,
        "recordsWritten": statute_inserted + article_inserted + edge_inserted,
        "statuteVertexId": statute_vid,
    }


async def task_houbun_plan_npc_fdb_chn(
    page: int = 1,
    size: int = 10,
    maxArticles: int = 500,
    **_: Any,
) -> dict[str, Any]:
    """Fetch one page of NPC FDB law list, return the first law ID as shard."""
    result = await asyncio.to_thread(_npc_fdb_search, page, size)
    items = result.get("data", {}).get("items") or result.get("result") or []
    if not items:
        # Try alternate response shape
        items = result.get("items") or result.get("list") or []
    if not items:
        return {
            "ok": False,
            "error": "npc-fdb search returned empty items",
            "page": page,
            "rawResponse": str(result)[:500],
        }
    law = items[0]
    law_id = str(law.get("id") or law.get("lawId") or law.get("law_id") or "")
    if not law_id:
        return {"ok": False, "error": "no id field in npc-fdb item", "item": str(law)[:200]}
    title = str(law.get("title") or law.get("name") or "")
    publish_date = str(law.get("publish") or law.get("publishDate") or "")
    shard_key = f"npc-fdb-{_hash(law_id, size=8)}"
    return {
        "ok": True,
        "shardKey": shard_key,
        "npcLawId": law_id,
        "title": title,
        "publishDate": publish_date,
        "maxArticles": maxArticles,
        "sourceId": CHN_NPC_SOURCE_ID,
    }


async def task_houbun_fetch_npc_fdb_chn(
    runId: str = "",
    shardKey: str = "",
    npcLawId: str = "",
    title: str = "",
    publishDate: str = "",
    maxArticles: int = 500,
    **_: Any,
) -> dict[str, Any]:
    """Fetch full law detail from NPC FDB, parse HTML body, return normalizedPayload."""
    if not npcLawId:
        return {"ok": False, "error": "npcLawId is required"}
    detail = await asyncio.to_thread(_npc_fdb_detail, npcLawId)
    html_body = str(detail.get("body") or detail.get("content") or "")
    law_title = str(detail.get("title") or title or npcLawId)
    publish = str(detail.get("publish") or detail.get("publishDate") or publishDate or "")
    if not shardKey:
        shardKey = f"npc-fdb-{_hash(npcLawId, size=8)}"
    sha = hashlib.sha256(html_body.encode("utf-8")).hexdigest()[:16]
    artifact_uri = f"inline://houbun/npc-fdb-chn/{shardKey}/{sha}"
    upsert_artifact(
        IngestArtifact(
            run_id=runId,
            artifact_uri=artifact_uri,
            source_id=CHN_NPC_SOURCE_ID,
            shard_key=shardKey,
            raw_bytes=len(html_body.encode("utf-8")),
            sha256=sha,
            content_type="text/html",
        ),
    )
    payload = await asyncio.to_thread(
        _parse_npc_fdb_html, html_body, npcLawId, law_title, publish, max_articles=maxArticles
    )
    return {
        "ok": True,
        "lawId": shardKey,
        "shardKey": shardKey,
        "artifactUri": artifact_uri,
        "rawSha256": sha,
        "normalizedPayload": payload,
        "sourceId": CHN_NPC_SOURCE_ID,
        "recordsRead": 1,
        "articleCount": len(payload.get("articles") or []),
    }
