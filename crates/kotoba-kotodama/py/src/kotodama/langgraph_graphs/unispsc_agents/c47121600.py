from typing import TypedDict
from langgraph.graph import StateGraph, END

class FloorMachineState(TypedDict):
    specs: dict
    validation_results: dict
    status: str

def validate_specs(state: FloorMachineState) -> FloorMachineState:
    specs = state.get('specs', {})
    # Logic to validate floor machine technical specs
    valid = all(k in specs for k in ['voltage', 'power'])
    return {'validation_results': {'passed': valid}, 'status': 'validated' if valid else 'failed'}

def route_by_validation(state: FloorMachineState) -> str:
    return 'end' if state['status'] == 'validated' else 'end'

graph = StateGraph(FloorMachineState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
