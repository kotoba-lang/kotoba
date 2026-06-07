"""kyber-projector NSID → apqc-pregel-orchestrator binding seed.

Revision ID: 20260514_0002
Revises: 20260514_0001
Create Date: 2026-05-14

SCOPE
-----
Seeds vertex_bpmn_lexicon_binding rows for all 12 com.etzhayyim.kyber.projector.*
NSIDs that were previously handled by the retired TypeScript WASM projector
(archived: _archive/2026-05-14-kyber-projector-wasm-kyb3proj/).

All rows route to assistant_id='apqc-pregel-orchestrator' via
routing_target='langgraph'.  The dispatcher's _dispatch_langgraph() path
picks them up; the graph infers execution mode from the _nsid suffix via
_NSID_MODE_MAP in apqc_pregel.py.

NSID → mode mapping (handled in apqc_pregel._dispatch_l1s):
  registerApqcActors  → catalog (list L1 actors)
  listApqcActors      → catalog (list L1 actors)
  listBpmnTasks       → catalog (list 28 BPMN tasks)
  listProcessGroups   → catalog (list 13 L1 groups)
  getProcessGroup     → catalog (single L1 detail)
  listProcesses       → catalog (L2 subprocesses for L1)
  getProcess          → catalog (single L2 process detail)
  listActivities      → catalog (BPMN activities for L1)
  getActivity         → catalog (single BPMN activity detail)
  runBpmnTask         → run_task (execute BPMN task → OCEL event)
  getApqcCoverage     → coverage (dry-run sweep of all 28 tasks)
  emitApqcEvent       → emit (direct OCEL emit, bypasses L1 fan-out)
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260514_0002"
down_revision: Union[str, Sequence[str], None] = "20260514_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_DID = "did:web:kyber-projector.etzhayyim.com"
_ACTOR_ID = "sys.worker.apqc.pregel"
_PROCESS_ID = "apqc-pregel-orchestrator"

# (vertex_id_suffix, nsid_suffix) — vertex_id = f"bpmn-bind-kyber-{suffix}"
_BINDINGS: list[tuple[str, str]] = [
    ("register-apqc-actors",  "registerApqcActors"),
    ("list-apqc-actors",      "listApqcActors"),
    ("list-bpmn-tasks",       "listBpmnTasks"),
    ("list-process-groups",   "listProcessGroups"),
    ("get-process-group",     "getProcessGroup"),
    ("list-processes",        "listProcesses"),
    ("get-process",           "getProcess"),
    ("list-activities",       "listActivities"),
    ("get-activity",          "getActivity"),
    ("run-bpmn-task",         "runBpmnTask"),
    ("get-apqc-coverage",     "getApqcCoverage"),
    ("emit-apqc-event",       "emitApqcEvent"),
]


def upgrade() -> None:
    for vid_suffix, nsid_suffix in _BINDINGS:
        vertex_id = f"bpmn-bind-kyber-{vid_suffix}"
        nsid = f"com.etzhayyim.kyber.projector.{nsid_suffix}"
        op.execute(f"""
INSERT INTO vertex_bpmn_lexicon_binding
    (vertex_id, owner_did, nsid, bpmn_process_id, status, created_at,
     routing_target, sensitivity_ord, org_id, user_id, actor_id, actor_did)
SELECT
    '{vertex_id}',
    '{_OWNER_DID}',
    '{nsid}',
    '{_PROCESS_ID}',
    'active',
    NOW()::VARCHAR,
    'langgraph',
    1,
    '{_OWNER_DID}',
    '{_OWNER_DID}',
    '{_ACTOR_ID}',
    '{_OWNER_DID}'
WHERE NOT EXISTS (
    SELECT 1 FROM vertex_bpmn_lexicon_binding
    WHERE vertex_id = '{vertex_id}'
)
""")


def downgrade() -> None:
    vertex_ids = ", ".join(
        f"'bpmn-bind-kyber-{vid_suffix}'" for vid_suffix, _ in _BINDINGS
    )
    op.execute(
        f"DELETE FROM vertex_bpmn_lexicon_binding WHERE vertex_id IN ({vertex_ids})"
    )
