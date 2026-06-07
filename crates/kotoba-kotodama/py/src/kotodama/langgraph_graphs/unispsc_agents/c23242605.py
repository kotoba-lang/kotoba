from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PolishingMachineState(TypedDict):
    machine_id: str
    specs: dict
    approved: bool
    validation_logs: List[str]

def validate_safety_specs(state: PolishingMachineState):
    specs = state.get('specs', {})
    valid = specs.get('safety_certified', False)
    return {'approved': valid, 'validation_logs': ['Safety check passed' if valid else 'Safety certification missing']}

def route_by_validation(state: PolishingMachineState):
    return 'process_order' if state['approved'] else END

def process_order(state: PolishingMachineState):
    return {'validation_logs': state['validation_logs'] + ['Procurement order processed']}

graph = StateGraph(PolishingMachineState)
graph.add_node('safety_check', validate_safety_specs)
graph.add_node('process_order', process_order)
graph.add_edge('safety_check', 'process_order')
graph.add_conditional_edges('safety_check', route_by_validation)
graph.set_entry_point('safety_check')
graph.set_finish_point('process_order')
graph = graph.compile()
