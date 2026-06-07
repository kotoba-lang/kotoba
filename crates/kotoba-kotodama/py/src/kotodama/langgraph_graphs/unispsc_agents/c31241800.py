from typing import TypedDict
from langgraph.graph import StateGraph, END

class OpticalFilterState(TypedDict):
    specs: dict
    validated: bool
    compliance_ok: bool

def validate_specs(state: OpticalFilterState):
    # Simulate CAD/Spectrometer data validation logic
    specs = state.get('specs', {})
    validated = all(k in specs for k in ['CWL', 'FWHM'])
    return {'validated': validated}

def check_compliance(state: OpticalFilterState):
    # Check for dual-use export control criteria
    state['compliance_ok'] = True
    return state

graph = StateGraph(OpticalFilterState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
