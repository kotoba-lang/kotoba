from typing import TypedDict
from langgraph.graph import StateGraph, END

class SwitchState(TypedDict):
    part_number: str
    specifications: dict
    approved: bool

def validate_specs(state: SwitchState):
    specs = state.get('specifications', {})
    # Validation logic: Ensure essential safety specs are present
    required = ['IP_rating', 'Voltage_rating']
    state['approved'] = all(k in specs for k in required)
    return state

graph = StateGraph(SwitchState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
