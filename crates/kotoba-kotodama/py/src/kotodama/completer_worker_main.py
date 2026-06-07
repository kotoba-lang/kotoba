"""
completer LangServer worker — DID Compliance Actor.

Subscribes to Zeebe job types matching the BPMN service tasks in
60-apps/etzhayyim-project-completer/bpmn/evaluate-compliance.bpmn.

Job types:
  com.etzhayyim.apps.completer.queryRules        — fetch applicable rules from graph
  com.etzhayyim.apps.completer.matchRules        — match rules to actor capabilities
  com.etzhayyim.apps.completer.llmEvaluate       — LLM gap analysis per rule
  com.etzhayyim.apps.completer.evaluate          — score + persist audit + findings
  com.etzhayyim.apps.completer.evaluateRepoDids  — batch: fan-out per DID in repo
  com.etzhayyim.apps.completer.remediate         — generate remediation action plan

Query jobs (served by dispatcher; these workers also handle them for direct BPMN use):
  com.etzhayyim.apps.completer.getAuditReport
  com.etzhayyim.apps.completer.listFindings
  com.etzhayyim.apps.completer.listAudits
  com.etzhayyim.apps.completer.getComplianceScore

Run inside cluster:
    python -m kotodama.completer_worker_main

Env:
  AGENTGATEWAY_MCP_URL        — AgentGateway MCP URL (default agentgateway-mcp.mitama-udf.svc.cluster.local:8080)
  ZEEBE_TIMEOUT_SEC    — per-job activation timeout (default 300)
  DATABASE_URL         — RisingWave Hyperdrive PG URL
  VULTR_SERVERLESS_KEY — required by kotodama.llm
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama import llm

LOG = logging.getLogger("completer_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

GATEWAY = os.environ.get("AGENTGATEWAY_MCP_URL", "agentgateway-mcp.mitama-udf.svc.cluster.local:8080")
ACTIVATION_TIMEOUT = int(os.environ.get("ZEEBE_TIMEOUT_SEC", "300"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")

_SCORE_WEIGHTS = {"critical": -25, "high": -15, "medium": -5, "low": -2}

# ─── DB helpers ──────────────────────────────────────────────────────────

async def _get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(DATABASE_URL)


def _gid(prefix: str) -> str:
    import random, string
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}_{int(time.time() * 1000):x}_{suffix}"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ─── Task: queryRules ────────────────────────────────────────────────────

async def task_query_rules(
    actor_did: str = "",
    jurisdictions: list[str] | None = None,
    sector_codes: list[str] | None = None,
) -> dict[str, Any]:
    if not actor_did:
        return {"error": "actor_did required"}

    conn = await _get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT vertex_id, rule_id, title, jurisdiction, sector_code, obligation_kind, risk_level, description
            FROM vertex_compliance_rule
            WHERE status = 'active'
            LIMIT 200
            """,
        )
        rules = [dict(r) for r in rows]
        if jurisdictions:
            rules = [r for r in rules if not r.get("jurisdiction") or r["jurisdiction"] in jurisdictions]
        if sector_codes:
            rules = [r for r in rules if not r.get("sector_code") or r["sector_code"] in sector_codes]
        return {"rules": rules, "rule_count": len(rules)}
    finally:
        await conn.close()


# ─── Task: matchRules ────────────────────────────────────────────────────

async def task_match_rules(
    actor_did: str = "",
    rules: list[dict] | None = None,
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    if not actor_did or not rules:
        return {"matched_rules": [], "skipped": 0}
    caps_set = set(capabilities or [])
    matched = []
    for rule in rules:
        obligation = rule.get("obligation_kind", "")
        if obligation and caps_set and obligation not in caps_set:
            matched.append({**rule, "match_reason": "obligation_gap"})
        else:
            matched.append({**rule, "match_reason": "applicable"})
    return {"matched_rules": matched, "skipped": len(rules) - len(matched)}


# ─── Task: llmEvaluate ───────────────────────────────────────────────────

_EVAL_SYSTEM = (
    "You are a compliance evaluation assistant. Given an actor's capabilities and a set of "
    "compliance rules, identify non-compliant rules and output a JSON object with keys: "
    "findings (array of {rule_id, risk_level, summary, remediation_hint}), "
    "overall_summary (<=300 chars). Output ONLY the JSON object."
)


async def task_llm_evaluate(
    actor_did: str = "",
    matched_rules: list[dict] | None = None,
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    if not actor_did or not matched_rules:
        return {"findings": [], "overall_summary": "No rules to evaluate."}

    prompt = (
        f"Actor DID: {actor_did}\n"
        f"Capabilities: {json.dumps(capabilities or [])}\n"
        f"Rules to evaluate:\n{json.dumps(matched_rules[:30], indent=2)}"
    )
    try:
        resp = llm.call_tier(
            "reasoning",
            system=_EVAL_SYSTEM,
            user=prompt,
            max_tokens=1500,
            temperature=0.1,
        )
        parsed = llm.parse_json_content(resp.get("content"))
        if parsed:
            return {
                "findings": parsed.get("findings", []),
                "overall_summary": parsed.get("overall_summary", ""),
                "model": resp.get("model"),
            }
    except Exception as e:
        LOG.warning("llm_evaluate error: %s", e)
    return {"findings": [], "overall_summary": "Evaluation error — manual review required."}


# ─── Task: evaluate (score + persist) ────────────────────────────────────

async def task_evaluate(
    actor_did: str = "",
    actor_name: str = "",
    findings: list[dict] | None = None,
    overall_summary: str = "",
    jurisdictions: list[str] | None = None,
    rule_bundle_ids: list[str] | None = None,
    org_id: str = "anon",
    user_id: str = "anon",
) -> dict[str, Any]:
    if not actor_did:
        return {"error": "actor_did required"}

    findings = findings or []
    score = 100
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        rl = f.get("risk_level", "low")
        counts[rl] = counts.get(rl, 0) + 1
        score = max(0, score + _SCORE_WEIGHTS.get(rl, 0))

    effect = "allow"
    if counts["critical"] > 0:
        effect = "deny"
    elif counts["high"] > 0 or counts["medium"] > 0:
        effect = "allow-with-obligations"

    audit_id = _gid("audit")
    now = _now()
    rkey = audit_id

    conn = await _get_conn()
    try:
        await conn.execute(
            """
            INSERT INTO vertex_completer_audit (
                vertex_id, _seq, created_date, sensitivity_ord,
                owner_did, rkey, repo, did, collection, status,
                id, actor_did, actor_name, score, effect,
                total_findings, critical_findings, high_findings,
                evaluated_jurisdictions, rule_bundle_ids, summary,
                evaluated_at, org_id, user_id, actor_id, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
                      $16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27)
            """,
            f"at://did:web:completer.etzhayyim.com/com.etzhayyim.apps.completer.audit/{rkey}",
            int(time.time() * 1000),
            now[:10],
            0,
            "did:web:completer.etzhayyim.com",
            rkey,
            "did:web:completer.etzhayyim.com",
            actor_did,
            "com.etzhayyim.apps.completer.audit",
            "completed",
            audit_id,
            actor_did,
            actor_name or actor_did,
            score,
            effect,
            len(findings),
            counts["critical"],
            counts["high"],
            json.dumps(jurisdictions or []),
            json.dumps(rule_bundle_ids or []),
            overall_summary,
            now,
            org_id,
            user_id,
            "did:web:completer.etzhayyim.com",
            now,
            now,
        )

        for f in findings:
            fid = _gid("finding")
            frkey = fid
            await conn.execute(
                """
                INSERT INTO vertex_completer_finding (
                    vertex_id, _seq, created_date, sensitivity_ord,
                    owner_did, rkey, repo, did, collection, status,
                    id, audit_id, actor_did, rule_id, rule_title,
                    jurisdiction, risk_level, obligation_kind, summary,
                    remediation_hint, org_id, user_id, actor_id, created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
                          $16,$17,$18,$19,$20,$21,$22,$23,$24,$25)
                """,
                f"at://did:web:completer.etzhayyim.com/com.etzhayyim.apps.completer.finding/{frkey}",
                int(time.time() * 1000),
                now[:10],
                0,
                "did:web:completer.etzhayyim.com",
                frkey,
                "did:web:completer.etzhayyim.com",
                actor_did,
                "com.etzhayyim.apps.completer.finding",
                "open",
                fid,
                audit_id,
                actor_did,
                f.get("rule_id", ""),
                f.get("rule_title", ""),
                f.get("jurisdiction", ""),
                f.get("risk_level", "low"),
                f.get("obligation_kind", ""),
                f.get("summary", ""),
                f.get("remediation_hint", ""),
                org_id,
                user_id,
                "did:web:completer.etzhayyim.com",
                now,
                now,
            )
    finally:
        await conn.close()

    LOG.info("audit persisted: %s score=%d effect=%s findings=%d", audit_id, score, effect, len(findings))
    return {"audit_id": audit_id, "score": score, "effect": effect, "total_findings": len(findings)}


# ─── Task: evaluateRepoDids ──────────────────────────────────────────────

async def task_evaluate_repo_dids(
    actor_dids: list[str] | None = None,
    org_id: str = "anon",
    user_id: str = "anon",
) -> dict[str, Any]:
    dids = actor_dids or []
    if not dids:
        return {"error": "actor_dids required"}
    results = []
    for did in dids[:50]:  # cap at 50 per batch
        rules_result = await task_query_rules(actor_did=did)
        match_result = await task_match_rules(actor_did=did, rules=rules_result.get("rules", []))
        eval_result = await task_llm_evaluate(
            actor_did=did,
            matched_rules=match_result.get("matched_rules", []),
        )
        persist_result = await task_evaluate(
            actor_did=did,
            findings=eval_result.get("findings", []),
            overall_summary=eval_result.get("overall_summary", ""),
            org_id=org_id,
            user_id=user_id,
        )
        results.append({"actor_did": did, **persist_result})
    return {"results": results, "evaluated": len(results)}


# ─── Task: remediate ────────────────────────────────────────────────────

_REMEDIATE_SYSTEM = (
    "You are a compliance remediation specialist. Given a compliance finding, "
    "output a JSON object with keys: action_plan (string, <=500 chars), "
    "priority (critical|high|medium|low), estimated_effort (string, e.g. '2 days'). "
    "Output ONLY the JSON object."
)


async def task_remediate(
    finding_id: str = "",
    rule_title: str = "",
    summary: str = "",
    risk_level: str = "medium",
    org_id: str = "anon",
    user_id: str = "anon",
) -> dict[str, Any]:
    if not finding_id:
        return {"error": "finding_id required"}

    prompt = (
        f"Finding ID: {finding_id}\n"
        f"Rule: {rule_title}\n"
        f"Risk level: {risk_level}\n"
        f"Summary: {summary}"
    )
    try:
        resp = llm.call_tier("fast", system=_REMEDIATE_SYSTEM, user=prompt, max_tokens=400, temperature=0.2)
        parsed = llm.parse_json_content(resp.get("content"))
        if parsed:
            rid = _gid("rem")
            now = _now()
            conn = await _get_conn()
            try:
                await conn.execute(
                    """
                    INSERT INTO vertex_completer_remediation (
                        vertex_id, _seq, created_date, sensitivity_ord,
                        owner_did, rkey, repo, did, collection, status,
                        id, finding_id, action_plan, priority,
                        estimated_effort, org_id, user_id, actor_id, created_at, updated_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
                    """,
                    f"at://did:web:completer.etzhayyim.com/com.etzhayyim.apps.completer.remediation/{rid}",
                    int(time.time() * 1000),
                    now[:10],
                    0,
                    "did:web:completer.etzhayyim.com",
                    rid,
                    "did:web:completer.etzhayyim.com",
                    "did:web:completer.etzhayyim.com",
                    "com.etzhayyim.apps.completer.remediation",
                    "active",
                    rid,
                    finding_id,
                    parsed.get("action_plan", ""),
                    parsed.get("priority", risk_level),
                    parsed.get("estimated_effort", ""),
                    org_id,
                    user_id,
                    "did:web:completer.etzhayyim.com",
                    now,
                    now,
                )
            finally:
                await conn.close()
            return {"remediation_id": rid, **parsed}
    except Exception as e:
        LOG.warning("remediate error: %s", e)
    return {"error": "remediation generation failed"}


# ─── Query tasks ─────────────────────────────────────────────────────────

async def task_get_audit_report(actor_did: str = "", audit_id: str = "") -> dict[str, Any]:
    conn = await _get_conn()
    try:
        if audit_id:
            row = await conn.fetchrow(
                "SELECT * FROM vertex_completer_audit WHERE id = $1 LIMIT 1", audit_id
            )
        elif actor_did:
            row = await conn.fetchrow(
                "SELECT * FROM vertex_completer_audit WHERE actor_did = $1 ORDER BY evaluated_at DESC LIMIT 1",
                actor_did,
            )
        else:
            return {"error": "actor_did or audit_id required"}
        if not row:
            return {"error": "not found"}
        findings = await conn.fetch(
            "SELECT * FROM vertex_completer_finding WHERE audit_id = $1 ORDER BY risk_level, created_at LIMIT 100",
            row["id"],
        )
        return {"audit": dict(row), "findings": [dict(f) for f in findings]}
    finally:
        await conn.close()


async def task_list_findings(
    actor_did: str = "",
    audit_id: str = "",
    risk_level: str = "",
    jurisdiction: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = await _get_conn()
    try:
        clauses = []
        params: list[Any] = []
        if actor_did:
            clauses.append(f"actor_did = ${len(params)+1}")
            params.append(actor_did)
        if audit_id:
            clauses.append(f"audit_id = ${len(params)+1}")
            params.append(audit_id)
        if risk_level:
            clauses.append(f"risk_level = ${len(params)+1}")
            params.append(risk_level)
        if jurisdiction:
            clauses.append(f"jurisdiction = ${len(params)+1}")
            params.append(jurisdiction)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = min(limit, 200)
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"SELECT * FROM vertex_completer_finding {where} ORDER BY created_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}",
            *params,
        )
        return {"findings": [dict(r) for r in rows], "offset": offset, "limit": limit}
    finally:
        await conn.close()


async def task_list_audits(
    actor_did: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = await _get_conn()
    try:
        limit = min(limit, 100)
        if actor_did:
            rows = await conn.fetch(
                "SELECT * FROM vertex_completer_audit WHERE actor_did = $1 ORDER BY evaluated_at DESC LIMIT $2 OFFSET $3",
                actor_did, limit, offset,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM vertex_completer_audit ORDER BY evaluated_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
        return {"audits": [dict(r) for r in rows], "offset": offset, "limit": limit}
    finally:
        await conn.close()


async def task_get_compliance_score(actor_did: str = "") -> dict[str, Any]:
    if not actor_did:
        return {"error": "actor_did required"}
    conn = await _get_conn()
    try:
        row = await conn.fetchrow(
            "SELECT id, score, effect, total_findings, evaluated_at FROM vertex_completer_audit WHERE actor_did = $1 ORDER BY evaluated_at DESC LIMIT 1",
            actor_did,
        )
        if not row:
            return {"actor_did": actor_did, "score": None, "effect": None, "evaluated": False}
        return {"actor_did": actor_did, **dict(row), "evaluated": True}
    finally:
        await conn.close()


# ─── Worker entrypoint ───────────────────────────────────────────────────

async def run_worker() -> None:
    channel = create_langserver_channel(grpc_address=GATEWAY)
    worker = LangServerWorker(channel)

    registrations = {
        "com.etzhayyim.apps.completer.queryRules":       task_query_rules,
        "com.etzhayyim.apps.completer.matchRules":        task_match_rules,
        "com.etzhayyim.apps.completer.llmEvaluate":       task_llm_evaluate,
        "com.etzhayyim.apps.completer.evaluate":          task_evaluate,
        "com.etzhayyim.apps.completer.evaluateRepoDids":  task_evaluate_repo_dids,
        "com.etzhayyim.apps.completer.remediate":         task_remediate,
        "com.etzhayyim.apps.completer.getAuditReport":    task_get_audit_report,
        "com.etzhayyim.apps.completer.listFindings":      task_list_findings,
        "com.etzhayyim.apps.completer.listAudits":        task_list_audits,
        "com.etzhayyim.apps.completer.getComplianceScore": task_get_compliance_score,
    }

    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=ACTIVATION_TIMEOUT * 1000)(fn)
        LOG.info("registered: %s", task_type)

    LOG.info("completer worker starting (gateway=%s)", GATEWAY)
    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
