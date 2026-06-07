from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SpacecraftState(TypedDict):
    part_id: str
    compliance_docs: List[str]
    export_cleared: bool
    approved: bool

def validate_aerospace_docs(state: SpacecraftState):
    state['compliance_docs'] = [d for d in state.get('compliance_docs', []) if 'AS9100' in d]
    return {'approved': len(state['compliance_docs']) > 0}

def check_export_controls(state: SpacecraftState):
    return {'export_cleared': True}

graph = StateGraph(SpacecraftState)
graph.add_node('validate', validate_aerospace_docs)
graph.add_node('export', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()
