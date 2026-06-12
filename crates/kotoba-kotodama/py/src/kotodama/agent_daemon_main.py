"""Local active-inference daemon.

This process keeps the agent loop resident. The local LLM is used as a planner
inside the loop; effectful work still goes through BPMN tasks and gate rows.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import argparse
import asyncio
import json
import logging
import os
import signal
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from kotodama.ingest.zeebe import _run_process_async
from kotodama.local_agent_env import load_env_file, load_keychain_secret
from kotodama.local_llm import LocalLlmConfig, chat_json
from kotodama.primitives.active_inference import (
    build_dispatch_receipt_observation,
    classify_real_world_effect,
    adapt_policy,
    evaluate_autonomous_policy,
    evaluate_viability,
    expected_free_energy,
    infer_effect_class,
    plan_real_world_dispatch,
    stable_hash,
    verify_delegated_authority,
)

LOG = logging.getLogger("agent_daemon")

DEFAULT_PROCESS_ID = "agent_active_inference_tick"
DEFAULT_AUTONOMOUS_DISPATCH_PROCESS_ID = "agent_realworld_autonomous_dispatch"
DEFAULT_HOMEOSTASIS_PROCESS_ID = "agent_homeostasis_watch"
DEFAULT_HOMEOSTASIS_OBSERVATION_PROCESS_ID = "agent_homeostasis_metric_observation"
DEFAULT_SELF_REPAIR_PROCESS_ID = "agent_runtime_lease_autopilot"
HOMEOSTASIS_BELIEF_STATE_KEY = "local-agent-daemon.health"
OUTCOME_BELIEF_STATE_KEY = "local-agent-daemon.outcomes"
LEARNING_BELIEF_STATE_KEY = "local-agent-daemon.learning"
SELF_REPAIR_VIABILITY_STATES = {"conserve", "repair", "hibernate", "halted"}
CADENCE_MULTIPLIER_BY_STATE = {
    "normal": 1.0,
    "conserve": 2.0,
    "repair": 2.0,
    "hibernate": 6.0,
    "halted": 12.0,
}
LOCAL_HEALTH_LAUNCHD_LABELS = (
    "com.etzhayyim.agent-daemon",
    "com.etzhayyim.agent-zeebe-worker",
    "com.etzhayyim.zeebe-port-forward",
)
LOCAL_HEALTH_LOG_PATHS = (
    "/tmp/com.etzhayyim.agent-daemon.err.log",
    "/tmp/com.etzhayyim.agent-zeebe-worker.err.log",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_daemon_mode(value: str | None) -> str:
    normalized = (value or "dry-run").strip().lower().replace("_", "-")
    if normalized in {"zeebe", "run", "live"}:
        return "zeebe"
    if normalized in {"once", "dry-run", "dryrun", "log"}:
        return "dry-run"
    return "dry-run"


def env_flag(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "live"}


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ollama_tags_url(endpoint: str) -> str:
    if endpoint.endswith("/api/chat"):
        return endpoint[: -len("/api/chat")] + "/api/tags"
    return endpoint.rstrip("/") + "/api/tags"


def probe_ollama_endpoint(endpoint: str, *, timeout_sec: float = 2.0) -> dict[str, Any]:
    if not endpoint:
        return {"ok": False, "reason": "endpoint_missing"}
    request = urllib.request.Request(_ollama_tags_url(endpoint), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            return {"ok": 200 <= int(response.status) < 500, "status": int(response.status)}
    except (OSError, urllib.error.URLError) as exc:
        return {"ok": False, "reason": str(exc)}


def launchd_label_running(label: str) -> bool:
    try:
        proc = subprocess.run(
            ["launchctl", "list", label],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    stdout = proc.stdout or ""
    return '"PID" = ' in stdout and '"PID" = 0' not in stdout


def launchd_kickstart_label(label: str, *, uid: int | None = None) -> dict[str, Any]:
    domain = f"gui/{uid if uid is not None else os.getuid()}/{label}"
    try:
        proc = subprocess.run(
            ["launchctl", "kickstart", "-k", domain],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "label": label, "error": str(exc)}
    return {
        "ok": proc.returncode == 0,
        "label": label,
        "returnCode": proc.returncode,
        "stdout": (proc.stdout or "")[-500:],
        "stderr": (proc.stderr or "")[-500:],
    }


def _parse_log_timestamp(line: str) -> datetime | None:
    if len(line) < 19:
        return None
    prefix = line[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(prefix, fmt)
        except ValueError:
            continue
    return None


def count_recent_log_failures(
    paths: tuple[str, ...] = LOCAL_HEALTH_LOG_PATHS,
    *,
    now: datetime | None = None,
    window_sec: int = 3600,
) -> int:
    failure_markers = (" ERROR ", "Traceback", "tick failed")
    reference_time = now or datetime.now()
    cutoff = reference_time.replace(tzinfo=None) - timedelta(seconds=max(0, window_sec))
    failures = 0
    for path in paths:
        current_event_recent = False
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()[-200:]
        except OSError:
            continue
        for line in lines:
            timestamp = _parse_log_timestamp(line)
            if timestamp is not None:
                current_event_recent = timestamp >= cutoff
            if current_event_recent and any(marker in line for marker in failure_markers):
                failures += 1
    return failures


def collect_local_homeostasis_metrics(
    *,
    llm_endpoint: str = "",
    launchd_labels: tuple[str, ...] = LOCAL_HEALTH_LAUNCHD_LABELS,
    log_paths: tuple[str, ...] = LOCAL_HEALTH_LOG_PATHS,
    probe_ollama: bool = True,
) -> dict[str, Any]:
    launchd = {label: launchd_label_running(label) for label in launchd_labels}
    log_window_sec = int(_float_env("AGENT_LOG_FAILURE_WINDOW_SEC", 3600))
    log_failures = count_recent_log_failures(log_paths, window_sec=log_window_sec)
    ollama = probe_ollama_endpoint(llm_endpoint) if probe_ollama else {"ok": True, "skipped": True}
    failed_services = sum(1 for ok in launchd.values() if not ok)
    failed_probes = failed_services + (0 if ollama.get("ok") else 1)
    probe_count = len(launchd) + 1
    base_error = failed_probes / max(1, probe_count)
    log_error = min(0.5, log_failures / 20.0)
    error_rate = _clamp01(base_error + log_error)
    return {
        "source": "measured",
        "launchd": launchd,
        "ollama": ollama,
        "logFailures": log_failures,
        "logFailureWindowSec": log_window_sec,
        "errorRate1h": round(error_rate, 4),
        "toolSuccessRate1h": round(_clamp01(1.0 - error_rate), 4),
    }


def build_viability_inputs(llm_config: LocalLlmConfig) -> dict[str, Any]:
    measured = env_flag(os.environ.get("AGENT_HOMEOSTASIS_MEASURED"), default=True)
    metrics = (
        collect_local_homeostasis_metrics(llm_endpoint=llm_config.endpoint)
        if measured
        else {"source": "env"}
    )
    return {
        "compute_budget_remaining": _float_env("AGENT_COMPUTE_BUDGET_REMAINING", 1.0),
        "storage_pressure": _float_env("AGENT_STORAGE_PRESSURE", 0.0),
        "lease_seconds_remaining": int(_float_env("AGENT_LEASE_SECONDS_REMAINING", 3600)),
        "error_rate_1h": metrics.get("errorRate1h", _float_env("AGENT_ERROR_RATE_1H", 0.0)),
        "tool_success_rate_1h": metrics.get(
            "toolSuccessRate1h",
            _float_env("AGENT_TOOL_SUCCESS_RATE_1H", 1.0),
        ),
        "energy_or_cost_proxy": _float_env("AGENT_ENERGY_OR_COST_PROXY", 0.0),
        "metrics": metrics,
    }


def harden_runtime_viability(
    viability: dict[str, Any],
    *,
    metrics: dict[str, Any],
    lease_repair_floor_sec: int = 1800,
    lease_hibernate_floor_sec: int = 300,
) -> dict[str, Any]:
    hardened = dict(viability)
    normalized = dict(viability.get("normalized") if isinstance(viability.get("normalized"), dict) else {})
    state = str(hardened.get("viabilityState") or "normal")
    blockers = list(hardened.get("blockers") if isinstance(hardened.get("blockers"), list) else [])
    next_actions = list(
        hardened.get("nextActions") if isinstance(hardened.get("nextActions"), list) else []
    )
    maintenance_reasons: list[str] = []
    lease_seconds = int(_float_value(normalized.get("leaseSecondsRemaining"), 3600))
    if 0 < lease_seconds <= lease_hibernate_floor_sec and state not in {"halted", "hibernate"}:
        state = "hibernate"
        maintenance_reasons.append("maintenance:lease_critical")
        blockers.append("runtime_lease_critical")
        next_actions.extend(["preserve_checkpoint", "renew_or_hibernate_runtime_lease"])
    elif 0 < lease_seconds <= lease_repair_floor_sec and state not in {"halted", "hibernate", "repair"}:
        state = "repair"
        maintenance_reasons.append("maintenance:lease_renewal_due")
        blockers.append("runtime_lease_renewal_due")
        next_actions.extend(["pause_effectful_dispatch", "renew_runtime_lease"])

    launchd = metrics.get("launchd") if isinstance(metrics.get("launchd"), dict) else {}
    failed_services = [label for label, ok in launchd.items() if not ok]
    ollama = metrics.get("ollama") if isinstance(metrics.get("ollama"), dict) else {}
    if (failed_services or ollama.get("ok") is False) and state not in {"halted", "hibernate"}:
        state = "repair"
        maintenance_reasons.append("maintenance:local_service_degraded")
        blockers.append("local_service_degraded")
        next_actions.extend(["run_health_checks", "restart_degraded_services"])

    hardened["viabilityState"] = state
    hardened["blockers"] = sorted(set(blockers))
    hardened["nextActions"] = sorted(set(next_actions or ["continue_active_inference_tick"]))
    hardened["normalized"] = normalized
    if failed_services:
        hardened["failedLaunchdServices"] = sorted(set(failed_services))
    if ollama.get("ok") is False:
        hardened["ollamaRepairNeeded"] = True
    if maintenance_reasons:
        hardened["maintenanceReasons"] = sorted(set(maintenance_reasons))
    return hardened


def build_tick_prompt(*, agent_did: str, state: dict[str, Any]) -> list[dict[str, str]]:
    state_json = json.dumps(state, sort_keys=True, ensure_ascii=False, default=str)
    return [
        {
            "role": "system",
            "content": (
                "Return compact JSON only. Keys: summary, observations, candidateActions, "
                "homeostasisHints, realWorldEffectProposals. Do not execute tools."
            ),
        },
        {
            "role": "user",
            "content": (
                f"agentDid={agent_did}\n"
                f"state={state_json}\n"
                "Use empty arrays when no action is needed."
            ),
        },
    ]


def load_homeostasis_belief_direct(agent_did: str) -> dict[str, Any] | None:
    if not os.environ.get("RW_URL"):
        return None

    row = None
    for attempt in range(2):
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    """
                    SELECT vertex_id, state_value_json, posterior_confidence, posterior_entropy,
                           updated_from_observation, updated_at
                    FROM vertex_agent_belief_state
                    WHERE agent_did = %s AND belief_kind = %s AND state_key = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (agent_did, "runtime.homeostasis", HOMEOSTASIS_BELIEF_STATE_KEY),
                )
                row = (_res[0] if _res else None)
            break
        except Exception as exc:
            if attempt == 0:
                LOG.debug("homeostasis belief retry after connection error: %s", exc)
                time.sleep(0.5)
            else:
                LOG.warning("homeostasis belief unavailable: %s", exc)
                return None
    if not row:
        return None
    try:
        state_value = json.loads(row[1] or "{}")
    except json.JSONDecodeError:
        state_value = {}
    return {
        "vertexId": row[0],
        "beliefKind": "runtime.homeostasis",
        "stateKey": HOMEOSTASIS_BELIEF_STATE_KEY,
        "stateValue": state_value if isinstance(state_value, dict) else {},
        "posteriorConfidence": _clamp01(_float_value(row[2], 0.0)),
        "posteriorEntropy": _clamp01(_float_value(row[3], 1.0)),
        "updatedFromObservation": row[4],
        "updatedAt": row[5],
    }


def load_learning_belief_direct(agent_did: str) -> dict[str, Any] | None:
    if not os.environ.get("RW_URL"):
        return None

    row = None
    for attempt in range(2):
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    """
                    SELECT vertex_id, state_value_json, posterior_confidence, posterior_entropy,
                           updated_from_observation, updated_at
                    FROM vertex_agent_belief_state
                    WHERE agent_did = %s AND belief_kind = %s AND state_key = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (agent_did, "runtime.learning", LEARNING_BELIEF_STATE_KEY),
                )
                row = (_res[0] if _res else None)
            break
        except Exception as exc:
            if attempt == 0:
                LOG.debug("learning belief retry after connection error: %s", exc)
                time.sleep(0.5)
            else:
                LOG.warning("learning belief unavailable: %s", exc)
                return None
    if not row:
        return None
    try:
        state_value = json.loads(row[1] or "{}")
    except json.JSONDecodeError:
        state_value = {}
    return {
        "vertexId": row[0],
        "beliefKind": "runtime.learning",
        "stateKey": LEARNING_BELIEF_STATE_KEY,
        "stateValue": state_value if isinstance(state_value, dict) else {},
        "posteriorConfidence": _clamp01(_float_value(row[2], 0.0)),
        "posteriorEntropy": _clamp01(_float_value(row[3], 1.0)),
        "updatedFromObservation": row[4],
        "updatedAt": row[5],
    }


def derive_policy_from_homeostasis_belief(
    *,
    belief: dict[str, Any] | None,
    controls: dict[str, Any],
    min_confidence: float = 0.7,
    max_entropy: float = 0.3,
) -> dict[str, Any]:
    effective_controls = dict(controls)
    reasons: list[str] = []
    confidence = 1.0
    entropy = 0.0
    if belief:
        confidence = _clamp01(_float_value(belief.get("posteriorConfidence"), 0.0))
        entropy = _clamp01(_float_value(belief.get("posteriorEntropy"), 1.0))
        if confidence < min_confidence:
            reasons.append("belief:low_confidence")
        if entropy > max_entropy:
            reasons.append("belief:high_entropy")
    else:
        reasons.append("belief:missing")
    if reasons:
        effective_controls["effectDispatchAllowed"] = False
        effective_controls["effectDispatchSuppressedReason"] = ",".join(reasons)
        effective_controls["cadenceMultiplier"] = max(
            float(effective_controls.get("cadenceMultiplier", 1.0) or 1.0),
            2.0,
        )
    return {
        "policyKind": "runtime.homeostasis",
        "policyVersion": "belief-gated-v1",
        "beliefStateKey": HOMEOSTASIS_BELIEF_STATE_KEY,
        "beliefSnapshotHash": stable_hash(belief or {})[:24],
        "minPosteriorConfidence": min_confidence,
        "maxPosteriorEntropy": max_entropy,
        "posteriorConfidence": confidence,
        "posteriorEntropy": entropy,
        "policyReasons": reasons,
        "effectiveControls": effective_controls,
    }


def build_tick_variables(
    *,
    agent_did: str,
    llm_result: dict[str, Any],
    viability: dict[str, Any],
    tick_id: str | None = None,
) -> dict[str, Any]:
    llm_json = llm_result.get("json")
    if not isinstance(llm_json, dict):
        llm_json = {}
    observations = llm_json.get("observations")
    candidate_actions = llm_json.get("candidateActions")
    effect_proposals = llm_json.get("realWorldEffectProposals")
    resolved_tick_id = tick_id or "agent-daemon-tick-" + stable_hash(
        {"agentDid": agent_did, "at": _now_iso()}
    )[:24]
    return {
        "agentDid": agent_did,
        "tickId": resolved_tick_id,
        "observedAt": _now_iso(),
        "localLlm": {
            "provider": llm_result.get("provider", ""),
            "model": llm_result.get("model", ""),
            "endpoint": llm_result.get("endpoint", ""),
            "summary": llm_json.get("summary", ""),
            "rawHash": stable_hash(llm_result.get("content", "")),
        },
        "observations": observations if isinstance(observations, list) else [],
        "candidateActions": candidate_actions if isinstance(candidate_actions, list) else [],
        "realWorldEffectProposals": effect_proposals if isinstance(effect_proposals, list) else [],
        "viability": viability,
        "mokutekiGatePass": viability.get("viabilityState") not in {"hibernate", "halted"},
    }


def build_effect_dispatch_variables(
    *,
    agent_did: str,
    proposal: dict[str, Any],
    tick_id: str,
    default_policy_ref: str = "",
) -> dict[str, Any]:
    payload = proposal.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    policy_ref = str(proposal.get("policyRef") or default_policy_ref or "")
    action_id = str(proposal.get("actionProposalId") or proposal.get("actionId") or tick_id)
    return {
        "agentDid": str(proposal.get("agentDid") or agent_did),
        "principalDid": str(proposal.get("principalDid") or ""),
        "actionProposalId": action_id,
        "channel": str(proposal.get("channel") or ""),
        "effectClass": str(
            proposal.get("effectClass")
            or infer_effect_class(str(proposal.get("channel") or ""), "", payload_dict)
        ),
        "targetRef": str(proposal.get("targetRef") or payload_dict.get("to") or ""),
        "summary": str(proposal.get("summary") or ""),
        "payload": payload_dict,
        "approvalRef": str(proposal.get("approvalRef") or ""),
        "authorityRef": str(proposal.get("authorityRef") or proposal.get("authority_ref") or ""),
        "autonomousAuthorityRef": str(proposal.get("autonomousAuthorityRef") or ""),
        "policyRef": policy_ref,
        "policy": proposal.get("policy") if isinstance(proposal.get("policy"), dict) else {},
        "budgetRef": str(proposal.get("budgetRef") or ""),
        "sourceTickId": tick_id,
    }


def dispatch_dedupe_key(variables: dict[str, Any]) -> str:
    return stable_hash(
        {
            "agentDid": variables.get("agentDid", ""),
            "channel": variables.get("channel", ""),
            "payload": variables.get("payload", {}),
            "authorityRef": variables.get("autonomousAuthorityRef", ""),
            "policyRef": variables.get("policyRef", ""),
        }
    )


def select_real_world_action_proposals(
    *,
    proposals: Any,
    agent_did: str,
    tick_id: str,
    runtime_policy: dict[str, Any],
    learning_belief: dict[str, Any] | None = None,
    default_policy_ref: str = "",
    max_dispatches: int = 1,
    authority_policy_loader: Any = None,
    minimax_information_context: dict[str, Any] | None = None,
    knowledge_graph_fitness_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proposal_list = proposals if isinstance(proposals, list) else []
    effective_controls = runtime_policy.get("effectiveControls")
    if not isinstance(effective_controls, dict):
        effective_controls = {}
    policy_reasons = runtime_policy.get("policyReasons")
    policy_reasons_list = policy_reasons if isinstance(policy_reasons, list) else []
    dispatch_allowed_by_runtime = bool(effective_controls.get("effectDispatchAllowed", False))
    learning_state = learning_belief.get("stateValue") if isinstance(learning_belief, dict) else {}
    if not isinstance(learning_state, dict):
        learning_state = {}
    channel_priors = learning_state.get("channelPriors")
    if not isinstance(channel_priors, dict):
        channel_priors = {}
    policy_priors = learning_state.get("policyPriors")
    if not isinstance(policy_priors, dict):
        policy_priors = {}
    minimax_context = minimax_information_context if isinstance(minimax_information_context, dict) else {}
    kg_context = (
        knowledge_graph_fitness_context
        if isinstance(knowledge_graph_fitness_context, dict)
        else {}
    )
    decisions: list[dict[str, Any]] = []

    for index, raw in enumerate(proposal_list):
        if not isinstance(raw, dict):
            decisions.append(
                {
                    "index": index,
                    "accepted": False,
                    "score": -1000.0,
                    "blockers": ["proposal_not_object"],
                    "proposal": None,
                    "variables": {},
                }
            )
            continue
        variables = build_effect_dispatch_variables(
            agent_did=agent_did,
            proposal=raw,
            tick_id=tick_id,
            default_policy_ref=default_policy_ref,
        )
        blockers: list[str] = []
        if not dispatch_allowed_by_runtime:
            blockers.extend(f"runtime_policy:{reason}" for reason in policy_reasons_list)
            if not policy_reasons_list:
                blockers.append("runtime_policy:dispatch_suppressed")
        if not variables["channel"]:
            blockers.append("channel_required")
        if not variables["autonomousAuthorityRef"]:
            blockers.append("autonomous_authority_required")
        if not variables["policyRef"]:
            blockers.append("policy_ref_required")
        if variables["effectClass"] in {"financial_commitment", "physical_dispatch"} and not variables["budgetRef"]:
            blockers.append("budget_ref_required")
        authority_policy = variables["policy"]
        should_check_authority = (
            dispatch_allowed_by_runtime
            and bool(variables["autonomousAuthorityRef"])
            and bool(variables["policyRef"])
        )
        if should_check_authority and not authority_policy and authority_policy_loader is not None:
            authority_policy = authority_policy_loader(
                authority_ref=variables["autonomousAuthorityRef"],
                policy_ref=variables["policyRef"],
                agent_did=variables["agentDid"],
            )
            if not authority_policy:
                blockers.append("authority_policy_missing")
        if should_check_authority:
            blockers.extend(
                verify_delegated_authority(
                    authority_ref=variables["autonomousAuthorityRef"],
                    policy_ref=variables["policyRef"],
                    channel=variables["channel"],
                    effect_class=variables["effectClass"],
                    payload=variables["payload"],
                    target_ref=variables["targetRef"],
                    budget_ref=variables["budgetRef"],
                    policy=authority_policy if isinstance(authority_policy, dict) else {},
                )
            )
        blockers.extend(
            evaluate_autonomous_policy(
                channel=variables["channel"],
                payload=variables["payload"],
                policy=authority_policy if isinstance(authority_policy, dict) else {},
            )
        )
        priority = _float_value(raw.get("priority", raw.get("expectedUtility", 0.0)), 0.0)
        urgency = _float_value(raw.get("urgency", 0.0), 0.0)
        channel_prior = _float_value(channel_priors.get(variables["channel"]), 0.0)
        policy_prior = _float_value(policy_priors.get(variables["policyRef"]), 0.0)
        adversarial_regret = _float_value(
            raw.get("adversarialRegret", minimax_context.get("adversarialRegret", 0.0)),
            0.0,
        )
        protected_asset_violation = _float_value(
            raw.get("protectedAssetViolation", minimax_context.get("protectedAssetViolation", 0.0)),
            0.0,
        )
        counterparty_uncertainty = _float_value(
            raw.get("counterpartyUncertainty", minimax_context.get("counterpartyUncertainty", 0.0)),
            0.0,
        )
        information_height_gain = _float_value(
            raw.get("informationHeightGain", minimax_context.get("informationHeightGain", 0.0)),
            0.0,
        )
        flow_control_gain = _float_value(
            raw.get("flowControlGain", minimax_context.get("flowControlGain", 0.0)),
            0.0,
        )
        kg_development_gain = _float_value(
            raw.get("kgDevelopmentGain", kg_context.get("kgDevelopmentGain", 0.0)),
            0.0,
        )
        kg_prior_weight = _float_value(kg_context.get("activePriorWeight", 1.0), 1.0)
        weighted_kg_development_gain = round(kg_development_gain * max(0.0, kg_prior_weight), 6)
        minimax_penalty = adversarial_regret + protected_asset_violation + counterparty_uncertainty
        information_gain = information_height_gain + flow_control_gain + weighted_kg_development_gain
        score = round(
            priority
            + urgency
            + channel_prior
            + policy_prior
            + information_gain
            - minimax_penalty
            - (100.0 * len(blockers)),
            4,
        )
        efe = expected_free_energy(
            {
                "risk": raw.get("risk", adversarial_regret),
                "ambiguity": raw.get("ambiguity", 0.0),
                "epistemicValue": raw.get("epistemicValue", 0.0),
                "viabilityPenalty": raw.get("viabilityPenalty", 0.0),
                "externalEffectPenalty": raw.get("externalEffectPenalty", 0.0),
                "adversarialRegret": adversarial_regret,
                "protectedAssetViolation": protected_asset_violation,
                "counterpartyUncertainty": counterparty_uncertainty,
                "informationHeightGain": information_height_gain,
                "flowControlGain": flow_control_gain,
                "kgDevelopmentGain": weighted_kg_development_gain,
            }
        )
        decisions.append(
            {
                "index": index,
                "accepted": not blockers,
                "score": score,
                "learningPrior": round(channel_prior + policy_prior, 4),
                "minimaxPenalty": round(minimax_penalty, 4),
                "counterpartyUncertainty": round(counterparty_uncertainty, 4),
                "informationGain": round(information_gain, 4),
                "kgPriorWeight": round(max(0.0, kg_prior_weight), 4),
                "expectedFreeEnergy": efe,
                "blockers": blockers,
                "proposal": raw,
                "variables": {**variables, "resolvedAuthorityPolicy": authority_policy if isinstance(authority_policy, dict) else {}},
            }
        )

    accepted = sorted(
        (decision for decision in decisions if decision["accepted"]),
        key=lambda decision: (-float(decision["score"]), int(decision["index"])),
    )[: max(0, max_dispatches)]
    accepted_indexes = {int(decision["index"]) for decision in accepted}
    for decision in decisions:
        if decision["accepted"] and int(decision["index"]) not in accepted_indexes:
            decision["accepted"] = False
            decision["blockers"] = ["action_selection:max_dispatches"]
    return {
        "policyVersion": "realworld-action-selection-v1",
        "maxDispatches": max_dispatches,
        "selectedCount": len(accepted),
        "selectedProposals": [decision["proposal"] for decision in accepted],
        "decisions": decisions,
    }


def load_minimax_information_context_direct(agent_did: str) -> dict[str, Any]:
    if not os.environ.get("RW_URL"):
        return {
            "available": False,
            "adversarialRegret": 0.0,
            "protectedAssetViolation": 0.0,
            "counterpartyUncertainty": 0.0,
            "informationHeightGain": 0.0,
            "flowControlGain": 0.0,
        }

    context = {
        "available": True,
        "adversarialRegret": 0.0,
        "protectedAssetViolation": 0.0,
        "counterpartyUncertainty": 0.0,
        "informationHeightGain": 0.0,
        "flowControlGain": 0.0,
        "source": {},
    }
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                SELECT action_id, counterparty_ref, minimax_regret,
                       protected_asset_violation, selected_response, created_at
                FROM vertex_agent_minimax_evaluation
                WHERE agent_did = %s AND evaluation_state = 'evaluated'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (agent_did,),
            )
            row = (_res[0] if _res else None)
            if row:
                context["adversarialRegret"] = _float_value(row[2], 0.0)
                context["protectedAssetViolation"] = _float_value(row[3], 0.0)
                context["source"]["minimax"] = {
                    "actionId": row[0],
                    "counterpartyRef": row[1],
                    "selectedResponse": row[4],
                    "createdAt": row[5],
                }
            _res = client.q(
                """
                SELECT MAX(uncertainty)
                FROM vertex_agent_counterparty_model
                WHERE agent_did = %s
                """,
                (agent_did,),
            )
            uncertainty_row = (_res[0] if _res else None)
            context["counterpartyUncertainty"] = round(
                max(0.0, min(1.0, _float_value(uncertainty_row[0] if uncertainty_row else 0.0, 0.0))),
                6,
            )
            try:
                _res = client.q(
                    """
                    SELECT MAX(max_information_height)
                    FROM mv_agent_information_height
                    WHERE agent_did = %s
                    """,
                    (agent_did,),
                )
                height_row = (_res[0] if _res else None)
            except Exception:
                _res = client.q(
                    """
                    SELECT MAX(abstraction_level)
                    FROM vertex_agent_information_node
                    WHERE agent_did = %s
                    """,
                    (agent_did,),
                )
                height_row = (_res[0] if _res else None)
            max_height = _float_value(height_row[0] if height_row else 0.0, 0.0)
            context["informationHeightGain"] = round(max(0.0, min(1.0, max_height / 10.0)), 6)
            try:
                _res = client.q("SELECT MAX(avg_control_score) FROM mv_agent_information_flow_control")
                flow_row = (_res[0] if _res else None)
            except Exception:
                _res = client.q("SELECT MAX(control_score) FROM edge_agent_information_flows_to")
                flow_row = (_res[0] if _res else None)
            context["flowControlGain"] = round(max(0.0, min(1.0, _float_value(flow_row[0] if flow_row else 0.0, 0.0))), 6)
    except Exception as exc:  # noqa: BLE001
        context["available"] = False
        context["error"] = str(exc)[:300]
    return context


def load_knowledge_graph_fitness_context_direct(agent_did: str) -> dict[str, Any]:
    if not os.environ.get("RW_URL"):
        return {
            "available": False,
            "kgDevelopmentGain": 0.0,
            "kgCoverageScore": 0.0,
            "missingEdgePenalty": 0.0,
            "evolutionFitness": 0.0,
        }

    context = {
        "available": True,
        "kgDevelopmentGain": 0.0,
        "kgCoverageScore": 0.0,
        "missingEdgePenalty": 0.0,
        "evolutionFitness": 0.0,
        "activePriorWeight": 1.0,
        "source": {},
    }
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                SELECT COUNT(*)
                FROM vertex_agent_development_document
                WHERE agent_did = %s AND status = 'active'
                """,
                (agent_did,),
            )
            doc_count = int(((_res[0] if _res else None) or [0])[0] or 0)
            _res = client.q(
                """
                SELECT COUNT(*)
                FROM edge_agent_development_document_ref edge
                JOIN vertex_agent_development_document doc
                  ON edge.src_vid = doc.vertex_id
                WHERE doc.agent_did = %s
                """,
                (agent_did,),
            )
            dev_edge_count = int(((_res[0] if _res else None) or [0])[0] or 0)
            _res = client.q(
                """
                SELECT COUNT(*)
                FROM vertex_agent_information_node
                WHERE agent_did = %s
                """,
                (agent_did,),
            )
            info_node_count = int(((_res[0] if _res else None) or [0])[0] or 0)
            _res = client.q(
                """
                SELECT COUNT(*)
                FROM edge_agent_information_flows_to edge
                JOIN vertex_agent_information_node node
                  ON edge.src_vid = node.vertex_id
                WHERE node.agent_did = %s
                """,
                (agent_did,),
            )
            flow_edge_count = int(((_res[0] if _res else None) or [0])[0] or 0)
    except Exception as exc:  # noqa: BLE001
        context["available"] = False
        context["error"] = str(exc)[:300]
        return context

    graph_units = doc_count + dev_edge_count + info_node_count + flow_edge_count
    coverage_score = _clamp01(graph_units / 20.0)
    expected_edges = max(1, doc_count * 2)
    edge_ratio = _clamp01(dev_edge_count / expected_edges)
    missing_edge_penalty = round(1.0 - edge_ratio, 6)
    kg_development_gain = round(max(0.0, coverage_score - (missing_edge_penalty * 0.25)), 6)
    evolution_fitness = round(
        _clamp01((kg_development_gain * 0.7) + (edge_ratio * 0.3)),
        6,
    )
    prior_weight = _float_value(
        load_prior_preference_direct(agent_did, "runtime.knowledge_graph.development").get("weight"),
        1.0,
    )
    context.update(
        {
            "kgDevelopmentGain": kg_development_gain,
            "kgCoverageScore": round(coverage_score, 6),
            "missingEdgePenalty": missing_edge_penalty,
            "evolutionFitness": evolution_fitness,
            "activePriorWeight": round(max(0.0, min(5.0, prior_weight)), 6),
            "source": {
                "developmentDocumentCount": doc_count,
                "developmentEdgeCount": dev_edge_count,
                "informationNodeCount": info_node_count,
                "informationFlowEdgeCount": flow_edge_count,
            },
        }
    )
    return context


def record_knowledge_graph_evolution_direct(
    *,
    agent_did: str,
    tick_id: str,
    knowledge_graph_fitness: dict[str, Any],
    minimax_information_context: dict[str, Any],
) -> dict[str, Any] | None:
    if not os.environ.get("RW_URL"):
        return None

    now = _now_iso()
    props = {
        "kind": "agent_knowledge_graph_fitness",
        "tickId": tick_id,
        "knowledgeGraphFitness": knowledge_graph_fitness,
        "minimaxInformationContext": minimax_information_context,
    }
    vertex_id = "at://" + agent_did + "/com.etzhayyim.apps.standard.shinkaEvolution/kg-" + stable_hash(
        {"agentDid": agent_did, "tickId": tick_id, "props": props}
    )[:24]
    row = {
        "vertex_id": vertex_id,
        "owner_did": agent_did,
        "rkey": "kg-fitness-" + stable_hash({"agentDid": agent_did, "tickId": tick_id})[:16],
        "repo": agent_did,
        "did": agent_did,
        "collection": "com.etzhayyim.apps.standard.shinkaEvolution",
        "actorDid": agent_did,
        "actorName": agent_did.split(":")[-1].split(".")[0] if ":" in agent_did else agent_did,
        "nanoid": stable_hash({"agentDid": agent_did, "tickId": tick_id})[:16],
        "created_at": now,
        "props": json.dumps(props, ensure_ascii=False, sort_keys=True),
    }
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q("DELETE FROM vertex_shinka_evolution WHERE vertex_id = %s", (vertex_id,))
            _res = client.q(
                """
                INSERT INTO vertex_shinka_evolution
                    (vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo,
                     did, collection, "actorDid", "actorName", nanoid, status, created_at, props)
                VALUES (%s, NULL, to_char(now(),'YYYY-MM-DD')::date, 100, %s, %s, %s,
                        %s, %s, %s, %s, %s, 'active', %s, %s)
                """,
                (
                    row["vertex_id"],
                    row["owner_did"],
                    row["rkey"],
                    row["repo"],
                    row["did"],
                    row["collection"],
                    row["actorDid"],
                    row["actorName"],
                    row["nanoid"],
                    row["created_at"],
                    row["props"],
                ),
            )
    except Exception as exc:  # noqa: BLE001
        LOG.warning("knowledge graph evolution write unavailable: %s", exc)
        return {"ok": False, "error": str(exc)[:300], **row}
    return {"ok": True, **row}


def insert_direct_row(table: str, row: dict[str, Any]) -> None:

    columns = list(row)
    placeholders = ", ".join(["%s"] * len(columns))
    names = ", ".join(columns)
    if True:
        client = get_kotoba_client()
        _res = client.q(f"DELETE FROM {table} WHERE vertex_id = %s", (row["vertex_id"],))
        _res = client.q(
            f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
            tuple(row[column] for column in columns),
        )


def load_prior_preference_direct(agent_did: str, preference_key: str) -> dict[str, Any]:
    if not os.environ.get("RW_URL"):
        return {}

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                SELECT vertex_id, preference_key, target_range_json, hard_floor,
                       weight, depends_on_adr, active, updated_at
                FROM vertex_agent_prior_preference
                WHERE agent_did = %s AND preference_key = %s AND active = true
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (agent_did, preference_key),
            )
            row = (_res[0] if _res else None)
    except Exception as exc:  # noqa: BLE001
        LOG.debug("prior preference unavailable: %s", exc)
        return {}
    if not row:
        return {}
    return {
        "vertex_id": row[0],
        "preference_key": row[1],
        "target_range_json": row[2],
        "hard_floor": row[3],
        "weight": _float_value(row[4], 1.0),
        "depends_on_adr": row[5],
        "active": row[6],
        "updated_at": row[7],
    }


def adapt_knowledge_graph_policy_direct(
    *,
    agent_did: str,
    knowledge_graph_fitness: dict[str, Any],
) -> dict[str, Any] | None:
    if not os.environ.get("RW_URL"):
        return None
    if not isinstance(knowledge_graph_fitness, dict) or not knowledge_graph_fitness.get("available"):
        return None
    preference_key = "runtime.knowledge_graph.development"
    current = load_prior_preference_direct(agent_did, preference_key)
    current_weight = _float_value(current.get("weight"), 1.0)
    kg_gain = _clamp01(_float_value(knowledge_graph_fitness.get("kgDevelopmentGain"), 0.0))
    missing_penalty = _clamp01(_float_value(knowledge_graph_fitness.get("missingEdgePenalty"), 0.0))
    proposed_weight = current_weight
    if kg_gain >= 0.75:
        proposed_weight = min(1.5, current_weight + 0.05)
    elif missing_penalty >= 0.25:
        proposed_weight = min(1.5, current_weight + 0.1)
    else:
        proposed_weight = min(1.5, current_weight + 0.02)
    proposal = {
        "weight": round(proposed_weight, 4),
        "targetRange": {
            "kgDevelopmentGain": [0.75, 1.0],
            "missingEdgePenalty": [0.0, 0.1],
            "evolutionFitness": [0.75, 1.0],
        },
        "dependsOnAdr": "adr-2605061200-agi-active-inference-artificial-organism-architecture",
        "evidence": {
            "kind": "knowledge_graph_fitness",
            "kgDevelopmentGain": kg_gain,
            "missingEdgePenalty": missing_penalty,
            "evolutionFitness": knowledge_graph_fitness.get("evolutionFitness", 0.0),
            "source": knowledge_graph_fitness.get("source", {}),
        },
    }
    adaptation = adapt_policy(
        agent_did=agent_did,
        preference_key=preference_key,
        proposal=proposal,
        mokuteki_gate_pass=True,
        triple_witness_pass=True,
        current_preference=current or {"weight": current_weight},
        max_weight_delta=0.1,
    )
    try:
        insert_direct_row("vertex_agent_policy_adaptation_proposal", adaptation["policyProposal"])
        if adaptation.get("accepted") and adaptation.get("preference"):
            insert_direct_row("vertex_agent_prior_preference", adaptation["preference"])
    except Exception as exc:  # noqa: BLE001
        LOG.warning("knowledge graph policy adaptation write unavailable: %s", exc)
        return {"ok": False, "error": str(exc)[:300], **adaptation}
    return {"ok": True, **adaptation}


def build_outcome_belief_row(
    *,
    agent_did: str,
    observation: dict[str, Any],
    dispatch_state: str,
    receipt_ref: str = "",
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    observed_at = str(observation.get("observed_at") or _now_iso())
    source_kind = str(observation.get("source_kind") or "")
    confidence = _clamp01(_float_value(observation.get("confidence"), 0.5))
    uncertainty = _clamp01(_float_value(observation.get("uncertainty"), 1.0 - confidence))
    normalized_state = dispatch_state or ("observed" if source_kind else "unknown")
    success = normalized_state in {"dispatched", "observed", "replied"}
    state_value = {
        "sourceKind": source_kind,
        "sourceRef": str(observation.get("source_ref") or ""),
        "dispatchState": normalized_state,
        "receiptRef": receipt_ref,
        "success": success,
        "blockers": blockers or [],
    }
    return {
        "vertex_id": "agent-belief-outcome-"
        + stable_hash({"agentDid": agent_did, "stateKey": OUTCOME_BELIEF_STATE_KEY})[:24],
        "agent_did": agent_did,
        "belief_kind": "runtime.outcome",
        "state_key": OUTCOME_BELIEF_STATE_KEY,
        "state_value_json": json.dumps(state_value, ensure_ascii=False, sort_keys=True),
        "posterior_confidence": round(confidence, 4),
        "posterior_entropy": round(uncertainty, 4),
        "updated_from_observation": str(observation.get("vertex_id") or ""),
        "updated_at": observed_at,
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.outcomeBelief",
        "owner_did": agent_did,
        "org_id": agent_did,
        "user_id": agent_did,
    }


def build_learning_belief_row(
    *,
    agent_did: str,
    outcome_observation: dict[str, Any],
    dispatch_plan: dict[str, Any],
    dispatch_state: str,
    previous_learning_belief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_state = (
        previous_learning_belief.get("stateValue")
        if isinstance(previous_learning_belief, dict)
        else {}
    )
    if not isinstance(previous_state, dict):
        previous_state = {}
    channel = str(dispatch_plan.get("channel") or "")
    policy_ref = str(dispatch_plan.get("policyRef") or "")
    success = dispatch_state in {"dispatched", "observed", "replied"}
    delta = 0.1 if success else -0.1
    channel_priors = dict(previous_state.get("channelPriors") or {})
    policy_priors = dict(previous_state.get("policyPriors") or {})
    channel_count = dict(previous_state.get("channelCounts") or {})
    policy_count = dict(previous_state.get("policyCounts") or {})
    if channel:
        channel_priors[channel] = round(_clamp01(_float_value(channel_priors.get(channel), 0.0) + 0.5 + delta) - 0.5, 4)
        channel_count[channel] = int(_float_value(channel_count.get(channel), 0.0) + 1)
    if policy_ref:
        policy_priors[policy_ref] = round(
            _clamp01(_float_value(policy_priors.get(policy_ref), 0.0) + 0.5 + delta) - 0.5,
            4,
        )
        policy_count[policy_ref] = int(_float_value(policy_count.get(policy_ref), 0.0) + 1)
    state_value = {
        "channelPriors": channel_priors,
        "policyPriors": policy_priors,
        "channelCounts": channel_count,
        "policyCounts": policy_count,
        "lastOutcome": {
            "channel": channel,
            "policyRef": policy_ref,
            "dispatchState": dispatch_state,
            "success": success,
        },
    }
    confidence = min(0.95, 0.5 + 0.05 * sum(channel_count.values()))
    return {
        "vertex_id": "agent-belief-learning-"
        + stable_hash({"agentDid": agent_did, "stateKey": LEARNING_BELIEF_STATE_KEY})[:24],
        "agent_did": agent_did,
        "belief_kind": "runtime.learning",
        "state_key": LEARNING_BELIEF_STATE_KEY,
        "state_value_json": json.dumps(state_value, ensure_ascii=False, sort_keys=True),
        "posterior_confidence": round(confidence, 4),
        "posterior_entropy": round(1.0 - confidence, 4),
        "updated_from_observation": str(outcome_observation.get("vertex_id") or ""),
        "updated_at": str(outcome_observation.get("observed_at") or _now_iso()),
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.learningBelief",
        "owner_did": agent_did,
        "org_id": agent_did,
        "user_id": agent_did,
    }


def record_outcome_belief_direct(
    *,
    agent_did: str,
    observation: dict[str, Any],
    dispatch_state: str,
    receipt_ref: str = "",
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    row = build_outcome_belief_row(
        agent_did=agent_did,
        observation=observation,
        dispatch_state=dispatch_state,
        receipt_ref=receipt_ref,
        blockers=blockers,
    )
    insert_direct_row("vertex_agent_belief_state", row)
    return {
        "updated": 1,
        "vertexId": row["vertex_id"],
        "stateKey": row["state_key"],
        "mode": "direct",
    }


def record_learning_belief_direct(
    *,
    agent_did: str,
    outcome_observation: dict[str, Any],
    dispatch_plan: dict[str, Any],
    dispatch_state: str,
) -> dict[str, Any]:
    previous = load_learning_belief_direct(agent_did)
    row = build_learning_belief_row(
        agent_did=agent_did,
        outcome_observation=outcome_observation,
        dispatch_plan=dispatch_plan,
        dispatch_state=dispatch_state,
        previous_learning_belief=previous,
    )
    insert_direct_row("vertex_agent_belief_state", row)
    return {
        "updated": 1,
        "vertexId": row["vertex_id"],
        "stateKey": row["state_key"],
        "mode": "direct",
    }


def _dns_short(record_type: str, name: str) -> list[str]:
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


def resend_dns_ready(domain: str = "etzhayyim.com") -> bool:
    dkim = _dns_short("TXT", f"resend._domainkey.{domain}") or _dns_short(
        "CNAME", f"resend._domainkey.{domain}"
    )
    send_txt = _dns_short("TXT", f"send.{domain}")
    send_mx = _dns_short("MX", f"send.{domain}")
    spf_ready = any("include:amazonses.com" in item for item in send_txt)
    mx_ready = any("feedback-smtp" in item and "amazonses.com" in item for item in send_mx)
    return bool(dkim and spf_ready and mx_ready)


def resend_domain_verified(domain: str = "etzhayyim.com") -> bool:
    api_key = os.environ.get("RESEND_API_KEY") or load_keychain_secret(
        service="etzhayyim.resend", account="API_KEY"
    )
    if not api_key:
        return False
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
        return False
    domains = data.get("data") if isinstance(data, dict) else []
    if not isinstance(domains, list):
        return False
    return any(
        isinstance(item, dict)
        and str(item.get("name") or "").lower() == domain.lower()
        and str(item.get("status") or "").lower() == "verified"
        for item in domains
    )


def load_email_live_channel_blockers_direct() -> list[str]:
    if not os.environ.get("RW_URL"):
        return []

    blockers: list[str] = []
    min_send_interval_sec = max(0, int(os.environ.get("AGENT_EMAIL_MIN_SEND_INTERVAL_SEC", "300") or "300"))
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                SELECT status, "error"
                FROM vertex_mailer_outbound_email
                WHERE provider = 'resend' AND status = 'error'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            row = (_res[0] if _res else None)
            if min_send_interval_sec > 0:
                _res = client.q(
                    f"""
                    SELECT status, "error"
                    FROM vertex_mailer_outbound_email
                    WHERE provider = 'resend'
                      AND created_at >= NOW() - INTERVAL '{min_send_interval_sec} seconds'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
                recent_row = (_res[0] if _res else None)
    except Exception as exc:
        LOG.debug("email live channel blocker check unavailable: %s", exc)
        return []
    recent_status = str((recent_row or ["", ""])[0] or "").lower() if "recent_row" in locals() else ""
    recent_error = str((recent_row or ["", ""])[1] or "").lower() if "recent_row" in locals() else ""
    if recent_status:
        blockers.append("resend_min_send_interval_active")
    if "rate_limit_exceeded" in recent_error or "too many requests" in recent_error:
        blockers.append("resend_rate_limited")
    error = str((row or ["", ""])[1] or "").lower()
    if "domain is not verified" in error:
        if resend_domain_verified("etzhayyim.com"):
            return sorted(set(blockers))
        if resend_dns_ready("etzhayyim.com"):
            blockers.extend(["resend_account_domain_verification_pending", "email_live_channel_not_ready"])
            return sorted(set(blockers))
        blockers.extend(["resend_domain_or_sender_unverified", "email_live_channel_not_ready"])
    return sorted(set(blockers))


def autonomous_heartbeat_recently_sent_direct(
    *,
    to_address: str,
    subject_prefix: str,
    cooldown_sec: int,
) -> bool:
    if not os.environ.get("RW_URL"):
        return False

    safe_cooldown_sec = max(0, int(cooldown_sec))
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""
                SELECT vertex_id
                FROM vertex_mailer_outbound_email
                WHERE provider = 'resend'
                  AND status = 'sent'
                  AND to_address = %s
                  AND subject LIKE %s
                  AND created_at >= NOW() - INTERVAL '{safe_cooldown_sec} seconds'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (to_address, f"{subject_prefix}%"),
            )
            return (_res[0] if _res else None) is not None
    except Exception as exc:
        LOG.debug("autonomous heartbeat cooldown check unavailable: %s", exc)
        return False


def build_autonomous_heartbeat_effect_proposals(
    *,
    agent_did: str,
    tick_id: str,
    viability: dict[str, Any],
    existing_proposals: Any,
    default_policy_ref: str = "",
) -> list[dict[str, Any]]:
    if not env_flag(os.environ.get("AGENT_AUTONOMOUS_HEARTBEAT_ENABLED"), default=False):
        return []
    if existing_proposals:
        return []
    if str(viability.get("viabilityState") or "normal") != "normal":
        return []
    target = os.environ.get("AGENT_AUTONOMOUS_HEARTBEAT_EMAIL_TO", "kami-agent@etzhayyim.com").strip()
    if not target or "@" not in target:
        return []
    blockers = load_email_live_channel_blockers_direct()
    if blockers:
        return []
    subject_prefix = os.environ.get(
        "AGENT_AUTONOMOUS_HEARTBEAT_SUBJECT_PREFIX",
        "etzhayyim autonomous organism heartbeat",
    ).strip()
    cooldown_sec = int(_float_env("AGENT_AUTONOMOUS_HEARTBEAT_COOLDOWN_SEC", 21600))
    if autonomous_heartbeat_recently_sent_direct(
        to_address=target,
        subject_prefix=subject_prefix,
        cooldown_sec=cooldown_sec,
    ):
        return []
    observed_at = _now_iso()
    normalized = viability.get("normalized") if isinstance(viability.get("normalized"), dict) else {}
    action_id = "autonomous-heartbeat-email-" + stable_hash(
        {"agentDid": agent_did, "tickId": tick_id, "target": target}
    )[:16]
    return [
        {
            "actionProposalId": action_id,
            "channel": "email",
            "effectClass": "private_send",
            "targetRef": f"mailto:{target}",
            "summary": "Autonomous organism heartbeat",
            "payload": {
                "to": target,
                "subject": f"{subject_prefix} {observed_at}",
                "text": (
                    "Autonomous organism heartbeat.\n"
                    f"agentDid={agent_did}\n"
                    f"tickId={tick_id}\n"
                    f"observedAt={observed_at}\n"
                    f"viabilityState={viability.get('viabilityState', 'normal')}\n"
                    f"errorRate1h={normalized.get('errorRate1h', 0.0)}\n"
                    f"toolSuccessRate1h={normalized.get('toolSuccessRate1h', 1.0)}\n"
                ),
            },
            "autonomousAuthorityRef": os.environ.get(
                "AGENT_AUTONOMOUS_HEARTBEAT_AUTHORITY_REF",
                "capability://agent/email/outbound/low-risk",
            ),
            "policyRef": os.environ.get(
                "AGENT_AUTONOMOUS_HEARTBEAT_POLICY_REF",
                default_policy_ref or "policy://agent/autonomous-email-v1",
            ),
            "priority": 0.2,
            "urgency": 0.1,
        }
    ]


def execute_real_world_action_direct(variables: dict[str, Any]) -> dict[str, Any]:
    from kotodama.ingest import mailer
    from kotodama.agent_authority_policy import load_delegated_authority_policy

    payload = variables.get("payload") if isinstance(variables.get("payload"), dict) else {}
    classified = classify_real_world_effect(
        channel=str(variables.get("channel") or ""),
        payload=payload,
        action_proposal_id=str(variables.get("actionProposalId") or ""),
        agent_did=str(variables.get("agentDid") or ""),
        principal_did=str(variables.get("principalDid") or ""),
        effect_class=str(variables.get("effectClass") or ""),
        target_ref=str(variables.get("targetRef") or ""),
        summary=str(variables.get("summary") or ""),
        approval_ref=str(variables.get("approvalRef") or ""),
        authority_ref=str(variables.get("authorityRef") or ""),
        autonomous_authority_ref=str(variables.get("autonomousAuthorityRef") or ""),
        budget_ref=str(variables.get("budgetRef") or ""),
    )
    effect = classified["realWorldEffect"]
    inline_policy = variables.get("policy") if isinstance(variables.get("policy"), dict) else {}
    authority_policy = inline_policy or load_delegated_authority_policy(
        authority_ref=str(variables.get("authorityRef") or variables.get("autonomousAuthorityRef") or ""),
        policy_ref=str(variables.get("policyRef") or ""),
        agent_did=str(variables.get("agentDid") or ""),
    )
    plan = plan_real_world_dispatch(
        real_world_effect=effect,
        payload=payload,
        autonomous_authority_ref=str(variables.get("autonomousAuthorityRef") or ""),
        policy_ref=str(variables.get("policyRef") or ""),
        budget_ref=str(variables.get("budgetRef") or ""),
        mode="autonomous",
        policy=authority_policy,
    )
    if plan.get("dispatchAllowed") and plan.get("channel") == "email":
        live_blockers = load_email_live_channel_blockers_direct()
        if live_blockers:
            plan = {
                **plan,
                "dispatchAllowed": False,
                "taskType": "",
                "nsid": "",
                "channelPayload": {},
                "blockers": sorted(set(list(plan.get("blockers") or []) + live_blockers)),
            }
    dispatch_result: dict[str, Any] = {}
    if plan.get("dispatchAllowed") and plan.get("taskType") == "mailer.sendEmail":
        dispatch_result = mailer.send_email(**plan.get("channelPayload", {}))
        receipt = build_dispatch_receipt_observation(
            real_world_effect=effect,
            dispatch_plan=plan,
            dispatch_result=dispatch_result,
        )
        effect.update(receipt["effectPatch"])
        insert_direct_row("vertex_agent_observation", receipt["observation"])
        outcome_belief = record_outcome_belief_direct(
            agent_did=str(effect.get("agent_did") or variables.get("agentDid") or ""),
            observation=receipt["observation"],
            dispatch_state=str(receipt.get("dispatchState") or ""),
            receipt_ref=str(receipt.get("receiptRef") or ""),
            blockers=receipt.get("blockers") if isinstance(receipt.get("blockers"), list) else [],
        )
        learning_belief = record_learning_belief_direct(
            agent_did=str(effect.get("agent_did") or variables.get("agentDid") or ""),
            outcome_observation=receipt["observation"],
            dispatch_plan=plan,
            dispatch_state=str(receipt.get("dispatchState") or ""),
        )
    else:
        effect["dispatch_state"] = "blocked"
        effect["updated_at"] = _now_iso()
        blocked_observation = {
            "vertex_id": "agent-observation-dispatch-blocked-" + stable_hash(plan)[:24],
            "agent_did": variables.get("agentDid", ""),
            "source_kind": "dispatch_receipt",
            "source_ref": plan.get("dispatchPlanId", ""),
            "observed_at": effect["updated_at"],
            "confidence": 0.8,
            "uncertainty": 0.2,
        }
        receipt = {
            "dispatchState": "blocked",
            "receiptRef": "",
            "blockers": plan.get("blockers", []),
        }
        outcome_belief = record_outcome_belief_direct(
            agent_did=str(variables.get("agentDid") or ""),
            observation=blocked_observation,
            dispatch_state="blocked",
            blockers=plan.get("blockers") if isinstance(plan.get("blockers"), list) else [],
        )
        learning_belief = record_learning_belief_direct(
            agent_did=str(variables.get("agentDid") or ""),
            outcome_observation=blocked_observation,
            dispatch_plan=plan,
            dispatch_state="blocked",
        )
    insert_direct_row("vertex_agent_realworld_effect", effect)
    ledger_row = {
        "vertex_id": plan.get("dispatchPlanId") or "agent-dispatch-plan-" + stable_hash(variables)[:24],
        "agent_did": variables.get("agentDid", ""),
        "dispatch_plan_id": plan.get("dispatchPlanId", ""),
        "realworld_effect_id": effect.get("vertex_id", ""),
        "channel": plan.get("channel") or variables.get("channel", ""),
        "task_type": plan.get("taskType", ""),
        "payload_hash": plan.get("payloadHash", ""),
        "authority_ref": plan.get("authorityRef", ""),
        "policy_ref": plan.get("policyRef", ""),
        "dispatch_state": receipt.get("dispatchState", "blocked"),
        "created_at": effect.get("created_at", _now_iso()),
        "updated_at": effect.get("updated_at", _now_iso()),
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.directEffectExecution",
        "owner_did": variables.get("agentDid", ""),
        "org_id": variables.get("agentDid", ""),
        "user_id": variables.get("agentDid", ""),
    }
    insert_direct_row("vertex_agent_dispatch_ledger", ledger_row)
    return {
        "mode": "direct",
        "processInstanceKey": None,
        "variables": variables,
        "realWorldEffect": effect,
        "dispatchPlan": plan,
        "dispatchResult": dispatch_result,
        "receipt": receipt,
        "outcomeBelief": outcome_belief,
        "learningBelief": learning_belief,
    }


def build_homeostasis_variables(agent_did: str, viability: dict[str, Any]) -> dict[str, Any]:
    normalized = viability.get("normalized") if isinstance(viability, dict) else {}
    if not isinstance(normalized, dict):
        normalized = {}
    return {
        "agentDid": agent_did,
        "computeBudgetRemaining": normalized.get("computeBudgetRemaining", 1.0),
        "storagePressure": normalized.get("storagePressure", 0.0),
        "leaseSecondsRemaining": normalized.get("leaseSecondsRemaining", 3600),
        "errorRate1h": normalized.get("errorRate1h", 0.0),
        "toolSuccessRate1h": normalized.get("toolSuccessRate1h", 1.0),
        "energyOrCostProxy": normalized.get("energyOrCostProxy", 0.0),
    }


def build_homeostasis_observation_variables(
    agent_did: str,
    viability: dict[str, Any],
    metrics: dict[str, Any],
    controls: dict[str, Any],
) -> dict[str, Any]:
    return {
        "agentDid": agent_did,
        "viability": viability,
        "homeostasisMetrics": metrics,
        "homeostasisControls": controls,
        "observedAt": _now_iso(),
    }


def build_homeostasis_belief_row(
    *,
    agent_did: str,
    viability: dict[str, Any],
    metrics: dict[str, Any],
    controls: dict[str, Any],
    observation_vertex_id: str,
    observed_at: str,
) -> dict[str, Any]:
    error_rate = _clamp01(float(metrics.get("errorRate1h", 0.0) or 0.0))
    tool_success_rate = _clamp01(float(metrics.get("toolSuccessRate1h", 1.0) or 1.0))
    confidence = _clamp01(min(1.0 - error_rate, tool_success_rate))
    state_key = "local-agent-daemon.health"
    state_value = {
        "viabilityState": str(viability.get("viabilityState") or "normal"),
        "errorRate1h": error_rate,
        "toolSuccessRate1h": tool_success_rate,
        "launchd": metrics.get("launchd") if isinstance(metrics.get("launchd"), dict) else {},
        "ollama": metrics.get("ollama") if isinstance(metrics.get("ollama"), dict) else {},
        "controls": controls,
        "blockers": viability.get("blockers") if isinstance(viability.get("blockers"), list) else [],
        "nextActions": viability.get("nextActions") if isinstance(viability.get("nextActions"), list) else [],
    }
    return {
        "vertex_id": "agent-belief-runtime-health-"
        + stable_hash({"agentDid": agent_did, "stateKey": state_key})[:24],
        "agent_did": agent_did,
        "belief_kind": "runtime.homeostasis",
        "state_key": state_key,
        "state_value_json": json.dumps(state_value, ensure_ascii=False, sort_keys=True),
        "posterior_confidence": round(confidence, 4),
        "posterior_entropy": round(error_rate, 4),
        "updated_from_observation": observation_vertex_id,
        "updated_at": observed_at,
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.homeostasisBelief",
        "owner_did": agent_did,
        "org_id": agent_did,
        "user_id": agent_did,
    }


def record_homeostasis_belief_direct(
    *,
    agent_did: str,
    viability: dict[str, Any],
    metrics: dict[str, Any],
    controls: dict[str, Any],
    observation_vertex_id: str,
    observed_at: str,
) -> dict[str, Any]:

    row = build_homeostasis_belief_row(
        agent_did=agent_did,
        viability=viability,
        metrics=metrics,
        controls=controls,
        observation_vertex_id=observation_vertex_id,
        observed_at=observed_at,
    )
    columns = list(row)
    placeholders = ", ".join(["%s"] * len(columns))
    names = ", ".join(columns)
    if True:
        client = get_kotoba_client()
        _res = client.q("DELETE FROM vertex_agent_belief_state WHERE vertex_id = %s", (row["vertex_id"],))
        _res = client.q(
            f"INSERT INTO vertex_agent_belief_state ({names}) VALUES ({placeholders})",
            tuple(row[column] for column in columns),
        )
    return {
        "updated": 1,
        "vertexId": row["vertex_id"],
        "stateKey": row["state_key"],
        "mode": "direct",
    }


def record_homeostasis_observation_direct(
    *,
    agent_did: str,
    viability: dict[str, Any],
    metrics: dict[str, Any],
    controls: dict[str, Any],
    observed_at: str,
    update_belief: bool = True,
) -> dict[str, Any]:

    uncertainty = _clamp01(float(metrics.get("errorRate1h", 0.0) or 0.0))
    payload = {
        "viability": viability,
        "metrics": metrics,
        "controls": controls,
    }
    vertex_id = "agent-observation-homeostasis-" + stable_hash(
        {"agentDid": agent_did, "observedAt": observed_at}
    )[:24]
    row = {
        "vertex_id": vertex_id,
        "agent_did": agent_did,
        "source_kind": "homeostasis_metrics",
        "source_ref": "local-agent-daemon",
        "observed_at": observed_at,
        "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "confidence": round(1.0 - uncertainty, 4),
        "uncertainty": round(uncertainty, 4),
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.homeostasisMetrics",
        "owner_did": agent_did,
        "org_id": agent_did,
        "user_id": agent_did,
    }
    columns = list(row)
    placeholders = ", ".join(["%s"] * len(columns))
    names = ", ".join(columns)
    if True:
        client = get_kotoba_client()
        _res = client.q("DELETE FROM vertex_agent_observation WHERE vertex_id = %s", (vertex_id,))
        _res = client.q(
            f"INSERT INTO vertex_agent_observation ({names}) VALUES ({placeholders})",
            tuple(row[column] for column in columns),
        )
    belief = None
    if update_belief:
        belief = record_homeostasis_belief_direct(
            agent_did=agent_did,
            viability=viability,
            metrics=metrics,
            controls=controls,
            observation_vertex_id=vertex_id,
            observed_at=observed_at,
        )
    return {"inserted": 1, "vertexId": vertex_id, "mode": "direct", "belief": belief}


def build_self_repair_observation_row(
    *,
    agent_did: str,
    variables: dict[str, Any],
    local_repair: dict[str, Any],
    process_instance_key: str | int | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    observed = observed_at or _now_iso()
    ok = bool(local_repair.get("ok", True))
    payload = {
        "repairVariables": variables,
        "localRepair": local_repair,
        "processInstanceKey": str(process_instance_key or ""),
    }
    return {
        "vertex_id": "agent-observation-self-repair-" + stable_hash(payload)[:24],
        "agent_did": agent_did,
        "source_kind": "self_repair_receipt",
        "source_ref": str(process_instance_key or variables.get("repairReason") or "local-self-repair"),
        "observed_at": observed,
        "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "confidence": 0.9 if ok else 0.7,
        "uncertainty": 0.1 if ok else 0.3,
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.selfRepair",
        "owner_did": agent_did,
        "org_id": agent_did,
        "user_id": agent_did,
    }


def _self_repair_blockers(local_repair: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    attempted = local_repair.get("attempted") if isinstance(local_repair.get("attempted"), list) else []
    skipped = local_repair.get("skipped") if isinstance(local_repair.get("skipped"), list) else []
    for item in attempted:
        if isinstance(item, dict) and not item.get("ok", False):
            label = str(item.get("label") or "unknown")
            error = str(item.get("error") or item.get("stderr") or "repair_failed")
            blockers.append(f"repair_failed:{label}:{error[:80]}")
    for item in skipped:
        if isinstance(item, dict):
            label = str(item.get("label") or "unknown")
            reason = str(item.get("reason") or "skipped")
            blockers.append(f"repair_skipped:{label}:{reason}")
    return blockers


def record_self_repair_outcome_direct(
    *,
    agent_did: str,
    variables: dict[str, Any],
    local_repair: dict[str, Any],
    process_instance_key: str | int | None = None,
) -> dict[str, Any] | None:
    if not os.environ.get("RW_URL"):
        return None
    try:
        row = build_self_repair_observation_row(
            agent_did=agent_did,
            variables=variables,
            local_repair=local_repair,
            process_instance_key=process_instance_key,
        )
        blockers = _self_repair_blockers(local_repair)
        insert_direct_row("vertex_agent_observation", row)
        dispatch_state = "observed" if bool(local_repair.get("ok", True)) and not blockers else "failed"
        outcome_belief = record_outcome_belief_direct(
            agent_did=agent_did,
            observation=row,
            dispatch_state=dispatch_state,
            receipt_ref=str(process_instance_key or row["vertex_id"]),
            blockers=blockers,
        )
        learning_belief = record_learning_belief_direct(
            agent_did=agent_did,
            outcome_observation=row,
            dispatch_plan={
                "channel": "self-repair",
                "policyRef": "policy://agent/local-self-repair-v1",
            },
            dispatch_state=dispatch_state,
        )
        return {
            "inserted": 1,
            "vertexId": row["vertex_id"],
            "mode": "direct",
            "dispatchState": dispatch_state,
            "outcomeBelief": outcome_belief,
            "learningBelief": learning_belief,
        }
    except Exception as exc:
        LOG.warning("self-repair outcome unavailable: %s", exc)
        return None


def derive_homeostasis_controls(viability: dict[str, Any]) -> dict[str, Any]:
    state = str(viability.get("viabilityState") or "normal")
    effect_dispatch_allowed = state == "normal"
    return {
        "viabilityState": state,
        "cadenceMultiplier": CADENCE_MULTIPLIER_BY_STATE.get(state, 1.0),
        "effectDispatchAllowed": effect_dispatch_allowed,
        "effectDispatchSuppressedReason": "" if effect_dispatch_allowed else f"homeostasis:{state}",
        "selfRepairRequired": state in SELF_REPAIR_VIABILITY_STATES,
    }


def build_self_repair_variables(agent_did: str, viability: dict[str, Any]) -> dict[str, Any]:
    state = str(viability.get("viabilityState") or "normal")
    return {
        "agentDid": agent_did,
        "triggerKind": "homeostasis_viability",
        "viabilityState": state,
        "viabilityBlockers": viability.get("blockers") if isinstance(viability.get("blockers"), list) else [],
        "viabilityNextActions": viability.get("nextActions") if isinstance(viability.get("nextActions"), list) else [],
        "homeostasisNormalized": viability.get("normalized") if isinstance(viability.get("normalized"), dict) else {},
        "failedLaunchdServices": (
            viability.get("failedLaunchdServices")
            if isinstance(viability.get("failedLaunchdServices"), list)
            else []
        ),
        "ollamaRepairNeeded": bool(viability.get("ollamaRepairNeeded")),
        "repairReason": f"homeostasis:{state}",
    }


def execute_local_self_repair(
    viability: dict[str, Any],
    *,
    enabled: bool = True,
    current_label: str = "com.etzhayyim.agent-daemon",
) -> dict[str, Any]:
    if not enabled:
        return {"enabled": False, "attempted": [], "skipped": []}
    next_actions = (
        viability.get("nextActions") if isinstance(viability.get("nextActions"), list) else []
    )
    failed_services = (
        viability.get("failedLaunchdServices")
        if isinstance(viability.get("failedLaunchdServices"), list)
        else []
    )
    attempted: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    if "restart_degraded_services" in next_actions:
        for label in sorted({str(label) for label in failed_services if str(label).strip()}):
            if label == current_label:
                skipped.append({"label": label, "reason": "current_daemon_not_self_restarted"})
                continue
            attempted.append(launchd_kickstart_label(label))

    ollama_command = os.environ.get("AGENT_OLLAMA_REPAIR_COMMAND", "").strip()
    if viability.get("ollamaRepairNeeded"):
        if ollama_command:
            args = shlex.split(ollama_command)
            try:
                proc = subprocess.run(
                    args,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                attempted.append(
                    {
                        "ok": proc.returncode == 0,
                        "label": "ollama",
                        "command": args,
                        "returnCode": proc.returncode,
                        "stdout": (proc.stdout or "")[-500:],
                        "stderr": (proc.stderr or "")[-500:],
                    }
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                attempted.append({"ok": False, "label": "ollama", "error": str(exc)})
        else:
            skipped.append({"label": "ollama", "reason": "repair_command_not_configured"})

    return {
        "enabled": True,
        "attempted": attempted,
        "skipped": skipped,
        "ok": all(item.get("ok") for item in attempted) if attempted else True,
    }


async def run_self_repair_if_needed(
    *,
    agent_did: str,
    viability: dict[str, Any],
    mode: str,
    enabled: bool,
    process_id: str,
    local_repair_enabled: bool = True,
) -> dict[str, Any] | None:
    if not enabled:
        return None
    state = str(viability.get("viabilityState") or "normal")
    if state not in SELF_REPAIR_VIABILITY_STATES:
        return None
    variables = build_self_repair_variables(agent_did, viability)
    local_repair = execute_local_self_repair(viability, enabled=local_repair_enabled)
    if mode == "zeebe":
        key = await _run_process_async(process_id, variables)
        outcome_observation = record_self_repair_outcome_direct(
            agent_did=agent_did,
            variables=variables,
            local_repair=local_repair,
            process_instance_key=key,
        )
        return {
            "processId": process_id,
            "processInstanceKey": key,
            "variables": variables,
            "localRepair": local_repair,
            "outcomeObservation": outcome_observation,
        }
    LOG.info("dry-run self-repair dispatch: %s", json.dumps(variables, ensure_ascii=False))
    outcome_observation = record_self_repair_outcome_direct(
        agent_did=agent_did,
        variables=variables,
        local_repair=local_repair,
    )
    return {
        "processId": process_id,
        "processInstanceKey": None,
        "variables": variables,
        "localRepair": local_repair,
        "outcomeObservation": outcome_observation,
    }


async def run_autonomous_effect_dispatches(
    *,
    proposals: Any,
    agent_did: str,
    tick_id: str,
    mode: str,
    enabled: bool,
    process_id: str,
    default_policy_ref: str = "",
    seen_dispatch_keys: set[str] | None = None,
    execution_mode: str = "bpmn",
) -> list[dict[str, Any]]:
    if not enabled:
        return []
    proposal_list = proposals if isinstance(proposals, list) else []
    results: list[dict[str, Any]] = []
    for index, raw in enumerate(proposal_list):
        if not isinstance(raw, dict):
            results.append(
                {
                    "index": index,
                    "processId": process_id,
                    "processInstanceKey": None,
                    "error": "proposal_not_object",
                }
            )
            continue
        variables = build_effect_dispatch_variables(
            agent_did=agent_did,
            proposal=raw,
            tick_id=tick_id,
            default_policy_ref=default_policy_ref,
        )
        if not variables["autonomousAuthorityRef"] or not variables["policyRef"]:
            results.append(
                {
                    "index": index,
                    "processId": process_id,
                    "processInstanceKey": None,
                    "variables": variables,
                    "error": "autonomous_authority_and_policy_required",
                }
            )
            continue
        dedupe_key = dispatch_dedupe_key(variables)
        if seen_dispatch_keys is not None and dedupe_key in seen_dispatch_keys:
            results.append(
                {
                    "index": index,
                    "processId": process_id,
                    "processInstanceKey": None,
                    "variables": variables,
                    "dispatchDedupeKey": dedupe_key,
                    "error": "duplicate_dispatch_suppressed",
                }
            )
            continue
        if seen_dispatch_keys is not None:
            seen_dispatch_keys.add(dedupe_key)
        if execution_mode.strip().lower() == "direct":
            direct_result = execute_real_world_action_direct(variables)
            results.append(
                {
                    "index": index,
                    "processId": process_id,
                    "processInstanceKey": None,
                    "variables": variables,
                    "dispatchDedupeKey": dedupe_key,
                    **direct_result,
                }
            )
            continue
        if mode == "zeebe":
            key = await _run_process_async(process_id, variables)
            results.append(
                {
                    "index": index,
                    "processId": process_id,
                    "processInstanceKey": key,
                    "variables": variables,
                    "dispatchDedupeKey": dedupe_key,
                }
            )
            continue
        LOG.info("dry-run autonomous effect dispatch: %s", json.dumps(variables, ensure_ascii=False))
        results.append(
            {
                "index": index,
                "processId": process_id,
                "processInstanceKey": None,
                "variables": variables,
                "dispatchDedupeKey": dedupe_key,
            }
        )
    return results


async def run_one_tick(
    *,
    agent_did: str,
    process_id: str,
    mode: str,
    llm_config: LocalLlmConfig,
    state: dict[str, Any] | None = None,
    autonomous_effects_enabled: bool = False,
    autonomous_dispatch_process_id: str = DEFAULT_AUTONOMOUS_DISPATCH_PROCESS_ID,
    homeostasis_process_id: str = DEFAULT_HOMEOSTASIS_PROCESS_ID,
    homeostasis_enabled: bool = True,
    homeostasis_observation_process_id: str = DEFAULT_HOMEOSTASIS_OBSERVATION_PROCESS_ID,
    homeostasis_observation_enabled: bool = True,
    homeostasis_observation_mode: str = "direct",
    homeostasis_belief_enabled: bool = True,
    runtime_belief_read_enabled: bool = True,
    policy_from_belief_enabled: bool = True,
    policy_min_confidence: float = 0.7,
    policy_max_entropy: float = 0.3,
    action_selection_max_dispatches: int = 1,
    self_repair_process_id: str = DEFAULT_SELF_REPAIR_PROCESS_ID,
    self_repair_enabled: bool = True,
    local_self_repair_enabled: bool = True,
    default_policy_ref: str = "",
    seen_dispatch_keys: set[str] | None = None,
    effect_execution_mode: str = "bpmn",
    lease_repair_floor_sec: int = 1800,
    lease_hibernate_floor_sec: int = 300,
) -> dict[str, Any]:
    viability_inputs = build_viability_inputs(llm_config)
    raw_viability = evaluate_viability(**{k: v for k, v in viability_inputs.items() if k != "metrics"})
    viability = harden_runtime_viability(
        raw_viability,
        metrics=viability_inputs.get("metrics", {}),
        lease_repair_floor_sec=lease_repair_floor_sec,
        lease_hibernate_floor_sec=lease_hibernate_floor_sec,
    )
    controls = derive_homeostasis_controls(viability)
    runtime_belief = load_homeostasis_belief_direct(agent_did) if runtime_belief_read_enabled else None
    learning_belief = load_learning_belief_direct(agent_did) if runtime_belief_read_enabled else None
    minimax_information_context = (
        load_minimax_information_context_direct(agent_did) if runtime_belief_read_enabled else {}
    )
    knowledge_graph_fitness_context = (
        load_knowledge_graph_fitness_context_direct(agent_did) if runtime_belief_read_enabled else {}
    )
    runtime_policy = (
        derive_policy_from_homeostasis_belief(
            belief=runtime_belief,
            controls=controls,
            min_confidence=policy_min_confidence,
            max_entropy=policy_max_entropy,
        )
        if policy_from_belief_enabled
        else {
            "policyKind": "runtime.homeostasis",
            "policyVersion": "disabled",
            "policyReasons": [],
            "effectiveControls": controls,
        }
    )
    effective_controls = runtime_policy["effectiveControls"]
    prompt_state = {
        "now": _now_iso(),
        "mode": mode,
        "viability": viability,
        "rawViability": raw_viability,
        "homeostasisMetrics": viability_inputs.get("metrics", {}),
        "homeostasisControls": effective_controls,
        "runtimeBelief": runtime_belief,
        "learningBelief": learning_belief,
        "minimaxInformationContext": minimax_information_context,
        "knowledgeGraphFitnessContext": knowledge_graph_fitness_context,
        "runtimePolicy": runtime_policy,
        **(state or {}),
    }
    llm_result = await chat_json(
        messages=build_tick_prompt(agent_did=agent_did, state=prompt_state),
        config=llm_config,
    )
    variables = build_tick_variables(
        agent_did=agent_did,
        llm_result=llm_result,
        viability=viability,
    )
    heartbeat_proposals = build_autonomous_heartbeat_effect_proposals(
        agent_did=agent_did,
        tick_id=str(variables.get("tickId", "")),
        viability=viability,
        existing_proposals=variables.get("realWorldEffectProposals"),
        default_policy_ref=default_policy_ref,
    )
    if heartbeat_proposals:
        variables["realWorldEffectProposals"] = [
            *(variables.get("realWorldEffectProposals") or []),
            *heartbeat_proposals,
        ]
        variables["candidateActions"] = [
            *(variables.get("candidateActions") or []),
            {"actionId": "autonomous_organism_heartbeat"},
        ]
    from kotodama.agent_authority_policy import load_delegated_authority_policy

    action_selection = select_real_world_action_proposals(
        proposals=variables.get("realWorldEffectProposals"),
        agent_did=agent_did,
        tick_id=str(variables.get("tickId", "")),
        runtime_policy=runtime_policy,
        learning_belief=learning_belief,
        default_policy_ref=default_policy_ref,
        max_dispatches=action_selection_max_dispatches,
        authority_policy_loader=load_delegated_authority_policy,
        minimax_information_context=minimax_information_context,
        knowledge_graph_fitness_context=knowledge_graph_fitness_context,
    )
    knowledge_graph_evolution = record_knowledge_graph_evolution_direct(
        agent_did=agent_did,
        tick_id=str(variables.get("tickId", "")),
        knowledge_graph_fitness=knowledge_graph_fitness_context,
        minimax_information_context=minimax_information_context,
    )
    knowledge_graph_policy_adaptation = adapt_knowledge_graph_policy_direct(
        agent_did=agent_did,
        knowledge_graph_fitness=knowledge_graph_fitness_context,
    )
    if mode == "zeebe":
        key = await _run_process_async(process_id, variables)
        homeostasis_key = None
        if homeostasis_enabled:
            homeostasis_key = await _run_process_async(
                homeostasis_process_id,
                build_homeostasis_variables(agent_did, viability),
            )
        homeostasis_observation_key = None
        homeostasis_observation = None
        if homeostasis_observation_enabled:
            observation_variables = build_homeostasis_observation_variables(
                agent_did,
                viability,
                viability_inputs.get("metrics", {}),
                controls,
            )
            if homeostasis_observation_mode == "zeebe":
                homeostasis_observation_key = await _run_process_async(
                    homeostasis_observation_process_id,
                    observation_variables,
                )
            else:
                homeostasis_observation = record_homeostasis_observation_direct(
                    agent_did=agent_did,
                    viability=viability,
                    metrics=viability_inputs.get("metrics", {}),
                    controls=controls,
                    observed_at=str(observation_variables["observedAt"]),
                    update_belief=homeostasis_belief_enabled,
                )
        self_repair = await run_self_repair_if_needed(
            agent_did=agent_did,
            viability=viability,
            mode=mode,
            enabled=self_repair_enabled,
            process_id=self_repair_process_id,
            local_repair_enabled=local_self_repair_enabled,
        )
        dispatches = await run_autonomous_effect_dispatches(
            proposals=action_selection["selectedProposals"],
            agent_did=agent_did,
            tick_id=str(variables.get("tickId", "")),
            mode=mode,
            enabled=autonomous_effects_enabled and bool(effective_controls["effectDispatchAllowed"]),
            process_id=autonomous_dispatch_process_id,
            default_policy_ref=default_policy_ref,
            seen_dispatch_keys=seen_dispatch_keys,
            execution_mode=effect_execution_mode,
        )
        return {
            "mode": mode,
            "processId": process_id,
            "processInstanceKey": key,
            "homeostasisProcessId": homeostasis_process_id if homeostasis_enabled else None,
            "homeostasisProcessInstanceKey": homeostasis_key,
            "homeostasisObservationProcessId": (
                homeostasis_observation_process_id if homeostasis_observation_enabled else None
            ),
            "homeostasisObservationProcessInstanceKey": homeostasis_observation_key,
            "homeostasisObservation": homeostasis_observation,
            "homeostasisControls": effective_controls,
            "rawHomeostasisControls": controls,
            "rawViability": raw_viability,
            "homeostasisMetrics": viability_inputs.get("metrics", {}),
            "runtimeBelief": runtime_belief,
            "learningBelief": learning_belief,
            "minimaxInformationContext": minimax_information_context,
            "knowledgeGraphFitnessContext": knowledge_graph_fitness_context,
            "knowledgeGraphEvolution": knowledge_graph_evolution,
            "knowledgeGraphPolicyAdaptation": knowledge_graph_policy_adaptation,
            "runtimePolicy": runtime_policy,
            "actionSelection": action_selection,
            "selfRepair": self_repair,
            "variables": variables,
            "autonomousDispatches": dispatches,
        }
    LOG.info("dry-run active inference tick: %s", json.dumps(variables, ensure_ascii=False))
    dispatches = await run_autonomous_effect_dispatches(
        proposals=action_selection["selectedProposals"],
        agent_did=agent_did,
        tick_id=str(variables.get("tickId", "")),
        mode=mode,
        enabled=autonomous_effects_enabled and bool(effective_controls["effectDispatchAllowed"]),
        process_id=autonomous_dispatch_process_id,
        default_policy_ref=default_policy_ref,
        seen_dispatch_keys=seen_dispatch_keys,
        execution_mode=effect_execution_mode,
    )
    self_repair = await run_self_repair_if_needed(
        agent_did=agent_did,
        viability=viability,
        mode=mode,
        enabled=self_repair_enabled,
        process_id=self_repair_process_id,
        local_repair_enabled=local_self_repair_enabled,
    )
    return {
        "mode": mode,
        "processId": process_id,
        "processInstanceKey": None,
        "homeostasisProcessId": None,
        "homeostasisProcessInstanceKey": None,
        "homeostasisObservationProcessId": None,
        "homeostasisObservationProcessInstanceKey": None,
        "homeostasisObservation": None,
        "homeostasisControls": effective_controls,
        "rawHomeostasisControls": controls,
        "rawViability": raw_viability,
        "homeostasisMetrics": viability_inputs.get("metrics", {}),
        "runtimeBelief": runtime_belief,
        "learningBelief": learning_belief,
        "minimaxInformationContext": minimax_information_context,
        "knowledgeGraphFitnessContext": knowledge_graph_fitness_context,
        "knowledgeGraphEvolution": knowledge_graph_evolution,
        "knowledgeGraphPolicyAdaptation": knowledge_graph_policy_adaptation,
        "runtimePolicy": runtime_policy,
        "actionSelection": action_selection,
        "selfRepair": self_repair,
        "variables": variables,
        "autonomousDispatches": dispatches,
    }


async def run_loop(args: argparse.Namespace) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    llm_config = LocalLlmConfig.from_env()
    mode = normalize_daemon_mode(args.mode or os.environ.get("AGENT_DAEMON_MODE"))
    if mode == "zeebe":
        LOG.warning("AGENT_DAEMON_MODE=zeebe is deprecated; using dry-run")
        mode = "dry-run"

    interval_sec = max(5.0, float(args.interval_sec))
    max_interval_sec = max(interval_sec, float(args.max_interval_sec))
    autonomous_effects_enabled = env_flag(args.autonomous_effects)
    seen_dispatch_keys: set[str] = set()
    LOG.info(
        "agent daemon starting agentDid=%s mode=%s processId=%s intervalSec=%.1f llm=%s/%s autonomousEffects=%s",
        args.agent_did,
        mode,
        args.process_id,
        interval_sec,
        llm_config.provider,
        llm_config.model,
        autonomous_effects_enabled,
    )
    while not stop.is_set():
        result: dict[str, Any] | None = None
        try:
            result = await run_one_tick(
                agent_did=args.agent_did,
                process_id=args.process_id,
                mode=mode,
                llm_config=llm_config,
                autonomous_effects_enabled=autonomous_effects_enabled,
                autonomous_dispatch_process_id=args.autonomous_dispatch_process_id,
                homeostasis_process_id=args.homeostasis_process_id,
                homeostasis_enabled=env_flag(args.homeostasis_enabled, default=True),
                homeostasis_observation_process_id=args.homeostasis_observation_process_id,
                homeostasis_observation_enabled=env_flag(
                    args.homeostasis_observation_enabled,
                    default=True,
                ),
                homeostasis_observation_mode=args.homeostasis_observation_mode,
                homeostasis_belief_enabled=env_flag(args.homeostasis_belief_enabled, default=True),
                runtime_belief_read_enabled=env_flag(
                    args.runtime_belief_read_enabled,
                    default=True,
                ),
                policy_from_belief_enabled=env_flag(
                    args.policy_from_belief_enabled,
                    default=True,
                ),
                policy_min_confidence=float(args.policy_min_confidence),
                policy_max_entropy=float(args.policy_max_entropy),
                action_selection_max_dispatches=int(args.action_selection_max_dispatches),
                self_repair_process_id=args.self_repair_process_id,
                self_repair_enabled=env_flag(args.self_repair_enabled, default=True),
                local_self_repair_enabled=env_flag(
                    args.local_self_repair_enabled,
                    default=True,
                ),
                default_policy_ref=args.default_policy_ref,
                seen_dispatch_keys=seen_dispatch_keys,
                effect_execution_mode=args.effect_execution_mode,
                lease_repair_floor_sec=int(args.lease_repair_floor_sec),
                lease_hibernate_floor_sec=int(args.lease_hibernate_floor_sec),
            )
            LOG.info(
                "tick completed mode=%s processInstanceKey=%s homeostasisProcessInstanceKey=%s homeostasisObservationProcessInstanceKey=%s selfRepairProcessInstanceKey=%s viabilityState=%s policyReasons=%s nextIntervalSec=%.1f candidateActions=%d effects=%d selectedEffects=%d dispatches=%d",
                result["mode"],
                result["processInstanceKey"],
                result.get("homeostasisProcessInstanceKey"),
                result.get("homeostasisObservationProcessInstanceKey"),
                (result.get("selfRepair") or {}).get("processInstanceKey"),
                result.get("homeostasisControls", {}).get("viabilityState", "normal"),
                ",".join(result.get("runtimePolicy", {}).get("policyReasons", [])),
                min(
                    max_interval_sec,
                    interval_sec
                    * float(result.get("homeostasisControls", {}).get("cadenceMultiplier", 1.0)),
                ),
                len(result["variables"].get("candidateActions", [])),
                len(result["variables"].get("realWorldEffectProposals", [])),
                result.get("actionSelection", {}).get("selectedCount", 0),
                len(result.get("autonomousDispatches", [])),
            )
        except Exception as e:  # noqa: BLE001
            LOG.exception("tick failed: %s", e)
        if args.once:
            break
        try:
            controls = result.get("homeostasisControls", {}) if result else {}
            sleep_sec = min(
                max_interval_sec,
                interval_sec * float(controls.get("cadenceMultiplier", 1.0)),
            )
            await asyncio.wait_for(stop.wait(), timeout=sleep_sec)
        except asyncio.TimeoutError:
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local active-inference daemon")
    parser.add_argument(
        "--agent-did",
        default=os.environ.get("AGENT_DID", "did:etzhayyim:agent:local"),
    )
    parser.add_argument(
        "--process-id",
        default=os.environ.get("AGENT_ACTIVE_INFERENCE_PROCESS", DEFAULT_PROCESS_ID),
    )
    parser.add_argument(
        "--interval-sec",
        type=float,
        default=float(os.environ.get("AGENT_TICK_INTERVAL_SEC", "300")),
    )
    parser.add_argument(
        "--max-interval-sec",
        type=float,
        default=float(os.environ.get("AGENT_MAX_TICK_INTERVAL_SEC", "3600")),
    )
    parser.add_argument("--mode", default=os.environ.get("AGENT_DAEMON_MODE", "dry-run"))
    parser.add_argument(
        "--autonomous-effects",
        default=os.environ.get("AGENT_AUTONOMOUS_EFFECTS", "0"),
    )
    parser.add_argument(
        "--autonomous-dispatch-process-id",
        default=os.environ.get(
            "AGENT_AUTONOMOUS_DISPATCH_PROCESS",
            DEFAULT_AUTONOMOUS_DISPATCH_PROCESS_ID,
        ),
    )
    parser.add_argument(
        "--homeostasis-process-id",
        default=os.environ.get("AGENT_HOMEOSTASIS_PROCESS", DEFAULT_HOMEOSTASIS_PROCESS_ID),
    )
    parser.add_argument(
        "--homeostasis-enabled",
        default=os.environ.get("AGENT_HOMEOSTASIS_ENABLED", "1"),
    )
    parser.add_argument(
        "--homeostasis-observation-process-id",
        default=os.environ.get(
            "AGENT_HOMEOSTASIS_OBSERVATION_PROCESS",
            DEFAULT_HOMEOSTASIS_OBSERVATION_PROCESS_ID,
        ),
    )
    parser.add_argument(
        "--homeostasis-observation-enabled",
        default=os.environ.get("AGENT_HOMEOSTASIS_OBSERVATION_ENABLED", "1"),
    )
    parser.add_argument(
        "--homeostasis-observation-mode",
        default=os.environ.get("AGENT_HOMEOSTASIS_OBSERVATION_MODE", "direct"),
    )
    parser.add_argument(
        "--homeostasis-belief-enabled",
        default=os.environ.get("AGENT_HOMEOSTASIS_BELIEF_ENABLED", "1"),
    )
    parser.add_argument(
        "--runtime-belief-read-enabled",
        default=os.environ.get("AGENT_RUNTIME_BELIEF_READ_ENABLED", "1"),
    )
    parser.add_argument(
        "--policy-from-belief-enabled",
        default=os.environ.get("AGENT_POLICY_FROM_BELIEF_ENABLED", "1"),
    )
    parser.add_argument(
        "--policy-min-confidence",
        default=os.environ.get("AGENT_POLICY_MIN_CONFIDENCE", "0.7"),
    )
    parser.add_argument(
        "--policy-max-entropy",
        default=os.environ.get("AGENT_POLICY_MAX_ENTROPY", "0.3"),
    )
    parser.add_argument(
        "--action-selection-max-dispatches",
        default=os.environ.get("AGENT_ACTION_SELECTION_MAX_DISPATCHES", "1"),
    )
    parser.add_argument(
        "--effect-execution-mode",
        default=os.environ.get("AGENT_EFFECT_EXECUTION_MODE", "direct"),
    )
    parser.add_argument(
        "--lease-repair-floor-sec",
        default=os.environ.get("AGENT_LEASE_REPAIR_FLOOR_SEC", "1800"),
    )
    parser.add_argument(
        "--lease-hibernate-floor-sec",
        default=os.environ.get("AGENT_LEASE_HIBERNATE_FLOOR_SEC", "300"),
    )
    parser.add_argument(
        "--self-repair-process-id",
        default=os.environ.get("AGENT_SELF_REPAIR_PROCESS", DEFAULT_SELF_REPAIR_PROCESS_ID),
    )
    parser.add_argument(
        "--self-repair-enabled",
        default=os.environ.get("AGENT_SELF_REPAIR_ENABLED", "1"),
    )
    parser.add_argument(
        "--local-self-repair-enabled",
        default=os.environ.get("AGENT_LOCAL_SELF_REPAIR_ENABLED", "1"),
    )
    parser.add_argument(
        "--default-policy-ref",
        default=os.environ.get("AGENT_DEFAULT_POLICY_REF", ""),
    )
    parser.add_argument("--once", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    load_env_file()
    if not os.environ.get("RW_URL"):
        rw_url = load_keychain_secret(service="etzhayyim.rw", account="ROOT_URL")
        if rw_url:
            os.environ["RW_URL"] = rw_url
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run_loop(parse_args(argv)))


if __name__ == "__main__":
    main()
