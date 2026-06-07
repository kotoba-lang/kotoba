"""Image — Modal-compatible build spec.

R0: records intent (chain of mutations) without executing anything. The image
ID is the SHA-256 of the canonical JSON representation, which is also the
content-address used for the future kotoba-kse Vault binding (R1).

Modal compatibility surface intentionally narrow:

* ``Image.debian_slim(python_version=...)`` → identity image carrying the
  requested python version as metadata.
* ``.pip_install(*pkgs)`` → records the pkg list for R1 Charter Rider scan.
* ``.run_commands(*cmds)`` → records the cmd list.
* ``.env({...})`` → records env additions.
* ``.wasm_component(path)`` → records that the image *is* a WASM Component
  bytes file (the long-term path; LLM-only callers won't touch this).

Surfaces that always raise ``MurakumoCompatNotImplemented``:

* ``Image.from_registry(...)`` — commercial registry forbidden per Charter
  Rider §2(c)+(e); ADR-2605282000 N2.
* ``Image.from_dockerhub(...)`` — same reason.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .exceptions import MurakumoCompatNotImplemented


@dataclass(frozen=True, slots=True)
class _Op:
    op: str
    args: tuple[Any, ...]
    kwargs: tuple[tuple[str, Any], ...]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "args": list(self.args),
            "kwargs": dict(self.kwargs),
        }


@dataclass(frozen=True, slots=True)
class Image:
    base: str
    ops: tuple[_Op, ...] = field(default_factory=tuple)

    # ---- constructors --------------------------------------------------------

    @classmethod
    def debian_slim(cls, python_version: str = "3.11") -> "Image":
        return cls(base=f"debian-slim:py{python_version}")

    @classmethod
    def wasm_component(cls, path: str) -> "Image":
        return cls(base=f"wasm-component:{path}")

    @classmethod
    def from_registry(cls, tag: str) -> "Image":  # noqa: ARG003
        raise MurakumoCompatNotImplemented(
            "Image.from_registry",
            "commercial container registries forbidden per Charter Rider §2(c)+(e) "
            "and ADR-2605282000 N2 — use Image.wasm_component or Image.debian_slim",
        )

    @classmethod
    def from_dockerhub(cls, tag: str) -> "Image":  # noqa: ARG003
        raise MurakumoCompatNotImplemented(
            "Image.from_dockerhub",
            "Docker Hub forbidden per Charter Rider §2(c)+(e); see ADR-2605282000 N2",
        )

    # ---- chainable ops -------------------------------------------------------

    def _push(self, op: str, *args: Any, **kwargs: Any) -> "Image":
        return Image(
            base=self.base,
            ops=self.ops + (_Op(op=op, args=args, kwargs=tuple(kwargs.items())),),
        )

    def pip_install(self, *packages: str) -> "Image":
        return self._push("pip_install", *packages)

    def run_commands(self, *commands: str) -> "Image":
        return self._push("run_commands", *commands)

    def env(self, vars: dict[str, str]) -> "Image":
        return self._push("env", **vars)

    # ---- identity ------------------------------------------------------------

    def to_jsonable(self) -> dict[str, Any]:
        return {"base": self.base, "ops": [o.to_jsonable() for o in self.ops]}

    @property
    def image_id(self) -> str:
        """Content-address (sha256) of the canonical JSON representation.

        R1: also used as the kotoba-kse Vault key.
        """
        canonical = json.dumps(
            self.to_jsonable(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
