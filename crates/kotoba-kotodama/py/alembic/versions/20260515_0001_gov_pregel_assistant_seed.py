"""gov LangGraph assistant seed — vertex_langgraph_assistant + deployment rows.

Registers the gov fractal Pregel orchestrator graph as an active LangGraph assistant
in the SSoT tables, per ADR-2605082000.

Assistant ID: gov-fractal-pregel
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260515_0001_gov_pregel_assistant_seed'
down_revision: Union[str, None] = '20260514_0005_mv_pregel_step_pending'  # Assuming this is the latest, adjust if needed
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Register the assistant SSoT (kind = 'topology')
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
            'at://sys.worker.gov.pregel/assistant/gov-fractal-pregel',
            'gov-fractal-pregel',
            1,
            'topology',
            '{"nodes": ["fetch_jurisdictions", "fan_out_countries", "fetch_agencies", "fan_out_agencies", "ingest_signals", "extract_entities", "bfs_expansion", "analyze_policy", "commit_state"], "entry": "fetch_jurisdictions"}',
            'Fractal LangGraph + Pregel Map-Reduce/BFS orchestrator for global government agency mapping and policy tracking.',
            'rw_vertex',
            'did:web:gov.etzhayyim.com',
            NULL,
            NOW()::VARCHAR,
            NOW()::VARCHAR
        ) ON CONFLICT DO NOTHING
    """)

    # 2. Register the deployment pin
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
            'at://sys.worker.gov.pregel/deployment/gov-fractal-pregel',
            'com.etzhayyim.apps.gov.syncWetUpdates',
            'gov-fractal-pregel',
            1,
            'active',
            3,
            NOW()::VARCHAR,
            NOW()::VARCHAR
        ) ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM vertex_langgraph_deployment WHERE assistant_id = 'gov-fractal-pregel'
    """)
    op.execute("""
        DELETE FROM vertex_langgraph_assistant 
        WHERE assistant_id = 'gov-fractal-pregel' AND version = 1
    """)
