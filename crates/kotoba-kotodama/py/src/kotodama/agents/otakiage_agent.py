"""Conversational agent for otakiage.etzhayyim.com (Reuse & Ritual Platform).

Graph id: ``otakiage.agent.chat.v1``
Task type: ``otakiage.agent.chat`` (registered via ``primitives/otakiage.py``)

Architecture (ADR-2605072000 LangGraph Agent Loop Pattern):
  intra-job ≥3 LLM branches を満たす設計:

    START → parse_intent (LLM #1)
              ├─ intent=submit → extract_details (LLM #2)
              ├─ intent=search → search_candidates (DB)
              ├─ intent=ritual → resolve_matsuri (DB)
              ├─ intent=inquire → fetch_info (DB)
              └─ intent=chat   → (no action)
                  ↓
              compose_reply (LLM #3) → END

  parse_intent + extract_details + compose_reply で LLM call は最大 3 つ。
  intent != submit でも parse_intent + compose_reply の 2 LLM、
  並びに分岐先で生成的な処理 (e.g. search で候補をランクづけ) で
  3 つ目の LLM を入れる設計余地あり。Phase 2 では submit パスが
  3 LLM、他は 2 LLM (許容、ADR では submit を主経路と想定)。

State persistence: vertex_otakiage_conversation_turn に user_message +
agent_reply + intent + actions_json を append-only で保存。LangGraph
checkpoint は Phase 3 で BaseCheckpointSaver (RisingWave 実装、ADR-2605080600)
を導入予定。
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama import llm
from kotodama.primitives import langgraph_registry
from kotodama.primitives.otakiage import (
    CATEGORY_MODE,
    PATH_DID_MATSURI,
    PATH_DID_RITUAL,
    PATH_DID_ROOT,
    _category_to_mode,
    _content_addressed_rkey,
)


# ── Graph state ────────────────────────────────────────────────────────


class OtakiageChatState(TypedDict, total=False):
    # Inputs (from XRPC handler)
    threadId: str
    callerDid: str
    userMessage: str
    h3Cell: str
    intentHint: str
    maxTurns: int

    # Loaded context (from conversation history)
    history: list[dict[str, str]]  # [{"role":"user"|"assistant","content":...}]
    threadUri: str
    isNewThread: bool

    # parse_intent output
    intent: str  # submit | search | ritual | inquire | chat | unknown

    # extract_details output (submit intent)
    draftItem: dict[str, Any]

    # search_candidates output (search intent)
    candidates: list[dict[str, Any]]

    # resolve_matsuri output (ritual intent)
    matsuriOptions: list[dict[str, Any]]

    # fetch_info output (inquire intent)
    inquiryFacts: dict[str, Any]

    # compose_reply output
    reply: str

    # Bookkeeping
    actions: list[dict[str, Any]]
    llmCalls: int
    error: str


# ── Helpers ────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_isoformat() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _new_thread_id(caller_did: str) -> str:
    return _content_addressed_rkey(caller_did, str(time.time_ns()))[:16]


# Allowed categories for submit (Phase 1 scope: ADR-2605081700)
ALLOWED_CATEGORIES = list(CATEGORY_MODE.keys())


# ── Graph nodes ────────────────────────────────────────────────────────


async def _node_load_history(state: OtakiageChatState) -> OtakiageChatState:
    """Load conversation history from vertex_otakiage_conversation_turn.

    Pure DB read; not counted as an LLM call.
    """
    thread_id = state.get("threadId") or ""
    caller_did = state.get("callerDid") or ""
    if not caller_did:
        return {**state, "error": "callerDid required"}

    is_new = not thread_id
    if is_new:
        thread_id = _new_thread_id(caller_did)
    thread_uri = f"at://{caller_did}/com.etzhayyim.apps.otakiage.conversation/{thread_id}"

    history: list[dict[str, str]] = []
    if not is_new:
        max_turns = int(state.get("maxTurns") or 10)
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"SELECT user_message, agent_reply FROM vertex_otakiage_conversation_turn "
                f"WHERE thread_id = %s "
                f"ORDER BY turn_index DESC "
                f"LIMIT {int(max_turns)}",
                (thread_id,),
            )
            rows = list(_res or [])
        # Reverse so oldest first
        for um, ar in reversed(rows):
            if um:
                history.append({"role": "user", "content": um})
            if ar:
                history.append({"role": "assistant", "content": ar})

    return {
        **state,
        "threadId": thread_id,
        "threadUri": thread_uri,
        "isNewThread": is_new,
        "history": history,
        "actions": list(state.get("actions") or []),
        "llmCalls": int(state.get("llmCalls") or 0),
    }


async def _node_parse_intent(state: OtakiageChatState) -> OtakiageChatState:
    """LLM #1 — classify the user's intent.

    If `intentHint` is provided by the caller (UI button), trust it and
    skip the LLM call. This keeps the agent cheap for high-volume button
    flows while the conversational path still benefits from classification.
    """
    hint = (state.get("intentHint") or "").strip().lower()
    if hint in {"submit", "search", "ritual", "inquire", "chat"}:
        return {**state, "intent": hint}

    user_message = state.get("userMessage") or ""
    history = state.get("history") or []
    history_block = "\n".join(
        f"{h.get('role', '')}: {h.get('content', '')[:200]}" for h in history[-6:]
    ) or "(no prior turns)"

    system = (
        "あなたは otakiage (お焚き上げ + reuse) platform の intent classifier です。"
        "ユーザの直近メッセージを 5 つのいずれかに分類してください: "
        "submit (物品を登録/譲渡したい), "
        "search (近所の reuse 候補を探したい), "
        "ritual (お焚き上げ/供養を依頼したい), "
        "inquire (季節祭/証跡について質問), "
        "chat (一般会話・雑談)。"
        "JSON で {\"intent\":\"submit|search|ritual|inquire|chat\"} のみを返してください。"
    )
    user_prompt = (
        f"## 過去の会話\n{history_block}\n\n## 直近のユーザメッセージ\n{user_message}\n\n"
        f"## タスク\nintent を 1 つ選んで JSON で返答。"
    )
    try:
        result = llm.call_tier_json(
            tier="fast",
            system=system,
            user=user_prompt,
            max_tokens=80,
            temperature=0.0,
        )
        parsed = result.get("data") if isinstance(result, dict) else None
        intent = (parsed or {}).get("intent") if isinstance(parsed, dict) else None
        if intent not in {"submit", "search", "ritual", "inquire", "chat"}:
            intent = "chat"
    except Exception as e:
        # Fallback: keyword heuristic so the agent is robust to LLM errors.
        msg = user_message.lower()
        if any(k in msg for k in ("登録", "譲", "あげ", "submit", "regist")):
            intent = "submit"
        elif any(k in msg for k in ("探", "近く", "近所", "ほしい", "search", "find")):
            intent = "search"
        elif any(k in msg for k in ("お焚き", "供養", "焚き上げ", "ritual")):
            intent = "ritual"
        elif any(k in msg for k in ("祭", "matsuri", "証跡", "certificate")):
            intent = "inquire"
        else:
            intent = "chat"
        return {
            **state,
            "intent": intent,
            "llmCalls": int(state.get("llmCalls") or 0) + 1,
            "error": f"parse_intent fallback: {e}",
        }

    return {
        **state,
        "intent": intent,
        "llmCalls": int(state.get("llmCalls") or 0) + 1,
    }


async def _node_extract_details(state: OtakiageChatState) -> OtakiageChatState:
    """LLM #2 (submit path) — extract category/title/storyText from message."""
    user_message = state.get("userMessage") or ""
    history = state.get("history") or []
    history_block = "\n".join(
        f"{h.get('role', '')}: {h.get('content', '')[:200]}" for h in history[-6:]
    ) or "(no prior turns)"

    cats_csv = ", ".join(ALLOWED_CATEGORIES)
    system = (
        "あなたは otakiage の物品登録 assistant です。"
        f"ユーザの記述から物品 1 件分の draft を抽出してください。category は次のいずれか必須: {cats_csv}。"
        "weightKgClass は light (<5kg) / medium (5-20kg) / heavy (20-50kg) / bulky (>50kg) のいずれか。"
        "needsConfirmation: ユーザの記述があいまいで category 推定や title 抽出に自信がない場合は true。"
        "JSON で {\"category\":\"...\", \"title\":\"...\", \"storyText\":\"...\", \"weightKgClass\":\"...\", \"needsConfirmation\":bool} を返す。"
        "値が抽出できない場合は空文字 \"\" にする (null/省略禁止)。"
    )
    user_prompt = (
        f"## 過去の会話\n{history_block}\n\n## 直近のユーザメッセージ\n{user_message}\n\n"
        f"## タスク\n物品 draft を抽出して JSON で返答。"
    )
    try:
        result = llm.call_tier_json(
            tier="balanced",
            system=system,
            user=user_prompt,
            max_tokens=400,
            temperature=0.1,
        )
        parsed = result.get("data") if isinstance(result, dict) else {}
        if not isinstance(parsed, dict):
            parsed = {}
    except Exception as e:
        parsed = {"needsConfirmation": True}
        return {
            **state,
            "draftItem": parsed,
            "llmCalls": int(state.get("llmCalls") or 0) + 1,
            "error": f"extract_details failed: {e}",
        }

    category = str(parsed.get("category") or "").strip()
    if category and category not in ALLOWED_CATEGORIES:
        category = ""
    draft = {
        "category": category,
        "title": str(parsed.get("title") or "").strip(),
        "storyText": str(parsed.get("storyText") or "").strip(),
        "weightKgClass": str(parsed.get("weightKgClass") or "light").strip() or "light",
        "needsConfirmation": bool(parsed.get("needsConfirmation") or False),
    }
    if category:
        draft["modeHint"] = _category_to_mode(category)
    if not draft["category"] or not draft["title"]:
        draft["needsConfirmation"] = True

    return {
        **state,
        "draftItem": draft,
        "llmCalls": int(state.get("llmCalls") or 0) + 1,
    }


async def _node_search_candidates(state: OtakiageChatState) -> OtakiageChatState:
    """DB query — list nearby reuse_open items.

    No LLM call here. Phase 2.1 may add a re-rank LLM as a 3rd LLM call
    in the search path.
    """
    h3 = state.get("h3Cell") or ""
    candidates: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        if h3:
            # Phase 2: exact h3 match. Adjacent cells will be added when the
            # h3 library is wired into the worker pod.
            _res = client.q(
                "SELECT vertex_id, category, title, h3_cell "
                "FROM vertex_otakiage_item "
                "WHERE state = 'reuse_open' AND h3_cell = %s "
                "LIMIT 20",
                (h3,),
            )
        else:
            _res = client.q(
                "SELECT vertex_id, category, title, h3_cell "
                "FROM vertex_otakiage_item "
                "WHERE state = 'reuse_open' "
                "ORDER BY created_at DESC "
                "LIMIT 20"
            )
        rows = list(_res or [])
    for v_id, cat, title, h3c in rows:
        candidates.append({"uri": v_id, "category": cat, "title": title, "h3Cell": h3c or ""})
    return {**state, "candidates": candidates}


async def _node_resolve_matsuri(state: OtakiageChatState) -> OtakiageChatState:
    """DB query — list upcoming matsuri (next 90 days)."""
    options: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT vertex_id, name, scheduled_date, category_scope "
            "FROM vertex_otakiage_matsuri "
            "WHERE state IN ('open','preparing') AND scheduled_date >= CURRENT_DATE "
            "ORDER BY scheduled_date ASC LIMIT 10"
        )
        rows = list(_res or [])
    for v_id, name, sched, scope_json in rows:
        try:
            scope = json.loads(scope_json or "[]")
        except Exception:
            scope = []
        options.append({
            "uri": v_id,
            "name": name,
            "scheduledDate": sched.isoformat() if sched else "",
            "categoryScope": scope,
        })
    return {**state, "matsuriOptions": options}


async def _node_fetch_info(state: OtakiageChatState) -> OtakiageChatState:
    """DB query — fetch coverage stats for inquiry."""
    facts: dict[str, Any] = {}
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT state, SUM(item_count) FROM mv_otakiage_items_by_state GROUP BY state"
        )
        rows = list(_res or [])
        facts["byState"] = {str(s): int(c or 0) for s, c in rows}
        _res = client.q("SELECT COUNT(*) FROM vertex_otakiage_certificate")
        r = (_res[0] if _res else None)
        facts["certificateCount"] = int(r[0]) if r else 0
        _res = client.q(
            "SELECT COUNT(*) FROM vertex_otakiage_matsuri "
            "WHERE state IN ('open','preparing') AND scheduled_date >= CURRENT_DATE"
        )
        r = (_res[0] if _res else None)
        facts["upcomingMatsuriCount"] = int(r[0]) if r else 0
    return {**state, "inquiryFacts": facts}


async def _node_compose_reply(state: OtakiageChatState) -> OtakiageChatState:
    """LLM #3 — compose final natural-language reply.

    Always called regardless of intent branch, ensuring the path has at
    least 2 LLM calls for non-submit and 3 LLM calls for submit (which
    satisfies the ADR-2605072000 ≥3-LLM condition for the principal path).
    """
    intent = state.get("intent") or "chat"
    user_message = state.get("userMessage") or ""
    history = state.get("history") or []
    history_block = "\n".join(
        f"{h.get('role', '')}: {h.get('content', '')[:200]}" for h in history[-6:]
    ) or "(no prior turns)"

    # Build intent-specific context block
    ctx_lines: list[str] = []
    if intent == "submit":
        draft = state.get("draftItem") or {}
        ctx_lines.append(f"draft抽出結果: {json.dumps(draft, ensure_ascii=False)}")
        if draft.get("needsConfirmation"):
            ctx_lines.append("→ category または title が不明確。ユーザに確認質問を投げる。")
        else:
            ctx_lines.append("→ draft 完成。「この内容で登録してよいか」確認質問を投げる。")
    elif intent == "search":
        cands = state.get("candidates") or []
        if cands:
            sample = ", ".join(f"{c['category']}/{c['title'][:20]}" for c in cands[:5])
            ctx_lines.append(f"近隣候補 {len(cands)} 件: {sample}")
        else:
            ctx_lines.append("近隣候補は 0 件。少し範囲を広げてみる提案、または別カテゴリを尋ねる。")
    elif intent == "ritual":
        opts = state.get("matsuriOptions") or []
        if opts:
            sample = ", ".join(f"{o['name']}({o['scheduledDate']})" for o in opts[:3])
            ctx_lines.append(f"開催予定 matsuri {len(opts)} 件: {sample}")
        else:
            ctx_lines.append("開催予定 matsuri なし → 翌月の auto-seed を案内。")
    elif intent == "inquire":
        facts = state.get("inquiryFacts") or {}
        ctx_lines.append(f"現状: {json.dumps(facts, ensure_ascii=False)}")

    context_block = "\n".join(ctx_lines) or "(intent specific context なし)"

    system = (
        "あなたは otakiage (お焚き上げ + reuse) platform の対話 assistant 'kotodama' です。"
        "etzhayyim (宗教法人・任意団体・blockchain 登記) が運営する物の供養と再生のサービス。"
        "ユーザの想いに丁寧に寄り添い、敬語で簡潔に応答 (200 字以内)。"
        "感情の重みを尊重しつつ、必要な情報や次のステップを 1〜2 提案する。"
        "絵文字は ✨🙏♻️ 程度を控えめに使ってよい。"
        "決済や配送の話題は『現在は無償譲渡 + ローカル受け渡しのみ対応』と返す (Phase 1 制約)。"
    )
    user_prompt = (
        f"## 過去の会話\n{history_block}\n\n"
        f"## ユーザの直近メッセージ\n{user_message}\n\n"
        f"## 検出された intent\n{intent}\n\n"
        f"## 文脈情報\n{context_block}\n\n"
        f"## タスク\n上記に応じた自然な返信文 (200 字以内、敬語、emoji 控えめ) を生成。"
    )
    try:
        result = llm.call_tier(
            tier="balanced",
            system=system,
            user=user_prompt,
            max_tokens=400,
            temperature=0.5,
        )
        reply = (result.get("content") or "").strip()
    except Exception as e:
        reply = "申し訳ありません、ただいま応答処理に少し時間がかかっております。もう一度お試しください。 🙏"
        return {
            **state,
            "reply": reply,
            "llmCalls": int(state.get("llmCalls") or 0) + 1,
            "error": f"compose_reply failed: {e}",
        }

    if len(reply) > 280:
        reply = reply[:277] + "..."
    return {
        **state,
        "reply": reply,
        "llmCalls": int(state.get("llmCalls") or 0) + 1,
    }


async def _node_persist_turn(state: OtakiageChatState) -> OtakiageChatState:
    """Append-only persist of this turn into vertex_otakiage_conversation* tables."""
    thread_id = state.get("threadId") or ""
    thread_uri = state.get("threadUri") or ""
    caller_did = state.get("callerDid") or ""
    if not (thread_id and thread_uri and caller_did):
        return state

    user_message = state.get("userMessage") or ""
    reply = state.get("reply") or ""
    intent = state.get("intent") or "unknown"
    actions = state.get("actions") or []
    llm_calls = int(state.get("llmCalls") or 0)
    is_new = bool(state.get("isNewThread"))

    now = _now_iso()
    today = _today_isoformat()

    # Build action records for this turn
    if intent == "submit":
        draft = state.get("draftItem") or {}
        if draft and not draft.get("needsConfirmation"):
            actions.append({
                "kind": "item_drafted",
                "uri": "",
                "details": json.dumps(draft, ensure_ascii=False),
            })
    elif intent == "search":
        cands = state.get("candidates") or []
        actions.append({
            "kind": "reuse_candidates_listed",
            "uri": "",
            "details": json.dumps([c.get("uri") for c in cands[:10]], ensure_ascii=False),
        })
    elif intent == "ritual":
        opts = state.get("matsuriOptions") or []
        actions.append({
            "kind": "matsuri_listed",
            "uri": (opts[0].get("uri") if opts else ""),
            "details": json.dumps([o.get("uri") for o in opts[:5]], ensure_ascii=False),
        })
    elif intent == "inquire":
        actions.append({
            "kind": "certificate_explained",
            "uri": "",
            "details": json.dumps(state.get("inquiryFacts") or {}, ensure_ascii=False),
        })
    else:
        actions.append({"kind": "no_action", "uri": "", "details": ""})

    if True:

        client = get_kotoba_client()
        # Determine turn_index
        _res = client.q(
            "SELECT COALESCE(MAX(turn_index), -1) FROM vertex_otakiage_conversation_turn "
            "WHERE thread_id = %s",
            (thread_id,),
        )
        r = (_res[0] if _res else None)
        turn_index = (int(r[0]) if r and r[0] is not None else -1) + 1

        if is_new:
            _res = client.q(
                """
                INSERT INTO vertex_otakiage_conversation (
                  vertex_id, owner_did, thread_id, caller_did, title, turn_count,
                  last_intent, last_message_at, state,
                  created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
                ) VALUES (
                  %s, %s, %s, %s, %s, %s,
                  %s, %s, %s,
                  %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    thread_uri, caller_did, thread_id, caller_did,
                    (user_message[:60] + "...") if len(user_message) > 60 else user_message,
                    1, intent, now, "active",
                    now, today, 1, caller_did, caller_did, "otakiage.agent.chat",
                ),
            )
        else:
            _res = client.q(
                "UPDATE vertex_otakiage_conversation "
                "SET turn_count = turn_count + 1, last_intent = %s, last_message_at = %s "
                "WHERE thread_id = %s",
                (intent, now, thread_id),
            )

        turn_rkey = hashlib.sha256(
            f"{thread_id}|{turn_index}|{int(time.time_ns())}".encode("utf-8")
        ).hexdigest()[:24]
        turn_uri = f"at://{caller_did}/com.etzhayyim.apps.otakiage.conversationTurn/{turn_rkey}"
        _res = client.q(
            """
            INSERT INTO vertex_otakiage_conversation_turn (
              vertex_id, owner_did, turn_id, thread_id, thread_uri, caller_did, turn_index,
              user_message, agent_reply, intent, actions_json, llm_calls, latency_ms,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s
            )
            """,
            (
                turn_uri, caller_did, turn_rkey, thread_id, thread_uri, caller_did, turn_index,
                user_message, reply, intent, json.dumps(actions, ensure_ascii=False), llm_calls, 0,
                now, today, 1, caller_did, caller_did, "otakiage.agent.chat",
            ),
        )
    return {**state, "actions": actions}


# ── Conditional routing ────────────────────────────────────────────────


def _route_after_intent(state: OtakiageChatState) -> str:
    intent = state.get("intent") or "chat"
    return {
        "submit": "extract_details",
        "search": "search_candidates",
        "ritual": "resolve_matsuri",
        "inquire": "fetch_info",
        "chat": "compose_reply",
    }.get(intent, "compose_reply")


# ── Build & register ───────────────────────────────────────────────────


def _build_graph() -> Any:
    g = StateGraph(OtakiageChatState)
    g.add_node("load_history", _node_load_history)
    g.add_node("parse_intent", _node_parse_intent)
    g.add_node("extract_details", _node_extract_details)
    g.add_node("search_candidates", _node_search_candidates)
    g.add_node("resolve_matsuri", _node_resolve_matsuri)
    g.add_node("fetch_info", _node_fetch_info)
    g.add_node("compose_reply", _node_compose_reply)
    g.add_node("persist_turn", _node_persist_turn)

    g.add_edge(START, "load_history")
    g.add_edge("load_history", "parse_intent")
    g.add_conditional_edges(
        "parse_intent",
        _route_after_intent,
        {
            "extract_details": "extract_details",
            "search_candidates": "search_candidates",
            "resolve_matsuri": "resolve_matsuri",
            "fetch_info": "fetch_info",
            "compose_reply": "compose_reply",
        },
    )
    g.add_edge("extract_details", "compose_reply")
    g.add_edge("search_candidates", "compose_reply")
    g.add_edge("resolve_matsuri", "compose_reply")
    g.add_edge("fetch_info", "compose_reply")
    g.add_edge("compose_reply", "persist_turn")
    g.add_edge("persist_turn", END)
    return g.compile()


otakiage_chat_graph = _build_graph()
langgraph_registry.register("otakiage.agent.chat.v1", otakiage_chat_graph)


# Avoid unused import linter complaint (PATH_DID_RITUAL/_MATSURI/_ROOT may
# be referenced by future graph nodes for authority checks)
_ = (PATH_DID_RITUAL, PATH_DID_MATSURI, PATH_DID_ROOT)
