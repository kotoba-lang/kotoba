"""Parity test: ``_eip191_payload`` (Python) ↔ ``Phenotype.payloadHash``
(Solidity).

The EligibilityCell signs a payload that the on-chain Phenotype contract
must accept. If the Python side encodes the tuple differently from
``abi.encode(...) + keccak256(...)``, the on-chain ``ecrecover`` returns
the wrong address and ``Phenotype.setMultiplier`` reverts
``InvalidSignature``. This file pins the encoding so a future drift in
either side surfaces here first.

Requires the ``eligibility`` optional dependency (eth-abi + eth-utils).
"""

from __future__ import annotations

import pytest

eth_abi = pytest.importorskip("eth_abi")
eth_utils = pytest.importorskip("eth_utils")

from kotodama.eligibility.cell import _eip191_payload  # noqa: E402


# Fixed test vector. If either Solidity or Python encoding changes,
# update the expected hash deliberately — that update is itself the diff
# that catches the drift.
PHENOTYPE = "0x0000000000000000000000000000000000000001"
CELL = "0x0000000000000000000000000000000000000002"
CHAIN_ID = 2605
TOKEN_ID = 7
NEW_BPS = 12_000
EPOCH = 42
NONCE = 0
EXPIRES_AT = 1_000_000_000
EVIDENCE = b"\xab" * 32


def _solidity_equivalent_inner() -> bytes:
    """Reproduce ``keccak256(abi.encode(...))`` independently of cell.py
    to cross-check the payload helper rather than calling it twice."""
    encoded = eth_abi.encode(
        [
            "address",
            "uint256",
            "uint256",
            "uint16",
            "uint64",
            "uint64",
            "uint64",
            "bytes32",
            "address",
        ],
        [
            PHENOTYPE,
            CHAIN_ID,
            TOKEN_ID,
            NEW_BPS,
            EPOCH,
            NONCE,
            EXPIRES_AT,
            EVIDENCE,
            CELL,
        ],
    )
    return eth_utils.keccak(encoded)


def test_payload_matches_solidity_envelope() -> None:
    """Python ``_eip191_payload`` == ``\\x19Ethereum…\\n32`` envelope over
    the same ``abi.encode`` inner hash. This is the exact value the
    on-chain contract recovers from."""
    inner = _solidity_equivalent_inner()
    expected = eth_utils.keccak(b"\x19Ethereum Signed Message:\n32" + inner)

    actual = _eip191_payload(
        phenotype=PHENOTYPE,
        chain_id=CHAIN_ID,
        token_id=TOKEN_ID,
        new_bps=NEW_BPS,
        epoch=EPOCH,
        nonce=NONCE,
        expires_at=EXPIRES_AT,
        evidence_hash=EVIDENCE,
        cell=CELL,
    )
    assert actual == expected


def test_payload_changes_on_field_perturbation() -> None:
    """Sanity: perturbing any field changes the hash (no field is dead
    weight in the encoding)."""
    base = _eip191_payload(
        phenotype=PHENOTYPE,
        chain_id=CHAIN_ID,
        token_id=TOKEN_ID,
        new_bps=NEW_BPS,
        epoch=EPOCH,
        nonce=NONCE,
        expires_at=EXPIRES_AT,
        evidence_hash=EVIDENCE,
        cell=CELL,
    )
    perturbed_token = _eip191_payload(
        phenotype=PHENOTYPE,
        chain_id=CHAIN_ID,
        token_id=TOKEN_ID + 1,
        new_bps=NEW_BPS,
        epoch=EPOCH,
        nonce=NONCE,
        expires_at=EXPIRES_AT,
        evidence_hash=EVIDENCE,
        cell=CELL,
    )
    perturbed_bps = _eip191_payload(
        phenotype=PHENOTYPE,
        chain_id=CHAIN_ID,
        token_id=TOKEN_ID,
        new_bps=NEW_BPS + 1,
        epoch=EPOCH,
        nonce=NONCE,
        expires_at=EXPIRES_AT,
        evidence_hash=EVIDENCE,
        cell=CELL,
    )
    perturbed_nonce = _eip191_payload(
        phenotype=PHENOTYPE,
        chain_id=CHAIN_ID,
        token_id=TOKEN_ID,
        new_bps=NEW_BPS,
        epoch=EPOCH,
        nonce=NONCE + 1,
        expires_at=EXPIRES_AT,
        evidence_hash=EVIDENCE,
        cell=CELL,
    )

    assert base != perturbed_token
    assert base != perturbed_bps
    assert base != perturbed_nonce
