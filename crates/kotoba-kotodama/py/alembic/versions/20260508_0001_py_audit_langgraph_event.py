"""py_audit_langgraph_event — LangGraph run lifecycle audit table.

Revision ID: 20260508_0001
Revises: (initial)
Create Date: 2026-05-08

SCOPE CONSTRAINT (ADR-2605080400)
----------------------------------
Python-owned table (py_audit_* prefix). NOT vertex_* / edge_* / mv_*.
Graph-schema tables belong in 30-graph/graph-schema/migrations/.

Purpose
-------
Append-only audit log for LangGraph Server run lifecycle events
(status transitions: pending → running → success|error).
Enables soak monitoring and latency analysis without touching
the primary vertex_langgraph_run table owned by Kysely migrations.

RisingWave notes
-----------------
- DDL runs in autocommit mode (no transaction wrapping).
- BIGINT for timestamps (epoch ms), consistent with vertex_langgraph_run.
- No ON CONFLICT — append-only by design.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS py_audit_langgraph_event (
            event_id        VARCHAR     NOT NULL,
            run_id          VARCHAR     NOT NULL,
            assistant_id    VARCHAR     NOT NULL,
            thread_id       VARCHAR     NOT NULL,
            actor_did       VARCHAR,
            from_status     VARCHAR,
            to_status       VARCHAR     NOT NULL,
            error_message   VARCHAR,
            latency_ms      BIGINT,
            ts_ms           BIGINT      NOT NULL,
            emitted_by      VARCHAR     NOT NULL DEFAULT 'langgraph-server'
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_py_audit_lg_run
            ON py_audit_langgraph_event (run_id, ts_ms ASC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_py_audit_lg_assistant
            ON py_audit_langgraph_event (assistant_id, ts_ms DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_py_audit_lg_assistant")
    op.execute("DROP INDEX IF EXISTS idx_py_audit_lg_run")
    op.execute("DROP TABLE IF EXISTS py_audit_langgraph_event")
