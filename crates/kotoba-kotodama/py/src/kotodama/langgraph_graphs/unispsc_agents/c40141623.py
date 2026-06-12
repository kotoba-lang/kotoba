from typing import TypedDict
from langgraph.graph import StateGraph, END

class ValveState(TypedDict):
    pressure_rating: str
    material_spec: str
    is_compliant: bool

def validate_specs(state: ValveState):
    # Business logic for knife gate valve compliance
    compliant = state.get('pressure_rating') in ['PN10', 'PN16', 'CLASS150']
    return {'is_compliant': compliant}

graph = StateGraph(ValveState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
