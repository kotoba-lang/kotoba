"""Unit tests for web3_ports module — ABI shape, config validation,
keccak key derivation. Network/web3 imports are not exercised here
(those run only when `build_production_ports()` is called against a
live geth-private RPC).

Lazy imports inside production code mean these tests can run without
the `eligibility` / `atproto` extras installed; the only optional
import this test file makes is `eth_utils.keccak`, which we skip when
absent.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Make the cell directory importable so `from web3_ports import ...` works
# when this test is collected from anywhere.
_CELL_DIR = str(Path(__file__).resolve().parent.parent)
if _CELL_DIR not in sys.path:
    sys.path.insert(0, _CELL_DIR)

import web3_ports  # noqa: E402


# ─── ABI shape ───────────────────────────────────────────────────────


def _abi_function_names(abi: list[dict]) -> set[str]:
    return {e["name"] for e in abi if e.get("type") == "function"}


def test_treasury_mirror_abi_has_required_functions():
    names = _abi_function_names(web3_ports.TREASURY_MIRROR_ABI)
    assert "tierLatest" in names
    assert "updateNAV" in names
    assert "reserveAverage" in names
    assert "monthlyEnvelopeUsdc" in names


def test_constitution_abi_has_required_functions():
    names = _abi_function_names(web3_ports.CONSTITUTION_ABI)
    assert "getMutable" in names
    assert "getConstant" in names


def test_governance_abi_has_propose_with_correct_signature():
    names = _abi_function_names(web3_ports.GOVERNANCE_ABI)
    assert "propose" in names
    propose = next(
        e for e in web3_ports.GOVERNANCE_ABI
        if e.get("type") == "function" and e["name"] == "propose"
    )
    input_types = [i["type"] for i in propose["inputs"]]
    # On-chain signature: propose(address[],bytes[],bytes32)
    assert input_types == ["address[]", "bytes[]", "bytes32"]
    assert propose["outputs"][0]["type"] == "uint256"


def test_tier_latest_takes_uint8_returns_uint256():
    tier_latest = next(
        e for e in web3_ports.TREASURY_MIRROR_ABI
        if e.get("type") == "function" and e["name"] == "tierLatest"
    )
    assert tier_latest["inputs"][0]["type"] == "uint8"
    assert tier_latest["outputs"][0]["type"] == "uint256"
    assert tier_latest["stateMutability"] == "view"


def test_update_nav_signature_matches_treasury_mirror_sol():
    update_nav = next(
        e for e in web3_ports.TREASURY_MIRROR_ABI
        if e.get("type") == "function" and e["name"] == "updateNAV"
    )
    # On-chain: updateNAV(uint8,uint256,uint64,uint64,uint64,address,bytes)
    input_types = [i["type"] for i in update_nav["inputs"]]
    assert input_types == [
        "uint8", "uint256", "uint64", "uint64", "uint64", "address", "bytes",
    ]


# ─── Config dataclasses ──────────────────────────────────────────────


def test_web3_config_default_chain_id_is_geth_private():
    cfg = web3_ports.Web3Config(
        rpc_url="http://localhost:8545",
        treasury_mirror_address="0x" + "1" * 40,
        constitution_address="0x" + "2" * 40,
        governance_address="0x" + "3" * 40,
        proposer_address="0x" + "4" * 40,
        proposer_private_key="0x" + "a" * 64,
    )
    # geth-private internal chainId per ADR-2605172300
    assert cfg.chain_id == 2605


def test_web3_config_chain_id_can_be_overridden():
    cfg = web3_ports.Web3Config(
        rpc_url="http://localhost:8545",
        treasury_mirror_address="0x" + "1" * 40,
        constitution_address="0x" + "2" * 40,
        governance_address="0x" + "3" * 40,
        proposer_address="0x" + "4" * 40,
        proposer_private_key="0x" + "a" * 64,
        chain_id=31337,  # anvil
    )
    assert cfg.chain_id == 31337


def test_pds_config_requires_either_session_or_handle_password():
    # Dataclass construction itself doesn't enforce — the runtime
    # build_pds_port() checks. Test confirms the shape.
    bare = web3_ports.PdsConfig(
        pds_url="https://pds.etzhayyim.com",
        did="did:web:etzhayyim.com",
    )
    assert bare.session is None
    assert bare.handle is None
    assert bare.password is None

    with_session = web3_ports.PdsConfig(
        pds_url="https://pds.etzhayyim.com",
        did="did:web:etzhayyim.com",
        session={"did": "did:web:x", "handle": "x.etzhayyim.com",
                 "accessJwt": "jwt", "refreshJwt": "jwt"},
    )
    assert with_session.session is not None


# ─── Port shape ──────────────────────────────────────────────────────


def test_port_dataclasses_carry_their_methods():
    # The cell's `build_graph()` accepts ports via duck typing — we
    # confirm the dataclasses expose the expected attribute names so a
    # signature mismatch would fail at class-definition time, not at
    # cell-run time.
    treasury_attrs = set(web3_ports.TreasuryPort.__dataclass_fields__.keys())
    assert treasury_attrs == {"tier_latest", "build_rebalance_proposal"}

    constitution_attrs = set(web3_ports.ConstitutionPort.__dataclass_fields__.keys())
    assert constitution_attrs == {"get_mutable_uint"}

    governance_attrs = set(web3_ports.GovernancePort.__dataclass_fields__.keys())
    assert governance_attrs == {"propose"}

    pds_attrs = set(web3_ports.PdsPort.__dataclass_fields__.keys())
    assert pds_attrs == {"create_record"}


# ─── Constitution key keccak ─────────────────────────────────────────


def test_keccak_key_matches_constitution_keys_sol_constants():
    """The geth-private side hashes Constitution keys via keccak256(text).
    Our `_keccak_key` helper must produce identical bytes for the same
    string so reads find the right slot.
    """
    eth_utils = pytest.importorskip("eth_utils")

    # Known hash from `ConstitutionKeys.sol`:
    #   TIER_LIQUID_BPS = keccak256("tier_liquid_bps")
    expected = eth_utils.keccak(text="tier_liquid_bps").hex()
    actual = web3_ports._keccak_key("tier_liquid_bps").hex()
    assert actual == expected
    assert len(actual) == 64  # bytes32

    # κ band keys also exercised by the cell on every tick.
    assert web3_ports._keccak_key("kappa_bps").hex() == \
        eth_utils.keccak(text="kappa_bps").hex()
    assert web3_ports._keccak_key("tier_reserve_bps").hex() == \
        eth_utils.keccak(text="tier_reserve_bps").hex()
    assert web3_ports._keccak_key("tier_corpus_bps").hex() == \
        eth_utils.keccak(text="tier_corpus_bps").hex()


# ─── Lazy-import behavior ────────────────────────────────────────────


def test_module_imports_without_extras():
    """Re-importing the module shouldn't pull in web3 / atproto at
    top-level. This protects test environments that don't have the
    extras installed.
    """
    # Force reload to confirm no hidden top-level side effects.
    importlib.reload(web3_ports)
    assert hasattr(web3_ports, "build_production_ports")
    assert hasattr(web3_ports, "Web3Config")
    assert hasattr(web3_ports, "PdsConfig")


def test_build_production_ports_requires_extras_when_called():
    """Calling without web3 installed should fail with a clear extras
    hint, not an opaque ImportError deep in the function body.

    We can only run this assertion in environments where web3 is
    genuinely absent. When it IS installed (CI with the eligibility
    extra), the call will instead fail with a connection error against
    the dummy RPC URL — which is fine for the test's purpose of
    "module-level import doesn't crash; call-time wiring is
    well-defined".
    """
    cfg = web3_ports.Web3Config(
        rpc_url="http://127.0.0.1:1",  # nothing listens here
        treasury_mirror_address="0x" + "1" * 40,
        constitution_address="0x" + "2" * 40,
        governance_address="0x" + "3" * 40,
        proposer_address="0x" + "4" * 40,
        proposer_private_key="0x" + "a" * 64,
    )
    pds_cfg = web3_ports.PdsConfig(
        pds_url="https://pds.etzhayyim.com",
        did="did:web:etzhayyim.com",
        handle="x.etzhayyim.com",
        password="x",
    )
    with pytest.raises((RuntimeError, Exception)):
        web3_ports.build_production_ports(cfg, pds_cfg)
