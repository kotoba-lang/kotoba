"""Run one EligibilityCell super-step against a live geth-private (Anvil
or production) and submit ``Phenotype.setMultiplier``.

S2 of ADR-2605172300. The script is intentionally minimal: it threads
CLI args into ``kotodama.eligibility.web3_ports.build_production_ports``,
constructs the cell, and dispatches one ``step()``. Output is a single
JSON object on stdout that an orchestrator (typically
``20-actors/etzhayyim-sdk/test/integration-eligibility.mjs``) can parse.

Usage:
  uv run --no-project --with web3 --with eth-account --with eth-abi \\
      --with eth-utils --with pycryptodome python -m scripts.run_eligibility_step \\
      --rpc http://localhost:8545 \\
      --token-id 1 \\
      --phenotype-address 0x... \\
      --registry-address 0x... \\
      --cell-private-key 0x... \\
      --chain-id 31337 \\
      --epoch 1 \\
      --window-start 0 \\
      --window-end 9999999999
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

# Make the package importable when running from a checkout without an
# installed wheel.
_HERE = Path(__file__).resolve()
_PKG_SRC = _HERE.parent.parent / "src"
if str(_PKG_SRC) not in sys.path:
    sys.path.insert(0, str(_PKG_SRC))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run one EligibilityCell.step")
    p.add_argument("--rpc", required=True, help="geth-private RPC URL")
    p.add_argument("--token-id", required=True, type=int)
    p.add_argument("--phenotype-address", required=True)
    p.add_argument("--registry-address", required=True)
    p.add_argument("--cell-private-key", required=True, help="0x-prefixed hex private key")
    p.add_argument("--chain-id", required=True, type=int)
    p.add_argument("--epoch", type=int, default=1)
    p.add_argument("--window-start", type=int, default=0)
    p.add_argument(
        "--window-end",
        type=int,
        default=0,
        help="Defaults to current unix seconds when omitted",
    )
    p.add_argument(
        "--signature-ttl-secs",
        type=int,
        default=600,
        help="Cell signature TTL (default 600s)",
    )
    args = p.parse_args(argv)

    # Lazy imports — web3 / eth-account / eth-utils only required when
    # this CLI actually runs. The eligibility package itself is
    # importable without them.
    from eth_account import Account  # type: ignore  # noqa: E402
    from web3 import Web3  # type: ignore  # noqa: E402

    from kotodama.eligibility import EligibilityCell
    from kotodama.eligibility.web3_ports import (
        Web3Config,
        build_production_ports,
        cell_config_from,
    )

    cell_acct = Account.from_key(args.cell_private_key)
    # Read the chain's block.timestamp. Anvil's evm_increaseTime warps
    # this far past wall-clock, so signing against `time.time()` would
    # produce an `ExpiredSignature()` revert at the contract's
    # `block.timestamp > expiresAt` check. Use the chain clock instead.
    w3_clock = Web3(Web3.HTTPProvider(args.rpc))
    chain_now = int(w3_clock.eth.get_block("latest").timestamp)
    window_end = args.window_end or chain_now

    cfg = Web3Config(
        rpc_url=args.rpc,
        phenotype_address=args.phenotype_address,
        registry_address=args.registry_address,
        cell_address=cell_acct.address,
        cell_private_key=args.cell_private_key,
        chain_id=args.chain_id,
    )

    ports = build_production_ports(cfg)
    eligibility_cell_cfg = cell_config_from(cfg)
    eligibility_cell_cfg = type(eligibility_cell_cfg)(
        cell_address=eligibility_cell_cfg.cell_address,
        phenotype_address=eligibility_cell_cfg.phenotype_address,
        chain_id=eligibility_cell_cfg.chain_id,
        signature_ttl_secs=args.signature_ttl_secs,
    )

    cell = EligibilityCell(cfg=eligibility_cell_cfg, ports=ports)
    tx_hash = cell.step(
        token_id=args.token_id,
        window_start=args.window_start,
        window_end=window_end,
        epoch=args.epoch,
        now=chain_now,
    )

    print(
        json.dumps(
            {
                "ok": True,
                "tx_hash": tx_hash,
                "cell_address": cell_acct.address,
                "token_id": args.token_id,
                "epoch": args.epoch,
                "window_start": args.window_start,
                "window_end": window_end,
                "ran_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(timespec="seconds"),
            }
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
