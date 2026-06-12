"""did_auth.py — Python did:key Ed25519 nonce challenge verifier.

Companion to the TS daemon's `did-auth.ts` and the svelte appview's
`did-auth.ts`. Issues short-lived single-use nonces from `/auth/nonce`
and verifies `Authorization: DIDSig <did:key>:<nonce_id>:<sig_b64url>`
headers.

Authoritative ADR: 90-docs/adr/2605191657-ameno-daemon-did-auth.md
"""
from __future__ import annotations

import base64
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

# `cryptography` is the standard Python crypto lib. We lazy-import so
# hosts that don't enable DID auth don't pay for it at startup.
_ED25519_BACKEND_IMPORTED = False
_InvalidSignature: Any = None
_Ed25519PublicKey: Any = None


def _load_backend() -> None:
    global _ED25519_BACKEND_IMPORTED, _InvalidSignature, _Ed25519PublicKey
    if _ED25519_BACKEND_IMPORTED:
        return
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
    except ImportError as e:
        raise RuntimeError(
            "DID auth requires `cryptography`. Install with: "
            "pip install cryptography"
        ) from e
    _InvalidSignature = InvalidSignature
    _Ed25519PublicKey = Ed25519PublicKey
    _ED25519_BACKEND_IMPORTED = True


# multibase base58btc alphabet (Bitcoin / IPFS).
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58_decode(s: str) -> bytes:
    """Pure-Python base58btc decode. ~256-byte inputs in our domain,
    perf irrelevant."""
    num = 0
    for ch in s:
        num *= 58
        idx = _B58_ALPHABET.find(ch)
        if idx < 0:
            raise ValueError(f"invalid base58 char: {ch!r}")
        num += idx
    out = bytearray()
    while num > 0:
        out.append(num & 0xFF)
        num >>= 8
    out.reverse()
    # leading zero bytes correspond to leading '1's in the base58 form
    leading = 0
    for ch in s:
        if ch == "1":
            leading += 1
        else:
            break
    return bytes(b"\x00" * leading) + bytes(out)


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _decode_did_key(did: str) -> bytes:
    """did:key:z<base58>...  →  raw 32-byte Ed25519 public key."""
    if not did.startswith("did:key:z"):
        raise ValueError(f"not a did:key: {did!r}")
    body = _b58_decode(did[len("did:key:z") :])
    if len(body) != 34 or body[0] != 0xED or body[1] != 0x01:
        raise ValueError("did:key is not Ed25519 (multicodec prefix mismatch)")
    return body[2:]


# ── Nonce store ───────────────────────────────────────────────────────


@dataclass
class _NonceEntry:
    nonce: str
    expires_at_ms: int
    used: bool = False


NONCE_TTL_MS = 60_000
_nonces: dict[str, _NonceEntry] = {}
_nonces_lock = threading.Lock()


def _load_allowlist() -> frozenset[str]:
    """Parse AMENO_ALLOWED_DIDS env (comma-separated did:key list).

    Empty / unset → empty set → no allowlist enforced (any well-formed
    did:key accepted). Set → only listed DIDs may auth via DIDSig.
    ADR-2605191641.
    """
    import os as _os

    raw = _os.environ.get("AMENO_ALLOWED_DIDS", "")
    return frozenset(
        s.strip() for s in raw.split(",") if s.strip().startswith("did:key:z")
    )


_ALLOWED_DIDS = _load_allowlist()


def is_did_allowed(did: str) -> bool:
    return len(_ALLOWED_DIDS) == 0 or did in _ALLOWED_DIDS


def get_allowed_dids() -> list[str]:
    return list(_ALLOWED_DIDS)


def issue_nonce() -> dict[str, Any]:
    nonce_id = _b64url_encode(secrets.token_bytes(8))
    nonce = _b64url_encode(secrets.token_bytes(16))
    expires_at_ms = int(time.time() * 1000) + NONCE_TTL_MS
    with _nonces_lock:
        _nonces[nonce_id] = _NonceEntry(nonce=nonce, expires_at_ms=expires_at_ms)
    return {"nonce_id": nonce_id, "nonce": nonce, "expires_at_ms": expires_at_ms}


def _sweep_locked() -> None:
    now_ms = int(time.time() * 1000)
    dead = [k for k, v in _nonces.items() if v.used or v.expires_at_ms <= now_ms]
    for k in dead:
        del _nonces[k]


# ── Verification ──────────────────────────────────────────────────────


@dataclass
class VerificationResult:
    ok: bool
    did: str | None = None
    error: str | None = None


def verify_did_sig(auth_header: str | None) -> VerificationResult:
    """Verify a `DIDSig <did>:<nonce_id>:<sig_b64url>` Authorization header."""
    if not auth_header:
        return VerificationResult(ok=False, error="missing Authorization header")
    if not auth_header.startswith("DIDSig "):
        return VerificationResult(ok=False, error="not a DIDSig header")
    body = auth_header[len("DIDSig ") :].strip()
    sig_idx = body.rfind(":")
    if sig_idx < 0:
        return VerificationResult(ok=False, error="malformed DIDSig: no sig separator")
    id_idx = body.rfind(":", 0, sig_idx)
    if id_idx < 0:
        return VerificationResult(ok=False, error="malformed DIDSig: no nonce_id separator")
    did = body[:id_idx]
    nonce_id = body[id_idx + 1 : sig_idx]
    sig_b64 = body[sig_idx + 1 :]

    if not is_did_allowed(did):
        return VerificationResult(ok=False, error="did not in allowlist")

    with _nonces_lock:
        _sweep_locked()
        entry = _nonces.get(nonce_id)
        if entry is None:
            return VerificationResult(ok=False, error="nonce unknown or already consumed")
        if entry.used:
            return VerificationResult(ok=False, error="nonce already consumed")
        if entry.expires_at_ms <= int(time.time() * 1000):
            del _nonces[nonce_id]
            return VerificationResult(ok=False, error="nonce expired")

    try:
        pub = _decode_did_key(did)
    except Exception as e:
        return VerificationResult(ok=False, error=str(e))
    try:
        sig = _b64url_decode(sig_b64)
    except Exception:
        return VerificationResult(ok=False, error="signature is not base64url")

    _load_backend()
    try:
        pk = _Ed25519PublicKey.from_public_bytes(pub)
        pk.verify(sig, f"{nonce_id}.{entry.nonce}".encode("utf-8"))
    except Exception:
        return VerificationResult(ok=False, error="signature verification failed")

    with _nonces_lock:
        # Single-use.
        entry.used = True

    return VerificationResult(ok=True, did=did)
