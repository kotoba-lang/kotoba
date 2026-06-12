"""billing.etzhayyim.com retail cloud billing v2 primitives (ADR-2605080000).

T2 actor (ADR-2604282300): kotodama module + BPMN + Zeebe, no CF Worker.
All writes hit RisingWave directly via Hyperdrive (ADR-0036).

BPMN coverage (ADR-0056 BPMN-as-actor):
  rollupDaily.bpmn        cron 0 0 1 * * ?  → billing.rollup.daily
  rollupMonthly.bpmn      cron 0 0 2 1 * ?  → billing.rollup.monthly
  detectOverage.bpmn      R/PT5M            → billing.detect.overage
  generateInvoice.bpmn    cron 0 0 3 1 * ?  → billing.generate.invoice
  applyDiscount.bpmn      XRPC              → billing.discount.validateRole
                                            → billing.discount.apply

XRPC additionally bound (read-side, no dedicated BPMN — wired through
generic.db.select):
  com.etzhayyim.apps.billing.recordUsageEvent  → billing.event.record
  com.etzhayyim.apps.billing.getUsage          → billing.usage.get
  com.etzhayyim.apps.billing.getQuotaStatus    → billing.quota.status
  com.etzhayyim.apps.billing.listInvoices      → billing.invoice.list
  com.etzhayyim.apps.billing.getInvoice        → billing.invoice.get
  com.etzhayyim.apps.billing.applyCredit       → billing.credit.apply
  com.etzhayyim.apps.billing.coverage          → billing.coverage.snapshot

Output target tables (created by 20260508140000_vertex_billing_schema.ts):
  vertex_billing_event       per-request usage event
  vertex_billing_org_plan    per-org plan + applied_discount_pct
  vertex_billing_discount    discount audit log
  vertex_billing_credit      one-time credit application log
  vertex_billing_invoice     monthly invoice

Streaming MVs:
  mv_billing_daily_org / mv_billing_monthly_org / mv_billing_overage_alert /
  mv_billing_margin_actual / mv_billing_quota_breach

Content-addressed PKs (ADR-0041) — re-runs idempotent.

Plan-limit registry: lives in this module as `_PLAN_LIMITS`. Keep in sync
with the 90-docs/adr/2605080000-yatabase-yata-retail-cloud.md tables.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import calendar
import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

_BILLING_ACTOR = "did:web:billing.etzhayyim.com"

# JPY-micro = ¥ × 1e6. All money internally is JPY-micro to keep integer
# arithmetic. Display layer divides by 1e6 to get yen.
_JPY_MICRO = 1_000_000

# List prices (ADR D1). unit_cost is etzhayyim-side cost; billed = list × qty.
_LIST_PRICE_JPY_MICRO: dict[str, int] = {
    # storage = ¥10/GB-month, charged hourly = ¥10 / (30*24) ≈ ¥0.0139/GB-h
    # Stored as integer JPY-micro per metric unit.
    "storage_gb_hour":     int(10 * _JPY_MICRO / (30 * 24)),  # ¥/GB-h
    "egress_gb":           15 * _JPY_MICRO,                    # ¥/GB
    "llm_input_tokens":    int(0.50 * _JPY_MICRO / 1000),     # ¥/token
    "llm_output_tokens":   int(1.50 * _JPY_MICRO / 1000),     # ¥/token
    "gpu_hour":            300 * _JPY_MICRO,                   # ¥/hour (6000 Ada inference, ADR-2605010000)
    "gpu_hour_h100_nvl":   1800 * _JPY_MICRO,                  # ¥/hour (H100 NVL training, ADR 2605092345; $3.07/hr × 150 ≈ ¥460 spot × 4× margin)
    "api_request":         int(2.0 * _JPY_MICRO / 10000),     # ¥/request
    "mcp_call":            int(3.0 * _JPY_MICRO / 100),       # ¥/call
    "did_mint":            300 * _JPY_MICRO,                   # ¥/mint
    "yata_node_hour":      int(1000 * _JPY_MICRO / (1_000_000 * 24 * 30)),  # ¥/(node·hour)
    "yata_edge_hour":      int(500 * _JPY_MICRO / (1_000_000 * 24 * 30)),
    "yata_query_cu_ms":    int(300 * _JPY_MICRO / (1000 * 60 * 60 * 1000)),  # ¥300/CU-h converted
    "yata_reasoning_run":  500 * _JPY_MICRO,                   # ¥/run
    "obj_class_a":         int(10 * _JPY_MICRO / 1_000_000),   # ¥/req (PUT/COPY/POST/LIST)
    "obj_class_b":         int(1 * _JPY_MICRO / 1_000_000),    # ¥/req (GET/HEAD)
}

# Cost-side estimates (host side) — used for margin tracking.
_UNIT_COST_JPY_MICRO: dict[str, int] = {
    "storage_gb_hour":     int(0.9 * _JPY_MICRO / (30 * 24)),  # B2 ¥0.9/GB-month
    "egress_gb":           0,                                   # BWA = ¥0
    "llm_input_tokens":    int(0.015 * _JPY_MICRO / 1000),
    "llm_output_tokens":   int(0.045 * _JPY_MICRO / 1000),
    "gpu_hour":            75 * _JPY_MICRO,                     # RunPod 6000 Ada amortized (always-on inference)
    "gpu_hour_h100_nvl":   460 * _JPY_MICRO,                    # RunPod H100 NVL Secure spot ($3.07/hr × 150 ≈ ¥460); ad-hoc training only — no amortization assumed
    "api_request":         int(0.045 * _JPY_MICRO / 10000),
    "mcp_call":            int(0.10 * _JPY_MICRO / 100),
    "did_mint":            30 * _JPY_MICRO,                     # gas + ops
    "yata_node_hour":      int(0.5 * _JPY_MICRO / (1_000_000 * 24 * 30)),
    "yata_edge_hour":      int(0.25 * _JPY_MICRO / (1_000_000 * 24 * 30)),
    "yata_query_cu_ms":    int(45 * _JPY_MICRO / (1000 * 60 * 60 * 1000)),
    "yata_reasoning_run":  100 * _JPY_MICRO,
    "obj_class_a":         int(2 * _JPY_MICRO / 1_000_000),
    "obj_class_b":         int(0.2 * _JPY_MICRO / 1_000_000),
}

# Plan included quotas. Per-period billing window aggregation;
# product `yata` / `obj` keyed.
# Values match ADR D3 (yatabase) + D4 (obj) plan tables.
_PLAN_LIMITS: dict[str, dict[str, dict[str, float]]] = {
    "free":       {"yata": {"yata_node_hour": 100_000, "yata_edge_hour": 500_000, "yata_query_cu_ms": 5 * 60 * 60 * 1000},
                   "obj":  {"storage_gb_hour": 5 * 30 * 24, "egress_gb": 50, "obj_class_a": 100_000, "obj_class_b": 1_000_000}},
    "starter":    {"yata": {"yata_node_hour": 1_000_000, "yata_edge_hour": 5_000_000, "yata_query_cu_ms": 50 * 60 * 60 * 1000},
                   "obj":  {"storage_gb_hour": 50 * 30 * 24, "egress_gb": 500, "obj_class_a": 1_000_000, "obj_class_b": 10_000_000}},
    "developer":  {"yata": {"yata_node_hour": 10_000_000, "yata_edge_hour": 50_000_000, "yata_query_cu_ms": 500 * 60 * 60 * 1000},
                   "obj":  {"storage_gb_hour": 500 * 30 * 24, "egress_gb": 5_000, "obj_class_a": 10_000_000, "obj_class_b": 100_000_000}},
    "team":       {"yata": {"yata_node_hour": 100_000_000, "yata_edge_hour": 1_000_000_000, "yata_query_cu_ms": 5_000 * 60 * 60 * 1000},
                   "obj":  {"storage_gb_hour": 5_000 * 30 * 24, "egress_gb": 50_000, "obj_class_a": 100_000_000, "obj_class_b": 1_000_000_000}},
    "business":   {"yata": {"yata_node_hour": 1_000_000_000, "yata_edge_hour": 10_000_000_000, "yata_query_cu_ms": 50_000 * 60 * 60 * 1000},
                   "obj":  {"storage_gb_hour": 50_000 * 30 * 24, "egress_gb": 500_000, "obj_class_a": 1_000_000_000, "obj_class_b": 10_000_000_000}},
    # Enterprise has no programmatic cap — hard cap is contract-driven.
    "enterprise": {},
}

# Sales discount approval bands (ADR D6).
_APPROVAL_BAND_PCT: dict[str, float] = {
    "sales-rep": 40.0,
    "csm":       40.0,
    "cfo":       50.0,
    "ceo":      100.0,
}

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _content_pk(prefix: str, parts: list[str]) -> str:
    """Content-addressed AT URI vertex_id (ADR-0041)."""
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"at://{_BILLING_ACTOR}/com.etzhayyim.apps.billing.{prefix}/{h}"


def _resolve_plan(org_did: str) -> tuple[str, float, date, date]:
    """Look up plan + applied_discount_pct + billing window for an org.

    Returns (plan, discount_pct, period_start, period_end). Defaults to
    `free` plan with 0% discount and current month if not registered.
    """
    today = _today()
    period_start = date(today.year, today.month, 1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    period_end = date(today.year, today.month, last_day)

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT plan, applied_discount_pct, billing_period_start, billing_period_end
            FROM vertex_billing_org_plan
            WHERE org_did = %s AND status = 'active'
            ORDER BY billing_period_start DESC
            LIMIT 1
            """,
            (org_did,),
        )
        row = (_res[0] if _res else None)

    if row is None:
        return ("free", 0.0, period_start, period_end)
    return (row[0], float(row[1] or 0.0), row[2] or period_start, row[3] or period_end)


def _alert_level(utilization_pct: float) -> str:
    if utilization_pct >= 150:
        return "critical150"
    if utilization_pct >= 100:
        return "exceeded"
    if utilization_pct >= 80:
        return "warn80"
    return "ok"


# ──────────────────────────────────────────────────────────────────────
# 1. recordUsageEvent — internal metering ingest (lexicon)
# ──────────────────────────────────────────────────────────────────────


async def task_billing_event_record(
    orgDid: str = "",
    actorDid: str | None = None,
    tsMs: int | None = None,
    metric: str = "",
    qty: float = 0.0,
    product: str = "",
    refResource: str | None = None,
    vertexId: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Insert one usage event row.

    Idempotent on `vertexId`. Server-side fills `unit_cost_jpy_micro`,
    `list_price_jpy_micro`, `applied_discount_pct`, and
    `billed_amount_jpy_micro` from registries — clients cannot override.
    """
    if not orgDid or not metric or not product or qty <= 0:
        return {"ok": False, "error": "orgDid, metric, product, qty (>0) required"}
    if metric not in _LIST_PRICE_JPY_MICRO:
        return {"ok": False, "error": f"unknown metric: {metric}"}

    ts_ms = int(tsMs or _now_ms())
    list_price = _LIST_PRICE_JPY_MICRO[metric]
    unit_cost = _UNIT_COST_JPY_MICRO.get(metric, 0)

    _, discount_pct, _, _ = _resolve_plan(orgDid)
    discount_factor = (100.0 - discount_pct) / 100.0
    billed = int(round(list_price * qty * discount_factor))

    vid = vertexId or _content_pk(
        "event",
        [orgDid, metric, str(ts_ms), refResource or "", actorDid or ""],
    )
    today = _today()

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_billing_event (
              vertex_id, _seq, created_date, sensitivity_ord, owner_did,
              org_did, actor_did, ts_ms, metric, qty, product, ref_resource,
              unit_cost_jpy_micro, list_price_jpy_micro,
              applied_discount_pct, billed_amount_jpy_micro,
              created_at, org_id, user_id, actor_id
            ) VALUES (
              %s, NULL, %s, 2, %s,
              %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s,
              %s, %s, %s, %s
            )
            """,
            (
                vid, today, _BILLING_ACTOR,
                orgDid, actorDid, ts_ms, metric, qty, product, refResource,
                unit_cost, list_price, discount_pct, billed,
                _now_iso(), orgDid, actorDid or orgDid, "sys.billing.meter",
            ),
        )

    return {
        "ok": True,
        "vertexId": vid,
        "billedAmountJpyMicro": billed,
        "appliedDiscountPct": discount_pct,
    }


# ──────────────────────────────────────────────────────────────────────
# 2. billing.rollup.daily — daily previous-day rollup audit
# ──────────────────────────────────────────────────────────────────────


async def task_billing_rollup_daily(**kwargs: Any) -> dict[str, Any]:
    """Audit-only rollup. mv_billing_daily_org is streaming so the actual
    aggregation already happens incrementally; this task only counts and
    sums the previous-day window for an OCEL trail.
    """
    yesterday = _today() - timedelta(days=1)

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT COUNT(DISTINCT org_did), COALESCE(SUM(billed_jpy_micro), 0)
            FROM mv_billing_daily_org
            WHERE day = %s
            """,
            (yesterday,),
        )
        row = (_res[0] if _res else None) or (0, 0)
    return {
        "ok": True,
        "day": yesterday.isoformat(),
        "summarizedOrgs": int(row[0] or 0),
        "billedJpyMicro": int(row[1] or 0),
    }


# ──────────────────────────────────────────────────────────────────────
# 3. billing.rollup.monthly — month-1st draft
# ──────────────────────────────────────────────────────────────────────


async def task_billing_rollup_monthly(**kwargs: Any) -> dict[str, Any]:
    """Snapshot last-month per-org × product totals. Does NOT mint
    invoices — that's `generateInvoice`. This task only confirms the MV
    has data and emits an audit summary.
    """
    today = _today()
    if today.month == 1:
        last_month = date(today.year - 1, 12, 1)
    else:
        last_month = date(today.year, today.month - 1, 1)

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT COUNT(DISTINCT org_did), COALESCE(SUM(billed_jpy_micro), 0)
            FROM mv_billing_monthly_org
            WHERE month = %s
            """,
            (last_month,),
        )
        row = (_res[0] if _res else None) or (0, 0)
    return {
        "ok": True,
        "month": last_month.isoformat(),
        "invoicesDrafted": 0,  # actual invoice rows minted by generateInvoice
        "totalJpyMicro": int(row[1] or 0),
    }


# ──────────────────────────────────────────────────────────────────────
# 4. billing.detect.overage — every 5 min
# ──────────────────────────────────────────────────────────────────────


async def task_billing_detect_overage(**kwargs: Any) -> dict[str, Any]:
    """Scan mv_billing_overage_alert × _PLAN_LIMITS and count alerts.

    Phase 1 emits alert counts only. Phase 5 will write
    `vertex_billing_alert` rows + push to org owner / Slack /
    notification webhook.
    """
    alerts = 0
    orgs_scanned = 0
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT org_did, plan, product, metric, consumed_qty
            FROM mv_billing_overage_alert
            """
        )
        rows = _res

    seen_orgs: set[str] = set()
    for row in rows:
        org_did, plan, product, metric, consumed = row
        seen_orgs.add(org_did)
        plan_key = (plan or "free").lower()
        included = _PLAN_LIMITS.get(plan_key, {}).get(product or "", {}).get(metric or "")
        if included is None or included == 0:
            continue
        utilization_pct = float(consumed or 0) / float(included) * 100.0
        if _alert_level(utilization_pct) != "ok":
            alerts += 1
    orgs_scanned = len(seen_orgs)

    return {
        "ok": True,
        "alertsEmitted": alerts,
        "orgsScanned": orgs_scanned,
    }


# ──────────────────────────────────────────────────────────────────────
# 5. billing.generate.invoice — month 1st 03:00 UTC
# ──────────────────────────────────────────────────────────────────────


async def task_billing_generate_invoice(**kwargs: Any) -> dict[str, Any]:
    """Mint vertex_billing_invoice rows for every active org with
    consumption in last month. Apply outstanding credits FIFO, compute
    10% 消費税 (内税表示, tax_jpy_micro = total * 10/110).
    """
    today = _today()
    if today.month == 1:
        period_start = date(today.year - 1, 12, 1)
    else:
        period_start = date(today.year, today.month - 1, 1)
    last_day = calendar.monthrange(period_start.year, period_start.month)[1]
    period_end = date(period_start.year, period_start.month, last_day)
    issued_at = _now_iso()
    due_at = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()

    invoices_minted = 0
    total_jpy_micro_all = 0
    credits_consumed_total = 0

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT org_did,
                   COALESCE(SUM(billed_jpy_micro), 0) AS subtotal,
                   COALESCE(SUM(cost_jpy_micro), 0)   AS total_cost
            FROM mv_billing_monthly_org
            WHERE month = %s
            GROUP BY org_did
            """,
            (period_start,),
        )
        org_rows = _res

    for org_row in org_rows:
        org_did, subtotal_micro, _cost_micro = org_row
        subtotal_micro = int(subtotal_micro or 0)
        if subtotal_micro <= 0:
            continue

        # Apply outstanding credits FIFO (oldest issued_at first).
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                SELECT credit_id, amount_jpy_micro, consumed_jpy_micro
                FROM vertex_billing_credit
                WHERE org_did = %s AND status = 'active'
                  AND (expires_at IS NULL OR expires_at > %s)
                ORDER BY issued_at ASC
                """,
                (org_did, issued_at),
            )
            credit_rows = _res

        remaining = subtotal_micro
        org_credit_consumed = 0
        for credit_id, amt, consumed in credit_rows:
            avail = int((amt or 0) - (consumed or 0))
            if avail <= 0:
                continue
            apply = min(avail, remaining)
            if apply <= 0:
                break
            new_consumed = int((consumed or 0) + apply)
            new_status = "exhausted" if new_consumed >= int(amt or 0) else "active"
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    """
                    UPDATE vertex_billing_credit
                    SET consumed_jpy_micro = %s, status = %s
                    WHERE credit_id = %s AND org_did = %s
                    """,
                    (new_consumed, new_status, credit_id, org_did),
                )
            remaining -= apply
            org_credit_consumed += apply
            credits_consumed_total += apply
            if remaining <= 0:
                break

        # 内税 — tax_jpy_micro = total × 10/110 of subtotal_after_credit
        subtotal_after_credit = max(0, remaining)
        # Already discount-applied at event time, so total = remaining.
        total = subtotal_after_credit
        tax = int(round(total * 10 / 110))

        invoice_id = f"INV-{period_start.strftime('%Y%m')}-{hashlib.sha256(org_did.encode()).hexdigest()[:8]}"
        vid = _content_pk("invoice", [org_did, period_start.isoformat()])

        line_items = json.dumps([{"month": period_start.isoformat()}])

        if True:

            client = get_kotoba_client()
            _res = client.q(
                """
                INSERT INTO vertex_billing_invoice (
                  vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                  invoice_id, org_did, period_start, period_end,
                  subtotal_jpy_micro, total_discount_jpy_micro, tax_jpy_micro,
                  total_jpy_micro, currency, status,
                  qualified_invoice_number, issued_at, due_at, paid_at,
                  stripe_invoice_id, line_items_json,
                  created_at, org_id, user_id, actor_id
                ) VALUES (
                  %s, NULL, %s, 2, %s,
                  %s, %s, %s, %s,
                  %s, %s, %s,
                  %s, %s, %s,
                  %s, %s, %s, %s,
                  %s, %s,
                  %s, %s, %s, %s
                )
                """,
                (
                    vid, today, _BILLING_ACTOR,
                    invoice_id, org_did, period_start, period_end,
                    subtotal_micro, org_credit_consumed, tax,
                    total, "JPY", "draft",
                    "T9007028460042", issued_at, due_at, None,
                    None, line_items,
                    _now_iso(), org_did, org_did, "sys.billing.invoicer",
                ),
            )
        invoices_minted += 1
        total_jpy_micro_all += total

    return {
        "ok": True,
        "invoicesGenerated": invoices_minted,
        "totalJpyMicro": total_jpy_micro_all,
        "creditsConsumedJpyMicro": credits_consumed_total,
    }


# ──────────────────────────────────────────────────────────────────────
# 6. billing.discount.validateRole — XRPC gate
# ──────────────────────────────────────────────────────────────────────


async def task_billing_discount_validate_role(
    orgDid: str = "",
    discountPct: float = 0.0,
    approver: str = "",
    approverRole: str = "sales-rep",
    **kwargs: Any,
) -> dict[str, Any]:
    """Check whether `approverRole` is allowed to grant `discountPct`."""
    role_band = _APPROVAL_BAND_PCT.get(approverRole)
    if role_band is None:
        return {"approvalAllowed": False,
                "rejectReason": f"unknown approverRole: {approverRole}"}
    if discountPct < 0 or discountPct > 100:
        return {"approvalAllowed": False,
                "rejectReason": "discountPct must be 0-100"}
    if discountPct > role_band:
        return {"approvalAllowed": False,
                "rejectReason": f"approverRole={approverRole} band={role_band}% < requested {discountPct}%"}
    return {"approvalAllowed": True, "rejectReason": ""}


# ──────────────────────────────────────────────────────────────────────
# 7. billing.discount.apply — XRPC, INSERT discount + UPDATE org_plan
# ──────────────────────────────────────────────────────────────────────


async def task_billing_discount_apply(
    orgDid: str = "",
    discountPct: float = 0.0,
    kind: str = "discretionary",
    approver: str = "",
    approverRole: str = "sales-rep",
    rationale: str | None = None,
    validFrom: str | None = None,
    validUntil: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    valid_from_d = date.fromisoformat(validFrom) if validFrom else _today()
    valid_until_d = date.fromisoformat(validUntil) if validUntil else None

    plan, prev_pct, period_start, period_end = _resolve_plan(orgDid)

    discount_id = f"DSC-{int(_now_ms())}-{hashlib.sha256(orgDid.encode()).hexdigest()[:6]}"
    vid = _content_pk("discount", [orgDid, discount_id])

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_billing_discount (
              vertex_id, _seq, created_date, sensitivity_ord, owner_did,
              discount_id, org_did, discount_pct, previous_discount_pct,
              kind, approver, approver_role, approval_state, reject_reason,
              rationale, valid_from, valid_until,
              created_at, org_id, user_id, actor_id
            ) VALUES (
              %s, NULL, %s, 2, %s,
              %s, %s, %s, %s,
              %s, %s, %s, %s, %s,
              %s, %s, %s,
              %s, %s, %s, %s
            )
            """,
            (
                vid, _today(), _BILLING_ACTOR,
                discount_id, orgDid, float(discountPct), float(prev_pct),
                kind, approver, approverRole, "approved", None,
                rationale, valid_from_d, valid_until_d,
                _now_iso(), orgDid, approver, "sys.billing.discount",
            ),
        )

        # Upsert applied_discount_pct on org_plan. RisingWave does not
        # support ON CONFLICT — use delete-then-insert (ADR-0002 RW
        # write semantics) keyed on (org_did, status='active').
        _res = client.q(
            """
            DELETE FROM vertex_billing_org_plan
            WHERE org_did = %s AND status = 'active'
            """,
            (orgDid,),
        )
        plan_vid = _content_pk("orgPlan", [orgDid, period_start.isoformat()])
        _res = client.q(
            """
            INSERT INTO vertex_billing_org_plan (
              vertex_id, _seq, created_date, sensitivity_ord, owner_did,
              org_did, plan, billing_period_start, billing_period_end,
              applied_discount_pct, base_fee_jpy_micro, currency,
              stripe_customer_id, stripe_subscription_id, status,
              created_at, org_id, user_id, actor_id
            ) VALUES (
              %s, NULL, %s, 2, %s,
              %s, %s, %s, %s,
              %s, %s, %s,
              %s, %s, %s,
              %s, %s, %s, %s
            )
            """,
            (
                plan_vid, _today(), _BILLING_ACTOR,
                orgDid, plan, period_start, period_end,
                float(discountPct), 0, "JPY",
                None, None, "active",
                _now_iso(), orgDid, approver, "sys.billing.discount",
            ),
        )

    return {
        "ok": True,
        "discountId": discount_id,
        "previousDiscountPct": float(prev_pct),
        "approvalState": "approved",
    }


# ──────────────────────────────────────────────────────────────────────
# 8. billing.credit.apply — XRPC
# ──────────────────────────────────────────────────────────────────────


async def task_billing_credit_apply(
    orgDid: str = "",
    amountJpyMicro: int = 0,
    kind: str = "service_credit",
    approver: str = "",
    approverRole: str = "csm",
    rationale: str | None = None,
    expiresAt: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    if amountJpyMicro <= 0:
        return {"ok": False, "error": "amountJpyMicro must be > 0"}
    expires = expiresAt or (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
    credit_id = f"CRD-{int(_now_ms())}-{hashlib.sha256(orgDid.encode()).hexdigest()[:6]}"
    vid = _content_pk("credit", [orgDid, credit_id])

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_billing_credit (
              vertex_id, _seq, created_date, sensitivity_ord, owner_did,
              credit_id, org_did, amount_jpy_micro, consumed_jpy_micro,
              kind, approver, approver_role, rationale,
              issued_at, expires_at, status,
              created_at, org_id, user_id, actor_id
            ) VALUES (
              %s, NULL, %s, 2, %s,
              %s, %s, %s, %s,
              %s, %s, %s, %s,
              %s, %s, %s,
              %s, %s, %s, %s
            )
            """,
            (
                vid, _today(), _BILLING_ACTOR,
                credit_id, orgDid, int(amountJpyMicro), 0,
                kind, approver, approverRole, rationale,
                _now_iso(), expires, "active",
                _now_iso(), orgDid, approver, "sys.billing.credit",
            ),
        )

        _res = client.q(
            """
            SELECT COALESCE(SUM(amount_jpy_micro - consumed_jpy_micro), 0)
            FROM vertex_billing_credit
            WHERE org_did = %s AND status = 'active'
              AND (expires_at IS NULL OR expires_at > %s)
            """,
            (orgDid, _now_iso()),
        )
        row = (_res[0] if _res else None) or (0,)

    return {
        "ok": True,
        "creditId": credit_id,
        "amountJpyMicro": int(amountJpyMicro),
        "remainingBalanceJpyMicro": int(row[0] or 0),
        "expiresAt": expires,
    }


# ──────────────────────────────────────────────────────────────────────
# 9. billing.usage.get — XRPC
# ──────────────────────────────────────────────────────────────────────


async def task_billing_usage_get(
    orgDid: str = "",
    fromDate: str | None = None,
    toDate: str | None = None,
    product: str | None = None,
    groupBy: str = "day",
    forceRaw: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    today = _today()
    from_d = date.fromisoformat(fromDate) if fromDate else date(today.year, today.month, 1)
    to_d = date.fromisoformat(toDate) if toDate else today

    rows: list[dict[str, Any]] = []
    total = 0
    if True:
        client = get_kotoba_client()
        if groupBy == "day":
            _res = client.q(
                """
                SELECT day::varchar AS bucket, metric, product,
                       SUM(total_qty) AS qty, SUM(billed_jpy_micro) AS billed
                FROM mv_billing_daily_org
                WHERE org_did = %s AND day BETWEEN %s AND %s
                  AND (%s IS NULL OR product = %s)
                GROUP BY day, metric, product
                ORDER BY day, metric, product
                """,
                (orgDid, from_d, to_d, product, product),
            )
        elif groupBy == "metric":
            _res = client.q(
                """
                SELECT metric AS bucket, metric, product,
                       SUM(total_qty) AS qty, SUM(billed_jpy_micro) AS billed
                FROM mv_billing_daily_org
                WHERE org_did = %s AND day BETWEEN %s AND %s
                  AND (%s IS NULL OR product = %s)
                GROUP BY metric, product
                ORDER BY metric
                """,
                (orgDid, from_d, to_d, product, product),
            )
        elif groupBy == "product":
            _res = client.q(
                """
                SELECT product AS bucket, ''::varchar AS metric, product,
                       SUM(total_qty) AS qty, SUM(billed_jpy_micro) AS billed
                FROM mv_billing_daily_org
                WHERE org_did = %s AND day BETWEEN %s AND %s
                GROUP BY product
                ORDER BY product
                """,
                (orgDid, from_d, to_d),
            )
        else:
            return {"ok": False, "error": f"unsupported groupBy: {groupBy}"}

        for bucket, metric, prod, qty, billed in _res:
            qty_f = float(qty or 0)
            billed_i = int(billed or 0)
            rows.append({
                "bucket": str(bucket),
                "metric": metric or "",
                "product": prod or "",
                "qty": qty_f,
                "billedJpyMicro": billed_i,
            })
            total += billed_i

    return {
        "ok": True,
        "orgDid": orgDid,
        "fromDate": from_d.isoformat(),
        "toDate": to_d.isoformat(),
        "rows": rows,
        "totalBilledJpyMicro": total,
    }


# ──────────────────────────────────────────────────────────────────────
# 10. billing.quota.status — XRPC
# ──────────────────────────────────────────────────────────────────────


async def task_billing_quota_status(orgDid: str = "", **kwargs: Any) -> dict[str, Any]:
    plan, _disc, period_start, period_end = _resolve_plan(orgDid)
    plan_key = plan.lower()
    plan_limits = _PLAN_LIMITS.get(plan_key, {})

    rows: list[dict[str, Any]] = []
    for prod, metric_map in plan_limits.items():
        for metric, included in metric_map.items():
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    """
                    SELECT COALESCE(SUM(total_qty), 0), COALESCE(SUM(billed_jpy_micro), 0)
                    FROM mv_billing_daily_org
                    WHERE org_did = %s AND product = %s AND metric = %s
                      AND day BETWEEN %s AND %s
                    """,
                    (orgDid, prod, metric, period_start, period_end),
                )
                row = (_res[0] if _res else None) or (0, 0)
            consumed = float(row[0] or 0)
            billed = int(row[1] or 0)
            included_f = float(included or 0)
            util = (consumed / included_f * 100.0) if included_f > 0 else 0.0
            overage_qty = max(0.0, consumed - included_f)
            rows.append({
                "metric": metric,
                "product": prod,
                "included": included_f,
                "consumed": consumed,
                "utilizationPct": util,
                "overageQty": overage_qty,
                "overageBilledJpyMicro": billed if util > 100 else 0,
                "alertLevel": _alert_level(util),
            })
    return {
        "ok": True,
        "orgDid": orgDid,
        "plan": plan,
        "billingPeriodStart": period_start.isoformat(),
        "billingPeriodEnd": period_end.isoformat(),
        "rows": rows,
    }


# ──────────────────────────────────────────────────────────────────────
# 11. billing.invoice.list — XRPC
# ──────────────────────────────────────────────────────────────────────


async def task_billing_invoice_list(
    orgDid: str = "",
    status: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    safe_limit = min(max(int(limit), 1), 200)
    invoices: list[dict[str, Any]] = []
    params: list[Any] = [orgDid]
    if status:
        params.extend([status, status])
    if cursor:
        params.append(cursor)
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT invoice_id, vertex_id, period_start, period_end,
                   total_jpy_micro, total_discount_jpy_micro, status,
                   issued_at, due_at, paid_at
            FROM vertex_billing_invoice
            WHERE org_did = %s
              AND ({'%s IS NULL OR status = %s' if status else 'TRUE'})
              AND ({'invoice_id < %s' if cursor else 'TRUE'})
            ORDER BY period_start DESC, invoice_id DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        )
        for row in _res:
            invoices.append({
                "invoiceId": row[0],
                "vertexId": row[1],
                "periodStart": str(row[2]),
                "periodEnd": str(row[3]),
                "totalJpyMicro": int(row[4] or 0),
                "totalDiscountJpyMicro": int(row[5] or 0),
                "status": row[6],
                "issuedAt": row[7],
                "dueAt": row[8],
                "paidAt": row[9],
            })
    next_cursor = invoices[-1]["invoiceId"] if len(invoices) == safe_limit else ""
    return {"ok": True, "orgDid": orgDid, "invoices": invoices, "nextCursor": next_cursor}


# ──────────────────────────────────────────────────────────────────────
# 12. billing.invoice.get — XRPC
# ──────────────────────────────────────────────────────────────────────


async def task_billing_invoice_get(invoiceId: str = "", **kwargs: Any) -> dict[str, Any]:
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT invoice_id, vertex_id, org_did, period_start, period_end,
                   subtotal_jpy_micro, total_discount_jpy_micro, tax_jpy_micro,
                   total_jpy_micro, currency, status, qualified_invoice_number,
                   issued_at, due_at, paid_at, line_items_json
            FROM vertex_billing_invoice
            WHERE invoice_id = %s
            LIMIT 1
            """,
            (invoiceId,),
        )
        row = (_res[0] if _res else None)
    if row is None:
        return {"ok": False, "error": "invoice not found"}

    line_items: list[dict[str, Any]] = []
    try:
        li = json.loads(row[15] or "[]")
        if isinstance(li, list):
            line_items = li
    except (TypeError, json.JSONDecodeError):
        line_items = []

    # If line_items_json is empty (Phase 1 minted), reconstruct from
    # mv_billing_monthly_org for the invoice period.
    if not line_items:
        period_start = row[3]
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                SELECT product, billed_jpy_micro, total_qty
                FROM mv_billing_monthly_org
                WHERE org_did = %s AND month = %s
                """,
                (row[2], period_start),
            )
            for prod, billed, qty in _res:
                line_items.append({
                    "metric": "(rolled up)",
                    "product": prod or "",
                    "qty": float(qty or 0),
                    "unitPriceJpyMicro": 0,
                    "billedJpyMicro": int(billed or 0),
                    "appliedDiscountPct": 0,
                })

    return {
        "ok": True,
        "invoiceId": row[0],
        "vertexId": row[1],
        "orgDid": row[2],
        "periodStart": str(row[3]),
        "periodEnd": str(row[4]),
        "subtotalJpyMicro": int(row[5] or 0),
        "totalDiscountJpyMicro": int(row[6] or 0),
        "taxJpyMicro": int(row[7] or 0),
        "totalJpyMicro": int(row[8] or 0),
        "currency": row[9] or "JPY",
        "status": row[10],
        "qualifiedInvoiceNumber": row[11],
        "issuedAt": row[12],
        "dueAt": row[13],
        "paidAt": row[14],
        "lineItems": line_items,
    }


# ──────────────────────────────────────────────────────────────────────
# 13. billing.coverage.snapshot — XRPC
# ──────────────────────────────────────────────────────────────────────


async def task_billing_coverage_snapshot(asOf: str | None = None, **kwargs: Any) -> dict[str, Any]:
    as_of = asOf or _now_iso()
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT COUNT(*) FROM vertex_billing_org_plan WHERE status = 'active'")
        orgs_total = int(((_res[0] if _res else None) or (0,))[0] or 0)
        _res = client.q(
            "SELECT COUNT(*) FROM vertex_billing_org_plan WHERE status = 'active' AND plan = 'free'"
        )
        orgs_free = int(((_res[0] if _res else None) or (0,))[0] or 0)
        orgs_paying = orgs_total - orgs_free

        _res = client.q(
            "SELECT COUNT(*), COALESCE(SUM(billed_amount_jpy_micro), 0) FROM vertex_billing_event WHERE ts_ms > %s",
            (_now_ms() - 24 * 60 * 60 * 1000,),
        )
        ev_row = (_res[0] if _res else None) or (0, 0)
        events_24h = int(ev_row[0] or 0)
        billed_24h = int(ev_row[1] or 0)

        _res = client.q(
            "SELECT COUNT(*) FROM vertex_billing_invoice WHERE status IN ('draft', 'issued', 'overdue')"
        )
        open_inv = int(((_res[0] if _res else None) or (0,))[0] or 0)

        # Margin trailing 30d.
        _res = client.q(
            """
            SELECT COALESCE(SUM(billed_jpy_micro), 0), COALESCE(SUM(cost_jpy_micro), 0)
            FROM mv_billing_margin_actual
            WHERE day > %s
            """,
            (_today() - timedelta(days=30),),
        )
        m_row = (_res[0] if _res else None) or (0, 0)
        billed_30d = int(m_row[0] or 0)
        cost_30d = int(m_row[1] or 0)
        margin_pct = (
            ((billed_30d - cost_30d) / billed_30d * 100.0) if billed_30d > 0 else 0.0
        )

    # Overage alert count via _PLAN_LIMITS (cheaper than the full
    # detect_overage path for a coverage snapshot).
    over = await task_billing_detect_overage()

    return {
        "ok": True,
        "asOf": as_of,
        "orgsTotal": orgs_total,
        "orgsFree": orgs_free,
        "orgsPaying": orgs_paying,
        "eventsLast24h": events_24h,
        "openInvoices": open_inv,
        "overageAlerts": int(over.get("alertsEmitted", 0)),
        "marginActualPct": margin_pct,
        "billedLast24hJpyMicro": billed_24h,
    }


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Wire all billing task types onto the shared LangServer worker.

    Static manifest below repeats each task_type as a literal so the
    BPMN worker-task coverage linter
    (`70-tools/scripts/lint/bpmn-worker-task-coverage.mjs`) discovers
    camelCase names — its `t("...")` regex is `[a-z0-9_.-]`-only and
    misses camelCase, while its `task_type="..."` regex is lazy and
    matches anywhere in the file (comments included).

      task_type="billing.event.record"
      task_type="billing.rollup.daily"
      task_type="billing.rollup.monthly"
      task_type="billing.detect.overage"
      task_type="billing.generate.invoice"
      task_type="billing.discount.validateRole"
      task_type="billing.discount.apply"
      task_type="billing.credit.apply"
      task_type="billing.usage.get"
      task_type="billing.quota.status"
      task_type="billing.invoice.list"
      task_type="billing.invoice.get"
      task_type="billing.coverage.snapshot"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("billing.event.record",          task_billing_event_record)
    t("billing.rollup.daily",          task_billing_rollup_daily,         ms=300_000)
    t("billing.rollup.monthly",        task_billing_rollup_monthly,       ms=300_000)
    t("billing.detect.overage",        task_billing_detect_overage,       ms=120_000)
    t("billing.generate.invoice",      task_billing_generate_invoice,     ms=600_000)
    t("billing.discount.validateRole", task_billing_discount_validate_role)
    t("billing.discount.apply",        task_billing_discount_apply)
    t("billing.credit.apply",          task_billing_credit_apply)
    t("billing.usage.get",             task_billing_usage_get)
    t("billing.quota.status",          task_billing_quota_status)
    t("billing.invoice.list",          task_billing_invoice_list)
    t("billing.invoice.get",           task_billing_invoice_get)
    t("billing.coverage.snapshot",     task_billing_coverage_snapshot,    ms=15_000)


__all__ = [
    "register",
    "task_billing_event_record",
    "task_billing_rollup_daily",
    "task_billing_rollup_monthly",
    "task_billing_detect_overage",
    "task_billing_generate_invoice",
    "task_billing_discount_validate_role",
    "task_billing_discount_apply",
    "task_billing_credit_apply",
    "task_billing_usage_get",
    "task_billing_quota_status",
    "task_billing_invoice_list",
    "task_billing_invoice_get",
    "task_billing_coverage_snapshot",
]
