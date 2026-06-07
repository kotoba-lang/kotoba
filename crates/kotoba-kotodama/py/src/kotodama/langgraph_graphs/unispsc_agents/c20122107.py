from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_requirements: dict
    validation_logs: List[str]
    is_approved: bool

def validate_bearing_specs(state: ProcurementState):
    specs = state.get('spec_requirements', {})
    logs = []
    if 'load_capacity_kn' not in specs:
        logs.append('Missing required load capacity.')
    return {'validation_logs': logs, 'is_approved': len(logs) == 0}

def approval_node(state: ProcurementState):
    return {'is_approved': state.get('is_approved', False)}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_bearing_specs)
graph.add_node('approve', approval_node)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
