"""Fund intel ingest worker package.

Source-specific parsers live here; Zeebe registration is in
`kotodama.zeebe_worker_main`.
"""

from .ids import FUND_DID, edge_id, fund_vertex_id, manager_vertex_id, slug

__all__ = [
    "FUND_DID",
    "edge_id",
    "fund_vertex_id",
    "manager_vertex_id",
    "slug",
]
