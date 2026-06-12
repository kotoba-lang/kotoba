"""web3.py-backed production ports for :class:`EligibilityCell`.

S2 of ADR-2605172300. The cell's :class:`CellPorts` dataclass defines a
minimal I/O surface (load_events, sign, submit_phenotype,
expected_nonce). This module provides a production wiring of those four
ports against:

  - geth-private RPC (web3.py HTTP provider)
  - the deployed :class:`Phenotype` contract (signed ``setMultiplier``)
  - the deployed :class:`AdherentRegistry` contract (``Attested``
    events as the event source for ``load_events``)

The wiring is deliberately thin — the heavy reducer logic lives in
:mod:`kotodama.eligibility.scoring` and is unit-tested independently.

This file imports web3 and eth-account lazily so the eligibility
package remains importable in environments where those wheels aren't
installed (tests, type-check-only runs). Install via the ``eligibility``
optional extra: ``uv pip install '.[eligibility]'``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kotodama.eligibility.cell import CellPorts, EligibilityCellConfig
from kotodama.eligibility.scoring import AttestationEvent


# ─── Minimal ABI fragments (mirrors @etzhayyim/sdk/src/abi.ts) ─────


PHENOTYPE_ABI: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "expectedNonce",
        "stateMutability": "view",
        "inputs": [{"name": "cell", "type": "address"}],
        "outputs": [{"name": "", "type": "uint64"}],
    },
    {
        "type": "function",
        "name": "setMultiplier",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "newBps", "type": "uint16"},
            {"name": "epoch", "type": "uint64"},
            {"name": "nonce", "type": "uint64"},
            {"name": "expiresAt", "type": "uint64"},
            {"name": "evidenceHash", "type": "bytes32"},
            {"name": "cell", "type": "address"},
            {"name": "sig", "type": "bytes"},
        ],
        "outputs": [],
    },
]

ADHERENT_REGISTRY_ABI: list[dict[str, Any]] = [
    {
        "type": "event",
        "name": "Attested",
        "anonymous": False,
        "inputs": [
            {"name": "tokenId", "type": "uint256", "indexed": True},
            {"name": "eventType", "type": "bytes32", "indexed": True},
            {"name": "evidenceCid", "type": "bytes32", "indexed": False},
            {"name": "attestedAt", "type": "uint64", "indexed": False},
        ],
    },
]


# Reverse mapping from keccak256("prayer"/"study"/…) → human label. Kept
# in sync with the SDK's AttestationEventType union and the canonical
# event vocabulary in :mod:`scoring`.
def _build_event_type_map() -> dict[bytes, str]:
    from eth_utils import keccak  # type: ignore

    return {keccak(text=name): name for name in ("prayer", "study", "service", "donation")}


# ─── Builder ─────────────────────────────────────────────────────────


@dataclass
class Web3Config:
    rpc_url: str
    phenotype_address: str            # 0x… on geth-private
    registry_address: str             # 0x… on geth-private
    cell_address: str                 # 0x… EOA whose private key signs
    cell_private_key: str             # 0x… hex private key (use Keychain in prod)
    chain_id: int = 2605
    block_window: int = 50_000        # max blocks scanned per load_events call


def build_production_ports(cfg: Web3Config) -> CellPorts:
    """Construct a :class:`CellPorts` bound to web3.py + eth-account.

    Imports are inside the function so this module is importable without
    web3/eth-account installed; only ``build_production_ports()`` and
    ``run_one_step()`` require the extras.
    """
    try:
        from web3 import Web3  # type: ignore
        from eth_account import Account  # type: ignore
        from eth_account.messages import encode_defunct  # type: ignore
        from eth_utils import keccak  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "kotodama.eligibility.web3_ports requires the `eligibility` extra: "
            "uv pip install -e '.[eligibility]'"
        ) from exc

    w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"web3.py could not connect to {cfg.rpc_url}")

    phenotype = w3.eth.contract(
        address=Web3.to_checksum_address(cfg.phenotype_address),
        abi=PHENOTYPE_ABI,
    )
    registry = w3.eth.contract(
        address=Web3.to_checksum_address(cfg.registry_address),
        abi=ADHERENT_REGISTRY_ABI,
    )
    cell_acct = Account.from_key(cfg.cell_private_key)
    if cell_acct.address.lower() != cfg.cell_address.lower():
        raise RuntimeError(
            f"cell_private_key derives {cell_acct.address} but cell_address is {cfg.cell_address}"
        )

    event_type_map = _build_event_type_map()

    # ── load_events ────────────────────────────────────────────────
    def _load_events(token_id: int, window_start: int, window_end: int) -> list[AttestationEvent]:
        # Map unix timestamps → block range. For a deterministic test
        # fixture against Anvil, we just scan from latest - block_window
        # to latest; production deployments should index Attested
        # events into a queryable store and bypass this raw scan.
        latest = w3.eth.block_number
        from_block = max(0, latest - cfg.block_window)
        event_filter = registry.events.Attested.create_filter(
            from_block=from_block,
            to_block="latest",
            argument_filters={"tokenId": token_id},
        )
        out: list[AttestationEvent] = []
        for evt in event_filter.get_all_entries():
            attested_at = int(evt["args"]["attestedAt"])
            if not (window_start <= attested_at <= window_end):
                continue
            event_type_hash: bytes = bytes(evt["args"]["eventType"])
            label = event_type_map.get(event_type_hash, "unknown")
            evidence: bytes = bytes(evt["args"]["evidenceCid"])
            out.append(
                AttestationEvent(
                    token_id=token_id,
                    event_type=label,
                    evidence_cid=evidence,
                    attested_at=attested_at,
                )
            )
        return out

    # ── sign ───────────────────────────────────────────────────────
    def _sign(inner_hash_then_envelope: bytes) -> bytes:
        # cell.py's _eip191_payload already wraps in
        # keccak("\x19Ethereum Signed Message:\n32" || inner).
        # Account.sign_message(encode_defunct(...)) does the same
        # wrapping, so to avoid double-wrapping we sign the raw `inner`
        # via Account._sign_hash. cell.py's contract is "pass me the
        # final envelope hash" — but in practice this port is given the
        # already-EIP-191-wrapped hash. We unwrap to the inner hash
        # because Account.unsafe_sign_hash signs whatever you give it.
        # The cleanest invariant: cell.step computes the envelope, and
        # this port signs the envelope directly (raw, no extra prefix).
        signed = Account._sign_hash(inner_hash_then_envelope, cfg.cell_private_key)
        return bytes(signed.signature)

    # ── expected_nonce ────────────────────────────────────────────
    def _expected_nonce() -> int:
        return int(phenotype.functions.expectedNonce(cell_acct.address).call())

    # ── submit_phenotype ──────────────────────────────────────────
    def _submit_phenotype(
        token_id: int,
        bps: int,
        epoch: int,
        nonce: int,
        expires_at: int,
        evidence_hash: bytes,
        sig: bytes,
    ) -> str:
        tx = phenotype.functions.setMultiplier(
            token_id,
            bps,
            epoch,
            nonce,
            expires_at,
            evidence_hash,
            cell_acct.address,
            sig,
        ).build_transaction(
            {
                "from": cell_acct.address,
                "chainId": cfg.chain_id,
                "nonce": w3.eth.get_transaction_count(cell_acct.address),
                "gas": 300_000,
                "gasPrice": w3.eth.gas_price,
            }
        )
        signed = Account.sign_transaction(tx, cfg.cell_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise RuntimeError(f"Phenotype.setMultiplier reverted, tx {tx_hash.hex()}")
        return tx_hash.hex()

    return CellPorts(
        load_events=_load_events,
        sign=_sign,
        submit_phenotype=_submit_phenotype,
        expected_nonce=_expected_nonce,
    )


def cell_config_from(cfg: Web3Config) -> EligibilityCellConfig:
    """Convenience: build an :class:`EligibilityCellConfig` matching the
    Web3Config so the caller doesn't have to pass the same addresses
    twice."""
    return EligibilityCellConfig(
        cell_address=cfg.cell_address,
        phenotype_address=cfg.phenotype_address,
        chain_id=cfg.chain_id,
    )
