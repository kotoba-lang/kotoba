from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MarkerState(TypedDict):
    material: str
    spec_compliance: bool
    validation_logs: List[str]

def validate_marker_spec(state: MarkerState):
    logs = state.get('validation_logs', [])
    if state.get('material') not in ['aluminum', 'plastic', 'vinyl']:
        logs.append('Non-compliant material detected')
        return {'spec_compliance': False, 'validation_logs': logs}
    logs.append('Material verification successful')
    return {'spec_compliance': True, 'validation_logs': logs}

graph = StateGraph(MarkerState)
graph.add_node('validate', validate_marker_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
