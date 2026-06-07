"""Pure tests for ADR-2604301200 agent economy primitives."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from kotodama.primitives import agent_economy as AE


class _FakeWorker:
    def __init__(self) -> None:
        self.registered: list[dict] = []

    def task(self, *, task_type: str, single_value: bool, timeout_ms: int, **kwargs):
        entry = {
            "task_type": task_type,
            "single_value": single_value,
            "timeout_ms": timeout_ms,
            **kwargs,
        }

        def decorator(fn):
            self.registered.append({**entry, "fn": fn.__name__})
            return fn

        return decorator

    def task_types(self) -> list[str]:
        return [entry["task_type"] for entry in self.registered]


def test_runtime_quote_returns_bond_and_resource_hash() -> None:
    out = AE.task_agent_runtime_quote(
        rootDid="did:ethr:260425:0xroot",
        agentDid="did:plc:agent",
        runtimeNamespace="yoro-actors",
        cpuMillicores=1000,
        memoryMiB=2048,
        gpuClass="none",
        leasePeriodSec=3600,
    )

    assert out["ok"] is True
    assert int(out["bondGccWei"]) > 0
    assert out["resourceHash"].startswith("sha256:")
    assert out["runtimeNamespace"] == "yoro-actors"


def test_runtime_quote_rejects_default_namespace() -> None:
    with pytest.raises(ValueError, match="runtimeNamespace"):
        AE.task_agent_runtime_quote(
            rootDid="did:ethr:260425:0xroot",
            agentDid="did:plc:agent",
            runtimeNamespace="default",
        )


def test_runtime_reserve_dry_run_does_not_submit_onchain() -> None:
    out = AE.task_agent_runtime_reserve(
        rootDid="did:ethr:260425:0xroot",
        agentDid="did:plc:agent",
        runtimeNamespace="yoro-actors",
        submitOnChain=True,
        dryRun=True,
    )

    assert out["ok"] is True
    assert out["pendingOnChain"] is True
    assert out["onchain"]["skipped"] is True
    assert out["leaseId"].startswith("lease_")


# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
def test_insert_normalizes_timestamp_values_for_risingwave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _Cursor:
        def execute(self, query: str, params: tuple[object, ...]) -> None:
            captured["query"] = query
            captured["params"] = params

    class _Ctx:
        def __enter__(self) -> _Cursor:
            return _Cursor()

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(AE, "sync_cursor", lambda: _Ctx())

    AE._insert(
        "vertex_agent_economy_profile",
        {
            "vertex_id": "at://did:web:agent.etzhayyim.com/com.etzhayyim.agent.economyProfile/profile_test",
            "created_at": "2026-04-30T02:04:58Z",
            "updated_at": None,
        },
    )

    assert isinstance(captured["params"][1], datetime)
    assert captured["params"][1].tzinfo is None
    assert captured["params"][1].isoformat() == "2026-04-30T02:04:58"
    assert captured["params"][2] is None


def test_spawn_child_org_dry_run_returns_lineage_and_profile_ids() -> None:
    out = AE.task_agent_spawn_child_org(
        parentRootDid="did:ethr:260425:0xroot",
        parentAgentDid="did:plc:parent",
        childRootDid="did:ethr:260425:0xchild",
        childAgentDid="did:plc:child",
        childOrgDid="did:web:child.etzhayyim.com",
        dryRun=True,
    )

    assert out["ok"] is True
    assert out["lineageVertexId"].startswith("at://")
    assert out["profileVertexId"].startswith("at://")
    assert out["pendingOnChain"] is True


def test_onchain_reserve_without_private_key_fails_before_cast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PRIVATE_KEY", raising=False)
    out = AE._reserve_onchain(
        lease_id="lease-1",
        agent_did="did:plc:agent",
        resource_hash="sha256:" + "1" * 64,
        policy_hash="slash-policy-v1",
        bond_wei=1,
        lease_period_sec=3600,
    )

    assert out["ok"] is False
    assert out["stage"] == "approve"
    assert out["error"] == "PRIVATE_KEY env not set"


def test_cast_send_extracts_receipt_transaction_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0
        stdout = """
logs                 [{"transactionHash":"0x1111111111111111111111111111111111111111111111111111111111111111"}]
status               1 (success)
transactionHash      0x2222222222222222222222222222222222222222222222222222222222222222
"""
        stderr = ""

    monkeypatch.setattr(AE.subprocess, "run", lambda *args, **kwargs: _Proc())

    out = AE._cast_send(["cast", "send", "0x0", "f()"])

    assert out["ok"] is True
    assert out["txHash"] == "0x2222222222222222222222222222222222222222222222222222222222222222"


def test_autopilot_tick_renews_expiring_runtime_lease() -> None:
    out = AE.task_agent_runtime_autopilot_tick(
        leaseRows=[
            {
                "lease_id": "lease-1",
                "root_did": "did:ethr:260425:0xroot",
                "agent_did": "did:plc:agent",
                "runtime_kind": "zeebe-langgraph",
                "runtime_namespace": "yoro-actors",
                "lease_period_sec": 3600,
                "expires_at": AE._iso(AE._now() + timedelta(minutes=30)),
            }
        ],
        profileRows=[],
        renewWindowSec=3600,
        dryRun=True,
    )

    assert out["ok"] is True
    assert out["renewed"] == 1
    assert out["hibernated"] == 0
    assert out["actions"][0]["action"] == "renew"


def test_autopilot_tick_hibernates_expired_runtime_lease() -> None:
    out = AE.task_agent_runtime_autopilot_tick(
        leaseRows=[
            {
                "lease_id": "lease-2",
                "root_did": "did:ethr:260425:0xroot",
                "agent_did": "did:plc:agent",
                "runtime_namespace": "yoro-actors",
                "expires_at": AE._iso(AE._now() - timedelta(hours=2)),
            }
        ],
        profileRows=[],
        hibernateGraceSec=3600,
        dryRun=True,
    )

    assert out["ok"] is True
    assert out["renewed"] == 0
    assert out["hibernated"] == 1
    assert out["actions"][0]["action"] == "hibernate"


def test_autopilot_tick_starts_active_profile_without_runtime_lease() -> None:
    out = AE.task_agent_runtime_autopilot_tick(
        leaseRows=[],
        profileRows=[
            {
                "root_did": "did:ethr:260425:0xroot",
                "agent_did": "did:plc:child",
                "runtime_policy_cid": "ipfs://runtime-policy",
            }
        ],
        runtimeNamespace="yoro-actors",
        startMissingProfiles=True,
        dryRun=True,
    )

    assert out["ok"] is True
    assert out["started"] == 1
    assert out["actions"][0]["action"] == "start"
    assert out["actions"][0]["leaseId"].startswith("lease_")


def test_register_wires_all_agent_economy_task_types() -> None:
    worker = _FakeWorker()
    AE.register(worker, timeout_ms=12_345)

    assert worker.task_types() == [
        "agent.runtime.quote",
        "agent.runtime.reserve",
        "agent.runtime.renew",
        "agent.runtime.hibernate",
        "agent.runtime.autopilotTick",
        "agent.income.record",
        "agent.usage.record",
        "agent.slash.record",
        "agent.spawnChildOrg",
    ]
    assert all(entry["single_value"] is False for entry in worker.registered)
    assert all(entry["timeout_ms"] == 12_345 for entry in worker.registered)
