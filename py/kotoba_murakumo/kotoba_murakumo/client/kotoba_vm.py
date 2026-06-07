"""kotoba-vm Invoke ChainEntry dispatch client.

R1.2 reserves the surface; R2 wires real dispatch to a `kotoba-server` XRPC
endpoint that executes WASM Components via the `kotoba-vm::WasmExecutor` host
(see ``40-engine/kotoba/crates/kotoba-vm`` + ``kotoba-runtime``).

R2 dispatch shape (target)::

    POST {kotoba_server_base}/xrpc/com.etzhayyim.kotoba.vm.invoke
    body: {
      "program_cid": "bafy...",      # WASM Component CID (Vault-stored)
      "args_cid":    "bafy...",      # CBOR-encoded args (Vault-stored)
      "gas_limit":   10_000_000,     # per ADR-2605240001 ガス default
      "caller_did":  "did:web:...",
    }
    →  { "result_cid": "bafy...", "gas_used": <int> }

This makes ``gpu=gpu.WebGPU()`` and ``Image.wasm_component(...)`` from
:mod:`kotoba_murakumo` route through the same content-addressed substrate
that ``kotoba_langgraph`` already uses for graph execution — closing the
last R0/R1 gap where Murakumo fleet dispatch was OpenAI-compat-HTTP only.

R1.2 surface (today)
--------------------

Importable + signature stable; live dispatch raises
:class:`MurakumoCompatNotImplemented` with the R2 plan in the message.
This lets ``Function.remote()`` already include the kotoba-vm route in its
resolver tree without an API churn at R2 cutover.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..exceptions import MurakumoCompatNotImplemented


@dataclass(frozen=True, slots=True)
class InvokeRequest:
    """Inputs for one kotoba-vm Invoke."""

    program_cid: str
    args_cid: str
    caller_did: str
    gas_limit: int = 10_000_000


@dataclass(frozen=True, slots=True)
class InvokeResult:
    """Outputs of one kotoba-vm Invoke."""

    result_cid: str
    gas_used: int
    program_cid: str  # echoed for log correlation


def invoke(
    *,
    server_url: str,
    request: InvokeRequest,
    timeout_s: float = 600.0,
) -> InvokeResult:
    """Dispatch a WASM Component invocation through ``kotoba-server`` XRPC.

    R1.2 stub: raises :class:`MurakumoCompatNotImplemented` with the full R2
    target shape (so callers see exactly what will land).
    """
    raise MurakumoCompatNotImplemented(
        "kotoba_vm.invoke",
        f"R2 will POST {server_url.rstrip('/')}/xrpc/com.etzhayyim.kotoba.vm.invoke "
        f"with body={{program_cid={request.program_cid!r}, args_cid={request.args_cid!r}, "
        f"caller_did={request.caller_did!r}, gas_limit={request.gas_limit}}} → "
        "InvokeResult(result_cid, gas_used, program_cid). "
        "Lexicon com.etzhayyim.kotoba.vm.invoke lands in the same R2 commit. "
        "See ADR-2605282000 §'Subrepo integration status' R1.2→R2 closure plan."
    )


async def invoke_async(
    *,
    server_url: str,
    request: InvokeRequest,
    timeout_s: float = 600.0,
) -> InvokeResult:
    """Async sibling of :func:`invoke`; same R2 wire shape."""
    raise MurakumoCompatNotImplemented(
        "kotoba_vm.invoke_async",
        f"R2 async dispatch — see kotoba_vm.invoke for the target POST shape. "
        f"Will POST {server_url.rstrip('/')}/xrpc/com.etzhayyim.kotoba.vm.invoke."
    )
