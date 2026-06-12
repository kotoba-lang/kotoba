"""py→wasm build — bundled toolchain with honest gating.

The component build is now **bundled**: the `kotoba-node` WIT lives under
`kotoba_modal`'s sibling `wit/` directory and `scripts/build-pywasm.bb` drives
`componentize-py`. A real component has been built and verified end-to-end (see
the README / the `build` integration test). What is still unverifiable without a
live node is the *on-node execution* of the built component.

Builder resolution (in order):
  1. ``builder=`` on the decorator, or ``KOTOBA_PYWASM_BUILD`` — an explicit
     script invoked as ``<script> <entry.py> -o <out.wasm>``.
  2. the bundled ``scripts/build-pywasm.bb`` — used only when ``componentize-py``
     and Babashka ``bb`` are resolvable; install the Python side with ``pip
     install 'kotoba-modal[build]'`` and set ``BB_BIN`` when ``bb`` is pinned
     outside PATH.
  3. none available → ``ToolchainNotFound``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

from ._errors import ToolchainNotFound

_PKG_ROOT = os.path.dirname(os.path.abspath(__file__))
BUNDLED_SCRIPT = os.path.join(_PKG_ROOT, "scripts", "build-pywasm.bb")
BUNDLED_WIT = os.path.join(_PKG_ROOT, "wit", "world.wit")

_GUIDANCE = (
    "py→wasm build toolchain not available. To run @app.function bodies on the "
    "node, either:\n"
    "  • pip install 'kotoba-modal[build]' and install Babashka bb 1.12.x "
    "(or set BB_BIN) — uses the bundled scripts/build-pywasm.bb + wit/), or\n"
    "  • set KOTOBA_PYWASM_BUILD=/path/to/build-pywasm.bb, or\n"
    "  • pass wasm_path=/program_cid= to @app.function (pre-built component), or\n"
    "  • use .local() for development (runs in CPython; llm.invoke → infer.run)."
)


def _nonempty_env(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _componentize_py_available() -> bool:
    return bool(shutil.which("componentize-py") or _nonempty_env("COMPONENTIZE_PY"))


def _bb_command() -> Optional[str]:
    return _nonempty_env("BB_BIN") or shutil.which("bb")


def _bb_available() -> bool:
    return _bb_command() is not None


def _builder_command(script: str) -> list[str]:
    if script.endswith(".bb"):
        bb = _bb_command()
        if not bb:
            raise ToolchainNotFound(_GUIDANCE)
        return [bb, script]
    return [script]


def _explicit_builder(builder: Optional[str]) -> tuple[bool, Optional[str]]:
    if builder is not None:
        value = builder.strip()
        return True, value or None
    if "KOTOBA_PYWASM_BUILD" in os.environ:
        value = os.environ.get("KOTOBA_PYWASM_BUILD", "").strip()
        return True, value or None
    return False, None


def resolve_builder(builder: Optional[str] = None) -> Optional[str]:
    """Return a usable build script path, or None. See module docstring."""
    has_explicit, explicit = _explicit_builder(builder)
    if has_explicit:
        if not explicit:
            return None
        if shutil.which(explicit) or os.path.isfile(explicit):
            return explicit
        return None
    if os.path.isfile(BUNDLED_SCRIPT) and _componentize_py_available() and _bb_available():
        return BUNDLED_SCRIPT
    return None


def have_builder(builder: Optional[str] = None) -> bool:
    return resolve_builder(builder) is not None


def build_component(
    entry_py: str,
    out_wasm: str,
    *,
    builder: Optional[str] = None,
    timeout: float = 900.0,
) -> bytes:
    """Build `entry_py` into a WASM component, returning its bytes.

    Raises ToolchainNotFound when no builder is resolvable.
    """
    script = resolve_builder(builder)
    if not script:
        raise ToolchainNotFound(_GUIDANCE)
    subprocess.run(_builder_command(script) + [entry_py, "-o", out_wasm], check=True, timeout=timeout)
    with open(out_wasm, "rb") as f:
        return f.read()
