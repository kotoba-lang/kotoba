"""curpus2skill handlers for BPMN + Zeebe.

Conservative corpus -> canonical ESCO skill evidence extraction. The task
writes edge_corpus_skill_evidence rows only; it does not create vertex_skill.
Persistence is handled by the kotoba Datom log.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


VERSION = "curpus2skill-langserver-v0.1.0"

SOURCES: dict[str, dict[str, str]] = {
    "legal-corpus": {
        "table": "vertex_legal_corpus_document",
        "actor_did": "did:web:legal-corpus.etzhayyim.com",
        "sql": """
            SELECT vertex_id, 'vertex_legal_corpus_document' AS corpus_table,
                   title, COALESCE(body_text, '') AS body,
                   COALESCE(topic_tags_csv, '') AS tags,
                   COALESCE(owner_did, 'did:web:legal-corpus.etzhayyim.com') AS owner_did,
                   COALESCE(source_id, 'unknown') AS source_license
            FROM vertex_legal_corpus_document
            WHERE body_text IS NOT NULL
              AND body_text NOT LIKE 'signal:v1:%%'
            LIMIT {limit}
        """,
    },
    "houbun-article": {
        "table": "vertex_houbun_article",
        "actor_did": "did:web:houbun.etzhayyim.com",
        "sql": """
            SELECT vertex_id, 'vertex_houbun_article' AS corpus_table,
                   title, COALESCE(text, '') AS body,
                   COALESCE(article_no, '') AS tags,
                   COALESCE(owner_did, 'did:web:houbun.etzhayyim.com') AS owner_did,
                   COALESCE(source_url, 'unknown') AS source_license
            FROM vertex_houbun_article
            WHERE text IS NOT NULL
              AND text NOT LIKE 'signal:v1:%%'
            LIMIT {limit}
        """,
    },
    "domain-knowledge": {
        "table": "vertex_domain_knowledge_chunk",
        "actor_did": "did:web:llm.etzhayyim.com",
        "sql": """
            SELECT c.vertex_id, 'vertex_domain_knowledge_chunk' AS corpus_table,
                   d.title, COALESCE(c.chunk_text, '') AS body,
                   COALESCE(c.keywords, '') AS tags,
                   COALESCE(d.owner_did, 'did:web:llm.etzhayyim.com') AS owner_did,
                   COALESCE(c.keywords, 'unknown') AS source_license
            FROM vertex_domain_knowledge_chunk c
            LEFT JOIN vertex_domain_knowledge_document d ON d.vertex_id = c.document_vid
            WHERE c.chunk_text IS NOT NULL
              AND c.chunk_text NOT LIKE 'signal:v1:%%'
            LIMIT {limit}
        """,
    },
}

STOPWORDS = {
    "and", "or", "the", "for", "with", "from", "that", "this", "into",
    "are", "was", "were", "have", "has", "not", "する", "こと", "ため",
    "及び", "また",
}

GENERIC_LABELS = {
    "assume responsibility",
    "communication",
    "delegate responsibilities",
    "manage data",
    "manage financial and material resources",
    "product comprehension",
    "provide membership service",
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "").lower())
    text = re.sub(r"[^\w+#.]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def tokens(value: str) -> list[str]:
    return [t for t in normalize(value).split(" ") if len(t) >= 2 and t not in STOPWORDS]


def label_usable(label: str) -> bool:
    ts = tokens(label)
    if label in GENERIC_LABELS:
        return False
    if len(ts) < 2 or len(label) < 14:
        return False
    if re.match(r"^(manage|provide|perform|carry out|execute|use|apply|follow)\s", label) and len(ts) < 4:
        return False
    return True


def parse_alt_labels(value: object) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, list):
            return [str(x) for x in parsed if x]
    except Exception:  # noqa: BLE001
        pass
    return [s.strip() for s in str(value).replace(";", "\n").splitlines() if s.strip()]


def stable_id(prefix: str, parts: list[object]) -> str:
    digest = hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()[:24]
    return f"{prefix}:{digest}"


def load_skills(skill_limit: int) -> list[dict[str, Any]]:
    client = get_kotoba_client()
    # R0: Using q() Datalog escape hatch to replicate SQL COALESCE logic
    query_edn = f"""
    [:find ?vertex_id ?label ?name ?alt_labels ?source_license
     :where
       [?e :vertex_skill/vertex_id ?vertex_id]
       [?e :vertex_skill/label ?label]
       [?e :vertex_skill/name ?name]
       [?e :vertex_skill/alt_labels ?alt_labels]
       [?e :vertex_skill/source_license ?source_license]
       (or (not-empty ?name) (not-empty ?label) (not-empty ?alt_labels))
     :limit {skill_limit}]
    """
    # Datomic's q() returns lists of values, not dicts, so we map them
    rows = client.q(query_edn)
    # The columns are hardcoded in the :find clause
    cols = ["vertex_id", "label", "name", "alt_labels", "source_license"]
    # Convert lists of values to dictionaries
    dicts = [dict(zip(cols, r)) for r in rows]
    # The original SQL had a WHERE clause that filtered based on COALESCE(name, label, '') <> ''.
    # The Datalog query's (or (not-empty ?name) ...) handles this.
    out: list[dict[str, Any]] = []
    for row in dicts:
        labels = [
            str(x) for x in [
                row.get("name"),
                row.get("label"),
                *parse_alt_labels(row.get("alt_labels")),
            ] if x
        ]
        norm_labels = sorted({normalize(label) for label in labels if len(label) >= 3})
        out.append({
            "skill_id": row.get("vertex_id"),
            "name": row.get("name") or row.get("label") or row.get("vertex_id"),
            "labels": norm_labels,
            "token_sets": [tokens(label) for label in norm_labels],
        })
    return out


def load_corpus(source: dict[str, str], limit: int) -> list[dict[str, Any]]:
    client = get_kotoba_client()
    table_name = source["table"]
    actor_did_default = source["actor_did"]
    corpus_table_label = source["table"] # This is constant for each source type

    query_edn = ""
    cols = []
    
    if table_name == "vertex_legal_corpus_document":
        # R0: `NOT LIKE` clause will be filtered in Python. Datalog does not have direct NOT LIKE.
        query_edn = f"""
        [:find ?vertex_id ?title ?body_text ?topic_tags_csv ?owner_did ?source_id
         :where
           [?e :vertex_legal_corpus_document/vertex_id ?vertex_id]
           [?e :vertex_legal_corpus_document/title ?title]
           [?e :vertex_legal_corpus_document/body_text ?body_text]
           (not (nil? ?body_text))
           [?e :vertex_legal_corpus_document/topic_tags_csv ?topic_tags_csv]
           [?e :vertex_legal_corpus_document/owner_did ?owner_did]
           [?e :vertex_legal_corpus_document/source_id ?source_id]
         :limit {limit}]
        """
        cols = ["vertex_id", "title", "body_text", "topic_tags_csv", "owner_did", "source_id"]
        
    elif table_name == "vertex_houbun_article":
        # R0: `NOT LIKE` clause will be filtered in Python. Datalog does not have direct NOT LIKE.
        query_edn = f"""
        [:find ?vertex_id ?title ?text ?article_no ?owner_did ?source_url
         :where
           [?e :vertex_houbun_article/vertex_id ?vertex_id]
           [?e :vertex_houbun_article/title ?title]
           [?e :vertex_houbun_article/text ?text]
           (not (nil? ?text))
           [?e :vertex_houbun_article/article_no ?article_no]
           [?e :vertex_houbun_article/owner_did ?owner_did]
           [?e :vertex_houbun_article/source_url ?source_url]
         :limit {limit}]
        """
        cols = ["vertex_id", "title", "text", "article_no", "owner_did", "source_url"]

    elif table_name == "vertex_domain_knowledge_chunk":
        # R0: `NOT LIKE` clause will be filtered in Python. Datalog does not have direct NOT LIKE.
        query_edn = f"""
        [:find ?c_vertex_id ?d_title ?c_chunk_text ?c_keywords ?d_owner_did ?c_keywords_for_license
         :where
           [?c :vertex_domain_knowledge_chunk/vertex_id ?c_vertex_id]
           [?c :vertex_domain_knowledge_chunk/document_vid ?d_vertex_id]
           [?c :vertex_domain_knowledge_chunk/chunk_text ?c_chunk_text]
           (not (nil? ?c_chunk_text))
           [?c :vertex_domain_knowledge_chunk/keywords ?c_keywords]
           [?d :vertex_domain_knowledge_document/vertex_id ?d_vertex_id]
           [?d :vertex_domain_knowledge_document/title ?d_title]
           [?d :vertex_domain_knowledge_document/owner_did ?d_owner_did]
           [?c :vertex_domain_knowledge_chunk/keywords ?c_keywords_for_license] ; Re-use keywords for source_license
         :limit {limit}]
        """
        cols = ["c_vertex_id", "d_title", "c_chunk_text", "c_keywords", "d_owner_did", "c_keywords_for_license"]
    else:
        return [] # Should not happen with current SOURCES

    rows = client.q(query_edn)
    
    output_docs = []
    for r in rows:
        row_dict = dict(zip(cols, r))
        
        # Apply COALESCE and NOT LIKE filtering in Python
        body_text_col = ""
        tags_col = ""
        owner_did_col = ""
        source_license_col = ""

        if table_name == "vertex_legal_corpus_document":
            if row_dict["body_text"] is None or row_dict["body_text"].startswith("signal:v1:"):
                continue # Apply NOT LIKE and IS NOT NULL filter
            body_text_col = row_dict["body_text"]
            tags_col = row_dict["topic_tags_csv"] if row_dict["topic_tags_csv"] is not None else ''
            owner_did_col = row_dict["owner_did"] if row_dict["owner_did"] is not None else actor_did_default
            source_license_col = row_dict["source_id"] if row_dict["source_id"] is not None else 'unknown'
            
            output_docs.append({
                "vertex_id": row_dict["vertex_id"],
                "corpus_table": corpus_table_label,
                "title": row_dict["title"],
                "body": body_text_col,
                "tags": tags_col,
                "owner_did": owner_did_col,
                "source_license": source_license_col,
            })
        elif table_name == "vertex_houbun_article":
            if row_dict["text"] is None or row_dict["text"].startswith("signal:v1:"):
                continue # Apply NOT LIKE and IS NOT NULL filter
            body_text_col = row_dict["text"]
            tags_col = row_dict["article_no"] if row_dict["article_no"] is not None else ''
            owner_did_col = row_dict["owner_did"] if row_dict["owner_did"] is not None else actor_did_default
            source_license_col = row_dict["source_url"] if row_dict["source_url"] is not None else 'unknown'
            
            output_docs.append({
                "vertex_id": row_dict["vertex_id"],
                "corpus_table": corpus_table_label,
                "title": row_dict["title"],
                "body": body_text_col,
                "tags": tags_col,
                "owner_did": owner_did_col,
                "source_license": source_license_col,
            })
        elif table_name == "vertex_domain_knowledge_chunk":
            if row_dict["c_chunk_text"] is None or row_dict["c_chunk_text"].startswith("signal:v1:"):
                continue # Apply NOT LIKE and IS NOT NULL filter
            body_text_col = row_dict["c_chunk_text"]
            tags_col = row_dict["c_keywords"] if row_dict["c_keywords"] is not None else ''
            owner_did_col = row_dict["d_owner_did"] if row_dict["d_owner_did"] is not None else actor_did_default
            source_license_col = row_dict["c_keywords_for_license"] if row_dict["c_keywords_for_license"] is not None else 'unknown'

            output_docs.append({
                "vertex_id": row_dict["c_vertex_id"],
                "corpus_table": corpus_table_label,
                "title": row_dict["d_title"],
                "body": body_text_col,
                "tags": tags_col,
                "owner_did": owner_did_col,
                "source_license": source_license_col,
            })
    return output_docs


def evidence(normalized_doc: str, label: str) -> dict[str, Any]:
    idx = normalized_doc.find(label)
    if idx < 0:
        first = label.split(" ")[0]
        idx = normalized_doc.find(first)
        end = idx + len(first) if idx >= 0 else 0
    else:
        end = idx + len(label)
    if idx < 0:
        return {"text": normalized_doc[:220], "start": 0, "end": 0}
    return {"text": normalized_doc[max(0, idx - 80): end + 180], "start": idx, "end": end}


def score_skill(normalized_doc: str, skill: dict[str, Any], min_score: float) -> dict[str, Any] | None:
    if normalize(skill.get("name")) in GENERIC_LABELS:
        return None
    best: dict[str, Any] | None = None
    labels: list[str] = skill.get("labels") or []
    token_sets: list[list[str]] = skill.get("token_sets") or []
    for i, label in enumerate(labels):
        if not label_usable(label):
            continue
        if label in normalized_doc:
            best = {"score": min(0.99, 0.9 + min(0.09, len(label) / 180)), "match_kind": "exact_label", "label": label}
            continue
        ts = token_sets[i] if i < len(token_sets) else []
        if len(ts) >= 4 and all(t in normalized_doc for t in ts):
            score = 0.82 + min(0.07, len(ts) / 100)
            if best is None or score > float(best["score"]):
                best = {"score": score, "match_kind": "token_overlap", "label": label}
    if best is None or float(best["score"]) < min_score:
        return None
    best["evidence"] = evidence(normalized_doc, str(best["label"]))
    return best


def insert_run(run: dict[str, Any]) -> None:
    client = get_kotoba_client()
    row_to_insert = {
        "vertex_id": run["vertex_id"],
        "sensitivity_ord": 1,
        "owner_did": "did:web:recruit.etzhayyim.com",
        "rkey": run["rkey"],
        "repo": "did:web:recruit.etzhayyim.com", # Original SQL had a literal here, not run["repo"]
        "label": run["label"],
        "source_table": run["source_table"],
        "source_actor_did": run["source_actor_did"],
        "extractor_version": VERSION,
        "model_id": "lexical-v0",
        "params_json": json.dumps(run["params"], ensure_ascii=False),
        "corpus_limit": run["corpus_limit"],
        "skill_limit": run["skill_limit"],
        "min_score": run["min_score"],
        "matched_documents": run["matched_documents"],
        "emitted_edges": run["emitted_edges"],
        "status": run["status"],
        "started_at": run["started_at"], # These are already formatted ISO strings
        "finished_at": run["finished_at"], # These are already formatted ISO strings
    }
    client.insert_row("vertex_corpus_skill_extraction_run", row_to_insert)


def insert_edge(run_id: str, edge: dict[str, Any]) -> None:
    edge_id = stable_id(
        "edge:corpus-skill",
        [edge["corpus_table"], edge["corpus_vertex_id"], edge["skill_id"], edge["match_kind"]],
    )
    client = get_kotoba_client()
    row_to_insert = {
        "edge_id": edge_id,
        "corpus_vertex_id": edge["corpus_vertex_id"],
        "corpus_table": edge["corpus_table"],
        "skill_id": edge["skill_id"],
        "extraction_run_id": run_id,
        "source_actor_did": edge["source_actor_did"],
        "match_kind": edge["match_kind"],
        "score": edge["score"],
        "evidence_text": edge["evidence_text"],
        "evidence_start": edge["evidence_start"],
        "evidence_end": edge["evidence_end"],
        "source": "curpus2skill",
        "source_license": edge.get("source_license"),
        "ingested_at": edge["ingested_at"], # This is already formatted ISO string
        "props": json.dumps({"skillName": edge.get("skill_name")}, ensure_ascii=False),
    }
    client.insert_row("edge_corpus_skill_evidence", row_to_insert)


async def task_curpus2skill_extract_evidence(
    source: str = "legal-corpus",
    limit: int = 10,
    skillLimit: int = 2000,
    minScore: float = 0.97,
    topK: int = 5,
    dryRun: bool = False,
) -> dict:
    source_key = source or "legal-corpus"
    if source_key not in SOURCES:
        return {"error": f"unknown source: {source_key}", "knownSources": sorted(SOURCES)}
    limit_i = max(1, min(int(limit or 10), 500))
    skill_limit_i = max(1, min(int(skillLimit or 2000), 20000))
    top_k_i = max(1, min(int(topK or 5), 20))
    min_score_f = max(0.0, min(float(minScore or 0.97), 1.0))
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    src = SOURCES[source_key]

    try:
        skills = await asyncio.to_thread(load_skills, skill_limit_i)
        docs = await asyncio.to_thread(load_corpus, src, limit_i)
    except Exception as e:  # noqa: BLE001
        return {"error": f"load failed: {e}", "source": source_key}

    edges: list[dict[str, Any]] = []
    for doc in docs:
        normalized_doc = normalize("\n".join(str(x or "") for x in [doc.get("title"), doc.get("tags"), doc.get("body")]))
        matches: list[dict[str, Any]] = []
        for skill in skills:
            scored = score_skill(normalized_doc, skill, min_score_f)
            if not scored:
                continue
            ev = scored["evidence"]
            matches.append({
                "corpus_vertex_id": doc.get("vertex_id"),
                "corpus_table": doc.get("corpus_table"),
                "skill_id": skill.get("skill_id"),
                "skill_name": skill.get("name"),
                "score": round(float(scored["score"]), 4),
                "match_kind": scored["match_kind"],
                "evidence_text": str(ev["text"])[:900],
                "evidence_start": int(ev["start"]),
                "evidence_end": int(ev["end"]),
                "source_actor_did": doc.get("owner_did") or src["actor_did"],
                "source_license": doc.get("source_license"),
                "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        matches.sort(key=lambda e: e["score"], reverse=True)
        edges.extend(matches[:top_k_i])

    finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    run_id = stable_id("run:curpus2skill", [source_key, started, limit_i, skill_limit_i, min_score_f])
    run = {
        "vertex_id": run_id,
        "rkey": re.sub(r"[^a-zA-Z0-9-]", "-", run_id)[:63],
        "label": f"curpus2skill {source_key} {started}",
        "source_table": src["table"],
        "source_actor_did": src["actor_did"],
        "params": {"source": source_key, "topK": top_k_i, "dryRun": bool(dryRun)},
        "corpus_limit": limit_i,
        "skill_limit": skill_limit_i,
        "min_score": min_score_f,
        "matched_documents": len({e["corpus_vertex_id"] for e in edges}),
        "emitted_edges": len(edges),
        "status": "dry_run" if dryRun else "completed",
        "started_at": started,
        "finished_at": finished,
    }
    if not dryRun:
        try:
            await asyncio.to_thread(insert_run, run)
            for edge in edges:
                await asyncio.to_thread(insert_edge, run_id, edge)
        except Exception as e:  # noqa: BLE001
            return {"error": f"write failed: {e}", "runId": run_id, "edgeCount": len(edges)}

    return {
        "runId": run_id,
        "source": source_key,
        "sourceTable": src["table"],
        "dryRun": bool(dryRun),
        "documentsScanned": len(docs),
        "skillsLoaded": len(skills),
        "matchedDocuments": run["matched_documents"],
        "emittedEdges": run["emitted_edges"],
        "sample": edges[:10],
    }
