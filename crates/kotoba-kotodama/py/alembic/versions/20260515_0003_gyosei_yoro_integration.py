"""gyosei and yoro integration assistant seed

Registers the intake and internal processing graphs.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20260515_0003_gyosei_yoro_integration'
down_revision: Union[str, None] = '20260515_0002_gyosei_pregel_assistant_seed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Intake Agent (Public -> Gyosei)
    op.execute("""
        INSERT INTO vertex_langgraph_assistant (
            vertex_id,
            assistant_id,
            version,
            kind,
            spec,
            description,
            checkpointer_mode,
            authored_by,
            superseded_by,
            created_at,
            updated_at
        ) VALUES (
            'at://sys.worker.gyosei.pregel/assistant/gyosei-intake-agent',
            'gyosei-intake-agent',
            1,
            'topology',
            '{"nodes": ["listen_yoro_messages", "classify_intent", "start_procedure", "gather_missing_info", "generate_draft", "submit_draft"], "entry": "listen_yoro_messages"}',
            'Conversational intake agent for gyosei procedures via yoro.etzhayyim.com.',
            'rw_vertex',
            'did:web:gyosei.etzhayyim.com',
            NULL,
            NOW()::VARCHAR,
            NOW()::VARCHAR
        ) ON CONFLICT DO NOTHING
    """)

    op.execute("""
        INSERT INTO vertex_langgraph_deployment (
            vertex_id,
            nsid,
            assistant_id,
            version,
            status,
            replicas,
            created_at,
            updated_at
        ) VALUES (
            'at://sys.worker.gyosei.pregel/deployment/gyosei-intake-agent',
            'com.etzhayyim.apps.gyosei.intake',
            'gyosei-intake-agent',
            1,
            'active',
            3,
            NOW()::VARCHAR,
            NOW()::VARCHAR
        ) ON CONFLICT DO NOTHING
    """)

    # 2. Internal Processing Agent (Gyosei Back-office)
    op.execute("""
        INSERT INTO vertex_langgraph_assistant (
            vertex_id,
            assistant_id,
            version,
            kind,
            spec,
            description,
            checkpointer_mode,
            authored_by,
            superseded_by,
            created_at,
            updated_at
        ) VALUES (
            'at://sys.worker.gyosei.pregel/assistant/gyosei-internal-processing',
            'gyosei-internal-processing',
            1,
            'topology',
            '{"nodes": ["receive_submitted_draft", "validate_schema", "decision_gate", "update_case_status", "notify_user_yoro"], "entry": "receive_submitted_draft"}',
            'Internal back-office processing for gyosei cases.',
            'rw_vertex',
            'did:web:gyosei.etzhayyim.com',
            NULL,
            NOW()::VARCHAR,
            NOW()::VARCHAR
        ) ON CONFLICT DO NOTHING
    """)

    op.execute("""
        INSERT INTO vertex_langgraph_deployment (
            vertex_id,
            nsid,
            assistant_id,
            version,
            status,
            replicas,
            created_at,
            updated_at
        ) VALUES (
            'at://sys.worker.gyosei.pregel/deployment/gyosei-internal-processing',
            'com.etzhayyim.apps.gyosei.processCase',
            'gyosei-internal-processing',
            1,
            'active',
            3,
            NOW()::VARCHAR,
            NOW()::VARCHAR
        ) ON CONFLICT DO NOTHING
    """)

def downgrade() -> None:
    op.execute("DELETE FROM vertex_langgraph_deployment WHERE assistant_id IN ('gyosei-intake-agent', 'gyosei-internal-processing')")
    op.execute("DELETE FROM vertex_langgraph_assistant WHERE assistant_id IN ('gyosei-intake-agent', 'gyosei-internal-processing') AND version = 1")
