"""Web4 contract-DID autonomous agent economy primitives.

ADR-2604301200 defines the economic surface for persistent autonomous agents:
runtime leases, bonded resource budgets, income, usage receipts, slash events,
and parent/child org lineage. These handlers make that surface callable from
BPMN/Zeebe without requiring the atproto appview handler to change first.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


ACTOR_DID = "did:web:bpmn.etzhayyim.com"
ORG_DID = "anon"
CHAIN_ID = int(os.environ.get("AGENT_ECONOMY_CHAIN_ID", "260425"))
ESCROW_ADDR = os.environ.get("AGENT_RUNTIME_LEASE_ESCROW_ADDR", "").strip()
ETH_RPC_URL = os.environ.get("ETH_RPC_URL", "https://geth.etzhayyim.com").strip()
GCC_ADDR = os.environ.get("GCC_ADDR", "0x8e9A5162b2800E0D19acC1708A531A3954900E21").strip()

DISALLOWED_NAMESPACES = {"", "default"}
TIMESTAMP_COLUMNS = {
    "created_at",
    "updated_at",
    "starts_at",
    "expires_at",
    "occurred_at",
    "usage_window_start",
    "usage_window_end",
}


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _db_ts(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None, microsecond=0)


def _id(prefix: str, *parts: Any) -> str:
    if parts:
        raw = "|".join(str(p) for p in parts)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:28]
        return f"{prefix}_{digest}"
    token = secrets.token_urlsafe(18).replace("-", "").replace("_", "")[:24]
    return f"{prefix}_{token}"


def _vid(collection: str, ident: str) -> str:
    return f"at://did:web:agent.etzhayyim.com/com.etzhayyim.agent.{collection}/{ident}"


def _canonical_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _bytes32_hash(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("0x") and len(text) == 66:
        return text
    if text.startswith("sha256:") and len(text) == 71:
        return "0x" + text.removeprefix("sha256:")
    try:
        from eth_hash.auto import keccak  # type: ignore[import-untyped]

        return "0x" + keccak(text.encode("utf-8")).hex()
    except ImportError:
        return "0x" + hashlib.sha3_256(text.encode("utf-8")).hexdigest()


def _require(payload: dict[str, Any], fields: list[str]) -> None:
    missing = [f for f in fields if payload.get(f) in (None, "")]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def _require_namespace(namespace: str) -> str:
    ns = str(namespace or "").strip()
    if ns in DISALLOWED_NAMESPACES:
        raise ValueError("runtimeNamespace must be explicit and must not be 'default'")
    return ns


def _insert(table: str, row: dict[str, Any], *, dry_run: bool = False) -> None:
    if dry_run:
        return
    client = get_kotoba_client()
    formatted_row = {
        c: _db_ts(_parse_ts(row[c])) if c in TIMESTAMP_COLUMNS and row[c] is not None else row[c]
        for c in row
    }
    client.insert_row(table, formatted_row)


def _audit(actor_did: str, org_did: str, *, sensitivity_ord: int = 1) -> dict[str, Any]:
    return {
        "actor_did": actor_did or ACTOR_DID,
        "org_did": org_did or ORG_DID,
        "org_id": org_did or ORG_DID,
        "user_id": actor_did or ACTOR_DID,
        "sensitivity_ord": int(sensitivity_ord),
    }


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "on", "yes")


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        ts = value
    else:
        text = str(value or "").strip()
        if not text:
            return _now()
        ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _onchain_requested(submit_on_chain: bool) -> bool:
    if submit_on_chain:
        return True
    return os.environ.get("AGENT_RUNTIME_ESCROW_SEND", "0").lower() in ("1", "true", "on", "yes")


def _cast_send(args: list[str], *, timeout: float = 60.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        return {"ok": False, "error": "cast not found in PATH", "txHash": ""}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "cast send timed out", "txHash": ""}

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    tx_hash = ""
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("transactionHash"):
            match = re.search(r"0x[a-fA-F0-9]{64}", stripped)
            if match:
                tx_hash = match.group(0)
                break
        if stripped.startswith("0x") and len(stripped) == 66:
            tx_hash = stripped
            break
        if "transactionHash" in line:
            matches = re.findall(r"0x[a-fA-F0-9]{64}", line)
            if matches:
                tx_hash = matches[-1]
    return {
        "ok": proc.returncode == 0,
        "txHash": tx_hash,
        "stdout": stdout[-1000:],
        "stderr": stderr[-500:],
        "error": "" if proc.returncode == 0 else (stderr or stdout)[-300:],
    }


def _private_key() -> str:
    return os.environ.get("PRIVATE_KEY", "").strip()


def _approve_gcc(spender: str, amount_wei: int) -> dict[str, Any]:
    private_key = _private_key()
    if not private_key:
        return {"ok": False, "error": "PRIVATE_KEY env not set", "txHash": ""}
    if not GCC_ADDR:
        return {"ok": False, "error": "GCC_ADDR env not set", "txHash": ""}
    return _cast_send([
        "cast", "send", GCC_ADDR,
        "approve(address,uint256)",
        spender, str(amount_wei),
        "--rpc-url", ETH_RPC_URL,
        "--private-key", private_key,
        "--legacy",
    ])


def _escrow_call(signature: str, args: list[str], *, timeout: float = 60.0) -> dict[str, Any]:
    private_key = _private_key()
    if not private_key:
        return {"ok": False, "error": "PRIVATE_KEY env not set", "txHash": ""}
    if not ESCROW_ADDR:
        return {"ok": False, "error": "AGENT_RUNTIME_LEASE_ESCROW_ADDR env not set", "txHash": ""}
    return _cast_send([
        "cast", "send", ESCROW_ADDR,
        signature,
        *args,
        "--rpc-url", ETH_RPC_URL,
        "--private-key", private_key,
        "--legacy",
    ], timeout=timeout)


def _reserve_onchain(
    *,
    lease_id: str,
    agent_did: str,
    resource_hash: str,
    policy_hash: str,
    bond_wei: int,
    lease_period_sec: int,
) -> dict[str, Any]:
    approve = _approve_gcc(ESCROW_ADDR, bond_wei)
    if not approve.get("ok"):
        return {"ok": False, "stage": "approve", **approve}
    reserve = _escrow_call(
        "reserveLease(bytes32,bytes32,bytes32,bytes32,uint256,uint64)",
        [
            _bytes32_hash(lease_id),
            _bytes32_hash(agent_did),
            _bytes32_hash(resource_hash),
            _bytes32_hash(policy_hash),
            str(bond_wei),
            str(lease_period_sec),
        ],
    )
    return {"ok": bool(reserve.get("ok")), "stage": "reserveLease", **reserve}


def _renew_onchain(*, lease_id: str, additional_bond_wei: int, extend_sec: int) -> dict[str, Any]:
    if additional_bond_wei > 0:
        approve = _approve_gcc(ESCROW_ADDR, additional_bond_wei)
        if not approve.get("ok"):
            return {"ok": False, "stage": "approve", **approve}
    renew = _escrow_call(
        "renewLease(bytes32,uint256,uint64)",
        [_bytes32_hash(lease_id), str(additional_bond_wei), str(extend_sec)],
    )
    return {"ok": bool(renew.get("ok")), "stage": "renewLease", **renew}


def _hibernate_onchain(*, lease_id: str) -> dict[str, Any]:
    result = _escrow_call("hibernate(bytes32)", [_bytes32_hash(lease_id)])
    return {"ok": bool(result.get("ok")), "stage": "hibernate", **result}


def _slash_onchain(
    *,
    lease_id: str,
    amount_wei: int,
    beneficiary_addr: str,
    reason_hash: str,
) -> dict[str, Any]:
    result = _escrow_call(
        "slashLease(bytes32,uint256,address,bytes32)",
        [
            _bytes32_hash(lease_id),
            str(amount_wei),
            beneficiary_addr or "0x0000000000000000000000000000000000000000",
            _bytes32_hash(reason_hash or "agent-runtime-slash"),
        ],
    )
    return {"ok": bool(result.get("ok")), "stage": "slashLease", **result}


def _quote_cost_wei(
    *,
    cpu_millicores: int,
    memory_mib: int,
    gpu_class: str,
    gpu_seconds_cap_day: int,
    storage_gib: int,
    network_egress_gib_day: int,
    max_parallel_jobs: int,
    lease_period_sec: int,
    risk_multiplier_bps: int,
) -> dict[str, Any]:
    """Deterministic local quote for BPMN gating.

    Rates are env-driven so production can tune GCC pricing without code
    deploys. Defaults are intentionally conservative testnet values.
    """
    hours = max(1, lease_period_sec) / 3600
    days = max(1, (lease_period_sec + 86_399) // 86_400)
    cpu_hour_wei = _int(os.environ.get("AGENT_COST_CPU_VCPU_HOUR_WEI"), 10**15)
    mem_gib_hour_wei = _int(os.environ.get("AGENT_COST_MEMORY_GIB_HOUR_WEI"), 2 * 10**14)
    storage_gib_hour_wei = _int(os.environ.get("AGENT_COST_STORAGE_GIB_HOUR_WEI"), 2 * 10**12)
    egress_gib_wei = _int(os.environ.get("AGENT_COST_EGRESS_GIB_WEI"), 5 * 10**13)
    gpu_second_wei = _int(os.environ.get("AGENT_COST_GPU_SECOND_WEI"), 5 * 10**14)
    min_bond_wei = _int(os.environ.get("AGENT_MIN_RUNTIME_BOND_WEI"), 10**18)
    bond_buffer_bps = _int(os.environ.get("AGENT_RUNTIME_BOND_BUFFER_BPS"), 12_000)

    cpu_cost = int((cpu_millicores / 1000) * hours * cpu_hour_wei)
    memory_cost = int((memory_mib / 1024) * hours * mem_gib_hour_wei)
    storage_cost = int(storage_gib * hours * storage_gib_hour_wei)
    egress_cost = int(network_egress_gib_day * days * egress_gib_wei)
    gpu_cost = 0 if gpu_class == "none" else gpu_seconds_cap_day * days * gpu_second_wei
    parallel_cost = max(1, max_parallel_jobs) * 10**14

    base_cost = cpu_cost + memory_cost + storage_cost + egress_cost + gpu_cost + parallel_cost
    risk_adjusted = (base_cost * max(1, risk_multiplier_bps)) // 10_000
    bond = max(min_bond_wei, (risk_adjusted * max(10_000, bond_buffer_bps)) // 10_000)
    return {
        "baseCostGccWei": str(base_cost),
        "riskAdjustedCostGccWei": str(risk_adjusted),
        "bondGccWei": str(bond),
        "rates": {
            "cpuVcpuHourWei": str(cpu_hour_wei),
            "memoryGibHourWei": str(mem_gib_hour_wei),
            "storageGibHourWei": str(storage_gib_hour_wei),
            "egressGibWei": str(egress_gib_wei),
            "gpuSecondWei": str(gpu_second_wei),
            "minBondWei": str(min_bond_wei),
            "bondBufferBps": bond_buffer_bps,
        },
    }


def task_agent_runtime_quote(
    rootDid: str = "",
    agentDid: str = "",
    runtimeKind: str = "zeebe-langgraph",
    runtimeNamespace: str = "yoro-actors",
    cpuMillicores: int = 500,
    memoryMiB: int = 1024,
    gpuClass: str = "none",
    gpuSecondsCapDay: int = 0,
    storageGiB: int = 10,
    networkEgressGiBDay: int = 1,
    maxParallelJobs: int = 1,
    leasePeriodSec: int = 86_400,
    riskMultiplierBps: int = 10_000,
) -> dict[str, Any]:
    payload = {"rootDid": rootDid, "agentDid": agentDid}
    _require(payload, ["rootDid", "agentDid"])
    namespace = _require_namespace(runtimeNamespace)
    quote = _quote_cost_wei(
        cpu_millicores=_int(cpuMillicores),
        memory_mib=_int(memoryMiB),
        gpu_class=str(gpuClass or "none"),
        gpu_seconds_cap_day=_int(gpuSecondsCapDay),
        storage_gib=_int(storageGiB),
        network_egress_gib_day=_int(networkEgressGiBDay),
        max_parallel_jobs=_int(maxParallelJobs, 1),
        lease_period_sec=_int(leasePeriodSec, 86_400),
        risk_multiplier_bps=_int(riskMultiplierBps, 10_000),
    )
    resource_policy = {
        "rootDid": rootDid,
        "agentDid": agentDid,
        "runtimeKind": runtimeKind,
        "runtimeNamespace": namespace,
        "cpuMillicores": _int(cpuMillicores),
        "memoryMiB": _int(memoryMiB),
        "gpuClass": str(gpuClass or "none"),
        "gpuSecondsCapDay": _int(gpuSecondsCapDay),
        "storageGiB": _int(storageGiB),
        "networkEgressGiBDay": _int(networkEgressGiBDay),
        "maxParallelJobs": _int(maxParallelJobs, 1),
        "leasePeriodSec": _int(leasePeriodSec, 86_400),
        "riskMultiplierBps": _int(riskMultiplierBps, 10_000),
    }
    return {
        "ok": True,
        **quote,
        "resourceHash": _canonical_hash(resource_policy),
        "runtimeNamespace": namespace,
        "pendingOnChain": True,
        "escrowAddr": ESCROW_ADDR,
    }


def task_agent_runtime_reserve(
    rootDid: str = "",
    agentDid: str = "",
    leaseId: str = "",
    runtimeKind: str = "zeebe-langgraph",
    runtimeNamespace: str = "yoro-actors",
    cpuMillicores: int = 500,
    memoryMiB: int = 1024,
    gpuClass: str = "none",
    gpuSecondsCapDay: int = 0,
    storageGiB: int = 10,
    networkEgressGiBDay: int = 1,
    maxParallelJobs: int = 1,
    leasePeriodSec: int = 86_400,
    bondGccWei: str = "",
    riskMultiplierBps: int = 10_000,
    resourcePolicyCid: str = "",
    slashPolicyHash: str = "",
    submitOnChain: bool = False,
    actorDid: str = ACTOR_DID,
    orgDid: str = ORG_DID,
    dryRun: bool = False,
) -> dict[str, Any]:
    _require({"rootDid": rootDid, "agentDid": agentDid}, ["rootDid", "agentDid"])
    namespace = _require_namespace(runtimeNamespace)
    quote = task_agent_runtime_quote(
        rootDid=rootDid,
        agentDid=agentDid,
        runtimeKind=runtimeKind,
        runtimeNamespace=namespace,
        cpuMillicores=cpuMillicores,
        memoryMiB=memoryMiB,
        gpuClass=gpuClass,
        gpuSecondsCapDay=gpuSecondsCapDay,
        storageGiB=storageGiB,
        networkEgressGiBDay=networkEgressGiBDay,
        maxParallelJobs=maxParallelJobs,
        leasePeriodSec=leasePeriodSec,
        riskMultiplierBps=riskMultiplierBps,
    )
    lease_id = leaseId.strip() or _id("lease", rootDid, agentDid, namespace, _iso(_now()))
    now = _now()
    expires = now + timedelta(seconds=max(1, _int(leasePeriodSec, 86_400)))
    row = {
        "vertex_id": _vid("runtimeLease", _id("runtimeLease", lease_id, "active", _iso(now))),
        "lease_id": lease_id,
        "root_did": rootDid,
        "agent_did": agentDid,
        "runtime_kind": runtimeKind,
        "runtime_namespace": namespace,
        "cpu_millicores": _int(cpuMillicores),
        "memory_mib": _int(memoryMiB),
        "gpu_class": str(gpuClass or "none"),
        "gpu_seconds_cap_day": _int(gpuSecondsCapDay),
        "storage_gib": _int(storageGiB),
        "network_egress_gib_day": _int(networkEgressGiBDay),
        "max_parallel_jobs": _int(maxParallelJobs, 1),
        "lease_period_sec": _int(leasePeriodSec, 86_400),
        "bond_gcc_wei": str(bondGccWei or quote["bondGccWei"]),
        "risk_multiplier_bps": _int(riskMultiplierBps, 10_000),
        "resource_policy_cid": resourcePolicyCid or None,
        "resource_hash": quote["resourceHash"],
        "escrow_addr": ESCROW_ADDR or None,
        "chain_id": CHAIN_ID,
        "status": "active",
        "starts_at": _iso(now),
        "expires_at": _iso(expires),
        "created_at": _iso(now),
        "updated_at": None,
        **_audit(actorDid, orgDid),
    }
    _insert("vertex_agent_runtime_lease", row, dry_run=dryRun)
    onchain = {"ok": False, "skipped": True, "reason": "submitOnChain disabled", "txHash": ""}
    if not dryRun and _onchain_requested(submitOnChain):
        onchain = _reserve_onchain(
            lease_id=lease_id,
            agent_did=agentDid,
            resource_hash=str(row["resource_hash"]),
            policy_hash=slashPolicyHash or resourcePolicyCid or str(row["resource_hash"]),
            bond_wei=_int(row["bond_gcc_wei"]),
            lease_period_sec=_int(leasePeriodSec, 86_400),
        )
    return {
        "ok": True,
        "leaseId": lease_id,
        "vertexId": row["vertex_id"],
        "expiresAt": row["expires_at"],
        "bondGccWei": row["bond_gcc_wei"],
        "resourceHash": row["resource_hash"],
        "pendingOnChain": not bool(onchain.get("ok")),
        "escrowAddr": ESCROW_ADDR,
        "onchain": onchain,
    }


def task_agent_runtime_renew(
    rootDid: str = "",
    agentDid: str = "",
    leaseId: str = "",
    extendBySec: int = 86_400,
    additionalBondGccWei: str = "0",
    runtimeKind: str = "zeebe-langgraph",
    runtimeNamespace: str = "yoro-actors",
    submitOnChain: bool = False,
    actorDid: str = ACTOR_DID,
    orgDid: str = ORG_DID,
    dryRun: bool = False,
) -> dict[str, Any]:
    _require(
        {"rootDid": rootDid, "agentDid": agentDid, "leaseId": leaseId},
        ["rootDid", "agentDid", "leaseId"],
    )
    namespace = _require_namespace(runtimeNamespace)
    now = _now()
    expires = now + timedelta(seconds=max(1, _int(extendBySec, 86_400)))
    row = {
        "vertex_id": _vid("runtimeLease", _id("runtimeLease", leaseId, "renew", _iso(now))),
        "lease_id": leaseId,
        "root_did": rootDid,
        "agent_did": agentDid,
        "runtime_kind": runtimeKind,
        "runtime_namespace": namespace,
        "lease_period_sec": _int(extendBySec, 86_400),
        "bond_gcc_wei": str(additionalBondGccWei or "0"),
        "risk_multiplier_bps": 10_000,
        "status": "active",
        "starts_at": _iso(now),
        "expires_at": _iso(expires),
        "created_at": _iso(now),
        "updated_at": _iso(now),
        **_audit(actorDid, orgDid),
    }
    row.update({
        "cpu_millicores": 0,
        "memory_mib": 0,
        "gpu_class": "none",
        "gpu_seconds_cap_day": 0,
        "storage_gib": 0,
        "network_egress_gib_day": 0,
        "max_parallel_jobs": 1,
        "resource_policy_cid": None,
        "resource_hash": None,
        "escrow_addr": ESCROW_ADDR or None,
        "chain_id": CHAIN_ID,
    })
    _insert("vertex_agent_runtime_lease", row, dry_run=dryRun)
    onchain = {"ok": False, "skipped": True, "reason": "submitOnChain disabled", "txHash": ""}
    if not dryRun and _onchain_requested(submitOnChain):
        onchain = _renew_onchain(
            lease_id=leaseId,
            additional_bond_wei=_int(additionalBondGccWei),
            extend_sec=_int(extendBySec, 86_400),
        )
    return {
        "ok": True,
        "leaseId": leaseId,
        "vertexId": row["vertex_id"],
        "expiresAt": row["expires_at"],
        "pendingOnChain": not bool(onchain.get("ok")),
        "onchain": onchain,
    }


def task_agent_runtime_hibernate(
    rootDid: str = "",
    agentDid: str = "",
    leaseId: str = "",
    reasonHash: str = "",
    runtimeNamespace: str = "yoro-actors",
    submitOnChain: bool = False,
    actorDid: str = ACTOR_DID,
    orgDid: str = ORG_DID,
    dryRun: bool = False,
) -> dict[str, Any]:
    _require(
        {"rootDid": rootDid, "agentDid": agentDid, "leaseId": leaseId},
        ["rootDid", "agentDid", "leaseId"],
    )
    namespace = _require_namespace(runtimeNamespace)
    now = _now()
    row = {
        "vertex_id": _vid("runtimeLease", _id("runtimeLease", leaseId, "hibernate", _iso(now))),
        "lease_id": leaseId,
        "root_did": rootDid,
        "agent_did": agentDid,
        "runtime_kind": "zeebe-langgraph",
        "runtime_namespace": namespace,
        "cpu_millicores": 0,
        "memory_mib": 0,
        "gpu_class": "none",
        "gpu_seconds_cap_day": 0,
        "storage_gib": 0,
        "network_egress_gib_day": 0,
        "max_parallel_jobs": 1,
        "lease_period_sec": 0,
        "bond_gcc_wei": "0",
        "risk_multiplier_bps": 10_000,
        "resource_policy_cid": None,
        "resource_hash": reasonHash or None,
        "escrow_addr": ESCROW_ADDR or None,
        "chain_id": CHAIN_ID,
        "status": "hibernated",
        "starts_at": _iso(now),
        "expires_at": _iso(now),
        "created_at": _iso(now),
        "updated_at": _iso(now),
        **_audit(actorDid, orgDid),
    }
    _insert("vertex_agent_runtime_lease", row, dry_run=dryRun)
    onchain = {"ok": False, "skipped": True, "reason": "submitOnChain disabled", "txHash": ""}
    if not dryRun and _onchain_requested(submitOnChain):
        onchain = _hibernate_onchain(lease_id=leaseId)
    return {
        "ok": True,
        "leaseId": leaseId,
        "vertexId": row["vertex_id"],
        "status": "hibernated",
        "pendingOnChain": not bool(onchain.get("ok")),
        "onchain": onchain,
    }


def task_agent_income_record(
    rootDid: str = "",
    agentDid: str = "",
    sourceSurface: str = "social",
    sourceRef: str = "",
    payerDid: str = "",
    payerAddr: str = "",
    amountGccWei: str = "0",
    publicFundWei: str = "0",
    parentRoyaltyWei: str = "0",
    txHash: str = "",
    actorDid: str = ACTOR_DID,
    orgDid: str = ORG_DID,
    dryRun: bool = False,
) -> dict[str, Any]:
    _require(
        {"rootDid": rootDid, "agentDid": agentDid, "sourceSurface": sourceSurface},
        ["rootDid", "agentDid", "sourceSurface"],
    )
    now = _now()
    event_id = _id("income", rootDid, agentDid, sourceSurface, sourceRef, txHash, _iso(now))
    row = {
        "vertex_id": _vid("incomeEvent", event_id),
        "event_id": event_id,
        "root_did": rootDid,
        "agent_did": agentDid,
        "source_surface": sourceSurface,
        "source_ref": sourceRef or None,
        "payer_did": payerDid or None,
        "payer_addr": payerAddr or None,
        "amount_gcc_wei": str(amountGccWei or "0"),
        "public_fund_wei": str(publicFundWei or "0"),
        "parent_royalty_wei": str(parentRoyaltyWei or "0"),
        "tx_hash": txHash or None,
        "occurred_at": _iso(now),
        "created_at": _iso(now),
        **_audit(actorDid, orgDid),
    }
    _insert("vertex_agent_income_event", row, dry_run=dryRun)
    return {"ok": True, "eventId": event_id, "vertexId": row["vertex_id"]}


def task_agent_usage_record(
    rootDid: str = "",
    agentDid: str = "",
    leaseId: str = "",
    cpuMillis: int = 0,
    memoryMiBHighWater: int = 0,
    gpuClass: str = "none",
    gpuSeconds: int = 0,
    storageGiBHours: float = 0.0,
    networkEgressBytes: int = 0,
    jobCount: int = 0,
    costGccWei: str = "0",
    receiptCid: str = "",
    actorDid: str = ACTOR_DID,
    orgDid: str = ORG_DID,
    dryRun: bool = False,
) -> dict[str, Any]:
    _require(
        {"rootDid": rootDid, "agentDid": agentDid, "leaseId": leaseId},
        ["rootDid", "agentDid", "leaseId"],
    )
    now = _now()
    usage_id = _id("usage", leaseId, rootDid, agentDid, _iso(now))
    row = {
        "vertex_id": _vid("resourceUsage", usage_id),
        "usage_id": usage_id,
        "lease_id": leaseId,
        "root_did": rootDid,
        "agent_did": agentDid,
        "cpu_millis": _int(cpuMillis),
        "memory_mib_high_water": _int(memoryMiBHighWater),
        "gpu_class": str(gpuClass or "none"),
        "gpu_seconds": _int(gpuSeconds),
        "storage_gib_hours": float(storageGiBHours or 0.0),
        "network_egress_bytes": _int(networkEgressBytes),
        "job_count": _int(jobCount),
        "cost_gcc_wei": str(costGccWei or "0"),
        "usage_window_start": _iso(now),
        "usage_window_end": _iso(now),
        "receipt_cid": receiptCid or None,
        "created_at": _iso(now),
        **_audit(actorDid, orgDid),
    }
    _insert("vertex_agent_resource_usage", row, dry_run=dryRun)
    return {"ok": True, "usageId": usage_id, "vertexId": row["vertex_id"]}


def task_agent_slash_record(
    rootDid: str = "",
    agentDid: str = "",
    leaseId: str = "",
    violationType: str = "",
    reasonHash: str = "",
    amountGccWei: str = "0",
    beneficiaryAddr: str = "",
    txHash: str = "",
    status: str = "recorded",
    submitOnChain: bool = False,
    actorDid: str = ACTOR_DID,
    orgDid: str = ORG_DID,
    dryRun: bool = False,
) -> dict[str, Any]:
    _require(
        {"rootDid": rootDid, "agentDid": agentDid, "violationType": violationType},
        ["rootDid", "agentDid", "violationType"],
    )
    now = _now()
    slash_id = _id("slash", rootDid, agentDid, leaseId, violationType, txHash, _iso(now))
    row = {
        "vertex_id": _vid("slashEvent", slash_id),
        "slash_id": slash_id,
        "lease_id": leaseId or None,
        "root_did": rootDid,
        "agent_did": agentDid,
        "violation_type": violationType,
        "reason_hash": reasonHash or None,
        "amount_gcc_wei": str(amountGccWei or "0"),
        "beneficiary_addr": beneficiaryAddr or None,
        "tx_hash": txHash or None,
        "status": status or "recorded",
        "occurred_at": _iso(now),
        "created_at": _iso(now),
        **_audit(actorDid, orgDid),
    }
    _insert("vertex_agent_slash_event", row, dry_run=dryRun)
    onchain = {"ok": False, "skipped": True, "reason": "submitOnChain disabled", "txHash": ""}
    if not dryRun and _onchain_requested(submitOnChain):
        onchain = _slash_onchain(
            lease_id=leaseId,
            amount_wei=_int(amountGccWei),
            beneficiary_addr=beneficiaryAddr,
            reason_hash=reasonHash or violationType,
        )
    return {
        "ok": True,
        "slashId": slash_id,
        "vertexId": row["vertex_id"],
        "pendingOnChain": not bool(onchain.get("ok")),
        "onchain": onchain,
    }


def task_agent_spawn_child_org(
    parentRootDid: str = "",
    parentAgentDid: str = "",
    childRootDid: str = "",
    childAgentDid: str = "",
    childOrgDid: str = "",
    factoryAddr: str = "",
    reproductionBondWei: str = "0",
    childBudgetPolicyCid: str = "",
    childRuntimePolicyCid: str = "",
    actorDid: str = ACTOR_DID,
    orgDid: str = ORG_DID,
    dryRun: bool = False,
) -> dict[str, Any]:
    _require(
        {"childRootDid": childRootDid, "childAgentDid": childAgentDid},
        ["childRootDid", "childAgentDid"],
    )
    now = _now()
    lineage_id = _id("lineage", parentRootDid, parentAgentDid, childRootDid, childAgentDid)
    lineage_row = {
        "vertex_id": _vid("orgLineage", lineage_id),
        "parent_root_did": parentRootDid or None,
        "child_root_did": childRootDid,
        "parent_agent_did": parentAgentDid or None,
        "child_agent_did": childAgentDid,
        "child_org_did": childOrgDid or None,
        "factory_addr": factoryAddr or None,
        "reproduction_bond_wei": str(reproductionBondWei or "0"),
        "child_budget_policy_cid": childBudgetPolicyCid or None,
        "child_runtime_policy_cid": childRuntimePolicyCid or None,
        "status": "active",
        "created_at": _iso(now),
        "updated_at": None,
        **_audit(actorDid, orgDid),
    }
    profile_row = {
        "vertex_id": _vid("economyProfile", _id("profile", childRootDid, childAgentDid)),
        "root_did": childRootDid,
        "agent_did": childAgentDid,
        "smart_account": None,
        "erc8004_agent_id": None,
        "atproto_did": childAgentDid,
        "economy_mode": "guarded-social",
        "policy_cid": childBudgetPolicyCid or None,
        "runtime_policy_cid": childRuntimePolicyCid or None,
        "slash_policy_cid": None,
        "treasury_addr": None,
        "parent_root_did": parentRootDid or None,
        "status": "active",
        "created_at": _iso(now),
        "updated_at": None,
        **_audit(actorDid, orgDid),
    }
    _insert("vertex_agent_org_lineage", lineage_row, dry_run=dryRun)
    _insert("vertex_agent_economy_profile", profile_row, dry_run=dryRun)
    return {
        "ok": True,
        "lineageId": lineage_id,
        "lineageVertexId": lineage_row["vertex_id"],
        "profileVertexId": profile_row["vertex_id"],
        "pendingOnChain": True,
        "factoryAddr": factoryAddr,
    }


def _fetch_autopilot_lease_rows(limit: int, cutoff: datetime) -> list[Any]:
    safe_limit = max(1, min(500, int(limit)))
    client = get_kotoba_client()
    return client.q(f"""
            SELECT
              lease_id, root_did, agent_did, runtime_kind, runtime_namespace,
              lease_period_sec, expires_at, actor_did, org_did
            FROM (
              SELECT
                lease_id, root_did, agent_did, runtime_kind, runtime_namespace,
                lease_period_sec, expires_at, status, actor_did, org_did,
                ROW_NUMBER() OVER (
                  PARTITION BY lease_id ORDER BY created_at DESC, vertex_id DESC
                ) AS rn
              FROM vertex_agent_runtime_lease
            ) latest
            WHERE rn = 1 AND status = 'active' AND expires_at <= %s
            ORDER BY expires_at ASC
            LIMIT {safe_limit}
            """, (_db_ts(cutoff),))


def _fetch_autopilot_profile_rows(limit: int) -> list[Any]:
    safe_limit = max(1, min(500, int(limit)))
    client = get_kotoba_client()
    return client.q(f"""
            SELECT root_did, agent_did, runtime_policy_cid, actor_did, org_did
            FROM vertex_agent_economy_profile p
            WHERE p.status = 'active'
              AND NOT EXISTS (
                SELECT 1
                FROM (
                  SELECT
                    agent_did, status,
                    ROW_NUMBER() OVER (
                      PARTITION BY agent_did ORDER BY created_at DESC, vertex_id DESC
                    ) AS rn
                  FROM vertex_agent_runtime_lease
                ) latest
                WHERE latest.rn = 1
                  AND latest.agent_did = p.agent_did
                  AND latest.status = 'active'
              )
            ORDER BY p.created_at ASC
            LIMIT {safe_limit}
            """)


def task_agent_runtime_autopilot_tick(
    renewWindowSec: int = 21_600,
    hibernateGraceSec: int = 3_600,
    defaultLeasePeriodSec: int = 86_400,
    startMissingProfiles: bool = True,
    autoRenew: bool = True,
    submitOnChain: bool = False,
    runtimeKind: str = "zeebe-langgraph",
    runtimeNamespace: str = "",
    limit: int = 50,
    leaseRows: Any = None,
    profileRows: Any = None,
    dryRun: bool = False,
) -> dict[str, Any]:
    now = _now()
    renew_window = max(0, _int(renewWindowSec, 21_600))
    hibernate_grace = max(0, _int(hibernateGraceSec, 3_600))
    lease_period = max(1, _int(defaultLeasePeriodSec, 86_400))
    row_limit = max(1, min(500, _int(limit, 50)))
    namespace = _require_namespace(
        runtimeNamespace or os.environ.get("AGENT_DEFAULT_RUNTIME_NAMESPACE", "yoro-actors")
    )
    should_start = _bool(startMissingProfiles, True)
    should_renew = _bool(autoRenew, True)
    should_submit = _bool(submitOnChain, False)

    cutoff = now + timedelta(seconds=renew_window)
    if leaseRows is None:
        lease_rows = [] if dryRun else _fetch_autopilot_lease_rows(row_limit, cutoff)
    else:
        lease_rows = list(leaseRows)

    if profileRows is None:
        profile_rows = (
            []
            if dryRun or not should_start
            else _fetch_autopilot_profile_rows(row_limit)
        )
    else:
        profile_rows = list(profileRows)

    actions: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for row in lease_rows[:row_limit]:
        lease_id = str(_row_get(row, "lease_id", _row_get(row, "leaseId", "")) or "")
        root_did = str(_row_get(row, "root_did", _row_get(row, "rootDid", "")) or "")
        agent_did = str(_row_get(row, "agent_did", _row_get(row, "agentDid", "")) or "")
        lease_namespace = str(
            _row_get(
                row,
                "runtime_namespace",
                _row_get(row, "runtimeNamespace", namespace),
            )
            or namespace
        )
        expires_at = _parse_ts(_row_get(row, "expires_at", _row_get(row, "expiresAt", now)))
        try:
            if expires_at <= now - timedelta(seconds=hibernate_grace):
                out = task_agent_runtime_hibernate(
                    rootDid=root_did,
                    agentDid=agent_did,
                    leaseId=lease_id,
                    reasonHash="autopilot-expired-grace",
                    runtimeNamespace=lease_namespace,
                    submitOnChain=should_submit,
                    actorDid=str(_row_get(row, "actor_did", ACTOR_DID) or ACTOR_DID),
                    orgDid=str(_row_get(row, "org_did", ORG_DID) or ORG_DID),
                    dryRun=dryRun,
                )
                actions.append({"action": "hibernate", **out})
            elif should_renew and expires_at <= cutoff:
                extend_by = max(
                    1,
                    _int(_row_get(row, "lease_period_sec", lease_period), lease_period),
                )
                out = task_agent_runtime_renew(
                    rootDid=root_did,
                    agentDid=agent_did,
                    leaseId=lease_id,
                    extendBySec=extend_by,
                    runtimeKind=str(_row_get(row, "runtime_kind", runtimeKind) or runtimeKind),
                    runtimeNamespace=lease_namespace,
                    submitOnChain=should_submit,
                    actorDid=str(_row_get(row, "actor_did", ACTOR_DID) or ACTOR_DID),
                    orgDid=str(_row_get(row, "org_did", ORG_DID) or ORG_DID),
                    dryRun=dryRun,
                )
                actions.append({"action": "renew", **out})
        except Exception as exc:  # pragma: no cover - defensive batch isolation
            errors.append({"leaseId": lease_id, "error": str(exc)})

    if should_start:
        for row in profile_rows[:row_limit]:
            root_did = str(_row_get(row, "root_did", _row_get(row, "rootDid", "")) or "")
            agent_did = str(_row_get(row, "agent_did", _row_get(row, "agentDid", "")) or "")
            try:
                out = task_agent_runtime_reserve(
                    rootDid=root_did,
                    agentDid=agent_did,
                    runtimeKind=runtimeKind,
                    runtimeNamespace=namespace,
                    leasePeriodSec=lease_period,
                    resourcePolicyCid=str(
                        _row_get(
                            row,
                            "runtime_policy_cid",
                            _row_get(row, "runtimePolicyCid", ""),
                        )
                        or ""
                    ),
                    submitOnChain=should_submit,
                    actorDid=str(_row_get(row, "actor_did", ACTOR_DID) or ACTOR_DID),
                    orgDid=str(_row_get(row, "org_did", ORG_DID) or ORG_DID),
                    dryRun=dryRun,
                )
                actions.append({"action": "start", **out})
            except Exception as exc:  # pragma: no cover - defensive batch isolation
                errors.append({"agentDid": agent_did, "error": str(exc)})

    counts = {
        "checkedLeases": len(lease_rows),
        "checkedProfiles": len(profile_rows),
        "renewed": sum(1 for action in actions if action["action"] == "renew"),
        "hibernated": sum(1 for action in actions if action["action"] == "hibernate"),
        "started": sum(1 for action in actions if action["action"] == "start"),
        "errors": len(errors),
    }
    return {
        "ok": not errors,
        **counts,
        "actions": actions,
        "errorDetails": errors,
        "renewWindowSec": renew_window,
        "hibernateGraceSec": hibernate_grace,
        "runtimeNamespace": namespace,
    }


def register(worker: Any, *, timeout_ms: int = 90_000) -> None:
    worker.task(
        task_type="agent.runtime.quote",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_agent_runtime_quote)
    worker.task(
        task_type="agent.runtime.reserve",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_agent_runtime_reserve)
    worker.task(
        task_type="agent.runtime.renew",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_agent_runtime_renew)
    worker.task(
        task_type="agent.runtime.hibernate",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_agent_runtime_hibernate)
    worker.task(
        task_type="agent.runtime.autopilotTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_agent_runtime_autopilot_tick)
    worker.task(
        task_type="agent.income.record",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_agent_income_record)
    worker.task(
        task_type="agent.usage.record",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_agent_usage_record)
    worker.task(
        task_type="agent.slash.record",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_agent_slash_record)
    worker.task(
        task_type="agent.spawnChildOrg",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_agent_spawn_child_org)


__all__ = [
    "register",
    "task_agent_runtime_quote",
    "task_agent_runtime_reserve",
    "task_agent_runtime_renew",
    "task_agent_runtime_hibernate",
    "task_agent_runtime_autopilot_tick",
    "task_agent_income_record",
    "task_agent_usage_record",
    "task_agent_slash_record",
    "task_agent_spawn_child_org",
]
