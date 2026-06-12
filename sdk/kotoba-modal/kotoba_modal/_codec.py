"""The kotoba_modal call-context wire contract — owned on both ends.

Request envelope (client → guest, carried as `invoke.run` `ctx_b64`):

    {"v": 1, "fn": <name>, "args": [...], "kwargs": {...}}

Response envelope (guest `run` return → `invoke.run` `output_b64`):

    {"v": 1, "ok": true,  "result": <value>}
    {"v": 1, "ok": false, "error": <message>}

The client (`Function.remote`) encodes the request and decodes the response; the
guest (`kotoba_modal.guest.handle_invoke`) decodes the request and encodes the
response. Both use these functions, so the contract is symmetric and unit-tested
in CPython — not a shape guessed against an unseen decoder.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from . import _cbor
from ._errors import RemoteError

CTX_VERSION = 1


def encode_ctx(fn_name: str, args, kwargs) -> bytes:
    return _cbor.dumps(
        {"v": CTX_VERSION, "fn": fn_name, "args": list(args), "kwargs": dict(kwargs)}
    )


def decode_ctx(ctx_cbor: bytes) -> Tuple[str, List[Any], Dict[str, Any]]:
    d = _cbor.loads(ctx_cbor)
    if not isinstance(d, dict):
        raise ValueError("ctx is not a CBOR map")
    return d.get("fn", ""), list(d.get("args", [])), dict(d.get("kwargs", {}))


def encode_result(value: Any) -> bytes:
    return _cbor.dumps({"v": CTX_VERSION, "ok": True, "result": value})


def encode_error(message: str) -> bytes:
    return _cbor.dumps({"v": CTX_VERSION, "ok": False, "error": message})


def decode_result(output_cbor: bytes) -> Any:
    """Decode a guest response; raise RemoteError on an error envelope."""
    d = _cbor.loads(output_cbor)
    if not isinstance(d, dict):
        # Guest returned a non-envelope value — hand it back as-is.
        return d
    if d.get("ok") is False:
        raise RemoteError(0, str(d.get("error", "guest error")), "invoke.run")
    return d.get("result")
