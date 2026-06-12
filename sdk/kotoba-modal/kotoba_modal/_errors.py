"""Exception types for kotoba_modal."""


class KotobaModalError(Exception):
    """Base class for all kotoba_modal errors."""


class ConfigError(KotobaModalError):
    """The App / Client is missing required configuration (URL, token, …)."""


class ToolchainNotFound(KotobaModalError):
    """The py→wasm build toolchain (componentize-py / build-pywasm.bb) is not
    available, so a `@app.function` body cannot be compiled to a component."""


class NoActiveAppError(KotobaModalError):
    """``llm.invoke`` was called with no active App context.

    An App context is active inside ``Function.local(...)`` and inside an
    explicit ``with app.run_local():`` block. Outside of those, call the node
    directly via ``app.client.infer(...)`` or ``Function.remote(...)``.
    """


class RemoteError(KotobaModalError):
    """The kotoba node returned a non-2xx response for an XRPC call."""

    def __init__(self, status: int, body: str, nsid: str):
        self.status = status
        self.body = body
        self.nsid = nsid
        super().__init__(f"{nsid} failed: HTTP {status}: {body}")
