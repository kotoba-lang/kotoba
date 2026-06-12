"""HTTP client stubs.

R0 ships the module so the wiring is visible. R1 lands actual ``httpx`` calls
behind the same function signatures.
"""

from . import comfyui, kotoba_vm, litellm, ollama

__all__ = ["litellm", "ollama", "comfyui", "kotoba_vm"]
