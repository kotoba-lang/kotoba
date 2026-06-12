"""kotoba_modal — a Modal-shaped authoring SDK for kotoba nodes.

Write functions with familiar Modal ergonomics; ``.remote()`` dispatches them to
a kotoba node, whose inference engine on a religious-corp deployment is the
**Murakumo Mac mini fleet** (ADR-2605202345 / ADR-2605215000).

    import kotoba_modal as modal

    app = modal.App("infer")

    @app.function(gpu="mac-mini")        # gpu hint → routed to the fleet
    def generate(prompt: str) -> str:
        return modal.llm.invoke(prompt)

    print(generate.remote("hello"))      # → infer.run on the fleet
    print(generate.local("hello"))       # → runs the Python body here

This is *authoring* compatibility, not wire compatibility: the official Modal
gRPC protocol is not implemented (see the package README / ADR-2606060004).
"""

from . import guest, llm
from ._app import App
from ._client import KotobaNodeClient
from ._context import active_app
from ._errors import (
    ConfigError,
    KotobaModalError,
    NoActiveAppError,
    RemoteError,
    ToolchainNotFound,
)
from ._function import Function

__version__ = "0.1.0"

__all__ = [
    "App",
    "Function",
    "KotobaNodeClient",
    "llm",
    "guest",
    "active_app",
    "KotobaModalError",
    "ConfigError",
    "NoActiveAppError",
    "RemoteError",
    "ToolchainNotFound",
    "__version__",
]
