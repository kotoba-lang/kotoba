"""Volume — persistent storage handle.

R0: in-process name registry (no IO). R1: each Volume binds to a kotoba-kse
Vault CID with pin/unpin via Kubo.
"""

from __future__ import annotations

from dataclasses import dataclass

_REGISTRY: dict[str, "Volume"] = {}


@dataclass(frozen=True, slots=True)
class Volume:
    name: str
    cid: str | None = None
    create_if_missing: bool = False

    @classmethod
    def from_name(
        cls,
        name: str,
        *,
        cid: str | None = None,
        create_if_missing: bool = False,
    ) -> "Volume":
        existing = _REGISTRY.get(name)
        if existing is not None:
            return existing
        if not create_if_missing and cid is None:
            # Modal semantics: from_name with no create_if_missing raises if the
            # volume doesn't exist. We match that, but the underlying store is
            # the local registry at R0.
            raise KeyError(
                f"Volume {name!r} not registered; pass create_if_missing=True "
                "or cid=<...> to bind"
            )
        v = cls(name=name, cid=cid, create_if_missing=create_if_missing)
        _REGISTRY[name] = v
        return v
