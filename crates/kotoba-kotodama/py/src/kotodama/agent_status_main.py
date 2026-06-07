"""Status surface for the local artificial-organism agent loop."""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import argparse
import json
import logging
import os
import subprocess
import urllib.request
from typing import Any

from kotodama.agent_daemon_main import (
    LOCAL_HEALTH_LAUNCHD_LABELS,
    launchd_label_running,
    load_knowledge_graph_fitness_context_direct,
)
from kotodama.local_agent_env import load_env_file, load_keychain_secret
from kotodama.primitives.active_inference import (
    CHANNEL_DISPATCH_TARGETS,
    HIGH_RISK_CHANNELS,
    LIVE_AUTONOMOUS_CHANNELS,
    REALWORLD_CHANNELS,
)

LOG = logging.getLogger("agent_status")


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _rows_to_dicts(columns: list[str], rows: list[tuple]) -> list[dict[str, Any]]:
    return [dict(zip(columns, row, strict=False)) for row in rows]


def _fetch_dicts(sql: str, params: tuple = ()) -> list[dict[str, Any]]:

    if True:

        client = get_kotoba_client()
        _res = client.q(sql, params)
        columns = [desc[0] for desc in [] or []]
        return _rows_to_dicts(columns, list(_res))


def load_belief_rows(agent_did: str) -> list[dict[str, Any]]:
    return _fetch_dicts(
        """
        SELECT belief_kind, state_key, state_value_json, posterior_confidence,
               posterior_entropy, updated_from_observation, updated_at
        FROM vertex_agent_belief_state
        WHERE agent_did = %s
          AND belief_kind IN ('runtime.homeostasis', 'runtime.outcome', 'runtime.learning')
        ORDER BY updated_at DESC
        LIMIT 12
        """,
        (agent_did,),
    )


def load_observation_rows(agent_did: str) -> list[dict[str, Any]]:
    return _fetch_dicts(
        """
        SELECT vertex_id, source_kind, source_ref, observed_at, payload_json,
               confidence, uncertainty
        FROM vertex_agent_observation
        WHERE agent_did = %s
          AND source_kind IN (
            'homeostasis_metrics',
            'self_repair_receipt',
            'dispatch_receipt'
          )
        ORDER BY observed_at DESC
        LIMIT 12
        """,
        (agent_did,),
    )


def load_count_rows(table: str, agent_did: str, state_column: str) -> list[dict[str, Any]]:
    if table not in {"vertex_agent_realworld_effect", "vertex_agent_dispatch_ledger"}:
        raise ValueError("unsupported status count table")
    if state_column not in {"dispatch_state"}:
        raise ValueError("unsupported status count column")
    return _fetch_dicts(
        f"""
        SELECT {state_column} AS state, COUNT(*) AS count
        FROM {table}
        WHERE agent_did = %s
        GROUP BY {state_column}
        ORDER BY count DESC, state ASC
        """,
        (agent_did,),
    )


def load_authority_rows(agent_did: str) -> list[dict[str, Any]]:
    return _fetch_dicts(
        """
        SELECT status AS state, COUNT(*) AS count
        FROM vertex_agent_delegated_authority_policy
        WHERE agent_did = %s
        GROUP BY status
        ORDER BY count DESC, status ASC
        """,
        (agent_did,),
    )


def load_recent_authority_effects(agent_did: str) -> list[dict[str, Any]]:
    return _fetch_dicts(
        """
        SELECT vertex_id, channel, effect_class, dispatch_state,
               COALESCE(authority_ref, approval_ref, '') AS authority_ref,
               budget_ref, updated_at
        FROM vertex_agent_realworld_effect
        WHERE agent_did = %s
        ORDER BY updated_at DESC
        LIMIT 8
        """,
        (agent_did,),
    )


def _dig_short(record_type: str, name: str) -> list[str]:
    try:
        result = subprocess.run(
            ["dig", "@1.1.1.1", "+short", record_type, name],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line.strip().strip('"') for line in result.stdout.splitlines() if line.strip()]


def _secret_configured(env_name: str, *, service: str, account: str) -> bool:
    if os.environ.get(env_name):
        return True
    return bool(load_keychain_secret(service=service, account=account))


def load_recent_email_outbound(limit: int = 5) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 20))
    try:
        return _fetch_dicts(
            f"""
            SELECT status, provider, from_address, to_address, subject,
                   "error" AS error, created_at
            FROM vertex_mailer_outbound_email
            ORDER BY created_at DESC
            LIMIT {safe_limit}
            """,
        )
    except Exception as exc:  # noqa: BLE001
        return [{"status": "unavailable", "error": str(exc)[:300]}]


def load_development_memory() -> dict[str, Any]:
    try:
        status_counts = _fetch_dicts(
            """
            SELECT topic, doc_type, status, document_count
            FROM mv_agent_development_document_status_counts
            ORDER BY topic ASC, doc_type ASC, status ASC
            LIMIT 20
            """,
        )
        latest_documents = _fetch_dicts(
            """
            SELECT doc_id, title, status, topic, related_ref, updated_at
            FROM mv_agent_development_document_latest
            ORDER BY updated_at DESC
            LIMIT 8
            """,
        )
        edge_counts = _fetch_dicts(
            """
            SELECT relation_kind, ref_kind, COUNT(*) AS edge_count
            FROM edge_agent_development_document_ref
            GROUP BY relation_kind, ref_kind
            ORDER BY relation_kind ASC, ref_kind ASC
            LIMIT 20
            """,
        )
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)[:300], "statusCounts": [], "latestDocuments": [], "edgeCounts": []}
    return {
        "available": True,
        "statusCounts": status_counts,
        "latestDocuments": latest_documents,
        "edgeCounts": edge_counts,
    }


def load_resend_domain_statuses() -> dict[str, str]:
    api_key = os.environ.get("RESEND_API_KEY") or load_keychain_secret(
        service="etzhayyim.resend", account="API_KEY"
    )
    if not api_key:
        return {}
    request = urllib.request.Request(
        "https://api.resend.com/domains",
        method="GET",
        headers={
            "authorization": f"Bearer {api_key}",
            "accept": "application/json",
            "user-agent": "etzhayyim-mailer-zeebe/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
    except Exception:
        return {}
    domains = data.get("data") if isinstance(data, dict) else []
    if not isinstance(domains, list):
        return {}
    return {
        str(item.get("name") or "").lower(): str(item.get("status") or "").lower()
        for item in domains
        if isinstance(item, dict) and item.get("name")
    }


def diagnose_email_live_channel(
    *,
    domains: tuple[str, ...] = ("etzhayyim.com", "mailer.etzhayyim.com"),
) -> dict[str, Any]:
    dns: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    resend_domain_statuses = load_resend_domain_statuses()
    active_domain = "etzhayyim.com"
    for domain in domains:
        txt = _dig_short("TXT", domain)
        send_txt = _dig_short("TXT", f"send.{domain}")
        send_mx = _dig_short("MX", f"send.{domain}")
        dkim_txt = _dig_short("TXT", f"resend._domainkey.{domain}")
        dkim_cname = _dig_short("CNAME", f"resend._domainkey.{domain}")
        spf_ready = any("include:amazonses.com" in item for item in [*txt, *send_txt])
        mx_ready = any("feedback-smtp" in item and "amazonses.com" in item for item in send_mx)
        dkim_ready = bool(dkim_txt or dkim_cname)
        dns[domain] = {
            "txt": txt,
            "sendTxt": send_txt,
            "sendMx": send_mx,
            "resendDkimTxt": dkim_txt,
            "resendDkim": dkim_cname,
            "spfReady": spf_ready,
            "mxReady": mx_ready,
            "dkimReady": dkim_ready,
            "dnsReady": spf_ready and mx_ready and dkim_ready,
            "resendStatus": resend_domain_statuses.get(domain.lower(), "unknown"),
        }
        if domain == active_domain and not spf_ready:
            blockers.append(f"resend_spf_missing:{domain}")
        if domain == active_domain and not mx_ready:
            blockers.append(f"resend_mx_missing:{domain}")
        if domain == active_domain and not dkim_ready:
            blockers.append(f"resend_dkim_missing:{domain}")

    resend_key = _secret_configured("RESEND_API_KEY", service="etzhayyim.resend", account="API_KEY")
    cloudflare_token = _secret_configured("CLOUDFLARE_API_TOKEN", service="etzhayyim.cloudflare", account="API_TOKEN")
    cloudflare_zone = _secret_configured("CLOUDFLARE_ZONE_ID", service="etzhayyim.cloudflare", account="ZONE_ID")
    if not resend_key:
        blockers.append("resend_api_key_missing")
    active_dns_ready = bool(dns.get(active_domain, {}).get("dnsReady"))
    if not (cloudflare_token and cloudflare_zone) and not active_dns_ready:
        blockers.append("cloudflare_dns_write_authority_missing")
    active_resend_verified = resend_domain_statuses.get(active_domain) == "verified"
    return {
        "ready": resend_key and active_dns_ready and active_resend_verified,
        "resendApiKey": "present" if resend_key else "missing",
        "resendDomainsApi": "available" if resend_domain_statuses else "forbidden_or_unavailable",
        "activeDomain": active_domain,
        "resendDomainStatuses": resend_domain_statuses,
        "cloudflareDnsWrite": "present" if cloudflare_token and cloudflare_zone else "missing",
        "dns": dns,
        "blockers": sorted(set(blockers)),
    }


def load_effect_channel_status(email_readiness: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    email_ready = bool((email_readiness or {}).get("ready"))
    rows: list[dict[str, Any]] = []
    for channel in sorted(REALWORLD_CHANNELS):
        target = CHANNEL_DISPATCH_TARGETS.get(channel)
        blockers: list[str] = []
        if not target:
            blockers.append(f"unsupported_autonomous_channel:{channel}")
        elif channel not in LIVE_AUTONOMOUS_CHANNELS:
            blockers.append(f"channel_worker_not_live:{channel}")
        if channel == "email" and not email_ready:
            blockers.append("email_live_channel_not_ready")
        rows.append(
            {
                "channel": channel,
                "state": "live" if not blockers else ("planned" if target else "unsupported"),
                "taskType": target.get("taskType", "") if target else "",
                "nsid": target.get("nsid", "") if target else "",
                "receipt": target.get("receipt", "") if target else "",
                "highRisk": channel in HIGH_RISK_CHANNELS,
                "blockers": sorted(set(blockers)),
            }
        )
    return rows


def load_economy_profile(agent_did: str) -> dict[str, Any] | None:
    rows = _fetch_dicts(
        """
        SELECT root_did, smart_account, erc8004_agent_id, atproto_did,
               economy_mode, policy_cid, runtime_policy_cid, slash_policy_cid,
               treasury_addr, status, updated_at, created_at
        FROM vertex_agent_economy_profile
        WHERE agent_did = %s
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
        """,
        (agent_did,),
    )
    return rows[0] if rows else None


def load_runtime_publication_status(agent_did: str, erc8004_agent_id: str | None = None) -> dict[str, Any]:
    if not os.environ.get("RW_URL"):
        return {"available": False, "error": "RW_URL missing"}
    publication_rows = _fetch_dicts(
        """
        SELECT token_id, root_did_hash, agent_uri, tx_hash, block_number,
               status, registry_addr, updated_at
        FROM vertex_agent_publication
        WHERE (%s = '' OR token_id = %s)
          AND (actor_did = %s OR owner_did = %s OR org_id = %s OR user_id = %s)
        ORDER BY updated_at DESC, block_number DESC
        LIMIT 1
        """,
        (
            erc8004_agent_id or "",
            erc8004_agent_id or "",
            agent_did,
            agent_did,
            agent_did,
            agent_did,
        ),
    )
    artifact_rows = _fetch_dicts(
        """
        SELECT artifact_id, runtime_kind_label, version, artifact_uri, tx_hash,
               block_number, status, updated_at
        FROM vertex_agent_runtime_artifact
        WHERE actor_did = %s OR owner_did = %s OR org_id = %s OR user_id = %s
        ORDER BY updated_at DESC, block_number DESC
        LIMIT 1
        """,
        (agent_did, agent_did, agent_did, agent_did),
    )
    receipt_rows = _fetch_dicts(
        """
        SELECT job_id, artifact_id, tx_hash, block_number, status, started_at,
               finished_at, updated_at
        FROM vertex_agent_runtime_receipt
        WHERE actor_did = %s OR owner_did = %s OR org_id = %s OR user_id = %s
        ORDER BY updated_at DESC, block_number DESC
        LIMIT 1
        """,
        (agent_did, agent_did, agent_did, agent_did),
    )
    publication = publication_rows[0] if publication_rows else None
    artifact = artifact_rows[0] if artifact_rows else None
    receipt = receipt_rows[0] if receipt_rows else None
    return {
        "available": True,
        "verified": bool(
            publication
            and publication.get("status") == "verified"
            and artifact
            and artifact.get("status") == "verified"
            and receipt
            and receipt.get("status") == "verified"
        ),
        "publication": publication,
        "runtimeArtifact": artifact,
        "runtimeReceipt": receipt,
    }


def load_policy_adaptation_status(agent_did: str) -> dict[str, Any]:
    try:
        proposal_counts = _fetch_dicts(
            """
            SELECT proposal_state AS state, COUNT(*) AS count
            FROM vertex_agent_policy_adaptation_proposal
            WHERE agent_did = %s
            GROUP BY proposal_state
            ORDER BY count DESC, proposal_state ASC
            """,
            (agent_did,),
        )
        recent_proposals = _fetch_dicts(
            """
            SELECT preference_key, proposal_state, mokuteki_gate_pass,
                   triple_witness_pass, blockers_json, created_at
            FROM vertex_agent_policy_adaptation_proposal
            WHERE agent_did = %s
            ORDER BY created_at DESC
            LIMIT 8
            """,
            (agent_did,),
        )
        active_priors = _fetch_dicts(
            """
            SELECT preference_key, weight, hard_floor, depends_on_adr, updated_at
            FROM vertex_agent_prior_preference
            WHERE agent_did = %s AND active = true
            ORDER BY updated_at DESC
            LIMIT 8
            """,
            (agent_did,),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "error": str(exc)[:300],
            "proposalCounts": [],
            "recentProposals": [],
            "activePriors": [],
        }
    return {
        "available": True,
        "proposalCounts": proposal_counts,
        "recentProposals": recent_proposals,
        "activePriors": active_priors,
    }


def load_counterparty_minimax_status(agent_did: str) -> dict[str, Any]:
    try:
        counterparties = _fetch_dicts(
            """
            SELECT counterparty_ref, model_kind, confidence, uncertainty, updated_at
            FROM vertex_agent_counterparty_model
            WHERE agent_did = %s
            ORDER BY updated_at DESC
            LIMIT 8
            """,
            (agent_did,),
        )
        protected_assets = _fetch_dicts(
            """
            SELECT counterparty_ref, asset_ref, asset_kind, violation_cost,
                   reversibility_score, updated_at
            FROM vertex_agent_protected_asset
            WHERE agent_did = %s
            ORDER BY updated_at DESC
            LIMIT 8
            """,
            (agent_did,),
        )
        minimax_evaluations = _fetch_dicts(
            """
            SELECT action_id, counterparty_ref, minimax_regret,
                   protected_asset_violation, selected_response,
                   evaluation_state, created_at
            FROM vertex_agent_minimax_evaluation
            WHERE agent_did = %s
            ORDER BY created_at DESC
            LIMIT 8
            """,
            (agent_did,),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "error": str(exc)[:300],
            "counterparties": [],
            "protectedAssets": [],
            "minimaxEvaluations": [],
        }
    return {
        "available": True,
        "counterparties": counterparties,
        "protectedAssets": protected_assets,
        "minimaxEvaluations": minimax_evaluations,
    }


def load_information_flow_status(agent_did: str) -> dict[str, Any]:
    try:
        nodes = _fetch_dicts(
            """
            SELECT info_ref, info_kind, abstraction_level, confidence,
                   uncertainty, counterparty_ref, updated_at
            FROM vertex_agent_information_node
            WHERE agent_did = %s
            ORDER BY abstraction_level DESC, updated_at DESC
            LIMIT 8
            """,
            (agent_did,),
        )
        try:
            height = _fetch_dicts(
                """
                SELECT counterparty_ref, info_kind, max_information_height, node_count
                FROM mv_agent_information_height
                WHERE agent_did = %s
                ORDER BY max_information_height DESC, node_count DESC
                LIMIT 8
                """,
                (agent_did,),
            )
        except Exception:
            height = _fetch_dicts(
                """
                SELECT counterparty_ref, info_kind,
                       MAX(abstraction_level) AS max_information_height,
                       COUNT(*) AS node_count
                FROM vertex_agent_information_node
                WHERE agent_did = %s
                GROUP BY counterparty_ref, info_kind
                ORDER BY max_information_height DESC, node_count DESC
                LIMIT 8
                """,
                (agent_did,),
            )
        try:
            flows = _fetch_dicts(
                """
                SELECT src_vid, out_flow_count, avg_control_score, avg_bandwidth_score
                FROM mv_agent_information_flow_control
                ORDER BY avg_control_score DESC, out_flow_count DESC
                LIMIT 8
                """,
            )
        except Exception:
            flows = _fetch_dicts(
                """
                SELECT src_vid, COUNT(*) AS out_flow_count,
                       AVG(control_score) AS avg_control_score,
                       AVG(bandwidth_score) AS avg_bandwidth_score
                FROM edge_agent_information_flows_to
                GROUP BY src_vid
                ORDER BY avg_control_score DESC, out_flow_count DESC
                LIMIT 8
                """,
            )
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)[:300], "nodes": [], "height": [], "flows": []}
    return {"available": True, "nodes": nodes, "height": height, "flows": flows}


def _latest_by_kind(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if value and value not in latest:
            latest[value] = row
    return latest


def _count_state(rows: list[dict[str, Any]], state: str) -> int:
    for row in rows:
        if str(row.get("state") or "") == state:
            try:
                return int(row.get("count") or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def evaluate_process_health(
    *,
    organism_state: str,
    organism_score: float,
    processes_ok: bool,
    viability_state: str,
    homeostasis_blockers: list[Any],
    latest_observation: dict[str, dict[str, Any]],
    knowledge_graph_fitness: dict[str, Any],
    dispatch_counts: list[dict[str, Any]],
    email_readiness: dict[str, Any],
) -> dict[str, Any]:
    blockers = [str(item) for item in homeostasis_blockers if str(item)]
    warnings: list[str] = []
    failures: list[str] = []
    repair_actions: list[str] = []
    if not processes_ok:
        failures.append("process_down")
    if viability_state in {"halted", "hibernate"}:
        failures.append(f"viability:{viability_state}")
    elif viability_state in {"repair", "unknown"}:
        warnings.append(f"viability:{viability_state}")
    if blockers:
        warnings.extend(f"homeostasis_blocker:{item}" for item in blockers)
    if not latest_observation.get("homeostasis_metrics"):
        warnings.append("homeostasis_metrics_missing")

    kg_available = bool(knowledge_graph_fitness.get("available"))
    kg_gain = float(knowledge_graph_fitness.get("kgDevelopmentGain") or 0.0)
    kg_evolution = float(knowledge_graph_fitness.get("evolutionFitness") or 0.0)
    missing_edge_penalty = float(knowledge_graph_fitness.get("missingEdgePenalty") or 0.0)
    if not kg_available:
        warnings.append("kg_fitness_unavailable")
    elif kg_gain < 0.75 or kg_evolution < 0.75:
        warnings.append("kg_fitness_low")
    if missing_edge_penalty > 0.1:
        warnings.append("kg_missing_edge_penalty")

    dispatch_failed = _count_state(dispatch_counts, "dispatch_failed")
    dispatched = _count_state(dispatch_counts, "dispatched")
    latest_dispatch_payload = _json_dict(latest_observation.get("dispatch_receipt", {}).get("payload_json"))
    latest_dispatch_error = str(latest_dispatch_payload.get("error") or "")
    latest_dispatch_success = bool(latest_dispatch_payload.get("receiptRef") or latest_dispatch_payload.get("messageId"))
    latest_dispatch_state = "dispatch_failed" if latest_dispatch_error else ("dispatched" if latest_dispatch_success else "")
    if dispatch_failed > dispatched and dispatch_failed > 0:
        if latest_dispatch_state == "dispatched" and email_readiness.get("ready"):
            repair_actions.append("monitor_dispatch_trend_recovery")
        else:
            warnings.append("dispatch_failures_exceed_successes")
            repair_actions.append("confirm_next_dispatch_success_resets_dispatch_trend")
    if latest_dispatch_error:
        warnings.append("latest_dispatch_failed")
        if latest_dispatch_error == "RESEND_API_KEY not configured":
            if email_readiness.get("ready"):
                repair_actions.append("restart_dispatch_worker_after_resend_secret_repair")
            else:
                repair_actions.append("configure_resend_api_key")
        elif latest_dispatch_error == "resend_api_failed":
            repair_actions.append("inspect_resend_provider_error")
    if not email_readiness.get("ready"):
        warnings.append("email_not_ready")
        repair_actions.append("repair_email_live_channel_readiness")

    if failures:
        level = "critical" if any(item.startswith("viability:") for item in failures) else "degraded"
    elif warnings or organism_score < 0.8 or organism_state not in {"active"}:
        level = "watch"
    else:
        level = "healthy"

    return {
        "level": level,
        "score": round(float(organism_score), 4),
        "processesOk": processes_ok,
        "viabilityState": viability_state,
        "homeostasisBlockers": blockers,
        "kgDevelopmentGain": round(kg_gain, 4),
        "kgEvolutionFitness": round(kg_evolution, 4),
        "kgMissingEdgePenalty": round(missing_edge_penalty, 4),
        "dispatchFailed": dispatch_failed,
        "dispatched": dispatched,
        "latestDispatchState": latest_dispatch_state,
        "latestDispatchError": latest_dispatch_error,
        "emailReady": bool(email_readiness.get("ready")),
        "repairActions": sorted(set(repair_actions)),
        "warnings": sorted(set(warnings)),
        "failures": sorted(set(failures)),
    }


def summarize_status(
    *,
    agent_did: str,
    launchd: dict[str, bool],
    belief_rows: list[dict[str, Any]],
    observation_rows: list[dict[str, Any]],
    effect_counts: list[dict[str, Any]],
    dispatch_counts: list[dict[str, Any]],
    authority_counts: list[dict[str, Any]] | None = None,
    recent_authority_effects: list[dict[str, Any]] | None = None,
    economy_profile: dict[str, Any] | None = None,
    email_outbound_rows: list[dict[str, Any]] | None = None,
    email_readiness: dict[str, Any] | None = None,
    development_memory: dict[str, Any] | None = None,
    policy_adaptation: dict[str, Any] | None = None,
    effect_channels: list[dict[str, Any]] | None = None,
    counterparty_minimax: dict[str, Any] | None = None,
    information_flow: dict[str, Any] | None = None,
    knowledge_graph_fitness: dict[str, Any] | None = None,
    runtime_publication: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest_belief = _latest_by_kind(belief_rows, "belief_kind")
    latest_observation = _latest_by_kind(observation_rows, "source_kind")
    homeostasis = latest_belief.get("runtime.homeostasis", {})
    outcome = latest_belief.get("runtime.outcome", {})
    learning = latest_belief.get("runtime.learning", {})
    homeostasis_state = _json_dict(homeostasis.get("state_value_json"))
    outcome_state = _json_dict(outcome.get("state_value_json"))
    learning_state = _json_dict(learning.get("state_value_json"))
    dispatch_receipt_payload = _json_dict(latest_observation.get("dispatch_receipt", {}).get("payload_json"))
    email_readiness_value = dict(email_readiness or {})
    if dispatch_receipt_payload.get("channel") == "email" and dispatch_receipt_payload.get("error"):
        readiness_blockers = list(email_readiness_value.get("blockers") or [])
        if not email_readiness_value.get("ready"):
            readiness_blockers.append(str(dispatch_receipt_payload.get("error")))
        if dispatch_receipt_payload.get("error") == "resend_api_failed" and not email_readiness_value.get("ready"):
            readiness_blockers.append("resend_domain_or_sender_unverified")
        email_readiness_value["blockers"] = sorted(set(readiness_blockers))
    viability_state = str(homeostasis_state.get("viabilityState") or "unknown")
    processes_ok = all(launchd.values()) if launchd else False
    latest_outcome_success = bool(outcome_state.get("success", False))
    blockers = homeostasis_state.get("blockers") if isinstance(homeostasis_state.get("blockers"), list) else []

    if viability_state in {"halted", "hibernate"}:
        organism_state = "critical"
    elif not processes_ok:
        organism_state = "degraded"
    elif viability_state == "repair":
        organism_state = "repairing"
    elif viability_state in {"normal", "conserve"}:
        organism_state = "active"
    else:
        organism_state = "unknown"

    score = 0.0
    score += 0.35 if processes_ok else 0.0
    score += {"normal": 0.35, "conserve": 0.25, "repair": 0.15}.get(viability_state, 0.0)
    score += 0.15 if latest_observation.get("homeostasis_metrics") else 0.0
    score += 0.10 if latest_belief.get("runtime.learning") else 0.0
    score += 0.05 if latest_outcome_success else 0.0

    organism_score = round(min(1.0, score), 4)
    kg_fitness_value = knowledge_graph_fitness or {
        "available": False,
        "kgDevelopmentGain": 0.0,
        "kgCoverageScore": 0.0,
        "missingEdgePenalty": 0.0,
        "evolutionFitness": 0.0,
    }
    health_evaluation = evaluate_process_health(
        organism_state=organism_state,
        organism_score=organism_score,
        processes_ok=processes_ok,
        viability_state=viability_state,
        homeostasis_blockers=blockers,
        latest_observation=latest_observation,
        knowledge_graph_fitness=kg_fitness_value,
        dispatch_counts=dispatch_counts,
        email_readiness=email_readiness_value,
    )

    return {
        "agentDid": agent_did,
        "organismState": organism_state,
        "organismScore": organism_score,
        "healthEvaluation": health_evaluation,
        "homeostasis": {
            "viabilityState": viability_state,
            "confidence": homeostasis.get("posterior_confidence"),
            "entropy": homeostasis.get("posterior_entropy"),
            "updatedAt": homeostasis.get("updated_at"),
            "blockers": blockers,
        },
        "processes": launchd,
        "latestObservations": latest_observation,
        "latestOutcome": {
            "success": latest_outcome_success,
            "dispatchState": outcome_state.get("dispatchState"),
            "updatedAt": outcome.get("updated_at"),
            "sourceKind": outcome_state.get("sourceKind"),
            "blockers": outcome_state.get("blockers", []),
        },
        "learning": {
            "updatedAt": learning.get("updated_at"),
            "channelPriors": learning_state.get("channelPriors", {}),
            "policyPriors": learning_state.get("policyPriors", {}),
            "lastOutcome": learning_state.get("lastOutcome", {}),
        },
        "realWorldEffects": effect_counts,
        "dispatchLedger": dispatch_counts,
        "authority": {
            "policies": authority_counts or [],
            "recentEffects": recent_authority_effects or [],
            "canonicalField": "authority_ref",
            "legacyField": "approval_ref",
        },
        "liveChannels": {
            "email": {
                "readiness": email_readiness_value,
                "latestDispatchReceipt": dispatch_receipt_payload,
                "recentOutbound": email_outbound_rows or [],
            }
        },
        "effectChannels": effect_channels or [],
        "erc8004": {
            "configured": bool(economy_profile and economy_profile.get("erc8004_agent_id")),
            "agentId": (economy_profile or {}).get("erc8004_agent_id"),
            "rootDid": (economy_profile or {}).get("root_did"),
            "smartAccount": (economy_profile or {}).get("smart_account"),
            "economyMode": (economy_profile or {}).get("economy_mode"),
            "policyCid": (economy_profile or {}).get("policy_cid"),
            "runtimePolicyCid": (economy_profile or {}).get("runtime_policy_cid"),
            "status": (economy_profile or {}).get("status"),
            "updatedAt": (economy_profile or {}).get("updated_at")
            or (economy_profile or {}).get("created_at"),
        },
        "runtimePublication": runtime_publication or {"available": False, "verified": False},
        "developmentMemory": development_memory or {
            "available": False,
            "statusCounts": [],
            "latestDocuments": [],
            "edgeCounts": [],
        },
        "policyAdaptation": policy_adaptation or {
            "available": False,
            "proposalCounts": [],
            "recentProposals": [],
            "activePriors": [],
        },
        "counterpartyMinimax": counterparty_minimax or {
            "available": False,
            "counterparties": [],
            "protectedAssets": [],
            "minimaxEvaluations": [],
        },
        "informationFlow": information_flow or {
            "available": False,
            "nodes": [],
            "height": [],
            "flows": [],
        },
        "knowledgeGraphFitness": kg_fitness_value,
    }


def load_status_report(agent_did: str) -> dict[str, Any]:
    launchd = {label: launchd_label_running(label) for label in LOCAL_HEALTH_LAUNCHD_LABELS}
    belief_rows = load_belief_rows(agent_did)
    observation_rows = load_observation_rows(agent_did)
    effect_counts = load_count_rows("vertex_agent_realworld_effect", agent_did, "dispatch_state")
    dispatch_counts = load_count_rows("vertex_agent_dispatch_ledger", agent_did, "dispatch_state")
    authority_counts = load_authority_rows(agent_did)
    recent_authority_effects = load_recent_authority_effects(agent_did)
    economy_profile = load_economy_profile(agent_did)
    email_outbound_rows = load_recent_email_outbound()
    email_readiness = diagnose_email_live_channel()
    development_memory = load_development_memory()
    policy_adaptation = load_policy_adaptation_status(agent_did)
    effect_channels = load_effect_channel_status(email_readiness)
    counterparty_minimax = load_counterparty_minimax_status(agent_did)
    information_flow = load_information_flow_status(agent_did)
    knowledge_graph_fitness = load_knowledge_graph_fitness_context_direct(agent_did)
    runtime_publication = load_runtime_publication_status(
        agent_did, str((economy_profile or {}).get("erc8004_agent_id") or "")
    )
    return summarize_status(
        agent_did=agent_did,
        launchd=launchd,
        belief_rows=belief_rows,
        observation_rows=observation_rows,
        effect_counts=effect_counts,
        dispatch_counts=dispatch_counts,
        authority_counts=authority_counts,
        recent_authority_effects=recent_authority_effects,
        economy_profile=economy_profile,
        email_outbound_rows=email_outbound_rows,
        email_readiness=email_readiness,
        development_memory=development_memory,
        policy_adaptation=policy_adaptation,
        effect_channels=effect_channels,
        counterparty_minimax=counterparty_minimax,
        information_flow=information_flow,
        knowledge_graph_fitness=knowledge_graph_fitness,
        runtime_publication=runtime_publication,
    )


def format_text(report: dict[str, Any]) -> str:
    homeostasis = report.get("homeostasis") if isinstance(report.get("homeostasis"), dict) else {}
    outcome = report.get("latestOutcome") if isinstance(report.get("latestOutcome"), dict) else {}
    learning = report.get("learning") if isinstance(report.get("learning"), dict) else {}
    erc8004 = report.get("erc8004") if isinstance(report.get("erc8004"), dict) else {}
    runtime_publication = (
        report.get("runtimePublication") if isinstance(report.get("runtimePublication"), dict) else {}
    )
    authority = report.get("authority") if isinstance(report.get("authority"), dict) else {}
    live_channels = report.get("liveChannels") if isinstance(report.get("liveChannels"), dict) else {}
    email = live_channels.get("email") if isinstance(live_channels.get("email"), dict) else {}
    email_readiness = email.get("readiness") if isinstance(email.get("readiness"), dict) else {}
    development_memory = (
        report.get("developmentMemory") if isinstance(report.get("developmentMemory"), dict) else {}
    )
    latest_documents = development_memory.get("latestDocuments") or []
    edge_counts = development_memory.get("edgeCounts") or []
    policy_adaptation = (
        report.get("policyAdaptation") if isinstance(report.get("policyAdaptation"), dict) else {}
    )
    adaptation_proposals = policy_adaptation.get("recentProposals") or []
    active_priors = policy_adaptation.get("activePriors") or []
    effect_channels = report.get("effectChannels") if isinstance(report.get("effectChannels"), list) else []
    live_effect_channels = [row for row in effect_channels if row.get("state") == "live"]
    counterparty_minimax = (
        report.get("counterpartyMinimax") if isinstance(report.get("counterpartyMinimax"), dict) else {}
    )
    counterparties = counterparty_minimax.get("counterparties") or []
    protected_assets = counterparty_minimax.get("protectedAssets") or []
    minimax_evaluations = counterparty_minimax.get("minimaxEvaluations") or []
    information_flow = report.get("informationFlow") if isinstance(report.get("informationFlow"), dict) else {}
    info_nodes = information_flow.get("nodes") or []
    info_flows = information_flow.get("flows") or []
    health = report.get("healthEvaluation") if isinstance(report.get("healthEvaluation"), dict) else {}
    process_lines = [
        f"  {label}: {'running' if ok else 'down'}"
        for label, ok in sorted((report.get("processes") or {}).items())
    ]
    return "\n".join(
        [
            f"agent: {report.get('agentDid')}",
            f"organism: {report.get('organismState')} score={report.get('organismScore')}",
            (
                "health: "
                f"{health.get('level', 'unknown')} "
                f"warnings={len(health.get('warnings') or [])} "
                f"failures={len(health.get('failures') or [])}"
            ),
            (
                "homeostasis: "
                f"{homeostasis.get('viabilityState')} "
                f"confidence={homeostasis.get('confidence')} entropy={homeostasis.get('entropy')}"
            ),
            f"outcome: {outcome.get('dispatchState')} success={outcome.get('success')}",
            f"learningUpdatedAt: {learning.get('updatedAt')}",
            (
                "erc8004: "
                f"{'configured' if erc8004.get('configured') else 'not-configured'} "
                f"agentId={erc8004.get('agentId') or '--'}"
            ),
            (
                "runtimePublication: "
                f"{'verified' if runtime_publication.get('verified') else 'pending'} "
                f"receipt={((runtime_publication.get('runtimeReceipt') or {}).get('job_id') or '--')}"
            ),
            f"authority: policies={len(authority.get('policies') or [])} recentEffects={len(authority.get('recentEffects') or [])}",
            (
                "emailLive: "
                f"{'ready' if email_readiness.get('ready') else 'blocked'} "
                f"blockers={','.join(email_readiness.get('blockers') or []) or '--'}"
            ),
            (
                "developmentMemory: "
                f"{'available' if development_memory.get('available') else 'unavailable'} "
                f"docs={len(latest_documents)} edgeKinds={len(edge_counts)}"
            ),
            (
                "policyAdaptation: "
                f"{'available' if policy_adaptation.get('available') else 'unavailable'} "
                f"proposals={len(adaptation_proposals)} activePriors={len(active_priors)}"
            ),
            f"effectChannels: live={len(live_effect_channels)} total={len(effect_channels)}",
            (
                "counterpartyMinimax: "
                f"{'available' if counterparty_minimax.get('available') else 'unavailable'} "
                f"counterparties={len(counterparties)} protectedAssets={len(protected_assets)} "
                f"evaluations={len(minimax_evaluations)}"
            ),
            (
                "informationFlow: "
                f"{'available' if information_flow.get('available') else 'unavailable'} "
                f"nodes={len(info_nodes)} flows={len(info_flows)}"
            ),
            "processes:",
            *process_lines,
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report local agent organism status")
    parser.add_argument("--agent-did", default=os.environ.get("AGENT_DID", "did:etzhayyim:agent:local"))
    parser.add_argument("--json", action="store_true", help="emit JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    load_env_file()
    if not os.environ.get("RW_URL"):
        rw_url = load_keychain_secret(service="etzhayyim.rw", account="ROOT_URL")
        if rw_url:
            os.environ["RW_URL"] = rw_url
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args(argv)
    report = load_status_report(args.agent_did)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, default=str))
    else:
        print(format_text(report))


if __name__ == "__main__":
    main()
