from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    material_spec: str
    tolerance_check: bool
    approved: bool

def validate_casting_specs(state: CastingState):
    # Perform dimensional and metallurgical validation
    passed = state.get('material_spec') is not None
    return {'tolerance_check': passed}

def final_approval(state: CastingState):
    return {'approved': state['tolerance_check']}

graph = StateGraph(CastingState)
graph.add_node('validate', validate_casting_specs)
graph.add_node('approve', final_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
