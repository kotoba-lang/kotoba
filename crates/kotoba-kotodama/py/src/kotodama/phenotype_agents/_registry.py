"""Dynamic loader for the per-adherent PhenotypeAgent fleet.

Each agent file is a self-contained Python module that exports a
compiled ``graph`` and a ``META`` dict, loaded dynamically by name.

This module is **not** the generator — it only loads what has already
been emitted. See ``scripts/gen_phenotype_agent.py`` for the generator.
"""

from __future__ import annotations

import hashlib
import importlib
import pkgutil
from typing import Any, Optional

AGENT_PACKAGE = "kotodama.phenotype_agents"


def did_short_hash(did: str) -> str:
    """Stable 12-hex-char identifier for a DID. Used as the agent file
    stem: ``a<short>.py``.

    blake2b is preferred over keccak/sha256 here because we want a fast,
    collision-resistant, fixed-length identifier for filesystem use; the
    on-chain identity is the DID itself and the SBT tokenId, not this
    hash.
    """
    h = hashlib.blake2b(did.encode("utf-8"), digest_size=8).hexdigest()
    return h


def _module_name(did: str) -> str:
    return f"{AGENT_PACKAGE}.a{did_short_hash(did)}"


def load_agent(did: str) -> Optional[Any]:
    """Import the agent module for ``did`` if it has been generated.

    Returns the module object (with ``graph`` and ``META`` attributes)
    or ``None`` if the agent file does not yet exist. Callers should
    fall back to the shared default cell in
    :mod:`kotodama.eligibility.cell` when ``None`` is returned.
    """
    try:
        return importlib.import_module(_module_name(did))
    except ModuleNotFoundError:
        return None


def list_agents() -> list[str]:
    """List short-hash stems of all currently-generated agents."""
    pkg = importlib.import_module(AGENT_PACKAGE)
    return sorted(
        m.name.removeprefix("a")
        for m in pkgutil.iter_modules(pkg.__path__)
        if m.name.startswith("a") and not m.ispkg
    )
