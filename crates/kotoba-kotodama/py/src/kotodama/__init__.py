"""
kotodama — Python runtime SDK for mitama reactive agents (ADR-0049).

Counterpart to `@etzhayyim/kotoba-kotodama-host-sdk` (TypeScript, for CF Worker Mode B).
Runs inside RisingWave External Python UDF servers on the mitama-udf pool
(Vultr VKE per ADR-0048).

Public surface:

    from kotodama import udf, serve
    from kotodama.db_sync import fetch_one, fetch_all, execute  # sync DB

    @udf("com.etzhayyim.apps.yabai.classify",
         input_types=["VARCHAR"], result_type="VARCHAR", io_threads=100)
    def classify(body_json: str) -> str:
        return compute_score(body_json)

    if __name__ == "__main__":
        serve()   # arrow-flight :8815 + prometheus :9090

WIT bindgen is intentionally NOT a dependency — AT Lexicon JSON at
`00-contracts/lexicons/**/*.json` is the surviving contract layer.

## Module topology

| Module | Role |
|---|---|
| `kotodama.registry` | @udf decorator + NSID handler table |
| `kotodama.server`   | arrow-flight UdfServer bootstrap |
| `kotodama.db_sync`  | psycopg3 sync pool (arrow-udf handlers) |
| `kotodama.rw_schema` | live information_schema reflection cache |
| `kotodama.rw_sql`   | optional SQLAlchemy Core helpers |
| `kotodama.shinka`   | LangGraph agent loop (shinka/koji/kyumei) |
| `kotodama.handlers.*` | per-actor handlers, imported at boot |

## Async DB access

arrow-udf does not currently await `async def` handlers. Handlers that
need DB must use `kotodama.db_sync`. Event-driven (non-UDF) consumers —
which would use asyncpg — do not exist yet; their SDK lands with Phase C.2.
"""

import os
from kotodama.registry import udf
from kotodama.server import serve

def get_lg_backend() -> str:
    """Return the selected LangGraph backend ('kotoba' or 'rw')."""
    return os.environ.get("KOTODAMA_LG_BACKEND", "kotoba")

try:
    from kotodama.langgraph_checkpoint_rw import RisingWaveCheckpointSaver
    from kotodama.langgraph_store_rw import RisingWaveStore
    from kotodama.langgraph_checkpoint_kotoba import KotobaCheckpointSaver
    from kotodama.langgraph_store_kotoba import KotobaStore
    _LG_RW_AVAILABLE = True
except ImportError:  # pragma: no cover — langgraph is a [lg] optional dep
    _LG_RW_AVAILABLE = False
    RisingWaveCheckpointSaver = None  # type: ignore[assignment]
    RisingWaveStore = None  # type: ignore[assignment]
    KotobaCheckpointSaver = None  # type: ignore[assignment]
    KotobaStore = None  # type: ignore[assignment]

__all__ = [
    "udf", "serve", "RisingWaveCheckpointSaver", "RisingWaveStore",
    "KotobaCheckpointSaver", "KotobaStore", "get_lg_backend"
]
__version__ = "0.3.35"
