from typing import TypedDict
from langgraph.graph import StateGraph, END

class MachineState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_specs(state: MachineState):
    specs = state.get('spec_data', {})
    # Logic for checking safety and precision requirements
    state['is_compliant'] = specs.get('power_requirements_v', 0) > 0
    return state

graph = StateGraph(MachineState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
