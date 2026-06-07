from typing import TypedDict
from langgraph.graph import StateGraph, END

class VacuumSealerState(TypedDict):
    model_number: str
    spec_check: bool
    safety_verified: bool
    final_approval: bool

def validate_specs(state: VacuumSealerState):
    state['spec_check'] = True
    return state

def verify_safety(state: VacuumSealerState):
    state['safety_verified'] = True
    return state

def finalize(state: VacuumSealerState):
    state['final_approval'] = state['spec_check'] and state['safety_verified']
    return state

graph = StateGraph(VacuumSealerState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', verify_safety)
graph.add_node('finalize', finalize)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
