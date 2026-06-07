"""Handotai semiconductor-news XRPC primitives for BPMN/LangServer."""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import decimal as _decimal
import json
import time
import uuid
from typing import Any

from kotodama import llm


APP_DID = "did:web:handotai.etzhayyim.com"
APP_ID = "dtyy44cr"
WRITE_TABLES = {
    "alert": "vertex_handotai_alert",
    "article": "vertex_handotai_article",
    "collectionJob": "vertex_handotai_collection_job",
    "digest": "vertex_handotai_digest",
    "report": "vertex_handotai_report",
    "semiEntity": "vertex_handotai_semi_entity",
    "source": "vertex_handotai_source",
    "subscription": "vertex_handotai_subscription",
}

WRITERS = [
    {"sourceId": "src-pcw", "name": "PC Watch", "url": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf", "language": "ja", "category": "fabrication"},
    {"sourceId": "src-itm", "name": "ITmedia NEWS", "url": "https://rss.itmedia.co.jp/rss/2.0/newsBursts.xml", "language": "ja", "category": "market"},
    {"sourceId": "src-pubk", "name": "Publickey", "url": "https://www.publickey1.jp/atom.xml", "language": "ja", "category": "design"},
    {"sourceId": "src-semia", "name": "SemiAnalysis", "url": "https://www.semianalysis.com/feed", "language": "en", "category": "market"},
    {"sourceId": "src-semie", "name": "Semiconductor Engineering", "url": "https://semiengineering.com/feed/", "language": "en", "category": "design"},
    {"sourceId": "src-eet", "name": "EE Times", "url": "https://www.eetimes.com/feed/", "language": "en", "category": "market"},
]

ENTITIES = [
    ("tsmc", "TSMC", "company", "twn", "foundry"),
    ("samsungSemi", "Samsung Semiconductor", "company", "kor", "idm"),
    ("intel", "Intel", "company", "usa", "idm"),
    ("nvidia", "NVIDIA", "company", "usa", "fabless"),
    ("amd", "AMD", "company", "usa", "fabless"),
    ("asml", "ASML", "company", "nld", "equipment"),
    ("tokyoElectron", "Tokyo Electron", "company", "jpn", "equipment"),
    ("shinEtsu", "Shin-Etsu Chemical", "company", "jpn", "materials"),
    ("catGpu", "GPU", "productCategory", "", "category"),
    ("catAiAccelerator", "AI Accelerator", "productCategory", "", "category"),
    ("catMemoryDram", "DRAM", "productCategory", "", "category"),
    ("catPowerManagement", "Power Management IC", "productCategory", "", "category"),
]

SEED_ARTICLES = [
    {"to": "TSMC 2nm N2 Node: GAAFET Risk Production Late 2025", "te": "TSMC 2nm N2 Node: GAAFET Risk Production Late 2025", "src": "Semiconductor Engineering", "cat": "fabrication", "sub": "advancedNode", "url": "https://semiengineering.com/tsmc-2nm-process/", "lang": "en", "summ": "TSMC is on track to begin risk production of its N2 node in late 2025.", "ent": '["TSMC","Apple","Qualcomm"]', "tags": '["2nm","GAAFET","N2"]', "sent": "positive", "imp": 5, "pub": "2026-03-18T06:00:00Z"},
    {"to": "Samsung HBM4: 12-Layer 1.5TB/s for AI Datacenters", "te": "Samsung HBM4: 12-Layer 1.5TB/s for AI Datacenters", "src": "EE Times", "cat": "fabrication", "sub": "memory", "url": "https://www.eetimes.com/samsung-hbm4/", "lang": "en", "summ": "Samsung will begin mass production of HBM4 memory in Q3 2026.", "ent": '["Samsung","SK Hynix","NVIDIA"]', "tags": '["HBM4","AI","memory"]', "sent": "positive", "imp": 5, "pub": "2026-03-18T08:00:00Z"},
    {"to": "NVIDIA Rubin R100: Next-Gen AI GPU on TSMC N3 with HBM4", "te": "NVIDIA Rubin R100: Next-Gen AI GPU on TSMC N3 with HBM4", "src": "SemiAnalysis", "cat": "design", "sub": "gpu", "url": "https://semianalysis.com/nvidia-rubin-r100/", "lang": "en", "summ": "NVIDIA has unveiled Rubin R100, its next-generation AI training GPU built on TSMC N3P.", "ent": '["NVIDIA","TSMC","Samsung"]', "tags": '["Rubin","R100","GPU","AI","HBM4"]', "sent": "positive", "imp": 5, "pub": "2026-03-21T10:00:00Z"},
]


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gid(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000):x}_{uuid.uuid4().hex[:6]}"


def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _num(v: Any, fallback: float = 0.0) -> float:
    try:
        n = float(v)
        return n if n == n and n not in (float("inf"), float("-inf")) else fallback
    except (TypeError, ValueError):
        return fallback


def _jsonable(v: Any) -> Any:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    return v


def _rows(cur: Any) -> list[dict[str, Any]]:
    cols = [d[0] for d in ([] or [])]
    out: list[dict[str, Any]] = []
    for row in _res:
        raw = {cols[i]: _jsonable(row[i]) for i in range(len(cols))}
        value_json = raw.get("value_json")
        if isinstance(value_json, str) and value_json:
            try:
                data = json.loads(value_json)
                if isinstance(data, dict):
                    raw = {**data, **raw}
            except json.JSONDecodeError:
                pass
        out.append(raw)
    return out


def _collection(name: str) -> str:
    return f"com.etzhayyim.apps.handotai.{name}"


def _record_key(name: str, record: dict[str, Any]) -> str:
    return _str(record.get("articleId") or record.get("alertId") or record.get("subId") or record.get("sourceId") or record.get("entityId") or record.get("reportId") or record.get("jobId") or _gid(name))[:128]


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _source_id_for(record: dict[str, Any]) -> str:
    if _str(record.get("sourceId")):
        return _str(record.get("sourceId"))
    name = _str(record.get("sourceName"))
    if name:
        return _writer_for_name(name)["sourceId"]
    return ""


def _edge_id(kind: str, left: str, right: str) -> str:
    return f"edge:handotai:{kind}:{uuid.uuid5(uuid.NAMESPACE_URL, left + '|' + right).hex}"


def _write_social_post(record: dict[str, Any], *, did: str) -> dict[str, str]:
    now = _str(record.get("postedAt")) or _now()
    rkey = _str(record.get("postId") or _gid("post"))[:128]
    value = {
        "$type": "app.bsky.feed.post",
        "text": _str(record.get("postText"))[:300],
        "createdAt": now,
    }
    uri = f"at://{did}/app.bsky.feed.post/{rkey}"
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_repo_record
              (uri,cid,collection,rkey,repo,value_json,indexed_at,ts_ms,created_at,actor_did,org_did)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (uri) DO UPDATE SET
              value_json = EXCLUDED.value_json,
              indexed_at = EXCLUDED.indexed_at,
              ts_ms = EXCLUDED.ts_ms
            """,
            (uri, "", "app.bsky.feed.post", rkey, did, json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str), now, int(time.time() * 1000), now, did, _str(record.get("orgId")) or "anon"),
        )
    return {"uri": uri, "rkey": rkey}


def _write(name: str, record: dict[str, Any], *, did: str = APP_DID) -> dict[str, str]:
    if name == "socialPost":
        return _write_social_post(record, did=did)
    table = WRITE_TABLES.get(name)
    if not table:
        raise ValueError(f"unsupported handotai record kind: {name!r}")
    now = _now()
    rkey = _record_key(name, record)
    collection = _collection(name)
    vertex_id = f"at://{did}/{collection}/{rkey}"
    value_json = json.dumps({"$type": collection, **record}, ensure_ascii=False, separators=(",", ":"), default=str)
    if True:
        client = get_kotoba_client()
        common_values = (
            vertex_id,
            rkey,
            _str(record.get("name") or record.get("titleJa") or record.get("titleOriginal") or record.get("reportType") or record.get("companyName")),
            _str(record.get("status")) or ("active" if name in {"source", "subscription", "semiEntity"} else ""),
            value_json,
            now,
            _str(record.get("createdAt") or record.get("created_at")) or now,
            _str(record.get("updatedAt")) or now,
            _str(record.get("orgId")) or "anon",
            _str(record.get("userId")) or "anon",
            _str(record.get("actorId")) or APP_ID,
            did,
            _str(record.get("orgId")) or "anon",
            APP_DID,
            2,
        )
        if name == "source":
            _res = client.q(
                """
                INSERT INTO vertex_handotai_source
                  (vertex_id,record_key,label,status,value_json,indexed_at,created_at,updated_at,org_id,user_id,actor_id,actor_did,org_did,owner_did,sensitivity_ord,
                   source_id,name,url,language,category,source_type,crawl_interval_min,enabled,writer_did,last_fetched_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vertex_id) DO UPDATE SET
                  label = EXCLUDED.label, status = EXCLUDED.status, value_json = EXCLUDED.value_json,
                  indexed_at = EXCLUDED.indexed_at, updated_at = EXCLUDED.updated_at,
                  name = EXCLUDED.name, url = EXCLUDED.url, category = EXCLUDED.category,
                  enabled = EXCLUDED.enabled, writer_did = EXCLUDED.writer_did
                """,
                (*common_values, _str(record.get("sourceId")) or rkey, _str(record.get("name")) or rkey, _str(record.get("url")), _str(record.get("language")) or "ja", _str(record.get("category")) or "general", _str(record.get("sourceType")) or "rss", int(_num(record.get("crawlIntervalMin"), 15)), bool(_num(record.get("enabled"), 1)), _str(record.get("writerDid")) or did, _str(record.get("lastFetchedAt")) or None),
            )
        elif name == "article":
            source_id = _source_id_for(record)
            _res = client.q(
                """
                INSERT INTO vertex_handotai_article
                  (vertex_id,record_key,label,status,value_json,indexed_at,created_at,updated_at,org_id,user_id,actor_id,actor_did,org_did,owner_did,sensitivity_ord,
                   article_id,source_id,source_name,source_lang,source_url,title,summary,category,subcategory,published_at,crawled_at,
                   title_original,title_ja,title_en,summary_original,summary_ja,summary_en,entities_json,tags_json,sentiment,importance,visibility,writer_did)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vertex_id) DO UPDATE SET
                  label = EXCLUDED.label, status = EXCLUDED.status, value_json = EXCLUDED.value_json,
                  indexed_at = EXCLUDED.indexed_at, updated_at = EXCLUDED.updated_at,
                  title = EXCLUDED.title, summary = EXCLUDED.summary,
                  title_ja = EXCLUDED.title_ja, title_en = EXCLUDED.title_en,
                  summary_ja = EXCLUDED.summary_ja, summary_en = EXCLUDED.summary_en,
                  entities_json = EXCLUDED.entities_json, tags_json = EXCLUDED.tags_json
                """,
                (
                    *common_values,
                    _str(record.get("articleId")) or rkey,
                    source_id,
                    _str(record.get("sourceName")) or source_id or "unknown",
                    _str(record.get("sourceLang") or record.get("language")) or "ja",
                    _str(record.get("sourceUrl") or record.get("url")),
                    _str(record.get("titleJa") or record.get("titleOriginal") or record.get("titleEn")),
                    _str(record.get("summaryJa") or record.get("summaryOriginal") or record.get("summaryEn")),
                    _str(record.get("category")) or "general",
                    _str(record.get("subcategory")),
                    _str(record.get("publishedAt")) or None,
                    _str(record.get("crawledAt")) or now,
                    _str(record.get("titleOriginal")),
                    _str(record.get("titleJa")),
                    _str(record.get("titleEn")),
                    _str(record.get("summaryOriginal")),
                    _str(record.get("summaryJa")),
                    _str(record.get("summaryEn")),
                    json.dumps(_json_list(record.get("entities")), ensure_ascii=False, separators=(",", ":")),
                    json.dumps(_json_list(record.get("tags")), ensure_ascii=False, separators=(",", ":")),
                    _str(record.get("sentiment")),
                    int(_num(record.get("importance"), 0)),
                    _str(record.get("visibility")) or "free",
                    _str(record.get("writerDid")) or did,
                ),
            )
            if source_id:
                _res = client.q(
                    """
                    INSERT INTO edge_handotai_source_article (edge_id,from_vertex_id,to_vertex_id,source_id,article_id,relation,created_at)
                    VALUES (%s,%s,%s,%s,%s,'published',%s)
                    ON CONFLICT (edge_id) DO UPDATE SET created_at = EXCLUDED.created_at
                    """,
                    (_edge_id("source_article", source_id, vertex_id), f"handotai:source:{source_id}", vertex_id, source_id, _str(record.get("articleId")) or rkey, now),
                )
            for entity in _json_list(record.get("entities")):
                entity_key = str(entity).strip()
                if entity_key:
                    _res = client.q(
                        """
                        INSERT INTO edge_handotai_article_entity (edge_id,from_vertex_id,to_vertex_id,article_id,entity_key,relation,created_at)
                        VALUES (%s,%s,%s,%s,%s,'mentions',%s)
                        ON CONFLICT (edge_id) DO UPDATE SET created_at = EXCLUDED.created_at
                        """,
                        (_edge_id("article_entity", vertex_id, entity_key), vertex_id, f"handotai:entity:{entity_key}", _str(record.get("articleId")) or rkey, entity_key, now),
                    )
        elif name == "digest":
            _res = client.q(
                """
                INSERT INTO vertex_handotai_digest
                  (vertex_id,record_key,label,status,value_json,indexed_at,created_at,updated_at,org_id,user_id,actor_id,actor_did,org_did,owner_did,sensitivity_ord,
                   digest_date,article_count,summary,key_topics,summary_ja,generated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vertex_id) DO UPDATE SET
                  value_json = EXCLUDED.value_json, indexed_at = EXCLUDED.indexed_at,
                  updated_at = EXCLUDED.updated_at, summary = EXCLUDED.summary,
                  summary_ja = EXCLUDED.summary_ja, article_count = EXCLUDED.article_count
                """,
                (*common_values, _str(record.get("date") or record.get("digestDate")) or now[:10], int(_num(record.get("totalArticles") or record.get("articleCount"), 0)), _str(record.get("summary") or record.get("summaryJa")), _str(record.get("keyTopics")), _str(record.get("summaryJa")), _str(record.get("generatedAt")) or now),
            )
        elif name == "collectionJob":
            _res = client.q(
                """
                INSERT INTO vertex_handotai_collection_job
                  (vertex_id,record_key,label,status,value_json,indexed_at,created_at,updated_at,org_id,user_id,actor_id,actor_did,org_did,owner_did,sensitivity_ord,
                   job_id,requested_at,started_at,finished_at,sources_count,articles_count)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vertex_id) DO UPDATE SET
                  status = EXCLUDED.status, value_json = EXCLUDED.value_json,
                  indexed_at = EXCLUDED.indexed_at, updated_at = EXCLUDED.updated_at,
                  finished_at = EXCLUDED.finished_at, articles_count = EXCLUDED.articles_count
                """,
                (*common_values, _str(record.get("jobId")) or rkey, _str(record.get("requestedAt")) or now, _str(record.get("startedAt")) or None, _str(record.get("finishedAt")) or None, int(_num(record.get("sources"), 0)), int(_num(record.get("articles"), 0))),
            )
        elif name == "report":
            _res = client.q(
                """
                INSERT INTO vertex_handotai_report
                  (vertex_id,record_key,label,status,value_json,indexed_at,created_at,updated_at,org_id,user_id,actor_id,actor_did,org_did,owner_did,sensitivity_ord,
                   report_id,report_type,entity_key,period,total_articles,report_ja,generated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vertex_id) DO UPDATE SET
                  value_json = EXCLUDED.value_json, indexed_at = EXCLUDED.indexed_at,
                  updated_at = EXCLUDED.updated_at, report_ja = EXCLUDED.report_ja,
                  total_articles = EXCLUDED.total_articles
                """,
                (*common_values, _str(record.get("reportId")) or rkey, _str(record.get("reportType")) or "weekly", _str(record.get("entity")), _str(record.get("period")), int(_num(record.get("totalArticles"), 0)), _str(record.get("reportJa")), _str(record.get("generatedAt")) or now),
            )
        elif name == "alert":
            _res = client.q(
                """
                INSERT INTO vertex_handotai_alert
                  (vertex_id,record_key,label,status,value_json,indexed_at,created_at,updated_at,org_id,user_id,actor_id,actor_did,org_did,owner_did,sensitivity_ord,
                   alert_id,name,filter_categories_json,filter_entities_json,filter_keywords_json,filter_importance_min,notify_channel,notify_email,tier,enabled)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vertex_id) DO UPDATE SET
                  label = EXCLUDED.label, status = EXCLUDED.status, value_json = EXCLUDED.value_json,
                  indexed_at = EXCLUDED.indexed_at, updated_at = EXCLUDED.updated_at,
                  enabled = EXCLUDED.enabled
                """,
                (*common_values, _str(record.get("alertId")) or rkey, _str(record.get("name")) or rkey, json.dumps(_json_list(record.get("filterCategories")), ensure_ascii=False, separators=(",", ":")), json.dumps(_json_list(record.get("filterEntities")), ensure_ascii=False, separators=(",", ":")), json.dumps(_json_list(record.get("filterKeywords")), ensure_ascii=False, separators=(",", ":")), int(_num(record.get("filterImportanceMin"), 0)), _str(record.get("notifyChannel")), _str(record.get("notifyEmail")), _str(record.get("tier")) or "free", bool(_num(record.get("enabled"), 1))),
            )
        elif name == "subscription":
            _res = client.q(
                """
                INSERT INTO vertex_handotai_subscription
                  (vertex_id,record_key,label,status,value_json,indexed_at,created_at,updated_at,org_id,user_id,actor_id,actor_did,org_did,owner_did,sensitivity_ord,
                   sub_id,tier,company_name,tracked_entities_json,started_at,expires_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vertex_id) DO UPDATE SET
                  status = EXCLUDED.status, value_json = EXCLUDED.value_json,
                  indexed_at = EXCLUDED.indexed_at, updated_at = EXCLUDED.updated_at,
                  tier = EXCLUDED.tier, expires_at = EXCLUDED.expires_at
                """,
                (*common_values, _str(record.get("subId")) or rkey, _str(record.get("tier")) or "free", _str(record.get("companyName")), json.dumps(_json_list(record.get("trackedEntities")), ensure_ascii=False, separators=(",", ":")), _str(record.get("startedAt")) or now, _str(record.get("expiresAt")) or None),
            )
            for entity in _json_list(record.get("trackedEntities")):
                entity_key = str(entity).strip()
                if entity_key:
                    _res = client.q(
                        """
                        INSERT INTO edge_handotai_subscription_entity (edge_id,from_vertex_id,to_vertex_id,sub_id,entity_key,relation,created_at)
                        VALUES (%s,%s,%s,%s,%s,'tracks',%s)
                        ON CONFLICT (edge_id) DO UPDATE SET created_at = EXCLUDED.created_at
                        """,
                        (_edge_id("subscription_entity", vertex_id, entity_key), vertex_id, f"handotai:entity:{entity_key}", _str(record.get("subId")) or rkey, entity_key, now),
                    )
        elif name == "semiEntity":
            _res = client.q(
                """
                INSERT INTO vertex_handotai_semi_entity
                  (vertex_id,record_key,label,status,value_json,indexed_at,created_at,updated_at,org_id,user_id,actor_id,actor_did,org_did,owner_did,sensitivity_ord,
                   entity_id,name,entity_type,country,segment,did)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vertex_id) DO UPDATE SET
                  label = EXCLUDED.label, value_json = EXCLUDED.value_json,
                  indexed_at = EXCLUDED.indexed_at, updated_at = EXCLUDED.updated_at,
                  name = EXCLUDED.name, segment = EXCLUDED.segment
                """,
                (*common_values, _str(record.get("entityId")) or rkey, _str(record.get("name")) or rkey, _str(record.get("entityType")) or "company", _str(record.get("country")), _str(record.get("segment")), _str(record.get("did")) or did),
            )
    return {"uri": vertex_id, "rkey": rkey}


def _list(name: str, match: dict[str, Any] | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    table = WRITE_TABLES.get(name)
    if not table:
        return []
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"SELECT * FROM {table} ORDER BY indexed_at DESC LIMIT %s OFFSET %s",
            (max(1, min(limit, 500)), max(0, offset)),
        )
        rows = _rows(cur)
    match = {k: v for k, v in (match or {}).items() if v not in ("", None)}
    if match:
        rows = [r for r in rows if all(str(r.get(k) or "") == str(v) for k, v in match.items())]
    return rows


def _writer_did(source_id: str) -> str:
    return f"{APP_DID}:writer:{source_id}"


def _writer_for_name(name: str) -> dict[str, Any]:
    for w in WRITERS:
        if w["name"] == name or w["sourceId"] == name:
            return w
    return WRITERS[0]


def _post(article_id: str, title: str, summary: str, source_url: str, writer_did: str) -> str:
    text = "\n".join([f"News: {title or 'Untitled'}", summary[:180], source_url, f"#{article_id}"]).strip()[:280]
    _write("socialPost", {"articleId": article_id, "writerDid": writer_did, "postText": text, "postedAt": _now(), "orgId": "anon", "userId": "anon", "actorId": writer_did}, did=writer_did)
    return text


def task_handotai_crawl_trigger(**_: Any) -> dict[str, Any]:
    job_id = _gid("job")
    _write("collectionJob", {"jobId": job_id, "status": "queued", "requestedAt": _now(), "orgId": "anon", "userId": "anon", "actorId": APP_ID})
    return {"status": "queued", "jobId": job_id, "sources": len(WRITERS)}


def task_handotai_translate_article(articleId: str = "", text: str = "", srcLang: str = "en", dstLang: str = "ja", **_: Any) -> dict[str, Any]:
    if not articleId and not text:
        return {"error": "articleId or text required"}
    if not text and articleId:
        rows = _list("article", {"articleId": articleId}, limit=1)
        text = _str(rows[0].get("titleOriginal") or rows[0].get("summaryOriginal")) if rows else ""
    if not text:
        return {"error": "source text not found", "articleId": articleId}
    try:
        resp = llm.call_tier("fast", system=f"Translate semiconductor industry text from {srcLang} to {dstLang}. Output only translation.", user=text[:3000], max_tokens=500, temperature=0)
        translated = _str(resp.get("content")) or text
    except Exception:
        translated = text
    if articleId:
        field = "summaryJa" if dstLang == "ja" else "summaryEn"
        _write("article", {"articleId": articleId, field: translated, "updatedAt": _now(), "orgId": "anon", "userId": "anon", "actorId": APP_ID})
    return {"status": "translated", "articleId": articleId, "translated": translated}


def task_handotai_list_articles(category: str = "", sourceName: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    rows = _list("article", {"category": category, "sourceName": sourceName}, int(_num(limit, 50)), int(_num(offset, 0)))
    return {"articles": rows, "total": len(rows), "offset": int(_num(offset, 0)), "limit": int(_num(limit, 50))}


def task_handotai_get_article(articleId: str = "", **_: Any) -> dict[str, Any]:
    rows = _list("article", {"articleId": articleId}, limit=1)
    return {"article": rows[0]} if rows else {"error": "not found", "articleId": articleId}


def task_handotai_search_articles(q: str = "", query: str = "", limit: Any = 50, **_: Any) -> dict[str, Any]:
    term = (q or query).lower()
    rows = _list("article", limit=500)
    if term:
        rows = [r for r in rows if term in str(r.get("titleOriginal", "")).lower() or term in str(r.get("summaryOriginal", "")).lower() or term in str(r.get("entities", "")).lower()]
    lim = int(_num(limit, 50))
    return {"articles": rows[:lim], "total": len(rows)}


def task_handotai_get_daily_digest(date: str = "", **_: Any) -> dict[str, Any]:
    day = date or _now()[:10]
    rows = _list("digest", {"date": day}, limit=1)
    if rows:
        return rows[0]
    articles = [r for r in _list("article", limit=500) if str(r.get("publishedAt", "")).startswith(day)]
    return {"date": day, "totalArticles": len(articles), "summaryJa": "", "generatedAt": _now()}


def task_handotai_get_weekly_report(**_: Any) -> dict[str, Any]:
    rows = _list("report", limit=1)
    return rows[0] if rows else {"reportType": "weekly", "totalArticles": 0, "reportJa": "", "generatedAt": _now()}


def task_handotai_report_generate(reportType: str = "weekly", entity: str = "", period: str = "", **_: Any) -> dict[str, Any]:
    rows = _list("article", limit=500)
    if entity:
        rows = [r for r in rows if entity.lower() in str(r.get("entities", "")).lower()]
    titles = "\n".join(f"- {r.get('titleOriginal') or r.get('titleEn')}" for r in rows[:100])
    try:
        resp = llm.call_tier("fast", system="You are a semiconductor industry analyst. Write Japanese report.", user=f"Generate a {reportType} report for {entity or 'semiconductors'}.\n{titles}", max_tokens=800, temperature=0.2)
        report = _str(resp.get("content"))
    except Exception:
        report = ""
    report_id = _gid("rpt")
    _write("report", {"reportId": report_id, "reportType": reportType, "entity": entity, "period": period, "totalArticles": len(rows), "reportJa": report, "generatedAt": _now(), "orgId": "anon", "userId": "anon", "actorId": APP_ID})
    return {"reportId": report_id, "totalArticles": len(rows)}


def task_handotai_alert_create(name: str = "", filterCategories: Any = None, filterEntities: Any = None, filterKeywords: Any = None, filterImportanceMin: Any = 0, notifyChannel: str = "", notifyEmail: str = "", **_: Any) -> dict[str, Any]:
    if not name:
        return {"error": "name is required"}
    alert_id = _gid("alr")
    _write("alert", {"alertId": alert_id, "name": name, "filterCategories": json.dumps(filterCategories if isinstance(filterCategories, list) else []), "filterEntities": json.dumps(filterEntities if isinstance(filterEntities, list) else []), "filterKeywords": json.dumps(filterKeywords if isinstance(filterKeywords, list) else []), "filterImportanceMin": _num(filterImportanceMin), "notifyChannel": notifyChannel, "notifyEmail": notifyEmail, "tier": "pro", "enabled": 1, "orgId": "anon", "userId": "anon", "actorId": APP_ID})
    return {"status": "created", "alertId": alert_id}


def task_handotai_alert_delete(alertId: str = "", **_: Any) -> dict[str, Any]:
    _write("alert", {"alertId": alertId, "enabled": 0, "orgId": "anon", "userId": "anon", "actorId": APP_ID})
    return {"status": "deleted", "alertId": alertId}


def task_handotai_alert_list(**_: Any) -> dict[str, Any]:
    rows = _list("alert", limit=100)
    return {"alerts": rows, "total": len(rows)}


def task_handotai_subscribe(tier: str = "free", companyName: str = "", trackedEntities: Any = None, **_: Any) -> dict[str, Any]:
    sub_id = _gid("sub")
    expires = (_dt.datetime.now(tz=_dt.UTC) + _dt.timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write("subscription", {"subId": sub_id, "tier": tier, "status": "active", "startedAt": _now(), "expiresAt": expires, "companyName": companyName, "trackedEntities": json.dumps(trackedEntities if isinstance(trackedEntities, list) else []), "orgId": "anon", "userId": "anon", "actorId": APP_ID})
    return {"status": "subscribed", "subId": sub_id, "tier": tier}


def task_handotai_get_subscription(**_: Any) -> dict[str, Any]:
    rows = _list("subscription", limit=1)
    return rows[0] if rows else {"tier": "free", "status": "noSubscription"}


def task_handotai_source_list(**_: Any) -> dict[str, Any]:
    sources = [{**w, "sourceType": "rss", "writerDid": _writer_did(w["sourceId"]), "enabled": True} for w in WRITERS]
    return {"sources": sources, "total": len(sources)}


def task_handotai_source_add(url: str = "", name: str = "", sourceType: str = "rss", language: str = "ja", category: str = "", **_: Any) -> dict[str, Any]:
    if not url:
        return {"error": "url is required"}
    source_id = _gid("src")
    writer_did = _writer_did(source_id)
    _write("source", {"sourceId": source_id, "name": name, "url": url, "sourceType": sourceType or "rss", "language": language or "ja", "category": category, "crawlIntervalMin": 15, "enabled": 1, "writerDid": writer_did, "orgId": "anon", "userId": "anon", "actorId": writer_did}, did=writer_did)
    return {"status": "added", "sourceId": source_id, "writerDid": writer_did}


def task_handotai_register_writer_profiles(**_: Any) -> dict[str, Any]:
    results = []
    for w in WRITERS:
        did = _writer_did(w["sourceId"])
        _write("source", {**w, "sourceType": "rss", "crawlIntervalMin": 15, "enabled": 1, "writerDid": did, "orgId": "anon", "userId": "anon", "actorId": did}, did=did)
        results.append({"sourceId": w["sourceId"], "name": w["name"], "did": did, "status": "registered"})
    return {"writers": results, "total": len(results)}


def task_handotai_list_semi_entities(entityType: str = "", segment: str = "", country: str = "", **_: Any) -> dict[str, Any]:
    rows = [{"entityId": a, "name": b, "did": f"{APP_DID}:{'company' if c == 'company' else 'category'}:{a}", "entityType": c, "country": d, "segment": e} for a, b, c, d, e in ENTITIES]
    if entityType:
        rows = [r for r in rows if r["entityType"] == entityType]
    if segment:
        rows = [r for r in rows if r["segment"] == segment]
    if country:
        rows = [r for r in rows if r["country"] == country]
    return {"entities": rows, "total": len(rows)}


def task_handotai_register_semi_entities(**_: Any) -> dict[str, Any]:
    for a, b, c, d, e in ENTITIES:
        did = f"{APP_DID}:{'company' if c == 'company' else 'category'}:{a}"
        _write("semiEntity", {"entityId": a, "name": b, "entityType": c, "country": d, "segment": e, "did": did, "orgId": "anon", "userId": "anon", "actorId": did}, did=did)
    return {"status": "registered", "total": len(ENTITIES), "companies": len([e for e in ENTITIES if e[2] == "company"]), "categories": len([e for e in ENTITIES if e[2] == "productCategory"])}


def task_handotai_seed_articles(i: Any = 0, **_: Any) -> dict[str, Any]:
    idx = int(_num(i, 0))
    if idx < 0 or idx >= len(SEED_ARTICLES):
        return {"status": "error", "msg": "index out of range", "max": len(SEED_ARTICLES) - 1}
    s = SEED_ARTICLES[idx]
    article_id = f"seed-{idx}"
    writer = _writer_for_name(s["src"])
    writer_did = _writer_did(writer["sourceId"])
    record = {"articleId": article_id, "titleOriginal": s["to"], "titleEn": s["te"], "titleJa": s["to"], "sourceName": s["src"], "sourceUrl": s["url"], "sourceLang": s["lang"], "summaryEn": s["summ"], "summaryJa": s["summ"], "summaryOriginal": s["summ"], "category": s["cat"], "subcategory": s["sub"], "entities": s["ent"], "tags": s["tags"], "sentiment": s["sent"], "importance": s["imp"], "publishedAt": s["pub"], "crawledAt": s["pub"], "visibility": "free", "writerDid": writer_did, "orgId": "anon", "userId": "anon", "actorId": writer_did}
    _write("article", record, did=writer_did)
    post_text = _post(article_id, s["to"] or s["te"], s["summ"], s["url"], writer_did)
    return {"status": "ok", "i": idx, "aid": article_id, "writerDid": writer_did, "posted": True, "postText": post_text}


def task_handotai_backfill_writer_posts(writerDid: str = "", sourceName: str = "", limit: Any = 20, **_: Any) -> dict[str, Any]:
    writer_did = writerDid or (_writer_did(_writer_for_name(sourceName)["sourceId"]) if sourceName else "")
    if not writer_did:
        return {"error": "writerDid or sourceName is required"}
    rows = _list("article", {"writerDid": writer_did}, int(_num(limit, 20)))
    posted = 0
    for row in rows:
        _post(_str(row.get("articleId")), _str(row.get("titleJa") or row.get("titleOriginal")), _str(row.get("summaryJa") or row.get("summaryOriginal")), _str(row.get("sourceUrl")), writer_did)
        posted += 1
    return {"status": "ok" if rows else "noArticles", "writerDid": writer_did, "limit": int(_num(limit, 20)), "posted": posted, "skipped": 0}


def task_handotai_update_translation(articleId: str = "", titleJa: str = "", titleEn: str = "", summaryJa: str = "", summaryEn: str = "", **_: Any) -> dict[str, Any]:
    if not articleId:
        return {"error": "articleId required"}
    updates = {k: v for k, v in {"titleJa": titleJa, "titleEn": titleEn, "summaryJa": summaryJa, "summaryEn": summaryEn}.items() if v}
    if not updates:
        return {"status": "noChanges"}
    _write("article", {"articleId": articleId, **updates, "updatedAt": _now(), "orgId": "anon", "userId": "anon", "actorId": APP_ID})
    return {"status": "updated", "articleId": articleId}


def task_handotai_handle_daily_evolution(**kwargs: Any) -> dict[str, Any]:
    crawl = task_handotai_crawl_trigger(**kwargs)
    digest = task_handotai_get_daily_digest()
    return {"status": "ok", "crawl": crawl, "digest": digest}


def task_handotai_wave(from_: str = "", fromName: str = "", message: str = "Hello!", **kwargs: Any) -> dict[str, Any]:
    sender = from_ or fromName or _str(kwargs.get("from")) or "someone"
    greeting = f"{sender} waved! {message or 'Hello!'}"
    _write("socialPost", {"postText": greeting, "postedAt": _now(), "orgId": "anon", "userId": "anon", "actorId": APP_ID})
    return {"status": "waved", "greeting": greeting}


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.handotai.alertCreate": task_handotai_alert_create,
        "xrpc.com.etzhayyim.apps.handotai.alertDelete": task_handotai_alert_delete,
        "xrpc.com.etzhayyim.apps.handotai.alertList": task_handotai_alert_list,
        "xrpc.com.etzhayyim.apps.handotai.backfillWriterPosts": task_handotai_backfill_writer_posts,
        "xrpc.com.etzhayyim.apps.handotai.crawlTrigger": task_handotai_crawl_trigger,
        "xrpc.com.etzhayyim.apps.handotai.getArticle": task_handotai_get_article,
        "xrpc.com.etzhayyim.apps.handotai.getDailyDigest": task_handotai_get_daily_digest,
        "xrpc.com.etzhayyim.apps.handotai.getSubscription": task_handotai_get_subscription,
        "xrpc.com.etzhayyim.apps.handotai.getWeeklyReport": task_handotai_get_weekly_report,
        "xrpc.com.etzhayyim.apps.handotai.handleDailyEvolution": task_handotai_handle_daily_evolution,
        "xrpc.com.etzhayyim.apps.handotai.listArticles": task_handotai_list_articles,
        "xrpc.com.etzhayyim.apps.handotai.listSemiEntities": task_handotai_list_semi_entities,
        "xrpc.com.etzhayyim.apps.handotai.registerSemiEntities": task_handotai_register_semi_entities,
        "xrpc.com.etzhayyim.apps.handotai.registerWriterProfiles": task_handotai_register_writer_profiles,
        "xrpc.com.etzhayyim.apps.handotai.reportGenerate": task_handotai_report_generate,
        "xrpc.com.etzhayyim.apps.handotai.searchArticles": task_handotai_search_articles,
        "xrpc.com.etzhayyim.apps.handotai.seedArticles": task_handotai_seed_articles,
        "xrpc.com.etzhayyim.apps.handotai.sourceAdd": task_handotai_source_add,
        "xrpc.com.etzhayyim.apps.handotai.sourceList": task_handotai_source_list,
        "xrpc.com.etzhayyim.apps.handotai.subscribe": task_handotai_subscribe,
        "xrpc.com.etzhayyim.apps.handotai.translateArticle": task_handotai_translate_article,
        "xrpc.com.etzhayyim.apps.handotai.updateTranslation": task_handotai_update_translation,
        "xrpc.com.etzhayyim.apps.handotai.wave": task_handotai_wave,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
