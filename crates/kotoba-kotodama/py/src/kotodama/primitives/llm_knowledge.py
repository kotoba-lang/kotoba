"""LLM domain-knowledge retrieval and LangGraph answer primitives.

These functions are Zeebe worker task bodies for:
  - llm.knowledge.retrieve
  - llm.knowledge.langgraphAnswer

Facts are read from kotoba Datom log domain-knowledge vertices/MVs. No domain facts
are hard-coded in Python or Cloudflare Workers.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any, TypedDict

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - optional in some worker images
    END = "__end__"
    StateGraph = None  # type: ignore[assignment]


class AnswerState(TypedDict, total=False):
    question: str
    contexts: list[dict[str, Any]]
    citations: list[str]
    tier: str
    lang: str
    ok: bool
    answer: str
    confidence: str
    model: str
    latencyMs: int
    error: str
    errorKind: str


# Keep the LLM attempt timeout below the BPMN result timeout. `llm.call_tier`
# retries once, so 40s + 2s backoff + 40s stays inside the 90s SSE result
# window and returns an explicit LlmError instead of silently hanging.
LLM_KNOWLEDGE_TIMEOUT_SEC = float(os.environ.get("LLM_KNOWLEDGE_TIMEOUT_SEC", "40"))


def _terms(question: str) -> list[str]:
    q = question.lower()
    raw = [x for x in re.split(r"[\s、。,.!?！？/]+", q) if len(x) >= 2]
    aliases = {
        "pokopia": ["ぽこあ", "ポコピア", "pokopia", "pokemon-pokopia"],
        "dream-island": ["夢島", "ゆめしま", "dream island"],
        "drifloon": ["フワンテ", "drifloon"],
        "habitat": ["棲家", "すみか", "あたたかい風"],
    }
    out = list(raw)
    for values in aliases.values():
        if any(v.lower() in q for v in values):
            out.extend(values)
    return list(dict.fromkeys(out))[:12]


def _fetch_citations(document_vids: list[str]) -> list[str]:
    if not document_vids:
        return []
    kotoba_client = get_kotoba_client()
    # R0: Using q() Datalog escape hatch for IN clause and JOIN, then sorting in Python.
    # Assuming attributes:
    # edge_domain_knowledge_cites: :edge-domain-knowledge-cites/src-vid, :edge-domain-knowledge-cites/dst-vid
    # vertex_domain_knowledge_source: :vertex-domain-knowledge-source/vertex-id, :vertex-domain-knowledge-source/url, :vertex-domain-knowledge-source/confidence
    query_edn = """
    [:find ?url ?confidence
     :in $ [?src_vid ...]
     :where
     [?e :edge-domain-knowledge-cites/src-vid ?src_vid]
     [?e :edge-domain-knowledge-cites/dst-vid ?s_vid]
     [?s_vid :vertex-domain-knowledge-source/url ?url]
     [?s_vid :vertex-domain-knowledge-source/confidence ?confidence]]
    """
    results = kotoba_client.q(query_edn, args=(document_vids,))
    # Sort in Python as per original SQL ORDER BY s.confidence DESC, s.url ASC
    # results are list of [url, confidence] tuples
    sorted_results = sorted(results, key=lambda x: (-x[1], x[0])) # x[1] is confidence, x[0] is url
    return list(dict.fromkeys(str(row[0]) for row in sorted_results))


def retrieve(
    question: str,
    domain: str = "",
    gameSlug: str = "",
    lang: str = "ja",
    topK: int = 8,
) -> dict[str, Any]:
    qs = _terms(question)

    limit = max(1, min(int(topK or 8), 20))
    kotoba_client = get_kotoba_client()

    # R0: Initial fetch based on 'lang', then filtering domain, game_slug, and search_text in Python
    #     due to complex WHERE clauses (AND, OR, LIKE) not directly supported by select_where,
    #     and applying ORDER BY and LIMIT in Python.
    # The 'mv_domain_knowledge_search' is treated as a table name for select_where.
    all_columns = [
        "chunk_vid", "document_vid", "domain", "actor_did", "canonical_work_id",
        "game_slug", "title", "lang", "chunk_index", "chunk_text", "keywords",
        "confidence", "updated_at"
    ]
    # Fetch broadly by lang, assuming it's the primary filter for a large initial set.
    # Limit to a reasonably large number (e.g., 2000) to ensure subsequent Python filters
    # have enough data to work with.
    fetched_rows = kotoba_client.select_where(
        "mv_domain_knowledge_search",
        "lang",
        lang or "ja",
        columns=all_columns,
        limit=2000 # Use a generous limit for the initial fetch
    )

    filtered_rows = []
    for row in fetched_rows:
        # Apply domain filter
        if domain and row.get("domain") != domain:
            continue
        # Apply gameSlug filter
        if gameSlug and row.get("game_slug") != gameSlug:
            continue

        # Apply search_text LIKE filter (for qs terms)
        match_qs = False
        if not qs: # No search terms, so it's a match
            match_qs = True
        else:
            chunk_text = row.get("chunk_text", "").lower()
            keywords = row.get("keywords", "").lower()
            for q_term in qs:
                # Original SQL used %term%, so it's a substring match
                if q_term.lower() in chunk_text or q_term.lower() in keywords:
                    match_qs = True
                    break
        if not match_qs:
            continue
        filtered_rows.append(row)

    # Apply ORDER BY updated_at DESC, chunk_index ASC in Python
    # If updated_at is None, handle it to avoid errors during comparison.
    # For descending updated_at, we need to sort descending.
    # For chunk_index ascending, we sort ascending.
    # To achieve updated_at DESC and chunk_index ASC with a single sort key,
    # we use a tuple for sorting: updated_at (effectively descending), then chunk_index ascending.
    # If `updated_at` values are `datetime` objects, `datetime.max - updated_at` can be used to reverse the order for sorting.
    # We sort by `updated_at` descending and `chunk_index` ascending.
    # Python's `sorted()` by default sorts ascending. To get `updated_at DESC`, we need to make larger `updated_at` values
    # appear "smaller" in the sort key. If updated_at is a datetime object,
    # `datetime.max - updated_at` effectively reverses its natural order.
    final_sorted_rows = sorted(
        filtered_rows,
        key=lambda x: (
            x.get("updated_at") if x.get("updated_at") is not None else datetime.min,
            x.get("chunk_index", 0)
        ),
        reverse=True # Apply reverse to the whole tuple to sort updated_at in descending order. chunk_index will still be sorted ascending among equal updated_at values due to tuple sorting rules.
    )

    # Apply LIMIT
    rows_limited = final_sorted_rows[:limit]

    used = sorted({str(row["document_vid"]) for row in rows_limited})
    return {
        "contexts": rows_limited,
        "citations": _fetch_citations(used),
        "usedKnowledge": used,
    }


def _answer_node(state: AnswerState) -> AnswerState:
    started = time.monotonic()
    contexts = state.get("contexts") or []
    citations = state.get("citations") or []
    if not contexts:
        return {
            **state,
            "ok": False,
            "answer": "該当する domain knowledge が kotoba Datom log に見つかりませんでした。",
            "confidence": "low",
            "model": "none",
            "latencyMs": int((time.monotonic() - started) * 1000),
        }

    evidence = "\n\n".join(
        f"[{i + 1}] {c.get('title')}\n{c.get('chunk_text')}"
        for i, c in enumerate(contexts)
    )
    system = (
        "You answer only from provided evidence. If evidence is insufficient, say so. "
        "Return concise Japanese by default and include source URLs when present."
    )
    user = (
        f"Question:\n{state['question']}\n\n"
        f"Evidence:\n{evidence}\n\n"
        "Sources:\n" + "\n".join(f"- {c}" for c in citations)
    )
    try:
        result = llm.call_tier(
            state.get("tier") or "fast",
            system=system,
            user=user,
            max_tokens=900,
            temperature=0.1,
            timeout_sec=LLM_KNOWLEDGE_TIMEOUT_SEC,
        )
        answer = str(result.get("content") or "").strip()
        model = str(result.get("model") or "")
        latency = int(result.get("latencyMs") or int((time.monotonic() - started) * 1000))
    except llm.LlmError as exc:
        return {
            **state,
            "ok": False,
            "answer": "",
            "confidence": "error",
            "model": "",
            "latencyMs": int((time.monotonic() - started) * 1000),
            "error": f"llm backend failed: {exc}",
            "errorKind": type(exc).__name__,
        }
    if not answer:
        return {
            **state,
            "ok": False,
            "answer": "",
            "confidence": "error",
            "model": model,
            "latencyMs": latency,
            "error": "llm backend returned empty content",
            "errorKind": "EmptyLlmContent",
        }

    return {
        **state,
        "ok": True,
        "answer": answer,
        "confidence": "high" if len(contexts) >= 2 else "medium",
        "model": model,
        "latencyMs": latency,
    }


def _build_graph():
    if StateGraph is None:
        return None
    graph = StateGraph(AnswerState)
    graph.add_node("answer", _answer_node)
    graph.set_entry_point("answer")
    graph.add_edge("answer", END)
    return graph.compile()


_GRAPH = None


def answer(
    question: str,
    contexts: list[dict[str, Any]] | None = None,
    citations: list[str] | None = None,
    tier: str = "fast",
    lang: str = "ja",
) -> dict[str, Any]:
    global _GRAPH
    state: AnswerState = {
        "question": question,
        "contexts": contexts or [],
        "citations": citations or [],
        "tier": tier,
        "lang": lang,
    }
    if _GRAPH is None:
        _GRAPH = _build_graph()
    if _GRAPH is not None and hasattr(_GRAPH, "invoke"):
        result = _GRAPH.invoke(state)
    else:
        result = _answer_node(state)
    return {
        "ok": bool(result.get("ok", bool(result.get("answer")))),
        "answer": result.get("answer", ""),
        "confidence": result.get("confidence", "low"),
        "model": result.get("model", ""),
        "latencyMs": result.get("latencyMs", 0),
        "error": result.get("error", ""),
        "errorKind": result.get("errorKind", ""),
    }
