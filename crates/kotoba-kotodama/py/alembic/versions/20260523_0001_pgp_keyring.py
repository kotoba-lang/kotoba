"""pgp_keyring — add vertex_mailer_pgp_key table and content_protection columns.

Revision ID: 20260523_0001
Revises: 20260515_0003
Create Date: 2026-05-23

SCOPE
-----
Adds PGP E2EE support to the mailer subsystem:

1. vertex_mailer_pgp_key
   Stores OpenPGP public keys for outbound recipients.
   When a recipient's key is registered, send_email / send_gewp_message will
   encrypt the body, subject, and GEWP Layer-1 attachment before sending.
   Private keys are NEVER stored server-side.

2. content_protection column on vertex_mailer_outbound_email
   Tracks whether a sent email is "plaintext" or "pgp".

RisingWave notes
-----------------
- DDL in autocommit mode (ADR-2605080400).
- No FK constraints — RisingWave does not enforce them.
"""

from __future__ import annotations

from alembic import op

revision = "20260523_0001"
down_revision = "20260515_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS vertex_mailer_pgp_key (
            email           VARCHAR NOT NULL,
            fingerprint     VARCHAR NOT NULL,
            public_key_armored TEXT NOT NULL,
            revoked         BOOLEAN NOT NULL DEFAULT FALSE,
            created_at_ms   BIGINT NOT NULL,
            PRIMARY KEY (email, fingerprint)
        )
    """)
    op.execute("""
        ALTER TABLE vertex_mailer_outbound_email
          ADD COLUMN IF NOT EXISTS content_protection VARCHAR DEFAULT 'plaintext'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE vertex_mailer_outbound_email
          DROP COLUMN IF EXISTS content_protection
    """)
    op.execute("DROP TABLE IF EXISTS vertex_mailer_pgp_key")
