"""
etzhayyim.etzhayyim.com — Japanese company operations LangGraph (ADR-2605080600).

Principal: etzhayyim (sole operator)
Vendor capacity: etzhayyim Japan株式会社 (engineering contractor)

Architecture: Supervisor + 5 domain-specialist nodes
  START → supervisor → {hr | finance | legal | sales | governance} → emit_audit → END

Domains:
  HR         採用/勤怠/評価/社会保険/給与計算
  Finance    仕訳/請求/経費承認/税務/キャッシュフロー
  Legal      契約レビュー/訴訟対応/コンプライアンス (LingLing/鈴木/鹿児島大学/松岡)
  Sales      顧客CRM/提案書/受注/パイプライン
  Governance OKR/意思決定/会議/株主報告/Ω(t)評価

State flow:
  input (task_type + payload) → supervisor classifies → domain node executes
  → result merged back → audit → END

LLM: llm.call_tier("structured", ...) via _etzhayyim_LLM_URL → murakumo/RunPod
  (ADR-2605010000: RunPod 6000 Ada is LLM SSoT)

Registered as assistant_id="etzhayyim-company-ops" in langgraph_server_app.
"""

from __future__ import annotations

import json
import logging
import time as _time
import uuid
from typing import Any, Literal, TypedDict
from kotodama.kotoba_datomic import get_kotoba_client
from datetime import datetime, timezone

LOG = logging.getLogger("etzhayyim.company_ops")

_ORG_DID   = "did:web:etzhayyim.etzhayyim.com"
_OWNER_DID = "did:web:bpmn.etzhayyim.com"

# Human-DID mapping for audit trail (same members as kaisya_ai_org.py)
_AGENT_HUMAN: dict[str, str] = {
    "supervisor":  "did:web:j-kawasaki.etzhayyim.com",   # CEO — routing decisions
    "hr":          "did:web:a-nakamura.etzhayyim.com",    # COO oversees HR
    "finance":     "did:web:j-kawasaki.etzhayyim.com",   # CEO/CFO for finance
    "legal":       "did:web:k-bakshi.etzhayyim.com",     # CLO
    "sales":       "did:web:t-ichihara.etzhayyim.com",   # Brand/BD
    "governance":  "did:web:j-kawasaki.etzhayyim.com",   # CEO governs
    "personnel":   "did:web:a-nakamura.etzhayyim.com",   # COO oversees personnel/RACI
}

Domain = Literal["hr", "finance", "legal", "sales", "governance", "personnel", "unknown"]


# ── State ──────────────────────────────────────────────────────────────────────

class CompanyOpsState(TypedDict, total=False):
    # Input
    task_type: str          # e.g. "hr.onboard", "finance.journal", "legal.review"
    payload: dict           # domain-specific payload dict
    thread_id: str          # actor-scoped thread (actor DID)
    requester_did: str      # DID of human/agent who initiated

    # Supervisor output
    domain: Domain          # classified domain
    routing_reason: str     # short rationale from supervisor

    # Domain node output
    result: dict            # domain-specific result (success/error + data)
    action_items: list[str] # follow-up tasks for human review

    # Governance only
    omega_score: float      # Ω(t) = Shannon_η × U_total [0,1]
    floor_violated: bool    # True when any U axis = 0

    # Lifecycle
    ok: bool
    error: str | None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")

def _vid(kind: str) -> str:
    import datetime as _dt
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://{_OWNER_DID}/com.etzhayyim.apps.etzhayyim.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"


def _llm_structured(system: str, user: str, max_tokens: int = 800) -> dict:
    """Call LLM via llm.call_tier (ADR-2605010000 — RunPod 6000 Ada SSoT)."""
    try:
        from kotodama.llm import call_tier
        result = call_tier("structured", system=system, user=user, max_tokens=max_tokens)
        content = result.get("content", "")
        # Strip markdown fences
        if "```" in content:
            parts = content.split("```")
            for p in parts[1::2]:
                stripped = p.lstrip("json").strip()
                try:
                    return json.loads(stripped)
                except Exception:
                    pass
        try:
            return json.loads(content)
        except Exception:
            return {"raw": content}
    except Exception as exc:
        LOG.warning("LLM call failed: %s", exc)
        return {"error": str(exc)}


def _db_insert(table: str, row: dict) -> bool:
    """Insert row into kotoba Datomic client."""
    try:
        get_kotoba_client().insert_row(table, row)
        return True
    except Exception as exc:
        LOG.warning("DB insert %s failed: %s", table, exc)
        return False


def _db_query(sql_str: str, params: dict | None = None) -> list[dict]:
    """Deprecated: Query functions should directly use kotoba client methods."""
    raise NotImplementedError("Direct SQL queries via _db_query are deprecated. Use kotoba_client.select_where or kotoba_client.q().")


# ── Node: supervisor ───────────────────────────────────────────────────────────

_SUPERVISOR_SYSTEM = """You are the AI supervisor for etzhayyim.etzhayyim.com (operated by etzhayyim, vendor: etzhayyim Japan株式会社).
Classify the incoming task into exactly ONE domain: hr | finance | legal | sales | governance.

Domain definitions:
- hr: hiring, attendance, payroll, social insurance, performance review, onboarding/offboarding
- finance: journal entries, invoices, expense approval, tax, cash flow, accounting
- legal: contracts, litigation, compliance, regulatory, IP, corporate procedures
- sales: CRM, proposals, orders, customer management, BD pipeline
- governance: OKR, management decisions, board/shareholder reporting, org health (Ω score)

Respond with JSON only: {"domain": "<domain>", "reason": "<one sentence>"}
"""

def supervisor(state: CompanyOpsState) -> dict:
    """Classify task_type + payload into a domain."""
    task_type = state.get("task_type", "")
    payload   = state.get("payload", {})

    # Fast path: task_type prefix → domain
    _PREFIX_MAP = {
        "hr.":         "hr",
        "finance.":    "finance",
        "accounting.": "finance",
        "legal.":      "legal",
        "contract.":   "legal",
        "sales.":      "sales",
        "crm.":        "sales",
        "governance.": "governance",
        "okr.":        "governance",
        "omega.":      "governance",
        "personnel.":  "personnel",
        "role.":       "personnel",
        "raci.":       "personnel",
        "assignment.": "personnel",
    }
    for prefix, domain in _PREFIX_MAP.items():
        if task_type.startswith(prefix):
            return {"domain": domain, "routing_reason": f"prefix match: {prefix}"}

    # LLM fallback
    user_msg = f"task_type: {task_type}\npayload keys: {list(payload.keys())}"
    classified = _llm_structured(_SUPERVISOR_SYSTEM, user_msg, max_tokens=100)
    domain = classified.get("domain", "governance")
    reason = classified.get("reason", "LLM classified")
    return {"domain": domain, "routing_reason": reason}


# ── Node: HR agent ─────────────────────────────────────────────────────────────

_HR_SYSTEM = """You are the HR AI agent for etzhayyim Japan株式会社 (principal: etzhayyim).
Handle: onboarding, offboarding, attendance records, payroll calculation,
social insurance procedures, performance reviews, hiring decisions.

Output JSON: {
  "action": "<action taken>",
  "summary": "<brief summary in Japanese>",
  "db_writes": [{"table": "...", "row": {...}}],
  "action_items": ["<human review item>", ...],
  "ok": true
}
"""

def hr_agent(state: CompanyOpsState) -> dict:
    """HR domain: 採用/勤怠/給与/社保."""
    task_type = state.get("task_type", "")
    payload   = state.get("payload", {})
    user_msg  = f"task: {task_type}\ndata: {json.dumps(payload, ensure_ascii=False)}"

    result = _llm_structured(_HR_SYSTEM, user_msg, max_tokens=1000)
    ok = bool(result.get("ok", True))

    # Persist DB writes requested by LLM
    for write in result.get("db_writes") or []:
        table = write.get("table", "vertex_etzhayyim_hr_event")
        row   = write.get("row", {})
        if row and not row.get("vertex_id"):
            row["vertex_id"] = _vid("hr." + task_type.split(".")[-1])
        if row:
            _db_insert(table, {k: str(v) for k, v in row.items()})

    return {
        "result": result,
        "action_items": result.get("action_items") or [],
        "ok": ok,
        "error": result.get("error") if not ok else None,
    }


# ── Node: Finance agent ────────────────────────────────────────────────────────

_FINANCE_SYSTEM = """You are the Finance/Accounting AI agent for etzhayyim Japan株式会社 (principal: etzhayyim).
Handle: journal entries (仕訳), invoices (請求書), expense approval (経費承認),
tax filings, cash flow forecasts, accounts payable/receivable.

Output JSON: {
  "action": "<action>",
  "journal_entry": {"debit": "...", "credit": "...", "amount_jpy": 0, "description": "..."},
  "summary": "<Japanese>",
  "db_writes": [{"table": "...", "row": {...}}],
  "action_items": ["..."],
  "ok": true
}
"""

def finance_agent(state: CompanyOpsState) -> dict:
    """Finance domain: 仕訳/請求/経費/税務."""
    task_type = state.get("task_type", "")
    payload   = state.get("payload", {})
    user_msg  = f"task: {task_type}\ndata: {json.dumps(payload, ensure_ascii=False)}"

    result = _llm_structured(_FINANCE_SYSTEM, user_msg, max_tokens=1200)
    ok = bool(result.get("ok", True))

    for write in result.get("db_writes") or []:
        table = write.get("table", "vertex_etzhayyim_finance_event")
        row   = write.get("row", {})
        if row and not row.get("vertex_id"):
            row["vertex_id"] = _vid("finance." + task_type.split(".")[-1])
        if row:
            _db_insert(table, {k: str(v) for k, v in row.items()})

    return {
        "result": result,
        "action_items": result.get("action_items") or [],
        "ok": ok,
        "error": result.get("error") if not ok else None,
    }


# ── Node: Legal agent ──────────────────────────────────────────────────────────

_LEGAL_SYSTEM = """You are the Legal/Compliance AI agent (CLO support) for etzhayyim Japan株式会社.
Principal: etzhayyim.
Active cases in kaisya.etzhayyim.com: LingLing著作権 / 鈴木損害賠償 / 鹿児島大学技術移転 / 松岡NDA.

Handle: contract review, litigation status, compliance checks, IP procedures,
corporate filings, regulatory inquiries.

Output JSON: {
  "action": "<action>",
  "risk_level": "low|medium|high|critical",
  "summary": "<Japanese>",
  "case_updates": [{"case_id": "...", "update": "..."}],
  "db_writes": [{"table": "...", "row": {...}}],
  "action_items": ["..."],
  "ok": true
}
"""

def legal_agent(state: CompanyOpsState) -> dict:
    """Legal domain: 契約/訴訟/コンプライアンス."""
    task_type = state.get("task_type", "")
    payload   = state.get("payload", {})

    # Enrich with active cases if needed
    cases_ctx = ""
    if any(kw in task_type for kw in ("legal.", "contract.", "litigation", "case")):
        # R0: Multi-predicate query for active/pending legal cases
        rows = get_kotoba_client().q(
            '[:find ?vertex_id ?title ?status ?priority '
            ':where '
            '  [?e :vertex/type "kaisya_legal_case"] '
            '  [?e :vertex_kaisya_legal_case/vertex_id ?vertex_id] '
            '  [?e :vertex_kaisya_legal_case/title ?title] '
            '  [?e :vertex_kaisya_legal_case/status ?status] '
            '  (or [?e :vertex_kaisya_legal_case/status "active"] '
            '      [?e :vertex_kaisya_legal_case/status "pending"]) '
            '  [?e :vertex_kaisya_legal_case/priority ?priority] '
            ':limit 10]'
        )
        if rows:
            cases_ctx = "\nActive cases: " + json.dumps(rows, ensure_ascii=False)

    user_msg = f"task: {task_type}\ndata: {json.dumps(payload, ensure_ascii=False)}{cases_ctx}"
    result = _llm_structured(_LEGAL_SYSTEM, user_msg, max_tokens=1200)
    ok = bool(result.get("ok", True))

    for write in result.get("db_writes") or []:
        table = write.get("table", "vertex_etzhayyim_legal_event")
        row   = write.get("row", {})
        if row and not row.get("vertex_id"):
            row["vertex_id"] = _vid("legal." + task_type.split(".")[-1])
        if row:
            _db_insert(table, {k: str(v) for k, v in row.items()})

    return {
        "result": result,
        "action_items": result.get("action_items") or [],
        "ok": ok,
        "error": result.get("error") if not ok else None,
    }


# ── Node: Sales agent ──────────────────────────────────────────────────────────

_SALES_SYSTEM = """You are the Sales/BD AI agent for etzhayyim Japan株式会社 (principal: etzhayyim).
Handle: CRM records, proposal generation (提案書), order management (受注),
BD pipeline tracking, customer relationship notes.

Output JSON: {
  "action": "<action>",
  "pipeline_update": {"customer": "...", "stage": "...", "amount_jpy": 0},
  "summary": "<Japanese>",
  "db_writes": [{"table": "...", "row": {...}}],
  "action_items": ["..."],
  "ok": true
}
"""

def sales_agent(state: CompanyOpsState) -> dict:
    """Sales domain: CRM/提案書/受注."""
    task_type = state.get("task_type", "")
    payload   = state.get("payload", {})
    user_msg  = f"task: {task_type}\ndata: {json.dumps(payload, ensure_ascii=False)}"

    result = _llm_structured(_SALES_SYSTEM, user_msg, max_tokens=1000)
    ok = bool(result.get("ok", True))

    for write in result.get("db_writes") or []:
        table = write.get("table", "vertex_etzhayyim_sales_event")
        row   = write.get("row", {})
        if row and not row.get("vertex_id"):
            row["vertex_id"] = _vid("sales." + task_type.split(".")[-1])
        if row:
            _db_insert(table, {k: str(v) for k, v in row.items()})

    return {
        "result": result,
        "action_items": result.get("action_items") or [],
        "ok": ok,
        "error": result.get("error") if not ok else None,
    }


# ── Node: Governance agent ─────────────────────────────────────────────────────

_GOVERNANCE_SYSTEM = """You are the Governance AI agent for etzhayyim.etzhayyim.com (etzhayyim principal).
Evaluate Ω(t) = Shannon_η(t) × U_total(t) and generate management decisions.

Ω axes:
  Spirit      = OKR attainment + CEO strategic clarity + Shannon η
  Wellbecoming= delivery quality + team growth + project completion rate
  Feeling     = team morale (inverse of pending task pressure) + legal load
  Buffer      = financial runway (months) + infra health [0-1]

Floor rule: any axis = 0 → U_total = 0 (Spirit zero kills utility).

Output JSON: {
  "omega_score": 0.0,
  "floor_violated": false,
  "axis_scores": {"spirit": 0.0, "wellbecoming": 0.0, "feeling": 0.0, "buffer": 0.0},
  "decisions": [{"priority": 1, "decision": "...", "assignee_did": "..."}],
  "summary": "<Japanese management summary>",
  "action_items": ["..."],
  "ok": true
}
"""

def governance_agent(state: CompanyOpsState) -> dict:
    """Governance domain: OKR/意思決定/Ω(t)評価."""
    task_type = state.get("task_type", "")
    payload   = state.get("payload", {})

    # Collect org snapshot for Ω calculation
    # R0: Order-by and limit query for latest org snapshot
    keys = ["omega_score", "shannon_eta", "u_spirit", "u_wellbecoming", "u_feeling", "u_buffer", "snapshot_at"]
    raw_rows = get_kotoba_client().q(
        '[:find ?omega_score ?shannon_eta ?u_spirit ?u_wellbecoming ?u_feeling ?u_buffer ?snapshot_at '
        ':where '
        '  [?e :vertex/type "kaisya_org_snapshot"] '
        '  [?e :vertex_kaisya_org_snapshot/omega_score ?omega_score] '
        '  [?e :vertex_kaisya_org_snapshot/shannon_eta ?shannon_eta] '
        '  [?e :vertex_kaisya_org_snapshot/u_spirit ?u_spirit] '
        '  [?e :vertex_kaisya_org_snapshot/u_wellbecoming ?u_wellbecoming] '
        '  [?e :vertex_kaisya_org_snapshot/u_feeling ?u_feeling] '
        '  [?e :vertex_kaisya_org_snapshot/u_buffer ?u_buffer] '
        '  [?e :vertex_kaisya_org_snapshot/snapshot_at ?snapshot_at] '
        ':order-by [?e :vertex_kaisya_org_snapshot/snapshot_at :desc] '
        ':limit 1]'
    )
    rows = [dict(zip(keys, row)) for row in raw_rows]
    snapshot_ctx = ""
    if rows:
        snapshot_ctx = "\nLatest org snapshot: " + json.dumps(rows[0], ensure_ascii=False)

    user_msg = (
        f"task: {task_type}\ndata: {json.dumps(payload, ensure_ascii=False)}{snapshot_ctx}"
    )
    result = _llm_structured(_GOVERNANCE_SYSTEM, user_msg, max_tokens=1500)

    omega = float(result.get("omega_score", 0.0))
    floor_violated = bool(result.get("floor_violated", False))
    ok = bool(result.get("ok", True))

    # Persist governance decision
    gov_row = {
        "vertex_id": _vid("governance"),
        "task_type": task_type,
        "omega_score": str(omega),
        "floor_violated": str(floor_violated).lower(),
        "decisions_json": json.dumps(result.get("decisions") or []),
        "summary": result.get("summary", ""),
        "created_at": _now_iso(),
    }
    _db_insert("vertex_etzhayyim_governance_event", gov_row)

    return {
        "result": result,
        "omega_score": omega,
        "floor_violated": floor_violated,
        "action_items": result.get("action_items") or [],
        "ok": ok,
        "error": result.get("error") if not ok else None,
    }


# ── Node: Personnel agent ──────────────────────────────────────────────────────

_PERSONNEL_SYSTEM = """You are the Personnel/HR-Ops AI agent for etzhayyim Japan株式会社 (principal: etzhayyim).
Manage contracted person records, role definitions, project assignments, and RACI matrices.

Tables:
  vertex_etzhayyim_person      (person_did, display_name, employment_type, department, title, status)
  vertex_etzhayyim_role        (role_id, role_name, department, level, is_leadership)
  vertex_etzhayyim_assignment  (person_did, role_id, project_id, allocation_pct, start_date, end_date, status)
  vertex_etzhayyim_raci        (task_nsid, person_did, raci_role ∈ {R,A,C,I}, context, effective_date)
  vertex_etzhayyim_okr         (person_did, team, period, objective, key_result, progress_pct)

Tasks:
- personnel.list / personnel.get / personnel.update — person CRUD
- role.list / role.assign — role definitions + binding
- assignment.create / assignment.end / assignment.list — project allocation
- raci.assign / raci.list / raci.lookup — RACI matrix per task NSID

Output JSON: {
  "action": "<action>",
  "summary": "<Japanese>",
  "queries": [{"sql": "SELECT ...", "params": {}}],
  "db_writes": [{"table": "...", "row": {...}}],
  "action_items": ["..."],
  "ok": true
}
"""

def personnel_agent(state: CompanyOpsState) -> dict:
    """Personnel domain: person/role/assignment/RACI."""
    task_type = state.get("task_type", "")
    payload   = state.get("payload", {})

    # Enrich with current personnel snapshot for context
    snapshot_ctx = ""
    if task_type.startswith(("personnel.list", "role.list", "assignment.list", "raci.list")):
        keys = ["person_did", "display_name", "department", "title", "status"]
        raw_rows = get_kotoba_client().q(
            '[:find ?person_did ?display_name ?department ?title ?status '
            ':where '
            '  [?e :vertex/type "etzhayyim_person"] '
            '  [?e :vertex_etzhayyim_person/person_did ?person_did] '
            '  [?e :vertex_etzhayyim_person/display_name ?display_name] '
            '  [?e :vertex_etzhayyim_person/department ?department] '
            '  [?e :vertex_etzhayyim_person/title ?title] '
            '  [?e :vertex_etzhayyim_person/status "active"] '
            ':limit 50]'
        )
        rows = [dict(zip(keys, row)) for row in raw_rows]
        if rows:
            snapshot_ctx = "\nActive personnel: " + json.dumps(rows, ensure_ascii=False)

    user_msg = f"task: {task_type}\ndata: {json.dumps(payload, ensure_ascii=False)}{snapshot_ctx}"
    result = _llm_structured(_PERSONNEL_SYSTEM, user_msg, max_tokens=1200)
    ok = bool(result.get("ok", True))

    # Persist DB writes (assignment / raci updates)
    for write in result.get("db_writes") or []:
        table = write.get("table", "vertex_etzhayyim_assignment")
        row   = write.get("row", {})
        if row and not row.get("vertex_id"):
            row["vertex_id"] = _vid("personnel." + task_type.split(".")[-1])
        if row:
            _db_insert(table, {k: str(v) for k, v in row.items()})

    return {
        "result": result,
        "action_items": result.get("action_items") or [],
        "ok": ok,
        "error": result.get("error") if not ok else None,
    }


# ── Node: emit_audit ───────────────────────────────────────────────────────────

def emit_audit(state: CompanyOpsState) -> dict:
    """Write OCEL audit row to kotoba Datom log."""
    ts_ms = int(_time.time() * 1000)
    domain   = state.get("domain", "unknown")
    ok       = state.get("ok", True)
    omega    = state.get("omega_score")
    result   = state.get("result") or {}

    try:
        row_to_insert = {
            "vertex_id": _vid("audit.repo_commit"),
            "repo": _ORG_DID,
            "collection": "com.etzhayyim.apps.etzhayyim.ops",
            "rkey": f"ops-{ts_ms}",
            "action": "create",
            "ts_ms": ts_ms,
            "record_json": json.dumps({
                "domain": domain,
                "ok": ok,
                "omega_score": omega,
                "action": result.get("action", ""),
            }),
        }
        get_kotoba_client().insert_row("vertex_repo_commit", row_to_insert)
    except Exception as exc:
        LOG.debug("audit emit skipped (non-fatal): %s", exc)

    return {}


# ── Phase E3 v2 helpers (data-driven decomposition, ADR-2605082000) ───────────
#
# Each domain agent is split into:
#   <domain>_fetch_ctx (only legal/governance/personnel) — py_primitive that
#     fetches SQL context and writes a `<domain>Context` field consumed by the
#     next node's user_template.
#   <domain>_call_llm — mcp_tool ref=mcp://com.etzhayyim.tools.llm.chat (in v2 SQL
#     migration; not a function here).
#   <domain>_persist — py_primitive that reads
#     `state.<domain>LlmOut.result.content` (envelope from llm.chat) or falls
#     back to legacy direct-call shape, parses the JSON (handling ```fences```)
#     and runs the db_writes loop. Also writes `<domain>_audit_record` for the
#     downstream emit_audit mcp_tool.
#
# supervisor / emit_audit are NOT decomposed (supervisor stays py_primitive
# because it sets `state.domain` for Phase D2 field routing; emit_audit becomes
# mcp_tool com.etzhayyim.tools.audit.emit consuming `<domain>_audit_record`).


def _envelope_content(state: CompanyOpsState, envelope_key: str) -> str:
    """Extract content from {envelope_key}.result.content if upstream node was
    mcp_tool com.etzhayyim.tools.llm.chat. Returns '' if absent."""
    envelope = state.get(envelope_key)
    if isinstance(envelope, dict):
        result = envelope.get("result")
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, str) and content:
                return content
    return ""


def _parse_llm_json(content: str) -> dict:
    """Parse JSON from LLM content, tolerating ```json fences```."""
    if not content:
        return {}
    if "```" in content:
        parts = content.split("```")
        for p in parts[1::2]:
            stripped = p.lstrip("json").strip()
            try:
                return json.loads(stripped)
            except Exception:
                pass
    try:
        return json.loads(content)
    except Exception:
        return {"raw": content}


def _persist_domain(
    state: CompanyOpsState,
    envelope_key: str,
    default_table: str,
    vid_prefix: str,
    audit_field_key: str,
) -> dict:
    """Shared persist primitive — parse LLM envelope, run db_writes loop,
    return result + audit record + ok/error."""
    content = _envelope_content(state, envelope_key)
    result = _parse_llm_json(content) if content else {}
    ok = bool(result.get("ok", True)) if result else False
    task_type = state.get("task_type", "")

    for write in result.get("db_writes") or []:
        table = write.get("table", default_table)
        row   = write.get("row", {})
        if row and not row.get("vertex_id"):
            row["vertex_id"] = _vid(f"{vid_prefix}." + task_type.split(".")[-1])
        if row:
            _db_insert(table, {k: str(v) for k, v in row.items()})

    audit_record = {
        "domain": vid_prefix,
        "ok": ok,
        "action": result.get("action", "") if isinstance(result, dict) else "",
    }
    out: dict = {
        "result": result,
        "action_items": (result.get("action_items") or []) if isinstance(result, dict) else [],
        "ok": ok,
        "error": result.get("error") if isinstance(result, dict) and not ok else None,
        audit_field_key: audit_record,
        "audit_record": audit_record,
    }
    return out


def hr_persist(state: CompanyOpsState) -> dict:
    return _persist_domain(state, "hrLlmOut", "vertex_etzhayyim_hr_event", "hr", "hr_audit_record")


def finance_persist(state: CompanyOpsState) -> dict:
    return _persist_domain(state, "financeLlmOut", "vertex_etzhayyim_finance_event", "finance", "finance_audit_record")


def sales_persist(state: CompanyOpsState) -> dict:
    return _persist_domain(state, "salesLlmOut", "vertex_etzhayyim_sales_event", "sales", "sales_audit_record")


def legal_fetch_ctx(state: CompanyOpsState) -> dict:
    """Pre-LLM SQL context: active legal cases, exposed as state.legalContext."""
    task_type = state.get("task_type", "")
    if any(kw in task_type for kw in ("legal.", "contract.", "litigation", "case")):
        # R0: Multi-predicate query for active/pending legal cases
        rows = get_kotoba_client().q(
            '[:find ?vertex_id ?title ?status ?priority '
            ':where '
            '  [?e :vertex/type "kaisya_legal_case"] '
            '  [?e :vertex_kaisya_legal_case/vertex_id ?vertex_id] '
            '  [?e :vertex_kaisya_legal_case/title ?title] '
            '  [?e :vertex_kaisya_legal_case/status ?status] '
            '  (or [?e :vertex_kaisya_legal_case/status "active"] '
            '      [?e :vertex_kaisya_legal_case/status "pending"]) '
            '  [?e :vertex_kaisya_legal_case/priority ?priority] '
            ':limit 10]'
        )
        if rows:
            return {"legalContext": "Active cases: " + json.dumps(rows, ensure_ascii=False)}
    return {"legalContext": ""}


def legal_persist(state: CompanyOpsState) -> dict:
    return _persist_domain(state, "legalLlmOut", "vertex_etzhayyim_legal_event", "legal", "legal_audit_record")


def governance_fetch_ctx(state: CompanyOpsState) -> dict:
    """Pre-LLM SQL context: latest org snapshot, exposed as state.governanceContext."""
    # R0: Order-by and limit query for latest org snapshot
    keys = ["omega_score", "shannon_eta", "u_spirit", "u_wellbecoming", "u_feeling", "u_buffer", "snapshot_at"]
    raw_rows = get_kotoba_client().q(
        '[:find ?omega_score ?shannon_eta ?u_spirit ?u_wellbecoming ?u_feeling ?u_buffer ?snapshot_at '
        ':where '
        '  [?e :vertex/type "kaisya_org_snapshot"] '
        '  [?e :vertex_kaisya_org_snapshot/omega_score ?omega_score] '
        '  [?e :vertex_kaisya_org_snapshot/shannon_eta ?shannon_eta] '
        '  [?e :vertex_kaisya_org_snapshot/u_spirit ?u_spirit] '
        '  [?e :vertex_kaisya_org_snapshot/u_wellbecoming ?u_wellbecoming] '
        '  [?e :vertex_kaisya_org_snapshot/u_feeling ?u_feeling] '
        '  [?e :vertex_kaisya_org_snapshot/u_buffer ?u_buffer] '
        '  [?e :vertex_kaisya_org_snapshot/snapshot_at ?snapshot_at] '
        ':order-by [?e :vertex_kaisya_org_snapshot/snapshot_at :desc] '
        ':limit 1]'
    )
    rows = [dict(zip(keys, row)) for row in raw_rows]
    if rows:
        return {"governanceContext": "Latest org snapshot: " + json.dumps(rows[0], ensure_ascii=False)}
    return {"governanceContext": ""}


def governance_persist(state: CompanyOpsState) -> dict:
    """Governance has extra fields: omega_score / floor_violated + a dedicated
    INSERT into vertex_etzhayyim_governance_event."""
    content = _envelope_content(state, "governanceLlmOut")
    result = _parse_llm_json(content) if content else {}
    task_type = state.get("task_type", "")
    omega = float(result.get("omega_score", 0.0)) if isinstance(result, dict) else 0.0
    floor_violated = bool(result.get("floor_violated", False)) if isinstance(result, dict) else False
    ok = bool(result.get("ok", True)) if isinstance(result, dict) else False

    gov_row = {
        "vertex_id": _vid("governance"),
        "task_type": task_type,
        "omega_score": str(omega),
        "floor_violated": str(floor_violated).lower(),
        "decisions_json": json.dumps(result.get("decisions") or [] if isinstance(result, dict) else []),
        "summary": result.get("summary", "") if isinstance(result, dict) else "",
        "created_at": _now_iso(),
    }
    _db_insert("vertex_etzhayyim_governance_event", gov_row)

    return {
        "result": result,
        "omega_score": omega,
        "floor_violated": floor_violated,
        "action_items": (result.get("action_items") or []) if isinstance(result, dict) else [],
        "ok": ok,
        "error": result.get("error") if isinstance(result, dict) and not ok else None,
        "governance_audit_record": {
            "domain": "governance",
            "ok": ok,
            "omega_score": omega,
            "action": result.get("action", "") if isinstance(result, dict) else "",
        },
        "audit_record": {
            "domain": "governance",
            "ok": ok,
            "omega_score": omega,
            "action": result.get("action", "") if isinstance(result, dict) else "",
        },
    }


def personnel_fetch_ctx(state: CompanyOpsState) -> dict:
    """Pre-LLM SQL context: active personnel snapshot for list-style tasks."""
    task_type = state.get("task_type", "")
    if task_type.startswith(("personnel.list", "role.list", "assignment.list", "raci.list")):
        keys = ["person_did", "display_name", "department", "title", "status"]
        raw_rows = get_kotoba_client().q(
            '[:find ?person_did ?display_name ?department ?title ?status '
            ':where '
            '  [?e :vertex/type "etzhayyim_person"] '
            '  [?e :vertex_etzhayyim_person/person_did ?person_did] '
            '  [?e :vertex_etzhayyim_person/display_name ?display_name] '
            '  [?e :vertex_etzhayyim_person/department ?department] '
            '  [?e :vertex_etzhayyim_person/title ?title] '
            '  [?e :vertex_etzhayyim_person/status "active"] '
            ':limit 50]'
        )
        rows = [dict(zip(keys, row)) for row in raw_rows]
        if rows:
            return {"personnelContext": "Active personnel: " + json.dumps(rows, ensure_ascii=False)}
    return {"personnelContext": ""}


def personnel_persist(state: CompanyOpsState) -> dict:
    return _persist_domain(state, "personnelLlmOut", "vertex_etzhayyim_assignment", "personnel", "personnel_audit_record")


# ── Router ─────────────────────────────────────────────────────────────────────

def _route_domain(state: CompanyOpsState) -> str:
    """Return the node name to execute next based on classified domain."""
    return state.get("domain", "governance")


# ── Graph factory ──────────────────────────────────────────────────────────────

def build_graph():
    """
    Compile the etzhayyim Company Ops StateGraph.

    Flow:
      supervisor → (domain router) → {hr|finance|legal|sales|governance}
                 → emit_audit → END
    """
    from langgraph.graph import END, StateGraph

    builder = StateGraph(CompanyOpsState)

    # Nodes
    builder.add_node("supervisor",  supervisor)
    builder.add_node("hr",          hr_agent)
    builder.add_node("finance",     finance_agent)
    builder.add_node("legal",       legal_agent)
    builder.add_node("sales",       sales_agent)
    builder.add_node("governance",  governance_agent)
    builder.add_node("personnel",   personnel_agent)
    builder.add_node("emit_audit",  emit_audit)

    # Entry
    builder.set_entry_point("supervisor")

    # Conditional edge: supervisor → domain node
    builder.add_conditional_edges(
        "supervisor",
        _route_domain,
        {
            "hr":         "hr",
            "finance":    "finance",
            "legal":      "legal",
            "sales":      "sales",
            "governance": "governance",
            "personnel":  "personnel",
            "unknown":    "governance",
        },
    )

    # All domain nodes → emit_audit → END
    for node in ("hr", "finance", "legal", "sales", "governance", "personnel"):
        builder.add_edge(node, "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
