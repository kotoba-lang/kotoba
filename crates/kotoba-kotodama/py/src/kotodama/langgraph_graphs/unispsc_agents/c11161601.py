from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class MiningState(TypedDict):
    purity_metrics: dict
    workflow_status: str
    compliance_flags: Annotated[Sequence[str], operator.add]

def validate_purity(state: MiningState):
    metrics = state.get('purity_metrics', {})
    status = 'APPROVED' if metrics.get('purity', 0) > 95 else 'REJECTED'
    return {'workflow_status': status}

def update_compliance(state: MiningState):
    flags = []
    if state.get('workflow_status') == 'REJECTED':
        flags.append('INSUFFICIENT_PURITY')
    return {'compliance_flags': flags}

graph = StateGraph(MiningState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', update_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
