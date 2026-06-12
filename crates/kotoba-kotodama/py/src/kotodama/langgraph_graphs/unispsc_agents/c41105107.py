from typing import TypedDict
from langgraph.graph import StateGraph, END

class PumpState(TypedDict):
    specifications: dict
    validation_status: str

def validate_pump_specs(state: PumpState):
    specs = state.get('specifications', {})
    if 'material' in specs and 'flow_rate' in specs:
        return {'validation_status': 'COMPLIANT'}
    return {'validation_status': 'PENDING_REVIEW'}

graph = StateGraph(PumpState)
graph.add_node('validate', validate_pump_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

# Compile the graph
graph = graph.compile()
