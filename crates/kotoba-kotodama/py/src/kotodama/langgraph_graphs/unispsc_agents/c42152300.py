from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END

class DentalLaserState(TypedDict):
    device_id: str
    validation_stage: str
    safety_check_passed: bool

def validate_specs(state: DentalLaserState):
    # Simulate laser safety compliance checking
    state['safety_check_passed'] = True
    state['validation_stage'] = 'COMPLIANCE_VERIFIED'
    return state

def run_quality_inspection(state: DentalLaserState):
    state['validation_stage'] = 'QUALITY_INSPECTED'
    return state

graph = StateGraph(DentalLaserState)
graph.add_node('ValidateSpecs', validate_specs)
graph.add_node('Inspection', run_quality_inspection)
graph.set_entry_point('ValidateSpecs')
graph.add_edge('ValidateSpecs', 'Inspection')
graph.add_edge('Inspection', END)
graph = graph.compile()
