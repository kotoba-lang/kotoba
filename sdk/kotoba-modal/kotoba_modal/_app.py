"""``App`` — the Modal-shaped entry point.

    import kotoba_modal as modal
    app = modal.App("infer")

    @app.function(gpu="mac-mini")     # gpu hint → routed to the Murakumo fleet
    def generate(prompt: str) -> str:
        return modal.llm.invoke(prompt)

    generate.remote("hello")          # → infer.run on the fleet

Configuration is read from the environment (so the same code runs against dev,
LAN, or the edge Worker) and may be overridden per-App:

    KOTOBA_NODE_URL         base URL of the kotoba node (required)
    KOTOBA_OPERATOR_TOKEN   operator JWT (Bearer; sub == operator DID)
    KOTOBA_INTERNAL_SECRET  x-internal-trust secret (direct LAN/pod access only)
    KOTOBA_AGENT_DID        default agent DID for component invokes
"""

from __future__ import annotations

import os
from typing import Callable, Optional, overload

from ._client import KotobaNodeClient
from ._context import activate
from ._errors import ConfigError
from ._function import Function


class App:
    def __init__(
        self,
        name: str = "kotoba",
        *,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        internal_secret: Optional[str] = None,
        agent_did: Optional[str] = None,
        client: Optional[KotobaNodeClient] = None,
    ):
        self.name = name
        self.agent_did = agent_did or os.environ.get("KOTOBA_AGENT_DID", "")
        self.functions: "dict[str, Function]" = {}

        if client is not None:
            self._client: Optional[KotobaNodeClient] = client
        else:
            url = base_url or os.environ.get("KOTOBA_NODE_URL")
            self._client = (
                KotobaNodeClient(
                    url,
                    token=token or os.environ.get("KOTOBA_OPERATOR_TOKEN"),
                    internal_secret=internal_secret
                    or os.environ.get("KOTOBA_INTERNAL_SECRET"),
                )
                if url
                else None
            )

    @property
    def client(self) -> KotobaNodeClient:
        if self._client is None:
            raise ConfigError(
                "no kotoba node configured: set KOTOBA_NODE_URL or pass "
                "base_url=/client= to App(...)"
            )
        return self._client

    # Used bare (@app.function) → returns the wrapped Function.
    @overload
    def function(self, _fn: Callable) -> Function: ...

    # Used with args (@app.function(...)) → returns a decorator.
    @overload
    def function(
        self,
        _fn: None = ...,
        *,
        gpu: Optional[str] = ...,
        program_cid: Optional[str] = ...,
        program_type: str = ...,
        max_new_tokens: Optional[int] = ...,
        builder: Optional[str] = ...,
        wasm: Optional[bytes] = ...,
        wasm_path: Optional[str] = ...,
        name: Optional[str] = ...,
    ) -> Callable[[Callable], Function]: ...

    def function(
        self,
        _fn: Optional[Callable] = None,
        *,
        gpu: Optional[str] = None,
        program_cid: Optional[str] = None,
        program_type: str = "wasm-node",
        max_new_tokens: Optional[int] = None,
        builder: Optional[str] = None,
        wasm: Optional[bytes] = None,
        wasm_path: Optional[str] = None,
        name: Optional[str] = None,
    ):
        """Register a function for execution on the kotoba node.

        Execution model (py→wasm→kotoba):

        * ``.remote(*args)`` runs the body **on the node as a WASM component**
          (``invoke.run``). The body is compiled with the configured toolchain
          (or supply ``program_cid=`` for an already-deployed component). Inside
          the compiled body, ``modal.llm.invoke`` binds to the ``kotoba:kais/llm``
          WIT import.
        * ``.local(*args)`` runs the body in CPython for dev/tests; there
          ``modal.llm.invoke`` routes over HTTP (``infer.run``).

        ``gpu=`` is a routing hint only; the node's configured engine is
        authoritative (CHARTER-RIDER §(i): religious-corp inference runs on the
        Murakumo fleet). ``builder=`` overrides the ``KOTOBA_PYWASM_BUILD``
        build script.
        """

        def wrap(fn: Callable) -> Function:
            f = Function(
                fn,
                app=self,
                gpu=gpu,
                program_cid=program_cid,
                program_type=program_type,
                max_new_tokens=max_new_tokens,
                builder=builder,
                wasm=wasm,
                wasm_path=wasm_path,
                name=name or fn.__name__,
            )
            self.functions[f.name] = f
            return f

        return wrap(_fn) if callable(_fn) else wrap

    def run_local(self):
        """Activate this App so ``llm.invoke`` resolves to its client.

        Usage: ``with app.run_local(): ...``
        """
        return activate(self)
