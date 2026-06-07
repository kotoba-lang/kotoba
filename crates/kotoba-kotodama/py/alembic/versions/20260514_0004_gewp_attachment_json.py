"""gewp_attachment_json — add attachment_json column to vertex_mailer_inbound_email.

Revision ID: 20260514_0004
Revises: 20260514_0003
Create Date: 2026-05-14

SCOPE
-----
Adds attachment_json VARCHAR to vertex_mailer_inbound_email so the email-relay
CF Worker can store the raw GEWP Layer-1 attachment JSON string extracted from
incoming MIME messages.  The graph worker will project this field from PDS
records (com.etzhayyim.apps.mailer.inboundEmail.gewpPayloadJson) once updated.

RisingWave notes
-----------------
- DDL in autocommit mode (ADR-2605080400).
- NULL = email has no GEWP attachment; populated by email-relay Worker Phase 2.
"""

from __future__ import annotations

from alembic import op

revision = "20260514_0004"
down_revision = "20260514_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE vertex_mailer_inbound_email
          ADD COLUMN IF NOT EXISTS attachment_json VARCHAR
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE vertex_mailer_inbound_email
          DROP COLUMN IF EXISTS attachment_json
    """)
