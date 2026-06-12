"""vertex_lora_adapter — P10v2 typed column upgrade + display_name_yomi.

Revision ID: 20260508_0002
Revises: 20260508_0001
Create Date: 2026-05-08

SCOPE (ADR-2605080400 Addendum 2026-05-08)
-------------------------------------------
vertex_lora_* tables are allowed in Alembic because the LoRA adapter
lifecycle is exclusively Python-driven (kotodama primitives → B2 upload).

Changes
-------
- Add P10v2 typed weight storage columns (weight_b2_uri, weight_byte_size,
  weight_sha256, base_model, adapter_rank, adapter_alpha, adapter_format)
- Add display_name_yomi for per-person name reading (ふりがな)
- Add supporting indexes for B2 URI and base_model lookups
- value_json kept nullable (grace period; drop in a future migration after
  all callers write typed columns)

RisingWave notes
-----------------
- DDL runs in autocommit mode (no transaction wrapping, ADR-2605080400).
- ALTER TABLE ADD COLUMN is safe on RisingWave — no table rewrite.
- No ON CONFLICT — append-only inserts from kotodama worker.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0002"
down_revision: Union[str, Sequence[str], None] = "20260508_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE vertex_lora_adapter ADD COLUMN weight_b2_uri     VARCHAR")
    op.execute("ALTER TABLE vertex_lora_adapter ADD COLUMN weight_byte_size  BIGINT")
    op.execute("ALTER TABLE vertex_lora_adapter ADD COLUMN weight_sha256     VARCHAR")
    op.execute("ALTER TABLE vertex_lora_adapter ADD COLUMN base_model        VARCHAR")
    op.execute("ALTER TABLE vertex_lora_adapter ADD COLUMN adapter_rank      INTEGER")
    op.execute("ALTER TABLE vertex_lora_adapter ADD COLUMN adapter_alpha     DOUBLE PRECISION")
    op.execute("ALTER TABLE vertex_lora_adapter ADD COLUMN adapter_format    VARCHAR")
    op.execute("ALTER TABLE vertex_lora_adapter ADD COLUMN display_name_yomi VARCHAR")

    op.execute("CREATE INDEX IF NOT EXISTS idx_lora_adapter_owner_did  ON vertex_lora_adapter (owner_did)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lora_adapter_base_model ON vertex_lora_adapter (base_model)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lora_adapter_weight_b2  ON vertex_lora_adapter (weight_b2_uri)")


def downgrade() -> None:
    op.execute("ALTER TABLE vertex_lora_adapter DROP COLUMN IF EXISTS display_name_yomi")
    op.execute("ALTER TABLE vertex_lora_adapter DROP COLUMN IF EXISTS adapter_format")
    op.execute("ALTER TABLE vertex_lora_adapter DROP COLUMN IF EXISTS adapter_alpha")
    op.execute("ALTER TABLE vertex_lora_adapter DROP COLUMN IF EXISTS adapter_rank")
    op.execute("ALTER TABLE vertex_lora_adapter DROP COLUMN IF EXISTS base_model")
    op.execute("ALTER TABLE vertex_lora_adapter DROP COLUMN IF EXISTS weight_sha256")
    op.execute("ALTER TABLE vertex_lora_adapter DROP COLUMN IF EXISTS weight_byte_size")
    op.execute("ALTER TABLE vertex_lora_adapter DROP COLUMN IF EXISTS weight_b2_uri")
