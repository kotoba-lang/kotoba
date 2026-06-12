"""GPU type selectors.

Each class describes a *requested* compute resource. Resolution to a concrete
fleet endpoint happens in :mod:`kotoba_murakumo._internal.routing`.

Modal-style string GPUs ("A10G", "A100", "H100", "T4", "L4") are accepted via
:func:`from_modal_string` and mapped to fleet equivalents. NVIDIA-class
requests log a warning but always route to ROCm EVO-X2 — there is no NVIDIA
hardware in the fleet (ADR-2605282000 N5: honesty, not bait-and-switch).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GpuSpec:
    """Base class for fleet GPU selectors."""

    kind: str


@dataclass(frozen=True, slots=True)
class EvoX2(GpuSpec):
    """EVO-X2 backend selector.

    Default endpoint: LiteLLM at :4000. Set ``prefer="ollama"`` for direct
    ollama :11434, or ``prefer="comfyui"`` for image gen :8188.
    """

    prefer: str = "litellm"   # "litellm" | "ollama" | "comfyui"
    vram_gib: int | None = None

    def __init__(self, *, prefer: str = "litellm", vram_gib: int | None = None) -> None:
        object.__setattr__(self, "kind", "evo-x2")
        object.__setattr__(self, "prefer", prefer)
        object.__setattr__(self, "vram_gib", vram_gib)


@dataclass(frozen=True, slots=True)
class MacMini(GpuSpec):
    """One Mac mini node, addressed by tribe name.

    Uses the node's own-node Ollama (gemma4:e4b default).
    """

    node: str

    def __init__(self, *, node: str) -> None:
        object.__setattr__(self, "kind", "mac-mini")
        object.__setattr__(self, "node", node)


@dataclass(frozen=True, slots=True)
class WebGPU(GpuSpec):
    """WebGPU compute on any fleet node (Metal on Mac mini, Vulkan on EVO-X2).

    R2 scope. R0 raises ``MurakumoCompatNotImplemented`` when actually
    dispatched.
    """

    def __init__(self) -> None:
        object.__setattr__(self, "kind", "webgpu")


@dataclass(frozen=True, slots=True)
class Any(GpuSpec):
    """Let the LiteLLM gateway route by model name.

    Equivalent to passing ``gpu=None`` or ``gpu="any"``.
    """

    def __init__(self) -> None:
        object.__setattr__(self, "kind", "any")


# ---------- Modal-string compatibility ----------------------------------------

# Modal GPU strings → fleet equivalents.
# NVIDIA-class strings all map to EVO-X2 with a warning at resolve time.
_MODAL_GPU_MAP: dict[str, type[GpuSpec]] = {
    "T4": EvoX2,
    "L4": EvoX2,
    "A10G": EvoX2,
    "A100": EvoX2,
    "A100-40GB": EvoX2,
    "A100-80GB": EvoX2,
    "H100": EvoX2,
    "H200": EvoX2,
    "L40S": EvoX2,
    "any": Any,
}


def from_modal_string(s: str) -> GpuSpec:
    """Resolve a Modal-style ``gpu="A10G"`` string to a fleet selector.

    NVIDIA-class strings log a one-line warning so the caller knows the routing
    is honest (ROCm EVO-X2, not NVIDIA).
    """
    cls = _MODAL_GPU_MAP.get(s)
    if cls is None:
        from .exceptions import MurakumoCompatNotImplemented
        raise MurakumoCompatNotImplemented(
            f"gpu={s!r}",
            f"unknown Modal GPU string; fleet exposes {sorted(_MODAL_GPU_MAP)}",
        )
    if cls is EvoX2 and s != "EvoX2":
        logger.warning(
            "gpu=%r requested; fleet has no NVIDIA hardware — routed to EVO-X2 "
            "(ROCm gfx1151, 32 GB VRAM). Expect throughput delta vs Modal.",
            s,
        )
    return cls()


__all__ = ["GpuSpec", "EvoX2", "MacMini", "WebGPU", "Any", "from_modal_string"]
