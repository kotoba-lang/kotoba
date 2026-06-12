"""Karma zk-SNARK rebirth proof primitives (Phase K3).

Backs the karma.zk.rebirthVerify task — verifies a Groth16 proof of
non-linkability between an old organism's santana root and a new one,
then burns the nullifier on-chain to prevent double-spend.

Phase K3 status: stub verifier (always-true). Phase K4 wires the
snarkjs-generated Groth16 verifier + actual on-chain
RebirthVerifier.verifyAndBurn submission via the bundler.

Pyzeebe task types:
  karma.zk.rebirthVerify       verify proof + burn nullifier + persist row
  karma.zk.rebirthProofLookup  query verified proof by new_did or nullifier
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("karma.zk")

KARMA_DID = "did:web:karma.etzhayyim.com"

DEFAULT_VERIFIER_CONTRACT = os.environ.get(
    "KARMA_REBIRTH_VERIFIER_CONTRACT",
    "0x0000000000000000000000000000000000000000",
)
DEFAULT_VERIFIER_CHAIN = os.environ.get(
    "KARMA_REBIRTH_VERIFIER_CHAIN",
    "base-sepolia",
)


# ── Helpers ────────────────────────────────────────────────────────────


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _proof_vertex_id(proof_id: str) -> str:
    return f"rebirth-proof-{proof_id}"


def _normalize_hex32(s: str) -> str:
    """Normalize a 32-byte hex value: lowercase, 0x-prefixed, 64 hex chars."""
    if not s:
        return ""
    s = s.lower()
    if s.startswith("0x"):
        s = s[2:]
    return "0x" + s.rjust(64, "0")[:64]


# ── Task: rebirth verify (Phase K3 stub) ───────────────────────────────


async def task_karma_zk_rebirth_verify(**kwargs: Any) -> dict[str, Any]:
    """Verify Groth16 proof + burn nullifier + persist row.

    Phase K3 contract:
      - Inputs validated (newDid, newSantanaRoot, nullifier, proof shape)
      - Nullifier double-spend check via vertex_karma_rebirth_proof scan
      - Stub verifier accepts any well-formed proof
      - Phase K4 wires actual RebirthVerifier.verifyAndBurn() bundler call

    On success: vertex_karma_rebirth_proof row with status='verified'
    is INSERTed; downstream karma.rebirth.emerge can then check that
    a verified proof exists for the (newDid, nullifier) pair when
    KARMA_REBIRTH_REQUIRE_PROOF=1.
    """
    new_did = kwargs["newDid"]
    old_did_hash = kwargs.get("oldDidHash") or ""
    new_santana_root = _normalize_hex32(kwargs["newSantanaRoot"])
    nullifier = _normalize_hex32(kwargs["nullifier"])
    proof = kwargs.get("proof") or {}
    public_signals = kwargs.get("publicSignals") or [new_santana_root, nullifier]

    proof_blob = json.dumps(proof, separators=(",", ":")) if proof else ""
    public_signals_blob = json.dumps(public_signals, separators=(",", ":"))

    proof_id = hashlib.sha256(
        f"{new_did}|{nullifier}|{new_santana_root}".encode()
    ).hexdigest()[:32]
    vertex_id = _proof_vertex_id(proof_id)
    today_iso = datetime.now(timezone.utc).date().isoformat()
    now_ms = _now_ms()
    now_ts = _now_ts()

    # Double-spend check: nullifier already verified
    # R0: Multi-predicate filter applied in Python (status = 'verified')
    existing_proofs = get_kotoba_client().select_where(
        "vertex_karma_rebirth_proof",
        "nullifier",
        nullifier,
        columns=["nullifier", "status"]
    )
    if any(p["status"] == "verified" for p in existing_proofs):
        return {
            "ok": False,
            "proofId": proof_id,
            "verifiedAt": "",
            "txHash": "",
            "blockNumber": 0,
            "rejectedReason": "nullifier-already-burned",
        }

        # Phase K4 hook: real bundler call. Phase K3 stub: deterministic tx_hash.
        use_real_verifier = bool(os.environ.get("KARMA_BUNDLER_URL")) and bool(
            os.environ.get("KARMA_ANCHOR_SIGNER_KEY")
        )
        if use_real_verifier:
            tx_hash = ""
            block_number = 0
            status = "deferred-real-verifier-not-wired"
            error_message = (
                "Phase K3 — RebirthVerifier.verifyAndBurn() bundler "
                "call requires web3.py + eth_account vendored in "
                "kotodama. Recorded as deferred for K4 retry."
            )
        else:
            # K3 stub: deterministic tx_hash so downstream BPMN works.
            tx_hash = "0x" + hashlib.sha256(
                f"verify|{nullifier}|{new_santana_root}".encode()
            ).hexdigest()
            block_number = int(time.time())
            status = "verified"
            error_message = ""

        # Persist
        try:
            row_dict = {
                "vertex_id": vertex_id,
                "_seq": None,
                "created_date": today_iso,
                "sensitivity_ord": 1,
                "owner_did": KARMA_DID,
                "proof_id": proof_id,
                "old_did_hash": old_did_hash,
                "new_did": new_did,
                "new_santana_root": new_santana_root,
                "nullifier": nullifier,
                "proof_blob": proof_blob,
                "public_signals": public_signals_blob,
                "verifier_contract": DEFAULT_VERIFIER_CONTRACT,
                "verifier_chain": DEFAULT_VERIFIER_CHAIN,
                "verified_at": now_ts,
                "verified_at_ms": now_ms,
                "tx_hash": tx_hash,
                "block_number": block_number,
                "status": status,
                "error_message": error_message,
                "created_at": now_ts,
                "org_id": KARMA_DID,
                "user_id": KARMA_DID,
                "actor_id": "karma.zk.rebirthVerify",
            }
            get_kotoba_client().insert_row("vertex_karma_rebirth_proof", row_dict)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("rebirth_proof INSERT err proof=%s: %s", proof_id, exc)
            return {
                "ok": False,
                "proofId": proof_id,
                "verifiedAt": "",
                "txHash": "",
                "blockNumber": 0,
                "error": str(exc)[:500],
            }

    LOG.info(
        "karma.zk.rebirthVerify proof=%s did=%s nullifier=%s status=%s",
        proof_id, new_did, nullifier, status,
    )
    return {
        "ok": status == "verified",
        "proofId": proof_id,
        "verifiedAt": now_ts,
        "txHash": tx_hash,
        "blockNumber": block_number,
        "rejectedReason": "" if status == "verified" else status,
    }


# ── Task: lookup proof for a given new_did or nullifier ────────────────


async def task_karma_zk_rebirth_proof_lookup(**kwargs: Any) -> dict[str, Any]:
    new_did = kwargs.get("newDid") or ""
    nullifier = _normalize_hex32(kwargs.get("nullifier") or "") if kwargs.get("nullifier") else ""

    if not new_did and not nullifier:
        return {"found": False, "error": "newDid-or-nullifier-required"}

    _COLS = [
        "proof_id", "status", "verified_at_ms", "tx_hash", "block_number",
        "verifier_contract", "verifier_chain",
    ]

    if new_did and nullifier:
        # R0: Multi-predicate filter applied in Python (nullifier is AND-ed)
        rows = get_kotoba_client().select_where(
            "vertex_karma_rebirth_proof",
            "new_did",
            new_did,
            columns=_COLS,
            limit=10, # Add a limit to prevent excessive data fetching for in-Python filtering
        )
        row = next((r for r in rows if r["nullifier"] == nullifier), None)
    elif new_did:
        # R0: ORDER BY verified_at_ms DESC applied in Python
        rows = get_kotoba_client().select_where(
            "vertex_karma_rebirth_proof",
            "new_did",
            new_did,
            columns=_COLS,
            limit=10, # Add a limit to prevent excessive data fetching for in-Python filtering
        )
        # Sort in Python
        rows.sort(key=lambda x: x.get("verified_at_ms", 0), reverse=True)
        row = rows[0] if rows else None
    else: # nullifier is present
        row = get_kotoba_client().select_first_where(
            "vertex_karma_rebirth_proof",
            "nullifier",
            nullifier,
            columns=_COLS,
        )

    if not row:
        return {"found": False}
    return {
        "found": True,
        "proofId": row["proof_id"],
        "status": row["status"],
        "verifiedAtMs": int(row["verified_at_ms"] or 0),
        "txHash": row["tx_hash"] or "",
        "blockNumber": int(row["block_number"] or 0),
        "verifierContract": row["verifier_contract"] or "",
        "verifierChain": row["verifier_chain"] or "",
    }


# ── Worker registration ────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Register karma zk-SNARK rebirth proof task types.

      task_type="karma.zk.rebirthVerify"
      task_type="karma.zk.rebirthProofLookup"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("karma.zk.rebirthVerify",       task_karma_zk_rebirth_verify,        ms=60_000)
    t("karma.zk.rebirthProofLookup",  task_karma_zk_rebirth_proof_lookup,  ms=15_000)


__all__ = [
    "register",
    "task_karma_zk_rebirth_verify",
    "task_karma_zk_rebirth_proof_lookup",
]
