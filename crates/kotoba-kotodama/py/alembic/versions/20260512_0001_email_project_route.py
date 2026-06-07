"""email_project_route — routing rules + result edges for Outlook → projector.

Revision ID: 20260512_0001
Revises: 20260508_0002
Create Date: 2026-05-12

SCOPE
-----
Supports the pregel LangGraph server (outlook.triage.v1) email→projector
routing pipeline. Two new tables:

  vertex_email_project_route
    Routing rule definitions: match incoming email domain/address to a
    project slug + convo_id.  Managed by operators; no LLM writes here.

  edge_email_routes_to_project
    Result edges written by kotodama.primitives.email_route.task_email_route
    each time a clean triaged email is matched to a project.

  vertex_bpmn_process_def seed row for outlook_triage BPMN
  vertex_bpmn_lexicon_binding seed row for outlook.triage task type

RisingWave notes
-----------------
- DDL runs in autocommit mode (no transaction wrapping, ADR-2605080400).
- No ON CONFLICT — append-only pattern; routing results are immutable once
  inserted (hard-delete only, ADR root rules).
- RisingWave does not support FK constraints; referential integrity is
  enforced at the application layer.
"""

from __future__ import annotations

import pathlib
from typing import Sequence, Union

from alembic import op

revision: str = "20260512_0001"
down_revision: Union[str, Sequence[str], None] = "20260508_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# BPMN XML path (relative to repo root — read at migration time)
_BPMN_PATH = (
    pathlib.Path(__file__).resolve().parents[5]
    / "00-contracts/bpmn/com/etzhayyim/outlook/outlookTriage.bpmn"
)


def upgrade() -> None:
    # ── vertex_email_project_route ────────────────────────────────────────
    op.execute("""
CREATE TABLE IF NOT EXISTS vertex_email_project_route (
    vertex_id     VARCHAR NOT NULL,
    rule_id       VARCHAR NOT NULL,
    project_slug  VARCHAR NOT NULL,
    convo_id      VARCHAR,
    match_type    VARCHAR NOT NULL,
    match_value   VARCHAR NOT NULL,
    priority      INTEGER NOT NULL DEFAULT 0,
    active        BOOLEAN NOT NULL DEFAULT true,
    description   VARCHAR,
    actor_did     VARCHAR NOT NULL,
    created_at    VARCHAR NOT NULL,
    PRIMARY KEY (vertex_id)
)
""")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_project_route_project "
        "ON vertex_email_project_route (project_slug)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_project_route_active "
        "ON vertex_email_project_route (active, priority)"
    )

    # ── edge_email_routes_to_project ──────────────────────────────────────
    op.execute("""
CREATE TABLE IF NOT EXISTS edge_email_routes_to_project (
    vertex_id       VARCHAR NOT NULL,
    email_vertex_id VARCHAR NOT NULL,
    project_slug    VARCHAR NOT NULL,
    convo_id        VARCHAR,
    rule_id         VARCHAR,
    matched_at      VARCHAR NOT NULL,
    actor_did       VARCHAR NOT NULL,
    created_at      VARCHAR NOT NULL,
    PRIMARY KEY (vertex_id)
)
""")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_route_email_vid "
        "ON edge_email_routes_to_project (email_vertex_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_route_project "
        "ON edge_email_routes_to_project (project_slug, matched_at)"
    )

    # ── BPMN seed: outlook_triage process def ─────────────────────────────
    bpmn_xml = ""
    if _BPMN_PATH.exists():
        bpmn_xml = _BPMN_PATH.read_text(encoding="utf-8").replace("'", "''")

    bpmn_size = len(_BPMN_PATH.read_bytes()) if _BPMN_PATH.exists() else 0
    op.execute(f"""
INSERT INTO vertex_bpmn_process_def
    (vertex_id, owner_did, bpmn_process_id, version, xml, xml_byte_size,
     source_path, status, created_at, sensitivity_ord, org_id, user_id, actor_id)
SELECT
    'bpmn-pregel-outlook-triage-v1',
    'did:web:pregel.etzhayyim.com',
    'outlook_triage',
    1,
    '{bpmn_xml}',
    {bpmn_size},
    '00-contracts/bpmn/com/etzhayyim/outlook/outlookTriage.bpmn',
    'active',
    NOW()::VARCHAR,
    1,
    'did:web:pregel.etzhayyim.com',
    'did:web:pregel.etzhayyim.com',
    'sys.bpmn.pregel'
WHERE NOT EXISTS (
    SELECT 1 FROM vertex_bpmn_process_def
    WHERE vertex_id = 'bpmn-pregel-outlook-triage-v1'
)
""")

    # ── BPMN seed: lexicon binding for outlook.triage task type ───────────
    op.execute("""
INSERT INTO vertex_bpmn_lexicon_binding
    (vertex_id, owner_did, nsid, bpmn_process_id, status, created_at, sensitivity_ord,
     org_id, user_id, actor_id, actor_did)
SELECT
    'bpmn-bind-outlook-triage',
    'did:web:pregel.etzhayyim.com',
    'com.etzhayyim.apps.pregel.outlookTriage',
    'outlook_triage',
    'active',
    NOW()::VARCHAR,
    1,
    'did:web:pregel.etzhayyim.com',
    'did:web:pregel.etzhayyim.com',
    'sys.bpmn.pregel',
    'did:web:pregel.etzhayyim.com'
WHERE NOT EXISTS (
    SELECT 1 FROM vertex_bpmn_lexicon_binding
    WHERE vertex_id = 'bpmn-bind-outlook-triage'
)
""")

    op.execute("""
INSERT INTO vertex_bpmn_lexicon_binding
    (vertex_id, owner_did, nsid, bpmn_process_id, status, created_at, sensitivity_ord,
     org_id, user_id, actor_id, actor_did)
SELECT
    'bpmn-bind-outlook-email-route',
    'did:web:pregel.etzhayyim.com',
    'com.etzhayyim.apps.pregel.outlookEmailRoute',
    'outlook_triage',
    'active',
    NOW()::VARCHAR,
    1,
    'did:web:pregel.etzhayyim.com',
    'did:web:pregel.etzhayyim.com',
    'sys.bpmn.pregel',
    'did:web:pregel.etzhayyim.com'
WHERE NOT EXISTS (
    SELECT 1 FROM vertex_bpmn_lexicon_binding
    WHERE vertex_id = 'bpmn-bind-outlook-email-route'
)
""")


def downgrade() -> None:
    op.execute("DELETE FROM vertex_bpmn_lexicon_binding WHERE vertex_id IN ('bpmn-bind-outlook-email-route', 'bpmn-bind-outlook-triage')")
    op.execute("DELETE FROM vertex_bpmn_process_def WHERE vertex_id = 'bpmn-pregel-outlook-triage-v1'")
    op.execute("DROP TABLE IF EXISTS edge_email_routes_to_project")
    op.execute("DROP TABLE IF EXISTS vertex_email_project_route")
