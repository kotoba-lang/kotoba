from __future__ import annotations

from kotodama.agent_authority_policy import row_to_policy


def test_row_to_policy_maps_signed_delegated_authority() -> None:
    policy = row_to_policy(
        {
            "authority_ref": "capability://agent/email/outbound",
            "policy_ref": "policy://agent/email-v1",
            "agent_did": "did:web:kami-agent.etzhayyim.com",
            "channels_json": '["email"]',
            "effect_classes_json": '["private_send"]',
            "target_bindings_json": '["mailto:ops@example.com"]',
            "payload_constraints_json": (
                '{"specificPredelegation": false, "allowedRecipientDomains": ["etzhayyim.com"]}'
            ),
            "rate_limit_json": '{"perHour": 4}',
            "expires_at": "2026-12-31T23:59:59Z",
            "signature_ref": "sig://authority/test",
            "status": "active",
        }
    )

    assert policy["authorityRef"] == "capability://agent/email/outbound"
    assert policy["allowedChannels"] == ["email"]
    assert policy["allowedEffectClasses"] == ["private_send"]
    assert policy["allowedTargetRefs"] == ["mailto:ops@example.com"]
    assert policy["allowedRecipientDomains"] == ["etzhayyim.com"]
    assert policy["rateLimit"] == {"perHour": 4}
    assert policy["signatureRef"] == "sig://authority/test"
