from __future__ import annotations

import json
from pathlib import Path

from kotodama import agent_erc8004_main


def test_build_agent_registration_uses_erc8004_envelope() -> None:
    registration = agent_erc8004_main.build_agent_registration(
        agent_did="did:web:kami-agent.etzhayyim.com",
        status_report={"organismState": "repairing", "organismScore": 0.8, "processes": {}},
        chain_id=260425,
        agent_registry="0xcA3480edDAfa39c9377B83eEB18291286C8Cb865",
        erc8004_agent_id="123",
        agent_uri="ipfs://bafy-agent/agent.json",
        root_address="0x1111111111111111111111111111111111111111",
        smart_account="0x2222222222222222222222222222222222222222",
        public_status_url="https://kami-agent.etzhayyim.com",
    )

    assert registration["schema"] == agent_erc8004_main.ERC8004_SCHEMA
    assert registration["agent"]["agentRegistry"].startswith("eip155:260425:")
    assert registration["agent"]["agentId"] == "123"
    assert registration["rootIdentity"]["facadeDids"] == ["did:web:kami-agent.etzhayyim.com"]
    assert registration["protocols"][1]["kind"] == "local-status"
    assert registration["protocols"][1]["api"] == "https://kami-agent.etzhayyim.com/api/status"


def test_registration_hash_is_stable_for_key_order() -> None:
    assert agent_erc8004_main.registration_hash({"b": 2, "a": 1}) == (
        agent_erc8004_main.registration_hash({"a": 1, "b": 2})
    )


def test_publish_registration_ipfs_dry_run_does_not_need_secret() -> None:
    result = agent_erc8004_main.publish_registration_ipfs(
        registration={
            "schema": agent_erc8004_main.ERC8004_SCHEMA,
            "agent": {"agentURI": "ipfs://TBD_AGENT_REGISTRATION_CID"},
        },
        dry_run=True,
    )

    assert result["published"] is False
    assert result["uri"] == "ipfs://DRY_RUN_AGENT_REGISTRATION_CID"
    assert result["sha256"].startswith("0x")


def test_execute_publish_flow_blocks_placeholder_chain_submit(tmp_path: Path) -> None:
    registration = agent_erc8004_main.build_agent_registration(
        agent_did="did:web:kami-agent.etzhayyim.com",
        status_report={"organismState": "repairing", "organismScore": 0.8, "processes": {}},
        chain_id=260425,
        agent_registry="0xcA3480edDAfa39c9377B83eEB18291286C8Cb865",
        erc8004_agent_id="TBD_AFTER_AGENT_REGISTRY_MINT",
        agent_uri="ipfs://TBD_AGENT_REGISTRATION_CID",
    )

    result = agent_erc8004_main.execute_publish_flow(
        registration=registration,
        registration_path=tmp_path / "agent.json",
        publish_ipfs=True,
        submit_chain=True,
        dry_run=True,
        ipfs_base="https://ipfs.etzhayyim.com",
        rpc_url="https://geth.etzhayyim.com",
        chain_id=260425,
        registry="0xcA3480edDAfa39c9377B83eEB18291286C8Cb865",
    )

    assert result["ok"] is False
    assert result["chain"]["blocked"] is True
    assert any("rootIdentity.address" in error for error in result["preflight"]["chainErrors"])


def test_run_chain_register_uses_etzhayyim_cli(monkeypatch, tmp_path: Path) -> None:
    calls = []

    class Result:
        returncode = 0
        stdout = json.dumps({"ok": True, "dryRun": True})
        stderr = ""

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202
        calls.append((cmd, kwargs))
        return Result()

    monkeypatch.setattr(agent_erc8004_main.subprocess, "run", fake_run)

    result = agent_erc8004_main.run_chain_register(
        registration_path=tmp_path / "agent.json",
        agent_uri="ipfs://bafy-agent",
        registry="0xcA3480edDAfa39c9377B83eEB18291286C8Cb865",
        rpc_url="https://geth.etzhayyim.com",
        chain_id=260425,
        dry_run=False,
    )

    assert result["ok"] is True
    assert calls[0][0][:3] == ["etzhayyim", "agent-runtime", "register"]
    assert "--dry-run=false" in calls[0][0]


def test_execute_publish_flow_rewrites_existing_registration_before_chain(monkeypatch, tmp_path: Path) -> None:
    stale_path = tmp_path / "agent.json"
    stale_path.write_text('{"rootIdentity":{"address":"0x0000000000000000000000000000000000000000"}}\n')
    registration = agent_erc8004_main.build_agent_registration(
        agent_did="did:web:kami-agent.etzhayyim.com",
        status_report={"organismState": "active", "organismScore": 1.0, "processes": {}},
        chain_id=260425,
        agent_registry="0xcA3480edDAfa39c9377B83eEB18291286C8Cb865",
        erc8004_agent_id="123",
        agent_uri="ipfs://bafy-agent",
        root_address="0xe506d815690ab0b81bf2f34b5057d7b8b96fe643",
    )

    monkeypatch.setattr(
        agent_erc8004_main,
        "run_chain_register",
        lambda **kwargs: {"ok": True, "dryRun": True, "registrationPath": str(kwargs["registration_path"])},
    )

    result = agent_erc8004_main.execute_publish_flow(
        registration=registration,
        registration_path=stale_path,
        publish_ipfs=False,
        submit_chain=True,
        dry_run=True,
        ipfs_base="https://ipfs.etzhayyim.com",
        rpc_url="https://geth.etzhayyim.com",
        chain_id=260425,
        registry="0xcA3480edDAfa39c9377B83eEB18291286C8Cb865",
    )

    written = json.loads(stale_path.read_text())
    assert result["ok"] is True
    assert written["rootIdentity"]["address"] == "0xe506d815690ab0b81bf2f34b5057d7b8b96fe643"
