"""Briefing business logic for BPMN/Zeebe.

WebRTC room/session edge handling stays in the Cloudflare Worker. Transcript
NLP, agenda validation, speaker analytics, and decision records run here.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from kotodama import llm

MAX_MEETING_DURATION_MS = 4 * 60 * 60 * 1000
MIN_TRANSCRIPT_LENGTH_FOR_SUMMARY = 200
MAX_AGENDA_ITEMS = 50
DEFAULT_ACTION_ITEM_DEADLINE_DAYS = 7


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def gen_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _str(value: Any, default: str = "") -> str:
    return default if value is None else str(value)


def _record(kind: str, record: dict[str, Any]) -> dict[str, Any]:
    return {"collection": f"com.etzhayyim.apps.briefing.{kind}", "record": record}


def _post(text: str) -> dict[str, str]:
    return {"text": text}


def _llm_text(prompt: str, max_tokens: int = 800) -> str:
    resp = llm.call_tier("fast", system="You are a concise meeting operations assistant.", user=prompt, max_tokens=max_tokens)
    return str(resp.get("content") or "")


def create_agenda(roomId: str = "", items: list[dict[str, Any]] | None = None, **_: Any) -> dict[str, Any]:
    if not roomId:
        return {"ok": False, "error": "missing_params", "detail": "roomId required"}
    items = items or []
    if len(items) > MAX_AGENDA_ITEMS:
        return {"ok": False, "error": "agenda_overflow", "detail": f"Max {MAX_AGENDA_ITEMS} agenda items allowed, got {len(items)}"}
    total = sum(int(item.get("durationMin") or 5) for item in items)
    if total * 60 * 1000 > MAX_MEETING_DURATION_MS:
        return {"ok": False, "error": "duration_exceeded", "detail": f"Total agenda {total}min exceeds max {MAX_MEETING_DURATION_MS // 60000}min"}
    agenda_id = gen_id("agd")
    record = {
        "agendaId": agenda_id,
        "roomId": roomId,
        "items": json.dumps(items, ensure_ascii=False),
        "totalDurationMin": total,
        "itemCount": len(items),
        "status": "draft",
        "createdAt": now_iso(),
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": "briefing-zeebe",
    }
    return {"ok": True, "agendaId": agenda_id, "roomId": roomId, "itemCount": len(items), "totalDurationMin": total, "records": [_record("briefingAgenda", record)]}


def save_transcript(roomId: str = "", recordingId: str = "", text: str = "", detectedLanguage: str = "unknown", convoId: str = "", **_: Any) -> dict[str, Any]:
    if not recordingId or not text:
        return {"ok": False, "error": "missing_params"}
    target = "English" if detectedLanguage.startswith("ja") else "Japanese"
    try:
        translated = _llm_text(f"Translate the following meeting transcript to {target}. Output only the translation, no explanation:\n\n{text[:4000]}", 1200)
    except Exception as e:  # noqa: BLE001
        translated = ""
        error = str(e)
    else:
        error = ""
    record = {
        "roomId": roomId,
        "recordingId": recordingId,
        "originalText": text,
        "translatedText": translated,
        "detectedLanguage": detectedLanguage,
        "convoId": convoId,
        "createdAt": now_iso(),
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": "briefing-zeebe",
    }
    return {"ok": True, "recordingId": recordingId, "originalText": text, "translatedText": translated, "detectedLanguage": detectedLanguage, "translationError": error, "records": [_record("briefingTranscript", record)]}


def extract_action_items(roomId: str = "", recordingId: str = "", text: str = "", priority: str = "normal", **_: Any) -> dict[str, Any]:
    if not roomId or not text:
        return {"ok": False, "error": "missing_params", "detail": "roomId and text required"}
    if len(text) < 50:
        return {"ok": False, "error": "transcript_too_short", "detail": "Transcript must be at least 50 characters for action item extraction"}
    try:
        raw = _llm_text(f'Extract action items from this meeting transcript. Return JSON array of {{"title": string, "assignee": string}}. If no assignee mentioned, use "unassigned":\n\n{text[:4000]}', 800)
        parsed = llm.parse_json_content(raw)
        items = parsed if isinstance(parsed, list) else parsed.get("items", []) if isinstance(parsed, dict) else []
    except Exception:  # noqa: BLE001
        items = [{"title": "Review meeting transcript", "assignee": "unassigned"}]
    if not items:
        items = [{"title": "Review meeting transcript", "assignee": "unassigned"}]
    deadline_days = 1 if priority == "urgent" else 3 if priority == "high" else DEFAULT_ACTION_ITEM_DEADLINE_DAYS if priority == "normal" else 14
    deadline = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + deadline_days * 86400))
    records = []
    for item in items:
        records.append(_record("briefingActionItem", {
            "actionItemId": gen_id("act"),
            "roomId": roomId,
            "recordingId": recordingId,
            "title": _str(item.get("title"), "Review meeting transcript") if isinstance(item, dict) else _str(item),
            "assignee": _str(item.get("assignee"), "unassigned") if isinstance(item, dict) else "unassigned",
            "priority": priority,
            "deadline": deadline,
            "status": "open",
            "createdAt": now_iso(),
            "org_id": "anon",
            "user_id": "anon",
            "actor_id": "briefing-zeebe",
        }))
    return {"ok": True, "roomId": roomId, "actionItemCount": len(records), "priority": priority, "deadline": deadline, "records": records, "posts": [_post(f"Extracted {len(records)} action items from briefing (priority: {priority}, deadline: {deadline.split('T')[0]})")]}


def generate_summary(roomId: str = "", recordingId: str = "", text: str = "", format: str = "bullet", **_: Any) -> dict[str, Any]:
    if not roomId or not text:
        return {"ok": False, "error": "missing_params", "detail": "roomId and text required"}
    if len(text) < MIN_TRANSCRIPT_LENGTH_FOR_SUMMARY:
        return {"ok": False, "error": "transcript_too_short", "detail": f"Transcript must be at least {MIN_TRANSCRIPT_LENGTH_FOR_SUMMARY} chars for summarization"}
    if format == "executive":
        prompt = f"Write a concise executive summary (3-5 sentences) of this meeting. Focus on decisions and outcomes:\n\n{text[:6000]}"
    elif format == "narrative":
        prompt = f"Write a narrative summary of this meeting in chronological order:\n\n{text[:6000]}"
    else:
        prompt = f"Summarize this meeting as bullet points. Include key discussions, decisions made, and next steps:\n\n{text[:6000]}"
    try:
        summary = _llm_text(prompt, 1200)
    except Exception:  # noqa: BLE001
        summary = "(Summary generation failed)"
    summary_id = gen_id("sum")
    record = {
        "summaryId": summary_id,
        "roomId": roomId,
        "recordingId": recordingId,
        "summary": summary,
        "format": format,
        "transcriptLength": len(text),
        "createdAt": now_iso(),
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": "briefing-zeebe",
    }
    return {"ok": True, "summaryId": summary_id, "roomId": roomId, "format": format, "summaryLength": len(summary), "records": [_record("briefingSummary", record)]}


def record_speaker_turn(roomId: str = "", peerId: str = "", displayName: str = "Unknown", startMs: float = 0, endMs: float = 0, **_: Any) -> dict[str, Any]:
    if not roomId or not peerId:
        return {"ok": False, "error": "missing_params", "detail": "roomId and peerId required"}
    duration = float(endMs) - float(startMs)
    if duration <= 0:
        return {"ok": False, "error": "invalid_duration", "detail": "endMs must be greater than startMs"}
    if duration > MAX_MEETING_DURATION_MS:
        return {"ok": False, "error": "duration_exceeded", "detail": "Speaker turn duration exceeds maximum meeting length"}
    record = {"roomId": roomId, "peerId": peerId, "displayName": displayName, "startMs": startMs, "endMs": endMs, "durationMs": duration, "recordedAt": now_iso(), "org_id": "anon", "user_id": "anon", "actor_id": peerId}
    return {"ok": True, "roomId": roomId, "peerId": peerId, "durationMs": duration, "records": [_record("briefingSpeakerTurn", record)]}


def record_decision(roomId: str = "", description: str = "", method: str = "consensus", voters: list[str] | None = None, votesFor: float = 0, votesAgainst: float = 0, **_: Any) -> dict[str, Any]:
    if not roomId or not description:
        return {"ok": False, "error": "missing_params", "detail": "roomId and description required"}
    voters = voters or []
    if method == "vote":
        if not voters:
            return {"ok": False, "error": "no_voters", "detail": "Vote-based decisions require at least one voter"}
        if votesFor + votesAgainst > len(voters):
            return {"ok": False, "error": "vote_count_mismatch", "detail": "Total votes exceed voter count"}
    outcome = "approved" if method in {"consensus", "authority"} or (method == "vote" and votesFor > votesAgainst) else "rejected" if method == "vote" else "recorded"
    decision_id = gen_id("dec")
    record = {"decisionId": decision_id, "roomId": roomId, "description": description, "method": method, "voters": json.dumps(voters), "votesFor": votesFor, "votesAgainst": votesAgainst, "outcome": outcome, "decidedAt": now_iso(), "org_id": "anon", "user_id": "anon", "actor_id": "briefing-zeebe"}
    return {"ok": True, "decisionId": decision_id, "roomId": roomId, "outcome": outcome, "method": method, "records": [_record("briefingDecision", record)], "posts": [_post(f'Decision {outcome}: "{description[:100]}" ({method})')]}
