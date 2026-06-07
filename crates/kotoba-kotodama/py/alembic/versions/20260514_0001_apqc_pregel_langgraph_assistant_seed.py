"""APQC Pregel LangGraph assistant seed — vertex_langgraph_assistant + deployment rows.

Revision ID: 20260514_0001
Revises: 20260512_0002
Create Date: 2026-05-14

SCOPE
-----
Registers the APQC Pregel orchestrator graph as an active LangGraph assistant
so langgraph_loader.load_active_graphs() picks it up at server startup.

  assistant_id : apqc-pregel-orchestrator
  kind         : py_factory
  factory_path : kotodama.langgraph_graphs.apqc_pregel
                 (resolved as build_graph() per langgraph_loader convention)
  version      : 1

Graph topology (two BSP super-steps):
  dispatch_l1s → [Send×13 L1 codes] → l1_coord (BSP)
               → [Send×N tasks]     → l2_task | l2_materialize (BSP)
               → finalize → END

All results accumulate via Annotated[list, operator.add] reducers into
ApqcOrchestratorState.l1_results.

Archive reference:
  _archive/2026-05-14-kyber-projector-wasm-kyb3proj/  (retired TS WASM)
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260514_0001"
down_revision: Union[str, Sequence[str], None] = "20260512_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
INSERT INTO vertex_langgraph_assistant
    (assistant_id, version, kind, factory_path, spec, checkpointer_mode,
     description, created_at, updated_at)
VALUES
    (
        'apqc-pregel-orchestrator',
        1,
        'py_factory',
        'kotodama.langgraph_graphs.apqc_pregel',
        NULL,
        'none',
        'APQC PCF 13 L1 BSP + L2 Send fan-out: materialize | run_task | coverage modes',
        NOW()::VARCHAR,
        NOW()::VARCHAR
    )
ON CONFLICT (assistant_id, version) DO NOTHING
""")

    op.execute("""
INSERT INTO vertex_langgraph_deployment
    (assistant_id, version, status, routing_target, created_at, updated_at)
VALUES
    (
        'apqc-pregel-orchestrator',
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
        "DELETE FROM vertex_langgraph_deployment WHERE assistant_id = 'apqc-pregel-orchestrator'"
    )
    op.execute(
        "DELETE FROM vertex_langgraph_assistant "
        "WHERE assistant_id = 'apqc-pregel-orchestrator' AND version = 1"
    )
