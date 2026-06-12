"""``EligibilityCell`` — LangGraph Pregel cell that computes phenotype
multipliers per adherent per super-step.

S2 of ADR-2605172300. The cell composes the pure scoring in
:mod:`kotodama.eligibility.scoring` with three I/O nodes:

  - ``load_events`` — pull AT Records (``com.etzhayyim.event.*``) for the
    given adherent from the configured PDS, fall back to geth-private
    ``AdherentRegistry.Attested`` events for redundancy.
  - ``sign_payload`` — assemble the EIP-191 envelope expected by
    ``Phenotype.setMultiplier`` and sign it with the cell private key.
  - ``emit_to_chain`` — submit the signed update to geth-private.

The graph is built so the I/O nodes are pluggable: tests can replace
them with in-memory stubs without changing the scoring code path.

LangGraph is used for the BSP super-step abstraction (per
ADR-2605171800), not for an LLM reasoning loop. There is no LLM call
in the steady-state path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypedDict

from kotodama.eligibility.scoring import (
    AttestationEvent,
    EligibilityState,
    PhenotypeUpdate,
    collapse_events,
    multiplier_from_score,
    score_participation,
)


class CellGraphState(TypedDict, total=False):
    """LangGraph state passed between nodes within one super-step."""

    token_id: int
    window_start: int
    window_end: int
    epoch: int
    events: list[AttestationEvent]
    update: PhenotypeUpdate
    payload_hash: bytes
    signature: bytes
    tx_hash: str


# ---------------------------------------------------------------------
# I/O ports (pluggable)
# ---------------------------------------------------------------------


@dataclass
class CellPorts:
    """The minimum I/O surface the cell needs against the outside world.

    In production these are bound to a viem-style RPC client + ATproto
    AtpAgent; tests use in-memory fakes. The cell itself stays pure.
    """

    # token_id, window_start, window_end → list of events
    load_events: Callable[[int, int, int], list[AttestationEvent]]

    # payload bytes → 65-byte EIP-191 signature
    sign: Callable[[bytes], bytes]

    # tokenId, bps, epoch, nonce, expiresAt, evidenceHash, signature → tx hash
    submit_phenotype: Callable[[int, int, int, int, int, bytes, bytes], str]

    # cell-side nonce read (mirror of Phenotype.cellNonce[cell] on-chain)
    expected_nonce: Callable[[], int]


# ---------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------


@dataclass
class EligibilityCellConfig:
    cell_address: str       # 0x-prefixed EOA representing the cell
    phenotype_address: str  # 0x-prefixed Phenotype.sol address
    chain_id: int = 2605    # geth-private per ADR-2605172300
    signature_ttl_secs: int = 600  # 10 min default
    # Constitutional clamp; the cell mirrors the chain band defensively.
    floor_bps: int = 5_000
    ceiling_bps: int = 20_000


@dataclass
class EligibilityCell:
    cfg: EligibilityCellConfig
    ports: CellPorts
    # Optional outlier-review hook; called for every floor/ceiling hit.
    on_outlier: Optional[Callable[[PhenotypeUpdate], None]] = None

    def step(
        self,
        token_id: int,
        window_start: int,
        window_end: int,
        epoch: int,
        now: int,
    ) -> Optional[str]:
        """Run one super-step for one adherent. Returns the submit tx
        hash, or ``None`` if no update was warranted (e.g., multiplier
        unchanged within tolerance — left to the caller's policy)."""
        events = collapse_events(self.ports.load_events(token_id, window_start, window_end))
        state = EligibilityState(
            token_id=token_id,
            window_start=window_start,
            window_end=window_end,
            events=events,
        )

        score, breakdown = score_participation(state)
        bps = multiplier_from_score(
            score, floor_bps=self.cfg.floor_bps, ceiling_bps=self.cfg.ceiling_bps
        )
        update = PhenotypeUpdate(token_id=token_id, bps=bps, score=score, breakdown=breakdown)

        if self.on_outlier and (bps == self.cfg.floor_bps or bps == self.cfg.ceiling_bps):
            self.on_outlier(update)

        nonce = self.ports.expected_nonce()
        expires_at = now + self.cfg.signature_ttl_secs

        payload = _eip191_payload(
            phenotype=self.cfg.phenotype_address,
            chain_id=self.cfg.chain_id,
            token_id=token_id,
            new_bps=bps,
            epoch=epoch,
            nonce=nonce,
            expires_at=expires_at,
            evidence_hash=b"\x00" * 32,
            cell=self.cfg.cell_address,
        )
        sig = self.ports.sign(payload)
        return self.ports.submit_phenotype(
            token_id, bps, epoch, nonce, expires_at, b"\x00" * 32, sig
        )


# ---------------------------------------------------------------------
# LangGraph integration
# ---------------------------------------------------------------------


def build_eligibility_graph(cell: EligibilityCell) -> Any:
    """Return a compiled LangGraph ``StateGraph`` whose entry point
    consumes ``CellGraphState`` and runs one super-step.

    Wired as a separate function so callers that already manage their
    own LangGraph runtime can splice it in alongside other cells; e.g.,
    a fleet driver can build the eligibility graph per adherent and run
    them as parallel pregel actors.
    """
    # Import locally so this module remains importable in environments
    # without langgraph installed (tests, type-check-only runs).
    from langgraph.graph import StateGraph, END

    def load_events(state: CellGraphState) -> CellGraphState:
        evs = cell.ports.load_events(
            state["token_id"], state["window_start"], state["window_end"]
        )
        return {"events": list(collapse_events(evs))}

    def score_node(state: CellGraphState) -> CellGraphState:
        es = EligibilityState(
            token_id=state["token_id"],
            window_start=state["window_start"],
            window_end=state["window_end"],
            events=tuple(state["events"]),
        )
        score, breakdown = score_participation(es)
        bps = multiplier_from_score(
            score, floor_bps=cell.cfg.floor_bps, ceiling_bps=cell.cfg.ceiling_bps
        )
        return {
            "update": PhenotypeUpdate(
                token_id=state["token_id"], bps=bps, score=score, breakdown=breakdown
            )
        }

    def sign_node(state: CellGraphState) -> CellGraphState:
        nonce = cell.ports.expected_nonce()
        # The TTL/now are not threaded through CellGraphState in this
        # minimal graph; tests can branch into a custom builder.
        import time

        now = int(time.time())
        u = state["update"]
        payload = _eip191_payload(
            phenotype=cell.cfg.phenotype_address,
            chain_id=cell.cfg.chain_id,
            token_id=u.token_id,
            new_bps=u.bps,
            epoch=state["epoch"],
            nonce=nonce,
            expires_at=now + cell.cfg.signature_ttl_secs,
            evidence_hash=b"\x00" * 32,
            cell=cell.cfg.cell_address,
        )
        return {"payload_hash": payload, "signature": cell.ports.sign(payload)}

    def emit_node(state: CellGraphState) -> CellGraphState:
        nonce = cell.ports.expected_nonce()
        import time

        now = int(time.time())
        u = state["update"]
        tx = cell.ports.submit_phenotype(
            u.token_id,
            u.bps,
            state["epoch"],
            nonce,
            now + cell.cfg.signature_ttl_secs,
            b"\x00" * 32,
            state["signature"],
        )
        return {"tx_hash": tx}

    g = StateGraph(CellGraphState)
    g.add_node("load_events", load_events)
    g.add_node("score", score_node)
    g.add_node("sign", sign_node)
    g.add_node("emit", emit_node)
    g.set_entry_point("load_events")
    g.add_edge("load_events", "score")
    g.add_edge("score", "sign")
    g.add_edge("sign", "emit")
    g.add_edge("emit", END)
    return g.compile()


# ---------------------------------------------------------------------
# Payload helper
# ---------------------------------------------------------------------


def _eip191_payload(
    *,
    phenotype: str,
    chain_id: int,
    token_id: int,
    new_bps: int,
    epoch: int,
    nonce: int,
    expires_at: int,
    evidence_hash: bytes,
    cell: str,
) -> bytes:
    """Compute the keccak digest the cell signs.

    Matches ``Phenotype.payloadHash`` followed by the EIP-191 envelope:

        h = keccak256(abi.encode(address(this), block.chainid, tokenId,
                                  newBps, epoch, nonce, expiresAt,
                                  evidenceHash, cell))
        envelope = keccak256("\\x19Ethereum Signed Message:\\n32" || h)
    """
    # Use eth_abi if available; fall back to a hand-encoded equivalent
    # for environments without it (e.g., type-check-only).
    try:
        from eth_abi import encode as abi_encode  # type: ignore
        from eth_utils import keccak  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "eligibility.cell._eip191_payload requires eth-abi + eth-utils"
        ) from exc

    inner = keccak(
        abi_encode(
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
                phenotype,
                chain_id,
                token_id,
                new_bps,
                epoch,
                nonce,
                expires_at,
                evidence_hash,
                cell,
            ],
        )
    )
    return keccak(b"\x19Ethereum Signed Message:\n32" + inner)
