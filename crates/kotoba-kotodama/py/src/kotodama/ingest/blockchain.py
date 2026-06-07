"""Blockchain head-delta ingest tasks for Zeebe workers.

The node pods own chain sync. These helpers only read stable RPC endpoints and
write deterministic kotoba Datom log entries plus the generic ingest cursor.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from datetime import datetime, timezone

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.ingest.core import now_iso, today, upsert_cursor


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _http_json(url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"RPC HTTP {e.code}: {body}") from e
    decoded = json.loads(body.decode("utf-8"))
    if decoded.get("error"):
        raise RuntimeError(f"RPC error: {decoded['error']}")
    return decoded.get("result")


def _bitcoin_rpc(method: str, params: list[Any] | None = None) -> Any:
    url = os.environ.get(
        "BITCOIN_RPC_URL",
        "http://bitcoin-mainnet.blockchain.svc.cluster.local:8332",
    )
    user = os.environ.get("BITCOIN_RPC_USER", "")
    password = os.environ.get("BITCOIN_RPC_PASSWORD", "")
    if not user or not password:
        raise RuntimeError("BITCOIN_RPC_USER/BITCOIN_RPC_PASSWORD are required")
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return _http_json(
        url,
        {"jsonrpc": "1.0", "id": "kotodama-blockchain", "method": method, "params": params or []},
        headers={"Authorization": f"Basic {token}"},
    )


def _ethereum_rpc(method: str, params: list[Any] | None = None) -> Any:
    url = os.environ.get(
        "ETHEREUM_RPC_URL",
        "http://ethereum-mainnet.blockchain.svc.cluster.local:8545",
    )
    return _http_json(
        url,
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
    )


def _get_cursor_height(source_id: str) -> int | None:
    vid = f"at://did:web:ingest.etzhayyim.com/com.etzhayyim.apps.ingest.cursor/blockchain-{source_id}-head"
    try:
        client = get_kotoba_client()
        row = client.select_first_where(
            "vertex_ingest_cursor", "vertex_id", vid, columns=["cursor_value"]
        )
        if not row or row["cursor_value"] is None:
            return None
        return int(str(row["cursor_value"]))
    except Exception:
        def _block_tables_available() -> bool:
            # In Datomic, tables/entities are implicitly available once referenced.
            # This function previously checked for SQLite table existence, which is no longer applicable.
            # Therefore, we assume the equivalent Datomic entities are always available.
            return True


def _insert_actor_landing(row: dict[str, Any], *, kind: str) -> int:
    raw = row.get("raw") or {}
    props = _json_dumps(
        {
            "kind": kind,
            "sourceId": row.get("source_id", ""),
            "height": row.get("height", row.get("block_height")),
            "blockHash": row.get("block_hash", ""),
            "parentHash": row.get("parent_hash", ""),
            "blockTime": row.get("block_time", ""),
            "txHash": row.get("tx_hash", ""),
            "txIndex": row.get("tx_index"),
            "from": row.get("from_addr", ""),
            "to": row.get("to_addr", ""),
            "valueWei": row.get("value_wei", ""),
            "rawSha256": _sha256_text(_json_dumps(raw)),
            "runId": row.get("run_id", ""),
        }
    )
    address = row.get("block_hash") if kind == "block" else row.get("tx_hash")

    client = get_kotoba_client()
    row_dict = {
        "vertex_id": row["vertex_id"],
        "_seq": None,
        "created_date": today(),
        "sensitivity_ord": 0,
        "owner_did": OWNER_DID,
        "rkey": row["vertex_id"][-64:],
        "repo": OWNER_DID,
        "label": f"{kind}:{row.get('height', row.get('block_height', ''))}",
        "did": f"did:web:blockchain.etzhayyim.com:{kind}:{row['vertex_id'][-48:]}",
        "chain": row["chain"],
        "address": address or "",
        "name": row["vertex_id"],
        "balance": 0,
        "total_received": 0,
        "total_sent": 0,
        "tx_count": row.get("tx_count", 0),
        "unconfirmed_tx_count": 0,
        "risk_score": 0.0,
        "source": row.get("source_id", ""),
        "observed_at": now_iso(),
        "props": props,
    }
    client.insert_row("vertex_blockchain_actor", row_dict)
    return 1


def _insert_block(row: dict[str, Any]) -> int:
    if not _block_tables_available():
        return _insert_actor_landing(row, kind="block")
    raw_json = _json_dumps(row.get("raw") or {})
    raw_sha256 = _sha256_text(raw_json)
    now = now_iso()

    client = get_kotoba_client()
    row_dict = {
        "vertex_id": row["vertex_id"],
        "_seq": None,
        "created_date": today(),
        "sensitivity_ord": 0,
        "owner_did": OWNER_DID,
        "chain": row["chain"],
        "source_id": row["source_id"],
        "height": row["height"],
        "block_hash": row["block_hash"],
        "parent_hash": row.get("parent_hash", ""),
        "block_time": row.get("block_time", ""),
        "tx_count": row.get("tx_count", 0),
        "raw_sha256": raw_sha256,
        "raw_json": raw_json,
        "canonical_status": "canonical",
        "ingested_at": now,
        "run_id": row.get("run_id", ""),
    }
    client.insert_row("vertex_blockchain_block", row_dict)
    return 1


def _insert_tx(row: dict[str, Any]) -> int:
    if not _block_tables_available():
        return _insert_actor_landing(row, kind="tx")
    raw_json = _json_dumps(row.get("raw") or {})
    raw_sha256 = _sha256_text(raw_json)
    now = now_iso()

    client = get_kotoba_client()
    row_dict = {
        "vertex_id": row["vertex_id"],
        "_seq": None,
        "created_date": today(),
        "sensitivity_ord": 0,
        "owner_did": OWNER_DID,
        "chain": row["chain"],
        "source_id": row["source_id"],
        "block_hash": row["block_hash"],
        "block_height": row["block_height"],
        "tx_hash": row["tx_hash"],
        "tx_index": row["tx_index"],
        "from_addr": row.get("from_addr", ""),
        "to_addr": row.get("to_addr", ""),
        "value_wei": row.get("value_wei", ""),
        "raw_sha256": raw_sha256,
        "raw_json": raw_json,
        "canonical_status": "canonical",
        "ingested_at": now,
        "run_id": row.get("run_id", ""),
    }
    client.insert_row("vertex_blockchain_tx", row_dict)
    return 1


def ingest_bitcoin_head(*, run_id: str, source_id: str, max_blocks: int) -> dict[str, Any]:
    info = _bitcoin_rpc("getblockchaininfo")
    latest = int(info.get("blocks") or 0)
    cursor = _get_cursor_height(source_id)
    catchup_skipped = False
    if cursor is None:
        start = max(0, latest - max_blocks + 1)
    elif latest - cursor > max(1, int(os.environ.get("BLOCKCHAIN_MAX_CATCHUP_LAG_BLOCKS", "100"))):
        start = max(0, latest - max_blocks + 1)
        catchup_skipped = True
    else:
        start = cursor + 1
    end = min(latest, start + max_blocks - 1)
    if latest <= 0 or start > end:
        upsert_cursor(
            ingest_family="blockchain",
            source_id=source_id,
            shard_key="head",
            cursor_value=str(cursor or 0),
            high_watermark=str(latest),
            status="idle",
        )
        return {
            "ok": True,
            "chain": "bitcoin",
            "latest": latest,
            "blocksRead": 0,
            "transactionsRead": 0,
            "rowsWritten": 0,
        }

    rows_written = 0
    tx_seen = 0
    last_height = cursor or 0
    for height in range(start, end + 1):
        block_hash = _bitcoin_rpc("getblockhash", [height])
        block = _bitcoin_rpc("getblock", [block_hash, 1])
        txs = block.get("tx") or []
        if not _write_head_blocks():
            last_height = height
            continue
        rows_written += _insert_block(
            {
                "vertex_id": f"blockchain:bitcoin-mainnet:block:{height}:{block_hash}",
                "chain": "bitcoin-mainnet",
                "source_id": source_id,
                "height": height,
                "block_hash": block_hash,
                "parent_hash": block.get("previousblockhash") or "",
                "block_time": str(block.get("time") or ""),
                "tx_count": len(txs),
                "run_id": run_id,
                "raw": block,
            }
        )
        tx_limit = max(0, int(os.environ.get("BLOCKCHAIN_INGEST_MAX_TX_PER_BLOCK", "0")))
        for idx, tx_hash in enumerate(txs[:tx_limit] if tx_limit else []):
            tx_seen += 1
            rows_written += _insert_tx(
                {
                    "vertex_id": f"blockchain:bitcoin-mainnet:tx:{tx_hash}",
                    "chain": "bitcoin-mainnet",
                    "source_id": source_id,
                    "block_hash": block_hash,
                    "block_height": height,
                    "tx_hash": tx_hash,
                    "tx_index": idx,
                    "run_id": run_id,
                    "raw": {"txid": tx_hash},
                }
            )
        last_height = height

    upsert_cursor(
        ingest_family="blockchain",
        source_id=source_id,
        shard_key="head",
        cursor_value=str(last_height),
        high_watermark=str(latest),
        content_hash=info.get("bestblockhash"),
        status="running" if bool(info.get("initialblockdownload")) else "synced",
    )
    return {
        "ok": True,
        "chain": "bitcoin",
        "latest": latest,
        "fromHeight": start,
        "toHeight": last_height,
        "blocksRead": max(0, end - start + 1),
        "transactionsRead": tx_seen,
        "rowsWritten": rows_written,
        "initialBlockDownload": bool(info.get("initialblockdownload")),
        "catchupSkipped": catchup_skipped,
        "txLimitPerBlock": max(0, int(os.environ.get("BLOCKCHAIN_INGEST_MAX_TX_PER_BLOCK", "0"))),
        "headBlocksWritten": _write_head_blocks(),
    }


def _hex_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    return int(str(value), 16)


def _write_head_blocks() -> bool:
    return os.environ.get("BLOCKCHAIN_HEAD_WRITE_BLOCKS", "1").lower() in ("1", "true", "on", "yes")


def ingest_ethereum_head(*, run_id: str, source_id: str, max_blocks: int) -> dict[str, Any]:
    latest = _hex_int(_ethereum_rpc("eth_blockNumber"))
    syncing = _ethereum_rpc("eth_syncing")
    cursor = _get_cursor_height(source_id)
    if latest <= 0:
        upsert_cursor(
            ingest_family="blockchain",
            source_id=source_id,
            shard_key="head",
            cursor_value=str(cursor or 0),
            high_watermark=str(latest),
            status="syncing",
        )
        return {
            "ok": True,
            "chain": "ethereum",
            "latest": latest,
            "blocksRead": 0,
            "transactionsRead": 0,
            "rowsWritten": 0,
            "syncing": bool(syncing),
        }

    catchup_skipped = False
    if cursor is None:
        start = max(0, latest - max_blocks + 1)
    elif latest - cursor > max(1, int(os.environ.get("BLOCKCHAIN_MAX_CATCHUP_LAG_BLOCKS", "100"))):
        start = max(0, latest - max_blocks + 1)
        catchup_skipped = True
    else:
        start = cursor + 1
    end = min(latest, start + max_blocks - 1)
    if start > end:
        upsert_cursor(
            ingest_family="blockchain",
            source_id=source_id,
            shard_key="head",
            cursor_value=str(cursor or latest),
            high_watermark=str(latest),
            status="idle",
        )
        return {
            "ok": True,
            "chain": "ethereum",
            "latest": latest,
            "blocksRead": 0,
            "transactionsRead": 0,
            "rowsWritten": 0,
            "syncing": bool(syncing),
        }

    rows_written = 0
    tx_seen = 0
    last_height = cursor or 0
    for height in range(start, end + 1):
        block = _ethereum_rpc("eth_getBlockByNumber", [hex(height), True])
        if not block:
            break
        block_hash = str(block.get("hash") or "")
        txs = block.get("transactions") or []
        if not _write_head_blocks():
            last_height = height
            continue
        rows_written += _insert_block(
            {
                "vertex_id": f"blockchain:ethereum-mainnet:block:{height}:{block_hash}",
                "chain": "ethereum-mainnet",
                "source_id": source_id,
                "height": height,
                "block_hash": block_hash,
                "parent_hash": str(block.get("parentHash") or ""),
                "block_time": str(_hex_int(block.get("timestamp"))),
                "tx_count": len(txs),
                "run_id": run_id,
                "raw": block,
            }
        )
        tx_limit = max(0, int(os.environ.get("BLOCKCHAIN_INGEST_MAX_TX_PER_BLOCK", "0")))
        for idx, tx in enumerate(txs[:tx_limit] if tx_limit else []):
            tx_hash = str(tx.get("hash") or "")
            if not tx_hash:
                continue
            tx_seen += 1
            rows_written += _insert_tx(
                {
                    "vertex_id": f"blockchain:ethereum-mainnet:tx:{tx_hash}",
                    "chain": "ethereum-mainnet",
                    "source_id": source_id,
                    "block_hash": block_hash,
                    "block_height": height,
                    "tx_hash": tx_hash,
                    "tx_index": _hex_int(tx.get("transactionIndex")) if tx.get("transactionIndex") is not None else idx,
                    "from_addr": str(tx.get("from") or ""),
                    "to_addr": str(tx.get("to") or ""),
                    "value_wei": str(_hex_int(tx.get("value"))),
                    "run_id": run_id,
                    "raw": tx,
                }
            )
        last_height = height

    upsert_cursor(
        ingest_family="blockchain",
        source_id=source_id,
        shard_key="head",
        cursor_value=str(last_height),
        high_watermark=str(latest),
        status="syncing" if syncing else "synced",
    )
    return {
        "ok": True,
        "chain": "ethereum",
        "latest": latest,
        "fromHeight": start,
        "toHeight": last_height,
        "blocksRead": max(0, last_height - start + 1),
        "transactionsRead": tx_seen,
        "rowsWritten": rows_written,
        "syncing": syncing,
        "catchupSkipped": catchup_skipped,
        "txLimitPerBlock": max(0, int(os.environ.get("BLOCKCHAIN_INGEST_MAX_TX_PER_BLOCK", "0"))),
        "headBlocksWritten": _write_head_blocks(),
    }


def ingest_head_delta(
    *,
    run_id: str,
    source_id: str,
    input_json: str | None = None,
    max_blocks: int | None = None,
) -> dict[str, Any]:
    try:
        payload = json.loads(input_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except json.JSONDecodeError:
        payload = {}
    resolved_max = int(max_blocks or payload.get("maxBlocks") or os.environ.get("BLOCKCHAIN_INGEST_MAX_BLOCKS", "3"))
    resolved_max = max(1, min(resolved_max, 25))
    started = time.monotonic()
    if source_id == "bitcoin-mainnet":
        out = ingest_bitcoin_head(run_id=run_id, source_id=source_id, max_blocks=resolved_max)
    elif source_id == "ethereum-mainnet":
        out = ingest_ethereum_head(run_id=run_id, source_id=source_id, max_blocks=resolved_max)
    else:
        raise ValueError(f"unsupported blockchain source_id: {source_id}")
    out["latencyMs"] = int((time.monotonic() - started) * 1000)
    return out
