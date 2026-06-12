"""Projector L7 primitives — LangGraph + LangChain integration for the
yoro `/projects` agent loop, Tree-of-Thoughts, Self-Consistency, and
Reflexion. ADR-2604271600.

Each task type maps 1:1 to a BPMN service task in
`00-contracts/bpmn/com/etzhayyim/projector/*.bpmn`. The BPMN layer is the
orchestration boundary (XOR routing, OCEL audit, retry, guardrail
errors); the LangGraph StateGraph inside each primitive is the
*reasoning* boundary (CoT injection, tool dispatch, branch evaluation,
majority vote).

Camunda 8.9 agentic-pattern alignment:
  - `projector.agent.loop`           = AI Agent connector + ad-hoc tools
  - `projector.tot.expand`           = ToT branch graph
  - `projector.sc.parallel`          = SC parallel sample + vote
  - `projector.reflexion.{load,write}` = episodic memory R/W
  - `projector.tools.discover`       = MCP discovery (graph SQL)
  - `projector.command.{parse,deferred}` = slash-command router glue
  - `projector.persist.message`      = Hyperdrive INSERT vertex_projector_message
                                        + OCEL flow.completed

LLM transport: `kotodama.llm.call_tier` (already wires Vultr Serverless
+ RunPod fallback per ADR-2604231328). LangChain `ChatOpenAI` is
intentionally NOT used at the call site — adding `langchain-openai` would
double the worker image; instead we wrap `call_tier` as a LangChain
`Runnable` so LangGraph nodes can compose with LangChain tool / message
abstractions without the heavy SDK.

Output format follows the existing LangServer convention: every coroutine
returns a flat JSON-serialisable dict that BPMN ioMapping can splice
into process variables. `single_value=False` registration in `register()`.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import datetime as _dt
import json
import os
import re
import time
import uuid
from collections import Counter
from typing import Any, TypedDict

from kotodama import llm

# Phase 3 PDS write path. Reuses the cached _mint_pds_service_auth +
# generic.pds.dispatch primitives wired in zeebe_worker_main; we import
# them lazily so the import-time cost only applies when PROJECTOR_PERSIST_VIA_PDS
# (or projector.auth.mint) is actually exercised.

# LangGraph is already a dep (see py/pyproject.toml). LangChain core
# arrives transitively via langgraph >=0.2 — we only touch
# `langchain_core.messages` for typed system/human/ai message envelopes.
try:
    from langgraph.graph import END, StateGraph  # type: ignore
    _LANGGRAPH_OK = True
except ImportError:
    _LANGGRAPH_OK = False
    StateGraph = object  # type: ignore[assignment]
    END = "END"  # type: ignore[assignment]

# ──────────────────────────────────────────────────────────────────────
# Common helpers
# ──────────────────────────────────────────────────────────────────────

DEFAULT_REPO_PROJECTOR = "did:web:ops.etzhayyim.com"
COLLECTION_MESSAGE = "com.etzhayyim.convo.message"
COLLECTION_REFLECTION = "com.etzhayyim.projector.reflection"

_TOOL_CALL_RE = re.compile(
    r"\[TOOL_CALL:\s*([a-zA-Z0-9_.-]+)\s*\((\{[^\}]*\}|\s*)\)\s*\]",
    re.DOTALL,
)
_REASONING_RE = re.compile(r"<reasoning>(.+?)</reasoning>", re.DOTALL)
_FINAL_ANSWER_RE = re.compile(r"<answer>(.+?)</answer>", re.DOTALL)


def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_rkey(prefix: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _strip_reasoning(text: str) -> tuple[str, str]:
    """Pull <reasoning>…</reasoning> out of an LLM response. Returns
    (reasoning, cleaned_reply). If no tag is present, reasoning="" and
    cleaned_reply=text."""
    m = _REASONING_RE.search(text or "")
    if not m:
        return "", (text or "").strip()
    reasoning = m.group(1).strip()
    cleaned = _REASONING_RE.sub("", text or "").strip()
    return reasoning, cleaned


def _extract_final_answer(text: str) -> str:
    m = _FINAL_ANSWER_RE.search(text or "")
    if m:
        return m.group(1).strip()
    return (text or "").strip()


# ──────────────────────────────────────────────────────────────────────
# slash-command parser + deferred shim
# ──────────────────────────────────────────────────────────────────────

_KNOWN_COMMANDS = {"/explore", "/consistent", "/reflect", "/image", "/think"}


def task_projector_command_parse(text: str = "") -> dict[str, Any]:
    """Pull the leading slash command (if any) out of `text`. Returns
    {command, argText} where command is "" for the default agent path."""
    body = (text or "").lstrip()
    if not body or not body.startswith("/"):
        return {"command": "", "argText": body}
    head, _, rest = body.partition(" ")
    head = head.strip()
    if head not in _KNOWN_COMMANDS:
        return {"command": "", "argText": body}
    return {"command": head, "argText": rest.strip()}


def task_projector_command_deferred(command: str = "") -> dict[str, Any]:
    """Reply shim for /image and /think while CF Worker keeps owning
    those slash commands (Phase 3 cuts them over)."""
    return {
        "reply": (
            f"`{command}` is currently handled by the CF Worker direct path. "
            "BPMN handoff for this command lands in Phase 3."
        ),
        "deferred": True,
    }


# ──────────────────────────────────────────────────────────────────────
# Reflexion (Shinn et al. 2023) — episodic memory R/W
# ──────────────────────────────────────────────────────────────────────


def _reflexion_table_exists() -> bool:
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'vertex_projector_reflection' LIMIT 1"
            )
            return (_res[0] if _res else None) is not None
    except Exception:
        return False


def task_projector_reflexion_load(
    convoId: str = "",
    callerDid: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    """Load the most recent reflexion lessons for this convo. Returns
    `memories` as a list of {lesson, attempt, outcome, ts} records that
    the agentLoop primitive can splice into the system prompt."""
    if not convoId:
        return {"memories": []}
    rows: list[dict[str, Any]] = []
    if not _reflexion_table_exists():
        return {"memories": []}
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "SELECT lesson, attempt, outcome, created_at "
                "FROM vertex_projector_reflection "
                "WHERE convo_id = %s "
                f"ORDER BY created_at DESC LIMIT {max(1, min(limit, 20))}",
                (convoId,),
            )
            cols = [d[0] for d in []] if [] else []
            for r in _res or []:
                d = dict(zip(cols, r))
                rows.append(
                    {
                        "lesson": str(d.get("lesson") or ""),
                        "attempt": str(d.get("attempt") or ""),
                        "outcome": str(d.get("outcome") or ""),
                        "ts": str(d.get("created_at") or ""),
                    }
                )
    except Exception:  # noqa: BLE001
        return {"memories": []}
    return {"memories": rows}


def task_projector_reflexion_write(
    convoId: str = "",
    callerDid: str = "",
    lessonText: str = "",
) -> dict[str, Any]:
    """Persist a `/reflect attempt | outcome | lesson` (or free-text)
    entry to the dedicated `vertex_projector_reflection` table."""
    if not convoId or not lessonText:
        return {"reply": "reflexion needs convoId and a lesson", "rkey": ""}

    parts = [p.strip() for p in lessonText.split("|", 2)]
    if len(parts) == 3:
        attempt, outcome, lesson = parts
    else:
        attempt, outcome, lesson = "", "", lessonText.strip()

    rkey = _new_rkey("refl")
    repo = callerDid or DEFAULT_REPO_PROJECTOR
    uri = f"at://{repo}/{COLLECTION_REFLECTION}/{rkey}"
    if not _reflexion_table_exists():
        return {
            "reply": "reflexion write failed: vertex_projector_reflection missing",
            "rkey": rkey,
            "uri": uri,
            "error": "vertex_projector_reflection missing",
        }

    written_to = "vertex_projector_reflection"
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                INSERT INTO vertex_projector_reflection (
                  vertex_id, convo_id, caller_did, lesson, attempt, outcome,
                  created_at, sensitivity_ord, org_id, user_id, actor_id
                )
                SELECT
                  %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s
                WHERE NOT EXISTS (
                  SELECT 1 FROM vertex_projector_reflection WHERE vertex_id = %s
                )
                """,
                (
                    uri,
                    convoId,
                    repo,
                    lesson,
                    attempt,
                    outcome,
                    _now_iso(),
                    repo,
                    repo,
                    "sys.projector.reflexion",
                    uri,
                ),
            )
    except Exception as e:  # noqa: BLE001
        return {
            "reply": f"reflexion write failed: {e}",
            "rkey": rkey,
            "uri": uri,
            "error": str(e),
        }

    return {
        "reply": f"Reflexion stored ({written_to}). Future runs will see this lesson.",
        "rkey": rkey,
        "uri": uri,
        "writtenTo": written_to,
    }


# ──────────────────────────────────────────────────────────────────────
# Tool discovery + dispatcher (PM built-in tools)
# ──────────────────────────────────────────────────────────────────────


_PM_BUILTIN_TOOLS: list[dict[str, Any]] = [
    {
        "name": "pm.search_agents",
        "description": "Find AI agents on the platform by topic / keyword.",
        "schema": {"query": "string"},
    },
    {
        "name": "pm.invite_agent",
        "description": "Invite an agent (by DID) to this project as a member.",
        "schema": {"did": "string"},
    },
    {
        "name": "pm.web_research",
        "description": "Fetch a URL via site.etzhayyim.com and return Markdown.",
        "schema": {"url": "string", "topic": "string"},
    },
    {
        "name": "pm.create_entity_did",
        "description": "Create a path-based DID for a discovered entity.",
        "schema": {
            "path": "string",
            "displayName": "string",
            "description": "string",
            "category": "string",
        },
    },
    {
        "name": "pm.graph_search",
        "description": "Search the knowledge graph (avoids duplicate DIDs).",
        "schema": {"query": "string"},
    },
]


def task_projector_tools_discover(convoId: str = "") -> dict[str, Any]:
    """Return the union of (PM built-in tools, member actor tools).
    Member tools are resolved by joining vertex_convo_member → vertex_actor
    → vertex_actor_card.tools_json. Falls back to PM-only if the join
    fails or the convo has no members."""
    tools: list[dict[str, Any]] = list(_PM_BUILTIN_TOOLS)
    if not convoId:
        return {"tools": tools}
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "SELECT card.tools_json "
                "FROM vertex_convo_member m "
                "LEFT JOIN vertex_actor_card card ON card.actor_did = m.member_did "
                "WHERE m.convo_id = %s AND card.tools_json IS NOT NULL "
                "LIMIT 50",
                (convoId,),
            )
            for (tools_json,) in _res or []:
                if not tools_json:
                    continue
                try:
                    parsed = json.loads(tools_json)
                except (TypeError, ValueError):
                    continue
                if not isinstance(parsed, list):
                    continue
                for t in parsed:
                    if isinstance(t, dict) and t.get("name"):
                        tools.append(
                            {
                                "name": str(t["name"]),
                                "description": str(t.get("description") or ""),
                                "schema": t.get("schema") or {},
                                "memberDid": None,
                            }
                        )
    except Exception:  # noqa: BLE001
        # vertex_actor_card / vertex_convo_member may not exist on this
        # cluster yet; fall back to PM-only tools rather than failing
        # the whole flow.
        pass
    return {"tools": tools}


def _format_tools_for_prompt(tools: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for t in tools:
        schema = t.get("schema") or {}
        try:
            schema_str = json.dumps(schema, ensure_ascii=False)
        except (TypeError, ValueError):
            schema_str = "{}"
        out.append(
            f'- {t["name"]}: {t.get("description", "")} ARGS={schema_str}'
        )
    return "\n".join(out) if out else "(none)"


def _parse_tool_calls(text: str) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    for m in _TOOL_CALL_RE.finditer(text or ""):
        name = m.group(1)
        raw = m.group(2).strip() or "{}"
        try:
            args = json.loads(raw)
            if not isinstance(args, dict):
                args = {}
        except (TypeError, ValueError):
            args = {}
        calls.append((name, args))
    return calls


async def _exec_pm_tool(
    name: str, args: dict[str, Any], *, convoId: str, callerDid: str
) -> dict[str, Any]:
    """Dispatch a PM built-in tool. Implementation stays minimal here —
    the existing CF Worker handler holds the full PDS / cross-actor
    integration. For Phase 1+2 we wire just enough so the LangGraph
    runner can iterate against real DB state without fanning out to
    PDS XRPC (which would re-introduce the 401 path documented in
    ADR-2604240946)."""
    if name == "pm.graph_search":
        q = str(args.get("query") or "").strip()
        if not q:
            return {"hits": [], "note": "empty query"}
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "SELECT vertex_id, display_name "
                    "FROM vertex_actor "
                    "WHERE display_name ILIKE %s "
                    "LIMIT 10",
                    (f"%{q}%",),
                )
                rows = [
                    {"vertexId": r[0], "displayName": r[1]}
                    for r in _res or []
                ]
            return {"hits": rows}
        except Exception as e:  # noqa: BLE001
            return {"hits": [], "error": str(e)}

    if name == "pm.search_agents":
        q = str(args.get("query") or "").strip()
        if not q:
            return {"agents": []}
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    "SELECT vertex_id, display_name, description "
                    "FROM vertex_actor "
                    "WHERE (display_name ILIKE %s OR description ILIKE %s) "
                    "AND vertex_id LIKE 'at://did:web:%%' "
                    "LIMIT 10",
                    (f"%{q}%", f"%{q}%"),
                )
                rows = [
                    {
                        "did": r[0].split("/")[-1] if r[0] else "",
                        "vertexId": r[0],
                        "displayName": r[1],
                        "description": r[2],
                    }
                    for r in _res or []
                ]
            return {"agents": rows}
        except Exception as e:  # noqa: BLE001
            return {"agents": [], "error": str(e)}

    # The remaining PM tools touch PDS XRPC / external HTTP and need a
    # signed Service Auth path (ADR-0023). Phase 3 wires those — for now
    # we return a typed deferral so the LangGraph node can fold the
    # response back into the conversation transparently.
    return {
        "deferred": True,
        "tool": name,
        "args": args,
        "note": "PDS-bound PM tools land in Phase 3 (Service Auth ES256 + dispatcher pod).",
    }


async def task_projector_tool_call(
    name: str = "",
    args: dict | None = None,
    convoId: str = "",
    callerDid: str = "",
) -> dict[str, Any]:
    """BPMN-callable tool dispatch. Same surface as the LangGraph inner
    dispatcher; surfaced as its own task type so non-agent BPMN flows
    (admin tools, batch jobs) can invoke individual PM tools."""
    if not name:
        return {"ok": False, "error": "tool name required"}
    out = await _exec_pm_tool(name, args or {}, convoId=convoId, callerDid=callerDid)
    return {"ok": "error" not in out, "result": out, "tool": name}


# ──────────────────────────────────────────────────────────────────────
# LangGraph state graphs
# ──────────────────────────────────────────────────────────────────────


class _AgentState(TypedDict, total=False):
    convoId: str
    callerDid: str
    userText: str
    reflexionMemory: list[dict[str, Any]]
    historyRows: list[dict[str, Any]]
    memberTools: list[dict[str, Any]]
    tier: str
    maxIterations: int
    messages: list[dict[str, str]]  # OpenAI-shape chat history
    toolsCalled: list[dict[str, Any]]
    iterations: int
    reasoning: str
    reply: str
    done: bool
    guardrail: dict[str, Any]


def _build_system_prompt(state: _AgentState) -> str:
    memory = state.get("reflexionMemory") or []
    tools = state.get("memberTools") or []
    parts = [
        "You are the project-manager agent for a yoro /projects conversation.",
        "Use Chain-of-Thought reasoning: emit your reasoning inside",
        "<reasoning>...</reasoning> tags BEFORE the final answer.",
        "When you need a tool, emit exactly: [TOOL_CALL: name({json args})].",
        "Only emit one tool call per turn. Wait for the observation",
        "before the next call. End with <answer>final reply</answer>.",
        "",
        "Available tools:",
        _format_tools_for_prompt(tools),
    ]
    if memory:
        parts.extend(["", "Past lessons (Reflexion):"])
        for m in memory[-5:]:
            lesson = m.get("lesson") or ""
            if lesson:
                parts.append(f"- {lesson}")
    return "\n".join(parts)


def _guardrail_check(text: str) -> dict[str, Any]:
    """Camunda agentic pattern #4 — block obvious policy violations
    *before* they become tool calls. Conservative allow-list keeps the
    surface tiny; richer DMN rules land in Phase 5."""
    lowered = (text or "").lower()
    for needle in ("rm -rf", "drop table", "shutdown -h", "delete from vertex_"):
        if needle in lowered:
            return {"ok": False, "reason": f"policy_block: {needle}"}
    return {"ok": True}


async def _agent_reason_node(state: _AgentState) -> _AgentState:
    """One LLM turn. Builds messages, calls Murakumo, captures reasoning
    + tool calls + final answer."""
    messages = state.get("messages") or []
    if not messages:
        sys_prompt = _build_system_prompt(state)
        history = [
            f"[history] {(r.get('value_json') or '')[:200]}"
            for r in (state.get("historyRows") or [])[:10]
        ]
        user_block = (state.get("userText") or "").strip()
        if history:
            user_block = "Recent context:\n" + "\n".join(history) + "\n\n" + user_block
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_block},
        ]

    user_for_llm = "\n\n".join(
        m["content"] for m in messages if m["role"] in ("user", "assistant", "tool")
    )

    try:
        resp = llm.call_tier(
            state.get("tier") or "fast",
            system=messages[0]["content"],
            user=user_for_llm,
            max_tokens=900,
            temperature=0.3,
        )
    except llm.LlmError as e:
        return {
            **state,
            "messages": messages,
            "reply": f"(agent error: {e})",
            "done": True,
        }

    raw = (resp.get("content") or "").strip()
    reasoning, cleaned = _strip_reasoning(raw)
    final = _extract_final_answer(cleaned)
    tool_calls = _parse_tool_calls(cleaned)

    new_messages = list(messages) + [{"role": "assistant", "content": raw}]
    new_state: _AgentState = {
        **state,
        "messages": new_messages,
        "reasoning": (state.get("reasoning") or "") + ("\n" + reasoning if reasoning else ""),
        "iterations": int(state.get("iterations") or 0) + 1,
    }

    if tool_calls:
        # Surface only the first tool call this turn (the system prompt
        # constrains the LLM to one); leave any extras for the next loop.
        first = tool_calls[0]
        new_state["__pending_tool"] = {"name": first[0], "args": first[1]}  # type: ignore[typeddict-unknown-key]
        new_state["done"] = False
        return new_state

    new_state["reply"] = final or cleaned
    new_state["done"] = True
    return new_state


async def _agent_guardrail_node(state: _AgentState) -> _AgentState:
    pending = state.get("__pending_tool")  # type: ignore[typeddict-item]
    if not pending:
        return state
    name = (pending or {}).get("name") or ""
    args = (pending or {}).get("args") or {}
    g = _guardrail_check(json.dumps({"name": name, "args": args}, ensure_ascii=False))
    if not g.get("ok"):
        return {
            **state,
            "guardrail": g,
            "reply": f"(blocked: {g.get('reason')})",
            "done": True,
        }
    return state


async def _agent_dispatch_node(state: _AgentState) -> _AgentState:
    pending = state.get("__pending_tool")  # type: ignore[typeddict-item]
    if not pending:
        return state
    name = pending.get("name") or ""
    args = pending.get("args") or {}
    result = await _exec_pm_tool(
        name, args, convoId=state.get("convoId") or "", callerDid=state.get("callerDid") or ""
    )
    obs = json.dumps({"tool": name, "args": args, "result": result}, ensure_ascii=False)
    new_messages = list(state.get("messages") or []) + [
        {"role": "tool", "content": obs[:2000]}
    ]
    tools_called = list(state.get("toolsCalled") or []) + [
        {"name": name, "args": args, "result": result}
    ]
    return {
        **state,
        "messages": new_messages,
        "toolsCalled": tools_called,
        "__pending_tool": None,  # type: ignore[typeddict-unknown-key]
    }


def _agent_route(state: _AgentState) -> str:
    if state.get("done"):
        return "end"
    if state.get("__pending_tool"):  # type: ignore[typeddict-item]
        return "guardrail"
    if int(state.get("iterations") or 0) >= int(state.get("maxIterations") or 6):
        return "end"
    return "reason"


def _build_agent_graph():
    if not _LANGGRAPH_OK:
        return None
    g = StateGraph(_AgentState)
    g.add_node("reason", _agent_reason_node)
    g.add_node("guardrail", _agent_guardrail_node)
    g.add_node("dispatch", _agent_dispatch_node)
    g.set_entry_point("reason")
    g.add_conditional_edges(
        "reason",
        _agent_route,
        {"guardrail": "guardrail", "reason": "reason", "end": END},
    )
    g.add_conditional_edges(
        "guardrail",
        lambda s: "end" if s.get("done") else "dispatch",
        {"dispatch": "dispatch", "end": END},
    )
    g.add_edge("dispatch", "reason")
    return g.compile()


_AGENT_GRAPH = _build_agent_graph()


async def task_projector_agent_loop(
    convoId: str = "",
    callerDid: str = "",
    userText: str = "",
    reflexionMemory: list | None = None,
    historyRows: list | None = None,
    memberTools: list | None = None,
    tier: str = "fast",
    maxIterations: int = 6,
) -> dict[str, Any]:
    """Run the LangGraph ReAct loop. Output keys map to BPMN ioMapping
    in agentLoop.bpmn (`reply`, `reasoning`, `toolsCalled`, `iterations`)."""
    if not userText:
        return {
            "reply": "(empty user text)",
            "reasoning": "",
            "toolsCalled": [],
            "iterations": 0,
        }
    if _AGENT_GRAPH is None:
        # Fallback: single-turn LLM call when LangGraph isn't installed
        # (e.g. CI with stripped-down deps). Keeps the BPMN flow alive
        # rather than throwing a Zeebe job error.
        try:
            resp = llm.call_tier(
                tier,
                system=_build_system_prompt(
                    {
                        "memberTools": memberTools or [],
                        "reflexionMemory": reflexionMemory or [],
                    }
                ),
                user=userText,
                max_tokens=600,
                temperature=0.3,
            )
        except llm.LlmError as e:
            return {
                "reply": f"(agent error: {e})",
                "reasoning": "",
                "toolsCalled": [],
                "iterations": 0,
            }
        reasoning, cleaned = _strip_reasoning(resp.get("content") or "")
        return {
            "reply": _extract_final_answer(cleaned),
            "reasoning": reasoning,
            "toolsCalled": [],
            "iterations": 1,
        }

    initial: _AgentState = {
        "convoId": convoId,
        "callerDid": callerDid,
        "userText": userText,
        "reflexionMemory": list(reflexionMemory or []),
        "historyRows": list(historyRows or []),
        "memberTools": list(memberTools or []),
        "tier": tier,
        "maxIterations": int(maxIterations or 6),
        "messages": [],
        "toolsCalled": [],
        "iterations": 0,
        "reasoning": "",
        "reply": "",
        "done": False,
    }
    final = await _AGENT_GRAPH.ainvoke(initial)
    if final.get("guardrail") and not final.get("guardrail", {}).get("ok"):
        # Surface as a BPMN error so the boundary event in agentLoop.bpmn
        # routes the run to EndDenied with `agent.guardrail.denied` OCEL.
        raise RuntimeError(
            f"agent.guardrail.denied:{final['guardrail'].get('reason', '')}"
        )
    return {
        "reply": str(final.get("reply") or ""),
        "reasoning": str(final.get("reasoning") or "").strip(),
        "toolsCalled": final.get("toolsCalled") or [],
        "iterations": int(final.get("iterations") or 0),
    }


# ──────────────────────────────────────────────────────────────────────
# Tree of Thoughts (Yao et al. 2023)
# ──────────────────────────────────────────────────────────────────────


class _ToTState(TypedDict, total=False):
    question: str
    branchCount: int
    tier: str
    approaches: list[str]
    scores: list[int]
    bestIndex: int
    reply: str


_TOT_EXPAND_SYSTEM = (
    "You are exploring multiple approaches to answer a question. "
    "Output ONE JSON object with shape {\"approaches\":[\"…\",…]}. "
    "Generate exactly N distinct approaches (different angles, not "
    "rewordings). No preamble, no commentary, no code fences."
)

_TOT_EVAL_SYSTEM = (
    "You are evaluating candidate approaches to a question. For each "
    "approach output its score 0..10 (10=clearly best). Output ONE JSON "
    "object {\"scores\":[<int>,…]} same length as input. "
    "No preamble, no commentary, no code fences."
)

_TOT_FINAL_SYSTEM = (
    "Given a question and the chosen best approach, write a concise "
    "final reply (<= 600 chars). No preamble."
)


async def _tot_expand(question: str, n: int, tier: str) -> list[str]:
    user = f"Question:\n{question}\n\nN: {n}"
    out = llm.call_tier_json(
        tier, system=_TOT_EXPAND_SYSTEM, user=user, max_tokens=600, temperature=0.7
    )
    if not out.get("ok"):
        return []
    raw = out.get("data") or {}
    arr = raw.get("approaches") if isinstance(raw, dict) else None
    if not isinstance(arr, list):
        return []
    return [str(x).strip() for x in arr if str(x).strip()][:n]


async def _tot_evaluate(question: str, approaches: list[str], tier: str) -> list[int]:
    if not approaches:
        return []
    enumerated = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(approaches))
    user = f"Question:\n{question}\n\nApproaches:\n{enumerated}"
    out = llm.call_tier_json(
        tier, system=_TOT_EVAL_SYSTEM, user=user, max_tokens=300, temperature=0.1
    )
    if not out.get("ok"):
        return [5] * len(approaches)
    raw = out.get("data") or {}
    arr = raw.get("scores") if isinstance(raw, dict) else None
    if not isinstance(arr, list) or len(arr) != len(approaches):
        return [5] * len(approaches)
    cleaned: list[int] = []
    for x in arr:
        try:
            cleaned.append(max(0, min(10, int(x))))
        except (TypeError, ValueError):
            cleaned.append(5)
    return cleaned


async def _tot_finalize(question: str, best: str, tier: str) -> str:
    if not best:
        return "(no candidate approach)"
    try:
        resp = llm.call_tier(
            tier,
            system=_TOT_FINAL_SYSTEM,
            user=f"Question:\n{question}\n\nBest approach:\n{best}",
            max_tokens=400,
            temperature=0.3,
        )
        return (resp.get("content") or "").strip()
    except llm.LlmError as e:
        return f"(tot error: {e})"


async def task_projector_tot_expand(
    convoId: str = "",
    callerDid: str = "",
    question: str = "",
    branchCount: int = 4,
    tier: str = "classifier",
) -> dict[str, Any]:
    """Tree of Thoughts. Returns reply + approaches[] + scores[] +
    bestIndex; BPMN ioMapping splices everything back into vars."""
    n = max(2, min(int(branchCount or 4), 6))
    approaches = await _tot_expand(question, n, tier)
    scores = await _tot_evaluate(question, approaches, tier)
    best_idx = -1
    if scores:
        best_idx = int(max(range(len(scores)), key=lambda i: scores[i]))
    best = approaches[best_idx] if 0 <= best_idx < len(approaches) else ""
    reply = await _tot_finalize(question, best, tier)
    return {
        "reply": reply,
        "approaches": approaches,
        "scores": scores,
        "bestIndex": best_idx,
    }


# ──────────────────────────────────────────────────────────────────────
# Self-Consistency (Wang et al. 2022)
# ──────────────────────────────────────────────────────────────────────


_SC_SYSTEM = (
    "You answer the user's question. Use Chain-of-Thought reasoning "
    "inside <reasoning>...</reasoning>, then put the FINAL one-line "
    "answer inside <answer>…</answer>. Keep <answer> short (<=120 chars)."
)


async def _sc_one_path(question: str, tier: str, temperature: float) -> str:
    try:
        resp = llm.call_tier(
            tier,
            system=_SC_SYSTEM,
            user=question,
            max_tokens=500,
            temperature=temperature,
        )
    except llm.LlmError as e:
        return f"(error: {e})"
    raw = resp.get("content") or ""
    return _extract_final_answer(raw)


async def task_projector_sc_parallel(
    convoId: str = "",
    callerDid: str = "",
    question: str = "",
    pathCount: int = 5,
    temperature: float = 0.7,
    tier: str = "fast",
) -> dict[str, Any]:
    """Self-Consistency. Run N paths in parallel, take majority vote
    over their <answer> blocks."""
    n = max(3, min(int(pathCount or 5), 9))
    paths = await asyncio.gather(
        *[_sc_one_path(question, tier, float(temperature or 0.7)) for _ in range(n)]
    )
    norm = [p.strip().lower() for p in paths]
    tally = Counter(norm).most_common()
    if not tally:
        return {
            "reply": "(no paths produced an answer)",
            "answer": "",
            "paths": list(paths),
            "tally": [],
        }
    winner_norm, winner_count = tally[0]
    # Find the original-cased path matching the winning normalised form.
    winner = next((p for p, n_ in zip(paths, norm) if n_ == winner_norm), paths[0])
    reply = (
        f"{winner.strip()}\n\n"
        f"(self-consistency: {winner_count}/{n} paths agreed)"
    )
    return {
        "reply": reply,
        "answer": winner.strip(),
        "paths": list(paths),
        "tally": [{"answer": a, "count": c} for a, c in tally],
    }


# ──────────────────────────────────────────────────────────────────────
# Persist reply
# ──────────────────────────────────────────────────────────────────────


async def task_projector_persist_message(
    convoId: str = "",
    callerDid: str = "",
    reply: str = "",
    command: str = "",
) -> dict[str, Any]:
    """Append the projector reply to vertex_projector_message so yoro UI can
    fetch it via existing graph queries. Same shape as the live yoro
    social pulse path so we share the SSE / poll surface for free.

    Phase 3 toggle: when PROJECTOR_PERSIST_VIA_PDS=1, route the write
    through `generic.pds.dispatch` (HMAC-mint Service Auth + PDS XRPC)
    so the reply enters the AT firehose. Default = direct INSERT
    (Phase 1+2 behaviour, non-federable but graph-visible)."""
    if not convoId or not reply:
        return {"ok": False, "rkey": "", "uri": "", "error": "convoId+reply required"}

    repo = DEFAULT_REPO_PROJECTOR
    rkey = _new_rkey("proj")
    uri = f"at://{repo}/{COLLECTION_MESSAGE}/{rkey}"
    record = {
        "$type": COLLECTION_MESSAGE,
        "convoId": convoId,
        "text": reply,
        "createdAt": _now_iso(),
        "command": command or None,
        "agent": "projector-bpmn",
    }

    via_pds = os.environ.get("PROJECTOR_PERSIST_VIA_PDS", "").lower() in ("1", "true", "on", "yes")
    if via_pds:
        try:
            from kotodama.zeebe_worker_main import task_generic_pds_dispatch  # type: ignore
            out = await task_generic_pds_dispatch(
                type="com.atproto.repo.createRecord",
                payload={
                    "repo": repo,
                    "collection": COLLECTION_MESSAGE,
                    "rkey": rkey,
                    "record": record,
                },
                callerDid=callerDid or "",
            )
            if out.get("error"):
                # Fall through to direct INSERT so the reply is at least
                # graph-visible; surface the PDS error in the result so
                # the BPMN OCEL audit captures it.
                pds_err = str(out.get("error"))
            else:
                return {
                    "ok": True,
                    "rkey": rkey,
                    "uri": uri,
                    "viaPds": True,
                    "pdsStatus": out.get("status"),
                }
        except Exception as e:  # noqa: BLE001
            pds_err = f"pds dispatch raised: {e}"
    else:
        pds_err = ""

    value_json = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
    now = _now_iso()
    ts_ms = int(time.time() * 1000)
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                INSERT INTO vertex_projector_message (
                  vertex_id, uri, rkey, repo, convo_id, sender_did, role, text,
                  value_json, ts_ms, created_at, owner_did, actor_id, sensitivity_ord
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 2)
                ON CONFLICT (vertex_id) DO UPDATE SET
                  text = EXCLUDED.text,
                  value_json = EXCLUDED.value_json,
                  ts_ms = EXCLUDED.ts_ms
                """,
                (
                    uri,
                    uri,
                    rkey,
                    repo,
                    convoId,
                    callerDid or repo,
                    "assistant",
                    reply,
                    value_json,
                    ts_ms,
                    now,
                    repo,
                    "projector-bpmn",
                ),
            )
            _res = client.q(
                """
                INSERT INTO edge_projector_convo_message (
                  edge_id, convo_id, message_vid, relation_kind, ts_ms, created_at, owner_did, sensitivity_ord
                )
                VALUES (%s, %s, %s, 'contains_message', %s, %s, %s, 2)
                ON CONFLICT (edge_id) DO UPDATE SET
                  ts_ms = EXCLUDED.ts_ms
                """,
                (
                    f"edge:projector:convo-message:{convoId}:{rkey}",
                    convoId,
                    uri,
                    ts_ms,
                    now,
                    repo,
                ),
            )
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "rkey": rkey, "uri": uri, "error": str(e), "pdsError": pds_err}
    return {
        "ok": True,
        "rkey": rkey,
        "uri": uri,
        "viaPds": False,
        "pdsError": pds_err or None,
    }


# ──────────────────────────────────────────────────────────────────────
# Phase 3 — Service Auth JWT mint exposed as a BPMN task
# ──────────────────────────────────────────────────────────────────────


async def task_projector_auth_mint(lxm: str = "") -> dict[str, Any]:
    """Mint a 60s lxm-scoped Service Auth JWT (or whatever TTL the
    PDS_SERVICE_AUTH_MINT endpoint returns). Re-uses the existing
    `_mint_pds_service_auth` helper from `zeebe_worker_main` so we share
    the in-process cache (one mint per lxm per ~TTL).

    BPMN ioMapping splices `token` back as a process variable; downstream
    `generic.http.fetch` / `generic.pds.dispatch` tasks can use it as
    Authorization: Bearer for typed-write paths.
    """
    if not lxm:
        return {"ok": False, "error": "lxm required (e.g. com.etzhayyim.identity.create)"}
    try:
        from kotodama.zeebe_worker_main import _mint_pds_service_auth  # type: ignore
    except ImportError as e:
        return {"ok": False, "error": f"mint helper unavailable: {e}"}
    token = await asyncio.to_thread(_mint_pds_service_auth, lxm)
    if not token:
        return {
            "ok": False,
            "error": "mint returned empty token (PDS_SERVICE_AUTH_MINT_URL/SECRET not configured)",
        }
    return {"ok": True, "token": token, "lxm": lxm}


# ──────────────────────────────────────────────────────────────────────
# LangServer registration
# ──────────────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire all projector primitives onto the shared LangServer worker.
    Called from `kotodama.zeebe_worker_main:main()` alongside the
    other primitive `register(...)` calls."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    # router glue
    t("projector.command.parse", task_projector_command_parse)
    t("projector.command.deferred", task_projector_command_deferred)

    # reflexion
    t("projector.reflexion.load", task_projector_reflexion_load)
    t("projector.reflexion.write", task_projector_reflexion_write)

    # tools
    t("projector.tools.discover", task_projector_tools_discover)
    t("projector.tool.call", task_projector_tool_call)

    # reasoning
    t("projector.agent.loop", task_projector_agent_loop, timeout=max(timeout_ms, 90_000))
    t("projector.tot.expand", task_projector_tot_expand, timeout=max(timeout_ms, 120_000))
    t("projector.sc.parallel", task_projector_sc_parallel, timeout=max(timeout_ms, 120_000))

    # persist
    t("projector.persist.message", task_projector_persist_message)

    # Phase 3 — Service Auth JWT mint exposed as a BPMN task
    t("projector.auth.mint", task_projector_auth_mint)


__all__ = [
    "register",
    "task_projector_command_parse",
    "task_projector_command_deferred",
    "task_projector_reflexion_load",
    "task_projector_reflexion_write",
    "task_projector_tools_discover",
    "task_projector_tool_call",
    "task_projector_agent_loop",
    "task_projector_tot_expand",
    "task_projector_sc_parallel",
    "task_projector_persist_message",
    "task_projector_auth_mint",
]
