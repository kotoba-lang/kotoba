"""Cross-domain ingest control handlers.

These handlers are the XRPC/MCP-facing control surface for the durable ingest
spine. Source-specific acquisition remains in `kotodama.ingest.*` workers.
"""

from __future__ import annotations

import json
from typing import Any
from datetime import datetime, timezone

from kotodama import udf
from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.ingest.core import IngestRun, mark_run_finished, upsert_run
from kotodama.ingest.zeebe import start_process_if_configured


_BPMN_BY_FAMILY_SOURCE = {
    ("houbun", "egov-jpn"): "ingest_houbun_egov_jpn_delta",
    ("houbun", "govinfo-cfr"): "ingest_houbun_govinfo_cfr",
    ("houbun", "eurlex"): "ingest_houbun_eurlex",
    ("houbun", "un-treaty"): "ingest_houbun_un_treaty",
    ("contracts", "constitute-project"): "ingest_contracts_constitute_project",
    ("contracts", "un-treaty"): "ingest_contracts_un_treaty",
    ("domain", "common-crawl"): "ingest_domain_common_crawl",
    ("site", "common-crawl"): "ingest_site_common_crawl_delta",
    ("patent", "uspto-patentsview"): "ingest_patent_uspto_patentsview",
    ("blockchain", "bitcoin-mainnet"): "blockchain_bitcoin_head_delta",
    ("blockchain", "ethereum-mainnet"): "blockchain_ethereum_head_delta",
}

_TARGETS_BY_FAMILY = {
    "houbun": ["vertex_houbun_statute", "vertex_houbun_article", "edge_houbun_statute_article"],
    "contracts": ["vertex_contracts_social_contract", "vertex_houbun_treaty"],
    "domain": ["vertex_page", "vertex_wet_chunk", "vertex_collection_job", "vertex_collector_run"],
    "site": ["vertex_page", "vertex_wet_chunk", "vertex_wat", "vertex_screenshot", "vertex_collection_job"],
    "maps": ["vertex_maps_job"],
    "patent": ["vertex_open_patent_patent", "edge_open_patent_citation_pair", "vertex_patent_blob"],
    "workspace": ["vertex_workspace_sync_job", "vertex_workspace_cursor", "vertex_workspace_raw_event"],
    "media": ["vertex_repo_commit"],
    "talent": ["vertex_job_posting", "vertex_occupation"],
    "blockchain": ["vertex_blockchain_block", "vertex_blockchain_tx"],
}


def _loads(params_json: str) -> dict[str, Any]:
    if not params_json:
        return {}
    data = json.loads(params_json)
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_str(params: dict[str, Any], key: str) -> str:
    value = str(params.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _mode(params: dict[str, Any], default: str = "delta") -> str:
    mode = str(params.get("mode") or default).strip().lower()
    if mode not in {"delta", "backfill", "repair", "verify"}:
        raise ValueError("mode must be one of delta, backfill, repair, verify")
    return mode


def _plan_payload(params: dict[str, Any]) -> dict[str, Any]:
    family = _require_str(params, "ingestFamily")
    source_id = _require_str(params, "sourceId")
    mode = _mode(params)
    bpmn_process_id = _BPMN_BY_FAMILY_SOURCE.get((family, source_id)) or f"ingest_{family}_{source_id}".replace("-", "_")
    targets = _TARGETS_BY_FAMILY.get(family, [])
    limit = params.get("limit")
    estimated_records = int(limit) if isinstance(limit, int) and limit > 0 else 0
    estimated_shards = 1 if estimated_records <= 0 else max(1, min(1000, (estimated_records + 999) // 1000))
    return {
        "ok": True,
        "ingestFamily": family,
        "sourceId": source_id,
        "mode": mode,
        "bpmnProcessId": bpmn_process_id,
        "estimatedShards": estimated_shards,
        "estimatedRecords": estimated_records,
        "targets": targets,
        "planJson": json.dumps(
            {
                "range": params.get("range"),
                "limit": params.get("limit"),
                "inputJson": params.get("inputJson"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    }


@udf(
    nsid="com.etzhayyim.apps.ingest.plan",
    io_threads=16,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("ingest", "plan", "mcp"),
    agent_tool="Dry-run a durable ingest plan without mutating graph rows.",
)
def ingest_plan(params_json: str) -> str:
    try:
        return _dump(_plan_payload(_loads(params_json)))
    except (ValueError, json.JSONDecodeError) as e:
        return _dump({"ok": False, "error": str(e)})


@udf(
    nsid="com.etzhayyim.apps.ingest.start",
    io_threads=16,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("ingest", "start", "mcp"),
    agent_tool="Create a durable ingest run row. Zeebe launch is handled by the scheduler/dispatcher layer.",
)
def ingest_start(params_json: str) -> str:
    try:
        params = _loads(params_json)
        plan = _plan_payload(params)
        if bool(params.get("dryRun")):
            return _dump({**plan, "dryRun": True})
        run = IngestRun(
            ingest_family=plan["ingestFamily"],
            source_id=plan["sourceId"],
            mode=plan["mode"],
            status="planned",
            bpmn_process_id=plan["bpmnProcessId"],
            requested_by=str(params.get("requestedBy") or "mcp"),
            input_json=str(params.get("inputJson") or params.get("range") or ""),
        ).with_run_id()
        vid = upsert_run(run)
        variables = {
            "runId": run.run_id,
            "runVertexId": vid,
            "ingestFamily": run.ingest_family,
            "sourceId": run.source_id,
            "mode": run.mode,
            "inputJson": run.input_json or "",
            "requestedBy": run.requested_by or "mcp",
        }
        instance_key, zeebe_error = start_process_if_configured(run.bpmn_process_id or "", variables)
        if instance_key:
            run = IngestRun(
                ingest_family=run.ingest_family,
                source_id=run.source_id,
                mode=run.mode,
                run_id=run.run_id,
                status="running",
                zeebe_process_instance_key=instance_key,
                bpmn_process_id=run.bpmn_process_id,
                requested_by=run.requested_by,
                input_json=run.input_json,
            )
            upsert_run(run)
        return _dump(
            {
                "ok": True,
                "runId": run.run_id,
                "runVertexId": vid,
                "status": run.status,
                "bpmnProcessId": run.bpmn_process_id,
                "zeebeProcessInstanceKey": instance_key,
                "zeebeError": zeebe_error,
            }
        )
    except (ValueError, json.JSONDecodeError) as e:
        return _dump({"ok": False, "error": str(e)})
    except Exception as e:  # noqa: BLE001
        return _dump({"ok": False, "error": f"ingest.start failed: {e}"})


@udf(
    nsid="com.etzhayyim.apps.ingest.backfill",
    io_threads=16,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("ingest", "backfill", "mcp"),
    agent_tool="Create a bounded durable backfill run with an explicit range.",
)
def ingest_backfill(params_json: str) -> str:
    try:
        params = _loads(params_json)
        if not str(params.get("range") or "").strip():
            raise ValueError("range is required for backfill")
        params["mode"] = "backfill"
        return ingest_start(json.dumps(params))
    except (ValueError, json.JSONDecodeError) as e:
        return _dump({"ok": False, "error": str(e)})


@udf(
    nsid="com.etzhayyim.apps.ingest.status",
    io_threads=16,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("ingest", "status", "mcp"),
    agent_tool="Read durable ingest run status from vertex_ingest_run.",
)
def ingest_status(params_json: str) -> str:
    try:
        params = _loads(params_json)
    except (ValueError, json.JSONDecodeError) as e:
        return _dump({"ok": False, "error": str(e), "runs": []})

    client = get_kotoba_client()
    find_vars = []
    where_clauses = [
        '[?e :vertex/type "vertex_ingest_run"]',
    ]
    select_columns = [
        "vertex_id", "run_id", "ingest_family", "source_id", "mode", "status",
        "zeebe_process_instance_key", "bpmn_process_id", "started_at", "finished_at",
        "records_read", "records_written", "records_skipped", "error_count",
        "last_error", "input_json", "output_json", "updated_at"
    ]

    # Use a mapping for Datomic attributes as they are often hyphen-cased
    datalog_col_mapping = {col: col.replace("_", "-") for col in select_columns}

    for col in select_columns:
        datalog_attr = datalog_col_mapping[col]
        find_vars.append(f"?{datalog_attr}")
        where_clauses.append(f"[?e :{datalog_attr} ?{datalog_attr}]")

    filter_params = {}
    # Add optional WHERE clauses based on input params
    for column, key in (
        ("run_id", "runId"),
        ("ingest_family", "ingestFamily"),
        ("source_id", "sourceId"),
        ("status", "status"),
    ):
        value = params.get(key)
        if value:
            datalog_attr = column.replace("_", "-")
            where_clauses.append(f"[?e :{datalog_attr} ${column}]")
            filter_params[f"${column}"] = str(value)

    # R0: Multi-predicate search with ORDER BY and LIMIT using q() and in-Python processing.
    query_edn_template = f"""
    [:find {' '.join(find_vars)}
     :where
       {' '.join(where_clauses)}
    ]
    """
    try:
        raw_results = client.q(query_edn_template, args=filter_params)

        rows = []
        for r in raw_results:
            row_dict = {}
            for i, col in enumerate(select_columns):
                row_dict[col] = r[i]
            rows.append(row_dict)

        # Apply ORDER BY started_at DESC
        # Ensure started_at values are comparable (e.g., all strings or all datetime objects)
        # Assuming they are strings that sort correctly or datetime objects
        rows.sort(key=lambda x: x.get("started_at", ""), reverse=True)

        # Apply LIMIT
        limit = max(1, min(int(params.get("limit") or 20), 100))
        rows = rows[:limit]

        return _dump({"ok": True, "runs": rows})
    except Exception as e:  # noqa: BLE001
        return _dump({"ok": False, "error": f"ingest.status failed: {e}", "runs": []})


def _update_run_status(params: dict[str, Any], status: str) -> int:
    client = get_kotoba_client()
    where_clauses_for_datalog: list[str] = ['[?e :vertex/type "vertex_ingest_run"]']
    filter_params_for_datalog = {}

    select_columns = [
        "vertex_id", "run_id", "ingest_family", "source_id", "mode", "status",
        "zeebe_process_instance_key", "bpmn_process_id", "started_at", "finished_at",
        "records_read", "records_written", "records_skipped", "error_count",
        "last_error", "input_json", "output_json", "updated_at"
    ]
    datalog_col_mapping = {col: col.replace("_", "-") for col in select_columns}

    for column, key in (("run_id", "runId"), ("ingest_family", "ingestFamily"), ("source_id", "sourceId")):
        value = params.get(key)
        if value:
            datalog_attr = column.replace("_", "-")
            where_clauses_for_datalog.append(f"[?e :{datalog_attr} ${column}]")
            filter_params_for_datalog[f"${column}"] = str(value)

    if not filter_params_for_datalog:
        raise ValueError("runId or ingestFamily/sourceId is required")

    find_vars = [f"?{datalog_col_mapping[col]}" for col in select_columns]

    # R0: Multi-predicate search in _update_run_status using q() to fetch records for update.
    query_edn = f"""
    [:find {' '.join(find_vars)}
     :where
       {' '.join(where_clauses_for_datalog)}
    ]
    """

    raw_existing_records = client.q(query_edn, args=filter_params_for_datalog)

    updated_count = 0
    current_utc_time = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'

    for r in raw_existing_records:
        existing_record_dict = {}
        for i, col in enumerate(select_columns):
            existing_record_dict[col] = r[i]

        existing_record_dict["status"] = status
        existing_record_dict["updated_at"] = current_utc_time

        client.insert_row("vertex_ingest_run", existing_record_dict)
        updated_count += 1

    return updated_count


@udf(
    nsid="com.etzhayyim.apps.ingest.pause",
    io_threads=16,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("ingest", "pause", "mcp"),
    agent_tool="Pause durable ingest runs by runId or family/source.",
)
def ingest_pause(params_json: str) -> str:
    try:
        params = _loads(params_json)
        count = _update_run_status(params, "paused")
        return _dump({"ok": True, "paused": count})
    except (ValueError, json.JSONDecodeError) as e:
        return _dump({"ok": False, "error": str(e), "paused": 0})
    except Exception as e:  # noqa: BLE001
        return _dump({"ok": False, "error": f"ingest.pause failed: {e}", "paused": 0})


@udf(
    nsid="com.etzhayyim.apps.ingest.resume",
    io_threads=16,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("ingest", "resume", "mcp"),
    agent_tool="Resume paused durable ingest runs by runId or family/source.",
)
def ingest_resume(params_json: str) -> str:
    try:
        params = _loads(params_json)
        count = _update_run_status(params, "planned")
        return _dump({"ok": True, "resumed": count})
    except (ValueError, json.JSONDecodeError) as e:
        return _dump({"ok": False, "error": str(e), "resumed": 0})
    except Exception as e:  # noqa: BLE001
        return _dump({"ok": False, "error": f"ingest.resume failed: {e}", "resumed": 0})


@udf(
    nsid="com.etzhayyim.apps.ingest.validate",
    io_threads=16,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("ingest", "validate", "mcp"),
    agent_tool="Validate ingest run visibility and cursor/artifact counts.",
)
def ingest_validate(params_json: str) -> str:
    try:
        params = _loads(params_json)
        run_id = str(params.get("runId") or "").strip()
        family = str(params.get("ingestFamily") or "").strip()
        source_id = str(params.get("sourceId") or "").strip()
        checks: list[dict[str, Any]] = []
        status = "ok"
        client = get_kotoba_client() # Initialize client here

        if run_id:
            # Check run_visible
            run_count = int(client.aggregate_where("vertex_ingest_run", "count", "*", "run_id", run_id))
            checks.append({"name": "run_visible", "ok": run_count == 1, "count": run_count})

            # Check artifacts_visible
            artifact_count = int(client.aggregate_where("vertex_ingest_artifact", "count", "*", "run_id", run_id))
            checks.append({"name": "artifacts_visible", "ok": True, "count": artifact_count})

        if family and source_id:
            # R0: Multi-predicate count for vertex_ingest_cursor using q().
            query_edn_cursor_count = """
            [:find (count ?e) .
             :where
               [?e :vertex/type "vertex_ingest_cursor"]
               [?e :ingest-family $ingest_family]
               [?e :source-id $source_id]
            ]
            """
            cursor_count_raw = client.q(
                query_edn_cursor_count,
                args={"$ingest_family": family, "$source_id": source_id}
            )
            # client.q returns list of lists, or empty list. `(count ?e) .` returns a single value if it's there.
            cursor_count = int(cursor_count_raw[0] if cursor_count_raw else 0)
            checks.append({"name": "cursors_visible", "ok": True, "count": cursor_count})

        if any(not c.get("ok") for c in checks):
            status = "failed"
        return _dump({"ok": status == "ok", "status": status, "checks": checks})
    except (ValueError, json.JSONDecodeError) as e:
        return _dump({"ok": False, "status": "failed", "checks": [], "error": str(e)})
    except Exception as e:  # noqa: BLE001
        return _dump({"ok": False, "status": "failed", "checks": [], "error": f"ingest.validate failed: {e}"})


@udf(
    nsid="com.etzhayyim.apps.coverage.refresh",
    io_threads=16,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("coverage", "refresh", "mcp"),
    agent_tool="Record a coverage refresh request for post-ingest reconciliation.",
)
def coverage_refresh(params_json: str) -> str:
    try:
        params = _loads(params_json)
        family = str(params.get("coverageFamily") or "world").strip()
        run_id = str(params.get("runId") or "").strip()
        if run_id:
            mark_run_finished(run_id, status="completed", output={"coverageFamily": family, "refreshRequested": True})
        return _dump({"ok": True, "coverageFamily": family, "status": "requested"})
    except (ValueError, json.JSONDecodeError) as e:
        return _dump({"ok": False, "status": "failed", "error": str(e)})
    except Exception as e:  # noqa: BLE001
        return _dump({"ok": False, "status": "failed", "error": f"coverage.refresh failed: {e}"})
