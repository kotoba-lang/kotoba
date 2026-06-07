"""gewp_mailer_columns — add GEWP protocol columns to mailer tables.

Revision ID: 20260514_0003
Revises: 20260514_0002
Create Date: 2026-05-14

SCOPE
-----
Adds GEWP (etzhayyim Email Wire Protocol) tracking columns to:

  vertex_mailer_inbound_email
    gewp_thread_id    VARCHAR  — Pregel partition key from incoming GEWP message
    gewp_step         BIGINT   — Pregel superstep counter
    gewp_type         VARCHAR  — pregel.message | pregel.barrier | human.intent
    gewp_performative VARCHAR  — FIPA-ACL performative from incoming message

  vertex_mailer_outbound_email
    gewp_thread_id    VARCHAR  — thread.id of the outbound GEWP message
    gewp_step         BIGINT   — thread.step of the outbound GEWP message

RisingWave notes
-----------------
- DDL in autocommit mode (ADR-2605080400).
- NULL = non-GEWP email (backward compatible).
- No ON CONFLICT — existing rows keep NULL, new rows fill on insert/update.
"""

from __future__ import annotations

from alembic import op

revision = "20260514_0003"
down_revision = "20260514_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE vertex_mailer_inbound_email
          ADD COLUMN IF NOT EXISTS gewp_thread_id    VARCHAR,
          ADD COLUMN IF NOT EXISTS gewp_step         BIGINT,
          ADD COLUMN IF NOT EXISTS gewp_type         VARCHAR,
          ADD COLUMN IF NOT EXISTS gewp_performative VARCHAR
    """)
    op.execute("""
        ALTER TABLE vertex_mailer_outbound_email
          ADD COLUMN IF NOT EXISTS gewp_thread_id  VARCHAR,
          ADD COLUMN IF NOT EXISTS gewp_step       BIGINT
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE vertex_mailer_inbound_email
          DROP COLUMN IF EXISTS gewp_thread_id,
          DROP COLUMN IF EXISTS gewp_step,
          DROP COLUMN IF EXISTS gewp_type,
          DROP COLUMN IF EXISTS gewp_performative
    """)
    op.execute("""
        ALTER TABLE vertex_mailer_outbound_email
          DROP COLUMN IF EXISTS gewp_thread_id,
          DROP COLUMN IF EXISTS gewp_step
    """)
