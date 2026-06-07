from typing import TypedDict
from langgraph.graph import StateGraph, END

class PipeState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_welding_specs(state: PipeState):
    specs = state.get('spec_data', {})
    # Check for mandatory AWS or ISO weld certification
    compliant = 'weld_cert' in specs and specs['pressure_rating_mpa'] > 0
    return {'is_compliant': compliant}

def route_by_compliance(state: PipeState):
    return 'process' if state['is_compliant'] else 'reject'

graph = StateGraph(PipeState)
graph.add_node('validate', validate_welding_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance, {'process': END, 'reject': END})
graph = graph.compile()
