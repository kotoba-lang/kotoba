"""pregel LangGraph assistant seed — vertex_langgraph_assistant + deployment row.

Revision ID: 20260512_0002
Revises: 20260512_0001
Create Date: 2026-05-12

SCOPE
-----
Registers the pregel email triage graph as an active LangGraph assistant
so langgraph_loader.load_active_graphs() picks it up at server startup.

  assistant_id : pregel-email-triage
  kind         : py_factory
  factory_path : kotodama.pregel.graph
                 (resolved as build_graph() per langgraph_loader convention)
  version      : 1

The graph pipeline is:
  parse_email → classify_intent → detect_deps → write_vertex → END
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260512_0002"
down_revision: Union[str, Sequence[str], None] = "20260512_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # vertex_langgraph_assistant (assistant schema / kind)
    op.execute("""
INSERT INTO vertex_langgraph_assistant
    (assistant_id, version, kind, factory_path, spec, checkpointer_mode,
     description, created_at, updated_at)
VALUES
    (
        'pregel-email-triage',
        1,
        'py_factory',
        'kotodama.pregel.graph',
        NULL,
        'none',
        'Email intent analysis — parse_email→classify_intent→detect_deps→write_vertex',
        NOW()::VARCHAR,
        NOW()::VARCHAR
    )
ON CONFLICT (assistant_id, version) DO NOTHING
""")

    # vertex_langgraph_deployment (active deployment pointer)
    op.execute("""
INSERT INTO vertex_langgraph_deployment
    (assistant_id, version, status, routing_target, created_at, updated_at)
VALUES
    (
        'pregel-email-triage',
        1,
        'active',
        'langgraph',
        NOW()::VARCHAR,
        NOW()::VARCHAR
    )
ON CONFLICT (assistant_id) DO UPDATE
    SET version    = EXCLUDED.version,
        status     = EXCLUDED.status,
        updated_at = EXCLUDED.updated_at
""")


def downgrade() -> None:
    op.execute(
        "DELETE FROM vertex_langgraph_deployment WHERE assistant_id = 'pregel-email-triage'"
    )
    op.execute(
        "DELETE FROM vertex_langgraph_assistant "
        "WHERE assistant_id = 'pregel-email-triage' AND version = 1"
    )
