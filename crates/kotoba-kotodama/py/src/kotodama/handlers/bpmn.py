"""
ADR-0047 Phase B pilot — bpmn actor on shared Python UDF pool.

Ports the *pure* subset of the TS implementation at
`60-apps/etzhayyim-project-bpmn/.../src/app.ts`:

- `com.etzhayyim.apps.bpmn.compileJsonToXml` — JSON subset → BPMN 2.0 XML
- `com.etzhayyim.apps.bpmn.validateXml` — cheap well-formedness check
- `com.etzhayyim.apps.bpmn.analyzeProcess` — Optimize-free OCEL process mining
  over kotoba Datom log BPMN audit rows, with optional LLM diagnosis

Stateful commands (deployProcess / startInstance / signalInstance /
getInstanceState / getActivityLog / cancelInstance / listProcesses /
listInstances) continue running on the pre-ADR-0049 TS Worker until the
BPMN execution engine (`engine.ts`, 477 LoC state machine) is ported
separately. The shared UDF pool carries pure verbs plus read-only analytics.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from kotodama import udf
from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client

# ---------------------------------------------------------------------------
# compileJsonToXml
# ---------------------------------------------------------------------------

_STEP_TYPES_WITH_NEXT = {
    "startEvent",
    "serviceTask",
    "userTask",
    "parallelGateway",
    "timerIntermediateCatchEvent",
}


def _esc(s: Any) -> str:
    """XML attribute-safe escape — matches the TS `esc` in app.ts."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _compile_json_to_xml(doc: dict[str, Any]) -> str:
    process_id = _esc(doc["id"])
    process_name = _esc(doc["name"])
    flow = doc.get("flow", [])

    flows: list[dict[str, str | None]] = []
    incoming: dict[str, list[str]] = {}
    outgoing: dict[str, list[str]] = {}

    def add_flow(src: str, dst: str, condition: str | None = None) -> None:
        fid = f"flow_{src}_{dst}"
        flows.append({"id": fid, "src": src, "dst": dst, "condition": condition})
        incoming.setdefault(dst, []).append(fid)
        outgoing.setdefault(src, []).append(fid)

    for step in flow:
        t = step.get("type")
        if t == "exclusiveGateway":
            if step.get("then"):
                add_flow(step["id"], step["then"], step.get("condition"))
            if step.get("else"):
                add_flow(step["id"], step["else"])
        elif t == "messageIntermediateCatchEvent":
            if step.get("next"):
                add_flow(step["id"], step["next"])
            if step.get("onTimeout"):
                add_flow(step["id"], step["onTimeout"])
        elif step.get("next"):
            add_flow(step["id"], step["next"])

    def inline_flows(node_id: str) -> str:
        inc = "".join(f"<bpmn:incoming>{_esc(f)}</bpmn:incoming>" for f in incoming.get(node_id, []))
        out = "".join(f"<bpmn:outgoing>{_esc(f)}</bpmn:outgoing>" for f in outgoing.get(node_id, []))
        return inc + out

    elements: list[str] = []
    for step in flow:
        id_ = _esc(step["id"])
        refs = inline_flows(step["id"])
        t = step.get("type")
        if t == "startEvent":
            elements.append(f'<bpmn:startEvent id="{id_}">{refs}</bpmn:startEvent>')
        elif t == "endEvent":
            elements.append(f'<bpmn:endEvent id="{id_}">{refs}</bpmn:endEvent>')
        elif t == "errorEndEvent":
            err = _esc(step.get("errorCode", "ERROR"))
            elements.append(
                f'<bpmn:endEvent id="{id_}">{refs}'
                f'<bpmn:errorEventDefinition errorRef="{err}"/></bpmn:endEvent>'
            )
        elif t == "serviceTask":
            nsid_val = _esc(step.get("nsid", ""))
            result_as = _esc(step.get("resultAs", ""))
            elements.append(
                f'<bpmn:serviceTask id="{id_}" name="{nsid_val}" '
                f'implementation="${{environment.services.xrpc}}">{refs}'
                f'<bpmn:extensionElements>'
                f'<etzhayyim:xrpc nsid="{nsid_val}" resultAs="{result_as}"/>'
                f'</bpmn:extensionElements></bpmn:serviceTask>'
            )
        elif t == "userTask":
            elements.append(f'<bpmn:userTask id="{id_}">{refs}</bpmn:userTask>')
        elif t == "exclusiveGateway":
            elements.append(f'<bpmn:exclusiveGateway id="{id_}">{refs}</bpmn:exclusiveGateway>')
        elif t == "parallelGateway":
            elements.append(f'<bpmn:parallelGateway id="{id_}">{refs}</bpmn:parallelGateway>')
        elif t == "timerIntermediateCatchEvent":
            dur = _esc(step.get("timeout", "PT1M"))
            elements.append(
                f'<bpmn:intermediateCatchEvent id="{id_}">{refs}'
                f'<bpmn:timerEventDefinition>'
                f'<bpmn:timeDuration>{dur}</bpmn:timeDuration>'
                f'</bpmn:timerEventDefinition></bpmn:intermediateCatchEvent>'
            )
        elif t == "messageIntermediateCatchEvent":
            msg = _esc(step.get("messageName", ""))
            elements.append(
                f'<bpmn:intermediateCatchEvent id="{id_}">{refs}'
                f'<bpmn:messageEventDefinition messageRef="{msg}"/>'
                f'</bpmn:intermediateCatchEvent>'
            )
        # sequenceFlow handled below as standalone elements

    # Standalone sequenceFlow elements
    for f in flows:
        body = ""
        cond = f.get("condition")
        if cond:
            body = (
                f'<bpmn:conditionExpression xsi:type="bpmn:tFormalExpression" '
                f'language="JavaScript">${{{_esc(cond)}}}</bpmn:conditionExpression>'
            )
        elements.append(
            f'<bpmn:sequenceFlow id="{_esc(f["id"])}" '
            f'sourceRef="{_esc(f["src"])}" targetRef="{_esc(f["dst"])}">{body}</bpmn:sequenceFlow>'
        )

    # Distinct message definitions
    messages = sorted(
        {
            step["messageName"]
            for step in flow
            if step.get("type") == "messageIntermediateCatchEvent" and step.get("messageName")
        }
    )
    message_defs = "\n  ".join(
        f'<bpmn:message id="{_esc(m)}" name="{_esc(m)}"/>' for m in messages
    )

    body_xml = "\n    ".join(elements)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:etzhayyim="https://etzhayyim.com/bpmn/extension" '
        f'id="def-{process_id}" targetNamespace="https://etzhayyim.com/bpmn">\n'
        f"  {message_defs}\n"
        f'  <bpmn:process id="{process_id}" name="{process_name}" isExecutable="true">\n'
        f"    {body_xml}\n"
        "  </bpmn:process>\n"
        "</bpmn:definitions>"
    )


@udf(
    nsid="com.etzhayyim.apps.bpmn.compileJsonToXml",
    io_threads=20,  # CPU-bound, minimal IO
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("bpmn", "compile"),
    agent_tool="Compile BPMN JSON subset to BPMN 2.0 XML.",
)
def compile_json_to_xml(doc_json: str) -> str:
    """
    Input: JSON-stringified BpmnJson `{id, name, flow[]}` OR an XRPC body
    wrapper `{"json": {id, name, flow}}` (matches the TS handler at
    `60-apps/etzhayyim-project-bpmn/.../src/app.ts` which also reads
    `params.json`).
    Output: JSON-stringified `{xml, byteSize}` or `{error}`.
    """
    import json

    try:
        parsed = json.loads(doc_json) if isinstance(doc_json, str) else doc_json
    except Exception as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    # Accept both the direct BpmnJson shape and the XRPC wrapper {json: ...}.
    if isinstance(parsed, dict) and "json" in parsed and isinstance(parsed.get("json"), dict):
        doc = parsed["json"]
    else:
        doc = parsed

    if not isinstance(doc, dict) or not doc.get("id") or not isinstance(doc.get("flow"), list):
        return json.dumps(
            {"error": "invalid BPMN JSON: require {id, name, flow[]}"}
        )
    try:
        xml = _compile_json_to_xml(doc)
        return json.dumps({"xml": xml, "byteSize": len(xml.encode("utf-8"))})
    except Exception as e:
        return json.dumps({"error": f"compile failed: {e}"})


# ---------------------------------------------------------------------------
# validateXml
# ---------------------------------------------------------------------------

_HAS_DECLARATION = re.compile(r"<\?xml")
_HAS_PROCESS = re.compile(r"<bpmn:process[^>]*>")
_HAS_CLOSE = re.compile(r"</bpmn:definitions>")


@udf(
    nsid="com.etzhayyim.apps.bpmn.validateXml",
    io_threads=20,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("bpmn", "validate"),
    agent_tool="Validate BPMN 2.0 XML (phase 1: well-formedness, no XSD).",
)
def validate_xml(xml: str) -> str:
    """
    Phase 1 cheap well-formedness check — matches the TS implementation.
    Phase 2 wires a real XSD validator (lxml + BPMN 2.0 schema) when the
    deployed actor graduates to authoritative validation.

    Accepts either a bare XML string or an XRPC body wrapper
    `{"xml": "<..."}` (matches TS handler input shape).
    """
    import json

    # Unwrap the XRPC body form if present.
    if xml and xml.lstrip().startswith("{"):
        try:
            parsed = json.loads(xml)
            if isinstance(parsed, dict) and isinstance(parsed.get("xml"), str):
                xml = parsed["xml"]
        except Exception:
            pass  # treat as bare XML

    if not xml:
        return json.dumps({"error": "xml required"})

    errors: list[str] = []
    if not _HAS_DECLARATION.search(xml):
        errors.append("missing xml declaration")
    if not _HAS_PROCESS.search(xml):
        errors.append("missing process element")
    if not _HAS_CLOSE.search(xml):
        errors.append("missing closing </bpmn:definitions>")

    if errors:
        return json.dumps({"valid": False, "errors": errors})
    return json.dumps({"valid": True, "errors": []})


# ---------------------------------------------------------------------------
# analyzeProcess
# ---------------------------------------------------------------------------


def _loads_obj(params_json: str) -> dict[str, Any]:
    if not params_json:
        return {}
    parsed = json.loads(params_json)
    if not isinstance(parsed, dict):
        raise ValueError("body must be a JSON object")
    return parsed


def _int_param(params: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    raw = params.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be an integer") from None
    if value < minimum or value > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _str_param(params: dict[str, Any], key: str) -> str:
    return str(params.get(key) or "").strip()


def _fetch_audit_events(params: dict[str, Any]) -> list[dict[str, Any]]:
    limit = _int_param(params, "limit", 500, 1, 5000)
    where = ["collection = 'com.etzhayyim.bpmn.audit'"]
    bind: list[Any] = []

    action_prefix = _str_param(params, "actionPrefix")
    if action_prefix:
        where.append("value_json::jsonb ->> 'action' LIKE %s")
        bind.append(f"{action_prefix}%")

    process_id = _str_param(params, "processId")
    if process_id:
        where.append(
            "("
            "value_json::jsonb ->> 'process_id' = %s OR "
            "value_json::jsonb ->> 'processId' = %s OR "
            "value_json::jsonb ->> '_bpmnProcessId' = %s"
            ")"
        )
        bind.extend([process_id, process_id, process_id])

    case_id = _str_param(params, "caseId")
    if case_id:
        where.append(
            "("
            "value_json::jsonb ->> 'case_id' = %s OR "
            "value_json::jsonb ->> 'caseId' = %s OR "
            "value_json::jsonb ->> 'runId' = %s OR "
            "rkey = %s"
            ")"
        )
        bind.extend([case_id, case_id, case_id, case_id])

    since = _str_param(params, "since")
    if since:
        where.append("created_at >= %s")
        bind.append(since)

    until = _str_param(params, "until")
    if until:
        where.append("created_at <= %s")
        bind.append(until)

    # R0: Initial fetch for audit events from kotoba Datom log,
    #     remaining filtering and projection applied in Python.
    client = get_kotoba_client()

    # Fetch all records for the specific collection. We'll filter further in Python.
    # The actual 'where' clause for the initial select should be minimal
    # to fetch a broad enough set, then filter in Python.
    # We fetch relevant fields: vertex_id, value_json, repo, ts_ms, created_at.
    # We use a generous limit for the initial fetch to allow for in-Python filtering.
    raw_events = client.select_where(
        "vertex_repo_commit",
        "collection",
        "com.etzhayyim.bpmn.audit",
        columns=["vertex_id", "value_json", "repo", "ts_ms", "created_at"],
        limit=5000,
    )

    processed_events: list[dict[str, Any]] = []
    for event_row in raw_events:
        value_json_str = event_row.get("value_json")
        if not value_json_str:
            continue
        try:
            event_value = json.loads(value_json_str)
        except json.JSONDecodeError:
            continue

        # Apply actionPrefix filter
        action = str(event_value.get("action", ""))
        if action_prefix and not action.startswith(action_prefix):
            continue

        # Apply processId filter
        process_id_val = str(event_value.get("process_id", ""))
        process_id_val_alt = str(event_value.get("processId", ""))
        process_id_val_bpmn = str(event_value.get("_bpmnProcessId", ""))
        if process_id and not (process_id_val == process_id or process_id_val_alt == process_id or process_id_val_bpmn == process_id):
            continue

        # Apply caseId filter
        event_rkey = str(event_row.get("vertex_id", ""))
        case_id_val = str(event_value.get("case_id", ""))
        case_id_val_alt = str(event_value.get("caseId", ""))
        case_id_val_runid = str(event_value.get("runId", ""))
        if case_id and not (case_id_val == case_id or case_id_val_alt == case_id or case_id_val_runid == case_id or event_rkey == case_id):
            continue

        # Apply since/until filters
        created_at_str = str(event_row.get("created_at", ""))
        if since and created_at_str < since:
            continue
        if until and created_at_str > until:
            continue

        # Construct the output row mirroring the SQL SELECT COALESCE/NULLIF logic
        case_id_out = (
            case_id_val or case_id_val_alt or case_id_val_runid or event_rkey
        )
        activity_out = event_value.get("action")
        actor_did_out = event_row.get("repo")
        ts_ms_out = event_row.get("ts_ms")
        timestamp_out = event_row.get("created_at")

        duration_ms_raw = event_value.get("duration_ms")
        duration_ms_out = int(duration_ms_raw) if duration_ms_raw is not None and str(duration_ms_raw).strip() != '' else None

        status_raw = str(event_value.get("status", ""))
        status_out = status_raw if status_raw.strip() != '' else 'ok'

        processed_events.append({
            "case_id": case_id_out,
            "activity": activity_out,
            "actor_did": actor_did_out,
            "ts_ms": ts_ms_out,
            "timestamp": timestamp_out,
            "duration_ms": duration_ms_out,
            "status": status_out,
            "payload_json": event_row.get("value_json"), # Keep original value_json as payload_json
        })

    # Apply ORDER BY ts_ms DESC
    processed_events.sort(key=lambda x: x.get("ts_ms", 0) or 0, reverse=True)

    # Apply LIMIT
    return processed_events[:limit]


def _summarize_events(events_desc: list[dict[str, Any]]) -> dict[str, Any]:
    events = list(reversed(events_desc))
    by_activity: dict[str, dict[str, Any]] = {}
    by_case: dict[str, list[dict[str, Any]]] = {}
    error_events: list[dict[str, Any]] = []
    durations: list[int] = []

    for event in events:
        activity = str(event.get("activity") or "unknown")
        case_id = str(event.get("case_id") or "unknown")
        by_case.setdefault(case_id, []).append(event)

        duration = event.get("duration_ms")
        duration_int: int | None = None
        if duration is not None:
            try:
                duration_int = int(duration)
                durations.append(duration_int)
            except (TypeError, ValueError):
                duration_int = None

        stat = by_activity.setdefault(
            activity,
            {
                "activity": activity,
                "count": 0,
                "totalDurationMs": 0,
                "maxDurationMs": None,
                "minDurationMs": None,
                "errorCount": 0,
            },
        )
        stat["count"] += 1
        if duration_int is not None:
            stat["totalDurationMs"] += duration_int
            stat["maxDurationMs"] = duration_int if stat["maxDurationMs"] is None else max(stat["maxDurationMs"], duration_int)
            stat["minDurationMs"] = duration_int if stat["minDurationMs"] is None else min(stat["minDurationMs"], duration_int)
        status = str(event.get("status") or "").lower()
        if status in {"error", "failed", "fail", "partial"}:
            stat["errorCount"] += 1
            if len(error_events) < 20:
                error_events.append(event)

    activity_rows: list[dict[str, Any]] = []
    for stat in by_activity.values():
        count = max(1, int(stat["count"]))
        row = dict(stat)
        row["avgDurationMs"] = int(row["totalDurationMs"] / count) if row["totalDurationMs"] else None
        row["errorRate"] = round(float(row["errorCount"]) / count, 4)
        activity_rows.append(row)

    bottlenecks = sorted(
        activity_rows,
        key=lambda r: (int(r.get("totalDurationMs") or 0), int(r.get("maxDurationMs") or 0), int(r.get("count") or 0)),
        reverse=True,
    )[:10]

    variants: dict[str, int] = {}
    case_summaries: list[dict[str, Any]] = []
    for case_id, rows in by_case.items():
        sequence = [str(r.get("activity") or "unknown") for r in rows]
        variant_key = " > ".join(sequence[:25])
        variants[variant_key] = variants.get(variant_key, 0) + 1
        case_summaries.append(
            {
                "caseId": case_id,
                "eventCount": len(rows),
                "firstEventAt": rows[0].get("timestamp") if rows else None,
                "lastEventAt": rows[-1].get("timestamp") if rows else None,
                "status": "failed" if any(str(r.get("status") or "").lower() in {"error", "failed", "fail"} for r in rows) else "observed",
                "variant": variant_key,
            }
        )

    avg_duration = (sum(durations) / len(durations)) if durations else 0
    slow_events = [
        event for event in events
        if event.get("duration_ms") is not None
        and avg_duration
        and int(event.get("duration_ms") or 0) > max(avg_duration * 2.0, avg_duration + 30_000)
    ][:20]

    return {
        "eventCount": len(events),
        "caseCount": len(by_case),
        "activityCount": len(by_activity),
        "window": {
            "firstEventAt": events[0].get("timestamp") if events else None,
            "lastEventAt": events[-1].get("timestamp") if events else None,
        },
        "activities": sorted(activity_rows, key=lambda r: str(r["activity"])),
        "bottlenecks": bottlenecks,
        "variants": [
            {"sequence": seq, "count": count}
            for seq, count in sorted(variants.items(), key=lambda kv: kv[1], reverse=True)[:10]
        ],
        "cases": sorted(case_summaries, key=lambda r: str(r.get("lastEventAt") or ""), reverse=True)[:50],
        "anomalies": {
            "errorEvents": error_events,
            "slowEvents": slow_events,
        },
    }


def _llm_analysis(params: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any] | None:
    if params.get("includeLlm") is False:
        return None
    compact = {
        "filters": {
            "processId": _str_param(params, "processId"),
            "caseId": _str_param(params, "caseId"),
            "actionPrefix": _str_param(params, "actionPrefix"),
            "since": _str_param(params, "since"),
            "until": _str_param(params, "until"),
        },
        "eventCount": summary["eventCount"],
        "caseCount": summary["caseCount"],
        "activityCount": summary["activityCount"],
        "window": summary["window"],
        "bottlenecks": summary["bottlenecks"][:6],
        "variants": summary["variants"][:5],
        "errorEvents": summary["anomalies"]["errorEvents"][:8],
        "slowEvents": summary["anomalies"]["slowEvents"][:8],
    }
    system = (
        "You are a process mining analyst for BPMN/Zeebe execution logs. "
        "Use only the supplied OCEL-style statistics. Return concise JSON with "
        "keys: summary, bottlenecks, anomalies, likelyCauses, recommendations, confidence."
    )
    user = json.dumps(compact, ensure_ascii=False, sort_keys=True, default=str)
    resp = llm.call_tier(
        "structured",
        system=system,
        user=user,
        max_tokens=900,
        temperature=0.1,
        extra={"response_format": {"type": "json_object"}},
    )
    content = str(resp.get("content") or "").strip()
    try:
        parsed = json.loads(llm._strip_code_fence(content))
    except Exception:
        parsed = {"summary": content[:4000]}
    parsed["_model"] = resp.get("model")
    parsed["_latencyMs"] = resp.get("latencyMs")
    return parsed


@udf(
    nsid="com.etzhayyim.apps.bpmn.analyzeProcess",
    io_threads=8,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("bpmn", "ocel", "process-mining", "llm"),
    agent_tool="Analyze BPMN/Zeebe OCEL audit events with deterministic statistics and optional LLM explanation.",
)
def analyze_process(params_json: str) -> str:
    """Optimize-free process mining over vertex_repo_commit (kotoba Datom log) BPMN audit rows."""
    try:
        params = _loads_obj(params_json)
        events = _fetch_audit_events(params)
        summary = _summarize_events(events)
        out: dict[str, Any] = {
            "ok": True,
            "source": "vertex_repo_commit:com.etzhayyim.bpmn.audit",
            "filters": {
                "processId": _str_param(params, "processId") or None,
                "caseId": _str_param(params, "caseId") or None,
                "actionPrefix": _str_param(params, "actionPrefix") or None,
                "since": _str_param(params, "since") or None,
                "until": _str_param(params, "until") or None,
                "limit": _int_param(params, "limit", 500, 1, 5000),
            },
            **summary,
        }
        try:
            out["llm"] = _llm_analysis(params, summary)
        except Exception as e:  # noqa: BLE001
            out["llm"] = None
            out["llmError"] = str(e)[:500]
        return json.dumps(out, ensure_ascii=False, sort_keys=True, default=str)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, sort_keys=True)
