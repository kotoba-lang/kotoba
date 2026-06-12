from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalDeviceState(TypedDict):
    device_id: str
    specifications: dict
    validation_passed: bool

def validate_lifting_specs(state: SurgicalDeviceState):
    specs = state.get('specifications', {})
    capacity = specs.get('capacity', 0)
    validation = capacity > 0 and 'iso_13485' in specs
    return {'validation_passed': validation}

def route_by_validation(state: SurgicalDeviceState):
    return 'process' if state['validation_passed'] else END

graph = StateGraph(SurgicalDeviceState)
graph.add_node('validate', validate_lifting_specs)
graph.add_node('process', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()
