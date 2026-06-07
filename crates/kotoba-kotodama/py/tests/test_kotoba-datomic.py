"""Tests for kotodama.kotoba-datomic attestation primitives.

Pairs with 20-actors/etzhayyim-sdk/test/kotoba-datomic-witnessed-write.test.ts
(TS-side). Verifies the Python signing pipeline produces byte-identical
canonical bytes to the TS side so signatures interoperate.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json

import pytest

from kotodama.kotoba-datomic import (
    Attestation,
    LayerVerdict,
    MembraneLayerRef,
    MembraneRule,
    MembraneValidators,
    WitnessRequest,
    canonical_attestation_bytes,
    ed25519_public_key_bytes,
    make_cell_signer,
    make_deterministic_test_signer,
    make_ed25519_signer,
    membrane_version_for,
    minimal_schema_validator,
    produce_attestation,
    quorum_group_for,
    validate_against_membrane,
    verify_ed25519_signature,
)


def _mock_rule(nsid: str = "test.example.foo") -> MembraneRule:
    return MembraneRule(
        v=1,
        nsid=nsid,
        schema_ref=MembraneLayerRef(path="00-contracts/lexicons/test/schema.json", content_hash="a" * 64, version="1.0.0"),
        policy_ref=MembraneLayerRef(path="00-contracts/policies/test/policy.rego", content_hash="b" * 64, version="1.0.0"),
        cell_ref=MembraneLayerRef(path="20-actors/kotoba-kotodama/cells/test/", content_hash="c" * 64, version="abcdef0"),
        quorum_size=5,
        quorum_threshold=3,
        registered_at="2026-05-23T00:00:00Z",
    )


# ── canonical bytes interop with TS ─────────────────────────────────


def test_canonical_attestation_bytes_format():
    b = canonical_attestation_bytes(
        record_cid="bafy-cid",
        cell_id="CellA",
        verdict="accept",
        reason="",
        membrane_version="lex:1.0.0/rego:1.0.0/cell:abcdef0",
        attested_at="2026-05-23T00:00:00Z",
    )
    expected = "bafy-cid\nCellA\naccept\n\nlex:1.0.0/rego:1.0.0/cell:abcdef0\n2026-05-23T00:00:00Z"
    assert b == expected.encode("utf-8")


def test_canonical_attestation_bytes_deterministic():
    args = dict(
        record_cid="bafy",
        cell_id="Cell",
        verdict="accept",
        reason="r",
        membrane_version="lex:1/rego:1/cell:abc",
        attested_at="2026-05-23T00:00:00Z",
    )
    assert canonical_attestation_bytes(**args) == canonical_attestation_bytes(**args)


def test_quorum_group_first_16_hex_chars_of_sha256():
    qg = quorum_group_for("bafy-cid-12345")
    assert len(qg) == 16
    full = hashlib.sha256(b"bafy-cid-12345").hexdigest()
    assert qg == full[:16]


def test_membrane_version_for_uses_versions():
    rule = _mock_rule()
    v = membrane_version_for(rule)
    assert v == "lex:1.0.0/rego:1.0.0/cell:abcdef0"


def test_membrane_version_falls_back_to_content_hash_prefix():
    rule = MembraneRule(
        v=1,
        nsid="x",
        schema_ref=MembraneLayerRef(path="a", content_hash="d" * 64),
        policy_ref=MembraneLayerRef(path="b", content_hash="e" * 64),
        cell_ref=MembraneLayerRef(path="c", content_hash="f" * 64),
        registered_at="2026-05-23T00:00:00Z",
    )
    assert membrane_version_for(rule) == "lex:" + "d" * 7 + "/rego:" + "e" * 7 + "/cell:" + "f" * 7


# ── deterministic test signer parity with TS ─────────────────────────


@pytest.mark.asyncio
async def test_test_signer_deterministic_and_32_bytes():
    sign = make_deterministic_test_signer("CellA")
    sig1 = await sign(b"canonical-bytes")
    sig2 = await sign(b"canonical-bytes")
    assert sig1 == sig2
    assert len(sig1) == 32
    # sha256(canonical || cell_id) — matches TS makeDeterministicTestSigner.
    expected = hashlib.sha256(b"canonical-bytes" + b"CellA").digest()
    assert sig1 == expected


@pytest.mark.asyncio
async def test_test_signer_differs_per_cell():
    sig_a = await make_deterministic_test_signer("CellA")(b"x")
    sig_b = await make_deterministic_test_signer("CellB")(b"x")
    assert sig_a != sig_b


# ── validate_against_membrane ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_minimal_schema_validator_accepts_v_field():
    rule = _mock_rule()
    verdict = await minimal_schema_validator({"v": 1, "hello": "world"}, rule)
    assert verdict.verdict == "accept"


@pytest.mark.asyncio
async def test_minimal_schema_validator_rejects_no_v():
    rule = _mock_rule()
    verdict = await minimal_schema_validator({"hello": "world"}, rule)
    assert verdict.verdict == "reject"
    assert "v" in (verdict.reason or "")


@pytest.mark.asyncio
async def test_validate_membrane_short_circuits_on_schema_reject():
    policy_called = False
    det_called = False

    async def policy(_r, _ru):
        nonlocal policy_called
        policy_called = True
        return LayerVerdict(layer="policy", verdict="accept")

    async def det(_r, _ru):
        nonlocal det_called
        det_called = True
        return LayerVerdict(layer="deterministic", verdict="accept")

    out = await validate_against_membrane(
        {"hello": "no v"},
        _mock_rule(),
        MembraneValidators(schema=minimal_schema_validator, policy=policy, deterministic=det),
    )
    assert out.verdict == "reject"
    assert not policy_called
    assert not det_called
    assert len(out.layers) == 1


@pytest.mark.asyncio
async def test_validate_membrane_all_accept():
    out = await validate_against_membrane(
        {"v": 1},
        _mock_rule(),
        MembraneValidators(schema=minimal_schema_validator),
    )
    assert out.verdict == "accept"
    assert [l.layer for l in out.layers] == ["schema", "policy", "deterministic"]


# ── produce_attestation ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_produce_attestation_emits_signed_record():
    rule = _mock_rule()
    att = await produce_attestation(
        record_uri="at://did:web:test/test.example.foo/abc",
        record_cid="bafy-cid-12345",
        record={"v": 1, "hello": "world"},
        rule=rule,
        cell_id="CellA",
        cell_node="node-0.test",
        signer=make_deterministic_test_signer("CellA"),
    )
    assert att.v == 1
    assert att.verdict == "accept"
    assert att.cell_id == "CellA"
    assert att.cell_node == "node-0.test"
    assert att.record_cid == "bafy-cid-12345"
    assert isinstance(att.signature, bytes)
    assert len(att.signature) == 32
    assert att.membrane_version == "lex:1.0.0/rego:1.0.0/cell:abcdef0"
    assert len(att.quorum_group) == 16


@pytest.mark.asyncio
async def test_produce_attestation_rejects_on_schema():
    att = await produce_attestation(
        record_uri="at://did:web:test/x/abc",
        record_cid="bafy-bad",
        record={"hello": "no v field"},
        rule=_mock_rule(),
        cell_id="CellA",
        cell_node="node-0",
        signer=make_deterministic_test_signer("CellA"),
        validators=MembraneValidators(schema=minimal_schema_validator),
    )
    assert att.verdict == "reject"
    assert att.reason is not None
    assert "v" in att.reason


@pytest.mark.asyncio
async def test_produce_attestation_escalation_sets_council_target():
    async def escalate(_r, _ru):
        return LayerVerdict(layer="deterministic", verdict="escalate", reason="human review")

    att = await produce_attestation(
        record_uri="at://x/y/z",
        record_cid="bafy-esc",
        record={"v": 1},
        rule=_mock_rule(),
        cell_id="CellA",
        cell_node="node-0",
        signer=make_deterministic_test_signer("CellA"),
        validators=MembraneValidators(deterministic=escalate),
    )
    assert att.verdict == "escalate"
    assert att.escalation_target == "council"


# ── wire shape interop ──────────────────────────────────────────────


def test_attestation_to_wire_matches_lexicon_camelcase():
    att = Attestation(
        v=1,
        record_uri="at://x/y/z",
        record_cid="bafy",
        cell_id="CellA",
        cell_node="node-0",
        verdict="accept",
        membrane_version="lex:1/rego:1/cell:abc",
        attested_at="2026-05-23T00:00:00Z",
        signature=b"\x00" * 32,
        quorum_group="abcdef0123456789",
    )
    wire = att.to_wire()
    assert wire["recordUri"] == "at://x/y/z"
    assert wire["recordCid"] == "bafy"
    assert wire["cellId"] == "CellA"
    assert wire["membraneVersion"] == "lex:1/rego:1/cell:abc"
    assert wire["attestedAt"] == "2026-05-23T00:00:00Z"
    assert wire["quorumGroup"] == "abcdef0123456789"
    # signature is base64-encoded for JSON transport
    decoded = base64.b64decode(wire["signature"])
    assert decoded == b"\x00" * 32
    assert "cellNode" in wire


def test_membrane_rule_from_wire_parses_tsdk_shape():
    payload = {
        "v": 1,
        "nsid": "com.etzhayyim.maps.feature",
        "schemaRef": {"path": "lex.json", "contentHash": "0" * 64, "version": "1.0.0"},
        "policyRef": {"path": "p.rego", "contentHash": "0" * 64},
        "cellRef": {"path": "cell/", "contentHash": "0" * 64},
        "quorumSize": 5,
        "quorumThreshold": 3,
        "escalationPolicy": "council",
        "registeredAt": "2026-05-23T00:00:00Z",
    }
    rule = MembraneRule.from_wire(payload)
    assert rule.nsid == "com.etzhayyim.maps.feature"
    assert rule.quorum_size == 5
    assert rule.quorum_threshold == 3
    assert rule.escalation_policy == "council"
    assert rule.schema_ref.version == "1.0.0"


# ── Ed25519 production signer ───────────────────────────────────────


@pytest.mark.asyncio
async def test_ed25519_signer_produces_64_byte_signature():
    seed = bytes.fromhex("a" * 64)  # 32-byte seed, all 0xaa
    signer = make_ed25519_signer(seed)
    sig = await signer(b"hello world")
    # Ed25519 signatures are 64 bytes
    assert len(sig) == 64
    # Deterministic — ed25519 sign is deterministic with same key + message
    sig2 = await signer(b"hello world")
    assert sig == sig2


@pytest.mark.asyncio
async def test_ed25519_sign_verify_round_trip():
    seed = bytes.fromhex("1" * 64)
    signer = make_ed25519_signer(seed)
    pubkey = ed25519_public_key_bytes(seed)
    canonical = b"canonical attestation bytes"
    sig = await signer(canonical)
    assert verify_ed25519_signature(canonical, sig, pubkey) is True


@pytest.mark.asyncio
async def test_ed25519_verify_rejects_tampered_canonical():
    seed = bytes.fromhex("2" * 64)
    signer = make_ed25519_signer(seed)
    pubkey = ed25519_public_key_bytes(seed)
    sig = await signer(b"original canonical")
    assert verify_ed25519_signature(b"tampered canonical", sig, pubkey) is False


@pytest.mark.asyncio
async def test_ed25519_verify_rejects_wrong_pubkey():
    seed_a = bytes.fromhex("3" * 64)
    seed_b = bytes.fromhex("4" * 64)
    signer_a = make_ed25519_signer(seed_a)
    pubkey_b = ed25519_public_key_bytes(seed_b)
    sig = await signer_a(b"canonical")
    assert verify_ed25519_signature(b"canonical", sig, pubkey_b) is False


def test_ed25519_rejects_non_32_byte_seed():
    with pytest.raises(ValueError, match="32 bytes"):
        make_ed25519_signer(b"short seed")
    with pytest.raises(ValueError, match="32 bytes"):
        ed25519_public_key_bytes(b"short")
    with pytest.raises(ValueError, match="32 bytes"):
        verify_ed25519_signature(b"x", b"y", b"short pubkey")


@pytest.mark.asyncio
async def test_produce_attestation_with_real_ed25519_signature_verifies():
    """End-to-end: produce_attestation with Ed25519 signer → third-party
    verification with verify_ed25519_signature passes against the same
    canonical bytes."""
    seed = bytes.fromhex("9" * 64)
    pubkey = ed25519_public_key_bytes(seed)

    att = await produce_attestation(
        record_uri="at://did:web:test/test.example.foo/abc",
        record_cid="bafy-cid-12345",
        record={"v": 1, "hello": "world"},
        rule=_mock_rule(),
        cell_id="CellA",
        cell_node="node-0.test",
        signer=make_ed25519_signer(seed),
    )

    # Re-derive the canonical bytes and verify the signature attached to
    # the attestation matches.
    canonical = canonical_attestation_bytes(
        record_cid=att.record_cid,
        cell_id=att.cell_id,
        verdict=att.verdict,
        reason=att.reason or "",
        membrane_version=att.membrane_version,
        attested_at=att.attested_at,
    )
    assert verify_ed25519_signature(canonical, att.signature, pubkey) is True


# ── Cell signer resolver chain ──────────────────────────────────────


def test_make_cell_signer_falls_back_to_deterministic_when_no_keys(monkeypatch):
    """With Keychain unavailable + no env var, resolver returns the
    deterministic test signer with source label."""
    # Force keychain miss by clearing PATH so `security` isn't found
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.delenv("CELL_PRIVATE_KEY_TestCellX", raising=False)
    signer, source = make_cell_signer("TestCellX")
    assert source == "deterministic"
    assert callable(signer)


@pytest.mark.asyncio
async def test_make_cell_signer_picks_env_key_when_present(monkeypatch):
    seed_hex = "7" * 64
    monkeypatch.setenv("PATH", "/nonexistent")  # block keychain
    monkeypatch.setenv("CELL_PRIVATE_KEY_TestCellY", seed_hex)
    signer, source = make_cell_signer("TestCellY")
    assert source == "env"
    # Should produce a 64-byte Ed25519 signature, not the 32-byte sha256
    sig = await signer(b"canonical")
    assert len(sig) == 64
    # Verifies under the corresponding public key
    pubkey = ed25519_public_key_bytes(bytes.fromhex(seed_hex))
    assert verify_ed25519_signature(b"canonical", sig, pubkey) is True


def test_make_cell_signer_ignores_malformed_env_key(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setenv("CELL_PRIVATE_KEY_TestCellZ", "not-hex")
    signer, source = make_cell_signer("TestCellZ")
    assert source == "deterministic"


def test_witness_request_from_wire():
    payload = {
        "v": 1,
        "recordUri": "at://x/y/z",
        "recordCid": "bafy",
        "record": {"v": 1, "label": "Mountain"},
        "rule": {
            "v": 1,
            "nsid": "com.etzhayyim.maps.feature",
            "schemaRef": {"path": "lex.json", "contentHash": "0" * 64},
            "policyRef": {"path": "p.rego", "contentHash": "0" * 64},
            "cellRef": {"path": "cell/", "contentHash": "0" * 64},
            "quorumSize": 5,
            "quorumThreshold": 3,
            "registeredAt": "2026-05-23T00:00:00Z",
        },
    }
    req = WitnessRequest.from_wire(payload)
    assert req.record_uri == "at://x/y/z"
    assert req.record_cid == "bafy"
    assert req.record["label"] == "Mountain"
    assert req.rule.nsid == "com.etzhayyim.maps.feature"
