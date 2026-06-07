from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingGraphState(TypedDict):
    equipment_id: str
    spec_compliance: bool
    safety_check: bool

def validate_specs(state: WeldingGraphState):
    state['spec_compliance'] = True
    return state

def check_safety(state: WeldingGraphState):
    state['safety_check'] = True
    return state

graph = StateGraph(WeldingGraphState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', check_safety)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
