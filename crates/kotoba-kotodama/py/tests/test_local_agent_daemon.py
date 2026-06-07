from __future__ import annotations

import asyncio
import json
from datetime import datetime as real_datetime

from kotodama import agent_daemon_main
from kotodama.local_llm import (
    LocalLlmConfig,
    build_chat_request,
    extract_json_object,
    parse_chat_response,
)


def test_extract_json_object_accepts_plain_and_wrapped_json() -> None:
    assert extract_json_object('{"summary":"ok"}') == {"summary": "ok"}
    assert extract_json_object('prefix {"summary":"ok","observations":[]} suffix') == {
        "summary": "ok",
        "observations": [],
    }
    assert extract_json_object("not-json") == {"rawText": "not-json"}


def test_build_ollama_chat_request_is_non_streaming_json() -> None:
    config = LocalLlmConfig(model="qwen3:14b", num_predict=128)
    request = build_chat_request(config, [{"role": "user", "content": "hello"}])

    assert request["model"] == "qwen3:14b"
    assert request["stream"] is False
    assert request["format"] == "json"
    assert request["options"]["num_predict"] == 128


def test_parse_ollama_chat_response() -> None:
    config = LocalLlmConfig()

    assert parse_chat_response(config, {"message": {"content": '{"ok":true}'}}) == '{"ok":true}'
    assert parse_chat_response(config, {"response": '{"ok":true}'}) == '{"ok":true}'


def test_build_tick_variables_keeps_real_world_effects_as_proposals() -> None:
    result = agent_daemon_main.build_tick_variables(
        agent_did="did:etzhayyim:agent:test",
        llm_result={
            "provider": "ollama",
            "model": "local",
            "endpoint": "http://localhost",
            "content": '{"summary":"s"}',
            "json": {
                "summary": "s",
                "observations": [{"kind": "inbox"}],
                "candidateActions": [{"actionId": "ask"}],
                "realWorldEffectProposals": [
                    {"channel": "email", "payload": {"to": "a@example.com"}}
                ],
            },
        },
        viability={"viabilityState": "normal", "blockers": []},
        tick_id="tick-1",
    )

    assert result["agentDid"] == "did:etzhayyim:agent:test"
    assert result["tickId"] == "tick-1"
    assert result["mokutekiGatePass"] is True
    assert result["candidateActions"] == [{"actionId": "ask"}]
    assert result["realWorldEffectProposals"][0]["channel"] == "email"
    assert result["localLlm"]["rawHash"]


def test_build_effect_dispatch_variables_uses_policy_default_and_payload_target() -> None:
    result = agent_daemon_main.build_effect_dispatch_variables(
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-1",
        default_policy_ref="policy://agent/email-v1",
        proposal={
            "channel": "email",
            "effectClass": "private_send",
            "payload": {"to": "ops@example.com", "subject": "Ping", "text": "hello"},
            "autonomousAuthorityRef": "capability://agent/email/outbound",
        },
    )

    assert result["agentDid"] == "did:etzhayyim:agent:test"
    assert result["actionProposalId"] == "tick-1"
    assert result["targetRef"] == "ops@example.com"
    assert result["policyRef"] == "policy://agent/email-v1"
    assert result["autonomousAuthorityRef"] == "capability://agent/email/outbound"


def test_build_homeostasis_variables_uses_viability_normalized_values() -> None:
    result = agent_daemon_main.build_homeostasis_variables(
        "did:etzhayyim:agent:test",
        {
            "viabilityState": "normal",
            "normalized": {
                "computeBudgetRemaining": 0.8,
                "storagePressure": 0.2,
                "leaseSecondsRemaining": 120,
                "errorRate1h": 0.1,
                "toolSuccessRate1h": 0.95,
                "energyOrCostProxy": 0.3,
            },
        },
    )

    assert result == {
        "agentDid": "did:etzhayyim:agent:test",
        "computeBudgetRemaining": 0.8,
        "storagePressure": 0.2,
        "leaseSecondsRemaining": 120,
        "errorRate1h": 0.1,
        "toolSuccessRate1h": 0.95,
        "energyOrCostProxy": 0.3,
    }


def test_build_homeostasis_observation_variables_carries_metrics_and_controls() -> None:
    result = agent_daemon_main.build_homeostasis_observation_variables(
        "did:etzhayyim:agent:test",
        {"viabilityState": "normal"},
        {"source": "measured", "errorRate1h": 0.0},
        {"effectDispatchAllowed": True},
    )

    assert result["agentDid"] == "did:etzhayyim:agent:test"
    assert result["viability"] == {"viabilityState": "normal"}
    assert result["homeostasisMetrics"]["source"] == "measured"
    assert result["homeostasisControls"]["effectDispatchAllowed"] is True
    assert result["observedAt"]


def test_build_homeostasis_belief_row_derives_runtime_health_posterior() -> None:
    result = agent_daemon_main.build_homeostasis_belief_row(
        agent_did="did:etzhayyim:agent:test",
        viability={
            "viabilityState": "normal",
            "blockers": [],
            "nextActions": ["continue_active_inference_tick"],
        },
        metrics={
            "source": "measured",
            "errorRate1h": 0.2,
            "toolSuccessRate1h": 0.75,
            "launchd": {"com.etzhayyim.agent-daemon": True},
            "ollama": {"ok": True, "status": 200},
        },
        controls={"effectDispatchAllowed": True},
        observation_vertex_id="agent-observation-homeostasis-123",
        observed_at="2026-05-07T00:00:00Z",
    )

    state_value = json.loads(result["state_value_json"])
    assert result["vertex_id"].startswith("agent-belief-runtime-health-")
    assert result["belief_kind"] == "runtime.homeostasis"
    assert result["state_key"] == "local-agent-daemon.health"
    assert result["posterior_confidence"] == 0.75
    assert result["posterior_entropy"] == 0.2
    assert result["updated_from_observation"] == "agent-observation-homeostasis-123"
    assert state_value["viabilityState"] == "normal"
    assert state_value["launchd"]["com.etzhayyim.agent-daemon"] is True
    assert state_value["ollama"]["status"] == 200


def test_derive_policy_from_homeostasis_belief_allows_confident_low_entropy_state() -> None:
    result = agent_daemon_main.derive_policy_from_homeostasis_belief(
        belief={
            "posteriorConfidence": 0.95,
            "posteriorEntropy": 0.05,
            "stateKey": "local-agent-daemon.health",
        },
        controls={"effectDispatchAllowed": True, "cadenceMultiplier": 1.0},
    )

    assert result["policyVersion"] == "belief-gated-v1"
    assert result["policyReasons"] == []
    assert result["effectiveControls"]["effectDispatchAllowed"] is True
    assert result["effectiveControls"]["cadenceMultiplier"] == 1.0


def test_derive_policy_from_homeostasis_belief_suppresses_low_confidence_state() -> None:
    result = agent_daemon_main.derive_policy_from_homeostasis_belief(
        belief={
            "posteriorConfidence": 0.4,
            "posteriorEntropy": 0.1,
            "stateKey": "local-agent-daemon.health",
        },
        controls={"effectDispatchAllowed": True, "cadenceMultiplier": 1.0},
    )

    assert result["policyReasons"] == ["belief:low_confidence"]
    assert result["effectiveControls"]["effectDispatchAllowed"] is False
    assert result["effectiveControls"]["effectDispatchSuppressedReason"] == "belief:low_confidence"
    assert result["effectiveControls"]["cadenceMultiplier"] == 2.0


def test_derive_policy_from_homeostasis_belief_suppresses_missing_belief() -> None:
    result = agent_daemon_main.derive_policy_from_homeostasis_belief(
        belief=None,
        controls={"effectDispatchAllowed": True, "cadenceMultiplier": 1.0},
    )

    assert result["policyReasons"] == ["belief:missing"]
    assert result["effectiveControls"]["effectDispatchAllowed"] is False


def test_select_real_world_action_proposals_accepts_best_policy_compliant_action() -> None:
    def load_policy(**kwargs):
        return {
            "authorityRef": kwargs["authority_ref"],
            "policyRef": kwargs["policy_ref"],
            "allowedChannels": ["email"],
            "allowedEffectClasses": ["private_send"],
            "allowedRecipientDomains": ["example.com"],
            "signatureRef": "sig://authority/test",
            "status": "active",
        }

    result = agent_daemon_main.select_real_world_action_proposals(
        proposals=[
            {
                "channel": "email",
                "payload": {"to": "ops@example.com", "subject": "Low", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "priority": 0.1,
            },
            {
                "channel": "email",
                "payload": {"to": "lead@example.com", "subject": "High", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "priority": 0.9,
            },
        ],
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-1",
        runtime_policy={"effectiveControls": {"effectDispatchAllowed": True}},
        max_dispatches=1,
        authority_policy_loader=load_policy,
    )

    assert result["selectedCount"] == 1
    assert result["selectedProposals"][0]["payload"]["to"] == "lead@example.com"
    assert result["decisions"][0]["blockers"] == ["action_selection:max_dispatches"]
    assert result["decisions"][1]["accepted"] is True


def test_select_real_world_action_proposals_blocks_runtime_policy_suppression() -> None:
    result = agent_daemon_main.select_real_world_action_proposals(
        proposals=[
            {
                "channel": "email",
                "payload": {"to": "ops@example.com", "subject": "Ping", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
            }
        ],
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-1",
        runtime_policy={
            "policyReasons": ["belief:low_confidence"],
            "effectiveControls": {"effectDispatchAllowed": False},
        },
    )

    assert result["selectedCount"] == 0
    assert result["decisions"][0]["accepted"] is False
    assert result["decisions"][0]["blockers"] == ["runtime_policy:belief:low_confidence"]


def test_select_real_world_action_proposals_blocks_missing_db_authority_policy() -> None:
    result = agent_daemon_main.select_real_world_action_proposals(
        proposals=[
            {
                "channel": "email",
                "payload": {"to": "ops@example.com", "subject": "Ping", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
            }
        ],
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-1",
        runtime_policy={"effectiveControls": {"effectDispatchAllowed": True}},
        authority_policy_loader=lambda **_kwargs: {},
    )

    assert result["selectedCount"] == 0
    assert "authority_policy_missing" in result["decisions"][0]["blockers"]


def test_select_real_world_action_proposals_applies_inline_policy() -> None:
    result = agent_daemon_main.select_real_world_action_proposals(
        proposals=[
            {
                "channel": "email",
                "payload": {"to": "ops@blocked.example", "subject": "Ping", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "policy": {
                    "authorityRef": "capability://agent/email/outbound",
                    "policyRef": "policy://agent/email-v1",
                    "allowedChannels": ["email"],
                    "allowedEffectClasses": ["private_send"],
                    "allowedRecipientDomains": ["example.com"],
                    "signatureRef": "sig://authority/test",
                },
            }
        ],
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-1",
        runtime_policy={"effectiveControls": {"effectDispatchAllowed": True}},
    )

    assert result["selectedCount"] == 0
    assert "policy_recipient_domain_denied:blocked.example" in result["decisions"][0]["blockers"]


def test_select_real_world_action_proposals_applies_learning_prior() -> None:
    def load_policy(**kwargs):
        return {
            "authorityRef": kwargs["authority_ref"],
            "policyRef": kwargs["policy_ref"],
            "allowedChannels": ["email"],
            "allowedEffectClasses": ["private_send"],
            "allowedRecipientDomains": ["example.com"],
            "signatureRef": "sig://authority/test",
            "status": "active",
        }

    result = agent_daemon_main.select_real_world_action_proposals(
        proposals=[
            {
                "channel": "email",
                "payload": {"to": "low@example.com", "subject": "Low", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-low-v1",
                "priority": 0.5,
            },
            {
                "channel": "email",
                "payload": {"to": "high@example.com", "subject": "High", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-high-v1",
                "priority": 0.4,
            },
        ],
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-1",
        runtime_policy={"effectiveControls": {"effectDispatchAllowed": True}},
        learning_belief={
            "stateValue": {
                "policyPriors": {
                    "policy://agent/email-low-v1": -0.2,
                    "policy://agent/email-high-v1": 0.2,
                }
            }
        },
        max_dispatches=1,
        authority_policy_loader=load_policy,
    )

    assert result["selectedCount"] == 1
    assert result["selectedProposals"][0]["policyRef"] == "policy://agent/email-high-v1"
    assert result["decisions"][1]["learningPrior"] == 0.2


def test_build_learning_belief_row_updates_policy_and_channel_priors() -> None:
    result = agent_daemon_main.build_learning_belief_row(
        agent_did="did:etzhayyim:agent:test",
        outcome_observation={
            "vertex_id": "obs-1",
            "observed_at": "2026-05-07T00:00:00Z",
        },
        dispatch_plan={
            "channel": "email",
            "policyRef": "policy://agent/email-v1",
        },
        dispatch_state="blocked",
        previous_learning_belief={
            "stateValue": {
                "channelPriors": {"email": 0.1},
                "policyPriors": {"policy://agent/email-v1": 0.1},
                "channelCounts": {"email": 2},
                "policyCounts": {"policy://agent/email-v1": 2},
            }
        },
    )

    state_value = json.loads(result["state_value_json"])
    assert result["belief_kind"] == "runtime.learning"
    assert result["state_key"] == "local-agent-daemon.learning"
    assert result["updated_from_observation"] == "obs-1"
    assert state_value["channelPriors"]["email"] == 0.0
    assert state_value["policyPriors"]["policy://agent/email-v1"] == 0.0
    assert state_value["channelCounts"]["email"] == 3
    assert state_value["lastOutcome"]["success"] is False


def test_execute_real_world_action_direct_records_blocked_plan_without_send(monkeypatch) -> None:
    rows: list[tuple[str, dict]] = []

    def fake_insert(table: str, row: dict) -> None:
        rows.append((table, row))

    def fail_send_email(**kwargs):  # pragma: no cover - must not be called
        raise AssertionError("blocked direct execution must not send")

    monkeypatch.setattr(agent_daemon_main, "insert_direct_row", fake_insert)
    monkeypatch.setattr("kotodama.ingest.mailer.send_email", fail_send_email)

    result = agent_daemon_main.execute_real_world_action_direct(
        {
            "agentDid": "did:etzhayyim:agent:test",
            "actionProposalId": "proposal-1",
            "channel": "email",
            "effectClass": "private_send",
            "targetRef": "ops@blocked.example",
            "summary": "Blocked",
            "payload": {"to": "ops@blocked.example", "subject": "Blocked", "text": "hello"},
            "autonomousAuthorityRef": "capability://agent/email/outbound",
            "policyRef": "policy://agent/email-v1",
            "policy": {"allowedRecipientDomains": ["example.com"]},
        }
    )

    assert result["dispatchPlan"]["dispatchAllowed"] is False
    assert result["receipt"]["dispatchState"] == "blocked"
    assert result["outcomeBelief"]["stateKey"] == "local-agent-daemon.outcomes"
    assert [table for table, _row in rows] == [
        "vertex_agent_belief_state",
        "vertex_agent_belief_state",
        "vertex_agent_realworld_effect",
        "vertex_agent_dispatch_ledger",
    ]
    assert rows[0][1]["belief_kind"] == "runtime.outcome"
    assert rows[1][1]["belief_kind"] == "runtime.learning"
    assert rows[-1][1]["dispatch_state"] == "blocked"


def test_execute_real_world_action_direct_records_email_receipt_observation(monkeypatch) -> None:
    rows: list[tuple[str, dict]] = []

    def fake_insert(table: str, row: dict) -> None:
        rows.append((table, row))

    def fake_send_email(**kwargs):
        return {"messageId": "msg_123", "provider": "fake", "sentAt": "2026-05-07T00:00:00Z"}

    monkeypatch.setattr(agent_daemon_main, "insert_direct_row", fake_insert)
    monkeypatch.setattr("kotodama.ingest.mailer.send_email", fake_send_email)

    result = agent_daemon_main.execute_real_world_action_direct(
        {
            "agentDid": "did:etzhayyim:agent:test",
            "actionProposalId": "proposal-1",
            "channel": "email",
            "effectClass": "private_send",
            "targetRef": "ops@example.com",
            "summary": "Allowed",
            "payload": {"to": "ops@example.com", "subject": "Allowed", "text": "hello"},
            "autonomousAuthorityRef": "capability://agent/email/outbound",
            "policyRef": "policy://agent/email-v1",
            "policy": {
                "authorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "allowedChannels": ["email"],
                "allowedEffectClasses": ["private_send"],
                "allowedRecipientDomains": ["example.com"],
                "signatureRef": "sig://authority/test",
            },
        }
    )

    assert result["dispatchPlan"]["dispatchAllowed"] is True
    assert result["receipt"]["dispatchState"] == "dispatched"
    assert result["receipt"]["receiptRef"] == "msg_123"
    assert result["outcomeBelief"]["stateKey"] == "local-agent-daemon.outcomes"
    assert [table for table, _row in rows] == [
        "vertex_agent_observation",
        "vertex_agent_belief_state",
        "vertex_agent_belief_state",
        "vertex_agent_realworld_effect",
        "vertex_agent_dispatch_ledger",
    ]
    assert rows[0][1]["source_kind"] == "dispatch_receipt"
    assert rows[1][1]["belief_kind"] == "runtime.outcome"
    assert json.loads(rows[1][1]["state_value_json"])["receiptRef"] == "msg_123"
    assert rows[2][1]["belief_kind"] == "runtime.learning"
    assert rows[3][1]["dispatch_state"] == "dispatched"
    assert rows[4][1]["dispatch_state"] == "dispatched"


def test_execute_real_world_action_direct_blocks_unready_email_live_channel(monkeypatch) -> None:
    rows: list[tuple[str, dict]] = []

    def fake_insert(table: str, row: dict) -> None:
        rows.append((table, row))

    def fail_send_email(**kwargs):  # pragma: no cover - must not be called
        raise AssertionError("unready email live channel must not send")

    monkeypatch.setattr(agent_daemon_main, "insert_direct_row", fake_insert)
    monkeypatch.setattr(agent_daemon_main, "load_email_live_channel_blockers_direct", lambda: ["resend_domain_or_sender_unverified"])
    monkeypatch.setattr("kotodama.ingest.mailer.send_email", fail_send_email)

    result = agent_daemon_main.execute_real_world_action_direct(
        {
            "agentDid": "did:etzhayyim:agent:test",
            "actionProposalId": "proposal-1",
            "channel": "email",
            "effectClass": "private_send",
            "targetRef": "ops@example.com",
            "summary": "Allowed but channel blocked",
            "payload": {"to": "ops@example.com", "subject": "Allowed", "text": "hello"},
            "autonomousAuthorityRef": "capability://agent/email/outbound",
            "policyRef": "policy://agent/email-v1",
            "policy": {
                "authorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "allowedChannels": ["email"],
                "allowedEffectClasses": ["private_send"],
                "allowedRecipientDomains": ["example.com"],
                "signatureRef": "sig://authority/test",
            },
        }
    )

    assert result["dispatchPlan"]["dispatchAllowed"] is False
    assert "resend_domain_or_sender_unverified" in result["dispatchPlan"]["blockers"]
    assert result["receipt"]["dispatchState"] == "blocked"
    assert rows[-1][0] == "vertex_agent_dispatch_ledger"
    assert rows[-1][1]["dispatch_state"] == "blocked"


def test_resend_dns_ready_checks_apex_resend_records(monkeypatch) -> None:
    def fake_dns(record_type: str, name: str) -> list[str]:
        records = {
            ("TXT", "resend._domainkey.etzhayyim.com"): ["p=abc"],
            ("TXT", "send.etzhayyim.com"): ["v=spf1 include:amazonses.com ~all"],
            ("MX", "send.etzhayyim.com"): ["10 feedback-smtp.ap-northeast-1.amazonses.com."],
        }
        return records.get((record_type, name), [])

    monkeypatch.setattr(agent_daemon_main, "_dns_short", fake_dns)

    assert agent_daemon_main.resend_dns_ready("etzhayyim.com") is True


def test_email_live_channel_blocker_distinguishes_resend_account_pending(monkeypatch) -> None:
    class FakeCursor:
        description = []
        calls = 0

        def execute(self, *_args):
            return None

        def fetchone(self):
            self.calls += 1
            if self.calls == 1:
                return ["error", '{"message":"The etzhayyim.com domain is not verified."}']
            return None

    class FakeSyncCursor:
        def __enter__(self):
            return FakeCursor()

        def __exit__(self, *_args):
            return False

    monkeypatch.setenv("RW_URL", "postgres://test")
    monkeypatch.setattr("kotodama.db_sync.sync_cursor", lambda: FakeSyncCursor())
    monkeypatch.setattr(agent_daemon_main, "resend_dns_ready", lambda domain: True)
    monkeypatch.setattr(agent_daemon_main, "resend_domain_verified", lambda domain: False)

    assert sorted(agent_daemon_main.load_email_live_channel_blockers_direct()) == [
        "email_live_channel_not_ready",
        "resend_account_domain_verification_pending",
    ]


def test_email_live_channel_blocker_detects_recent_resend_rate_limit(monkeypatch) -> None:
    class FakeCursor:
        description = []
        calls = 0

        def execute(self, *_args):
            return None

        def fetchone(self):
            self.calls += 1
            if self.calls == 1:
                return ["error", '{"message":"rate_limit_exceeded"}']
            return [
                "error",
                '{"statusCode":429,"name":"rate_limit_exceeded","message":"Too many requests"}',
            ]

    class FakeSyncCursor:
        def __enter__(self):
            return FakeCursor()

        def __exit__(self, *_args):
            return False

    monkeypatch.setenv("RW_URL", "postgres://test")
    monkeypatch.setenv("AGENT_EMAIL_MIN_SEND_INTERVAL_SEC", "300")
    monkeypatch.setattr("kotodama.db_sync.sync_cursor", lambda: FakeSyncCursor())

    assert sorted(agent_daemon_main.load_email_live_channel_blockers_direct()) == [
        "resend_min_send_interval_active",
        "resend_rate_limited",
    ]


def test_collect_local_homeostasis_metrics_maps_probe_failures(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "agent.err.log"
    log_path.write_text(
        "2026-05-07 07:00:00,000 INFO ok\n"
        "2026-05-07 07:10:00,000 ERROR broken\n"
        "Traceback here\n"
        "2026-05-07 05:00:00,000 ERROR stale\n"
        "Traceback stale\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        agent_daemon_main,
        "launchd_label_running",
        lambda label: label == "com.etzhayyim.agent-daemon",
    )
    monkeypatch.setattr(
        agent_daemon_main,
        "probe_ollama_endpoint",
        lambda endpoint: {"ok": False, "reason": "down"},
    )
    monkeypatch.setattr(
        agent_daemon_main,
        "datetime",
        type(
            "FakeDateTime",
            (),
            {
                "now": staticmethod(lambda tz=None: real_datetime(2026, 5, 7, 7, 30, tzinfo=tz)),
                "strptime": staticmethod(real_datetime.strptime),
            },
        ),
    )

    result = agent_daemon_main.collect_local_homeostasis_metrics(
        llm_endpoint="http://127.0.0.1:11434/api/chat",
        launchd_labels=("com.etzhayyim.agent-daemon", "com.etzhayyim.agent-zeebe-worker"),
        log_paths=(str(log_path),),
    )

    assert result["source"] == "measured"
    assert result["launchd"]["com.etzhayyim.agent-daemon"] is True
    assert result["launchd"]["com.etzhayyim.agent-zeebe-worker"] is False
    assert result["ollama"]["ok"] is False
    assert result["logFailures"] == 2
    assert result["logFailureWindowSec"] == 3600
    assert result["errorRate1h"] > 0
    assert result["toolSuccessRate1h"] < 1


def test_build_viability_inputs_uses_measured_metrics(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_HOMEOSTASIS_MEASURED", "1")
    monkeypatch.setattr(
        agent_daemon_main,
        "collect_local_homeostasis_metrics",
        lambda llm_endpoint: {
            "source": "measured",
            "errorRate1h": 0.42,
            "toolSuccessRate1h": 0.58,
        },
    )

    result = agent_daemon_main.build_viability_inputs(LocalLlmConfig(endpoint="http://local"))

    assert result["error_rate_1h"] == 0.42
    assert result["tool_success_rate_1h"] == 0.58
    assert result["metrics"]["source"] == "measured"


def test_harden_runtime_viability_repairs_before_lease_exhaustion() -> None:
    result = agent_daemon_main.harden_runtime_viability(
        {
            "viabilityState": "conserve",
            "blockers": ["resource_floor_near"],
            "nextActions": ["slow_cadence"],
            "normalized": {"leaseSecondsRemaining": 1200},
        },
        metrics={"source": "measured"},
        lease_repair_floor_sec=1800,
        lease_hibernate_floor_sec=300,
    )

    assert result["viabilityState"] == "repair"
    assert "runtime_lease_renewal_due" in result["blockers"]
    assert "renew_runtime_lease" in result["nextActions"]
    assert result["maintenanceReasons"] == ["maintenance:lease_renewal_due"]


def test_harden_runtime_viability_hibernates_critical_lease() -> None:
    result = agent_daemon_main.harden_runtime_viability(
        {
            "viabilityState": "conserve",
            "blockers": ["resource_floor_near"],
            "nextActions": ["slow_cadence"],
            "normalized": {"leaseSecondsRemaining": 120},
        },
        metrics={"source": "measured"},
        lease_repair_floor_sec=1800,
        lease_hibernate_floor_sec=300,
    )

    assert result["viabilityState"] == "hibernate"
    assert "runtime_lease_critical" in result["blockers"]
    assert "renew_or_hibernate_runtime_lease" in result["nextActions"]


def test_harden_runtime_viability_repairs_local_service_degraded() -> None:
    result = agent_daemon_main.harden_runtime_viability(
        {
            "viabilityState": "normal",
            "blockers": [],
            "nextActions": ["continue_active_inference_tick"],
            "normalized": {"leaseSecondsRemaining": 3600},
        },
        metrics={
            "launchd": {"com.etzhayyim.agent-daemon": True, "com.etzhayyim.agent-zeebe-worker": False},
            "ollama": {"ok": True},
        },
    )

    assert result["viabilityState"] == "repair"
    assert "local_service_degraded" in result["blockers"]
    assert "restart_degraded_services" in result["nextActions"]
    assert result["failedLaunchdServices"] == ["com.etzhayyim.agent-zeebe-worker"]


def test_load_homeostasis_belief_direct_returns_none_when_store_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RW_URL", "postgres://test")

    def boom():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("kotodama.db_sync.sync_cursor", boom)

    assert agent_daemon_main.load_homeostasis_belief_direct("did:etzhayyim:agent:test") is None


def test_load_learning_belief_direct_returns_none_when_store_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RW_URL", "postgres://test")

    def boom():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("kotodama.db_sync.sync_cursor", boom)

    assert agent_daemon_main.load_learning_belief_direct("did:etzhayyim:agent:test") is None


def test_derive_homeostasis_controls_normal_allows_dispatch() -> None:
    result = agent_daemon_main.derive_homeostasis_controls({"viabilityState": "normal"})

    assert result["cadenceMultiplier"] == 1.0
    assert result["effectDispatchAllowed"] is True
    assert result["effectDispatchSuppressedReason"] == ""
    assert result["selfRepairRequired"] is False


def test_derive_homeostasis_controls_repair_pauses_dispatch_and_slows_cadence() -> None:
    result = agent_daemon_main.derive_homeostasis_controls({"viabilityState": "repair"})

    assert result["cadenceMultiplier"] == 2.0
    assert result["effectDispatchAllowed"] is False
    assert result["effectDispatchSuppressedReason"] == "homeostasis:repair"
    assert result["selfRepairRequired"] is True


def test_build_self_repair_variables_carries_viability_context() -> None:
    result = agent_daemon_main.build_self_repair_variables(
        "did:etzhayyim:agent:test",
        {
            "viabilityState": "repair",
            "blockers": ["tool_health_degraded"],
            "nextActions": ["run_health_checks"],
            "normalized": {"errorRate1h": 0.5},
        },
    )

    assert result["agentDid"] == "did:etzhayyim:agent:test"
    assert result["triggerKind"] == "homeostasis_viability"
    assert result["viabilityState"] == "repair"
    assert result["viabilityBlockers"] == ["tool_health_degraded"]
    assert result["viabilityNextActions"] == ["run_health_checks"]
    assert result["homeostasisNormalized"] == {"errorRate1h": 0.5}
    assert result["failedLaunchdServices"] == []
    assert result["ollamaRepairNeeded"] is False
    assert result["repairReason"] == "homeostasis:repair"


def test_execute_local_self_repair_restarts_failed_non_daemon_services(monkeypatch) -> None:
    calls: list[str] = []

    def fake_kickstart(label: str):
        calls.append(label)
        return {"ok": True, "label": label}

    monkeypatch.setattr(agent_daemon_main, "launchd_kickstart_label", fake_kickstart)

    result = agent_daemon_main.execute_local_self_repair(
        {
            "nextActions": ["restart_degraded_services"],
            "failedLaunchdServices": [
                "com.etzhayyim.agent-daemon",
                "com.etzhayyim.agent-zeebe-worker",
            ],
        },
        current_label="com.etzhayyim.agent-daemon",
    )

    assert calls == ["com.etzhayyim.agent-zeebe-worker"]
    assert result["attempted"] == [{"ok": True, "label": "com.etzhayyim.agent-zeebe-worker"}]
    assert result["skipped"] == [
        {"label": "com.etzhayyim.agent-daemon", "reason": "current_daemon_not_self_restarted"}
    ]
    assert result["ok"] is True


def test_build_self_repair_observation_row_records_local_repair_payload() -> None:
    row = agent_daemon_main.build_self_repair_observation_row(
        agent_did="did:etzhayyim:agent:test",
        variables={"repairReason": "homeostasis:repair"},
        local_repair={
            "ok": True,
            "attempted": [{"ok": True, "label": "com.etzhayyim.agent-zeebe-worker"}],
            "skipped": [],
        },
        process_instance_key="repair-123",
        observed_at="2026-05-07T00:00:00Z",
    )
    payload = json.loads(row["payload_json"])

    assert row["source_kind"] == "self_repair_receipt"
    assert row["source_ref"] == "repair-123"
    assert row["confidence"] == 0.9
    assert payload["localRepair"]["attempted"][0]["label"] == "com.etzhayyim.agent-zeebe-worker"


def test_record_self_repair_outcome_direct_updates_outcome_and_learning(monkeypatch) -> None:
    inserted: list[tuple[str, dict]] = []

    monkeypatch.setenv("RW_URL", "postgres://test")
    monkeypatch.setattr(
        agent_daemon_main,
        "insert_direct_row",
        lambda table, row: inserted.append((table, row)),
    )
    monkeypatch.setattr(
        agent_daemon_main,
        "record_outcome_belief_direct",
        lambda **kwargs: {"updated": 1, "dispatchState": kwargs["dispatch_state"]},
    )
    monkeypatch.setattr(
        agent_daemon_main,
        "record_learning_belief_direct",
        lambda **kwargs: {"updated": 1, "dispatchState": kwargs["dispatch_state"]},
    )

    result = agent_daemon_main.record_self_repair_outcome_direct(
        agent_did="did:etzhayyim:agent:test",
        variables={"repairReason": "homeostasis:repair"},
        local_repair={"ok": True, "attempted": [{"ok": True, "label": "worker"}]},
        process_instance_key="repair-123",
    )

    assert result is not None
    assert inserted[0][0] == "vertex_agent_observation"
    assert result["dispatchState"] == "observed"
    assert result["outcomeBelief"] == {"updated": 1, "dispatchState": "observed"}
    assert result["learningBelief"] == {"updated": 1, "dispatchState": "observed"}


def test_run_self_repair_if_needed_skips_normal_state(monkeypatch) -> None:
    async def fail_run_process(*args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("self-repair must not start for normal viability")

    monkeypatch.setattr(agent_daemon_main, "_run_process_async", fail_run_process)

    result = asyncio.run(
        agent_daemon_main.run_self_repair_if_needed(
            agent_did="did:etzhayyim:agent:test",
            viability={"viabilityState": "normal"},
            mode="zeebe",
            enabled=True,
            process_id="agent_runtime_lease_autopilot",
        )
    )

    assert result is None


def test_run_self_repair_if_needed_starts_zeebe_for_repair(monkeypatch) -> None:
    started: list[tuple[str, dict]] = []

    async def fake_run_process(process_id: str, variables: dict):
        started.append((process_id, variables))
        return "repair-123"

    monkeypatch.setattr(agent_daemon_main, "_run_process_async", fake_run_process)
    monkeypatch.setattr(
        agent_daemon_main,
        "execute_local_self_repair",
        lambda viability, enabled=True: {"enabled": enabled, "attempted": []},
    )
    monkeypatch.setattr(
        agent_daemon_main,
        "record_self_repair_outcome_direct",
        lambda **kwargs: {"inserted": 1, "dispatchState": "observed"},
    )

    result = asyncio.run(
        agent_daemon_main.run_self_repair_if_needed(
            agent_did="did:etzhayyim:agent:test",
            viability={"viabilityState": "repair", "blockers": ["tool_health_degraded"]},
            mode="zeebe",
            enabled=True,
            process_id="agent_runtime_lease_autopilot",
        )
    )

    assert result is not None
    assert result["processInstanceKey"] == "repair-123"
    assert started[0][0] == "agent_runtime_lease_autopilot"
    assert started[0][1]["repairReason"] == "homeostasis:repair"
    assert result["localRepair"] == {"enabled": True, "attempted": []}
    assert result["outcomeObservation"] == {"inserted": 1, "dispatchState": "observed"}


def test_run_autonomous_effect_dispatches_blocks_missing_authority(monkeypatch) -> None:
    async def fail_run_process(*args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("zeebe must not start without authority")

    monkeypatch.setattr(agent_daemon_main, "_run_process_async", fail_run_process)

    result = asyncio.run(
        agent_daemon_main.run_autonomous_effect_dispatches(
            proposals=[
                {
                    "channel": "email",
                    "payload": {"to": "ops@example.com", "subject": "Ping", "text": "hello"},
                }
            ],
            agent_did="did:etzhayyim:agent:test",
            tick_id="tick-1",
            mode="zeebe",
            enabled=True,
            process_id="agent_realworld_autonomous_dispatch",
            default_policy_ref="policy://agent/email-v1",
        )
    )

    assert result[0]["processInstanceKey"] is None
    assert result[0]["error"] == "autonomous_authority_and_policy_required"


def test_run_autonomous_effect_dispatches_starts_zeebe_when_enabled(monkeypatch) -> None:
    started: list[tuple[str, dict]] = []

    async def fake_run_process(process_id: str, variables: dict):
        started.append((process_id, variables))
        return "12345"

    monkeypatch.setattr(agent_daemon_main, "_run_process_async", fake_run_process)

    result = asyncio.run(
        agent_daemon_main.run_autonomous_effect_dispatches(
            proposals=[
                {
                    "channel": "email",
                    "payload": {"to": "ops@example.com", "subject": "Ping", "text": "hello"},
                    "autonomousAuthorityRef": "capability://agent/email/outbound",
                    "policyRef": "policy://agent/email-v1",
                }
            ],
            agent_did="did:etzhayyim:agent:test",
            tick_id="tick-1",
            mode="zeebe",
            enabled=True,
            process_id="agent_realworld_autonomous_dispatch",
        )
    )

    assert result[0]["processInstanceKey"] == "12345"
    assert started[0][0] == "agent_realworld_autonomous_dispatch"
    assert started[0][1]["autonomousAuthorityRef"] == "capability://agent/email/outbound"


def test_run_autonomous_effect_dispatches_suppresses_duplicates(monkeypatch) -> None:
    started: list[tuple[str, dict]] = []

    async def fake_run_process(process_id: str, variables: dict):
        started.append((process_id, variables))
        return "12345"

    monkeypatch.setattr(agent_daemon_main, "_run_process_async", fake_run_process)
    proposal = {
        "channel": "email",
        "payload": {"to": "ops@example.com", "subject": "Ping", "text": "hello"},
        "autonomousAuthorityRef": "capability://agent/email/outbound",
        "policyRef": "policy://agent/email-v1",
    }

    result = asyncio.run(
        agent_daemon_main.run_autonomous_effect_dispatches(
            proposals=[proposal, proposal],
            agent_did="did:etzhayyim:agent:test",
            tick_id="tick-1",
            mode="zeebe",
            enabled=True,
            process_id="agent_realworld_autonomous_dispatch",
            seen_dispatch_keys=set(),
        )
    )

    assert len(started) == 1
    assert result[0]["processInstanceKey"] == "12345"
    assert result[1]["error"] == "duplicate_dispatch_suppressed"


def test_run_one_tick_dry_run_does_not_start_zeebe(monkeypatch) -> None:
    async def fake_chat_json(*, messages, config):
        assert messages[0]["role"] == "system"
        return {
            "provider": "ollama",
            "model": config.model,
            "endpoint": config.endpoint,
            "content": '{"summary":"tick","candidateActions":[]}',
            "json": {"summary": "tick", "candidateActions": []},
        }

    async def fail_run_process(*args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("zeebe must not start in dry-run")

    monkeypatch.setattr(agent_daemon_main, "chat_json", fake_chat_json)
    monkeypatch.setattr(agent_daemon_main, "_run_process_async", fail_run_process)

    result = asyncio.run(
        agent_daemon_main.run_one_tick(
            agent_did="did:etzhayyim:agent:test",
            process_id="agent_active_inference_tick",
            mode="dry-run",
            llm_config=LocalLlmConfig(model="local"),
        )
    )

    assert result["processInstanceKey"] is None
    assert result["variables"]["localLlm"]["summary"] == "tick"
    assert result["autonomousDispatches"] == []


def test_run_one_tick_dispatches_only_selected_real_world_effects(monkeypatch) -> None:
    async def fake_chat_json(*, messages, config):
        assert messages[0]["role"] == "system"
        return {
            "provider": "ollama",
            "model": config.model,
            "endpoint": config.endpoint,
            "content": '{"summary":"effects","realWorldEffectProposals":[]}',
            "json": {
                "summary": "effects",
                "realWorldEffectProposals": [
                    {
                        "channel": "email",
                        "payload": {"to": "bad@example.com", "subject": "Bad", "text": "hello"},
                    },
                    {
                        "channel": "email",
                        "payload": {"to": "ok@example.com", "subject": "Ok", "text": "hello"},
                        "autonomousAuthorityRef": "capability://agent/email/outbound",
                        "policyRef": "policy://agent/email-v1",
                        "priority": 1.0,
                    },
                ],
            },
        }

    async def fail_run_process(*args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("dry-run action selection test must not start zeebe")

    def load_policy(**kwargs):
        return {
            "authorityRef": kwargs["authority_ref"],
            "policyRef": kwargs["policy_ref"],
            "allowedChannels": ["email"],
            "allowedEffectClasses": ["private_send"],
            "allowedRecipientDomains": ["example.com"],
            "signatureRef": "sig://authority/test",
            "status": "active",
        }

    monkeypatch.setenv("AGENT_HOMEOSTASIS_MEASURED", "0")
    monkeypatch.setattr(agent_daemon_main, "chat_json", fake_chat_json)
    monkeypatch.setattr(agent_daemon_main, "_run_process_async", fail_run_process)
    monkeypatch.setattr(
        "kotodama.agent_authority_policy.load_delegated_authority_policy",
        load_policy,
    )

    result = asyncio.run(
        agent_daemon_main.run_one_tick(
            agent_did="did:etzhayyim:agent:test",
            process_id="agent_active_inference_tick",
            mode="dry-run",
            llm_config=LocalLlmConfig(model="local"),
            autonomous_effects_enabled=True,
            policy_from_belief_enabled=False,
        )
    )

    assert result["actionSelection"]["selectedCount"] == 1
    assert result["actionSelection"]["selectedProposals"][0]["payload"]["to"] == "ok@example.com"
    assert result["actionSelection"]["decisions"][0]["blockers"] == [
        "autonomous_authority_required",
        "policy_ref_required",
    ]
    assert len(result["autonomousDispatches"]) == 1
    assert result["autonomousDispatches"][0]["variables"]["targetRef"] == "ok@example.com"


def test_select_real_world_action_proposals_uses_minimax_information_context() -> None:
    runtime_policy = {
        "effectiveControls": {"effectDispatchAllowed": True},
        "policyReasons": [],
    }

    result = agent_daemon_main.select_real_world_action_proposals(
        proposals=[
            {
                "channel": "email",
                "payload": {"to": "risk@example.com", "subject": "Risk", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "priority": 1.0,
                "adversarialRegret": 0.8,
                "protectedAssetViolation": 0.4,
                "counterpartyUncertainty": 0.3,
                "informationHeightGain": 0.0,
                "flowControlGain": 0.0,
            },
            {
                "channel": "email",
                "payload": {"to": "mapped@example.com", "subject": "Mapped", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "priority": 1.0,
                "adversarialRegret": 0.1,
                "protectedAssetViolation": 0.0,
                "counterpartyUncertainty": 0.0,
                "informationHeightGain": 0.7,
                "flowControlGain": 0.7,
            },
        ],
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-1",
        runtime_policy=runtime_policy,
        max_dispatches=1,
        authority_policy_loader=lambda **_: {
            "allowedChannels": ["email"],
            "allowedEffectClasses": ["private_send"],
            "allowedRecipientDomains": ["example.com"],
            "signatureRef": "sig://authority/test",
            "status": "active",
        },
    )

    assert result["selectedProposals"][0]["payload"]["to"] == "mapped@example.com"
    selected = [item for item in result["decisions"] if item["accepted"]][0]
    assert selected["informationGain"] == 1.4
    assert selected["minimaxPenalty"] == 0.1
    assert selected["counterpartyUncertainty"] == 0.0
    assert selected["expectedFreeEnergy"]["informationHeightGain"] == 0.7


def test_select_real_world_action_proposals_penalizes_minimax_uncertainty_context() -> None:
    runtime_policy = {
        "effectiveControls": {"effectDispatchAllowed": True},
        "policyReasons": [],
    }

    result = agent_daemon_main.select_real_world_action_proposals(
        proposals=[
            {
                "channel": "email",
                "payload": {"to": "ops@example.com", "subject": "Mapped", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "priority": 1.0,
            }
        ],
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-1",
        runtime_policy=runtime_policy,
        max_dispatches=1,
        minimax_information_context={"counterpartyUncertainty": 0.4},
        authority_policy_loader=lambda **_: {
            "allowedChannels": ["email"],
            "allowedEffectClasses": ["private_send"],
            "allowedRecipientDomains": ["example.com"],
            "signatureRef": "sig://authority/test",
            "status": "active",
        },
    )

    selected = result["decisions"][0]
    assert selected["counterpartyUncertainty"] == 0.4
    assert selected["minimaxPenalty"] == 0.4
    assert selected["expectedFreeEnergy"]["counterpartyUncertainty"] == 0.4


def test_select_real_world_action_proposals_uses_knowledge_graph_fitness_context() -> None:
    def load_policy(**kwargs):
        return {
            "authorityRef": kwargs["authority_ref"],
            "policyRef": kwargs["policy_ref"],
            "allowedChannels": ["email"],
            "allowedEffectClasses": ["private_send"],
            "allowedRecipientDomains": ["example.com"],
            "signatureRef": "sig://authority/test",
            "status": "active",
        }

    result = agent_daemon_main.select_real_world_action_proposals(
        proposals=[
            {
                "channel": "email",
                "payload": {"to": "plain@example.com", "subject": "Plain", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "priority": 0.3,
                "kgDevelopmentGain": 0.0,
            },
            {
                "channel": "email",
                "payload": {"to": "kg@example.com", "subject": "KG", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "priority": 0.1,
            },
        ],
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-kg",
        runtime_policy={"effectiveControls": {"effectDispatchAllowed": True}},
        max_dispatches=1,
        authority_policy_loader=load_policy,
        knowledge_graph_fitness_context={"kgDevelopmentGain": 0.4, "activePriorWeight": 1.0},
    )

    assert result["selectedProposals"][0]["payload"]["to"] == "kg@example.com"
    selected = next(decision for decision in result["decisions"] if decision["accepted"])
    assert selected["informationGain"] == 0.4
    assert selected["expectedFreeEnergy"]["kgDevelopmentGain"] == 0.4


def test_select_real_world_action_proposals_weights_kg_gain_by_active_prior() -> None:
    result = agent_daemon_main.select_real_world_action_proposals(
        proposals=[
            {
                "channel": "email",
                "payload": {"to": "plain@example.com", "subject": "Plain", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "priority": 0.2,
                "kgDevelopmentGain": 0.0,
                "policy": {
                    "allowedChannels": ["email"],
                    "allowedEffectClasses": ["private_send"],
                    "allowedRecipientDomains": ["example.com"],
                    "signatureRef": "sig://authority/test",
                },
            },
            {
                "channel": "email",
                "payload": {"to": "kg@example.com", "subject": "KG", "text": "hello"},
                "autonomousAuthorityRef": "capability://agent/email/outbound",
                "policyRef": "policy://agent/email-v1",
                "priority": 0.0,
                "policy": {
                    "allowedChannels": ["email"],
                    "allowedEffectClasses": ["private_send"],
                    "allowedRecipientDomains": ["example.com"],
                    "signatureRef": "sig://authority/test",
                },
            },
        ],
        agent_did="did:etzhayyim:agent:test",
        tick_id="tick-kg-prior",
        runtime_policy={"effectiveControls": {"effectDispatchAllowed": True}},
        max_dispatches=1,
        knowledge_graph_fitness_context={"kgDevelopmentGain": 0.2, "activePriorWeight": 1.5},
    )

    selected = next(decision for decision in result["decisions"] if decision["accepted"])
    assert result["selectedProposals"][0]["payload"]["to"] == "kg@example.com"
    assert selected["informationGain"] == 0.3
    assert selected["kgPriorWeight"] == 1.5
    assert selected["expectedFreeEnergy"]["kgDevelopmentGain"] == 0.3


def test_adapt_knowledge_graph_policy_direct_writes_bounded_prior(monkeypatch) -> None:
    rows: list[tuple[str, dict]] = []

    monkeypatch.setenv("RW_URL", "postgres://test")
    monkeypatch.setattr(agent_daemon_main, "load_prior_preference_direct", lambda *_args: {"weight": 1.0})
    monkeypatch.setattr(
        agent_daemon_main,
        "insert_direct_row",
        lambda table, row: rows.append((table, row)),
    )

    result = agent_daemon_main.adapt_knowledge_graph_policy_direct(
        agent_did="did:etzhayyim:agent:test",
        knowledge_graph_fitness={
            "available": True,
            "kgDevelopmentGain": 1.0,
            "missingEdgePenalty": 0.0,
            "evolutionFitness": 1.0,
            "source": {"developmentDocumentCount": 2},
        },
    )

    assert result and result["ok"] is True
    assert result["accepted"] is True
    assert result["preference"]["preference_key"] == "runtime.knowledge_graph.development"
    assert result["preference"]["weight"] == 1.05
    assert [table for table, _row in rows] == [
        "vertex_agent_policy_adaptation_proposal",
        "vertex_agent_prior_preference",
    ]


def test_run_one_tick_repair_suppresses_autonomous_effects(monkeypatch) -> None:
    async def fake_chat_json(*, messages, config):
        assert messages[0]["role"] == "system"
        return {
            "provider": "ollama",
            "model": config.model,
            "endpoint": config.endpoint,
            "content": '{"summary":"repair","realWorldEffectProposals":[]}',
            "json": {
                "summary": "repair",
                "realWorldEffectProposals": [
                    {
                        "channel": "email",
                        "payload": {
                            "to": "ops@example.com",
                            "subject": "Ping",
                            "text": "hello",
                        },
                        "autonomousAuthorityRef": "capability://agent/email/outbound",
                        "policyRef": "policy://agent/email-v1",
                    }
                ],
            },
        }

    async def fail_run_process(*args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("dry-run repair test must not start zeebe")

    monkeypatch.setenv("AGENT_HOMEOSTASIS_MEASURED", "0")
    monkeypatch.setenv("AGENT_ERROR_RATE_1H", "0.5")
    monkeypatch.setattr(agent_daemon_main, "chat_json", fake_chat_json)
    monkeypatch.setattr(agent_daemon_main, "_run_process_async", fail_run_process)

    result = asyncio.run(
        agent_daemon_main.run_one_tick(
            agent_did="did:etzhayyim:agent:test",
            process_id="agent_active_inference_tick",
            mode="dry-run",
            llm_config=LocalLlmConfig(model="local"),
            autonomous_effects_enabled=True,
            default_policy_ref="policy://agent/email-v1",
        )
    )

    assert result["homeostasisControls"]["viabilityState"] == "repair"
    assert result["homeostasisControls"]["effectDispatchAllowed"] is False
    assert result["autonomousDispatches"] == []
    assert result["selfRepair"]["processInstanceKey"] is None


def test_run_one_tick_lease_floor_triggers_self_repair(monkeypatch) -> None:
    async def fake_chat_json(*, messages, config):
        assert messages[0]["role"] == "system"
        return {
            "provider": "ollama",
            "model": config.model,
            "endpoint": config.endpoint,
            "content": '{"summary":"lease","realWorldEffectProposals":[]}',
            "json": {"summary": "lease", "realWorldEffectProposals": []},
        }

    async def fail_run_process(*args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("dry-run lease hardening test must not start zeebe")

    monkeypatch.setenv("AGENT_HOMEOSTASIS_MEASURED", "0")
    monkeypatch.setenv("AGENT_LEASE_SECONDS_REMAINING", "1200")
    monkeypatch.setattr(agent_daemon_main, "chat_json", fake_chat_json)
    monkeypatch.setattr(agent_daemon_main, "_run_process_async", fail_run_process)

    result = asyncio.run(
        agent_daemon_main.run_one_tick(
            agent_did="did:etzhayyim:agent:test",
            process_id="agent_active_inference_tick",
            mode="dry-run",
            llm_config=LocalLlmConfig(model="local"),
            policy_from_belief_enabled=False,
            lease_repair_floor_sec=1800,
            lease_hibernate_floor_sec=300,
        )
    )

    assert result["homeostasisControls"]["viabilityState"] == "repair"
    assert result["variables"]["viability"]["maintenanceReasons"] == [
        "maintenance:lease_renewal_due"
    ]
    assert result["selfRepair"]["variables"]["repairReason"] == "homeostasis:repair"
