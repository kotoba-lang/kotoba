"""KA executive dashboard handlers for BPMN + Zeebe."""

from __future__ import annotations

from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from datetime import datetime, timezone

def _query_raw_datalog(datalog: str, columns: list[str]) -> list[dict[str, Any]]:
    """Helper to execute raw Datalog and map results to dicts."""
    client = get_kotoba_client()
    rows = client.q(datalog)
    result = []
    for row_values in rows:
        if len(row_values) != len(columns):
            # This should ideally not happen if the Datalog :find clause matches `columns`
            raise ValueError(f"Datalog query result row length {len(row_values)} != expected columns {len(columns)}")
        result.append(dict(zip(columns, row_values)))
    return result

NS = "com.etzhayyim.apps.ka"
ACTOR = "did:web:ka.etzhayyim.com"

QUERIES = {
    "entities": {
        "datalog": """
            [:find ?entity_code ?legal_name ?status ?notes
             :where
             [?e :business-entity/entity-code ?entity_code]
             [?e :business-entity/legal-name ?legal_name]
             [?e :business-entity/status ?status]
             [?e :business-entity/notes ?notes]]
        """,
        "columns": ["entity_code", "legal_name", "status", "notes"],
        "post_process": lambda rows: sorted(rows, key=lambda x: x["entity_code"]) # R0: In-Python ordering
    },
    "goals": {
        "datalog": """
            [:find ?goal_code ?display_name ?goal_type ?status ?attainment_bps ?target_date ?target_value_jpy
             :where
             [?e :goal/goal-code ?goal_code]
             [?e :goal/display-name ?display_name]
             [?e :goal/goal-type ?goal_type]
             [?e :goal/status ?status]
             [?e :goal/attainment-bps ?attainment_bps]
             [?e :goal/target-date ?target_date]
             [?e :goal/target-value-jpy ?target_value_jpy]]
        """,
        "columns": ["goal_code", "display_name", "goal_type", "status", "attainment_bps", "target_date", "target_value_jpy"],
        "post_process": lambda rows: sorted(rows, key=lambda x: x["attainment_bps"], reverse=True) # R0: In-Python ordering
    },
    "actions": {
        "datalog": """
            [:find ?action_code ?display_name ?status ?phase ?topo_level ?priority ?effort_days ?confidence_bps
             :where
             [?e :action/action-code ?action_code]
             [?e :action/display-name ?display_name]
             [?e :action/status ?status]
             [?e :action/phase ?phase]
             [?e :action/topo-level ?topo_level]
             [?e :action/priority ?priority]
             [?e :action/effort-days ?effort_days]
             [?e :action/confidence-bps ?confidence_bps]]
        """,
        "columns": ["action_code", "display_name", "status", "phase", "topo_level", "priority", "effort_days", "confidence_bps"],
        "post_process": lambda rows: sorted(rows, key=lambda x: (x["topo_level"], -x["priority"])) # R0: In-Python ordering
    },
    "revenue": {
        "datalog": """
            [:find ?stream_code ?display_name ?status ?current_mrr_jpy ?target_mrr_jpy ?gross_margin_bps ?entity_id ?notes
             :where
             [?e :revenue-stream/stream-code ?stream_code]
             [?e :revenue-stream/display-name ?display_name]
             [?e :revenue-stream/status ?status]
             [?e :revenue-stream/current-mrr-jpy ?current_mrr_jpy]
             [?e :revenue-stream/target-mrr-jpy ?target_mrr_jpy]
             [?e :revenue-stream/gross-margin-bps ?gross_margin_bps]
             [?e :revenue-stream/entity-id ?entity_id]
             [?e :revenue-stream/notes ?notes]]
        """,
        "columns": ["stream_code", "display_name", "status", "current_mrr_jpy", "target_mrr_jpy", "gross_margin_bps", "entity_id", "notes"],
        "post_process": lambda rows: sorted(rows, key=lambda x: x["target_mrr_jpy"], reverse=True) # R0: In-Python ordering
    },
    "burn": {
        "datalog": """
            [:find ?center_code ?display_name ?category ?monthly_burn_jpy ?reducible_bps ?entity_id ?notes
             :where
             [?e :cost-center/center-code ?center_code]
             [?e :cost-center/display-name ?display_name]
             [?e :cost-center/category ?category]
             [?e :cost-center/monthly-burn-jpy ?monthly_burn_jpy]
             [?e :cost-center/reducible-bps ?reducible_bps]
             [?e :cost-center/entity-id ?entity_id]
             [?e :cost-center/notes ?notes]]
        """,
        "columns": ["center_code", "display_name", "category", "monthly_burn_jpy", "reducible_bps", "entity_id", "notes"],
        "post_process": lambda rows: sorted(rows, key=lambda x: x["monthly_burn_jpy"], reverse=True) # R0: In-Python ordering
    },
    "risks": {
        "datalog": """
            [:find ?risk_code ?display_name ?risk_type ?severity ?probability_bps ?impact_jpy ?expected_loss_jpy ?status
             :where
             [?e :risk/risk-code ?risk_code]
             [?e :risk/display-name ?display_name]
             [?e :risk/risk-type ?risk_type]
             [?e :risk/severity ?severity]
             [?e :risk/probability-bps ?probability_bps]
             [?e :risk/impact-jpy ?impact_jpy]
             [?e :risk/expected-loss-jpy ?expected_loss_jpy]
             [?e :risk/status ?status]]
        """,
        "columns": ["risk_code", "display_name", "risk_type", "severity", "probability_bps", "impact_jpy", "expected_loss_jpy", "status"],
        "post_process": lambda rows: sorted([r for r in rows if r["status"] in ("open", "mitigating")], key=lambda x: x["expected_loss_jpy"], reverse=True) # R0: In-Python filtering and ordering
    },
    "cases": {
        "datalog": """
            [:find ?case_code ?display_name ?case_type ?status ?counterparty ?estimated_impact_jpy ?document_count ?last_activity_at
             :where
             [?e :business-case/case-code ?case_code]
             [?e :business-case/display-name ?display_name]
             [?e :business-case/case-type ?case_type]
             [?e :business-case/status ?status]
             [?e :business-case/counterparty ?counterparty]
             [?e :business-case/estimated-impact-jpy ?estimated_impact_jpy]
             [?e :business-case/document-count ?document_count]
             [?e :business-case/last-activity-at ?last_activity_at]]
        """,
        "columns": ["case_code", "display_name", "case_type", "status", "counterparty", "estimated_impact_jpy", "document_count", "last_activity_at"],
        "post_process": lambda rows: sorted([r for r in rows if r["status"] != "closed"], key=lambda x: x["estimated_impact_jpy"], reverse=True) # R0: In-Python filtering and ordering
    },
    "kpi": {
        "datalog": """
            [:find ?kpi_code ?display_name ?unit ?direction ?current_value ?target_value ?threshold_red ?threshold_green ?measured_at
             :where
             [?e :kpi/kpi-code ?kpi_code]
             [?e :kpi/display-name ?display_name]
             [?e :kpi/unit ?unit]
             [?e :kpi/direction ?direction]
             [?e :kpi/current-value ?current_value]
             [?e :kpi/target-value ?target_value]
             [?e :kpi/threshold-red ?threshold_red]
             [?e :kpi/threshold-green ?threshold_green]
             [?e :kpi/measured-at ?measured_at]]
        """,
        "columns": ["kpi_code", "display_name", "unit", "direction", "current_value", "target_value", "threshold_red", "threshold_green", "measured_at"],
        "post_process": lambda rows: sorted(rows, key=lambda x: x["kpi_code"]) # R0: In-Python ordering
    },
    "projects": { # R0: Special handling for projects due to aggregation and join
        "handler": "_get_projects_data"
    },
    "infra": {
        "datalog": """
            [:find ?capability_code ?display_name ?capability_type ?status ?deployed_at
             :where
             [?e :infra-capability/capability-code ?capability_code]
             [?e :infra-capability/display-name ?display_name]
             [?e :infra-capability/capability-type ?capability_type]
             [?e :infra-capability/status ?status]
             [?e :infra-capability/deployed-at ?deployed_at]]
        """,
        "columns": ["capability_code", "display_name", "capability_type", "status", "deployed_at"],
        "post_process": lambda rows: sorted(rows, key=lambda x: (x["status"], x["capability_code"]), reverse=True) # R0: In-Python ordering
    },
    "milestones": {
        "datalog": """
            [:find ?milestone_code ?display_name ?target_date ?actual_date ?status
             :where
             [?e :milestone/milestone-code ?milestone_code]
             [?e :milestone/display-name ?display_name]
             [?e :milestone/target-date ?target_date]
             [?e :milestone/actual-date ?actual_date]
             [?e :milestone/status ?status]]
        """,
        "columns": ["milestone_code", "display_name", "target_date", "actual_date", "status"],
        "post_process": lambda rows: sorted(rows, key=lambda x: x["target_date"]) # R0: In-Python ordering
    },
    "snapshots": {
        "datalog": """
            [:find ?snapshot_at ?total_documents ?monthly_revenue_jpy ?monthly_burn_jpy ?net_margin_jpy ?open_risks ?open_cases
             :where
             [?e :strategy-snapshot/snapshot-at ?snapshot_at]
             [?e :strategy-snapshot/total-documents ?total_documents]
             [?e :strategy-snapshot/monthly-revenue-jpy ?monthly_revenue_jpy]
             [?e :strategy-snapshot/monthly-burn-jpy ?monthly_burn_jpy]
             [?e :strategy-snapshot/net-margin-jpy ?net_margin_jpy]
             [?e :strategy-snapshot/open-risks ?open_risks]
             [?e :strategy-snapshot/open-cases ?open_cases]]
        """,
        "columns": ["snapshot_at", "total_documents", "monthly_revenue_jpy", "monthly_burn_jpy", "net_margin_jpy", "open_risks", "open_cases"],
        "post_process": lambda rows: sorted(rows, key=lambda x: x["snapshot_at"], reverse=True)[:5] # R0: In-Python ordering and limit 5
    },
    "deps": {
        "datalog": """
            [:find ?edge_id ?src_vid ?dst_vid ?dep_type
             :where
             [?e :depends-on/edge-id ?edge_id]
             [?e :depends-on/src-vid ?src_vid]
             [?e :depends-on/dst-vid ?dst_vid]
             [?e :depends-on/dep-type ?dep_type]]
        """,
        "columns": ["edge_id", "src_vid", "dst_vid", "dep_type"],
        "post_process": lambda rows: sorted([r for r in rows if r["src_vid"].startswith("action:")], key=lambda x: x["src_vid"]) # R0: In-Python filtering and ordering
    },
    "achieves": {
        "datalog": """
            [:find ?src_vid ?dst_vid ?contribution_bps ?confidence_bps
             :where
             [?e :achieves/src-vid ?src_vid]
             [?e :achieves/dst-vid ?dst_vid]
             [?e :achieves/contribution-bps ?contribution_bps]
             [?e :achieves/confidence-bps ?confidence_bps]]
        """,
        "columns": ["src_vid", "dst_vid", "contribution_bps", "confidence_bps"],
    },
    "inbox_health": {
        "datalog": """
            [:find ?total_30d ?unread_30d ?noise_30d ?signal_30d
             :where
             [?e :mv-inbox-health/total-30d ?total_30d]
             [?e :mv-inbox-health/unread-30d ?unread_30d]
             [?e :mv-inbox-health/noise-30d ?noise_30d]
             [?e :mv-inbox-health/signal-30d ?signal_30d]]
        """,
        "columns": ["total_30d", "unread_30d", "noise_30d", "signal_30d"],
        "post_process": lambda rows: rows[:1] # R0: In-Python limit 1
    },
    "dept_signals": {
        "datalog": """
            [:find ?dept_code ?signal_class ?email_count ?event_count ?total_count
             :where
             [?e :mv-kyber-dept-signals/dept-code ?dept_code]
             [?e :mv-kyber-dept-signals/signal-class ?signal_class]
             [?e :mv-kyber-dept-signals/email-count ?email_count]
             [?e :mv-kyber-dept-signals/event-count ?event_count]
             [?e :mv-kyber-dept-signals/total-count ?total_count]]
        """,
        "columns": ["dept_code", "signal_class", "email_count", "event_count", "total_count"],
        "post_process": lambda rows: sorted(rows, key=lambda x: x["total_count"], reverse=True) # R0: In-Python ordering
    },
    "blob_stats": {
        "datalog": """
            [:find ?row_count ?dedup_hits ?logical_bytes ?physical_bytes
             :where
             [?e :mv-blob-dedup-stats/row-count ?row_count]
             [?e :mv-blob-dedup-stats/dedup-hits ?dedup_hits]
             [?e :mv-blob-dedup-stats/logical-bytes ?logical_bytes]
             [?e :mv-blob-dedup-stats/physical-bytes ?physical_bytes]]
        """,
        "columns": ["row_count", "dedup_hits", "logical_bytes", "physical_bytes"],
        "post_process": lambda rows: [{
            "row_count": r["row_count"],
            "dedup_hits": r["dedup_hits"],
            "logical_mb": int(r["logical_bytes"] / 1024 / 1024), # R0: In-Python arithmetic and casting
            "physical_mb": int(r["physical_bytes"] / 1024 / 1024), # R0: In-Python arithmetic and casting
        } for r in rows[:1]] if rows else [] # R0: In-Python limit 1
    },
}

# R0: Multi-step query for projects with aggregation
def _get_projects_data() -> list[dict[str, Any]]:
    # Fetch business cases that start with 'P'
    cases = _query_raw_datalog(
        """
        [:find ?case_code ?display_name ?bc_id
         :where
         [?bc_id :business-case/case-code ?case_code]
         [?bc_id :business-case/display-name ?display_name]
         [(str/starts-with? ?case_code "P")]]
        """,
        ["case_code", "display_name", "bc_id"]
    )

    # Fetch all edge_in_project links
    in_projects = _query_raw_datalog(
        """
        [:find ?src_vid ?dst_vid
         :where
         [?ip :edge-in-project/src-vid ?src_vid]
         [?ip :edge-in-project/dst-vid ?dst_vid]]
        """,
        ["src_vid", "dst_vid"]
    )

    case_doc_counts: dict[Any, dict[str, Any]] = {}
    for case in cases:
        case_doc_counts[case["bc_id"]] = {"case_code": case["case_code"], "display_name": case["display_name"], "doc_count": 0}

    for ip in in_projects:
        if ip["dst_vid"] in case_doc_counts:
            case_doc_counts[ip["dst_vid"]]["doc_count"] += 1

    # Convert to list of dicts and sort
    result = list(case_doc_counts.values())
    return sorted(result, key=lambda x: x["doc_count"], reverse=True)


def _query(name: str) -> list[dict[str, Any]]:
    if name == "projects":
        return _get_projects_data()

    query_spec = QUERIES[name]
    datalog_query = query_spec["datalog"]
    columns = query_spec["columns"]

    rows = _query_raw_datalog(datalog_query, columns)

    if "post_process" in query_spec:
        # R0: In-Python filtering, ordering, aggregation, or limiting.
        return query_spec["post_process"](rows)
    return rows


def get_dashboard(**_: Any) -> dict[str, Any]:
    return {
        "entities": _query("entities"),
        "goals": _query("goals"),
        "kpis": _query("kpi"),
        "revenue": _query("revenue"),
        "burn": _query("burn"),
        "risks": _query("risks"),
        "actions": _query("actions"),
        "cases": _query("cases"),
        "infra": _query("infra"),
    }


def get_goals(**_: Any) -> dict[str, Any]:
    return {"rows": _query("goals")}


def get_actions(**_: Any) -> dict[str, Any]:
    return {"rows": _query("actions")}


def get_revenue(**_: Any) -> dict[str, Any]:
    return {"rows": _query("revenue")}


def get_burn(**_: Any) -> dict[str, Any]:
    return {"rows": _query("burn")}


def get_risks(**_: Any) -> dict[str, Any]:
    return {"rows": _query("risks")}


def get_cases(**_: Any) -> dict[str, Any]:
    return {"rows": _query("cases")}


def get_kpi(**_: Any) -> dict[str, Any]:
    return {"rows": _query("kpi")}


def get_projects(**_: Any) -> dict[str, Any]:
    return {"rows": _query("projects")}


def get_infra(**_: Any) -> dict[str, Any]:
    return {"rows": _query("infra")}


def get_milestones(**_: Any) -> dict[str, Any]:
    return {"rows": _query("milestones")}


def get_snapshots(**_: Any) -> dict[str, Any]:
    return {"rows": _query("snapshots")}


def get_topo(**_: Any) -> dict[str, Any]:
    return {
        "goals": _query("goals"),
        "actions": _query("actions"),
        "deps": _query("deps"),
        "achieves": _query("achieves"),
        "infra": _query("infra"),
    }


def get_inbox(**_: Any) -> dict[str, Any]:
    health = _query("inbox_health")
    blob = _query("blob_stats")
    return {
        "email": health[0] if health else {},
        "dept_signals": _query("dept_signals"),
        "blob": blob[0] if blob else {},
    }
