"""Generic-primitive worker for com.etzhayyim.tools.crypto.* (ADR-2605082000 Phase D).

Stateless content-addressing primitive. Replaces per-actor inline
``hashlib.sha256(...).hexdigest()`` / ``base64.b64encode(...)``
py_primitive nodes (e.g. copyright store_blob's vertex_id derivation).

Surface:

  com.etzhayyim.tools.crypto.hash({"algorithm": "sha256"|"sha1"|"md5",
                             "input": "<utf8 string>",
                             "encoding": "hex"|"base64"})
    → {"hash": "<digest>"}

The dispatcher convention does not apply — namespace is
``com.etzhayyim.tools.crypto``, wired via ``register_overrides`` in mcp_dispatch.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

_ALGORITHMS = {"sha256", "sha1", "md5", "sha512"}
_ENCODINGS = {"hex", "base64"}


async def task_crypto_hash(
    *,
    algorithm: str = "sha256",
    input: Any = None,
    encoding: str = "hex",
    **_ignored: Any,
) -> dict[str, Any]:
    """Return ``hashlib.<algo>(input).<encoding>``.

    ``input`` may be str (utf-8 encoded) or bytes-like. ``algorithm`` and
    ``encoding`` are validated against fixed allowlists so a typo at the
    config layer surfaces immediately rather than silently falling back.
    """
    if algorithm not in _ALGORITHMS:
        return {"error": f"algorithm must be one of {sorted(_ALGORITHMS)}, got {algorithm!r}"}
    if encoding not in _ENCODINGS:
        return {"error": f"encoding must be one of {sorted(_ENCODINGS)}, got {encoding!r}"}
    if input is None:
        return {"error": "input is required"}

    if isinstance(input, str):
        data = input.encode("utf-8")
    elif isinstance(input, (bytes, bytearray)):
        data = bytes(input)
    else:
        return {"error": f"input must be str or bytes, got {type(input).__name__}"}

    digest = hashlib.new(algorithm, data).digest()
    if encoding == "hex":
        return {"hash": digest.hex()}
    return {"hash": base64.b64encode(digest).decode("ascii")}
