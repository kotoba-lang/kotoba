from typing import TypedDict
from langgraph.graph import StateGraph, END

class MiningState(TypedDict):
    machine_id: str
    compliance_check: bool
    safety_validation: bool

def validate_compliance(state: MiningState):
    state['compliance_check'] = True
    return state

def safety_gate(state: MiningState):
    state['safety_validation'] = True
    return state

graph = StateGraph(MiningState)
graph.add_node('compliance', validate_compliance)
graph.add_node('safety', safety_gate)
graph.add_edge('compliance', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('compliance')
graph = graph.compile()
