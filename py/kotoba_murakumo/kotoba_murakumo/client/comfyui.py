"""ComfyUI client — R0 stub.

Used for image / video gen via the EVO-X2 ComfyUI endpoint at :8188.
"""

from __future__ import annotations

from ..exceptions import MurakumoCompatNotImplemented


def submit_prompt(*, url: str, workflow: dict, timeout_s: float = 600.0) -> bytes:
    raise MurakumoCompatNotImplemented(
        "comfyui.submit_prompt",
        f"live dispatch lands R1 (would POST {url}/prompt with workflow JSON)",
    )
