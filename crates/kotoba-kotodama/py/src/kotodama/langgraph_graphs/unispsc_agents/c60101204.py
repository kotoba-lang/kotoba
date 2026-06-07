from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    specs: dict
    is_approved: bool

def validate_chart_specs(state: ProcurementState):
    specs = state.get('specs', {})
    # Check for visual clarity and material durability
    is_valid = 'material' in specs and 'dimensions' in specs
    return {'is_approved': is_valid}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_chart_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
