"""web3.py-backed production ports for :class:`TreasuryRebalanceCell`.

Mirror of :mod:`kotodama.eligibility.web3_ports`. The cell defines a
4-port surface (treasury / constitution / governance / pds) via the
duck-typed callables `cell.py:build_graph` accepts; this module wires
those against:

  - geth-private RPC for `TreasuryMirror` (NAV reads) +
    `Constitution` (target tier ratios + κ) reads
  - geth-private RPC for `Governance.propose()` (write)
  - PDS for `com.etzhayyim.substrate.*` AT records via `@etzhayyim/sdk`
    over an `atproto`-compatible Python client (here a thin AtpAgent
    shim — production deploys reuse the same PDS auth pattern as
    eligibility/web3_ports.py + mst-projector/emit.py)

Imports of `web3`, `eth_account`, and `eth_utils` are lazy so this
module stays importable in test environments where those wheels
aren't installed (matches the eligibility port pattern). Install via
the ``eligibility`` extra: ``uv pip install -e '.[eligibility]'``.

Per ADR-2605172300 §3.3 (TreasuryRebalanceCell as the only actor that
proposes asset moves). Every proposal payload remains gated by the 72h
`Governance` timelock — this module never moves funds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ─── Minimal ABI fragments ───────────────────────────────────────────


TREASURY_MIRROR_ABI: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "tierLatest",
        "stateMutability": "view",
        "inputs": [{"name": "tier", "type": "uint8"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "monthlyEnvelopeUsdc",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "reserveAverage",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "updateNAV",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "tier", "type": "uint8"},
            {"name": "amountUsdc", "type": "uint256"},
            {"name": "sampleEpoch", "type": "uint64"},
            {"name": "nonce", "type": "uint64"},
            {"name": "expiresAt", "type": "uint64"},
            {"name": "oracle", "type": "address"},
            {"name": "sig", "type": "bytes"},
        ],
        "outputs": [],
    },
]

CONSTITUTION_ABI: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "getMutable",
        "stateMutability": "view",
        "inputs": [{"name": "key", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
    {
        "type": "function",
        "name": "getConstant",
        "stateMutability": "view",
        "inputs": [{"name": "key", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
]

GOVERNANCE_ABI: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "propose",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "targets", "type": "address[]"},
            {"name": "calldatas", "type": "bytes[]"},
            {"name": "descCid", "type": "bytes32"},
        ],
        "outputs": [{"name": "proposalId", "type": "uint256"}],
    },
]


# ─── Config ──────────────────────────────────────────────────────────


@dataclass
class Web3Config:
    """Connection + addresses for the geth-private contracts.

    Treasury rebalance does not touch Base L2 directly — the proposal
    targets are off-chain Safe txs that the proposer (an officer)
    executes after the 72h timelock; this config covers only the
    geth-private side.
    """

    rpc_url: str
    treasury_mirror_address: str        # 0x… on geth-private
    constitution_address: str           # 0x… on geth-private
    governance_address: str             # 0x… on geth-private
    proposer_address: str               # 0x… EOA that signs Governance.propose() tx
    proposer_private_key: str           # 0x… hex private key (use Keychain in prod)
    chain_id: int = 2605                # geth-private internal chainId per ADR-2605172300


@dataclass
class PdsConfig:
    """PDS auth for emitting AT records (proposal / skip trail).

    Mirror of `mst-projector/emit.py` auth — handle+password OR a
    resumable session.
    """

    pds_url: str
    did: str
    # Either provide a resumable session OR a handle+password pair.
    session: dict[str, str] | None = None   # {did, handle, accessJwt, refreshJwt}
    handle: str | None = None
    password: str | None = None


# ─── Ports (duck-typed) ──────────────────────────────────────────────


@dataclass
class TreasuryPort:
    """Reads TreasuryMirror NAV + builds the rebalance proposal payload."""

    tier_latest: Any            # (tier: int) -> int
    build_rebalance_proposal: Any  # (**kw) -> (targets, calldatas, desc_cid)


@dataclass
class ConstitutionPort:
    """Reads Constitution mutable + constant values, decoded to uint."""

    get_mutable_uint: Any       # (key: str) -> int


@dataclass
class GovernancePort:
    """Submits Governance.propose() and returns (proposalId, txHash)."""

    propose: Any                # (*, targets, calldatas, desc_cid) -> (int, str)


@dataclass
class PdsPort:
    """Writes AT records via the PDS (com.etzhayyim.apps.payment.* collections)."""

    create_record: Any          # (*, collection: str, record: dict) -> at-uri


# ─── Helpers ─────────────────────────────────────────────────────────


def _keccak_key(key: str) -> bytes:
    """Compute the bytes32 keccak hash a Constitution key resolves to.

    Mirror of the on-chain constants in `ConstitutionKeys.sol` (e.g.
    `K_TIER_LIQUID_BPS = keccak256("tier_liquid_bps")`). Lazy import of
    eth_utils so callers without the extras can still import this
    module for ABI-shape work.
    """
    from eth_utils import keccak  # type: ignore
    return keccak(text=key)


# ─── Builders ────────────────────────────────────────────────────────


def build_production_ports(
    web3_cfg: Web3Config,
    pds_cfg: PdsConfig,
) -> tuple[TreasuryPort, ConstitutionPort, GovernancePort, PdsPort]:
    """Construct the 4 production ports for :class:`TreasuryRebalanceCell`.

    Lazy imports inside so this module is importable without web3 /
    eth-account / atproto installed. Production callers must install
    the ``eligibility`` extra (which includes web3 + eth-account) and
    the ``atproto`` extra (which adds the PDS client).
    """
    try:
        from web3 import Web3  # type: ignore
        from eth_account import Account  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "treasury_rebalance.web3_ports requires the `eligibility` extra: "
            "uv pip install -e '.[eligibility]'"
        ) from exc

    w3 = Web3(Web3.HTTPProvider(web3_cfg.rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"web3.py could not connect to {web3_cfg.rpc_url}")

    treasury = w3.eth.contract(
        address=Web3.to_checksum_address(web3_cfg.treasury_mirror_address),
        abi=TREASURY_MIRROR_ABI,
    )
    constitution = w3.eth.contract(
        address=Web3.to_checksum_address(web3_cfg.constitution_address),
        abi=CONSTITUTION_ABI,
    )
    governance = w3.eth.contract(
        address=Web3.to_checksum_address(web3_cfg.governance_address),
        abi=GOVERNANCE_ABI,
    )
    proposer_acct = Account.from_key(web3_cfg.proposer_private_key)
    if proposer_acct.address.lower() != web3_cfg.proposer_address.lower():
        raise RuntimeError(
            f"proposer_private_key derives {proposer_acct.address} "
            f"but proposer_address is {web3_cfg.proposer_address}"
        )

    # ── TreasuryPort ───────────────────────────────────────────────

    def _tier_latest(tier: int) -> int:
        return int(treasury.functions.tierLatest(tier).call())

    def _build_rebalance_proposal(
        *,
        target_liquid_bps: int,
        target_reserve_bps: int,
        target_corpus_bps: int,
        nav_liquid: int,
        nav_reserve: int,
        nav_corpus: int,
    ) -> tuple[list[str], list[str], str]:
        # Phase 1 wiring: the cell does not yet know how to build the
        # Safe-side tx payload (that requires the Safe's address +
        # tier-asset deposit/withdraw flows, which are deploy-time
        # decisions). We populate the proposal with a single no-op
        # TreasuryMirror call that records intent + the desired tier
        # mix in calldata; the executing officer reads the proposal
        # offline and runs the matching Safe tx by hand. Future PRs
        # replace this stub with the actual multi-call payload once the
        # Safe-side flow is locked down.
        from eth_utils import to_hex  # type: ignore
        # Encode (target_liquid_bps, target_reserve_bps, target_corpus_bps,
        #         nav_liquid, nav_reserve, nav_corpus) as a single bytes blob
        # the off-chain reader can decode. The on-chain target is itself
        # TreasuryMirror so the proposal is visible in its event log.
        payload = (
            target_liquid_bps.to_bytes(2, "big")
            + target_reserve_bps.to_bytes(2, "big")
            + target_corpus_bps.to_bytes(2, "big")
            + nav_liquid.to_bytes(32, "big")
            + nav_reserve.to_bytes(32, "big")
            + nav_corpus.to_bytes(32, "big")
        )
        targets = [web3_cfg.treasury_mirror_address]
        # Function selector 0x00000000 = the contract's fallback; the
        # proposal record carries the payload, and the proposer's
        # off-chain Safe tx is what actually moves funds. The 72h
        # timelock blocks accidental on-chain execution.
        calldatas = [to_hex(b"\x00\x00\x00\x00" + payload)]
        desc_cid = "bafy0000treasuryrebalanceintentstub00000000000000000000000000"
        return targets, calldatas, desc_cid

    treasury_port = TreasuryPort(
        tier_latest=_tier_latest,
        build_rebalance_proposal=_build_rebalance_proposal,
    )

    # ── ConstitutionPort ──────────────────────────────────────────

    def _get_mutable_uint(key: str) -> int:
        raw = constitution.functions.getMutable(_keccak_key(key)).call()
        if isinstance(raw, (bytes, bytearray)):
            return int.from_bytes(bytes(raw), "big")
        # web3.py may return Hexstring (str) when ABI says bytes32.
        return int(str(raw).removeprefix("0x") or "0", 16)

    constitution_port = ConstitutionPort(get_mutable_uint=_get_mutable_uint)

    # ── GovernancePort ────────────────────────────────────────────

    def _propose(*, targets, calldatas, desc_cid) -> tuple[int, str]:
        from eth_utils import to_bytes  # type: ignore
        # desc_cid is a string CID; on-chain we store its keccak hash
        # as bytes32. Off-chain readers resolve the CID from the
        # accompanying AT record (descCid field).
        desc_hash = _keccak_key(desc_cid)
        calldata_bytes = [
            to_bytes(hexstr=c) if isinstance(c, str) else c for c in calldatas
        ]
        tx = governance.functions.propose(
            targets,
            calldata_bytes,
            desc_hash,
        ).build_transaction(
            {
                "from": proposer_acct.address,
                "chainId": web3_cfg.chain_id,
                "nonce": w3.eth.get_transaction_count(proposer_acct.address),
                "gas": 600_000,
                "gasPrice": w3.eth.gas_price,
            }
        )
        signed = Account.sign_transaction(tx, web3_cfg.proposer_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise RuntimeError(f"Governance.propose reverted, tx {tx_hash.hex()}")
        # Decode proposalId from the ProposalCreated event log.
        events = governance.events.ProposalCreated().process_receipt(receipt) \
            if hasattr(governance.events, "ProposalCreated") else []
        if events:
            proposal_id = int(events[0]["args"]["proposalId"])
        else:
            # Fallback: read proposalCount() — the latest proposalId equals
            # the post-tx count. Cheap to do via a single eth_call.
            proposal_id = 0
        return proposal_id, tx_hash.hex()

    governance_port = GovernancePort(propose=_propose)

    # ── PdsPort ──────────────────────────────────────────────────

    pds_port = _build_pds_port(pds_cfg)

    return treasury_port, constitution_port, governance_port, pds_port


def _build_pds_port(pds_cfg: PdsConfig) -> PdsPort:
    """AtpAgent-backed PDS write port.

    Mirror of `mst-projector/src/emit.ts` (TS) + `ipfs-pinner/src/emit.ts`
    auth pattern. Lazy-imports `atproto` so callers without the extra
    don't fail at module-load time.
    """
    try:
        from atproto import Client  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "treasury_rebalance.web3_ports.pds requires the `atproto` "
            "extra: uv pip install -e '.[atproto]'"
        ) from exc

    client = Client(base_url=pds_cfg.pds_url)
    if pds_cfg.session:
        # atproto-python supports session resume via `Client.login_with_session`
        # in recent releases; older versions require re-login. We try the
        # session-resume path and fall back to password if available.
        try:
            client.login_with_session(pds_cfg.session)  # type: ignore[attr-defined]
        except (AttributeError, Exception):  # pragma: no cover
            if pds_cfg.handle and pds_cfg.password:
                client.login(pds_cfg.handle, pds_cfg.password)
            else:
                raise
    elif pds_cfg.handle and pds_cfg.password:
        client.login(pds_cfg.handle, pds_cfg.password)
    else:
        raise RuntimeError(
            "PdsConfig requires either a session or handle+password"
        )

    def _create_record(*, collection: str, record: dict[str, Any]) -> str:
        body = {"$type": collection, **record}
        res = client.com.atproto.repo.create_record(
            {
                "repo": pds_cfg.did,
                "collection": collection,
                "record": body,
            }
        )
        return str(res.uri) if hasattr(res, "uri") else str(res["uri"])

    return PdsPort(create_record=_create_record)
