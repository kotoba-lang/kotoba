"""kotodama.checkpointer — LangGraph checkpoint savers for the etzhayyim
substrate.

The primary export is ``MstCheckpointSaver``, a thin
``BaseCheckpointSaver`` subclass that proxies every checkpoint operation
over a Unix-socket (or TCP) wire to the ``@etzhayyim/sdk`` TypeScript
checkpointer sidecar. The TS sidecar is the only seam allowed to import
MST / IPFS / viem clients (ADR-2605172100), so this Python module holds
zero substrate logic — it is pure IPC.

Authoritative ADR: 2605171800 (LangGraph Pregel → MstCheckpointSaver →
atproto MST → IPFS → Base L2 anchor pipeline).
"""
from __future__ import annotations

from .mst_saver import (
    MST_CHECKPOINT_PROTOCOL_VERSION,
    MstCheckpointSaver,
    MstCheckpointSaverError,
    MstCheckpointSaverProtocolError,
)

__all__ = [
    "MstCheckpointSaver",
    "MstCheckpointSaverError",
    "MstCheckpointSaverProtocolError",
    "MST_CHECKPOINT_PROTOCOL_VERSION",
]
