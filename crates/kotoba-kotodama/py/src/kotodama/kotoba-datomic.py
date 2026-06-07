"""kotodama.kotoba-datomic — Python-side kotoba-datomic attestation primitives.

Mirror of the TypeScript surface in
``20-actors/etzhayyim-sdk/src/kotoba-datomic/attestation.ts`` so Murakumo
Pregel cells (running on the cell-runner) can produce attestations
without round-tripping through Node.

The cell-runner's ``/kotoba-datomic/attest`` HTTP endpoint receives a
``WitnessRequest`` body from the orchestrator, dispatches it to one of
the local cells, and calls :func:`produce_attestation` to emit a signed
``com.etzhayyim.kotoba-datomic.attestation`` record. The record is then
written back to PDS via :mod:`kotodama.substrate`.

Per kotoba-datomic SPEC §4 + §5 + ADR-2605231400.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable, Literal, Optional


# ─── public types (mirror lexicon shape) ─────────────────────────────


Verdict = Literal["accept", "reject", "escalate"]


@dataclass
class MembraneLayerRef:
    """Reference to one membrane layer artifact. Mirrors
    ``com.etzhayyim.kotoba-datomic.membraneRule#layerRef``."""

    path: str
    content_hash: str
    version: Optional[str] = None


@dataclass
class MembraneRule:
    """Loaded ``(L1 schema, L2 policy, L3 deterministic)`` triple for a
    single NSID. Mirrors ``com.etzhayyim.kotoba-datomic.membraneRule``."""

    v: int
    nsid: str
    schema_ref: MembraneLayerRef
    policy_ref: MembraneLayerRef
    cell_ref: MembraneLayerRef
    quorum_size: int = 5
    quorum_threshold: int = 3
    escalation_policy: Literal["reject", "council", "pending"] = "council"
    ciphertext_only: bool = False
    registered_at: str = ""
    supersedes_nsid: Optional[str] = None

    @classmethod
    def from_wire(cls, payload: dict) -> "MembraneRule":
        """Parse the TS-side wire shape (camelCase) into a Python instance.

        Tolerates both the lexicon shape and the test-fixture shape produced
        by the JS orchestrator.
        """

        def _ref(d: dict) -> MembraneLayerRef:
            return MembraneLayerRef(
                path=d["path"],
                content_hash=d.get("contentHash") or d.get("content_hash") or "",
                version=d.get("version"),
            )

        return cls(
            v=int(payload.get("v", 1)),
            nsid=payload["nsid"],
            schema_ref=_ref(payload["schemaRef"]),
            policy_ref=_ref(payload["policyRef"]),
            cell_ref=_ref(payload["cellRef"]),
            quorum_size=int(payload.get("quorumSize", 5)),
            quorum_threshold=int(payload.get("quorumThreshold", 3)),
            escalation_policy=payload.get("escalationPolicy", "council"),
            ciphertext_only=bool(payload.get("ciphertextOnly", False)),
            registered_at=payload.get("registeredAt", ""),
            supersedes_nsid=payload.get("supersedesNsid"),
        )


@dataclass
class LayerVerdict:
    layer: Literal["schema", "policy", "deterministic"]
    verdict: Verdict
    reason: Optional[str] = None


@dataclass
class MembraneVerdict:
    verdict: Verdict
    layers: list[LayerVerdict] = field(default_factory=list)
    reason: Optional[str] = None


@dataclass
class Attestation:
    """Mirrors ``com.etzhayyim.kotoba-datomic.attestation`` record shape. The
    ``signature`` is bytes locally; wire encoding uses base64 (see
    :meth:`to_wire`)."""

    v: int
    record_uri: str
    record_cid: str
    cell_id: str
    cell_node: str
    verdict: Verdict
    membrane_version: str
    attested_at: str
    signature: bytes
    quorum_group: str
    reason: Optional[str] = None
    escalation_target: Optional[Literal["council", "membrane-amendment", "human-review"]] = None

    def to_wire(self) -> dict:
        """JSON-ready dict matching the lexicon wire shape (camelCase, base64 sig)."""
        payload: dict[str, Any] = {
            "v": self.v,
            "recordUri": self.record_uri,
            "recordCid": self.record_cid,
            "cellId": self.cell_id,
            "verdict": self.verdict,
            "membraneVersion": self.membrane_version,
            "attestedAt": self.attested_at,
            "signature": base64.b64encode(self.signature).decode("ascii"),
            "quorumGroup": self.quorum_group,
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.escalation_target is not None:
            payload["escalationTarget"] = self.escalation_target
        # `cellNode` is part of the SDK's TS Attestation interface but is
        # NOT in the lexicon required set — included here for parity with
        # the TS in-memory shape; PDS may strip on validation.
        payload["cellNode"] = self.cell_node
        return payload


# ─── validators ──────────────────────────────────────────────────────


SchemaValidator = Callable[[dict, MembraneRule], Awaitable[LayerVerdict]]
PolicyValidator = Callable[[dict, MembraneRule], Awaitable[LayerVerdict]]
DeterministicValidator = Callable[[dict, MembraneRule], Awaitable[LayerVerdict]]


async def _accept_schema(_record: dict, _rule: MembraneRule) -> LayerVerdict:
    return LayerVerdict(layer="schema", verdict="accept")


async def _accept_policy(_record: dict, _rule: MembraneRule) -> LayerVerdict:
    return LayerVerdict(layer="policy", verdict="accept")


async def _accept_deterministic(_record: dict, _rule: MembraneRule) -> LayerVerdict:
    return LayerVerdict(layer="deterministic", verdict="accept")


@dataclass
class MembraneValidators:
    schema: Optional[SchemaValidator] = None
    policy: Optional[PolicyValidator] = None
    deterministic: Optional[DeterministicValidator] = None


async def minimal_schema_validator(record: dict, _rule: MembraneRule) -> LayerVerdict:
    """Match the TS ``minimalSchemaValidator``: require ``v`` integer ≥1.

    Apps with real lexicon validators (e.g., ``featureSchemaValidator``)
    pass their own callable instead.
    """
    if not isinstance(record, dict):
        return LayerVerdict(layer="schema", verdict="reject", reason="record is not a dict")
    v = record.get("v")
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        return LayerVerdict(
            layer="schema", verdict="reject", reason="record.v must be a positive integer"
        )
    return LayerVerdict(layer="schema", verdict="accept")


async def validate_against_membrane(
    record: dict,
    rule: MembraneRule,
    validators: Optional[MembraneValidators] = None,
) -> MembraneVerdict:
    """Run all three membrane layers and short-circuit on first non-accept.

    Pure (no I/O) — defaults to always-accept stubs for each layer.
    """
    v = validators or MembraneValidators()
    schema_check = v.schema or _accept_schema
    policy_check = v.policy or _accept_policy
    det_check = v.deterministic or _accept_deterministic

    layers: list[LayerVerdict] = []

    s = await schema_check(record, rule)
    layers.append(s)
    if s.verdict != "accept":
        return MembraneVerdict(verdict=s.verdict, layers=layers, reason=s.reason)

    p = await policy_check(record, rule)
    layers.append(p)
    if p.verdict != "accept":
        return MembraneVerdict(verdict=p.verdict, layers=layers, reason=p.reason)

    d = await det_check(record, rule)
    layers.append(d)
    if d.verdict != "accept":
        return MembraneVerdict(verdict=d.verdict, layers=layers, reason=d.reason)

    return MembraneVerdict(verdict="accept", layers=layers)


# ─── signing ─────────────────────────────────────────────────────────


CellSigner = Callable[[bytes], Awaitable[bytes]]


def canonical_attestation_bytes(
    *,
    record_cid: str,
    cell_id: str,
    verdict: Verdict,
    reason: str,
    membrane_version: str,
    attested_at: str,
) -> bytes:
    """Stable canonicalization. Matches the TS ``canonicalAttestationBytes``
    so signatures from either side verify against the other's bytes."""
    text = "\n".join(
        [record_cid, cell_id, verdict, reason, membrane_version, attested_at]
    )
    return text.encode("utf-8")


def make_deterministic_test_signer(cell_id: str) -> CellSigner:
    """Test-only signer: ``sha256(canonical || cell_id)``. Matches the TS
    ``makeDeterministicTestSigner``. Replace with :func:`make_ed25519_signer`
    in production cells; see :func:`make_cell_signer` for the runtime
    resolver chain used by the cell-runner.
    """
    cell_bytes = cell_id.encode("utf-8")

    async def _sign(canonical: bytes) -> bytes:
        return hashlib.sha256(canonical + cell_bytes).digest()

    return _sign


def make_ed25519_signer(private_key: bytes) -> CellSigner:
    """Production signer: Ed25519 over the canonical attestation bytes.

    ``private_key`` is the raw 32-byte Ed25519 seed (the format produced
    by ``Ed25519PrivateKey.generate().private_bytes(Encoding.Raw,
    PrivateFormat.Raw, NoEncryption())``).
    """
    if len(private_key) != 32:
        raise ValueError(f"Ed25519 private key must be 32 bytes, got {len(private_key)}")

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.from_private_bytes(private_key)

    async def _sign(canonical: bytes) -> bytes:
        return sk.sign(canonical)

    return _sign


def ed25519_public_key_bytes(private_key: bytes) -> bytes:
    """Derive the raw 32-byte Ed25519 public key from a 32-byte seed."""
    if len(private_key) != 32:
        raise ValueError(f"Ed25519 private key must be 32 bytes, got {len(private_key)}")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    sk = Ed25519PrivateKey.from_private_bytes(private_key)
    return sk.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def verify_ed25519_signature(canonical: bytes, signature: bytes, public_key: bytes) -> bool:
    """Third-party verifier — given the canonical bytes, the cell's
    detached signature, and the cell's published public key, return
    whether the signature is valid.

    This is what an orchestrator (or any third party) does to verify each
    attestation in a witness quorum. Pure function, no I/O.
    """
    if len(public_key) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(public_key)}")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    try:
        pk = Ed25519PublicKey.from_public_bytes(public_key)
        pk.verify(signature, canonical)
        return True
    except InvalidSignature:
        return False


def _keychain_cell_key(cell_id: str) -> Optional[bytes]:
    """Load a cell's Ed25519 private key from the macOS Keychain.

    Resolution: ``security find-generic-password -s com.etzhayyim.kotoba-datomic
    -a {cell_id} -w`` returns hex-encoded 32-byte seed. Returns None
    when the keychain entry is absent or ``security`` is not on PATH
    (non-mac runtimes).
    """
    import shutil
    import subprocess

    if not shutil.which("security"):
        return None
    try:
        out = subprocess.check_output(
            [
                "security", "find-generic-password",
                "-s", "com.etzhayyim.kotoba-datomic",
                "-a", cell_id,
                "-w",
            ],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    hex_seed = out.decode("ascii", errors="ignore").strip()
    if len(hex_seed) != 64:
        return None
    try:
        return bytes.fromhex(hex_seed)
    except ValueError:
        return None


def _env_cell_key(cell_id: str) -> Optional[bytes]:
    """Load a cell's Ed25519 private key from env var
    ``CELL_PRIVATE_KEY_<cellId>`` (hex-encoded 32-byte seed). Used in
    container deploys where macOS Keychain is not available.
    """
    import os

    raw = os.environ.get(f"CELL_PRIVATE_KEY_{cell_id}", "").strip()
    if len(raw) != 64:
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return None


def make_cell_signer(cell_id: str) -> tuple[CellSigner, str]:
    """Production resolver chain. Returns ``(signer, source)`` where
    ``source`` is one of:

      - ``"keychain"``      — macOS Keychain entry under
                              ``service=com.etzhayyim.kotoba-datomic, account={cell_id}``
      - ``"env"``           — ``CELL_PRIVATE_KEY_{cell_id}`` env var
      - ``"deterministic"`` — fallback for dev / unit-tests. Prominent
                              warning is logged at the cell-runner level
                              (this function is pure).

    The cell-runner uses this resolver; tests typically inject signers
    directly via :func:`make_deterministic_test_signer` or
    :func:`make_ed25519_signer`.
    """
    key = _keychain_cell_key(cell_id)
    if key is not None:
        return make_ed25519_signer(key), "keychain"
    key = _env_cell_key(cell_id)
    if key is not None:
        return make_ed25519_signer(key), "env"
    return make_deterministic_test_signer(cell_id), "deterministic"


def membrane_version_for(rule: MembraneRule) -> str:
    lex = rule.schema_ref.version or rule.schema_ref.content_hash[:7]
    rego = rule.policy_ref.version or rule.policy_ref.content_hash[:7]
    cell = rule.cell_ref.version or rule.cell_ref.content_hash[:7]
    return f"lex:{lex}/rego:{rego}/cell:{cell}"


def quorum_group_for(record_cid: str) -> str:
    """sha256(record_cid)[:16] hex — matches the TS ``quorumGroup``."""
    return hashlib.sha256(record_cid.encode("utf-8")).hexdigest()[:16]


# ─── produce_attestation ────────────────────────────────────────────


@dataclass
class WitnessRequest:
    """The body of a ``/kotoba-datomic/attest`` POST from the orchestrator."""

    v: int
    record_uri: str
    record_cid: str
    record: dict
    rule: MembraneRule

    @classmethod
    def from_wire(cls, payload: dict) -> "WitnessRequest":
        return cls(
            v=int(payload.get("v", 1)),
            record_uri=payload["recordUri"],
            record_cid=payload["recordCid"],
            record=payload["record"],
            rule=MembraneRule.from_wire(payload["rule"]),
        )


async def produce_attestation(
    *,
    record_uri: str,
    record_cid: str,
    record: dict,
    rule: MembraneRule,
    cell_id: str,
    cell_node: str,
    signer: CellSigner,
    validators: Optional[MembraneValidators] = None,
    attested_at: Optional[str] = None,
) -> Attestation:
    """Cell-side: validate the record against the membrane rule, sign the
    canonical attestation prefix, and return the signed Attestation.

    Caller writes the resulting record to PDS via
    :class:`kotodama.substrate.Etzhayyim` (the cell-runner does this).
    """
    verdict_result = await validate_against_membrane(record, rule, validators)
    when = attested_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    membrane_version = membrane_version_for(rule)
    reason = verdict_result.reason or ""

    canonical = canonical_attestation_bytes(
        record_cid=record_cid,
        cell_id=cell_id,
        verdict=verdict_result.verdict,
        reason=reason,
        membrane_version=membrane_version,
        attested_at=when,
    )
    signature = await signer(canonical)

    att = Attestation(
        v=1,
        record_uri=record_uri,
        record_cid=record_cid,
        cell_id=cell_id,
        cell_node=cell_node,
        verdict=verdict_result.verdict,
        membrane_version=membrane_version,
        attested_at=when,
        signature=signature,
        quorum_group=quorum_group_for(record_cid),
        reason=reason or None,
    )
    if verdict_result.verdict == "escalate":
        att.escalation_target = "council"
    return att


__all__ = [
    "Attestation",
    "CellSigner",
    "DeterministicValidator",
    "LayerVerdict",
    "MembraneLayerRef",
    "MembraneRule",
    "MembraneValidators",
    "MembraneVerdict",
    "PolicyValidator",
    "SchemaValidator",
    "Verdict",
    "WitnessRequest",
    "canonical_attestation_bytes",
    "ed25519_public_key_bytes",
    "make_cell_signer",
    "make_deterministic_test_signer",
    "make_ed25519_signer",
    "membrane_version_for",
    "minimal_schema_validator",
    "produce_attestation",
    "quorum_group_for",
    "validate_against_membrane",
    "verify_ed25519_signature",
]
