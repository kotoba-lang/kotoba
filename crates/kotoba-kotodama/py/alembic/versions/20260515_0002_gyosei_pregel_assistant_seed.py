"""gyosei-procedure LangGraph assistant seed

Registers the gyosei procedure pregel graph as an active LangGraph assistant.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20260515_0002_gyosei_pregel_assistant_seed'
down_revision: Union[str, None] = '20260515_0001_gov_pregel_assistant_seed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
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
            'at://sys.worker.gyosei.pregel/assistant/gyosei-procedure-pregel',
            'gyosei-procedure-pregel',
            1,
            'topology',
            '{"nodes": ["fetch_pending_cases", "fan_out_procedures", "start_procedure", "gather_evidence", "generate_draft", "review_gate", "submit_draft", "commit_case_state"], "entry": "fetch_pending_cases"}',
            'Pregel Map-Reduce architecture for mass dispatching administrative procedures.',
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
            'at://sys.worker.gyosei.pregel/deployment/gyosei-procedure-pregel',
            'com.etzhayyim.apps.gyosei.startProcedure',
            'gyosei-procedure-pregel',
            1,
            'active',
            3,
            NOW()::VARCHAR,
            NOW()::VARCHAR
        ) ON CONFLICT DO NOTHING
    """)

def downgrade() -> None:
    op.execute("DELETE FROM vertex_langgraph_deployment WHERE assistant_id = 'gyosei-procedure-pregel'")
    op.execute("DELETE FROM vertex_langgraph_assistant WHERE assistant_id = 'gyosei-procedure-pregel' AND version = 1")
