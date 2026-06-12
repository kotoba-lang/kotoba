"""
cell_runtime — kotoba-kotodama cell runtime contract.

Per ADR-2605202200 (Cell runtime contract).

Exports:
  - CellDeps : dependency injection container passed to every cell's build_graph
  - default_state_from_event : standard MST event → initial state mapping
  - default_thread_id_from_event : standard thread_id from MST event
  - HealthzStatus : healthz response shape

Each cell.py module under 20-actors/kotoba-kotodama/cells/<name>/cell.py MUST export:
  - build_graph(deps: CellDeps) -> CompiledStateGraph
  - state_from_event(event_record: dict, nsid: str) -> dict
  - thread_id_from_event(event_record: dict, nsid: str) -> str

Optional:
  - on_startup(deps: CellDeps) -> None
  - on_shutdown(deps: CellDeps) -> None
  - healthz_extra(deps: CellDeps) -> dict

cell_host imports the cell module by name, instantiates CellDeps from
fleet.toml + sidecar discovery, calls build_graph(deps), and drives the
graph via the trigger configured in fleet.toml.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CellDeps:
    """Dependency injection container passed to every cell's build_graph.

    cell-runner instantiates one CellDeps per cell at startup and threads
    it through build_graph. Individual cells access only the fields they
    need; unused fields stay None.

    Frozen so cells cannot accidentally mutate shared dependencies.
    """

    # Always populated
    cell_name: str
    node_name: str
    checkpointer: Any  # MstCheckpointSaver or fallback FileCheckpointSaver

    # Substrate ports (lazy-loaded by cell-host, None if not wired yet)
    sdk: Any = None  # @etzhayyim/sdk facade via subprocess RPC (ADR-2605171800)
    base_l2_port: Any = None  # web3.py to Base L2
    geth_private_port: Any = None  # web3.py to geth-private (chainId 260425)
    pds_client: Any = None  # atproto.PDS client (pds.etzhayyim.com)

    # LLM clients (only populated for cells that need them)
    llm_primary: Any = None  # claude-sonnet-4-6 or configured primary
    llm_fallback_local: Any = None  # Murakumo Gemma local fallback

    # Cell-specific config (from fleet.toml [cells.<cell_name>] block)
    config: dict[str, Any] = field(default_factory=dict)


def default_state_from_event(event_record: dict, nsid: str) -> dict:
    """Default mapping from MST event record to cell initial state.

    Event record shape (per @etzhayyim/sdk MST subscription):
        {
            "uri": "at://did:web:.../<nsid>/<rkey>",
            "cid": "bafyrei...",
            "collection": "<nsid>",
            "rkey": "<rkey>",
            "value": { ... lexicon input shape ... },
            "indexedAt": "2026-05-20T...",
        }

    Returns:
        Dict with _event_* audit fields + event value fields merged in.
    """
    return {
        "_event_uri": event_record.get("uri"),
        "_event_cid": event_record.get("cid"),
        "_event_indexed_at": event_record.get("indexedAt"),
        "_event_nsid": nsid,
        **event_record.get("value", {}),
    }


def default_thread_id_from_event(event_record: dict, nsid: str) -> str:
    """Default deterministic thread_id from MST event.

    Format: '{nsid}:{rkey}'

    Ensures idempotency — re-processing the same MST event resolves to the
    same checkpointer thread, so the graph naturally short-circuits.
    """
    rkey = event_record.get("rkey", "unknown")
    return f"{nsid}:{rkey}"


@dataclass
class HealthzStatus:
    """Healthz response shape for /healthz endpoint.

    Per ADR-2605202200 §5.
    """

    cell: str
    node: str
    uptime_seconds: float
    trigger: str
    listens_to: list[str]
    checkpointer_type: str  # "mst" / "file" / "none"
    checkpointer_ok: bool
    checkpointer_last_write_seconds_ago: float | None
    swarm_role: str  # "leader" / "follower" / "unknown"
    witness_min: int | None  # per cell config, None if not applicable
    cell_extra: dict[str, Any] = field(default_factory=dict)

    @property
    def status_code(self) -> int:
        """200 if all healthy, 503 if any critical dependency unhealthy."""
        if not self.checkpointer_ok:
            return 503
        return 200

    def to_dict(self) -> dict:
        return {
            "cell": self.cell,
            "node": self.node,
            "uptime_seconds": self.uptime_seconds,
            "trigger": self.trigger,
            "listens_to": self.listens_to,
            "checkpointer": {
                "type": self.checkpointer_type,
                "ok": self.checkpointer_ok,
                "last_write_seconds_ago": self.checkpointer_last_write_seconds_ago,
            },
            "swarm_role": self.swarm_role,
            "witness_min": self.witness_min,
            "cell_extra": self.cell_extra,
        }
