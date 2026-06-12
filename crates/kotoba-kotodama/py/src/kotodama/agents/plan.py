"""
com.etzhayyim.agent.plan — LangGraph ingest planner (Phase D pilot).

Three-node StateGraph:

    classify_task   — LLM decides which "branch" to take (fast / thorough
                      / skip) given the input context. This is the single
                      agentic decision; everything else is deterministic.
    summarise_plan  — Build a flat plan dict the BPMN caller can switch on
                      via FEEL (branch, nextTool, confidence, reason).
    audit_plan      — Record the plan in vertex_repo_commit so the
                      decision leaves an OCEL-compatible trail. Same
                      shape as generic.audit.emit.

Input variables (Zeebe → LangGraph state):
    context        — arbitrary dict (e.g. row being ingested)
    taskHint       — optional string narrowing the decision space
    threadId       — BPMN process instance key, used as LangGraph
                     thread_id for checkpoint persistence
    budgetMs       — soft cap (default 5000) — informational, Zeebe
                     timeout is the hard limit

Output variables (LangGraph state → Zeebe):
    branch         — one of "fast" / "thorough" / "skip"
    nextTool       — NSID of the tool the caller should invoke next
                     (e.g. "com.etzhayyim.apps.yabai.trackPhishingInfra")
    confidence     — 0.0 - 1.0 (LLM-reported)
    reason         — <=200 char human rationale
    planLatencyMs  — wall clock of the LLM call
    auditRkey      — vertex_repo_commit rkey if audit succeeded
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client

log = logging.getLogger(__name__)


# ─── State ──────────────────────────────────────────────────────────────


class PlanState(TypedDict, total=False):
    # Input
    context: dict[str, Any]
    taskHint: str
    threadId: str
    budgetMs: int
    # Decision
    branch: str
    nextTool: str
    confidence: float
    reason: str
    planLatencyMs: int
    llmModel: str
    # Audit
    auditRkey: str


# ─── Nodes ──────────────────────────────────────────────────────────────


_CLASSIFY_SYSTEM = """\
You are an ingest-pipeline dispatcher routing rows through a etzhayyim BPMN pipeline.

Output ONE minified JSON object with these EXACT four keys:
  branch      — one of "fast" | "thorough" | "skip"
  nextTool    — the NSID of the tool to invoke, or "" (empty) for skip
  confidence  — 0.1 to 1.0 (NEVER output 0.0; if truly uncertain, pick 0.3)
  reason      — a non-empty English sentence, <=200 chars, naming the signal

BRANCH SEMANTICS:
  fast      — cheap per-row primitive enough. Row already has a vertex_id
              + recent probed_at (<7d), or a trivial single-field enrichment.
              nextTool: "generic.db.insert" or "com.etzhayyim.apps.dns.resolve".
  thorough  — full multi-step enrichment actor. Examples: phishing domain
              with unknown TLS + unknown ASN, unseen legal entity needing
              GLEIF + registrar + jurisdiction lookup.
              nextTool: "com.etzhayyim.apps.yabai.trackPhishingInfra" or
              "com.etzhayyim.apps.yabai.enrichLegalEntity".
  skip      — stale, duplicate, out-of-scope, or cost exceeds signal.
              nextTool MUST be "".

HARD RULES (violating these breaks downstream SQL):
  - confidence is a NUMBER between 0.1 and 1.0 (not a string, never 0).
  - reason is a NON-EMPTY string naming a concrete signal from the context
    (e.g. "TLS missing + unknown ASN", "LEI absent", "fresh crt.sh entry").
  - If context is thin and hint is empty: branch="fast", confidence=0.3,
    reason="minimal signal — default fast path".
  - Output ONLY the JSON object. No preamble, no explanation, no code fences.
"""


def _classify_task(state: PlanState) -> PlanState:
    """Single LLM call. Fails safe to branch=fast, confidence=0, so a
    bad LLM response doesn't block the whole BPMN."""
    ctx = state.get("context") or {}
    hint = state.get("taskHint") or ""
    user = (
        f"Task hint: {hint}\n"
        f"Context (JSON): {json.dumps(ctx, ensure_ascii=False)[:1500]}\n"
        "Decide the branch."
    )
    started = time.monotonic()
    result = llm.call_tier_json(
        "classifier",
        system=_CLASSIFY_SYSTEM,
        user=user,
        max_tokens=200,
        temperature=0.1,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    if not result.get("ok"):
        return {
            **state,
            "branch": "fast",
            "nextTool": "",
            "confidence": 0.0,
            "reason": f"llm-error:{str(result.get('error') or '')[:100]}",
            "planLatencyMs": latency_ms,
            "llmModel": str(result.get("model") or ""),
        }
    data = result.get("data") or {}
    branch = str(data.get("branch") or "fast").lower()
    if branch not in ("fast", "thorough", "skip"):
        branch = "fast"
    try:
        conf = float(data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(conf, 1.0))
    return {
        **state,
        "branch": branch,
        "nextTool": str(data.get("nextTool") or ""),
        "confidence": conf,
        "reason": str(data.get("reason") or "")[:200],
        "planLatencyMs": latency_ms,
        "llmModel": str(result.get("model") or ""),
    }


def _summarise_plan(state: PlanState) -> PlanState:
    """Identity pass — in this minimal agent the classifier already produces
    a flat output, but the slot is reserved so later revisions can add a
    second LLM call (e.g. cost estimate) without changing the graph."""
    return state


def _audit_plan(state: PlanState) -> PlanState:
    """Append one vertex_repo_commit row to the kotoba Datom log so the
    planning decision is auditable alongside the BPMN flow. Mirrors
    `generic.audit.emit`."""
    ts_ms = int(time.time() * 1000)
    rkey = f"plan-{ts_ms}"
    vertex_id = f"did:web:langgraph.etzhayyim.com:com.etzhayyim.agent.plan:{rkey}:create"
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    payload = {
        "branch": state.get("branch"),
        "nextTool": state.get("nextTool"),
        "confidence": state.get("confidence"),
        "reason": state.get("reason"),
        "threadId": state.get("threadId"),
        "llmModel": state.get("llmModel"),
        "planLatencyMs": state.get("planLatencyMs"),
    }
    row_dict = {
        "vertex_id": vertex_id,
        "seq": ts_ms,
        "repo": "did:web:langgraph.etzhayyim.com",
        "collection": "com.etzhayyim.agent.plan",
        "rkey": rkey,
        "action": "create",
        "rev": "",
        "cid": "",
        "prev": "",
        "sig": "",
        "value_json": json.dumps(payload, ensure_ascii=False),
        "ts_ms": ts_ms,
        "created_at": created_at,
    }
    try:
        get_kotoba_client().insert_row("vertex_repo_commit", row_dict)
        return {**state, "auditRkey": rkey}
    except Exception as e:  # noqa: BLE001
        log.warning("plan audit emit failed: %s", e)
        return {**state, "auditRkey": ""}


# ─── Graph ──────────────────────────────────────────────────────────────

def _build_graph() -> Any:
    g = StateGraph(PlanState)
    g.add_node("classify_task", _classify_task)
    g.add_node("summarise_plan", _summarise_plan)
    g.add_node("audit_plan", _audit_plan)
    g.add_edge(START, "classify_task")
    g.add_edge("classify_task", "summarise_plan")
    g.add_edge("summarise_plan", "audit_plan")
    g.add_edge("audit_plan", END)
    return g.compile()


plan_graph = _build_graph()


# ─── LangServer task wrapper ───────────────────────────────────────────────


async def task_agent_plan(context: dict | None = None, taskHint: str = "",
                          threadId: str = "", budgetMs: int = 5000) -> dict:
    """Entry point registered as `com.etzhayyim.agent.plan` in
    kotodama.zeebe_worker_main. The BPMN caller passes `context` (as a
    FEEL context literal → dict), optional `taskHint`, and a `threadId`
    (business key or instance key). Returns the flat state dict.
    """
    initial: PlanState = {
        "context": context or {},
        "taskHint": taskHint or "",
        "threadId": threadId or "",
        "budgetMs": int(budgetMs) if budgetMs else 5000,
    }
    try:
        final = await plan_graph.ainvoke(initial)
    except Exception as e:  # noqa: BLE001
        # Safety net — if the graph itself explodes, return a fast-branch
        # fallback so the BPMN flow keeps moving.
        return {
            "branch": "fast",
            "nextTool": "",
            "confidence": 0.0,
            "reason": f"graph-error:{type(e).__name__}:{str(e)[:100]}",
            "planLatencyMs": 0,
            "auditRkey": "",
        }
    return {
        "branch": final.get("branch") or "fast",
        "nextTool": final.get("nextTool") or "",
        "confidence": float(final.get("confidence") or 0.0),
        "reason": final.get("reason") or "",
        "planLatencyMs": int(final.get("planLatencyMs") or 0),
        "llmModel": final.get("llmModel") or "",
        "auditRkey": final.get("auditRkey") or "",
    }
