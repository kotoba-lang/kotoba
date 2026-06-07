"""tools.py — Python port of the daemon-side ReAct tool registry.

Subset of ADR-2605191129 (browser tools). Long-term memory tools
(remember / recall_long_term) intentionally absent — that's browser
IndexedDB territory; will be re-added once substrate-side MstCheckpointSaver
lands (ADR-2605171800).

Authoritative ADR: 90-docs/adr/2605191257-ameno-daemon-path-b-kotodama-python.md
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx


ChatMessage = dict[str, str]
ToolContext = dict[str, Any]  # at minimum: {"messages": list[ChatMessage]}


@dataclass
class ToolDef:
    name: str
    description: str
    arg_spec: str
    execute: Callable[[Any, ToolContext], Awaitable[str]]


def _trunc(s: str, n: int = 500) -> str:
    return s if len(s) <= n else s[:n] + "…"


async def _now_exec(_args: Any, _ctx: ToolContext) -> str:
    return datetime.now(timezone.utc).isoformat()


async def _recall_exec(args: Any, ctx: ToolContext) -> str:
    if not isinstance(args, dict):
        args = {}
    query = args.get("query") if isinstance(args.get("query"), str) else ""
    if not query:
        return "error: missing 'query' argument"
    history = [m for m in ctx.get("messages", [])[:-1] if isinstance(m, dict) and m.get("role") != "system"]
    if not history:
        return "no prior messages to search"

    def tok(s: str) -> set[str]:
        return set(re.findall(r"[\w]+", s.lower(), flags=re.UNICODE))

    q = tok(query)
    scored: list[tuple[float, dict[str, str], str]] = []
    for m in history:
        text = m.get("content", "") if isinstance(m.get("content"), str) else json.dumps(m.get("content"))
        t = tok(text)
        if not q and not t:
            continue
        inter = len(q & t)
        union = len(q | t)
        score = (inter / union) if union > 0 else 0.0
        scored.append((score, m, text))
    scored.sort(key=lambda x: x[0], reverse=True)
    lines = [
        f"[{i + 1}] ({m.get('role','?')}, jaccard={score:.3f}) {_trunc(text, 200)}"
        for i, (score, m, text) in enumerate(scored[:3])
    ]
    return "\n".join(lines) if lines else "no prior messages to search"


async def _wikipedia_exec(args: Any, _ctx: ToolContext) -> str:
    if not isinstance(args, dict):
        args = {}
    title = (args.get("title") or "").strip() if isinstance(args.get("title"), str) else ""
    if not title:
        return "error: missing 'title' argument"
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + title.replace(" ", "_")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers={"accept": "application/json"})
            if r.status_code != 200:
                return f"error: HTTP {r.status_code} fetching Wikipedia '{title}'"
            body = r.json()
    except Exception as e:
        return f"error: wikipedia fetch failed: {e}"
    extract = body.get("extract") if isinstance(body.get("extract"), str) else ""
    t = body.get("title") if isinstance(body.get("title"), str) else title
    if not extract:
        return f"no extract found for '{t}'"
    return f"{t}\n{_trunc(extract, 480)}"


TOOLS: dict[str, ToolDef] = {
    "now": ToolDef(
        name="now",
        description="Returns the current UTC time as ISO 8601.",
        arg_spec="{}",
        execute=_now_exec,
    ),
    "recall": ToolDef(
        name="recall",
        description=(
            "Lexical search over PRIOR messages in this thread. "
            "Returns up to 3 best matches by token overlap."
        ),
        arg_spec='{"query": string}',
        execute=_recall_exec,
    ),
    "wikipedia": ToolDef(
        name="wikipedia",
        description=(
            "Fetch a short Wikipedia summary by article title. "
            "English Wikipedia only. Use underscored or spaced titles."
        ),
        arg_spec='{"title": string}',
        execute=_wikipedia_exec,
    ),
}


# ── Parser ──────────────────────────────────────────────────────────────


@dataclass
class ParsedToolCall:
    raw: str
    name: str
    args: Any
    parse_error: str | None


_TOOL_TAG_RE = re.compile(r"<tool>\s*(\{[\s\S]*?\})\s*</tool>")


def parse_tool_calls(text: str) -> list[ParsedToolCall]:
    out: list[ParsedToolCall] = []
    for m in _TOOL_TAG_RE.finditer(text):
        raw = m.group(0)
        body = m.group(1)
        try:
            obj = json.loads(body)
            if not isinstance(obj, dict):
                out.append(ParsedToolCall(raw=raw, name="", args={}, parse_error="not an object"))
                continue
            name = obj.get("name") if isinstance(obj.get("name"), str) else ""
            args = obj.get("args", {})
            out.append(
                ParsedToolCall(
                    raw=raw,
                    name=name,
                    args=args,
                    parse_error=None if name else "missing 'name'",
                )
            )
        except json.JSONDecodeError as e:
            out.append(ParsedToolCall(raw=raw, name="", args={}, parse_error=str(e)))
    return out


def strip_tool_markup(text: str) -> str:
    s = _TOOL_TAG_RE.sub("", text)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


async def execute_tool_call(call: ParsedToolCall, ctx: ToolContext) -> str:
    if call.parse_error:
        return f"error: {call.parse_error}"
    tool = TOOLS.get(call.name)
    if not tool:
        return f"error: unknown tool '{call.name}'. Available: {', '.join(TOOLS.keys())}"
    try:
        return await tool.execute(call.args, ctx)
    except Exception as e:
        return f"error: tool '{call.name}' threw: {e}"


def format_tools_for_prompt() -> str:
    lines = [
        "You can call tools by emitting EXACTLY this format on its own:",
        '<tool>{"name":"<tool_name>","args":{...}}</tool>',
        "You may emit a tool call instead of a final answer. After tool results "
        "come back, you can emit another call or answer directly. Available tools:",
    ]
    for t in TOOLS.values():
        lines.append(f"- {t.name}: {t.description} args: {t.arg_spec}")
    return "\n".join(lines)


def format_tool_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return ""
    lines = ["Tool calls already made this turn:"]
    for h in history:
        args_str = json.dumps(h.get("args", {}), ensure_ascii=False)
        result = h.get("result", "")
        lines.append(f"- {h.get('name','?')}({args_str}) → {_trunc(result, 200)}")
    lines.append(
        "Either emit another <tool>{...}</tool> if you need more information, "
        "or give the final answer directly. Do not repeat a tool call with the same arguments."
    )
    return "\n".join(lines)
