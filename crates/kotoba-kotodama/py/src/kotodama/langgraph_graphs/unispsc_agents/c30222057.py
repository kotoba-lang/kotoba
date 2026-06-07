from typing import TypedDict
from langgraph.graph import StateGraph, END

class PipelineState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_materials(state: PipelineState):
    specs = state.get('spec_data', {})
    # Check for mandatory material grade and pressure rating
    passed = 'Material Grade' in specs and 'Pressure Rating PSI' in specs
    return {'validation_passed': passed}

def check_compliance(state: PipelineState):
    # Business logic for regulatory compliance
    return {'validation_passed': state['validation_passed']}

graph = StateGraph(PipelineState)
graph.add_node('validate', validate_materials)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
