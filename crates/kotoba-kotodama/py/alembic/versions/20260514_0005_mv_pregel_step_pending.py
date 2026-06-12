"""mv_pregel_step_pending — ext:pregel barrier tracking MV.

Revision ID: 20260514_0005
Revises: 20260514_0004
Create Date: 2026-05-14

SCOPE
-----
Creates mv_pregel_step_pending, a streaming MV that aggregates
vertex_mailer_inbound_email rows where gewp_type = 'pregel.barrier'
by (gewp_thread_id, gewp_step).  The pregel triage pipeline can
query this MV to check whether all expected barrier messages for a
given superstep have arrived (arrived_count == expected_count from
the GEWP payload) before advancing to the next step.

This completes ADR-2605141900 Phase 3 (ext:pregel barrier semantics).

RisingWave notes
-----------------
- DDL in autocommit mode (ADR-2605080400).
- The MV is append-only; RisingWave computes the GROUP BY
  incrementally on each new inbound row.
"""

from __future__ import annotations

from alembic import op

revision = "20260514_0005"
down_revision = "20260514_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_pregel_step_pending AS
        SELECT
            gewp_thread_id,
            gewp_step,
            COUNT(*)                                        AS arrived_count,
            MIN(received_at_ms)                             AS first_arrived_ms,
            MAX(received_at_ms)                             AS last_arrived_ms,
            ARRAY_AGG(vertex_id ORDER BY received_at_ms)    AS vertex_ids,
            ARRAY_AGG(DISTINCT sender_address)              AS sender_addresses
        FROM vertex_mailer_inbound_email
        WHERE gewp_thread_id IS NOT NULL
          AND gewp_step      IS NOT NULL
          AND gewp_type      = 'pregel.barrier'
        GROUP BY gewp_thread_id, gewp_step
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_pregel_step_pending")
