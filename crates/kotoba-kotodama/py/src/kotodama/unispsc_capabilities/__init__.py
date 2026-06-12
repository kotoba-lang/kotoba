"""unispsc-capabilities — perceive/learn loop around UNSPSC actor invocations.

Per ADR-2605232100 Stage D (UNSPSC actor capability wiring). Each of the
18,342 UNSPSC actor graphs is wrapped at invocation time with a
substrate-compliant knowledge accumulation loop (kotoba-datomic-dht belief
store backed by AT-IPFS-local SQLite hot cache per ADR-2605211200).

Wrapping is opt-in via env (`ETZ_UNISPSC_CAPABILITY_WRAP=1`) so the
existing invokeAgent contract is preserved for callers that don't expect
the augmentation fields. When the env is unset the inner graph is
invoked directly with no wrapping cost.
"""

from __future__ import annotations

__version__ = "0.1.0"

from kotodama.unispsc_capabilities.wrapper import invoke_with_capability

__all__ = ["invoke_with_capability"]
