"""
legal.houbunLinker — infer LEI / contract / Japanese law-article links.

Graph:
  START -> load_candidates -> infer_links -> persist_links -> emit_audit -> END

The graph writes hypotheses first. Promoted edge rows are still marked
`status='inferred'`; review/gate promotion can move them to verified later.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client


OWNER_DID = "did:web:legal-intel.etzhayyim.com"
RUN_COLLECTION = "com.etzhayyim.apps.legalHoubun.linkRun"
HYP_COLLECTION = "com.etzhayyim.apps.legalHoubun.linkHypothesis"


class LegalHoubunLinkerState(TypedDict, total=False):
    country: str
    jurisdiction: str
    maxEntities: int
    maxArticles: int
    minConfidence: float
    dryRun: bool
    legalEntityVid: str
    contractVid: str
    llmTier: str
    _entities: list[dict[str, Any]]
    _articles: list[dict[str, Any]]
    _contracts: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    runId: str
    runVertexId: str
    hypothesisRows: int
    edgeRows: int
    model: str
    ok: bool
    error: str | None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _vid(collection: str) -> str:
    return f"at://{OWNER_DID}/{collection}/{int(time.time() * 1000)}-{uuid.uuid4().hex[:10]}"


def _json_loads_maybe(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    return json.loads(raw)


def _fallback_hypotheses(
    entities: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Conservative deterministic fallback when the LLM is unavailable."""
    if not articles:
        return []
    out: list[dict[str, Any]] = []
    company_article = next(
        (
            a
            for a in articles
            if "companies" in str(a.get("lawId") or "")
            or "会社" in str(a.get("title") or "")
            or "法人" in str(a.get("text") or "")
        ),
        articles[0],
    )
    contract_article = next(
        (
            a
            for a in articles
            if "contract" in str(a.get("lawId") or "")
            or "契約" in str(a.get("title") or "")
            or "契約" in str(a.get("text") or "")
        ),
        articles[0],
    )
    for entity in entities[:5]:
        out.append(
            {
                "subjectVid": entity["vertexId"],
                "subjectKind": "legal_entity",
                "articleVid": company_article["vertexId"],
                "relationType": "governed_by",
                "confidence": 0.55,
                "rationale": "Fallback heuristic: Japanese legal entity links to corporate-law article candidate.",
                "evidence": [entity.get("name", ""), company_article.get("title", "")],
            }
        )
    for contract in contracts[:5]:
        out.append(
            {
                "subjectVid": contract["vertexId"],
                "subjectKind": "contract",
                "articleVid": contract_article["vertexId"],
                "relationType": "has_legal_basis",
                "confidence": 0.55,
                "rationale": "Fallback heuristic: contract-like record links to contract/labor article candidate.",
                "evidence": [contract.get("title", ""), contract_article.get("title", "")],
            }
        )
    return out


def load_candidates(state: LegalHoubunLinkerState) -> dict:
    country = (state.get("country") or "JP").upper()
    jurisdiction = (state.get("jurisdiction") or "JPN").upper()
    max_entities = int(state.get("maxEntities") or 24)
    max_articles = int(state.get("maxArticles") or 48)
    entity_vid = (state.get("legalEntityVid") or "").strip()
    contract_vid = (state.get("contractVid") or "").strip()

    kotoba_client = get_kotoba_client()

    # R0: Converted complex SQL query for vertex_open_lei_entity to Datalog q() with in-Python filtering and ordering.
    entity_datalog_query = """
    [:find (pull ?e [:vertex/id :open_lei_entity/lei :open_lei_entity/legal_name
                     :open_lei_entity/country :open_lei_entity/legal_form
                     :open_lei_entity/registration_authority :open_lei_entity/next_renewal_at
                     :open_lei_entity/status])
     :where
     [?e :vertex/type "open_lei_entity"]]
    """
    all_lei_entities = kotoba_client.q(entity_datalog_query)

    filtered_entities = []
    for r_list in all_lei_entities:
        r = r_list[0] if isinstance(r_list, list) else r_list # q() returns list of lists or just lists of dicts
        if not r or not isinstance(r, dict):
            continue

        # Apply WHERE conditions from original SQL query
        vertex_id_match = (not entity_vid) or (r.get("vertex/id") == entity_vid)
        country_upper = (r.get("open_lei_entity/country") or "").upper()
        country_match = country_upper in (country, jurisdiction)
        status_match = r.get("open_lei_entity/status") == "active"

        if vertex_id_match and country_match and status_match:
            filtered_entities.append(r)

    # Sort and limit in Python as per original SQL ORDER BY and LIMIT
    entities_sorted_limited = sorted(
        filtered_entities,
        key=lambda x: x.get("open_lei_entity/next_renewal_at") or "", # NULLS LAST is handled by empty string effectively
        reverse=True,
    )[:max_entities]

    # Convert to desired dict format
    entities = [
        {
            "vertexId": r.get("vertex/id"),
            "lei": r.get("open_lei_entity/lei"),
            "name": r.get("open_lei_entity/legal_name"),
            "country": r.get("open_lei_entity/country"),
            "legalForm": r.get("open_lei_entity/legal_form"),
            "registrationAuthority": r.get("open_lei_entity/registration_authority"),
        }
        for r in entities_sorted_limited
    ]

    # R0: Converted complex SQL query for vertex_governance_contract to Datalog q() with in-Python filtering and ordering.
    contract_datalog_query = """
    [:find (pull ?e [:vertex/id :governance_contract/name :governance_contract/legal_basis
                     :governance_contract/country_code :governance_contract/url
                     :governance_contract/effective_date])
     :where
     [?e :vertex/type "governance_contract"]]
    """
    all_contracts = kotoba_client.q(contract_datalog_query)

    filtered_contracts = []
    for r_list in all_contracts:
        r = r_list[0] if isinstance(r_list, list) else r_list
        if not r or not isinstance(r, dict):
            continue

        # Apply WHERE conditions from original SQL query
        vertex_id_match = (not contract_vid) or (r.get("vertex/id") == contract_vid)
        country_upper = (r.get("governance_contract/country_code") or "").upper()
        country_match = country_upper in (country, jurisdiction, "")

        if vertex_id_match and country_match:
            filtered_contracts.append(r)

    # Sort and limit in Python as per original SQL ORDER BY and LIMIT
    contracts_sorted_limited = sorted(
        filtered_contracts,
        key=lambda x: x.get("governance_contract/effective_date") or "", # NULLS LAST
        reverse=True,
    )[:12]

    contracts = [
        {
            "vertexId": r.get("vertex/id"),
            "title": r.get("governance_contract/name"),
            "legalBasis": r.get("governance_contract/legal_basis"),
            "country": r.get("governance_contract/country_code"),
            "url": r.get("governance_contract/url"),
        }
        for r in contracts_sorted_limited
    ]

    # R0: Converted complex SQL query for vertex_houbun_article to Datalog q() with in-Python filtering and ordering.
    houbun_datalog_query = """
    [:find (pull ?e [:vertex/id :houbun_article/statute_ref :houbun_article/article_no
                     :houbun_article/title :houbun_article/text :houbun_article/language])
     :where
     [?e :vertex/type "houbun_article"]]
    """
    all_houbun_articles = kotoba_client.q(houbun_datalog_query)

    houbun_articles_filtered = []
    for r_list in all_houbun_articles:
        r = r_list[0] if isinstance(r_list, list) else r_list
        if not r or not isinstance(r, dict):
            continue

        language = (r.get("houbun_article/language") or "").upper()
        statute_ref = (r.get("houbun_article/statute_ref") or "").lower()

        # Apply WHERE conditions from original SQL query
        if language in ("JA", "JPN", "JAPANESE", "") or "jpn" in statute_ref:
            houbun_articles_filtered.append(r)

    # R0: Converted complex SQL query for vertex_hourei_jobun to Datalog q() with in-Python filtering and ordering.
    hourei_datalog_query = """
    [:find (pull ?e [:vertex/id :hourei_jobun/hourei_id :hourei_jobun/article_no
                     :hourei_jobun/title :hourei_jobun/summary :hourei_jobun/text])
     :where
     [?e :vertex/type "hourei_jobun"]]
    """
    all_hourei_jobuns = kotoba_client.q(hourei_datalog_query)

    hourei_jobuns_filtered = []
    for r_list in all_hourei_jobuns:
        r = r_list[0] if isinstance(r_list, list) else r_list
        if not r or not isinstance(r, dict):
            continue
        # No specific filtering for hourei_jobun in SQL, just language.
        # Assuming Japanese for now based on context of 'JA', 'JPN' above.
        # If there's a language field, it would be filtered like houbun.
        # For now, all fetched hourei_jobun are considered.
        hourei_jobuns_filtered.append(r)

    # Prepare for in-Python sorting based on original SQL's complex ORDER BY
    houbun_rows_for_sorting = [
        {
            "vertexId": r.get("vertex/id"),
            "sourceKind": "houbun",
            "lawId": r.get("houbun_article/statute_ref"),
            "articleNo": r.get("houbun_article/article_no"),
            "title": r.get("houbun_article/title"),
            "text": (r.get("houbun_article/text") or ""),
            "sort_text": (r.get("houbun_article/text") or "") + (r.get("houbun_article/title") or "")
        }
        for r in houbun_articles_filtered
    ]

    hourei_rows_for_sorting = [
        {
            "vertexId": r.get("vertex/id"),
            "sourceKind": "hourei",
            "lawId": r.get("hourei_jobun/hourei_id"),
            "articleNo": r.get("hourei_jobun/article_no"),
            "title": r.get("hourei_jobun/title"),
            "text": (r.get("hourei_jobun/summary") or r.get("hourei_jobun/text") or ""),
            "sort_text": (r.get("hourei_jobun/summary") or r.get("hourei_jobun/text") or "") + (r.get("hourei_jobun/title") or "")
        }
        for r in hourei_jobuns_filtered
    ]

    all_articles_for_sorting = houbun_rows_for_sorting + hourei_rows_for_sorting

    def article_sort_key(article):
        text = article.get("sort_text", "")
        if "法人" in text:
            return 0
        if "会社" in text:
            return 1
        if "契約" in text:
            return 2
        if "登記" in text:
            return 3
        return 9

    sorted_articles_limited = sorted(
        all_articles_for_sorting,
        key=lambda x: (article_sort_key(x), x.get("articleNo") or float('inf'))
    )[:max_articles]

    articles = [
        {
            "vertexId": r["vertexId"],
            "sourceKind": r["sourceKind"],
            "lawId": r["lawId"],
            "articleNo": r["articleNo"],
            "title": r["title"],
            "text": (r["text"] or "")[:700],
        }
        for r in sorted_articles_limited
    ]

    return {
        "_entities": entities,
        "_contracts": contracts,
        "_articles": articles,
        "ok": True,
        "error": None,
    }


def infer_links(state: LegalHoubunLinkerState) -> dict:
    entities = state.get("_entities") or []
    contracts = state.get("_contracts") or []
    articles = state.get("_articles") or []
    if not entities and not contracts:
        return {"hypotheses": [], "ok": True, "error": "no legal entities or contracts to link"}
    if not articles:
        return {"hypotheses": [], "ok": False, "error": "no houbun/hourei articles available"}

    system = (
        "You infer legal graph links. Return strict JSON only. "
        "Use relationType governed_by for legal_entity -> article, "
        "has_legal_basis for contract -> article, and depends_on_contract only "
        "when an entity explicitly depends on a contract. Do not invent statutes. "
        "Low certainty is allowed; confidence must be 0..1."
    )
    user = json.dumps(
        {
            "task": "Infer Japanese legal-entity / contract links to law articles.",
            "legalEntities": entities[:20],
            "contracts": contracts[:10],
            "articles": articles[:40],
            "outputSchema": {
                "links": [
                    {
                        "subjectVid": "vertex id from legalEntities or contracts",
                        "subjectKind": "legal_entity|contract",
                        "articleVid": "vertex id from articles",
                        "relationType": "governed_by|has_legal_basis|regulated_by",
                        "confidence": 0.0,
                        "rationale": "short reason",
                        "evidence": ["short evidence strings"],
                    }
                ]
            },
        },
        ensure_ascii=False,
    )

    tier = state.get("llmTier") or "structured"
    try:
        resp = llm.call_tier(
            tier,
            system,
            user,
            max_tokens=900,
            temperature=0.1,
            timeout_sec=20.0,
            extra={"response_format": {"type": "json_object"}},
        )
        parsed = _json_loads_maybe(resp.get("content") or "")
        links = parsed.get("links") if isinstance(parsed, dict) else []
        model = resp.get("model") or tier
    except Exception as exc:
        links = _fallback_hypotheses(entities, contracts, articles)
        model = f"fallback:{type(exc).__name__}"
    if not links:
        links = _fallback_hypotheses(entities, contracts, articles)
        model = f"{model or tier}:fallback-empty"

    valid_subjects = {r["vertexId"] for r in entities} | {r["vertexId"] for r in contracts}
    valid_articles = {r["vertexId"] for r in articles}
    hypotheses: list[dict[str, Any]] = []
    for link in links or []:
        if not isinstance(link, dict):
            continue
        subject = str(link.get("subjectVid") or "")
        article = str(link.get("articleVid") or "")
        if subject not in valid_subjects or article not in valid_articles:
            continue
        try:
            confidence = max(0.0, min(1.0, float(link.get("confidence") or 0.0)))
        except (TypeError, ValueError):
            confidence = 0.0
        hypotheses.append(
            {
                "subjectVid": subject,
                "subjectKind": str(link.get("subjectKind") or "legal_entity"),
                "articleVid": article,
                "relationType": str(link.get("relationType") or "governed_by"),
                "confidence": confidence,
                "rationale": str(link.get("rationale") or "")[:1200],
                "evidence": link.get("evidence") if isinstance(link.get("evidence"), list) else [],
            }
        )

    return {"hypotheses": hypotheses, "model": model, "ok": True, "error": None}


def persist_links(state: LegalHoubunLinkerState) -> dict:
    hypotheses = state.get("hypotheses") or []
    now = _now_iso()
    today = now[:10]
    run_id = f"legal-houbun-link-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
    run_vid = _vid(RUN_COLLECTION)
    min_conf = float(state.get("minConfidence") or 0.55)
    dry_run = bool(state.get("dryRun") or False)
    if dry_run:
        return {
            "runId": run_id,
            "runVertexId": run_vid,
            "hypothesisRows": 0,
            "edgeRows": 0,
            "ok": True,
        }

    kotoba_client = get_kotoba_client()
    hyp_rows = 0
    edge_rows = 0

    # Insert into vertex_legal_houbun_link_run
    run_row_dict = {
        "vertex_id": run_vid,
        "run_id": run_id,
        "country": state.get("country") or "JP",
        "jurisdiction": state.get("jurisdiction") or "JPN",
        "entity_count": len(state.get("_entities") or []),
        "contract_count": len(state.get("_contracts") or []),
        "article_count": len(state.get("_articles") or []),
        "hypothesis_count": len(hypotheses),
        "model": state.get("model") or "",
        "status": "completed",
        "started_at": now,
        "completed_at": now,
        "created_date": today,
        "sensitivity_ord": 0,
        "owner_did": OWNER_DID,
    }
    kotoba_client.insert_row("vertex_legal_houbun_link_run", run_row_dict)

    for hyp in hypotheses:
        hyp_vid = _vid(HYP_COLLECTION)
        status = "pending_review"

        # Insert into vertex_legal_houbun_link_hypothesis
        hypothesis_row_dict = {
            "vertex_id": hyp_vid,
            "run_id": run_id,
            "subject_vid": hyp["subjectVid"],
            "subject_kind": hyp["subjectKind"],
            "article_vid": hyp["articleVid"],
            "relation_type": hyp["relationType"],
            "confidence": hyp["confidence"],
            "rationale": hyp["rationale"],
            "evidence_json": json.dumps(hyp.get("evidence") or [], ensure_ascii=False),
            "status": status,
            "model": state.get("model") or "",
            "created_at": now,
            "created_date": today,
            "sensitivity_ord": 0,
            "owner_did": OWNER_DID,
        }
        kotoba_client.insert_row("vertex_legal_houbun_link_hypothesis", hypothesis_row_dict)
        hyp_rows += 1

        if float(hyp["confidence"]) < min_conf:
            continue

        table = (
            "edge_contract_houbun_article"
            if hyp["subjectKind"] == "contract"
            else "edge_legal_entity_houbun_article"
        )
        edge_id = "edge:" + uuid.uuid4().hex

        # Insert into edge_* table
        edge_row_dict = {
            "edge_id": edge_id,
            "src_vid": hyp["subjectVid"],
            "dst_vid": hyp["articleVid"],
            "relation_type": hyp["relationType"],
            "confidence": hyp["confidence"],
            "hypothesis_vid": hyp_vid,
            "status": "inferred",
            "created_at": now,
            "created_date": today,
            "sensitivity_ord": 0,
            "owner_did": OWNER_DID,
        }
        kotoba_client.insert_row(table, edge_row_dict)
        edge_rows += 1

    return {
        "runId": run_id,
        "runVertexId": run_vid,
        "hypothesisRows": hyp_rows,
        "edgeRows": edge_rows,
        "ok": True,
        "error": None,
    }


def emit_audit(state: LegalHoubunLinkerState) -> dict:
    try:
        kotoba_client = get_kotoba_client()
        # Insert into vertex_repo_commit
        repo_commit_row_dict = {
            "vertex_id": str(uuid.uuid4()),
            "repo": OWNER_DID,
            "collection": RUN_COLLECTION,
            "rkey": f"lg-{int(time.time() * 1000)}",
            "action": "create",
            "ts_ms": int(time.time() * 1000),
            "record_json": json.dumps(
                {
                    "runId": state.get("runId"),
                    "hypothesisRows": state.get("hypothesisRows", 0),
                    "edgeRows": state.get("edgeRows", 0),
                    "ok": state.get("ok", False),
                },
                ensure_ascii=False,
            ),
        }
        kotoba_client.insert_row("vertex_repo_commit", repo_commit_row_dict)
    except Exception:
        pass
    return {}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(LegalHoubunLinkerState)
    builder.add_node("load_candidates", load_candidates)
    builder.add_node("infer_links", infer_links)
    builder.add_node("persist_links", persist_links)
    builder.add_node("emit_audit", emit_audit)
    builder.set_entry_point("load_candidates")
    builder.add_edge("load_candidates", "infer_links")
    builder.add_edge("infer_links", "persist_links")
    builder.add_edge("persist_links", "emit_audit")
    builder.add_edge("emit_audit", END)
    return builder.compile()
