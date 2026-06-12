from typing import TypedDict
from langgraph.graph import StateGraph, END

class JunctionState(TypedDict):
    spec_compliance: bool
    safety_assessment: str
    approval_status: str

def validate_specs(state: JunctionState):
    state['spec_compliance'] = True
    return state

def assess_safety(state: JunctionState):
    state['safety_assessment'] = 'High'
    return state

def finalize_approval(state: JunctionState):
    state['approval_status'] = 'Approved'
    return state

graph = StateGraph(JunctionState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', assess_safety)
graph.add_node('approve', finalize_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
