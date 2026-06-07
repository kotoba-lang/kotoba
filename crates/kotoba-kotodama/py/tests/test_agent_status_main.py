from __future__ import annotations

import json

from kotodama import agent_status_main


def test_summarize_status_reports_repairing_organism() -> None:
    report = agent_status_main.summarize_status(
        agent_did="did:etzhayyim:agent:test",
        launchd={
            "com.etzhayyim.agent-daemon": True,
            "com.etzhayyim.agent-zeebe-worker": True,
        },
        belief_rows=[
            {
                "belief_kind": "runtime.homeostasis",
                "state_value_json": json.dumps(
                    {
                        "viabilityState": "repair",
                        "blockers": ["runtime_lease_renewal_due"],
                    }
                ),
                "posterior_confidence": 0.7,
                "posterior_entropy": 0.3,
                "updated_at": "2026-05-07T00:00:00Z",
            },
            {
                "belief_kind": "runtime.outcome",
                "state_value_json": json.dumps(
                    {
                        "sourceKind": "self_repair_receipt",
                        "dispatchState": "observed",
                        "success": True,
                    }
                ),
                "updated_at": "2026-05-07T00:00:01Z",
            },
            {
                "belief_kind": "runtime.learning",
                "state_value_json": json.dumps(
                    {
                        "channelPriors": {"self-repair": 0.1},
                        "lastOutcome": {"dispatchState": "observed"},
                    }
                ),
                "updated_at": "2026-05-07T00:00:01Z",
            },
        ],
        observation_rows=[
            {"source_kind": "homeostasis_metrics", "observed_at": "2026-05-07T00:00:00Z"},
            {"source_kind": "self_repair_receipt", "observed_at": "2026-05-07T00:00:01Z"},
            {
                "source_kind": "dispatch_receipt",
                "observed_at": "2026-05-07T00:00:02Z",
                "payload_json": json.dumps({"channel": "email", "error": "resend_api_failed"}),
            },
        ],
        effect_counts=[{"state": "blocked", "count": 1}],
        dispatch_counts=[{"state": "blocked", "count": 1}],
        authority_counts=[{"state": "active", "count": 1}],
        recent_authority_effects=[
            {
                "vertex_id": "effect-1",
                "channel": "email",
                "effect_class": "private_send",
                "dispatch_state": "blocked",
                "authority_ref": "capability://agent/email/outbound",
            }
        ],
        economy_profile={
            "root_did": "did:erc725:etzhayyim:260425:0x1",
            "erc8004_agent_id": "123",
            "economy_mode": "guarded-social",
            "status": "active",
        },
        email_outbound_rows=[{"status": "error", "provider": "resend"}],
        email_readiness={
            "ready": False,
            "blockers": ["resend_dkim_missing:etzhayyim.com"],
            "resendDomainStatuses": {"etzhayyim.com": "not_started"},
        },
        development_memory={
            "available": True,
            "latestDocuments": [
                {
                    "doc_id": "devdoc-20260507-artificial-organism-live-email",
                    "status": "active",
                    "topic": "artificial-organism-runtime",
                }
            ],
            "edgeCounts": [{"relation_kind": "evidenced_by_email", "ref_kind": "vertex", "edge_count": 1}],
            "statusCounts": [
                {
                    "topic": "artificial-organism-runtime",
                    "doc_type": "development-session-summary",
                    "status": "active",
                    "document_count": 1,
                }
            ],
        },
        policy_adaptation={
            "available": True,
            "proposalCounts": [{"state": "accepted", "count": 1}],
            "recentProposals": [
                {
                    "preference_key": "runtime.observability",
                    "proposal_state": "accepted",
                    "mokuteki_gate_pass": True,
                    "triple_witness_pass": True,
                }
            ],
            "activePriors": [{"preference_key": "runtime.observability", "weight": 1.05}],
        },
        effect_channels=[
            {"channel": "email", "state": "live"},
            {"channel": "fax", "state": "planned"},
        ],
        counterparty_minimax={
            "available": True,
            "counterparties": [{"counterparty_ref": "mailto:partner@example.com"}],
            "protectedAssets": [{"asset_ref": "asset://counterparty/reputation"}],
            "minimaxEvaluations": [{"action_id": "send-notice", "minimax_regret": 0.7}],
        },
        information_flow={
            "available": True,
            "nodes": [{"info_ref": "info://strategy", "abstraction_level": 7}],
            "height": [{"info_kind": "strategy", "max_information_height": 7}],
            "flows": [{"src_vid": "info://evidence", "avg_control_score": 0.7}],
        },
        knowledge_graph_fitness={
            "available": True,
            "kgDevelopmentGain": 1.0,
            "evolutionFitness": 1.0,
            "missingEdgePenalty": 0.0,
        },
        runtime_publication={
            "available": True,
            "verified": True,
            "runtimeReceipt": {"job_id": "0xreceipt"},
        },
    )

    assert report["organismState"] == "repairing"
    assert report["organismScore"] == 0.8
    assert report["latestOutcome"]["success"] is True
    assert report["learning"]["channelPriors"] == {"self-repair": 0.1}
    assert report["erc8004"]["configured"] is True
    assert report["erc8004"]["agentId"] == "123"
    assert report["runtimePublication"]["verified"] is True
    assert report["authority"]["policies"][0]["state"] == "active"
    assert report["authority"]["recentEffects"][0]["authority_ref"].startswith("capability://")
    assert report["liveChannels"]["email"]["readiness"]["ready"] is False
    assert report["developmentMemory"]["available"] is True
    assert report["developmentMemory"]["latestDocuments"][0]["topic"] == "artificial-organism-runtime"
    assert report["policyAdaptation"]["available"] is True
    assert report["policyAdaptation"]["proposalCounts"][0]["state"] == "accepted"
    assert report["effectChannels"][0]["state"] == "live"
    assert report["counterpartyMinimax"]["available"] is True
    assert report["counterpartyMinimax"]["minimaxEvaluations"][0]["minimax_regret"] == 0.7
    assert report["informationFlow"]["height"][0]["max_information_height"] == 7
    assert report["healthEvaluation"]["level"] == "watch"
    assert "email_not_ready" in report["healthEvaluation"]["warnings"]
    assert "latest_dispatch_failed" in report["healthEvaluation"]["warnings"]
    assert "inspect_resend_provider_error" in report["healthEvaluation"]["repairActions"]


def test_format_text_includes_process_status() -> None:
    text = agent_status_main.format_text(
        {
            "agentDid": "did:etzhayyim:agent:test",
            "organismState": "active",
            "organismScore": 0.95,
            "homeostasis": {"viabilityState": "normal", "confidence": 0.9, "entropy": 0.1},
            "latestOutcome": {"dispatchState": "observed", "success": True},
            "learning": {"updatedAt": "2026-05-07T00:00:00Z"},
            "erc8004": {"configured": True, "agentId": "123"},
            "runtimePublication": {"verified": True, "runtimeReceipt": {"job_id": "0xreceipt"}},
            "authority": {"policies": [{"state": "active"}], "recentEffects": [{"vertex_id": "effect-1"}]},
            "liveChannels": {"email": {"readiness": {"ready": False, "blockers": ["resend_domain_unverified"]}}},
            "developmentMemory": {
                "available": True,
                "latestDocuments": [{"doc_id": "devdoc-1"}],
                "edgeCounts": [{"relation_kind": "documents_design"}],
            },
            "policyAdaptation": {
                "available": True,
                "recentProposals": [{"preference_key": "runtime.observability"}],
                "activePriors": [{"preference_key": "runtime.observability"}],
            },
            "counterpartyMinimax": {
                "available": True,
                "counterparties": [{"counterparty_ref": "mailto:partner@example.com"}],
                "protectedAssets": [{"asset_ref": "asset://counterparty/reputation"}],
                "minimaxEvaluations": [{"action_id": "send-notice"}],
            },
            "informationFlow": {
                "available": True,
                "nodes": [{"info_ref": "info://strategy"}],
                "height": [{"info_kind": "strategy"}],
                "flows": [{"src_vid": "info://evidence"}],
            },
            "healthEvaluation": {
                "level": "watch",
                "warnings": ["email_not_ready"],
                "failures": [],
            },
            "effectChannels": [{"channel": "email", "state": "live"}, {"channel": "fax", "state": "planned"}],
            "processes": {"com.etzhayyim.agent-daemon": True, "com.etzhayyim.agent-zeebe-worker": False},
        }
    )

    assert "organism: active score=0.95" in text
    assert "health: watch warnings=1 failures=0" in text
    assert "erc8004: configured agentId=123" in text
    assert "runtimePublication: verified receipt=0xreceipt" in text
    assert "authority: policies=1 recentEffects=1" in text
    assert "emailLive: blocked blockers=resend_domain_unverified" in text
    assert "developmentMemory: available docs=1 edgeKinds=1" in text
    assert "policyAdaptation: available proposals=1 activePriors=1" in text
    assert "effectChannels: live=1 total=2" in text
    assert "counterpartyMinimax: available counterparties=1 protectedAssets=1 evaluations=1" in text
    assert "informationFlow: available nodes=1 flows=1" in text
    assert "com.etzhayyim.agent-daemon: running" in text
    assert "com.etzhayyim.agent-zeebe-worker: down" in text


def test_health_marks_historical_dispatch_failures_as_recovering_after_success() -> None:
    health = agent_status_main.evaluate_process_health(
        organism_state="active",
        organism_score=1.0,
        processes_ok=True,
        viability_state="normal",
        homeostasis_blockers=[],
        latest_observation={
            "homeostasis_metrics": {"source_kind": "homeostasis_metrics"},
            "dispatch_receipt": {
                "payload_json": json.dumps(
                    {
                        "channel": "email",
                        "error": "",
                        "provider": "resend",
                        "receiptRef": "msg_123",
                    }
                )
            },
        },
        knowledge_graph_fitness={
            "available": True,
            "kgDevelopmentGain": 1.0,
            "evolutionFitness": 1.0,
            "missingEdgePenalty": 0.0,
        },
        dispatch_counts=[{"state": "dispatch_failed", "count": 12}, {"state": "dispatched", "count": 2}],
        email_readiness={"ready": True},
    )

    assert health["level"] == "healthy"
    assert health["latestDispatchState"] == "dispatched"
    assert "dispatch_failures_exceed_successes" not in health["warnings"]
    assert health["repairActions"] == ["monitor_dispatch_trend_recovery"]


def test_load_effect_channel_status_marks_email_live_and_fax_planned() -> None:
    rows = agent_status_main.load_effect_channel_status({"ready": True})
    by_channel = {row["channel"]: row for row in rows}

    assert by_channel["email"]["state"] == "live"
    assert by_channel["fax"]["state"] == "planned"
    assert "channel_worker_not_live:fax" in by_channel["fax"]["blockers"]
    assert by_channel["print-mail"]["highRisk"] is True
