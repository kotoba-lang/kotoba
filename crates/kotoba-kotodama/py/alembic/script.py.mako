"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

SCOPE CONSTRAINT (ADR-2605080400)
----------------------------------
This migration is for Python-owned tables ONLY.
DO NOT add vertex_* / edge_* / mv_* tables here.
Graph-schema tables belong in 30-graph/graph-schema/migrations/.

RisingWave notes
-----------------
- DDL runs in autocommit mode (no transaction wrapping).
- Use ``op.execute("CREATE TABLE ...")`` for RW-specific DDL.
- LIMIT $N in parameterised queries is rejected by RW prepared statements;
  use f-string int literals (see [[conventions]] rw-psycopg3-no-param-limit).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
