from kotodama.primitives import active_inference


def test_score_candidate_actions_selects_lowest_auditable_efe() -> None:
    result = active_inference.score_candidate_actions(
        candidate_actions=[
            {
                "actionId": "send-email",
                "risk": 0.4,
                "ambiguity": 0.2,
                "epistemicValue": 0.1,
                "viabilityPenalty": 0.1,
                "externalEffectPenalty": 0.3,
                "authorityRequired": True,
            },
            {
                "actionId": "bind-authority",
                "risk": 0.1,
                "ambiguity": 0.15,
                "epistemicValue": 0.05,
                "viabilityPenalty": 0.0,
                "externalEffectPenalty": 0.0,
            },
        ]
    )

    assert result["selectedActionId"] == "bind-authority"
    assert result["expectedFreeEnergy"]["total"] == 0.2
    assert result["rejected"] == [{"actionId": "send-email", "reason": "delegated_authority_required"}]


def test_score_candidate_actions_includes_minimax_and_protected_asset_terms() -> None:
    result = active_inference.score_candidate_actions(
        candidate_actions=[
            {
                "actionId": "press",
                "risk": 0.1,
                "ambiguity": 0.1,
                "adversarialRegret": 0.6,
                "protectedAssetViolation": 0.2,
            },
            {
                "actionId": "negotiate",
                "risk": 0.2,
                "ambiguity": 0.1,
                "adversarialRegret": 0.1,
                "protectedAssetViolation": 0.0,
            },
        ]
    )

    assert result["selectedActionId"] == "negotiate"
    assert result["expectedFreeEnergy"]["adversarialRegret"] == 0.1
    assert result["expectedFreeEnergy"]["protectedAssetViolation"] == 0.0
    assert result["expectedFreeEnergy"]["counterpartyUncertainty"] == 0.0


def test_score_candidate_actions_includes_counterparty_uncertainty_in_minimax() -> None:
    result = active_inference.score_candidate_actions(
        candidate_actions=[
            {
                "actionId": "uncertain-counterparty",
                "risk": 0.1,
                "ambiguity": 0.1,
                "adversarialRegret": 0.1,
                "protectedAssetViolation": 0.0,
                "counterpartyUncertainty": 0.5,
            },
            {
                "actionId": "known-counterparty",
                "risk": 0.1,
                "ambiguity": 0.1,
                "adversarialRegret": 0.1,
                "protectedAssetViolation": 0.0,
                "counterpartyUncertainty": 0.0,
            },
        ]
    )

    assert result["selectedActionId"] == "known-counterparty"
    assert result["expectedFreeEnergy"]["counterpartyUncertainty"] == 0.0


def test_score_candidate_actions_rewards_information_height_and_flow_control() -> None:
    result = active_inference.score_candidate_actions(
        candidate_actions=[
            {
                "actionId": "low-context",
                "risk": 0.2,
                "ambiguity": 0.3,
                "informationHeightGain": 0.0,
                "flowControlGain": 0.0,
            },
            {
                "actionId": "map-dependency-frontier",
                "risk": 0.2,
                "ambiguity": 0.3,
                "informationHeightGain": 0.2,
                "flowControlGain": 0.2,
            },
        ]
    )

    assert result["selectedActionId"] == "map-dependency-frontier"
    assert result["expectedFreeEnergy"]["informationHeightGain"] == 0.2
    assert result["expectedFreeEnergy"]["flowControlGain"] == 0.2


def test_score_candidate_actions_rewards_knowledge_graph_development() -> None:
    result = active_inference.score_candidate_actions(
        candidate_actions=[
            {"actionId": "plain", "risk": 0.2, "ambiguity": 0.2},
            {
                "actionId": "fill-kg-frontier",
                "risk": 0.2,
                "ambiguity": 0.2,
                "kgDevelopmentGain": 0.3,
            },
        ]
    )

    assert result["selectedActionId"] == "fill-kg-frontier"
    assert result["expectedFreeEnergy"]["kgDevelopmentGain"] == 0.3


def test_score_candidate_actions_rejects_when_mokuteki_gate_fails() -> None:
    result = active_inference.score_candidate_actions(
        candidate_actions=[{"actionId": "post", "risk": 0.0}],
        mokuteki_gate_pass=False,
    )

    assert result["selectedActionId"] is None
    assert result["rejected"] == [{"actionId": "post", "reason": "mokuteki_gate_failed"}]


def test_minimax_counterparty_model_builds_graph_rows() -> None:
    model = active_inference.build_counterparty_model(
        agent_did="did:web:kami-agent.etzhayyim.com",
        counterparty_ref="mailto:partner@example.com",
        prior_preferences={"protects": ["reputation", "budget"]},
        protected_assets=[{"assetRef": "asset://counterparty/reputation"}],
        confidence=0.8,
        uncertainty=0.2,
    )
    asset = active_inference.build_protected_asset(
        agent_did="did:web:kami-agent.etzhayyim.com",
        counterparty_ref="mailto:partner@example.com",
        asset_ref="asset://counterparty/reputation",
        asset_kind="reputation",
        protected_state={"noPublicEmbarrassment": True},
        violation_cost=0.9,
        reversibility_score=0.2,
    )
    edge = active_inference.build_counterparty_protects_asset_edge(
        counterparty_model_id=model["vertex_id"],
        protected_asset_id=asset["vertex_id"],
        owner_did="did:web:kami-agent.etzhayyim.com",
    )

    assert model["counterparty_ref"] == "mailto:partner@example.com"
    assert model["confidence"] == 0.8
    assert asset["asset_kind"] == "reputation"
    assert asset["violation_cost"] == 0.9
    assert edge["relation_kind"] == "protects_asset"


def test_evaluate_minimax_regret_selects_worst_counterparty_response() -> None:
    result = active_inference.evaluate_minimax_regret(
        agent_did="did:web:kami-agent.etzhayyim.com",
        action_id="send-notice",
        counterparty_ref="mailto:partner@example.com",
        payoff_matrix=[
            {"response": "cooperate", "utility": 0.8, "regret": 0.0},
            {
                "response": "escalate",
                "utility": -0.4,
                "regret": 0.7,
                "protectedAssetViolation": 0.6,
            },
        ],
        counterparty_uncertainty=0.3,
    )

    assert result["selectedResponse"] == "escalate"
    assert result["adversarialRegret"] == 0.7
    assert result["protectedAssetViolation"] == 0.6
    assert result["counterpartyUncertainty"] == 0.3
    assert result["evaluation"]["counterparty_uncertainty"] == 0.3
    assert result["evaluation"]["evaluation_state"] == "evaluated"


def test_information_flow_helpers_build_height_and_flow_rows() -> None:
    root = active_inference.build_information_node(
        agent_did="did:web:kami-agent.etzhayyim.com",
        info_ref="info://strategy/protected-asset-map",
        info_kind="strategy",
        abstraction_level=7,
        value={"summary": "counterparty protects reputation via escalation options"},
        counterparty_ref="mailto:partner@example.com",
    )
    detail = active_inference.build_information_node(
        agent_did="did:web:kami-agent.etzhayyim.com",
        info_ref="info://evidence/message-thread",
        info_kind="evidence",
        abstraction_level=2,
        value={"messageId": "m1"},
    )
    dep = active_inference.build_information_dependency_edge(
        src_vid=root["vertex_id"],
        dst_vid=detail["vertex_id"],
        dependency_kind="abstracts_from",
        weight=0.8,
    )
    flow = active_inference.build_information_flow_edge(
        src_vid=detail["vertex_id"],
        dst_vid=root["vertex_id"],
        flow_kind="updates_belief",
        bandwidth_score=0.6,
        control_score=0.7,
    )
    leverage = active_inference.evaluate_information_leverage(
        information_nodes=[root, detail],
        flow_edges=[flow],
    )

    assert root["abstraction_level"] == 7
    assert dep["dependency_kind"] == "abstracts_from"
    assert flow["flow_kind"] == "updates_belief"
    assert leverage["maxInformationHeight"] == 7
    assert leverage["informationHeightGain"] == 0.7
    assert leverage["flowControlGain"] == 0.7


def test_classify_real_world_effect_blocks_high_risk_without_authority() -> None:
    result = active_inference.classify_real_world_effect(
        channel="print-mail",
        effect_class="physical_dispatch",
        payload={"pdfSha256": "abc", "recipient": "court"},
        target_ref="postal:jp:tokyo",
        summary="Send notice",
    )

    effect = result["realWorldEffect"]
    assert result["requiresDelegatedAuthority"] is True
    assert "delegated_authority_required" in result["blockers"]
    assert "budget_or_quote_required" in result["blockers"]
    assert result["externalEffectPenalty"] > 0.5
    assert effect["channel"] == "print-mail"
    assert effect["effect_class"] == "physical_dispatch"
    assert effect["dispatch_state"] == "blocked"
    assert len(effect["payload_hash"]) == 64


def test_classify_generation_artifact_as_draft_only() -> None:
    result = active_inference.classify_real_world_effect(
        channel="image",
        payload={"prompt": "internal draft", "publish": False},
        summary="Draft image",
    )

    assert result["requiresApproval"] is False
    assert result["blockers"] == []
    assert result["realWorldEffect"]["effect_class"] == "draft_only"
    assert result["realWorldEffect"]["dispatch_state"] == "classified"


def test_classify_real_world_effect_accepts_autonomous_authority() -> None:
    result = active_inference.classify_real_world_effect(
        channel="email",
        effect_class="private_send",
        payload={"to": "ops@example.com", "subject": "Ping", "text": "hello"},
        target_ref="mailto:ops@example.com",
        autonomous_authority_ref="capability://agent/email/outbound/low-risk",
        summary="Send operational ping",
    )

    assert result["authorityMode"] == "delegated"
    assert result["blockers"] == []
    assert result["realWorldEffect"]["dispatch_state"] == "classified"
    assert result["realWorldEffect"]["authority_ref"].startswith("capability://")


def test_plan_real_world_dispatch_allows_email_with_capability_policy_and_hash() -> None:
    payload = {"to": "ops@example.com", "subject": "Ping", "text": "hello", "ignored": True}
    effect = active_inference.classify_real_world_effect(
        channel="email",
        effect_class="private_send",
        payload=payload,
        target_ref="mailto:ops@example.com",
        agent_did="did:web:kami-agent.etzhayyim.com",
        autonomous_authority_ref="capability://agent/email/outbound/low-risk",
    )["realWorldEffect"]

    plan = active_inference.plan_real_world_dispatch(
        real_world_effect=effect,
        payload=payload,
        policy_ref="policy://agent/autonomous-email-v1",
    )

    assert plan["dispatchAllowed"] is True
    assert plan["taskType"] == "mailer.sendEmail"
    assert plan["nsid"] == "com.etzhayyim.apps.mailer.sendEmail"
    assert plan["channelPayload"] == {
        "from": "kami-agent@etzhayyim.com",
        "fromAddress": "kami-agent@etzhayyim.com",
        "subject": "Ping",
        "text": "hello",
        "to": "ops@example.com",
    }
    assert plan["receiptExpectation"] == "messageId"


def test_plan_real_world_dispatch_blocks_payload_tampering() -> None:
    original = {"to": "ops@example.com", "subject": "Ping", "text": "hello"}
    effect = active_inference.classify_real_world_effect(
        channel="email",
        effect_class="private_send",
        payload=original,
        target_ref="mailto:ops@example.com",
        autonomous_authority_ref="capability://agent/email/outbound/low-risk",
    )["realWorldEffect"]

    plan = active_inference.plan_real_world_dispatch(
        real_world_effect=effect,
        payload={**original, "text": "changed"},
        policy_ref="policy://agent/autonomous-email-v1",
    )

    assert plan["dispatchAllowed"] is False
    assert "payload_hash_mismatch" in plan["blockers"]
    assert plan["taskType"] == ""


def test_sender_email_for_agent_derives_etzhayyim_sender() -> None:
    assert active_inference.sender_email_for_agent("did:web:mailer.etzhayyim.com") == "mailer@etzhayyim.com"
    assert active_inference.sender_email_for_agent("did:web:a8wwtz73.etzhayyim.com") == "a8wwtz73@etzhayyim.com"
    assert active_inference.sender_email_for_agent("did:etzhayyim:agent:local") == "local@etzhayyim.com"
    assert active_inference.sender_email_for_agent("did:etzhayyim:agent:123") == "a-123@etzhayyim.com"


def test_plan_real_world_dispatch_blocks_unsupported_phone_channel() -> None:
    payload = {"to": "+81300000000", "text": "hello"}
    effect = active_inference.classify_real_world_effect(
        channel="phone",
        effect_class="private_send",
        payload=payload,
        target_ref="tel:+81300000000",
        autonomous_authority_ref="capability://agent/phone/outbound/test",
    )["realWorldEffect"]

    plan = active_inference.plan_real_world_dispatch(
        real_world_effect=effect,
        payload=payload,
        policy_ref="policy://agent/autonomous-phone-v1",
    )

    assert plan["dispatchAllowed"] is False
    assert "unsupported_autonomous_channel:phone" in plan["blockers"]


def test_plan_real_world_dispatch_blocks_non_email_live_channel() -> None:
    payload = {"to": "+81300000000", "url": "ipfs://bafy-doc"}
    effect = active_inference.classify_real_world_effect(
        channel="fax",
        effect_class="private_send",
        payload=payload,
        target_ref="fax:+81300000000",
        autonomous_authority_ref="capability://agent/fax/outbound/test",
    )["realWorldEffect"]

    plan = active_inference.plan_real_world_dispatch(
        real_world_effect=effect,
        payload=payload,
        policy_ref="policy://agent/autonomous-fax-v1",
        policy={"specificPredelegation": True, "signatureRef": "sig://authority/test"},
    )

    assert plan["dispatchAllowed"] is False
    assert "channel_worker_not_live:fax" in plan["blockers"]


def test_plan_real_world_dispatch_applies_inline_policy() -> None:
    payload = {"to": "ops@blocked.example", "subject": "Ping", "text": "hello"}
    effect = active_inference.classify_real_world_effect(
        channel="email",
        effect_class="private_send",
        payload=payload,
        target_ref="mailto:ops@blocked.example",
        agent_did="did:web:kami-agent.etzhayyim.com",
        autonomous_authority_ref="capability://agent/email/outbound/low-risk",
    )["realWorldEffect"]

    plan = active_inference.plan_real_world_dispatch(
        real_world_effect=effect,
        payload=payload,
        policy_ref="policy://agent/autonomous-email-v1",
        policy={"allowedChannels": ["email"], "allowedRecipientDomains": ["example.com"]},
    )

    assert plan["dispatchAllowed"] is False
    assert "policy_recipient_domain_denied:blocked.example" in plan["blockers"]


def test_verify_delegated_authority_blocks_expired_policy() -> None:
    blockers = active_inference.verify_delegated_authority(
        authority_ref="capability://agent/email/outbound/low-risk",
        policy_ref="policy://agent/autonomous-email-v1",
        channel="email",
        effect_class="private_send",
        payload={"to": "ops@example.com"},
        policy={
            "authorityRef": "capability://agent/email/outbound/low-risk",
            "policyRef": "policy://agent/autonomous-email-v1",
            "allowedChannels": ["email"],
            "allowedEffectClasses": ["private_send"],
            "allowedRecipientDomains": ["example.com"],
            "signatureRef": "sig://authority/test",
            "expiresAt": "2026-01-01T00:00:00Z",
        },
        now=active_inference.datetime(2026, 5, 7, tzinfo=active_inference.timezone.utc),
    )

    assert "authority_policy_expired" in blockers


def test_verify_delegated_authority_allows_target_ref_wildcard() -> None:
    blockers = active_inference.verify_delegated_authority(
        authority_ref="capability://agent/email/outbound/low-risk",
        policy_ref="policy://agent/autonomous-email-v1",
        channel="email",
        effect_class="private_send",
        payload={"to": "kami-agent@etzhayyim.com"},
        target_ref="mailto:kami-agent@etzhayyim.com",
        policy={
            "authorityRef": "capability://agent/email/outbound/low-risk",
            "policyRef": "policy://agent/autonomous-email-v1",
            "allowedChannels": ["email"],
            "allowedEffectClasses": ["private_send"],
            "allowedTargetRefs": ["mailto:*@etzhayyim.com"],
            "allowedRecipientDomains": ["etzhayyim.com"],
            "signatureRef": "sig://authority/test",
        },
    )

    assert "authority_target_denied" not in blockers


def test_high_risk_requires_specific_predelegation() -> None:
    payload = {"to": "+81300000000", "text": "hello"}
    effect = active_inference.classify_real_world_effect(
        channel="phone",
        effect_class="private_send",
        payload=payload,
        target_ref="tel:+81300000000",
        autonomous_authority_ref="capability://agent/phone/outbound/test",
    )["realWorldEffect"]

    plan = active_inference.plan_real_world_dispatch(
        real_world_effect=effect,
        payload=payload,
        policy_ref="policy://agent/autonomous-phone-v1",
        policy={"allowedChannels": ["phone"], "signatureRef": "sig://authority/test"},
    )

    assert plan["dispatchAllowed"] is False
    assert "specific_predelegation_required" in plan["blockers"]


def test_build_dispatch_receipt_observation_records_message_id() -> None:
    effect = {"vertex_id": "effect-1", "agent_did": "did:web:kami-agent.etzhayyim.com", "channel": "email"}
    plan = {
        "dispatchPlanId": "plan-1",
        "channel": "email",
        "taskType": "mailer.sendEmail",
        "receiptExpectation": "messageId",
    }

    result = active_inference.build_dispatch_receipt_observation(
        real_world_effect=effect,
        dispatch_plan=plan,
        dispatch_result={"messageId": "msg_123", "provider": "resend"},
    )

    assert result["dispatchState"] == "dispatched"
    assert result["receiptRef"] == "msg_123"
    assert result["observation"]["source_kind"] == "dispatch_receipt"
    assert result["effectPatch"]["dispatch_receipt_ref"] == "msg_123"


def test_inbound_email_to_observation_maps_to_agent() -> None:
    result = active_inference.inbound_email_to_observation(
        {
            "uri": "at://mail/1",
            "messageId": "m1",
            "toLocal": "kami-agent",
            "subject": "hello",
            "bodyText": "world",
        }
    )

    assert result["observation"]["agent_did"] == "did:web:kami-agent.etzhayyim.com"
    assert result["observation"]["source_kind"] == "inbound_email"
    assert result["payload"]["subject"] == "hello"


def test_evaluate_viability_transitions() -> None:
    assert active_inference.evaluate_viability()["viabilityState"] == "normal"

    conserve = active_inference.evaluate_viability(
        compute_budget_remaining=0.1,
        lease_seconds_remaining=1200,
    )
    assert conserve["viabilityState"] == "conserve"
    assert "resource_floor_near" in conserve["blockers"]

    repair = active_inference.evaluate_viability(error_rate_1h=0.5)
    assert repair["viabilityState"] == "repair"

    halted = active_inference.evaluate_viability(error_rate_1h=0.9)
    assert halted["viabilityState"] == "halted"

    hibernate = active_inference.evaluate_viability(
        compute_budget_remaining=0.0,
        lease_seconds_remaining=0,
    )
    assert hibernate["viabilityState"] == "hibernate"


def test_adapt_policy_accepts_bounded_prior_update() -> None:
    result = active_inference.adapt_policy(
        agent_did="did:web:kami-agent.etzhayyim.com",
        preference_key="runtime.email.low_risk_latency",
        current_preference={"weight": 1.0, "target_range_json": {"maxMinutes": 10}},
        proposal={
            "proposedWeight": 1.1,
            "targetRange": {"maxMinutes": 7},
            "dependsOnAdr": "ADR-2605061200",
        },
        mokuteki_gate_pass=True,
        triple_witness_pass=True,
    )

    assert result["accepted"] is True
    assert result["blockers"] == []
    assert result["preference"]["preference_key"] == "runtime.email.low_risk_latency"
    assert result["preference"]["weight"] == 1.1
    assert result["preference"]["active"] is True
    assert result["policyProposal"]["proposal_state"] == "accepted"


def test_adapt_policy_blocks_objective_and_unbounded_change() -> None:
    result = active_inference.adapt_policy(
        agent_did="did:web:kami-agent.etzhayyim.com",
        preference_key="mokuteki.core",
        current_preference={"weight": 1.0},
        proposal={"proposedWeight": 2.0, "hardFloor": True},
        mokuteki_gate_pass=True,
        triple_witness_pass=False,
    )

    assert result["accepted"] is False
    assert result["preference"] == {}
    assert "immutable_preference_key" in result["blockers"]
    assert "hard_floor_mutation_forbidden" in result["blockers"]
    assert "triple_witness_failed" in result["blockers"]
    assert "weight_delta_exceeds_bound" in result["blockers"]
    assert result["policyProposal"]["proposal_state"] == "blocked"
