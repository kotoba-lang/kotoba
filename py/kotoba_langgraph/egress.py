"""kotoba:kais/egress host import accessor for guests (ADR-2605312355).

Outbound HTTP for componentize-py guests, intended to live in the kotoba_langgraph
PY_PKG_DIR alongside checkpointer.py (which is how `kqe` reaches the guest).

STATUS (2026-05-31): host side complete + deployed; the `http`→`egress` rename
ELIMINATED the original `ImportError: outgoing_handler` collision. BUT a residual
componentize-py 0.23 quirk remains: it places `wit_world/imports/kqe.py` on the guest
`/world` filesystem but NOT `wit_world/imports/egress.py`, so `from wit_world.imports
import egress` still fails with `cannot import name 'egress'`. Reproduced with the
binding imported (a) lazily in the agent module, (b) at agent-module top level (freezes
it in the binary but the /world package shadows it), and (c) via this PY_PKG_DIR helper
mirroring checkpointer._try_kqe — none get egress.py onto /world. Why kqe.py is copied
but egress.py is not — despite identical import patterns — needs componentize-py-level
investigation (its module→/world copy logic treats the newly-added interface differently
than the original kqe/kse/auth/llm/chain/evm set). This helper is the right abstraction
and will work once that copy step includes egress.
"""

from __future__ import annotations

from typing import Optional


def _try_egress():
    """Return (egress module, True) inside a kotoba WASM guest, (None, False) otherwise."""
    try:
        from wit_world.imports import egress
        return egress, True
    except ImportError:
        return None, False


def fetch(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    body: Optional[bytes] = None,
    timeout_ms: int = 30000,
) -> tuple[int, bytes]:
    """Blocking outbound HTTP via the host egress client; returns (status, body_bytes)."""
    egress, ok = _try_egress()
    if not ok:
        raise RuntimeError("kotoba:kais/egress unavailable (not running inside a kotoba guest)")
    from componentize_py_types import Err

    hdr = [(k, v) for k, v in (headers or {}).items()]
    try:
        status, data = egress.fetch(method.upper(), url, hdr, body, int(timeout_ms))
    except Err as exc:  # result<_, string> error arm
        raise RuntimeError(f"egress: {exc.value}")
    return status, bytes(data)
