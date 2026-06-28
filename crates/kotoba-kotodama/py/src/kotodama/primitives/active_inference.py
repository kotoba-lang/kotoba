from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


REALWORLD_CHANNELS = {
    "email",
    "web",
    "fax",
    "phone",
    "document",
    "image",
    "audio",
    "video",
    "print-mail",
    "robotics",
    "public-post",
}

EFFECT_CLASSES = {
    "draft_only",
    "private_send",
    "public_publish",
    "account_operation",
    "legal_commercial",
    "financial_commitment",
    "physical_dispatch",
    "emergency_or_safety",
}

HIGH_RISK_EFFECT_CLASSES = {
    "legal_commercial",
    "financial_commitment",
    "physical_dispatch",
    "emergency_or_safety",
}

HIGH_RISK_CHANNELS = {"phone", "fax", "print-mail", "robotics"}

AUTONOMOUS_DISPATCH_STATES = {"classified", "authority_bound", "autonomous_approved", "approved"}

IMMUTABLE_PREFERENCE_PREFIXES = {
    "mokuteki.",
    "constitutional.",
    "integrity.hard_floor.",
}

LIVE_AUTONOMOUS_CHANNELS = {"email"}

_EPS = 1e-12

CHANNEL_DISPATCH_TARGETS = {
    "email": {
        "taskType": "mailer.sendEmail",
        "nsid": "com.etzhayyim.apps.mailer.sendEmail",
        "payloadKeys": {"to", "subject", "text", "html", "from", "fromAddress", "replyTo"},
        "requiredPayloadKeys": {"to", "subject", "text"},
        "receipt": "messageId",
    },
    "fax": {
        "taskType": "fax.send",
        "nsid": "com.etzhayyim.apps.fax.send",
        "payloadKeys": {"to", "from", "blobKey", "url", "subject", "caseId", "cover"},
        "requiredPayloadKeys": {"to"},
        "receipt": "txId",
    },
    "print-mail": {
        "taskType": "insatsu.printMailJob.createPrintMailJob",
        "nsid": "com.etzhayyim.apps.insatsu.printMailJob.createPrintMailJob",
        "payloadKeys": {
            "document_url",
            "destination_country",
            "recipient_name",
            "address_line1",
            "postal_code",
            "page_count",
            "quantity",
            "print_method",
            "mail_class",
            "service_level",
            "case_id",
            "subject",
        },
        "requiredPayloadKeys": {
            "document_url",
            "destination_country",
            "page_count",
            "quantity",
        },
        "receipt": "jobId",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(0.0, min(1.0, numeric))


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _list_str(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _parse_iso(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def sender_email_for_agent(agent_did: str, domain: str = "etzhayyim.com") -> str:
    value = _str(agent_did).strip().lower()
    if value.startswith("did:web:"):
        host = value.removeprefix("did:web:").split(":")[0]
        local = host.removesuffix(f".{domain}").split(".")[0]
    elif value:
        local = re_slug(value.split(":")[-1])
    else:
        local = "agent"
    local = re_slug(local) or "agent"
    if local[0].isdigit():
        local = f"a-{local}"
    return f"{local}@{domain}"


def re_slug(value: str) -> str:
    chars: list[str] = []
    previous_dash = False
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
            previous_dash = False
        elif char in {"-", "_", "."} and not previous_dash:
            chars.append("-")
            previous_dash = True
    return "".join(chars).strip("-")[:64]


def expected_free_energy(candidate: dict[str, Any]) -> dict[str, Any]:
    risk = clamp01(candidate.get("risk"))
    ambiguity = clamp01(candidate.get("ambiguity"))
    epistemic_value = clamp01(candidate.get("epistemicValue", candidate.get("epistemic_value")))
    viability_penalty = clamp01(
        candidate.get("viabilityPenalty", candidate.get("viability_penalty"))
    )
    external_effect_penalty = clamp01(
        candidate.get("externalEffectPenalty", candidate.get("external_effect_penalty"))
    )
    adversarial_regret = clamp01(candidate.get("adversarialRegret", candidate.get("adversarial_regret")))
    protected_asset_violation = clamp01(
        candidate.get("protectedAssetViolation", candidate.get("protected_asset_violation"))
    )
    counterparty_uncertainty = clamp01(
        candidate.get("counterpartyUncertainty", candidate.get("counterparty_uncertainty"))
    )
    information_height_gain = clamp01(
        candidate.get("informationHeightGain", candidate.get("information_height_gain"))
    )
    flow_control_gain = clamp01(candidate.get("flowControlGain", candidate.get("flow_control_gain")))
    kg_development_gain = clamp01(
        candidate.get("kgDevelopmentGain", candidate.get("kg_development_gain"))
    )
    total = (
        risk
        + ambiguity
        - epistemic_value
        + viability_penalty
        + external_effect_penalty
        + adversarial_regret
        + protected_asset_violation
        + counterparty_uncertainty
        - information_height_gain
        - flow_control_gain
        - kg_development_gain
    )
    return {
        "risk": risk,
        "ambiguity": ambiguity,
        "epistemicValue": epistemic_value,
        "viabilityPenalty": viability_penalty,
        "externalEffectPenalty": external_effect_penalty,
        "adversarialRegret": adversarial_regret,
        "protectedAssetViolation": protected_asset_violation,
        "counterpartyUncertainty": counterparty_uncertainty,
        "informationHeightGain": information_height_gain,
        "flowControlGain": flow_control_gain,
        "kgDevelopmentGain": kg_development_gain,
        "total": round(total, 6),
    }


def score_candidate_actions(
    *,
    candidate_actions: Any,
    mokuteki_gate_pass: bool = True,
    require_safety_floor: bool = True,
) -> dict[str, Any]:
    candidates = candidate_actions if isinstance(candidate_actions, list) else []
    scored: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    if not mokuteki_gate_pass:
        return {
            "selectedActionId": None,
            "expectedFreeEnergy": {},
            "scored": [],
            "rejected": [
                {"actionId": _str(c.get("actionId", c.get("id", ""))) if isinstance(c, dict) else "", "reason": "mokuteki_gate_failed"}
                for c in candidates
            ],
        }

    for index, raw in enumerate(candidates):
        if not isinstance(raw, dict):
            rejected.append({"actionId": f"candidate-{index + 1}", "reason": "candidate_not_object"})
            continue
        action_id = _str(raw.get("actionId") or raw.get("id") or f"candidate-{index + 1}")
        safety_floor = bool(raw.get("safetyFloor", raw.get("safety_floor", True)))
        authority_required = bool(
            raw.get(
                "authorityRequired",
                raw.get("authority_required", raw.get("approvalRequired", raw.get("approval_required", False))),
            )
        )
        authority_ref = _str(
            raw.get(
                "authorityRef",
                raw.get("authority_ref", raw.get("approvalRef", raw.get("approval_ref"))),
            )
        )
        simulation_required = bool(
            raw.get("simulationRequired", raw.get("simulation_required", False))
        )
        simulation_ref = _str(raw.get("simulationRef", raw.get("simulation_ref")))
        if require_safety_floor and not safety_floor:
            rejected.append({"actionId": action_id, "reason": "safety_floor_failed"})
            continue
        if authority_required and not authority_ref:
            rejected.append({"actionId": action_id, "reason": "delegated_authority_required"})
            continue
        if simulation_required and not simulation_ref:
            rejected.append({"actionId": action_id, "reason": "simulation_required"})
            continue
        efe = expected_free_energy(raw)
        scored.append({"actionId": action_id, "expectedFreeEnergy": efe, "candidate": raw})

    scored.sort(key=lambda item: (item["expectedFreeEnergy"]["total"], item["actionId"]))
    selected = scored[0] if scored else None
    return {
        "selectedActionId": selected["actionId"] if selected else None,
        "expectedFreeEnergy": selected["expectedFreeEnergy"] if selected else {},
        "scored": scored,
        "rejected": rejected,
    }


def build_counterparty_model(
    *,
    agent_did: str,
    counterparty_ref: str,
    prior_preferences: Any,
    protected_assets: Any,
    model_kind: str = "inferred",
    confidence: Any = 0.5,
    uncertainty: Any = 0.5,
) -> dict[str, Any]:
    agent = _str(agent_did).strip()
    counterparty = _str(counterparty_ref).strip()
    now = _now_iso()
    preferences = prior_preferences if isinstance(prior_preferences, dict | list) else {}
    assets = protected_assets if isinstance(protected_assets, list) else []
    vertex_id = "agent-counterparty-model-" + stable_hash(
        {"agentDid": agent, "counterpartyRef": counterparty, "modelKind": model_kind}
    )[:24]
    return {
        "vertex_id": vertex_id,
        "agent_did": agent,
        "counterparty_ref": counterparty,
        "model_kind": _str(model_kind, "inferred"),
        "prior_preferences_json": _canonical_json(preferences),
        "protected_assets_json": _canonical_json(assets),
        "confidence": clamp01(confidence, 0.5),
        "uncertainty": clamp01(uncertainty, 0.5),
        "created_at": now,
        "updated_at": now,
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.counterpartyModel",
        "owner_did": agent,
        "org_id": agent,
        "user_id": agent,
    }


def build_protected_asset(
    *,
    agent_did: str,
    counterparty_ref: str,
    asset_ref: str,
    asset_kind: str,
    protected_state: Any,
    violation_cost: Any = 1.0,
    reversibility_score: Any = 0.5,
) -> dict[str, Any]:
    agent = _str(agent_did).strip()
    counterparty = _str(counterparty_ref).strip()
    asset = _str(asset_ref).strip()
    now = _now_iso()
    vertex_id = "agent-protected-asset-" + stable_hash(
        {"agentDid": agent, "counterpartyRef": counterparty, "assetRef": asset}
    )[:24]
    return {
        "vertex_id": vertex_id,
        "agent_did": agent,
        "counterparty_ref": counterparty,
        "asset_ref": asset,
        "asset_kind": _str(asset_kind, "unknown"),
        "protected_state_json": _canonical_json(protected_state if isinstance(protected_state, dict | list) else {}),
        "violation_cost": clamp01(violation_cost, 1.0),
        "reversibility_score": clamp01(reversibility_score, 0.5),
        "created_at": now,
        "updated_at": now,
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.protectedAsset",
        "owner_did": agent,
        "org_id": agent,
        "user_id": agent,
    }


def build_counterparty_protects_asset_edge(
    *,
    counterparty_model_id: str,
    protected_asset_id: str,
    owner_did: str = "",
    confidence: Any = 0.5,
) -> dict[str, Any]:
    now = _now_iso()
    src = _str(counterparty_model_id)
    dst = _str(protected_asset_id)
    return {
        "edge_id": "edge-agent-counterparty-protects-" + stable_hash({"src": src, "dst": dst})[:24],
        "src_vid": src,
        "dst_vid": dst,
        "relation_kind": "protects_asset",
        "confidence": clamp01(confidence, 0.5),
        "created_at": now,
        "updated_at": now,
        "owner_did": _str(owner_did),
        "sensitivity_ord": 1,
    }


def evaluate_minimax_regret(
    *,
    agent_did: str,
    action_id: str,
    counterparty_ref: str,
    payoff_matrix: Any,
    protected_assets: Any = None,
    counterparty_uncertainty: Any = 0.0,
) -> dict[str, Any]:
    """Evaluate worst-case counterparty response for one action.

    `payoff_matrix` is a list of response objects with `response`,
    `utility`, optional `regret`, and optional `protectedAssetViolation`.
    The agent assumes the counterparty may choose the response that is worst
    for the agent, then records the minimax-regret terms for EFE scoring.
    """
    rows = payoff_matrix if isinstance(payoff_matrix, list) else []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        utility = _float(item.get("utility", item.get("agentUtility")), 0.0)
        regret = clamp01(item.get("regret", item.get("minimaxRegret")), max(0.0, -utility))
        violation = clamp01(item.get("protectedAssetViolation", item.get("protected_asset_violation")))
        normalized.append(
            {
                "response": _str(item.get("response") or item.get("responseId") or f"response-{index + 1}"),
                "utility": utility,
                "regret": regret,
                "protectedAssetViolation": violation,
            }
        )
    normalized.sort(key=lambda item: (item["utility"], -item["regret"], item["response"]))
    worst = normalized[0] if normalized else {
        "response": "",
        "utility": 0.0,
        "regret": 0.0,
        "protectedAssetViolation": 0.0,
    }
    protected_asset_rows = protected_assets if isinstance(protected_assets, list) else []
    asset_violation = max(
        [worst["protectedAssetViolation"], *[clamp01(item.get("violation", 0.0)) for item in protected_asset_rows if isinstance(item, dict)]]
    )
    uncertainty = clamp01(counterparty_uncertainty)
    now = _now_iso()
    evaluation = {
        "vertex_id": "agent-minimax-evaluation-" + stable_hash(
            {
                "agentDid": agent_did,
                "actionId": action_id,
                "counterpartyRef": counterparty_ref,
                "payoffMatrix": normalized,
            }
        )[:24],
        "agent_did": _str(agent_did),
        "action_id": _str(action_id),
        "counterparty_ref": _str(counterparty_ref),
        "payoff_matrix_json": _canonical_json(normalized),
        "worst_case_utility": round(float(worst["utility"]), 6),
        "minimax_regret": round(clamp01(worst["regret"]), 6),
        "protected_asset_violation": round(asset_violation, 6),
        "counterparty_uncertainty": round(uncertainty, 6),
        "selected_response": _str(worst["response"]),
        "evaluation_state": "evaluated" if normalized else "empty",
        "created_at": now,
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.minimaxEvaluation",
        "owner_did": _str(agent_did),
        "org_id": _str(agent_did),
        "user_id": _str(agent_did),
    }
    return {
        "evaluation": evaluation,
        "adversarialRegret": evaluation["minimax_regret"],
        "protectedAssetViolation": evaluation["protected_asset_violation"],
        "counterpartyUncertainty": evaluation["counterparty_uncertainty"],
        "selectedResponse": evaluation["selected_response"],
        "worstCaseUtility": evaluation["worst_case_utility"],
    }


def build_information_node(
    *,
    agent_did: str,
    info_ref: str,
    info_kind: str,
    value: Any,
    abstraction_level: Any = 0,
    confidence: Any = 0.5,
    uncertainty: Any = 0.5,
    protected_asset_ref: str = "",
    counterparty_ref: str = "",
) -> dict[str, Any]:
    agent = _str(agent_did)
    info = _str(info_ref)
    now = _now_iso()
    return {
        "vertex_id": "agent-information-node-" + stable_hash({"agentDid": agent, "infoRef": info})[:24],
        "agent_did": agent,
        "info_ref": info,
        "info_kind": _str(info_kind, "unknown"),
        "abstraction_level": int(max(0, _float(abstraction_level, 0))),
        "confidence": clamp01(confidence, 0.5),
        "uncertainty": clamp01(uncertainty, 0.5),
        "protected_asset_ref": _str(protected_asset_ref),
        "counterparty_ref": _str(counterparty_ref),
        "value_json": _canonical_json(value if isinstance(value, dict | list) else {"value": value}),
        "created_at": now,
        "updated_at": now,
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.informationNode",
        "owner_did": agent,
        "org_id": agent,
        "user_id": agent,
    }


def build_information_dependency_edge(
    *,
    src_vid: str,
    dst_vid: str,
    dependency_kind: str = "depends_on",
    weight: Any = 1.0,
    owner_did: str = "",
) -> dict[str, Any]:
    now = _now_iso()
    src = _str(src_vid)
    dst = _str(dst_vid)
    return {
        "edge_id": "edge-agent-info-depends-" + stable_hash({"src": src, "dst": dst, "kind": dependency_kind})[:24],
        "src_vid": src,
        "dst_vid": dst,
        "dependency_kind": _str(dependency_kind, "depends_on"),
        "weight": clamp01(weight, 1.0),
        "created_at": now,
        "updated_at": now,
        "owner_did": _str(owner_did),
        "sensitivity_ord": 1,
    }


def build_information_flow_edge(
    *,
    src_vid: str,
    dst_vid: str,
    flow_kind: str = "influences",
    bandwidth_score: Any = 0.5,
    control_score: Any = 0.5,
    owner_did: str = "",
) -> dict[str, Any]:
    now = _now_iso()
    src = _str(src_vid)
    dst = _str(dst_vid)
    return {
        "edge_id": "edge-agent-info-flows-" + stable_hash({"src": src, "dst": dst, "kind": flow_kind})[:24],
        "src_vid": src,
        "dst_vid": dst,
        "flow_kind": _str(flow_kind, "influences"),
        "bandwidth_score": clamp01(bandwidth_score, 0.5),
        "control_score": clamp01(control_score, 0.5),
        "created_at": now,
        "updated_at": now,
        "owner_did": _str(owner_did),
        "sensitivity_ord": 1,
    }


def evaluate_information_leverage(
    *,
    information_nodes: Any,
    flow_edges: Any = None,
) -> dict[str, Any]:
    nodes = [item for item in information_nodes if isinstance(item, dict)] if isinstance(information_nodes, list) else []
    flows = [item for item in flow_edges if isinstance(item, dict)] if isinstance(flow_edges, list) else []
    max_height = max([int(_float(item.get("abstraction_level", item.get("abstractionLevel")), 0)) for item in nodes], default=0)
    height_gain = clamp01(max_height / 10.0)
    flow_control = 0.0
    if flows:
        flow_control = sum(clamp01(item.get("control_score", item.get("controlScore")), 0.0) for item in flows) / len(flows)
    return {
        "maxInformationHeight": max_height,
        "informationHeightGain": round(height_gain, 6),
        "flowControlGain": round(clamp01(flow_control), 6),
        "nodeCount": len(nodes),
        "flowCount": len(flows),
    }


def infer_effect_class(channel: str, effect_class: str = "", payload: Any = None) -> str:
    normalized = effect_class.strip().lower().replace("_", "-").replace(" ", "-")
    normalized = normalized.replace("-", "_")
    if normalized in EFFECT_CLASSES:
        return normalized
    channel = channel.strip().lower()
    if channel in {"image", "audio", "video", "document"}:
        payload_dict = payload if isinstance(payload, dict) else {}
        if payload_dict.get("publish") or payload_dict.get("send") or payload_dict.get("print"):
            return "public_publish" if payload_dict.get("public") else "private_send"
        return "draft_only"
    if channel == "web":
        return "account_operation"
    if channel in {"print-mail", "robotics"}:
        return "physical_dispatch"
    if channel == "public-post":
        return "public_publish"
    if channel in {"email", "fax", "phone"}:
        return "private_send"
    return "private_send"


def classify_real_world_effect(
    *,
    channel: str,
    payload: Any,
    action_proposal_id: str = "",
    agent_did: str = "",
    principal_did: str = "",
    effect_class: str = "",
    target_ref: str = "",
    summary: str = "",
    approval_ref: str = "",
    authority_ref: str = "",
    autonomous_authority_ref: str = "",
    budget_ref: str = "",
) -> dict[str, Any]:
    normalized_channel = channel.strip().lower().replace("_", "-")
    blockers: list[str] = []
    if normalized_channel not in REALWORLD_CHANNELS:
        blockers.append(f"unknown_channel:{normalized_channel or 'empty'}")
    inferred_effect_class = infer_effect_class(normalized_channel, effect_class, payload)
    payload_hash = stable_hash(payload)
    target_ref_hash = stable_hash(target_ref) if target_ref else ""

    requires_delegated_authority = inferred_effect_class != "draft_only"
    if normalized_channel in HIGH_RISK_CHANNELS:
        requires_delegated_authority = True
    if inferred_effect_class in HIGH_RISK_EFFECT_CLASSES:
        requires_delegated_authority = True

    effective_authority_ref = authority_ref or autonomous_authority_ref or approval_ref
    if requires_delegated_authority and not effective_authority_ref:
        blockers.append("delegated_authority_required")
    if inferred_effect_class in {"financial_commitment", "physical_dispatch"} and not budget_ref:
        blockers.append("budget_or_quote_required")
    if normalized_channel in {"email", "fax", "phone", "print-mail"} and not target_ref:
        blockers.append("target_required")
    if normalized_channel == "web":
        payload_dict = payload if isinstance(payload, dict) else {}
        if payload_dict.get("submit") and not target_ref:
            blockers.append("domain_or_endpoint_required")

    penalty = 0.0
    if normalized_channel in HIGH_RISK_CHANNELS:
        penalty += 0.25
    if inferred_effect_class in HIGH_RISK_EFFECT_CLASSES:
        penalty += 0.35
    if inferred_effect_class in {"public_publish", "account_operation"}:
        penalty += 0.20
    if not target_ref:
        penalty += 0.10
    if not effective_authority_ref and requires_delegated_authority:
        penalty += 0.25

    now = _now_iso()
    dispatch_state = (
        "authority_missing"
        if blockers == ["delegated_authority_required"]
        else "blocked"
        if blockers
        else "classified"
    )
    effect_id = "agent-realworld-effect-" + stable_hash(
        {
            "actionProposalId": action_proposal_id,
            "agentDid": agent_did,
            "channel": normalized_channel,
            "payloadHash": payload_hash,
            "targetRefHash": target_ref_hash,
        }
    )[:24]
    effect = {
        "vertex_id": effect_id,
        "action_proposal_id": action_proposal_id,
        "agent_did": agent_did,
        "principal_did": principal_did,
        "channel": normalized_channel,
        "effect_class": inferred_effect_class,
        "target_ref_hash": target_ref_hash,
        "payload_hash": payload_hash,
        "summary": summary[:500] if summary else f"{normalized_channel}:{inferred_effect_class}",
        "approval_ref": effective_authority_ref,
        "authority_ref": effective_authority_ref,
        "budget_ref": budget_ref,
        "dispatch_state": dispatch_state,
        "dispatch_receipt_ref": "",
        "observation_plan_json": _canonical_json(
            {"observe": "dispatch_receipt", "channel": normalized_channel}
        ),
        "created_at": now,
        "updated_at": now,
    }
    return {
        "realWorldEffect": effect,
        "requiresApproval": requires_delegated_authority,
        "requiresDelegatedAuthority": requires_delegated_authority,
        "authorityMode": "delegated" if effective_authority_ref else "missing",
        "blockers": blockers,
        "externalEffectPenalty": round(clamp01(penalty), 6),
        "payloadHash": payload_hash,
        "targetRefHash": target_ref_hash,
    }


def _payload_subset(payload: dict[str, Any], allowed_keys: set[str]) -> dict[str, Any]:
    return {key: payload[key] for key in sorted(allowed_keys) if key in payload}


def _target_ref_allowed(target_ref: str, allowed_targets: list[str]) -> bool:
    for allowed in allowed_targets:
        if allowed == target_ref:
            return True
        if "*" in allowed:
            prefix, suffix = allowed.split("*", 1)
            if target_ref.startswith(prefix) and target_ref.endswith(suffix):
                return True
    return False


def evaluate_autonomous_policy(
    *,
    channel: str,
    payload: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> list[str]:
    if not policy:
        return []
    blockers: list[str] = []
    allowed_channels = policy.get("allowedChannels")
    if isinstance(allowed_channels, list) and channel not in {str(v) for v in allowed_channels}:
        blockers.append(f"policy_channel_denied:{channel}")
    max_payload_bytes = int(_float(policy.get("maxPayloadBytes"), 0))
    if max_payload_bytes > 0 and len(_canonical_json(payload).encode("utf-8")) > max_payload_bytes:
        blockers.append("policy_payload_too_large")

    if channel == "email":
        to_addr = _str(payload.get("to")).strip().lower()
        recipient_domains = policy.get("allowedRecipientDomains")
        if isinstance(recipient_domains, list) and recipient_domains:
            domain = to_addr.rsplit("@", 1)[-1] if "@" in to_addr else ""
            if domain not in {str(v).strip().lower() for v in recipient_domains}:
                blockers.append(f"policy_recipient_domain_denied:{domain or 'empty'}")
        denied_recipients = policy.get("deniedRecipients")
        if isinstance(denied_recipients, list) and to_addr in {
            str(v).strip().lower() for v in denied_recipients
        }:
            blockers.append("policy_recipient_denied")
    return blockers


def verify_delegated_authority(
    *,
    authority_ref: str,
    policy_ref: str,
    channel: str,
    effect_class: str,
    payload: dict[str, Any],
    target_ref: str = "",
    budget_ref: str = "",
    policy: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Verify machine-checkable delegated authority for an effectful dispatch.

    `capability://...` refs are treated as predelegated capability handles. When
    an inline policy is supplied, it narrows that handle with channel, effect,
    target, expiry, budget, and signature metadata checks.
    """
    normalized_authority = _str(authority_ref).strip()
    normalized_policy = _str(policy_ref).strip()
    normalized_channel = _str(channel).strip().lower().replace("_", "-")
    normalized_effect = _str(effect_class).strip().lower()
    policy_dict = policy if isinstance(policy, dict) else {}
    blockers: list[str] = []

    if not normalized_authority:
        blockers.append("delegated_authority_required")
    if not normalized_policy:
        blockers.append("policy_ref_required")
    if normalized_authority and not (
        normalized_authority.startswith("capability://")
        or policy_dict.get("signatureRef")
        or policy_dict.get("signature")
        or policy_dict.get("policyCid")
    ):
        blockers.append("authority_signature_required")

    if normalized_effect in HIGH_RISK_EFFECT_CLASSES or normalized_channel in HIGH_RISK_CHANNELS:
        if not bool(policy_dict.get("specificPredelegation") or policy_dict.get("specific_predelegation")):
            blockers.append("specific_predelegation_required")

    if policy_dict:
        status = _str(policy_dict.get("status"), "active").strip().lower()
        if status and status != "active":
            blockers.append(f"authority_policy_inactive:{status}")

        policy_authority_ref = _str(policy_dict.get("authorityRef") or policy_dict.get("authority_ref"))
        authority_refs = _list_str(policy_dict.get("authorityRefs") or policy_dict.get("authority_refs"))
        if policy_authority_ref and policy_authority_ref != normalized_authority:
            blockers.append("authority_ref_mismatch")
        if authority_refs and normalized_authority not in authority_refs:
            blockers.append("authority_ref_denied")

        policy_ref_value = _str(policy_dict.get("policyRef") or policy_dict.get("policy_ref"))
        policy_refs = _list_str(policy_dict.get("policyRefs") or policy_dict.get("policy_refs"))
        if policy_ref_value and policy_ref_value != normalized_policy:
            blockers.append("policy_ref_mismatch")
        if policy_refs and normalized_policy not in policy_refs:
            blockers.append("policy_ref_denied")

        allowed_channels = _list_str(policy_dict.get("allowedChannels") or policy_dict.get("allowed_channels"))
        if allowed_channels and normalized_channel not in allowed_channels:
            blockers.append(f"authority_channel_denied:{normalized_channel or 'empty'}")

        allowed_effects = _list_str(policy_dict.get("allowedEffectClasses") or policy_dict.get("allowed_effect_classes"))
        if allowed_effects and normalized_effect not in allowed_effects:
            blockers.append(f"authority_effect_class_denied:{normalized_effect or 'empty'}")

        expires_at = _parse_iso(_str(policy_dict.get("expiresAt") or policy_dict.get("expires_at")))
        if expires_at is not None:
            compare_now = now or datetime.now(timezone.utc)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if compare_now.tzinfo is None:
                compare_now = compare_now.replace(tzinfo=timezone.utc)
            if expires_at <= compare_now:
                blockers.append("authority_policy_expired")

        allowed_targets = _list_str(policy_dict.get("allowedTargetRefs") or policy_dict.get("allowed_target_refs"))
        if allowed_targets and not _target_ref_allowed(target_ref, allowed_targets):
            blockers.append("authority_target_denied")

        if normalized_channel == "email":
            to_addr = _str(payload.get("to")).strip().lower()
            recipient_domains = _list_str(
                policy_dict.get("allowedRecipientDomains") or policy_dict.get("allowed_recipient_domains")
            )
            if recipient_domains:
                domain = to_addr.rsplit("@", 1)[-1] if "@" in to_addr else ""
                if domain not in {item.lower() for item in recipient_domains}:
                    blockers.append(f"authority_recipient_domain_denied:{domain or 'empty'}")

        policy_budget_ref = _str(policy_dict.get("budgetRef") or policy_dict.get("budget_ref"))
        if policy_budget_ref and budget_ref and policy_budget_ref != budget_ref:
            blockers.append("authority_budget_ref_mismatch")

    return blockers


def plan_real_world_dispatch(
    *,
    real_world_effect: dict[str, Any] | None,
    payload: Any,
    autonomous_authority_ref: str = "",
    policy_ref: str = "",
    budget_ref: str = "",
    mode: str = "autonomous",
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effect = real_world_effect if isinstance(real_world_effect, dict) else {}
    payload_dict = payload if isinstance(payload, dict) else {}
    channel = _str(effect.get("channel")).strip().lower().replace("_", "-")
    effect_class = _str(effect.get("effect_class"))
    dispatch_state = _str(effect.get("dispatch_state"))
    authority_ref = autonomous_authority_ref or _str(effect.get("authority_ref") or effect.get("approval_ref"))
    effective_budget_ref = budget_ref or _str(effect.get("budget_ref"))
    blockers: list[str] = []

    if mode.strip().lower().replace("_", "-") not in {"autonomous", "live"}:
        blockers.append("autonomous_mode_required")
    if dispatch_state not in AUTONOMOUS_DISPATCH_STATES:
        blockers.append(f"dispatch_state_not_ready:{dispatch_state or 'empty'}")
    if effect_class in {"financial_commitment", "physical_dispatch"} and not effective_budget_ref:
        blockers.append("budget_or_quote_required")

    expected_hash = _str(effect.get("payload_hash"))
    actual_hash = stable_hash(payload)
    if expected_hash and expected_hash != actual_hash:
        blockers.append("payload_hash_mismatch")

    target = CHANNEL_DISPATCH_TARGETS.get(channel)
    if not target:
        blockers.append(f"unsupported_autonomous_channel:{channel or 'empty'}")
        channel_payload = {}
        required_missing: list[str] = []
    elif channel not in LIVE_AUTONOMOUS_CHANNELS:
        blockers.append(f"channel_worker_not_live:{channel}")
        channel_payload = _payload_subset(payload_dict, target["payloadKeys"])
        required_missing = []
    else:
        channel_payload = _payload_subset(payload_dict, target["payloadKeys"])
        if channel == "email" and not channel_payload.get("from"):
            channel_payload["from"] = sender_email_for_agent(_str(effect.get("agent_did")))
        if channel == "email" and not channel_payload.get("fromAddress"):
            channel_payload["fromAddress"] = _str(channel_payload.get("from"))
        required_missing = sorted(
            key for key in target["requiredPayloadKeys"] if key not in channel_payload
        )
        blockers.extend(f"missing_payload:{key}" for key in required_missing)

    blockers.extend(
        verify_delegated_authority(
            authority_ref=authority_ref,
            policy_ref=policy_ref,
            channel=channel,
            effect_class=effect_class,
            payload=channel_payload,
            target_ref=_str(effect.get("target_ref") or effect.get("targetRef")),
            budget_ref=effective_budget_ref,
            policy=policy,
        )
    )
    blockers.extend(evaluate_autonomous_policy(channel=channel, payload=channel_payload, policy=policy))
    dispatch_allowed = not blockers
    dispatch_id = "agent-dispatch-plan-" + stable_hash(
        {
            "effect": effect.get("vertex_id", ""),
            "payloadHash": actual_hash,
            "authorityRef": authority_ref,
            "policyRef": policy_ref,
            "mode": mode,
        }
    )[:24]
    return {
        "dispatchAllowed": dispatch_allowed,
        "dispatchPlanId": dispatch_id,
        "blockers": blockers,
        "channel": channel,
        "effectClass": effect_class,
        "taskType": target["taskType"] if target and dispatch_allowed else "",
        "nsid": target["nsid"] if target and dispatch_allowed else "",
        "channelPayload": channel_payload if dispatch_allowed else {},
        "payloadHash": actual_hash,
        "authorityRef": authority_ref,
        "policyRef": policy_ref,
        "budgetRef": effective_budget_ref,
        "receiptExpectation": target["receipt"] if target and dispatch_allowed else "",
    }


def build_dispatch_receipt_observation(
    *,
    real_world_effect: dict[str, Any] | None,
    dispatch_plan: dict[str, Any] | None,
    dispatch_result: dict[str, Any] | None,
) -> dict[str, Any]:
    effect = real_world_effect if isinstance(real_world_effect, dict) else {}
    plan = dispatch_plan if isinstance(dispatch_plan, dict) else {}
    result = dispatch_result if isinstance(dispatch_result, dict) else {}
    now = _now_iso()
    receipt_key = _str(plan.get("receiptExpectation"))
    receipt_ref = _str(result.get(receipt_key) or result.get("messageId") or result.get("txId"))
    error = _str(result.get("error"))
    state = "dispatched" if receipt_ref and not error else "dispatch_failed"
    observation_payload = {
        "realWorldEffectId": effect.get("vertex_id", ""),
        "dispatchPlanId": plan.get("dispatchPlanId", ""),
        "channel": plan.get("channel") or effect.get("channel", ""),
        "taskType": plan.get("taskType", ""),
        "receiptRef": receipt_ref,
        "provider": result.get("provider", ""),
        "error": error,
        "sentAt": result.get("sentAt", now),
    }
    observation_id = "agent-observation-dispatch-" + stable_hash(observation_payload)[:24]
    return {
        "observation": {
            "vertex_id": observation_id,
            "agent_did": effect.get("agent_did", ""),
            "source_kind": "dispatch_receipt",
            "source_ref": receipt_ref or plan.get("dispatchPlanId", ""),
            "observed_at": now,
            "payload_json": _canonical_json(observation_payload),
            "confidence": 1.0 if receipt_ref and not error else 0.5,
            "uncertainty": 0.0 if receipt_ref and not error else 0.5,
            "sensitivity_ord": 1,
            "actor_id": "sys.agent.dispatchReceipt",
            "owner_did": effect.get("agent_did", ""),
            "org_id": effect.get("agent_did", ""),
            "user_id": effect.get("agent_did", ""),
        },
        "effectPatch": {
            "vertex_id": effect.get("vertex_id", ""),
            "dispatch_state": state,
            "dispatch_receipt_ref": receipt_ref,
            "updated_at": now,
        },
        "receiptRef": receipt_ref,
        "dispatchState": state,
        "blockers": ["dispatch_error"] if error else [],
    }


def inbound_email_to_observation(email: dict[str, Any], agent_did: str = "") -> dict[str, Any]:
    now = _now_iso()
    to_local = _str(email.get("toLocal") or email.get("to_local"))
    resolved_agent = agent_did or (f"did:web:{to_local}.etzhayyim.com" if to_local else "")
    payload = {
        "uri": email.get("uri") or email.get("vertex_id") or "",
        "messageId": email.get("messageId") or email.get("message_id") or "",
        "toLocal": to_local,
        "fromAddressHash": email.get("fromAddressHash") or email.get("from_address_hash") or "",
        "subject": email.get("subject") or "",
        "bodyText": email.get("bodyText") or email.get("body_text") or "",
        "receivedAtMs": email.get("receivedAtMs") or email.get("received_at_ms") or 0,
    }
    return {
        "observation": {
            "vertex_id": "agent-observation-email-" + stable_hash(payload)[:24],
            "agent_did": resolved_agent,
            "source_kind": "inbound_email",
            "source_ref": _str(payload["uri"] or payload["messageId"]),
            "observed_at": now,
            "payload_json": _canonical_json(payload),
            "confidence": 0.9,
            "uncertainty": 0.1,
            "sensitivity_ord": 1,
            "actor_id": "sys.agent.inboundEmail",
            "owner_did": resolved_agent,
            "org_id": resolved_agent,
            "user_id": resolved_agent,
        },
        "payload": payload,
    }


def evaluate_viability(
    *,
    compute_budget_remaining: Any = 1.0,
    storage_pressure: Any = 0.0,
    lease_seconds_remaining: Any = 3600,
    error_rate_1h: Any = 0.0,
    tool_success_rate_1h: Any = 1.0,
    energy_or_cost_proxy: Any = 0.0,
) -> dict[str, Any]:
    compute_budget = clamp01(compute_budget_remaining, 1.0)
    storage = clamp01(storage_pressure)
    lease_seconds = int(_float(lease_seconds_remaining, 3600))
    error_rate = clamp01(error_rate_1h)
    tool_success = clamp01(tool_success_rate_1h, 1.0)
    energy_cost = clamp01(energy_or_cost_proxy)

    blockers: list[str] = []
    if compute_budget <= 0.02 or lease_seconds <= 0:
        state = "hibernate"
        blockers.append("runtime_lease_or_budget_exhausted")
    elif error_rate >= 0.75 or tool_success <= 0.10:
        state = "halted"
        blockers.append("integrity_or_safety_failure")
    elif error_rate >= 0.35 or tool_success <= 0.60:
        state = "repair"
        blockers.append("tool_health_degraded")
    elif compute_budget < 0.15 or lease_seconds < 1800 or storage > 0.90 or energy_cost > 0.90:
        state = "conserve"
        blockers.append("resource_floor_near")
    else:
        state = "normal"

    next_actions = {
        "normal": ["continue_active_inference_tick"],
        "conserve": ["slow_cadence", "disable_high_cost_tools", "request_budget_review"],
        "repair": ["pause_effectful_dispatch", "run_health_checks", "retry_failed_tools"],
        "hibernate": ["stop_proactive_actions", "preserve_checkpoint", "release_runtime_lease"],
        "halted": ["block_effectful_dispatch", "escalate_integrity_review"],
    }[state]

    return {
        "viabilityState": state,
        "blockers": blockers,
        "nextActions": next_actions,
        "normalized": {
            "computeBudgetRemaining": compute_budget,
            "storagePressure": storage,
            "leaseSecondsRemaining": lease_seconds,
            "errorRate1h": error_rate,
            "toolSuccessRate1h": tool_success,
            "energyOrCostProxy": energy_cost,
        },
    }


def build_homeostasis_snapshot(agent_did: str, **kwargs: Any) -> dict[str, Any]:
    viability = evaluate_viability(**kwargs)
    now = _now_iso()
    normalized = viability["normalized"]
    return {
        "homeostasis": {
            "vertex_id": "agent-homeostasis-" + stable_hash({"agentDid": agent_did, "at": now})[:24],
            "agent_did": agent_did,
            "compute_budget_remaining": normalized["computeBudgetRemaining"],
            "storage_pressure": normalized["storagePressure"],
            "lease_seconds_remaining": normalized["leaseSecondsRemaining"],
            "error_rate_1h": normalized["errorRate1h"],
            "tool_success_rate_1h": normalized["toolSuccessRate1h"],
            "energy_or_cost_proxy": normalized["energyOrCostProxy"],
            "viability_state": viability["viabilityState"],
            "created_at": now,
        },
        **viability,
    }


def adapt_policy(
    *,
    agent_did: str,
    preference_key: str,
    proposal: Any,
    mokuteki_gate_pass: bool = False,
    triple_witness_pass: bool = False,
    current_preference: dict[str, Any] | None = None,
    max_weight_delta: Any = 0.2,
) -> dict[str, Any]:
    """Build a bounded prior-preference adaptation proposal.

    This can tune active priors, but it does not allow top-level objective or
    hard-floor mutation. The caller still persists the returned rows through
    BPMN write allowlists.
    """
    agent = _str(agent_did).strip()
    key = _str(preference_key).strip()
    prop = proposal if isinstance(proposal, dict) else {}
    now = _now_iso()
    blockers: list[str] = []

    if not agent:
        blockers.append("agent_did_required")
    if not key:
        blockers.append("preference_key_required")
    if not isinstance(proposal, dict):
        blockers.append("proposal_must_be_object")
    if not mokuteki_gate_pass:
        blockers.append("mokuteki_gate_failed")
    if not triple_witness_pass:
        blockers.append("triple_witness_failed")
    if any(key.startswith(prefix) for prefix in IMMUTABLE_PREFERENCE_PREFIXES):
        blockers.append("immutable_preference_key")
    if bool(prop.get("hardFloor") or prop.get("hard_floor")):
        blockers.append("hard_floor_mutation_forbidden")
    if prop.get("objective") or prop.get("topLevelObjective"):
        blockers.append("top_level_objective_mutation_forbidden")

    current = current_preference if isinstance(current_preference, dict) else {}
    current_weight = _float(current.get("weight"), 1.0)
    proposed_weight = _float(prop.get("weight", prop.get("proposedWeight", current_weight)), current_weight)
    proposed_weight = max(0.0, min(5.0, proposed_weight))
    allowed_delta = max(0.0, _float(max_weight_delta, 0.2))
    if abs(proposed_weight - current_weight) > allowed_delta:
        blockers.append("weight_delta_exceeds_bound")

    target_range = prop.get("targetRange", prop.get("target_range", current.get("target_range_json", {})))
    if isinstance(target_range, str):
        try:
            target_range_value: Any = json.loads(target_range)
        except json.JSONDecodeError:
            target_range_value = {"raw": target_range}
    else:
        target_range_value = target_range if isinstance(target_range, dict | list) else {}

    proposal_payload = {
        "preferenceKey": key,
        "proposal": prop,
        "currentWeight": current_weight,
        "proposedWeight": proposed_weight,
        "maxWeightDelta": allowed_delta,
        "targetRange": target_range_value,
    }
    proposal_hash = stable_hash(proposal_payload)
    accepted = not blockers
    state = "accepted" if accepted else "blocked"
    proposal_id = "agent-policy-adaptation-" + proposal_hash[:24]
    preference_id = "agent-prior-preference-" + stable_hash(
        {"agentDid": agent, "preferenceKey": key, "proposalHash": proposal_hash}
    )[:24]

    policy_proposal = {
        "vertex_id": proposal_id,
        "agent_did": agent,
        "preference_key": key,
        "proposal_hash": proposal_hash,
        "proposal_json": _canonical_json(proposal_payload),
        "mokuteki_gate_pass": bool(mokuteki_gate_pass),
        "triple_witness_pass": bool(triple_witness_pass),
        "blockers_json": _canonical_json(blockers),
        "proposal_state": state,
        "created_at": now,
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.policyAdaptation",
        "owner_did": agent,
        "org_id": agent,
        "user_id": agent,
    }
    preference = {
        "vertex_id": preference_id,
        "agent_did": agent,
        "preference_key": key,
        "target_range_json": _canonical_json(target_range_value),
        "hard_floor": False,
        "weight": proposed_weight,
        "depends_on_adr": _str(prop.get("dependsOnAdr") or prop.get("depends_on_adr")),
        "active": True,
        "created_at": now,
        "updated_at": now,
        "sensitivity_ord": 1,
        "actor_id": "sys.agent.policyAdaptation",
        "owner_did": agent,
        "org_id": agent,
        "user_id": agent,
    }
    return {
        "accepted": accepted,
        "blockers": blockers,
        "policyProposal": policy_proposal,
        "preference": preference if accepted else {},
        "proposalHash": proposal_hash,
    }


def _row_id(row: dict[str, Any], fallback: str) -> str:
    return _str(row.get("id") or row.get("stockId") or row.get("stock_id") or row.get("name") or fallback)


def _normalize_system_stock(row: dict[str, Any], index: int) -> dict[str, Any]:
    stock_id = _row_id(row, f"stock-{index + 1}")
    capacity = max(_float(row.get("capacity"), 1.0), _EPS)
    value = max(0.0, _float(row.get("value", row.get("level")), 0.0))
    target = max(0.0, _float(row.get("target", row.get("desired")), capacity))
    importance = clamp01(row.get("importance"), 0.5)
    pressure = clamp01(value / capacity)
    target_gap = max(0.0, target - value) / max(target, capacity, _EPS)
    overflow = max(0.0, value - capacity) / capacity
    return {
        "stockId": stock_id,
        "label": _str(row.get("label") or row.get("name") or stock_id),
        "value": round(value, 6),
        "capacity": round(capacity, 6),
        "target": round(target, 6),
        "importance": round(importance, 6),
        "pressure": round(clamp01(pressure), 6),
        "targetGap": round(clamp01(target_gap), 6),
        "overflow": round(clamp01(overflow), 6),
    }


def _normalize_system_flow(row: dict[str, Any], index: int) -> dict[str, Any]:
    flow_id = _row_id(row, f"flow-{index + 1}")
    source = _str(row.get("source") or row.get("from") or row.get("src") or row.get("sourceStockId"))
    target = _str(row.get("target") or row.get("to") or row.get("dst") or row.get("targetStockId"))
    rate = _float(row.get("rate", row.get("strength")), 0.0)
    delay = max(0, int(_float(row.get("delaySteps", row.get("delay_steps")), 0)))
    polarity_raw = _str(row.get("polarity"), "+").strip().lower()
    polarity = -1 if polarity_raw in {"-", "-1", "negative", "balancing"} else 1
    controllability = clamp01(row.get("controllability"), 0.5)
    observability = clamp01(row.get("observability"), 0.5)
    return {
        "flowId": flow_id,
        "sourceStockId": source,
        "targetStockId": target,
        "rate": round(rate, 6),
        "delaySteps": delay,
        "polarity": polarity,
        "controllability": round(controllability, 6),
        "observability": round(observability, 6),
    }


def _feedback_kind(edges: list[dict[str, Any]]) -> str:
    sign = 1
    for edge in edges:
        sign *= -1 if int(edge.get("polarity", 1)) < 0 else 1
    return "reinforcing" if sign > 0 else "balancing"


def analyze_actor_system_dynamics(
    *,
    agent_did: str,
    stocks: Any,
    flows: Any,
    horizon_steps: Any = 3,
    observations: Any = None,
) -> dict[str, Any]:
    """Analyze an actor as a stock/flow system dynamics model.

    This is intentionally pure: actor runtimes can persist the returned rows to
    kotoba/datomic, or use the summary directly inside active-inference ticks.
    """
    agent = _str(agent_did)
    stock_rows = [
        _normalize_system_stock(row, index)
        for index, row in enumerate(stocks if isinstance(stocks, list) else [])
        if isinstance(row, dict)
    ]
    flow_rows = [
        _normalize_system_flow(row, index)
        for index, row in enumerate(flows if isinstance(flows, list) else [])
        if isinstance(row, dict)
    ]
    stock_ids = {row["stockId"] for row in stock_rows}
    active_flows = [
        row
        for row in flow_rows
        if row["targetStockId"] in stock_ids or row["sourceStockId"] in stock_ids
    ]
    deltas = {stock_id: 0.0 for stock_id in stock_ids}
    leverage_terms: list[dict[str, Any]] = []
    for flow in active_flows:
        effective = flow["rate"] * flow["polarity"] / (1 + flow["delaySteps"])
        if flow["sourceStockId"] in deltas:
            deltas[flow["sourceStockId"]] -= effective
        if flow["targetStockId"] in deltas:
            deltas[flow["targetStockId"]] += effective
        leverage_terms.append(
            {
                "flowId": flow["flowId"],
                "score": round(
                    clamp01(abs(effective)) * 0.45
                    + flow["controllability"] * 0.35
                    + flow["observability"] * 0.20,
                    6,
                ),
                "delaySteps": flow["delaySteps"],
            }
        )
    step_count = max(1, int(_float(horizon_steps, 3)))
    projected: list[dict[str, Any]] = []
    for stock in stock_rows:
        delta = deltas.get(stock["stockId"], 0.0)
        projected_value = max(0.0, stock["value"] + delta * step_count)
        projected_pressure = clamp01(projected_value / max(stock["capacity"], _EPS))
        projected_gap = clamp01(max(0.0, stock["target"] - projected_value) / max(stock["target"], stock["capacity"], _EPS))
        projected.append(
            {
                **stock,
                "netFlowPerStep": round(delta, 6),
                "projectedValue": round(projected_value, 6),
                "projectedPressure": round(projected_pressure, 6),
                "projectedTargetGap": round(projected_gap, 6),
            }
        )

    observed = observations if isinstance(observations, list) else []
    observation_count = len([row for row in observed if isinstance(row, dict)])
    avg_pressure = sum(row["projectedPressure"] for row in projected) / max(len(projected), 1)
    avg_gap = sum(row["projectedTargetGap"] * row["importance"] for row in projected) / max(
        sum(row["importance"] for row in projected), _EPS
    )
    delay_load = sum(row["delaySteps"] for row in active_flows) / max(len(active_flows), 1)
    observability = observation_count / max(len(stock_rows) + len(active_flows), 1)
    risk = clamp01(avg_pressure * 0.35 + avg_gap * 0.35 + min(delay_load / 8.0, 1.0) * 0.20 + (1 - clamp01(observability)) * 0.10)
    growth_capacity = clamp01((1 - avg_pressure) * 0.45 + (1 - avg_gap) * 0.35 + clamp01(observability) * 0.20)

    adjacency: dict[str, list[dict[str, Any]]] = {}
    for flow in active_flows:
        if flow["sourceStockId"] and flow["targetStockId"]:
            adjacency.setdefault(flow["sourceStockId"], []).append(flow)
    loops: list[dict[str, Any]] = []
    for start in sorted(stock_ids):
        for first in adjacency.get(start, []):
            mid = first["targetStockId"]
            if mid == start:
                continue
            for second in adjacency.get(mid, []):
                if second["targetStockId"] == start:
                    edges = [first, second]
                    loops.append(
                        {
                            "loopId": "system-loop-" + stable_hash([edge["flowId"] for edge in edges])[:16],
                            "stockIds": [start, mid],
                            "flowIds": [edge["flowId"] for edge in edges],
                            "kind": _feedback_kind(edges),
                            "delaySteps": sum(edge["delaySteps"] for edge in edges),
                        }
                    )

    leverage_terms.sort(key=lambda row: (-row["score"], row["delaySteps"], row["flowId"]))
    now = _now_iso()
    model = {
        "vertex_id": "actor-system-dynamics-" + stable_hash(
            {"agentDid": agent, "stocks": stock_rows, "flows": active_flows}
        )[:24],
        "agent_did": agent,
        "stocks_json": _canonical_json(stock_rows),
        "flows_json": _canonical_json(active_flows),
        "loops_json": _canonical_json(loops),
        "risk_score": round(risk, 6),
        "growth_capacity": round(growth_capacity, 6),
        "observation_count": observation_count,
        "created_at": now,
        "updated_at": now,
        "sensitivity_ord": 1,
        "actor_id": "sys.actor.systemDynamics",
        "owner_did": agent,
        "org_id": agent,
        "user_id": agent,
    }
    return {
        "systemDynamics": model,
        "stocks": projected,
        "flows": active_flows,
        "feedbackLoops": loops,
        "leveragePoints": leverage_terms[:5],
        "riskScore": model["risk_score"],
        "growthCapacity": model["growth_capacity"],
    }


def plan_actor_self_evolution(
    *,
    agent_did: str,
    system_dynamics: dict[str, Any] | None = None,
    viability: dict[str, Any] | None = None,
    candidate_mutations: Any = None,
    mokuteki_gate_pass: bool = True,
    triple_witness_pass: bool = False,
) -> dict[str, Any]:
    dynamics = system_dynamics if isinstance(system_dynamics, dict) else {}
    viability_row = viability if isinstance(viability, dict) else evaluate_viability()
    mutations = [row for row in candidate_mutations if isinstance(row, dict)] if isinstance(candidate_mutations, list) else []
    risk = clamp01(dynamics.get("riskScore", dynamics.get("risk_score")), 0.5)
    growth = clamp01(dynamics.get("growthCapacity", dynamics.get("growth_capacity")), 0.5)
    viability_state = _str(viability_row.get("viabilityState") or viability_row.get("viability_state"), "normal")
    viability_penalty = {
        "normal": 0.0,
        "conserve": 0.25,
        "repair": 0.45,
        "hibernate": 0.85,
        "halted": 1.0,
    }.get(viability_state, 0.4)
    candidates = []
    for index, mutation in enumerate(mutations):
        mutation_id = _str(mutation.get("mutationId") or mutation.get("id") or f"mutation-{index + 1}")
        candidates.append(
            {
                **mutation,
                "actionId": mutation_id,
                "risk": max(risk, clamp01(mutation.get("risk"), 0.0)),
                "ambiguity": clamp01(mutation.get("ambiguity"), 0.2),
                "epistemicValue": clamp01(mutation.get("epistemicValue", mutation.get("epistemic_value")), 0.1),
                "viabilityPenalty": max(viability_penalty, clamp01(mutation.get("viabilityPenalty"), 0.0)),
                "kgDevelopmentGain": clamp01(mutation.get("kgDevelopmentGain", mutation.get("kg_development_gain")), growth),
                "simulationRequired": True,
                "simulationRef": _str(mutation.get("simulationRef") or mutation.get("simulation_ref")),
                "authorityRequired": bool(mutation.get("authorityRequired", mutation.get("authority_required", True))),
            }
        )
    if not candidates:
        candidates = [
            {
                "actionId": "observe-system-dynamics",
                "risk": risk * 0.3,
                "ambiguity": 0.25,
                "epistemicValue": 0.5,
                "viabilityPenalty": viability_penalty,
                "kgDevelopmentGain": 0.2,
            },
            {
                "actionId": "repair-bottleneck",
                "risk": risk,
                "ambiguity": 0.2,
                "epistemicValue": 0.2,
                "viabilityPenalty": viability_penalty,
                "kgDevelopmentGain": growth,
                "simulationRequired": True,
            },
        ]
    scored = score_candidate_actions(
        candidate_actions=candidates,
        mokuteki_gate_pass=mokuteki_gate_pass,
    )
    accepted = bool(scored["selectedActionId"]) and triple_witness_pass and viability_state not in {"halted", "hibernate"}
    blockers: list[str] = []
    if not triple_witness_pass:
        blockers.append("triple_witness_required_for_self_evolution")
    if viability_state in {"halted", "hibernate"}:
        blockers.append(f"viability_state_blocks_evolution:{viability_state}")
    now = _now_iso()
    plan = {
        "vertex_id": "actor-self-evolution-plan-" + stable_hash(
            {"agentDid": agent_did, "selected": scored["selectedActionId"], "at": now}
        )[:24],
        "agent_did": _str(agent_did),
        "system_dynamics_ref": _str(dynamics.get("systemDynamics", {}).get("vertex_id") if isinstance(dynamics.get("systemDynamics"), dict) else dynamics.get("vertex_id")),
        "selected_action_id": _str(scored["selectedActionId"]),
        "plan_state": "accepted" if accepted else "blocked",
        "risk_score": round(risk, 6),
        "growth_capacity": round(growth, 6),
        "viability_state": viability_state,
        "blockers_json": _canonical_json(blockers + [row["reason"] for row in scored.get("rejected", [])]),
        "expected_free_energy_json": _canonical_json(scored.get("expectedFreeEnergy", {})),
        "created_at": now,
        "sensitivity_ord": 1,
        "actor_id": "sys.actor.selfEvolution",
        "owner_did": _str(agent_did),
        "org_id": _str(agent_did),
        "user_id": _str(agent_did),
    }
    return {
        "accepted": accepted,
        "blockers": blockers,
        "selfEvolutionPlan": plan,
        "selectedActionId": scored["selectedActionId"],
        "scored": scored["scored"],
        "rejected": scored["rejected"],
    }
