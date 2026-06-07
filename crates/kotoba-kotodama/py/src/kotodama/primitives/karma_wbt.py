"""Karma WBT (Well-Becoming Token) settlement primitives.

Backs the rebirth.forfeit primitive (currently stub) plus generic
WBT transfer between organism DIDs. Phase K1 ledger:

  - balance per DID in vertex_karma_wbt_balance
  - append-only log in vertex_karma_wbt_transfer (content-addressed PK)
  - singleton commons pool in vertex_karma_commons_pool

Pyzeebe task types:
  karma.wbt.balanceGet      query balance + stats for a DID
  karma.wbt.transfer        atomic debit + credit + log
  karma.wbt.forfeitToCommons forfeit entire balance to commons pool
                              (called from karma.rebirth.forfeit)
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import time
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("karma.wbt")

KARMA_DID = "did:web:karma.etzhayyim.com"
COMMONS_DID = "did:web:karma.etzhayyim.com:commons"
COMMONS_VERTEX_ID = "commons-pool"

VALID_REASONS = ("transfer", "forfeit", "tax", "tip", "settlement", "refund")


# ── Helpers ────────────────────────────────────────────────────────────


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_ts() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _content_addressed_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f"{prefix}-{digest[:24]}"


def _balance_vertex_id(did: str) -> str:
    return f"wbt-bal-{hashlib.sha256(did.encode()).hexdigest()[:32]}"


def _read_balance_row(did: str) -> dict[str, Any] | None:
    client = get_kotoba_client()
    row = client.select_first_where(
        "vertex_karma_wbt_balance",
        "did",
        did,
        columns=[
            "vertex_id", "balance", "total_inflow", "total_outflow",
            "tx_count", "last_tx_ts_ms", "last_tx_id",
        ],
    )
    if not row:
        return None
    row["balance"] = float(row.get("balance") or 0.0)
    row["total_inflow"] = float(row.get("total_inflow") or 0.0)
    row["total_outflow"] = float(row.get("total_outflow") or 0.0)
    row["tx_count"] = int(row.get("tx_count") or 0)
    row["last_tx_ts_ms"] = int(row.get("last_tx_ts_ms") or 0)
    row["last_tx_id"] = row.get("last_tx_id") or ""
    return row


def _upsert_balance(
    did: str,
    new_balance: float,
    delta: float,
    is_inflow: bool,
    tx_id: str,
    ts_ms: int,
) -> None:
    """Idempotent upsert. Kotoba Datom log semantics: insert_row handles
    upsert on vertex_id.
    """
    client = get_kotoba_client()
    existing = _read_balance_row(did)

    today_iso = _dt.datetime.now(tz=_dt.UTC).date().isoformat()
    created_at = _now_ts()

    if existing is None:
        vertex_id = _balance_vertex_id(did)
        total_inflow = abs(delta) if is_inflow else 0.0
        total_outflow = abs(delta) if not is_inflow else 0.0
        tx_count = 1
        # New record, so provide all default values
        balance_row_dict = {
            "vertex_id": vertex_id,
            # "_seq": None, # Handled by Datomic
            "created_date": today_iso,
            "sensitivity_ord": 1,
            "owner_did": did,
            "did": did,
            "balance": new_balance,
            "last_tx_ts_ms": ts_ms,
            "last_tx_id": tx_id,
            "total_inflow": total_inflow,
            "total_outflow": total_outflow,
            "tx_count": tx_count,
            "created_at": created_at,
            "org_id": did,
            "user_id": did,
            "actor_id": "karma.wbt.upsertBalance",
        }
    else:
        # Existing record, update relevant fields
        vertex_id = existing["vertex_id"] # Use existing vertex_id for upsert
        total_inflow = existing["total_inflow"] + (abs(delta) if is_inflow else 0.0)
        total_outflow = existing["total_outflow"] + (abs(delta) if not is_inflow else 0.0)
        tx_count = existing["tx_count"] + 1

        balance_row_dict = {
            "vertex_id": vertex_id,
            "balance": new_balance,
            "last_tx_ts_ms": ts_ms,
            "last_tx_id": tx_id,
            "total_inflow": total_inflow,
            "total_outflow": total_outflow,
            "tx_count": tx_count,
            # Preserve other existing fields that are not changed
            "created_date": existing["created_date"],
            "sensitivity_ord": existing["sensitivity_ord"],
            "owner_did": existing["owner_did"],
            "did": existing["did"],
            "created_at": existing["created_at"],
            "org_id": existing["org_id"],
            "user_id": existing["user_id"],
            "actor_id": existing["actor_id"],
            # "_seq": existing.get("_seq"), # Keep existing _seq if present, but handled by Datomic
        }

    client.insert_row("vertex_karma_wbt_balance", balance_row_dict)


def _bump_commons_pool(amount: float, source_did: str, is_forfeit: bool, ts_ms: int) -> None:
    client = get_kotoba_client()
    
    existing_pool = client.select_first_where(
        "vertex_karma_commons_pool",
        "vertex_id",
        COMMONS_VERTEX_ID,
        columns=[
            "total_balance", "total_inflow", "forfeit_inflow_count",
            "tax_inflow_count", "last_inflow_ts_ms", "last_inflow_did",
            "created_at", "org_id", "user_id", "actor_id",
            "created_date", "sensitivity_ord", "owner_did",
        ],
    )

    current_balance = float(existing_pool.get("total_balance", 0.0)) if existing_pool else 0.0
    current_inflow = float(existing_pool.get("total_inflow", 0.0)) if existing_pool else 0.0
    current_forfeit_count = int(existing_pool.get("forfeit_inflow_count", 0)) if existing_pool else 0
    current_tax_count = int(existing_pool.get("tax_inflow_count", 0)) if existing_pool else 0

    new_total_balance = current_balance + amount
    new_total_inflow = current_inflow + amount
    new_forfeit_inflow_count = current_forfeit_count + (1 if is_forfeit else 0)
    new_tax_inflow_count = current_tax_count + (0 if is_forfeit else 1)

    final_pool_row_dict = {
        "vertex_id": COMMONS_VERTEX_ID,
        "total_balance": new_total_balance,
        "total_inflow": new_total_inflow,
        "forfeit_inflow_count": new_forfeit_inflow_count,
        "tax_inflow_count": new_tax_inflow_count,
        "last_inflow_ts_ms": ts_ms,
        "last_inflow_did": source_did,
    }

    if existing_pool:
        for key in ["created_at", "org_id", "user_id", "actor_id", "created_date", "sensitivity_ord", "owner_did"]:
            if key not in final_pool_row_dict and existing_pool.get(key) is not None:
                final_pool_row_dict[key] = existing_pool[key]
    else:
        final_pool_row_dict.update({
            "created_at": _now_ts(),
            "org_id": COMMONS_DID,
            "user_id": COMMONS_DID,
            "actor_id": "karma.wbt.commons",
            "created_date": _dt.datetime.now(tz=_dt.UTC).date().isoformat(),
            "sensitivity_ord": 1,
            "owner_did": COMMONS_DID,
        })
    
    client.insert_row("vertex_karma_commons_pool", final_pool_row_dict)


def _record_transfer(
    transfer_id: str,
    from_did: str,
    to_did: str,
    amount: float,
    reason: str,
    memo: str,
    is_forfeit: bool,
    ts_ms: int,
) -> None:
    client = get_kotoba_client()
    today_iso = _dt.datetime.now(tz=_dt.UTC).date().isoformat()
    created_at = _now_ts()
    vertex_id = f"wbt-tx-{transfer_id}"

    transfer_row_dict = {
        "vertex_id": vertex_id,
        # "_seq": None, # Handled by Datomic
        "created_date": today_iso,
        "sensitivity_ord": 1,
        "owner_did": from_did, # Owner DID is from_did for this record
        "transfer_id": transfer_id,
        "from_did": from_did,
        "to_did": to_did,
        "amount": amount,
        "reason": reason,
        "memo": memo,
        "is_forfeit": is_forfeit,
        "is_inflow": True, # This column is always true in the original INSERT
        "ts_ms": ts_ms,
        "created_at": created_at,
        "org_id": from_did,
        "user_id": from_did,
        "actor_id": "karma.wbt.transfer",
    }
    client.insert_row("vertex_karma_wbt_transfer", transfer_row_dict)


# ── Task: balance get ──────────────────────────────────────────────────


async def task_karma_wbt_balance_get(**kwargs: Any) -> dict[str, Any]:
    did = kwargs["did"]
    is_commons = did == COMMONS_DID
    client = get_kotoba_client()

    if is_commons:
        commons_pool_row = client.select_first_where(
            "vertex_karma_commons_pool",
            "vertex_id",
            COMMONS_VERTEX_ID,
            columns=[
                "total_balance", "total_inflow", "last_inflow_ts_ms"
            ]
        )
        if not commons_pool_row:
            return {
                "did": did, "balance": 0.0, "totalInflow": 0.0, "totalOutflow": 0.0,
                "txCount": 0, "lastTxTsMs": 0, "lastTxId": "", "isCommons": True,
            }
        return {
            "did": did,
            "balance": float(commons_pool_row.get("total_balance") or 0.0),
            "totalInflow": float(commons_pool_row.get("total_inflow") or 0.0),
            "totalOutflow": 0.0,
            "txCount": 0,
            "lastTxTsMs": int(commons_pool_row.get("last_inflow_ts_ms") or 0),
            "lastTxId": "",
            "isCommons": True,
        }

    bal = _read_balance_row(did)
    if bal is None:
        return {
            "did": did, "balance": 0.0, "totalInflow": 0.0, "totalOutflow": 0.0,
            "txCount": 0, "lastTxTsMs": 0, "lastTxId": "", "isCommons": False,
        }
    return {
        "did": did,
        "balance": bal["balance"],
        "totalInflow": bal["total_inflow"],
        "totalOutflow": bal["total_outflow"],
        "txCount": bal["tx_count"],
        "lastTxTsMs": bal["last_tx_ts_ms"],
        "lastTxId": bal["last_tx_id"],
        "isCommons": False,
    }


# ── Task: transfer (atomic debit + credit + log) ───────────────────────


async def task_karma_wbt_transfer(**kwargs: Any) -> dict[str, Any]:
    from_did = kwargs["fromDid"]
    to_did = kwargs["toDid"]
    amount = float(kwargs["amount"])
    reason = (kwargs.get("reason") or "transfer").lower()
    memo = kwargs.get("memo") or ""

    if reason not in VALID_REASONS:
        raise ValueError(f"karma.wbt.transfer: invalid reason {reason}")
    if amount < 0:
        raise ValueError("karma.wbt.transfer: invalid-amount")
    if from_did == to_did:
        raise ValueError("karma.wbt.transfer: self-transfer")

    is_forfeit = reason == "forfeit"
    is_to_commons = to_did == COMMONS_DID
    ts_ms = _now_ms()
    nonce = uuid.uuid4().hex
    transfer_id = _content_addressed_id(
        "transfer", from_did, to_did, str(amount), reason, str(ts_ms), nonce
    )

    from_bal = _read_balance_row(from_did)
    if from_bal is None or from_bal["balance"] < amount:
        raise ValueError("insufficient-funds")

    new_from_balance = from_bal["balance"] - amount

    # Append transfer log first (immutable record).
    _record_transfer(transfer_id, from_did, to_did, amount, reason, memo, is_forfeit, ts_ms)

    # Debit sender.
    _upsert_balance(from_did, new_from_balance, amount, is_inflow=False, tx_id=transfer_id, ts_ms=ts_ms)

    # Credit receiver: if commons, bump pool singleton; else upsert balance.
    if is_to_commons:
        _bump_commons_pool(amount, from_did, is_forfeit, ts_ms)
        new_to_balance = -1.0  # signal: commons pool — query separately
    else:
        to_bal = _read_balance_row(to_did)
        new_to_balance = (to_bal["balance"] if to_bal else 0.0) + amount
        _upsert_balance(to_did, new_to_balance, amount, is_inflow=True, tx_id=transfer_id, ts_ms=ts_ms)

    return {
        "transferId": transfer_id,
        "fromBalance": new_from_balance,
        "toBalance": new_to_balance,
        "tsMs": ts_ms,
    }


# ── Task: forfeit-to-commons (called from rebirth.forfeit) ─────────────


async def task_karma_wbt_forfeit_to_commons(**kwargs: Any) -> dict[str, Any]:
    """Move entire balance of `did` to commons pool. Idempotent: if
    balance already 0, returns 0 with no transfer recorded."""
    did = kwargs["did"]
    if did == COMMONS_DID:
        raise ValueError("commons cannot forfeit to itself")

    bal = _read_balance_row(did)
    if bal is None or bal["balance"] <= 0:
        return {"wbtForfeited": 0.0, "transferId": ""}
    amount = bal["balance"]

    # Delegate to general transfer for atomicity.
    result = await task_karma_wbt_transfer(
        fromDid=did,
        toDid=COMMONS_DID,
        amount=amount,
        reason="forfeit",
        memo=f"rebirth-forfeit:{did}",
    )
    return {"wbtForfeited": amount, "transferId": result["transferId"]}


# ── Worker registration ────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 30_000) -> None:
    """Register WBT settlement task types.

      task_type="karma.wbt.balanceGet"
      task_type="karma.wbt.transfer"
      task_type="karma.wbt.forfeitToCommons"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("karma.wbt.balanceGet",        task_karma_wbt_balance_get,        ms=15_000)
    t("karma.wbt.transfer",          task_karma_wbt_transfer,           ms=30_000)
    t("karma.wbt.forfeitToCommons",  task_karma_wbt_forfeit_to_commons, ms=30_000)


__all__ = [
    "register",
    "task_karma_wbt_balance_get",
    "task_karma_wbt_transfer",
    "task_karma_wbt_forfeit_to_commons",
    "COMMONS_DID",
]
