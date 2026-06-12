"""kenkyusha — discipline + LangGraph assistant seed (INSERT-only).

Revision ID: 20260514_0001
Revises: 20260512_0002
Create Date: 2026-05-14

SCOPE
-----
Phase 1 seed rows for the kenkyusha LangGraph server. The DDL for
``vertex_kenkyusha_*`` and ``edge_kenkyusha_*`` lives in the Kysely scope
(``30-graph/graph-schema/migrations/20260514150000_vertex_kenkyusha_pipeline.ts``)
per the Alembic env.py guard — Alembic env rejects vertex_* / edge_* DDL.

This migration is INSERT-only so it bypasses the DDL regex guard:

  vertex_kenkyusha_discipline    — 5 ISCED-F seeds from actor-manifest.jsonld
  vertex_langgraph_assistant     — registers kenkyusha-research-loop graph

Both INSERTs are idempotent via WHERE NOT EXISTS.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260514_0001"
down_revision: Union[str, Sequence[str], None] = "20260512_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ACTOR = "did:web:kenkyusha.etzhayyim.com"


def upgrade() -> None:
    # ── Seed disciplines (5 from actor-manifest.jsonld) ───────────────────
    _seed = [
        ("0511", "05", "051", "Biology", "生物学"),
        ("0531", "05", "053", "Chemistry", "化学"),
        ("0533", "05", "053", "Physics", "物理学"),
        ("0541", "05", "054", "Mathematics", "数学"),
        ("0613", "06", "061", "Software and Applications Development",
         "ソフトウェア・アプリケーション開発"),
    ]
    for isced4, broad, narrow, name_en, name_ja in _seed:
        did = f"{_ACTOR}:discipline:{isced4}"
        vid = f"at://{did}/com.etzhayyim.apps.kenkyusha.discipline/{isced4}"
        op.execute(f"""
INSERT INTO vertex_kenkyusha_discipline
    (vertex_id, rkey, repo, did, isced4, isced_broad, isced_narrow,
     name_en, name_ja, paradigm, maturity, interdisciplinarity,
     publication_count, citation_count, frontier_count,
     actor_did, org_did, created_at, sensitivity_ord)
SELECT
    '{vid}', '{isced4}', '{_ACTOR}', '{did}', '{isced4}', '{broad}', '{narrow}',
    '{name_en}', '{name_ja}', 'mixed', 'established', 'multi',
    0, 0, 0,
    '{_ACTOR}', '{_ACTOR}', NOW()::VARCHAR, 0
WHERE NOT EXISTS (
    SELECT 1 FROM vertex_kenkyusha_discipline WHERE vertex_id = '{vid}'
)
""")

    # ── LangGraph assistant registration ──────────────────────────────────
    op.execute(f"""
INSERT INTO vertex_langgraph_assistant
    (vertex_id, assistant_id, kind, factory_path, version, status,
     actor_did, org_did, created_at, sensitivity_ord)
SELECT
    'lg-assistant-kenkyusha-research-loop',
    'kenkyusha-research-loop',
    'py_factory',
    'kotodama.kenkyusha.graph',
    1,
    'active',
    '{_ACTOR}', '{_ACTOR}', NOW()::VARCHAR, 0
WHERE NOT EXISTS (
    SELECT 1 FROM vertex_langgraph_assistant
    WHERE assistant_id = 'kenkyusha-research-loop'
)
""")


def downgrade() -> None:
    op.execute(
        "DELETE FROM vertex_langgraph_assistant "
        "WHERE assistant_id = 'kenkyusha-research-loop'"
    )
    op.execute("DELETE FROM vertex_kenkyusha_discipline")
