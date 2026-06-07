"""Karma Filecoin storage deal primitives (Phase K3).

Backs the L4 long-term persistence layer beyond ETH anchor. Each
IPFS-pinned karma CID gets proposed to N=5 Filecoin storage providers
via Estuary / Lighthouse / Web3.Storage HTTP API. Renewal cycle
(R/P30D) re-proposes deals expiring within 30 days.

# Karma.lean karma_5_layer_persistence guarantee — kotoba Datom log / AT-repo
/ IPFS-self / IPFS-ext / Filecoin = 5 layers.

Pyzeebe task types:
  karma.filecoin.proposeBatch    R/PT24H — propose deals for new pinned CIDs
  karma.filecoin.renewExpiring   R/P30D — renew deals expiring < 30d
  karma.filecoin.statusGet       query deal status for a CID
"""

from __future__ import annotations


import hashlib
import logging
import os
import time
import uuid
from datetime import datetime, timezone # Added for kotoba_datomic migration
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client # Replaced db_sync
# from kotodama.db_sync import sync_cursor # Removed

LOG = logging.getLogger("karma.filecoin")

KARMA_DID = "did:web:karma.etzhayyim.com"

# Phase K3: SP list is a static curated list. Phase K4 reads from a
# self-managed SP registry table populated from on-chain Storage
# Provider auctions.
DEFAULT_SP_LIST = [
    "f01000",  # placeholder Filecoin actor IDs
    "f01001",
    "f01002",
    "f01003",
    "f01004",
]

ESTUARY_URL = os.environ.get("KARMA_FILECOIN_ESTUARY_URL", "")
LIGHTHOUSE_URL = os.environ.get("KARMA_FILECOIN_LIGHTHOUSE_URL", "")
WEB3STORAGE_URL = os.environ.get("KARMA_FILECOIN_WEB3STORAGE_URL", "")
DEAL_PROVIDER = os.environ.get("KARMA_FILECOIN_PROVIDER", "estuary")  # estuary|lighthouse|web3storage|stub

DEFAULT_DURATION_DAYS = 540
DEFAULT_BYTES_FALLBACK = 4096
PROPOSAL_BATCH_DEFAULT = 200
RENEWAL_BATCH_DEFAULT = 500


# ── Helpers ────────────────────────────────────────────────────────────


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_ts() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _deal_vertex_id(deal_id: str) -> str:
    return f"filecoin-deal-{deal_id}"


def _deal_id(cid: str, sp_address: str, nonce: str) -> str:
    return hashlib.sha256(f"{cid}|{sp_address}|{nonce}".encode()).hexdigest()[:32]


def _deal_proposal_cid_stub(cid: str, sp_address: str, nonce: str) -> str:
    """Phase K3 stub deal-proposal CID. K4 replaces with the real
    deal proposal hash returned by the SP/Estuary."""
    digest = hashlib.sha256(f"proposal|{cid}|{sp_address}|{nonce}".encode()).hexdigest()
    return f"bafyrei{digest[:52]}"


def _select_sps(count: int) -> list[str]:
    """Select N SPs round-robin from the configured list."""
    if count <= len(DEFAULT_SP_LIST):
        return DEFAULT_SP_LIST[:count]
    return (DEFAULT_SP_LIST * ((count // len(DEFAULT_SP_LIST)) + 1))[:count]


# ── Task: propose batch ────────────────────────────────────────────────


async def task_karma_filecoin_propose_batch(**kwargs: Any) -> dict[str, Any]:
    """Find IPFS-pinned CIDs without active Filecoin deals, propose
    deals at N SPs each. Phase K3 stub: records intent + deterministic
    deal_proposal_cid; the actual Estuary HTTP call is K4.
    """
    batch_size = int(kwargs.get("batchSize") or PROPOSAL_BATCH_DEFAULT)
    sp_count = int(kwargs.get("spCount") or 5)
    duration_days = int(kwargs.get("durationDays") or DEFAULT_DURATION_DAYS)

    proposed = 0
    skipped = 0
    failed = 0

    now_ms = _now_ms()
    now_ts = _now_ts()
    today_iso = datetime.now(tz=timezone.utc).date().isoformat()
    expires_at_ms = now_ms + duration_days * 24 * 60 * 60 * 1000

    kc = get_kotoba_client()
    # R0: Multi-predicate filter with NOT IN, ORDER BY and LIMIT handled in Python.
    ipfs_cids_dicts = kc.select_where("vertex_karma_ipfs_pin", columns=["cid"])
    all_pinned_cids = {d["cid"] for d in ipfs_cids_dicts if d and "cid" in d}

    active_deals_proposed = kc.select_where("vertex_karma_filecoin_deal", "status", "proposed", columns=["cid"])
    active_deals_sealed = kc.select_where("vertex_karma_filecoin_deal", "status", "sealed", columns=["cid"])
    active_deals_active = kc.select_where("vertex_karma_filecoin_deal", "status", "active", columns=["cid"])

    cids_with_active_deals = {d["cid"] for d in active_deals_proposed if d and "cid" in d}
    cids_with_active_deals.update({d["cid"] for d in active_deals_sealed if d and "cid" in d})
    cids_with_active_deals.update({d["cid"] for d in active_deals_active if d and "cid" in d})

    cids = sorted(list(all_pinned_cids - cids_with_active_deals))[:batch_size]

    for cid in cids:
        sps = _select_sps(sp_count)
        for sp in sps:
            nonce = uuid.uuid4().hex
            deal_id = _deal_id(cid, sp, nonce)
            proposal_cid = _deal_proposal_cid_stub(cid, sp, nonce)
            vertex_id = _deal_vertex_id(deal_id)

            provider_endpoint = (
                ESTUARY_URL if DEAL_PROVIDER == "estuary"
                else LIGHTHOUSE_URL if DEAL_PROVIDER == "lighthouse"
                else WEB3STORAGE_URL if DEAL_PROVIDER == "web3storage"
                else ""
            )

            use_real_call = bool(provider_endpoint) and DEAL_PROVIDER != "stub"
            if use_real_call:
                # Phase K4: HTTP POST to provider /deals endpoint
                status = "deferred-real-provider-not-wired"
                error_code = "K3_STUB"
                error_message = (
                    "Phase K3 — real Filecoin deal proposal requires "
                    "py-multiformats / py-cid + provider SDK; recorded "
                    "as deferred for K4 retry."
                )
            else:
                status = "proposed"
                error_code = ""
                error_message = ""

            try:
                deal_data = {
                    "vertex_id": vertex_id,
                    "_seq": None,
                    "created_date": today_iso,
                    "sensitivity_ord": 1,
                    "owner_did": KARMA_DID,
                    "deal_id": deal_id,
                    "cid": cid,
                    "sp_address": sp,
                    "deal_proposal_cid": proposal_cid,
                    "provider_endpoint": provider_endpoint,
                    "bundler_used": DEAL_PROVIDER,
                    "proposed_at": now_ts,
                    "proposed_at_ms": now_ms,
                    "sealed_at": None,
                    "sealed_at_ms": None,
                    "expires_at_ms": expires_at_ms,
                    "duration_days": duration_days,
                    "bytes_size": DEFAULT_BYTES_FALLBACK,
                    "retrieval_url": f"https://{sp}.deal/{deal_id}",
                    "cost_usd_estimate": None,
                    "status": status,
                    "error_code": error_code,
                    "error_message": error_message,
                    "created_at": now_ts,
                    "org_id": KARMA_DID,
                    "user_id": KARMA_DID,
                    "actor_id": "karma.filecoin.proposeBatch",
                }
                kc.insert_row("vertex_karma_filecoin_deal", deal_data)
                if status == "proposed":
                    proposed += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                LOG.warning("filecoin.propose INSERT err cid=%s sp=%s: %s", cid, sp, exc)
                failed += 1

    return {"proposed": proposed, "skipped": skipped, "failed": failed}


# ── Task: renew expiring ───────────────────────────────────────────────


async def task_karma_filecoin_renew_expiring(**kwargs: Any) -> dict[str, Any]:
    """Find deals expiring < 30d, propose fresh deals (same SP if
    possible). Original row stays for audit lineage; new row gets a
    new deal_id."""
    batch_size = int(kwargs.get("batchSize") or RENEWAL_BATCH_DEFAULT)
    new_duration_days = int(kwargs.get("newDurationDays") or DEFAULT_DURATION_DAYS)

    renewed = 0
    skipped = 0
    failed = 0

    now_ms = _now_ms()
    now_ts = _now_ts()
    today_iso = datetime.now(tz=timezone.utc).date().isoformat()
    new_expires_at_ms = now_ms + new_duration_days * 24 * 60 * 60 * 1000

    kc = get_kotoba_client()
    # R0: ORDER BY and LIMIT handled in Python.
    all_expiring_deals = kc.select_where("mv_karma_filecoin_expiring_soon", columns=["cid", "sp_address", "bytes_size", "expires_at_ms"])
    # Sort by expires_at_ms (ascending) and apply limit
    sorted_deals = sorted(all_expiring_deals, key=lambda x: x.get("expires_at_ms", 0))[:batch_size]
    rows = [(d["cid"], d["sp_address"], d["bytes_size"]) for d in sorted_deals]

    for cid, sp, bytes_size in rows:
        nonce = uuid.uuid4().hex
        deal_id = _deal_id(cid, sp, nonce + "-renew")
        proposal_cid = _deal_proposal_cid_stub(cid, sp, nonce + "-renew")
        vertex_id = _deal_vertex_id(deal_id)
        try:
            deal_data = {
                "vertex_id": vertex_id,
                "_seq": None,
                "created_date": today_iso,
                "sensitivity_ord": 1,
                "owner_did": KARMA_DID,
                "deal_id": deal_id,
                "cid": cid,
                "sp_address": sp,
                "deal_proposal_cid": proposal_cid,
                "provider_endpoint": "", # from the VALUES in old code
                "bundler_used": DEAL_PROVIDER,
                "proposed_at": now_ts,
                "proposed_at_ms": now_ms,
                "sealed_at": None,
                "sealed_at_ms": None,
                "expires_at_ms": new_expires_at_ms,
                "duration_days": new_duration_days,
                "bytes_size": int(bytes_size or DEFAULT_BYTES_FALLBACK),
                "retrieval_url": f"https://{sp}.deal/{deal_id}",
                "cost_usd_estimate": None,
                "status": "proposed",
                "error_code": "",
                "error_message": "",
                "created_at": now_ts,
                "org_id": KARMA_DID,
                "user_id": KARMA_DID,
                "actor_id": "karma.filecoin.renewExpiring",
            }
            kc.insert_row("vertex_karma_filecoin_deal", deal_data)
            renewed += 1
        except Exception as exc:  # noqa: BLE001
            LOG.warning("filecoin.renew INSERT err cid=%s sp=%s: %s", cid, sp, exc)
            failed += 1

    return {"renewed": renewed, "skipped": skipped, "failed": failed}


# ── Task: status get ───────────────────────────────────────────────────


async def task_karma_filecoin_status_get(**kwargs: Any) -> dict[str, Any]:
    cid = kwargs["cid"]
    deals: list[dict[str, Any]] = []
    active = 0
    expiring_soon = 0
    soon_threshold_ms = _now_ms() + 30 * 24 * 60 * 60 * 1000

    kc = get_kotoba_client()
    # R0: ORDER BY and LIMIT handled in Python.
    deal_records = kc.select_where(
        "vertex_karma_filecoin_deal",
        "cid",
        cid,
        columns=[
            "deal_id", "sp_address", "status", "sealed_at_ms", "expires_at_ms",
            "bytes_size", "retrieval_url", "proposed_at_ms" # Need proposed_at_ms for sorting
        ]
    )
    # Sort by proposed_at_ms DESC and apply limit
    sorted_deal_records = sorted(deal_records, key=lambda x: x.get("proposed_at_ms", 0), reverse=True)[:50]

    for row in sorted_deal_records:
        deal_id = row.get("deal_id")
        sp = row.get("sp_address")
        status = row.get("status")
        sealed_at_ms = row.get("sealed_at_ms")
        expires_at_ms = row.get("expires_at_ms")
        bytes_size = row.get("bytes_size")
        retrieval_url = row.get("retrieval_url")

        d = {
            "dealId": deal_id,
            "spAddress": sp,
            "status": status,
            "sealedAtMs": int(sealed_at_ms or 0),
            "expiresAtMs": int(expires_at_ms or 0),
            "bytesSize": int(bytes_size or 0),
            "retrievalUrl": retrieval_url or "",
        }
        deals.append(d)
        if status in ("proposed", "sealed", "active"):
            active += 1
            if expires_at_ms and int(expires_at_ms) < soon_threshold_ms:
                expiring_soon += 1

    return {
        "cid": cid,
        "deals": deals,
        "activeDealCount": active,
        "expiringSoonCount": expiring_soon,
    }


# ── Worker registration ────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Register karma Filecoin task types.

      task_type="karma.filecoin.proposeBatch"
      task_type="karma.filecoin.renewExpiring"
      task_type="karma.filecoin.statusGet"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("karma.filecoin.proposeBatch",   task_karma_filecoin_propose_batch,    ms=180_000)
    t("karma.filecoin.renewExpiring",  task_karma_filecoin_renew_expiring,   ms=180_000)
    t("karma.filecoin.statusGet",      task_karma_filecoin_status_get,       ms=15_000)


__all__ = [
    "register",
    "task_karma_filecoin_propose_batch",
    "task_karma_filecoin_renew_expiring",
    "task_karma_filecoin_status_get",
]
