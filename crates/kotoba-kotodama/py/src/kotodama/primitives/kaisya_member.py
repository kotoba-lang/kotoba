"""
kaisya.member.* — LangServer handler for member chat dispatch.

Task type: kaisya.member.chat
Submits to LangGraph kaisya-member-assistant in-process.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

LOG = logging.getLogger("kaisya.member.primitive")


async def task_kaisya_member_chat(
    user_upn: str = "",
    user_message: str = "",
    session_id: str = "",
    channel: str = "web",
) -> dict:
    """Dispatch a member chat turn to the LangGraph assistant."""
    if not user_upn or not user_message:
        return {"ok": False, "error": "user_upn + user_message required"}

    thread_id = session_id or f"kaisya-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"

    def _run() -> dict:
        from kotodama.langgraph_graphs.kaisya_member_assistant import build_graph
        graph = build_graph()
        return dict(graph.invoke({
            "user_upn":     user_upn,
            "user_message": user_message,
            "session_id":   thread_id,
            "channel":      channel,
            "history":      [],
        }))

    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
    except Exception as exc:
        LOG.error("kaisya.member.chat failed: %s", exc)
        return {"ok": False, "error": str(exc)}

    return {
        "ok":                       result.get("ok", True),
        "member_did":               result.get("member_did", ""),
        "member_name":              result.get("member_name", ""),
        "route":                    result.get("route", ""),
        "routing_reason":           result.get("routing_reason", ""),
        "reply_text":               result.get("reply_text", ""),
        "sub_summary":              result.get("sub_summary", ""),
        "requires_human_approval":  result.get("requires_human_approval", False),
        "session_id":               thread_id,
        "error":                    result.get("error"),
    }


def register(app: Any, timeout_ms: int = 90_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="kaisya.member.chat",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _chat(user_upn: str = "", user_message: str = "",
                    session_id: str = "", channel: str = "web") -> dict:
        return await task_kaisya_member_chat(
            user_upn=user_upn, user_message=user_message,
            session_id=session_id, channel=channel,
        )

    LOG.info("Registered task: kaisya.member.chat")
