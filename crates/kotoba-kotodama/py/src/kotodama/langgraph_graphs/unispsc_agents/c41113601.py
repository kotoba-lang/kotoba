from typing import TypedDict
from langgraph.graph import StateGraph, END

class AmmeterState(TypedDict):
    model_number: str
    calibration_status: bool
    is_compliant: bool

def validate_specs(state: AmmeterState):
    # Business logic for ammeter validation
    compliant = state.get('calibration_status') and len(state.get('model_number', '')) > 3
    return {'is_compliant': compliant}

def finalize_order(state: AmmeterState):
    return {'is_compliant': True}

graph = StateGraph(AmmeterState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
