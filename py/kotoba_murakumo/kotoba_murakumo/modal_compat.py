"""Drop-in ``import modal`` shim.

Usage::

    import kotoba_murakumo.modal_compat as modal

    stub = modal.App("my-inference")

    @stub.function(gpu="A10G")
    def f(x: str) -> str: ...

Every name here intentionally matches Modal's public surface. Where the surface
diverges (rare: ``Image.from_registry``, ``Sandbox``, ``web_endpoint``), the
divergence raises :class:`kotoba_murakumo.exceptions.MurakumoCompatNotImplemented`
with the constitutional reason — never silent.

Modal® is a registered trademark of Modal Labs Inc. This shim is API-compat
only (Google v. Oracle 2021 API fair-use, analogous to ADR-2605261800 §D10
``nv_compat``). It does not link to Modal Labs servers.
"""

from __future__ import annotations

from .app import App
from .cls import enter, exit, method
from .exceptions import (
    CharterViolation,
    FleetUnreachable,
    MurakumoCompatNotImplemented,
)
from .image import Image
from .secret import Secret
from .volume import Volume

# Modal historically called this `Stub`; alias for legacy code.
Stub = App


# Modal exposes its GPU classes via ``modal.gpu`` *and* via string ``gpu="A10G"``.
# We honor both — the App.function decorator accepts either form.
class _GpuNamespace:
    from .gpu import (
        Any,
        EvoX2,
        MacMini,
        WebGPU,
    )

    # NVIDIA-class names: each returns an EvoX2 selector (with warning logged
    # on resolve). This is the honest mapping per ADR-2605282000 N5.
    @staticmethod
    def T4() -> "EvoX2":  # type: ignore[name-defined]
        from .gpu import EvoX2
        return EvoX2()

    @staticmethod
    def L4() -> "EvoX2":  # type: ignore[name-defined]
        from .gpu import EvoX2
        return EvoX2()

    @staticmethod
    def A10G() -> "EvoX2":  # type: ignore[name-defined]
        from .gpu import EvoX2
        return EvoX2()

    @staticmethod
    def A100(*, memory: int = 40) -> "EvoX2":  # type: ignore[name-defined]  # noqa: ARG004
        from .gpu import EvoX2
        return EvoX2()

    @staticmethod
    def H100() -> "EvoX2":  # type: ignore[name-defined]
        from .gpu import EvoX2
        return EvoX2()

    @staticmethod
    def H200() -> "EvoX2":  # type: ignore[name-defined]
        from .gpu import EvoX2
        return EvoX2()


gpu = _GpuNamespace()


# Modal surfaces that we deliberately don't support: declared here so callers
# see a single canonical reason string.

def web_endpoint(*args, **kwargs):  # noqa: ARG001
    raise MurakumoCompatNotImplemented(
        "modal.web_endpoint",
        "expose HTTP via yoro / kotoba-server XRPC instead; ADR-2605282000",
    )


def asgi_app(*args, **kwargs):  # noqa: ARG001
    raise MurakumoCompatNotImplemented(
        "modal.asgi_app",
        "expose HTTP via yoro / kotoba-server XRPC instead; ADR-2605282000",
    )


def fastapi_endpoint(*args, **kwargs):  # noqa: ARG001
    raise MurakumoCompatNotImplemented(
        "modal.fastapi_endpoint",
        "expose HTTP via yoro / kotoba-server XRPC instead; ADR-2605282000",
    )


class Sandbox:
    """Modal ``modal.Sandbox`` is intentionally unsupported."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ARG002
        raise MurakumoCompatNotImplemented(
            "modal.Sandbox",
            "no container runtime in fleet; use Image.wasm_component instead; ADR-2605282000",
        )


__all__ = [
    "App",
    "Stub",
    "Image",
    "Volume",
    "Secret",
    "gpu",
    "enter",
    "exit",
    "method",
    "web_endpoint",
    "asgi_app",
    "fastapi_endpoint",
    "Sandbox",
    "CharterViolation",
    "FleetUnreachable",
    "MurakumoCompatNotImplemented",
]
