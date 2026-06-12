"""``Function`` — a registered callable with Modal-shaped invocation methods.

    f.local(*args, **kwargs)   run the Python body in CPython, in-process. The
                               llm.invoke inside it routes over HTTP to the node
                               (infer.run). For development and tests.
    f.remote(*args, **kwargs)  the designed execution path: the body runs on the
                               kotoba node as a **WASM component** (py→wasm→kotoba)
                               via invoke.run. The llm.invoke inside the compiled
                               body binds to the kotoba:kais/llm WIT import.
    f.map(iterable)            remote() over each item (sequential in this MVP).

`.remote()` and `.local()` are NOT equivalent: different execution location
(node-WASM vs CPython) and different llm binding (WIT vs HTTP). The decorated
body is the single source compiled for both.
"""

from __future__ import annotations

import base64
import functools
import os
import tempfile
from typing import TYPE_CHECKING, Any, Callable, Iterable, List, Optional

from . import _build
from ._codec import decode_result, encode_ctx
from ._context import activate
from ._errors import ConfigError

if TYPE_CHECKING:  # pragma: no cover
    from ._app import App


class Function:
    def __init__(
        self,
        fn: Callable,
        *,
        app: "App",
        name: str,
        gpu: Optional[str] = None,
        program_cid: Optional[str] = None,
        program_type: str = "wasm-node",
        max_new_tokens: Optional[int] = None,
        builder: Optional[str] = None,
        wasm: Optional[bytes] = None,
        wasm_path: Optional[str] = None,
    ):
        self._fn = fn
        self.app = app
        self.name = name
        self.gpu = gpu
        self.program_cid = program_cid  # optional metadata; node recomputes the CID
        self.program_type = program_type
        self.max_new_tokens = max_new_tokens
        self.builder = builder
        self.wasm = wasm
        self.wasm_path = wasm_path
        self._wasm_b64_cache: Optional[str] = None
        functools.update_wrapper(self, fn)

    # ── invocation ───────────────────────────────────────────────────────

    def __call__(self, *args, **kwargs):
        return self.local(*args, **kwargs)

    def local(self, *args, **kwargs):
        """Run the Python body in CPython under this App's context (llm → HTTP)."""
        with activate(self.app, self):
            return self._fn(*args, **kwargs)

    def remote(self, *args, **kwargs):
        """Run the body on the node as a WASM component (py→wasm→kotoba).

        Dispatches `invoke.run`, which **always requires the component bytes**
        (the node has no by-CID program store on this path). The bytes come from,
        in order: ``wasm=`` / ``wasm_path=`` (a pre-built component — works
        without the build toolchain), else a build via the configured toolchain
        (``ToolchainNotFound`` if none). A valid ``agent_did`` is required (the
        node's `validate_did` rejects empty/non-DID values). Note: the node must
        be built with the ``wasm-runtime`` feature or `invoke.run` is disabled.
        """
        if not self.app.agent_did:
            raise ConfigError(
                "agent_did is required for .remote() — invoke.run validates it. "
                "Set KOTOBA_AGENT_DID or App(agent_did='did:key:…')."
            )
        wasm_b64 = self._wasm_b64()  # always present (or ToolchainNotFound)
        ctx_b64 = base64.b64encode(encode_ctx(self.name, args, kwargs)).decode("ascii")
        resp = self.app.client.invoke(
            self.program_cid or "",
            ctx_b64,
            program_type=self.program_type,
            agent_did=self.app.agent_did,
            wasm_b64=wasm_b64,
        )
        out_b64 = resp.get("output_b64", "")
        if not out_b64:
            return None
        return decode_result(base64.b64decode(out_b64))

    def map(self, items: Iterable[Any]) -> List[Any]:
        """remote() over each item. Sequential in this MVP — see README; each
        call still dispatches to the node independently."""
        return [self.remote(x) for x in items]

    # ── component resolution ─────────────────────────────────────────────

    def _wasm_b64(self) -> str:
        """Return base64 component bytes for invoke.run (never None).

        Source order: cached → ``wasm=`` → ``wasm_path=`` → build via toolchain
        (raises ToolchainNotFound if none configured).
        """
        if self._wasm_b64_cache is not None:
            return self._wasm_b64_cache
        if self.wasm is not None:
            raw = self.wasm
        elif self.wasm_path is not None:
            with open(self.wasm_path, "rb") as f:
                raw = f.read()
        else:
            raw = self._build()
        self._wasm_b64_cache = base64.b64encode(raw).decode("ascii")
        return self._wasm_b64_cache

    def _build(self) -> bytes:
        import sys

        # Surface the clean ToolchainNotFound before resolving module paths.
        if not _build.have_builder(self.builder):
            from ._errors import ToolchainNotFound

            raise ToolchainNotFound(_build._GUIDANCE)

        mod = sys.modules.get(getattr(self._fn, "__module__", ""))
        entry_file = getattr(mod, "__file__", None)
        if not entry_file:
            from ._errors import ToolchainNotFound

            raise ToolchainNotFound(
                f"cannot locate source file for {self.name!r} "
                f"(module {self._fn.__module__!r}); pass program_cid= instead."
            )
        with tempfile.NamedTemporaryFile(suffix=".wasm", delete=False) as tmp:
            out = tmp.name
        return _build.build_component(os.path.abspath(entry_file), out, builder=self.builder)
