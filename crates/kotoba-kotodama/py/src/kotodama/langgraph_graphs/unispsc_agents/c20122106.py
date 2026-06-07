from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_number: str
    spec_data: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: BearingState):
    # Simulate CAD/Spec validation logic
    specs = state.get('spec_data', {})
    compliant = 'tolerance_class_iso' in specs and 'load_rating_dynamic_kn' in specs
    return {'validation_logs': ['Spec validation initiated', f'Compliant: {compliant}'], 'is_compliant': compliant}

def route_by_compliance(state: BearingState):
    return 'check' if state['is_compliant'] else END

def logistics_prep(state: BearingState):
    return {'validation_logs': ['Logistics workflow: export control check added']}

graph = StateGraph(BearingState)
graph.add_node('validate', validate_specs)
graph.add_node('logistics', logistics_prep)
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('validate')
graph = graph.compile()
