"""ADR-2604281400 Phase 2 — contribution royalty primitives.

Two entry points:
  emit_contribution_usage()     — called by any actor after each billable event
                                  (inference, render, deploy) to record usage.
  distribute_royalties_task()   — LangServer task (contribution.distributeRoyalties)
                                  called by the daily BPMN timer. Reads
                                  mv_contribution_royalty_daily rows, builds
                                  sourceHashes[] + amounts[] arrays, then
                                  submits GCC.approve() + ContributionRoyaltyRegistry.credit()
                                  via `cast send` (same pattern as ActorRuntimeRegistry).

Environment variables:
  RW_URL                   — RisingWave connection string (same as rest of worker)
  ETH_RPC_URL              — https://geth.etzhayyim.com
  PRIVATE_KEY              — sealer EOA private key (oracle on ContributionRoyaltyRegistry)
  GCC_ADDR                 — 0x8e9A5162b2800E0D19acC1708A531A3954900E21
  CONTRIBUTION_REGISTRY_ADDR — 0x689706981d7D10D4CC8244C2BF1a4cA8b0f67cD7
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import hashlib
import logging
import os
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from kotodama.langserver_compat import LangServerWorker

from kotodama.kotoba_datomic import get_kotoba_client
LOG = logging.getLogger("contribution_royalty")

# ── env ────────────────────────────────────────────────────────────────────

_ETH_RPC_URL = os.environ.get("ETH_RPC_URL", "https://geth.etzhayyim.com").strip()
_GCC_ADDR = os.environ.get("GCC_ADDR", "0x8e9A5162b2800E0D19acC1708A531A3954900E21").strip()
_REGISTRY_ADDR = os.environ.get(
    "CONTRIBUTION_REGISTRY_ADDR",
    "0x689706981d7D10D4CC8244C2BF1a4cA8b0f67cD7",
).strip()

_ACTOR_DID = "did:web:bpmn.etzhayyim.com"
_ORG_DID = "anon"

# Maximum batch size for a single credit() call to stay inside block gas limit
_MAX_BATCH = 200


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _keccak256_hex(canonical_id: str) -> str:
    """Compute keccak256(canonical_id). Requires pysha3 or eth_hash."""
    try:
        from eth_hash.auto import keccak  # type: ignore[import-untyped]
        return "0x" + keccak(canonical_id.encode()).hex()
    except ImportError:
        # Fallback: sha3_256 (not keccak; acceptable for dev/test only)
        LOG.warning("eth_hash unavailable; using sha3-256 as keccak256 stand-in")
        return "0x" + hashlib.sha3_256(canonical_id.encode()).hexdigest()


# ── Usage emit ──────────────────────────────────────────────────────────────

def emit_contribution_usage(
    *,
    source_hash: str,
    consumer_did: str,
    usage_type: str,
    gcc_value_wei: str = "0",
    actor_did: str = _ACTOR_DID,
    org_did: str = _ORG_DID,
) -> dict[str, Any]:
    """Insert one usage event into vertex_contribution_usage.

    Caller is responsible for computing the correct source_hash via
    keccak256(canonical_id) to match ContributionRoyaltyRegistry.contributors.
    gcc_value_wei = "0" is valid for free-tier usage (we still log it).
    """
    from kotodama.primitives.ipfs_ingest import _generate_tid  # local TID helper
    tid = _generate_tid()
    vertex_id = (
        f"at://did:web:contribution.etzhayyim.com"
        f"/com.etzhayyim.apps.contribution.usage/{tid}"
    )
    used_at = _utc_now_iso()
    try:
        get_kotoba_client().insert_row("vertex_contribution_usage", {
            "vertex_id": vertex_id,
            "source_hash": source_hash,
            "consumer_did": consumer_did,
            "usage_type": usage_type,
            "gcc_value_wei": gcc_value_wei,
            "used_at": used_at,
            "actor_did": actor_did,
            "org_did": org_did,
        })
        return {"ok": True, "vertex_id": vertex_id}
    except Exception as exc:  # noqa: BLE001
        LOG.error("emit_contribution_usage failed: %s", exc)
        return {"ok": False, "error": str(exc)}


# ── On-chain distribute via cast send ─────────────────────────────────────

async def _cast_send(args: list[str], *, timeout: float = 60.0) -> dict[str, Any]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except FileNotFoundError:
        return {"ok": False, "error": "cast not found in PATH"}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "cast send timed out"}
    out = (stdout or b"").decode(errors="replace")
    err = (stderr or b"").decode(errors="replace")
    ok = proc.returncode == 0
    tx_hash = ""
    for line in out.splitlines():
        if "transactionHash" in line or line.strip().startswith("0x") and len(line.strip()) == 66:
            tx_hash = line.split()[-1].strip()
            break
    return {"ok": ok, "txHash": tx_hash, "stdout": out[-1000:], "stderr": err[-500:]}


async def _erc20_approve(spender: str, amount_wei: int, private_key: str) -> dict[str, Any]:
    """Call GCC.approve(spender, amount) so the registry can pull tokens."""
    return await _cast_send([
        "cast", "send", _GCC_ADDR,
        f"approve(address,uint256)",
        spender, str(amount_wei),
        "--rpc-url", _ETH_RPC_URL,
        "--private-key", private_key,
        "--legacy",
    ])


async def _registry_credit(
    source_hashes: list[str],
    amounts: list[int],
    private_key: str,
) -> dict[str, Any]:
    """Call ContributionRoyaltyRegistry.credit(bytes32[], uint256[])."""
    hashes_arg = "[" + ",".join(source_hashes) + "]"
    amounts_arg = "[" + ",".join(str(a) for a in amounts) + "]"
    return await _cast_send([
        "cast", "send", _REGISTRY_ADDR,
        "credit(bytes32[],uint256[])",
        hashes_arg, amounts_arg,
        "--rpc-url", _ETH_RPC_URL,
        "--private-key", private_key,
        "--legacy",
    ])


# ── BPMN task: contribution.distributeRoyalties ───────────────────────────

async def distribute_royalties_task(royalty_rows: Any = None) -> dict[str, Any]:
    """Pyzeebe handler for contribution.distributeRoyalties.

    Input (from BPMN generic.db.select output):
      royalty_rows — list of dicts with source_hash, contributor_addr, total_earned_wei

    Steps:
      1. Filter rows where contributor_addr is set and earned > 0
      2. Aggregate by source_hash (MV may already group, but be defensive)
      3. ERC-20 approve registry for total amount
      4. ContributionRoyaltyRegistry.credit(hashes, amounts) in batches of _MAX_BATCH
    """
    private_key = os.environ.get("PRIVATE_KEY", "").strip()
    if not private_key:
        return {"ok": False, "error": "PRIVATE_KEY env not set"}

    rows: list[dict] = royalty_rows if isinstance(royalty_rows, list) else []
    if not rows:
        return {"ok": True, "txHash": "", "totalWei": "0", "rowsCredit": 0, "skipped": True}

    # Aggregate: source_hash → earned_wei
    aggregated: dict[str, int] = {}
    for row in rows:
        sh = (row.get("source_hash") or "").strip()
        addr = (row.get("contributor_addr") or "").strip()
        earned = row.get("total_earned_wei") or row.get("earned_wei") or 0
        try:
            earned_int = int(float(str(earned)))
        except (ValueError, TypeError):
            earned_int = 0
        # Only credit rows where registry has a contributor address registered
        if sh and addr and earned_int > 0:
            aggregated[sh] = aggregated.get(sh, 0) + earned_int

    if not aggregated:
        return {"ok": True, "txHash": "", "totalWei": "0", "rowsCredit": 0, "skipped": True}

    source_hashes = list(aggregated.keys())
    amounts = [aggregated[sh] for sh in source_hashes]
    total_wei = sum(amounts)

    # Step 1: approve registry to pull total GCC
    approve_result = await _erc20_approve(_REGISTRY_ADDR, total_wei, private_key)
    if not approve_result["ok"]:
        LOG.error("GCC approve failed: %s", approve_result.get("stderr", ""))
        return {
            "ok": False,
            "error": f"approve failed: {approve_result.get('stderr', '')[-200:]}",
            "txHash": "",
            "totalWei": str(total_wei),
            "rowsCredit": 0,
        }

    # Step 2: credit in batches
    last_tx = ""
    rows_credited = 0
    for i in range(0, len(source_hashes), _MAX_BATCH):
        batch_hashes = source_hashes[i : i + _MAX_BATCH]
        batch_amounts = amounts[i : i + _MAX_BATCH]
        result = await _registry_credit(batch_hashes, batch_amounts, private_key)
        if not result["ok"]:
            LOG.error("credit() batch %d failed: %s", i // _MAX_BATCH, result.get("stderr", ""))
            return {
                "ok": False,
                "error": f"credit batch failed: {result.get('stderr', '')[-200:]}",
                "txHash": result.get("txHash", ""),
                "totalWei": str(total_wei),
                "rowsCredit": rows_credited,
            }
        last_tx = result.get("txHash", "")
        rows_credited += len(batch_hashes)

    LOG.info(
        "contribution.distributeRoyalties done: rows=%d totalWei=%d txHash=%s",
        rows_credited, total_wei, last_tx,
    )
    return {
        "ok": True,
        "txHash": last_tx,
        "totalWei": str(total_wei),
        "rowsCredit": rows_credited,
    }


# ── Source registration (off-chain DB write) ──────────────────────────────

def register_source_task(
    *,
    canonical_id: str,
    contributor_addr: str,
    source_type: str,
    royalty_bps: int = 100,
    description: str = "",
    license: str = "",
    actor_did: str = _ACTOR_DID,
    org_did: str = _ORG_DID,
) -> dict[str, Any]:
    """Write one contribution source row to vertex_contribution_source.

    Computes sourceHash = keccak256(canonicalId) locally.  The Safe owner
    must separately call ContributionRoyaltyRegistry.registerSource() on-chain
    to activate earnings; until then the daily credit() batch accumulates
    wei in pendingEarned.
    """
    from kotodama.primitives.ipfs_ingest import _generate_tid

    source_hash = _keccak256_hex(canonical_id)
    tid = _generate_tid()
    vertex_id = (
        f"at://did:web:contribution.etzhayyim.com"
        f"/com.etzhayyim.apps.contribution.source/{tid}"
    )
    created_at = _utc_now_iso()
    try:
        get_kotoba_client().insert_row("vertex_contribution_source", {
            "vertex_id": vertex_id,
            "source_hash": source_hash,
            "canonical_id": canonical_id,
            "source_type": source_type,
            "contributor_addr": contributor_addr.lower(),
            "royalty_bps": royalty_bps,
            "description": description or '',
            "license": license or '',
            "created_at": created_at,
            "actor_did": actor_did,
            "org_did": org_did,
        })
        LOG.info("contribution.registerSource: sourceHash=%s vertexId=%s", source_hash, vertex_id)
        return {
            "ok": True,
            "sourceHash": source_hash,
            "vertexId": vertex_id,
            "pendingOnChain": True,
        }
    except Exception as exc:  # noqa: BLE001
        LOG.error("contribution.registerSource failed: %s", exc)
        return {"ok": False, "sourceHash": source_hash, "vertexId": "", "error": str(exc)}


# ── Zeebe registration ─────────────────────────────────────────────────────

def register(worker: "LangServerWorker", *, timeout_ms: int = 300_000) -> None:
    """Register contribution.* Zeebe tasks on *worker*."""

    @worker.task(task_type="contribution.registerSource")
    async def _register_source(
        canonicalId: str = "",
        contributorAddr: str = "",
        sourceType: str = "",
        royaltyBps: int = 100,
        description: str = "",
        license: str = "",
    ) -> dict:
        return register_source_task(
            canonical_id=canonicalId,
            contributor_addr=contributorAddr,
            source_type=sourceType,
            royalty_bps=royaltyBps,
            description=description,
            license=license,
        )

    @worker.task(task_type="contribution.distributeRoyalties")
    async def _distribute(royalty_rows: Any = None) -> dict:
        return await distribute_royalties_task(royalty_rows=royalty_rows)
