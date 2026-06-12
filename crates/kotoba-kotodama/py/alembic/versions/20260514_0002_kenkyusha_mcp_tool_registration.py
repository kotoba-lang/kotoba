"""kenkyusha MCP tool registration — vertex_capability rows for tools/list discovery.

Revision ID: 20260514_0002
Revises: 20260514_0001
Create Date: 2026-05-14

SCOPE
-----
Phase 2A — expose kenkyusha's research lifecycle endpoints as MCP tools at
``atproto.etzhayyim.com/xrpc/com.etzhayyim.mcp.message`` (compat: ``atproto.etzhayyim.com/mcp``).

The MCP adapter (``50-infra/cloudflare/workers/atproto/src/mcp-adapter.ts``)
discovers tools by querying ``vertex_capability`` rows where
``collection = 'com.etzhayyim.tool.tool'`` and ``status = 'active'``. Each row also
declares the ``capability_worker`` (= kenkyusha nanoid ``kk8r3n5v``); the
generic dispatcher in ``handleToolsCall`` then proxies to
``https://kk8r3n5v.etzhayyim.com/xrpc/com.etzhayyim.apps.kenkyusha.<method>``, which is
handled by the kenkyusha appview Worker — it in turn proxies to the
lg-kenkyusha pod at ``https://kenkyusha.etzhayyim.com`` (ADR-2605111200).

Three tools are registered:

  kenkyusha.publishFrontier — Science OS / EACN3 "Publish A Problem" entry
  kenkyusha.getFrontier     — frontier detail (top hypothesis + evidence)
  kenkyusha.listFrontiers   — list active frontiers (Use-cases view)

Discovery is also surfaced via ``/_app/meta`` (already includes these NSIDs
through the kenkyusha appview Worker's ``NSIDS`` set, so no extra wiring
needed on that path).

RisingWave notes
-----------------
- DDL runs in autocommit mode (ADR-2605080400).
- First-write-wins via WHERE NOT EXISTS (no ON CONFLICT, ADR record-log).
- Hard delete only.
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op

revision: str = "20260514_0002"
down_revision: Union[str, Sequence[str], None] = "20260514_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# capability_worker = subdomain (NOT nanoid) so that mcp-adapter routes
# directly to https://kenkyusha.etzhayyim.com/xrpc/... (= lg-kenkyusha pod
# ingress) rather than the appview Worker. This matches the ADR-2605111200
# rule that the pod is the single writer for vertex_kenkyusha_*. Without
# the indirection, MCP traffic is 1 hop (CF edge → pod) instead of 2 hops
# (CF edge → appview Worker → pod).
_ACTOR = "did:web:kenkyusha.etzhayyim.com"
_NANOID = "kenkyusha"


_PUBLISH_INPUT = json.dumps({
    "type": "object",
    "required": ["title"],
    "properties": {
        "title": {
            "type": "string",
            "minLength": 4,
            "maxLength": 240,
            "description": "One-sentence statement of the research frontier.",
        },
        "primaryDiscipline": {
            "type": "string",
            "description": "ISCED-F 2013 four-digit detailed field code (default '0613').",
            "default": "0613",
        },
        "maxHypotheses": {
            "type": "integer",
            "minimum": 2,
            "maximum": 8,
            "default": 4,
        },
        "description": {"type": "string", "maxLength": 1024},
    },
}).replace("'", "''")

_GET_INPUT = json.dumps({
    "type": "object",
    "required": ["frontier_id"],
    "properties": {
        "frontier_id": {"type": "string", "description": "Frontier hash id."},
    },
}).replace("'", "''")

_LIST_INPUT = json.dumps({
    "type": "object",
    "properties": {
        "limit":  {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
        "status": {
            "type": "string",
            "enum": ["frontier_active", "frontier_resolved", "frontier_dormant", "detected"],
            "description": "Optional status filter.",
        },
    },
}).replace("'", "''")


_TOOLS = [
    (
        "kenkyusha.publishFrontier",
        "Publish a research problem (Science OS Step 1). Runs the kenkyusha co-scientist Pregel loop (Generation / Reflection / Ranking / Evolution / Proximity / Meta-review) over the frontier and returns the winning hypothesis + consensus level.",
        _PUBLISH_INPUT,
    ),
    (
        "kenkyusha.getFrontier",
        "Return frontier detail: top-elo hypothesis, all evidence rows, consensus + evidence levels. Use after publishFrontier returns frontier_id.",
        _GET_INPUT,
    ),
    (
        "kenkyusha.listFrontiers",
        "List recent research frontiers ordered by last_analyzed_at desc. Use to browse the Science OS / EACN3 use-cases view.",
        _LIST_INPUT,
    ),
]


def upgrade() -> None:
    for name, description, schema_json in _TOOLS:
        vid = f"capability-tool-{name.replace('.', '-')}"
        op.execute(f"""
INSERT INTO vertex_capability
    (vertex_id, did, repo, rkey, collection,
     name, description, input_schema_json,
     capability_worker, status,
     actor_did, org_did, created_at, sensitivity_ord)
SELECT
    '{vid}',
    '{_ACTOR}', '{_ACTOR}', '{name.replace('.', '_')}',
    'com.etzhayyim.tool.tool',
    '{name}',
    '{description.replace("'", "''")}',
    '{schema_json}',
    '{_NANOID}',
    'active',
    '{_ACTOR}', '{_ACTOR}', NOW()::VARCHAR, 0
WHERE NOT EXISTS (
    SELECT 1 FROM vertex_capability
    WHERE name = '{name}' AND collection = 'com.etzhayyim.tool.tool'
)
""")


def downgrade() -> None:
    for name, _, _ in _TOOLS:
        op.execute(
            f"DELETE FROM vertex_capability "
            f"WHERE name = '{name}' AND collection = 'com.etzhayyim.tool.tool'"
        )
